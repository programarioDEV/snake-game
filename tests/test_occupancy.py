import pytest

from snake_arena.analysis import BLOCKED, release_times, threat_cells
from snake_arena.core import Direction, GameState, SnakeId, step
from support import make_snake, walled

A = SnakeId(0)


def test_release_times_follow_body_order_and_pending_growth() -> None:
    grid = walled(5, 3, [(4, 2)])
    snake = make_snake(grid, A, [(2, 1), (1, 1), (0, 1)], pending_growth=1)
    free_at = release_times(GameState(grid, (snake,)))

    assert [free_at[c] for c in snake.body] == [4, 3, 2]
    assert free_at[grid.cell(4, 2)] == BLOCKED
    assert free_at[grid.cell(4, 0)] == 0


@pytest.mark.parametrize("pending_growth", [0, 1])
def test_release_times_agree_with_the_rules(pending_growth: int) -> None:
    grid = walled(4, 4, [])
    snake = make_snake(grid, A, [(0, 0), (0, 1), (1, 1), (1, 0)], pending_growth)
    state = GameState(grid, (snake,))
    free_at = release_times(state)

    for direction in Direction:
        target = grid.step(snake.head, direction)
        if target is None or direction == snake.direction.opposite:
            continue
        survives = step(state, {A: direction}).state.snake(A).alive
        assert survives == (free_at[target] <= 1)


def test_threat_cells_skip_reversal_and_blocked_cells() -> None:
    grid = walled(5, 5, [(2, 1)])
    snake = make_snake(grid, A, [(2, 2), (2, 3), (2, 4)])
    free_at = release_times(GameState(grid, (snake,)))
    assert threat_cells(grid, snake, free_at) == {grid.cell(1, 2), grid.cell(3, 2)}
