from __future__ import annotations

from ..analysis import (
    UNREACHED,
    candidate_moves,
    reach_times,
    reachable_count,
    release_times,
    threat_cells,
)
from ..core import Cell, Direction, GameState, SnakeId
from .base import BaseAgent, Decision


class GreedyAgent(BaseAgent):
    """Benchmark baseline: nearest food, no pockets smaller than itself, no losing head-ons."""

    def decide(self, state: GameState, me: SnakeId) -> Decision:
        grid = state.grid
        snake = state.snake(me)
        free_at = release_times(state)
        danger: set[Cell] = set()
        for rival in state.opponents(me):
            if rival.next_length >= snake.next_length:
                danger |= threat_cells(grid, rival, free_at)

        best: tuple[tuple[bool, bool, int, int], Direction] | None = None
        for direction, cell in candidate_moves(grid, snake):
            if cell is None or free_at[cell] > 1:
                continue
            times = reach_times(grid, free_at, cell, 1)
            space = reachable_count(times)
            food = [times[f] for f in state.food if times[f] != UNREACHED]
            key = (cell not in danger, space >= snake.length, -min(food, default=grid.size), space)
            if best is None or key > best[0]:
                best = (key, direction)
        return Decision(best[1] if best else snake.direction)
