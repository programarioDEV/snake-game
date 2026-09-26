from __future__ import annotations

from dataclasses import dataclass

import pygame

from ..agents import DecisionTrace, TacticalMode
from ..core import SnakeId
from ..engine import AgentStats
from .theme import RGB, Theme, font, mix

_KEYS = (("V", "Voronoi"), ("P", "A* path"), ("I", "intercept"), ("C", "chokepoints"))


@dataclass(frozen=True, slots=True)
class SnakeRow:
    label: str
    length: int
    alive: bool


@dataclass(frozen=True, slots=True)
class HudModel:
    tick: int
    tick_rate: float
    fps: int
    paused: bool
    rows: tuple[SnakeRow, ...]
    focus: SnakeId
    rival: SnakeId
    trace: DecisionTrace | None
    decide_ms: float | None
    tick_ms: float | None
    stats: AgentStats
    toggles: tuple[bool, ...]
    show_timing: bool = True


class HudPanel:
    """Live reasoning of the focused agent; re-rendered only when its inputs change."""

    def __init__(self, size: tuple[int, int], theme: Theme) -> None:
        self.surface = pygame.Surface(size)
        self.theme = theme
        self.title = font(19, bold=True)
        self.body = font(14)
        self.small = font(12)
        self.pad = 18
        self._key: object = None

    def render(self, m: HudModel) -> pygame.Surface:
        key = (m.tick, m.fps, m.paused, m.toggles, m.tick_rate, m.rows, m.focus, id(m.trace))
        if key == self._key:
            return self.surface
        self._key = key
        t = self.theme
        self.surface.fill(t.panel)
        pygame.draw.line(self.surface, t.panel_rule, (0, 0), (0, self.surface.get_height()))

        y = self._line("SNAKE ARENA // AI DEBUG", self.title, t.text, 14)
        status = f"tick {m.tick}  {m.tick_rate:.1f} t/s  {m.fps or '--'} fps"
        y = self._line(status + ("  PAUSED" if m.paused else ""), self.small, t.text_dim, y + 2)
        y = self._rule(y)
        for index, row in enumerate(m.rows):
            y = self._snake_row(row, index, index == m.focus, y)
        y = self._rule(y)

        trace = m.trace
        if trace is None:
            y = self._line(self._no_trace_reason(m), self.small, t.text_dim, y)
            self._line("[1] / [2] switch the inspected snake", self.small, t.text_dim, y)
            self._footer(m.toggles)
            return self.surface

        y = self._header("TACTICAL STATE", y)
        y = self._badge(trace.mode, y)
        for text in self._wrap(trace.rationale, self.small):
            y = self._line(text, self.small, t.text, y)
        y = self._rule(y + 2)

        y = self._header("UTILITY", y)
        for mode in TacticalMode:
            y = self._utility_bar(mode, trace.utilities.get(mode, 0.0), mode is trace.mode, y)
        y = self._rule(y + 2)

        y = self._header("PERFORMANCE", y)
        if m.show_timing:
            s = m.stats
            decide = f"{m.decide_ms:.2f}" if m.decide_ms is not None else "-"
            y = self._pair("decide ms", f"{decide}  avg {s.mean_ms:.2f}  max {s.max_ms:.2f}", y)
            y = self._pair("tick ms", f"{m.tick_ms:.2f}" if m.tick_ms is not None else "-", y)
        else:
            y = self._pair("timing", "omitted: bit-exact replay", y) + self.small.get_linesize()
        y = self._pair("A* nodes", str(trace.nodes_expanded), y)
        cost = f"{trace.path_cost:.1f}" if trace.path_cost is not None else "-"
        y = self._pair("path", f"{len(trace.planned_path)} cells  cost {cost}", y)
        y = self._rule(y + 2)

        y = self._header("TERRITORY", y)
        y = self._territory(trace, m, y)
        rival_length = m.rows[m.rival].length
        lethal = sum(1 for room in trace.chokepoints.values() if room < rival_length)
        y = self._pair("chokepoints", f"{len(trace.chokepoints)}  ({lethal} lethal)", y)
        y = self._rule(y + 2)
        self._legend(self.theme.snakes[m.rival], y)
        self._footer(m.toggles)
        return self.surface

    @staticmethod
    def _no_trace_reason(m: HudModel) -> str:
        row = m.rows[m.focus]
        if m.tick == 0:
            return "waiting for the first decision..."
        if not row.alive:
            return f"{row.label} is out"
        return f"{row.label} publishes no trace"

    def _line(self, text: str, font: pygame.font.Font, color: RGB, y: int, x: int | None = None) -> int:
        self.surface.blit(font.render(text, True, color), (self.pad if x is None else x, y))
        return y + font.get_linesize()

    def _header(self, text: str, y: int) -> int:
        return self._line(text, self.small, self.theme.text_dim, y) + 2

    def _rule(self, y: int) -> int:
        width = self.surface.get_width()
        pygame.draw.line(self.surface, self.theme.panel_rule, (self.pad, y + 6), (width - self.pad, y + 6))
        return y + 13

    def _pair(self, label: str, value: str, y: int) -> int:
        self._line(label, self.small, self.theme.text_dim, y)
        return self._line(value, self.small, self.theme.text, y, self.pad + 96)

    def _snake_row(self, row: SnakeRow, index: int, focused: bool, y: int) -> int:
        t = self.theme
        color = t.snakes[index] if row.alive else t.dead
        if focused:
            pygame.draw.polygon(self.surface, t.text, [(4, y + 4), (10, y + 9), (4, y + 14)])
        pygame.draw.rect(self.surface, color, pygame.Rect(self.pad, y + 4, 10, 10), border_radius=2)
        self._line(row.label, self.body, t.text if focused else t.text_dim, y, self.pad + 18)
        state = f"len {row.length}" if row.alive else f"len {row.length} OUT"
        return self._line(state, self.body, color if row.alive else t.text_dim, y, self.pad + 206)

    def _badge(self, mode: TacticalMode, y: int) -> int:
        label = self.body.render(f" {mode.value} ", True, self.theme.panel)
        box = label.get_rect(topleft=(self.pad, y)).inflate(10, 6)
        box.topleft = (self.pad, y)
        pygame.draw.rect(self.surface, self.theme.modes[mode], box, border_radius=4)
        self.surface.blit(label, label.get_rect(center=box.center))
        return y + box.height + 6

    def _utility_bar(self, mode: TacticalMode, value: float, active: bool, y: int) -> int:
        color = self.theme.modes[mode]
        label_color = color if active else self.theme.text_dim
        self._line(mode.value, self.small, label_color, y)
        track = pygame.Rect(self.pad + 96, y + 3, 150, 9)
        pygame.draw.rect(self.surface, self.theme.panel_rule, track, border_radius=3)
        fill = track.copy()
        fill.width = round(track.width * max(0.0, min(1.0, value)))
        if fill.width:
            shade = color if active else mix(color, self.theme.panel, 0.55)
            pygame.draw.rect(self.surface, shade, fill, border_radius=3)
        return self._line(f"{value:.2f}", self.small, label_color, y, track.right + 10)

    def _territory(self, trace: DecisionTrace, m: HudModel, y: int) -> int:
        ratio = trace.territory_ratio or 0.0
        bar = pygame.Rect(self.pad, y + 2, self.surface.get_width() - 2 * self.pad, 12)
        pygame.draw.rect(self.surface, self.theme.snakes[m.rival], bar, border_radius=3)
        mine = bar.copy()
        mine.width = round(bar.width * ratio)
        if mine.width:
            pygame.draw.rect(self.surface, self.theme.snakes[m.focus], mine, border_radius=3)
        y = bar.bottom + 6
        cells = trace.territory or ()
        own = sum(1 for owner in cells if owner == m.focus)
        rival = sum(1 for owner in cells if owner == m.rival)
        return self._pair("control", f"{ratio:.0%}  ({own} vs {rival} cells)", y)

    def _legend(self, rival_color: RGB, y: int) -> None:
        t = self.theme
        y = self._header("LEGEND", y)
        step = self.small.get_linesize() + 3
        x, text_x = self.pad, self.pad + 30
        s = self.surface
        for offset in range(0, 22, 6):
            pygame.draw.line(s, t.intercept, (x + offset, y + 7), (x + offset + 3, y + 7), 2)
        self._line("intercept vector -> cut point", self.small, t.text, y, text_x)
        y += step
        pygame.draw.line(s, t.path, (x, y + 7), (x + 22, y + 7), 3)
        self._line("A* planned route", self.small, t.text, y, text_x)
        y += step
        for offset in range(0, 16, 5):
            pygame.draw.circle(s, rival_color, (x + 2 + offset, y + 7), 2)
        pygame.draw.circle(s, rival_color, (x + 22, y + 7), 6, 2)
        self._line("predicted rival route / goal", self.small, t.text, y, text_x)
        y += step
        cx, cy = x + 11, y + 7
        pygame.draw.polygon(s, t.chokepoint, [(cx, cy - 6), (cx + 6, cy), (cx, cy + 6), (cx - 6, cy)], 2)
        self._line("chokepoint (articulation point)", self.small, t.text, y, text_x)
        y += step
        cy = y + 7
        pygame.draw.polygon(s, t.lethal, [(cx, cy - 6), (cx + 6, cy), (cx, cy + 6), (cx - 6, cy)])
        self._line("lethal cut: room < rival length", self.small, t.text, y, text_x)

    def _footer(self, toggles: tuple[bool, ...]) -> None:
        t = self.theme
        line = self.small.get_linesize()
        y = self.surface.get_height() - 4 * line - 14
        self._rule(y - 14)
        for index, ((key, label), on) in enumerate(zip(_KEYS, toggles)):
            x = self.pad + (index % 2) * 150
            row = y + (index // 2) * line
            self._line(f"[{key}] {label}", self.small, t.text if on else t.text_dim, row, x)
        self._line("[SPACE] pause [N] step [R] reset [+/-]", self.small, t.text_dim, y + 2 * line)
        self._line("[1]/[2] focus  [TAB] all  [ESC] quit", self.small, t.text_dim, y + 3 * line)

    def _wrap(self, text: str, font: pygame.font.Font) -> list[str]:
        limit = self.surface.get_width() - 2 * self.pad
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= limit or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines[:3]
