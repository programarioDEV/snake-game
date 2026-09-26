from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields

import pygame

from ..agents import AggressiveAIController, BaseAgent, DecisionTrace
from ..core import Cell, Grid, SnakeId
from ..engine import REPETITION_LIMIT, GameResult, MatchSeries, SimulationEngine
from .board import BoardRenderer, OverlayToggles
from .hud import HudModel, HudPanel, SnakeRow
from .series_panel import SeriesPanel
from .theme import RGB, Theme, font, mix

HUD_WIDTH = 340
SERIES_WIDTH = 270
MIN_HEIGHT = 640
VEIL_ALPHA = 170
_SWATCH = 24


def default_focus(agents: Sequence[BaseAgent]) -> SnakeId:
    """First agent that explains itself, so the overlays have something to show."""
    for index, agent in enumerate(agents):
        if isinstance(agent, AggressiveAIController):
            return SnakeId(index)
    return SnakeId(0)


def decision_traces(engine: SimulationEngine) -> dict[SnakeId, DecisionTrace]:
    record = engine.last
    if record is None:
        return {}
    return {sid: d.trace for sid, d in record.decisions.items() if d.trace is not None}


def match_result(engine: SimulationEngine, labels: Sequence[str]) -> tuple[str, str]:
    """Banner title and caption (death causes or the draw rule that fired) of a finished match."""
    if engine.ending is GameResult.DRAW_CYCLE:
        caption = f"same position {REPETITION_LIMIT} times, repeating every {engine.cycle_period} ticks"
        return "DRAW: LOOP DETECTED", caption
    if engine.ending is GameResult.DRAW_STALEMATE:
        return "DRAW: STALEMATE", f"no food eaten for {engine.ticks_without_food} ticks"
    winner = engine.winner
    title = "DRAW" if winner is None else f"{labels[winner].upper()} WINS"
    causes = ", ".join(f"#{d.snake_id + 1} {d.cause.name}" for d in engine.deaths) or "tick limit"
    return title, causes


class SceneRenderer:
    """Composes board, banner, HUD and the optional series column onto any target surface."""

    def __init__(
        self,
        grid: Grid,
        labels: Sequence[str],
        *,
        cell: int,
        theme: Theme,
        series_column: bool = False,
    ) -> None:
        self.theme = theme
        self.labels = tuple(labels)
        colors = {SnakeId(i): color for i, color in enumerate(theme.snakes)}
        self.board = BoardRenderer(grid, cell, theme, colors)
        board_w, board_h = self.board.size
        height = max(board_h, MIN_HEIGHT)
        self.board_origin = (0, (height - board_h) // 2)
        self.hud = HudPanel((HUD_WIDTH, height), theme)
        self.series_panel = SeriesPanel((SERIES_WIDTH, height), theme) if series_column else None
        self.size = (board_w + HUD_WIDTH + (SERIES_WIDTH if series_column else 0), height)
        self.banner_font = font(34, bold=True)
        self.caption_font = font(15)
        self.veil = pygame.Surface(self.board.size, pygame.SRCALPHA)
        self.veil.fill((*theme.background, VEIL_ALPHA))
        self.ribbon = pygame.Surface((self.board.size[0], 30), pygame.SRCALPHA)
        self.ribbon.fill((*theme.background, 215))

    def draw(
        self,
        target: pygame.Surface,
        engine: SimulationEngine,
        *,
        focus: SnakeId,
        toggles: OverlayToggles,
        tick_rate: float,
        fps: int = 0,
        paused: bool = False,
        banner: tuple[str, str] | None = None,
        series: MatchSeries | None = None,
        show_timing: bool = True,
    ) -> None:
        state = engine.state
        record = engine.last
        traces = decision_traces(engine)
        rival = next(s.id for s in state.snakes if s.id != focus)

        target.fill(self.theme.background)
        target.blit(self.board.render(state, focus, traces, toggles), self.board_origin)
        if banner is not None:
            self.draw_banner(target, *banner)

        model = HudModel(
            tick=state.tick,
            tick_rate=tick_rate,
            fps=fps,
            paused=paused,
            rows=tuple(SnakeRow(self.labels[s.id], s.length, s.alive) for s in state.snakes),
            focus=focus,
            rival=rival,
            trace=traces.get(focus),
            decide_ms=record.compute_ms.get(focus) if record is not None else None,
            tick_ms=record.tick_ms if record is not None else None,
            stats=engine.stats[focus],
            toggles=toggles.as_tuple(),
            show_timing=show_timing,
        )
        hud_x = self.board.size[0]
        target.blit(self.hud.render(model), (hud_x, 0))
        if series is not None and self.series_panel is not None:
            target.blit(self.series_panel.render(series, self.labels, focus), (hud_x + HUD_WIDTH, 0))

    def draw_banner(self, target: pygame.Surface, title: str, caption: str) -> None:
        target.blit(self.veil, self.board_origin)
        cx = self.board_origin[0] + self.board.size[0] // 2
        cy = self.board_origin[1] + self.board.size[1] // 2
        label = self.banner_font.render(title, True, self.theme.text)
        target.blit(label, label.get_rect(center=(cx, cy - 14)))
        sub = self.caption_font.render(caption, True, self.theme.text_dim)
        target.blit(sub, sub.get_rect(center=(cx, cy + 20)))

    def draw_replay(self, target: pygame.Surface, cell: Cell, caption: str) -> None:
        """Instant-replay marker: rings around the sealed chokepoint and a caption ribbon."""
        t = self.theme
        x, y = self.board.center(cell)
        center = (x + self.board_origin[0], y + self.board_origin[1])
        size = self.board.cell
        for radius, width in ((size + 4, 3), (2 * size + 2, 2), (3 * size, 1)):
            pygame.draw.circle(target, t.lethal, center, radius, width)
        target.blit(self.ribbon, self.board_origin)
        label = self.caption_font.render(f"REPLAY  LETHAL CUT  {caption}", True, t.lethal)
        target.blit(label, label.get_rect(midleft=(self.board_origin[0] + 10, self.board_origin[1] + 15)))

    def palette_swatches(self, width: int) -> pygame.Surface:
        """Every theme color plain, veiled and as antialiased text, to seed palette quantization."""
        t = self.theme
        colors: list[RGB] = [*t.snakes, *t.modes.values()]
        for f in fields(t):
            value = getattr(t, f.name)
            if isinstance(value, tuple) and len(value) == 3 and all(isinstance(v, int) for v in value):
                colors.append(value)
        backgrounds = (t.panel, t.board, mix(t.board, t.background, VEIL_ALPHA / 255))
        per_row = max(1, width // _SWATCH)
        rows = -(-len(colors) // per_row)
        block = _SWATCH * len(backgrounds) * 2
        strip = pygame.Surface((width, rows * block))
        strip.fill(t.panel)
        small = font(12)
        for index, color in enumerate(colors):
            x, y = (index % per_row) * _SWATCH, (index // per_row) * block
            for row, background in enumerate(backgrounds):
                top = y + row * _SWATCH * 2
                pygame.draw.rect(strip, background, (x, top, _SWATCH, _SWATCH * 2))
                pygame.draw.rect(strip, color, (x + 2, top + 2, 8, 8))
                veiled = mix(color, t.background, VEIL_ALPHA / 255)
                pygame.draw.rect(strip, veiled, (x + 12, top + 2, 8, 8))
                strip.blit(small.render("Ag", True, color), (x + 2, top + 14))
        return strip
