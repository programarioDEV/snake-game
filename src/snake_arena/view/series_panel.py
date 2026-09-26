from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import pygame

from ..agents import TacticalMode
from ..core import SnakeId
from ..engine import MatchSeries
from .theme import RGB, Theme, font

_RECENT = 12


class SeriesPanel:
    """Scoreboard column for AI-vs-AI showcases."""

    def __init__(self, size: tuple[int, int], theme: Theme) -> None:
        self.surface = pygame.Surface(size)
        self.theme = theme
        self.title = font(19, bold=True)
        self.body = font(14)
        self.small = font(12)
        self.pad = 16
        self._key: object = None

    def render(self, series: MatchSeries, labels: Sequence[str], focus: SnakeId) -> pygame.Surface:
        wait = series.restart_in
        key = (
            series.stats.matches,
            series.round,
            series.finished,
            None if wait is None else round(wait, 1),
            focus,
            series.engine.state.tick,
        )
        if key == self._key:
            return self.surface
        self._key = key
        t = self.theme
        stats = series.stats
        self.surface.fill(t.panel)
        pygame.draw.line(self.surface, t.panel_rule, (0, 0), (0, self.surface.get_height()))

        y = self._line("SERIES", self.title, t.text, 14)
        total = str(series.rounds) if series.rounds is not None else "endless"
        y = self._line(f"round {series.round} / {total}", self.small, t.text_dim, y + 2)
        if series.finished:
            status, color = "series complete", t.intercept
        elif wait is not None:
            status, color = f"next round in {wait:.1f} s", t.intercept
        else:
            status, color = "match in progress", t.text_dim
        y = self._rule(self._line(status, self.small, color, y))

        y = self._header("SCORE", y)
        for index, label in enumerate(labels):
            sid = SnakeId(index)
            y = self._score(label, index, stats.wins[sid], stats.win_rate(sid), sid == focus, y)
        y = self._pair("draws", f"{stats.draws}  ({stats.draw_rate:.0%})", y)
        y = self._pair("matches", str(stats.matches), y)
        mean = f"{stats.mean_ticks:.0f}" if stats.matches else "-"
        y = self._rule(self._pair("avg ticks", mean, y))

        y = self._header("TACTIC MIX (live)", y)
        shown = False
        for index, label in enumerate(labels):
            mix = series.mode_mix(SnakeId(index))
            if sum(mix.values()):
                y = self._tactics(label, index, mix, y)
                shown = True
        if not shown:
            y = self._line("no offensive agent yet", self.small, t.text_dim, y)
        y = self._rule(y)

        y = self._header(f"LAST {_RECENT} RESULTS", y)
        self._recent(stats.results[-_RECENT:], y)
        return self.surface

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
        return self._line(value, self.small, self.theme.text, y, self.pad + 90)

    def _swatch(self, index: int, y: int) -> None:
        rect = pygame.Rect(self.pad, y + 4, 10, 10)
        pygame.draw.rect(self.surface, self.theme.snakes[index], rect, border_radius=2)

    def _score(self, label: str, index: int, wins: int, rate: float, focused: bool, y: int) -> int:
        t = self.theme
        if focused:
            pygame.draw.polygon(self.surface, t.text, [(4, y + 4), (10, y + 9), (4, y + 14)])
        self._swatch(index, y)
        y = self._line(label, self.body, t.text if focused else t.text_dim, y, self.pad + 18)
        self._line(f"{wins} W  {rate:>4.0%}", self.small, t.text, y, self.pad + 18)
        track = pygame.Rect(self.pad + 110, y + 3, self.surface.get_width() - self.pad * 2 - 110, 9)
        pygame.draw.rect(self.surface, t.panel_rule, track, border_radius=3)
        if rate > 0:
            fill = track.copy()
            fill.width = max(2, round(track.width * rate))
            pygame.draw.rect(self.surface, t.snakes[index], fill, border_radius=3)
        return y + self.small.get_linesize() + 4

    def _tactics(self, label: str, index: int, mix: Counter[TacticalMode], y: int) -> int:
        t = self.theme
        self._swatch(index, y)
        y = self._line(label, self.small, t.text, y, self.pad + 18)
        total = sum(mix.values())
        bar = pygame.Rect(self.pad, y + 2, self.surface.get_width() - 2 * self.pad, 10)
        x, cumulative = bar.left, 0
        for mode in TacticalMode:
            cumulative += mix[mode]
            end = bar.left + round(bar.width * cumulative / total)
            if end > x:
                pygame.draw.rect(self.surface, t.modes[mode], pygame.Rect(x, bar.top, end - x, bar.height))
            x = end
        y = bar.bottom + 4
        modes = list(TacticalMode)
        for pair in (modes[:2], modes[2:]):
            text = "  ".join(f"{m.value} {mix[m] / total:.0%}" for m in pair)
            y = self._line(text, self.small, t.text_dim, y)
        return y + 4

    def _recent(self, results: Sequence[SnakeId | None], y: int) -> None:
        size, gap = 14, 5
        for position, winner in enumerate(results):
            color = self.theme.dead if winner is None else self.theme.snakes[winner]
            rect = pygame.Rect(self.pad + position * (size + gap), y + 2, size, size)
            pygame.draw.rect(self.surface, color, rect, border_radius=3)
        if not results:
            self._line("no finished matches yet", self.small, self.theme.text_dim, y)
