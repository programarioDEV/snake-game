from snake_arena.analysis import (
    NEUTRAL,
    UNREACHED,
    Source,
    backtrack,
    reach_times,
    reachable_count,
    voronoi,
)
from snake_arena.core import Grid, SnakeId
from support import walled

A = SnakeId(0)
B = SnakeId(1)


def corridor() -> Grid:
    return walled(5, 3, [(x, y) for x in range(5) for y in (0, 2)])


def test_reach_times_block_cells_until_their_occupant_leaves() -> None:
    grid = corridor()
    free_at = [0] * grid.size
    free_at[grid.cell(2, 1)] = 3
    times = reach_times(grid, free_at, grid.cell(0, 1))
    assert times[grid.cell(1, 1)] == 1
    assert times[grid.cell(2, 1)] == UNREACHED
    assert reachable_count(times) == 1

    free_at[grid.cell(2, 1)] = 2
    times = reach_times(grid, free_at, grid.cell(0, 1))
    assert times[grid.cell(4, 1)] == 4


def test_reach_times_take_a_detour_while_a_cell_is_still_occupied() -> None:
    grid = Grid(4, 4)
    free_at = [0] * grid.size
    target = grid.cell(1, 0)
    free_at[target] = 3
    times = reach_times(grid, free_at, grid.cell(0, 0))
    assert times[target] == 3


def test_backtrack_rebuilds_a_shortest_route() -> None:
    grid = Grid(4, 4)
    free_at = [0] * grid.size
    source, target = grid.cell(0, 0), grid.cell(3, 2)
    route = backtrack(grid, reach_times(grid, free_at, source), source, target)
    assert len(route) == 5
    assert route[-1] == target
    assert grid.manhattan(source, route[0]) == 1
    assert all(grid.manhattan(a, b) == 1 for a, b in zip(route, route[1:]))


def test_voronoi_leaves_an_equidistant_band_neutral() -> None:
    grid = Grid(5, 3)
    free_at = [0] * grid.size
    result = voronoi(
        grid, free_at, [Source(A, grid.cell(0, 1), 0, 3), Source(B, grid.cell(4, 1), 0, 3)]
    )
    assert result.counts == {A: 5, B: 5}
    assert all(result.owner[grid.cell(2, y)] == NEUTRAL for y in range(3))
    assert result.share(A) == 0.5


def test_voronoi_gives_ties_to_the_longer_snake() -> None:
    grid = Grid(5, 3)
    free_at = [0] * grid.size
    result = voronoi(
        grid, free_at, [Source(A, grid.cell(0, 1), 0, 5), Source(B, grid.cell(4, 1), 0, 3)]
    )
    assert result.counts == {A: 8, B: 5}


def test_voronoi_respects_a_late_start() -> None:
    grid = Grid(5, 3)
    free_at = [0] * grid.size
    result = voronoi(
        grid, free_at, [Source(A, grid.cell(0, 1), 1, 3), Source(B, grid.cell(4, 1), 0, 3)]
    )
    assert result.counts == {A: 5, B: 8}
    assert NEUTRAL not in result.owner


def test_voronoi_cannot_claim_through_bodies() -> None:
    grid = corridor()
    free_at = [0] * grid.size
    free_at[grid.cell(1, 1)] = 5
    result = voronoi(
        grid, free_at, [Source(A, grid.cell(0, 1), 0, 3), Source(B, grid.cell(4, 1), 0, 3)]
    )
    assert result.counts == {A: 0, B: 2}
