from __future__ import annotations

from collections.abc import Sequence

from ..core import Cell, Direction, GameState, Grid, Snake

BLOCKED = 1 << 30


def release_times(state: GameState) -> list[int]:
    """Moves until a head may enter each cell: 0 if free now, k once the segment there has left."""
    free_at = [0] * state.grid.size
    for cell in state.grid.obstacles:
        free_at[cell] = BLOCKED
    for snake in state.alive_snakes():
        vacate = snake.length + snake.pending_growth
        for index, cell in enumerate(snake.body):
            free_at[cell] = vacate - index
    return free_at


def candidate_moves(grid: Grid, snake: Snake) -> list[tuple[Direction, Cell | None]]:
    return [
        (direction, grid.step(snake.head, direction))
        for direction in Direction
        if snake.length == 1 or direction != snake.direction.opposite
    ]


def threat_cells(grid: Grid, snake: Snake, free_at: Sequence[int]) -> frozenset[Cell]:
    """Cells the snake's head can legally occupy on the next tick."""
    return frozenset(
        cell for _, cell in candidate_moves(grid, snake) if cell is not None and free_at[cell] <= 1
    )
