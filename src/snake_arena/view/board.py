from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields

import pygame

from ..agents import DecisionTrace
from ..core import Cell, GameState, Grid, Snake, SnakeId
from .theme import RGB, Theme, mix


@dataclass(slots=True)
class OverlayToggles:
    voronoi: bool = True
    path: bool = True
    intercept: bool = True
    chokepoints: bool = True

    def flip(self, name: str) -> None:
        setattr(self, name, not getattr(self, name))

    def flip_all(self) -> None:
        value = not any(self.as_tuple())
        for f in fields(self):
            setattr(self, f.name, value)

    def as_tuple(self) -> tuple[bool, ...]:
        return (self.voronoi, self.path, self.intercept, self.chokepoints)


class BoardRenderer:
    """Draws the arena into one reusable surface; static and per-tick layers are cached."""

    def __init__(
        self, grid: Grid, cell: int, theme: Theme, colors: Mapping[SnakeId, RGB]
    ) -> None:
        self.grid = grid
        self.cell = cell
        self.theme = theme
        self.colors = dict(colors)
        self.size = (grid.width * cell, grid.height * cell)
        self.surface = pygame.Surface(self.size)
        self._base = self._build_base()
        self._tiles: dict[int, pygame.Surface] = {
            sid: self._tint(color) for sid, color in self.colors.items()
        }
        self._territory = pygame.Surface(self.size, pygame.SRCALPHA)
        self._territory_source: DecisionTrace | None = None

    def render(
        self,
        state: GameState,
        focus: SnakeId,
        traces: Mapping[SnakeId, DecisionTrace],
        toggles: OverlayToggles,
    ) -> pygame.Surface:
        """Voronoi from any agent (mirror agents agree); route, intercept and cuts from the focus."""
        surface = self.surface
        surface.blit(self._base, (0, 0))
        territory = self._territory_trace(focus, traces)
        if territory is not None and territory.territory is not None and toggles.voronoi:
            if territory is not self._territory_source:
                self._rebuild_territory(territory.territory, state)
                self._territory_source = territory
            surface.blit(self._territory, (0, 0))

        self._draw_food(state.food)
        trace = traces.get(focus)
        rival = next(s for s in state.snakes if s.id != focus)
        if trace is not None and toggles.chokepoints:
            self._draw_chokepoints(trace.chokepoints, rival.length)
        for snake in sorted(state.snakes, key=lambda s: s.alive):
            self._draw_snake(snake)

        focused = state.snake(focus)
        if trace is not None and focused.alive:
            if toggles.intercept:
                self._draw_intercept(trace, focused.head, self.colors.get(rival.id, self.theme.text))
            if toggles.path:
                self._draw_path(trace.planned_path, focused.head)
        return surface

    @staticmethod
    def _territory_trace(
        focus: SnakeId, traces: Mapping[SnakeId, DecisionTrace]
    ) -> DecisionTrace | None:
        focused = traces.get(focus)
        if focused is not None and focused.territory is not None:
            return focused
        return next((t for t in traces.values() if t.territory is not None), None)

    def center(self, cell: Cell) -> tuple[int, int]:
        x, y = self.grid.xy(cell)
        half = self.cell // 2
        return x * self.cell + half, y * self.cell + half

    def _rect(self, cell: Cell, inset: int) -> pygame.Rect:
        x, y = self.grid.xy(cell)
        side = self.cell - 2 * inset
        return pygame.Rect(x * self.cell + inset, y * self.cell + inset, side, side)

    def _build_base(self) -> pygame.Surface:
        base = pygame.Surface(self.size)
        base.fill(self.theme.board)
        width, height = self.size
        for x in range(0, width, self.cell):
            pygame.draw.line(base, self.theme.grid_line, (x, 0), (x, height))
        for y in range(0, height, self.cell):
            pygame.draw.line(base, self.theme.grid_line, (0, y), (width, y))
        for cell in self.grid.obstacles:
            pygame.draw.rect(base, self.theme.obstacle, self._rect(cell, 1), border_radius=3)
        return base

    def _tint(self, color: RGB) -> pygame.Surface:
        tile = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
        tile.fill((*color, self.theme.territory_alpha))
        return tile

    def _rebuild_territory(self, territory: Sequence[int], state: GameState) -> None:
        layer = self._territory
        layer.fill((0, 0, 0, 0))
        width, height, size = self.grid.width, self.grid.height, self.cell
        tiles = self._tiles
        layer.fblits(
            [
                (tiles[owner], ((i % width) * size, (i // width) * size))
                for i, owner in enumerate(territory)
                if owner in tiles
            ]
        )
        blocked = state.occupied() | self.grid.obstacles
        color = (*self.theme.text, self.theme.frontier_alpha)
        for i, owner in enumerate(territory):
            if i in blocked:
                continue
            x, y = i % width, i // width
            right, below = i + 1, i + width
            if x + 1 < width and right not in blocked and _borders(owner, territory[right]):
                pygame.draw.line(layer, color, ((x + 1) * size, y * size), ((x + 1) * size, (y + 1) * size))
            if y + 1 < height and below not in blocked and _borders(owner, territory[below]):
                pygame.draw.line(layer, color, (x * size, (y + 1) * size), ((x + 1) * size, (y + 1) * size))

    def _draw_food(self, food: frozenset[Cell]) -> None:
        radius = max(3, round(self.cell * 0.3))
        shine = mix(self.theme.food, (255, 255, 255), 0.6)
        for cell in food:
            cx, cy = self.center(cell)
            pygame.draw.circle(self.surface, self.theme.food, (cx, cy), radius)
            pygame.draw.circle(self.surface, shine, (cx - radius // 3, cy - radius // 3), max(1, radius // 3))

    def _draw_snake(self, snake: Snake) -> None:
        base = self.colors.get(snake.id, self.theme.text) if snake.alive else self.theme.dead
        body = snake.body
        inset = max(2, self.cell // 7)
        radius = max(2, self.cell // 4)
        for index in range(len(body) - 1, 0, -1):
            shade = mix(base, self.theme.board, 0.55 * index / len(body))
            joint = self._rect(body[index], inset).union(self._rect(body[index - 1], inset))
            pygame.draw.rect(self.surface, shade, joint, border_radius=radius)
        head = self._rect(body[0], 1)
        pygame.draw.rect(self.surface, mix(base, (255, 255, 255), 0.2), head, border_radius=radius)
        if snake.alive:
            dx, dy = snake.direction.delta
            cx, cy = head.center
            reach, spread = self.cell * 0.18, self.cell * 0.2
            for side in (-1, 1):
                eye = (cx + dx * reach - dy * spread * side, cy + dy * reach + dx * spread * side)
                pygame.draw.circle(self.surface, self.theme.board, eye, max(2, self.cell // 9))

    def _draw_chokepoints(self, chokepoints: Mapping[Cell, int], rival_length: int) -> None:
        r = max(3, round(self.cell * 0.26))
        for cell, room in chokepoints.items():
            cx, cy = self.center(cell)
            diamond = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
            if room < rival_length:
                pygame.draw.polygon(self.surface, self.theme.lethal, diamond)
                pygame.draw.circle(self.surface, self.theme.lethal, (cx, cy), r + 4, 1)
            else:
                pygame.draw.polygon(self.surface, self.theme.chokepoint, diamond, 2)

    def _draw_intercept(self, trace: DecisionTrace, ai_head: Cell, rival_color: RGB) -> None:
        for cell in trace.opponent_path:
            pygame.draw.circle(self.surface, rival_color, self.center(cell), max(2, self.cell // 10))
        if trace.opponent_goal is not None:
            pygame.draw.circle(self.surface, rival_color, self.center(trace.opponent_goal), round(self.cell * 0.48), 2)
        if trace.intercept_point is not None:
            target = self.center(trace.intercept_point)
            _dashed_line(self.surface, self.theme.intercept, self.center(ai_head), target, 2, 6)
            r = round(self.cell * 0.42)
            cx, cy = target
            pygame.draw.circle(self.surface, self.theme.intercept, target, r, 2)
            pygame.draw.line(self.surface, self.theme.intercept, (cx - r - 3, cy), (cx + r + 3, cy), 1)
            pygame.draw.line(self.surface, self.theme.intercept, (cx, cy - r - 3), (cx, cy + r + 3), 1)

    def _draw_path(self, path: Sequence[Cell], ai_head: Cell) -> None:
        cells = list(path[1:] if path and path[0] == ai_head else path)
        if not cells:
            return
        points = [self.center(ai_head), *(self.center(c) for c in cells)]
        pygame.draw.lines(self.surface, self.theme.path, False, points, 3)
        end = pygame.Rect(0, 0, self.cell // 3, self.cell // 3)
        end.center = points[-1]
        pygame.draw.rect(self.surface, self.theme.path, end)


def _borders(a: int, b: int) -> bool:
    return a != b and (a >= 0 or b >= 0)


def _dashed_line(
    surface: pygame.Surface,
    color: RGB,
    start: tuple[int, int],
    end: tuple[int, int],
    width: int,
    dash: int,
) -> None:
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        return
    for i in range(0, int(length // dash) + 1, 2):
        a, b = i * dash / length, min((i + 1) * dash / length, 1.0)
        pygame.draw.line(
            surface,
            color,
            (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
            (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b),
            width,
        )
