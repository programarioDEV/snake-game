from dataclasses import replace

import pytest

from snake_arena.core import Cell, Direction, Grid, Snake, SnakeId


def test_spawn_lays_body_behind_head() -> None:
    grid = Grid(6, 3)
    snake = Snake.spawn(grid, SnakeId(0), grid.cell(3, 1), Direction.RIGHT, 3)
    assert [grid.xy(c) for c in snake.body] == [(3, 1), (2, 1), (1, 1)]
    assert snake.direction is Direction.RIGHT


def test_spawn_rejects_body_that_does_not_fit() -> None:
    grid = Grid(6, 3)
    with pytest.raises(ValueError):
        Snake.spawn(grid, SnakeId(0), grid.cell(1, 1), Direction.RIGHT, 3)


def test_body_cannot_overlap_itself() -> None:
    with pytest.raises(ValueError):
        Snake(SnakeId(0), (Cell(1), Cell(2), Cell(1)), Direction.UP)


def test_tail_is_retained_only_while_growing() -> None:
    snake = Snake(SnakeId(0), (Cell(2), Cell(1), Cell(0)), Direction.RIGHT)
    assert snake.retained_body == (Cell(2), Cell(1))
    assert replace(snake, pending_growth=2).retained_body == snake.body
