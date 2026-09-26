from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from ..core import Direction, GameState, Grid, Snake, SnakeId, spawn_food


def open_arena(width: int, height: int) -> frozenset[tuple[int, int]]:
    return frozenset()


def cross_arena(width: int, height: int) -> frozenset[tuple[int, int]]:
    """Plus-shaped walls around a central plaza: four rooms joined through narrow passages."""
    cx, cy, plaza, margin = width // 2, height // 2, 3, 3
    vertical = [*range(margin, cy - plaza), *range(cy + plaza + 1, height - margin)]
    horizontal = [*range(margin, cx - plaza), *range(cx + plaza + 1, width - margin)]
    return frozenset([(cx, y) for y in vertical] + [(x, cy) for x in horizontal])


ARENAS: dict[str, Callable[[int, int], frozenset[tuple[int, int]]]] = {
    "open": open_arena,
    "cross": cross_arena,
}


@dataclass(frozen=True, slots=True)
class MatchConfig:
    width: int = 31
    height: int = 31
    arena: str = "cross"
    food_count: int = 3
    growth_per_food: int = 1
    initial_length: int = 4
    max_ticks: int = 5000
    seed: int = 0

    def build_grid(self) -> Grid:
        probe = Grid(self.width, self.height)
        walls = ARENAS[self.arena](self.width, self.height)
        return Grid(self.width, self.height, frozenset(probe.cell(x, y) for x, y in walls))

    def initial_state(self, rng: random.Random) -> GameState:
        grid = self.build_grid()
        w, h = self.width, self.height
        snakes = (
            Snake.spawn(grid, SnakeId(0), grid.cell(w // 4, 3 * h // 4), Direction.UP, self.initial_length),
            Snake.spawn(grid, SnakeId(1), grid.cell(3 * w // 4, h // 4), Direction.DOWN, self.initial_length),
        )
        return spawn_food(GameState(grid, snakes), rng, self.food_count)
