from __future__ import annotations

from dataclasses import dataclass

from .grid import Cell, Grid
from .snake import Snake, SnakeId


@dataclass(frozen=True, slots=True)
class GameState:
    """Immutable, hashable snapshot of a match; snakes[i].id == i."""

    grid: Grid
    snakes: tuple[Snake, ...]
    food: frozenset[Cell] = frozenset()
    tick: int = 0

    def __post_init__(self) -> None:
        for index, snake in enumerate(self.snakes):
            if snake.id != index:
                raise ValueError(f"snake at index {index} has id {snake.id}")

    def snake(self, snake_id: SnakeId) -> Snake:
        return self.snakes[snake_id]

    def alive_snakes(self) -> tuple[Snake, ...]:
        return tuple(s for s in self.snakes if s.alive)

    def opponents(self, snake_id: SnakeId) -> tuple[Snake, ...]:
        return tuple(s for s in self.snakes if s.alive and s.id != snake_id)

    @property
    def is_over(self) -> bool:
        needed = 2 if len(self.snakes) > 1 else 1
        return len(self.alive_snakes()) < needed

    @property
    def winner(self) -> SnakeId | None:
        """Last snake standing once the match is over; None while running or on a draw."""
        if not self.is_over:
            return None
        alive = self.alive_snakes()
        return alive[0].id if len(alive) == 1 else None

    def occupied(self) -> frozenset[Cell]:
        cells: set[Cell] = set()
        for snake in self.snakes:
            if snake.alive:
                cells.update(snake.cells)
        return frozenset(cells)

    def free_cells(self) -> list[Cell]:
        """Open cells without a live snake or food, in ascending order for deterministic sampling."""
        taken = self.occupied() | self.food
        return [cell for cell in self.grid.open_cells() if cell not in taken]
