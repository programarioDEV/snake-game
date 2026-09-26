from snake_arena.core import Direction, Grid


def test_cell_coordinates_roundtrip() -> None:
    grid = Grid(5, 4)
    for x in range(5):
        for y in range(4):
            assert grid.xy(grid.cell(x, y)) == (x, y)


def test_moves_stop_at_borders_and_obstacles() -> None:
    wall = Grid(3, 3).cell(1, 0)
    grid = Grid(3, 3, obstacles=frozenset({wall}))
    corner = grid.cell(0, 0)

    assert grid.step(corner, Direction.UP) is None
    assert grid.step(corner, Direction.LEFT) is None
    assert grid.step(corner, Direction.RIGHT) is None
    assert grid.step(corner, Direction.DOWN) == grid.cell(0, 1)
    assert grid.neighbors(corner) == (grid.cell(0, 1),)
    assert wall not in set(grid.open_cells())


def test_opposite_directions_cancel_out() -> None:
    for direction in Direction:
        dx, dy = direction.delta
        assert direction.opposite.delta == (-dx, -dy)
        assert direction.opposite.opposite is direction
