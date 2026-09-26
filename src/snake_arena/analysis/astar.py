from __future__ import annotations

import heapq
import math
from collections.abc import Sequence
from dataclasses import dataclass

from ..core import Cell, Grid


@dataclass(frozen=True, slots=True)
class PathResult:
    path: tuple[Cell, ...] | None
    cost: float
    nodes_expanded: int

    @property
    def found(self) -> bool:
        return self.path is not None


def astar(
    grid: Grid,
    free_at: Sequence[int],
    start: Cell,
    goal: Cell,
    *,
    start_time: int = 0,
    weight: float = 1.0,
    penalty: Sequence[float] | None = None,
    max_expansions: int | None = None,
) -> PathResult:
    """Weighted A* (f = g + w*h) over the time-aware grid; the path excludes start."""
    if start == goal:
        return PathResult((), 0.0, 0)
    width = grid.width
    size = grid.size
    adjacency = grid.adjacency
    goal_y, goal_x = divmod(goal, width)
    best = [math.inf] * size
    steps = [0] * size
    parent = [start] * size
    closed = bytearray(size)
    best[start] = 0.0
    steps[start] = start_time
    start_y, start_x = divmod(start, width)
    h_start = abs(start_x - goal_x) + abs(start_y - goal_y)
    heap: list[tuple[float, int, int, Cell]] = [(weight * h_start, h_start, 0, start)]
    pushes = 0
    expanded = 0

    while heap:
        cell = heapq.heappop(heap)[3]
        if closed[cell]:
            continue
        closed[cell] = 1
        expanded += 1
        if cell == goal:
            return PathResult(_rebuild(parent, start, goal), best[goal], expanded)
        if max_expansions is not None and expanded >= max_expansions:
            break
        arrival = steps[cell] + 1
        base = best[cell] + 1.0
        for neighbor in adjacency[cell]:
            if closed[neighbor] or free_at[neighbor] > arrival:
                continue
            cost = base + penalty[neighbor] if penalty is not None else base
            if cost < best[neighbor]:
                best[neighbor] = cost
                steps[neighbor] = arrival
                parent[neighbor] = cell
                y, x = divmod(neighbor, width)
                h = abs(x - goal_x) + abs(y - goal_y)
                pushes += 1
                heapq.heappush(heap, (cost + weight * h, h, pushes, neighbor))
    return PathResult(None, math.inf, expanded)


def _rebuild(parent: Sequence[Cell], start: Cell, goal: Cell) -> tuple[Cell, ...]:
    path = [goal]
    cell = goal
    while (cell := parent[cell]) != start:
        path.append(cell)
    path.reverse()
    return tuple(path)
