import math

from snake_arena.analysis import astar
from snake_arena.core import Grid
from support import walled


def test_open_grid_path_is_shortest_and_contiguous() -> None:
    grid = Grid(8, 8)
    start, goal = grid.cell(1, 1), grid.cell(6, 4)
    result = astar(grid, [0] * grid.size, start, goal)

    assert result.path is not None
    assert len(result.path) == grid.manhattan(start, goal)
    assert result.cost == len(result.path)
    assert result.path[-1] == goal
    assert all(grid.manhattan(a, b) == 1 for a, b in zip((start, *result.path), result.path))
    assert result.nodes_expanded >= len(result.path)


def test_routes_around_obstacles() -> None:
    grid = walled(5, 5, [(2, y) for y in range(4)])
    result = astar(grid, [0] * grid.size, grid.cell(0, 0), grid.cell(4, 0))
    assert result.path is not None
    assert grid.cell(2, 4) in result.path
    assert len(result.path) == 12


def test_unreachable_goal_reports_failure_with_telemetry() -> None:
    grid = walled(5, 5, [(2, y) for y in range(5)])
    result = astar(grid, [0] * grid.size, grid.cell(0, 0), grid.cell(4, 0))
    assert not result.found
    assert result.cost == math.inf
    assert result.nodes_expanded == 10


def test_penalties_bend_the_route() -> None:
    grid = Grid(3, 3)
    penalty = [0.0] * grid.size
    penalty[grid.cell(1, 1)] = 10.0
    result = astar(grid, [0] * grid.size, grid.cell(0, 1), grid.cell(2, 1), penalty=penalty)
    assert result.path is not None
    assert grid.cell(1, 1) not in result.path
    assert result.cost == 4.0


def test_goal_is_entered_only_once_it_is_released() -> None:
    grid = Grid(3, 3)
    free_at = [0] * grid.size
    tail = grid.cell(1, 0)
    free_at[tail] = 3
    result = astar(grid, free_at, grid.cell(0, 0), tail)
    assert result.path is not None
    assert len(result.path) == 3


def test_weighted_search_trades_optimality_for_fewer_expansions() -> None:
    grid = walled(20, 20, [(10, y) for y in range(2, 20)] + [(x, 10) for x in range(3, 10)])
    start, goal = grid.cell(2, 17), grid.cell(17, 17)
    exact = astar(grid, [0] * grid.size, start, goal)
    greedy = astar(grid, [0] * grid.size, start, goal, weight=2.0)
    assert exact.path is not None and greedy.path is not None
    assert greedy.nodes_expanded < exact.nodes_expanded
    assert greedy.cost <= 2.0 * exact.cost
