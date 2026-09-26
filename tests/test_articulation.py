from snake_arena.analysis import articulation_points
from snake_arena.core import Grid
from support import walled


def test_every_inner_corridor_cell_is_a_cut() -> None:
    grid = walled(5, 3, [(x, y) for x in range(5) for y in (0, 2)])
    cuts = articulation_points(grid, [True] * grid.size, grid.cell(0, 1))
    assert cuts.component_size == 4
    assert cuts.cut_area == {grid.cell(1, 1): 0, grid.cell(2, 1): 1, grid.cell(3, 1): 2}


def test_open_grid_has_no_chokepoints() -> None:
    grid = Grid(4, 4)
    cuts = articulation_points(grid, [True] * grid.size, grid.cell(0, 0))
    assert cuts.points == frozenset()
    assert cuts.component_size == 15


def test_door_between_rooms_reports_area_left_to_the_root() -> None:
    grid = walled(5, 5, [(2, 0), (2, 1), (2, 3), (2, 4)])
    cuts = articulation_points(grid, [True] * grid.size, grid.cell(0, 0))
    assert cuts.cut_area == {grid.cell(1, 2): 8, grid.cell(2, 2): 9, grid.cell(3, 2): 10}


def test_impassable_cells_create_chokepoints_and_root_may_be_occupied() -> None:
    grid = Grid(3, 3)
    passable = [True] * grid.size
    passable[grid.cell(1, 0)] = passable[grid.cell(1, 2)] = False
    passable[grid.cell(0, 0)] = False
    cuts = articulation_points(grid, passable, grid.cell(0, 0))
    assert cuts.cut_area == {grid.cell(0, 1): 0, grid.cell(1, 1): 2, grid.cell(2, 1): 3}
