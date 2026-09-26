import random

import pytest

from snake_arena.core import (
    CollisionType,
    DeathEvent,
    Direction,
    GameState,
    Grid,
    SnakeId,
    spawn_food,
    step,
)
from support import body_xy, make_snake

A = SnakeId(0)
B = SnakeId(1)


def test_snake_advances_and_tail_follows() -> None:
    grid = Grid(5, 5)
    state = GameState(grid, (make_snake(grid, A, [(2, 2), (1, 2), (0, 2)]),))
    result = step(state, {A: Direction.DOWN})
    assert body_xy(grid, result.state.snake(A)) == [(2, 3), (2, 2), (1, 2)]
    assert result.state.tick == 1
    assert result.deaths == ()


def test_reversal_and_missing_moves_keep_heading() -> None:
    grid = Grid(6, 3)
    state = GameState(grid, (make_snake(grid, A, [(2, 1), (1, 1)]),))
    assert step(state, {A: Direction.LEFT}).state.snake(A).head == grid.cell(3, 1)
    assert step(state, {}).state.snake(A).head == grid.cell(3, 1)


def test_wall_collision_ends_the_game() -> None:
    grid = Grid(3, 3)
    state = GameState(grid, (make_snake(grid, A, [(2, 1), (1, 1)]),))
    result = step(state, {A: Direction.RIGHT})
    assert result.deaths == (DeathEvent(A, CollisionType.WALL, None),)
    assert not result.state.snake(A).alive
    assert result.state.is_over


def test_hitting_own_body_is_a_self_collision() -> None:
    grid = Grid(4, 4)
    u_shape = [(1, 1), (1, 2), (2, 2), (2, 1), (2, 0)]
    state = GameState(grid, (make_snake(grid, A, u_shape),))
    result = step(state, {A: Direction.RIGHT})
    assert result.deaths == (DeathEvent(A, CollisionType.SELF, grid.cell(2, 1)),)


@pytest.mark.parametrize(("pending_growth", "survives"), [(0, True), (1, False)])
def test_chasing_own_tail_is_safe_only_when_it_moves(pending_growth: int, survives: bool) -> None:
    grid = Grid(4, 4)
    square = [(0, 0), (0, 1), (1, 1), (1, 0)]
    state = GameState(grid, (make_snake(grid, A, square, pending_growth),))
    result = step(state, {A: Direction.RIGHT})
    assert result.state.snake(A).alive is survives


@pytest.mark.parametrize(("pending_growth", "survives"), [(0, True), (1, False)])
def test_entering_opponent_tail_is_safe_only_when_it_moves(
    pending_growth: int, survives: bool
) -> None:
    grid = Grid(4, 4)
    a = make_snake(grid, A, [(1, 0), (0, 0)])
    b = make_snake(grid, B, [(2, 2), (2, 1), (2, 0)], pending_growth)
    result = step(GameState(grid, (a, b)), {A: Direction.RIGHT, B: Direction.DOWN})
    assert result.state.snake(A).alive is survives
    assert result.state.snake(B).alive
    if not survives:
        assert result.deaths == (DeathEvent(A, CollisionType.BODY, grid.cell(2, 0), B),)


@pytest.mark.parametrize(
    ("b_coords", "b_pending", "a_survives"),
    [
        ([(4, 1), (5, 1)], 0, True),
        ([(4, 1), (5, 1), (6, 1)], 0, False),
        ([(4, 1), (5, 1)], 1, False),
    ],
    ids=["longer-wins", "equal-both-die", "pending-growth-counts"],
)
def test_head_to_head_on_same_cell(
    b_coords: list[tuple[int, int]], b_pending: int, a_survives: bool
) -> None:
    grid = Grid(7, 3)
    food = grid.cell(3, 1)
    a = make_snake(grid, A, [(2, 1), (1, 1), (0, 1)])
    b = make_snake(grid, B, b_coords, b_pending)
    result = step(GameState(grid, (a, b), frozenset({food})), {A: Direction.RIGHT, B: Direction.LEFT})

    assert result.state.snake(A).alive is a_survives
    assert not result.state.snake(B).alive
    assert all(d.cause is CollisionType.HEAD_TO_HEAD for d in result.deaths)
    assert result.state.winner == (A if a_survives else None)
    assert (A in result.eaten) is a_survives
    assert (food in result.state.food) is not a_survives


@pytest.mark.parametrize(
    ("b_coords", "a_survives"),
    [([(3, 1), (4, 1)], True), ([(3, 1), (4, 1), (5, 1)], False)],
    ids=["longer-wins", "equal-both-die"],
)
def test_swapping_heads_is_a_frontal_collision(
    b_coords: list[tuple[int, int]], a_survives: bool
) -> None:
    grid = Grid(7, 3)
    a = make_snake(grid, A, [(2, 1), (1, 1), (0, 1)])
    b = make_snake(grid, B, b_coords)
    result = step(GameState(grid, (a, b)), {A: Direction.RIGHT, B: Direction.LEFT})

    assert result.state.snake(A).alive is a_survives
    assert not result.state.snake(B).alive
    assert all(d.cause is CollisionType.HEAD_TO_HEAD for d in result.deaths)
    if a_survives:
        assert body_xy(grid, result.state.snake(A)) == [(3, 1), (2, 1), (1, 1)]


def test_bodies_of_snakes_dying_this_tick_still_block() -> None:
    grid = Grid(4, 4)
    a = make_snake(grid, A, [(1, 0), (1, 1), (1, 2)])
    b = make_snake(grid, B, [(0, 1), (0, 2)])
    result = step(GameState(grid, (a, b)), {A: Direction.UP, B: Direction.RIGHT})
    assert result.deaths == (
        DeathEvent(A, CollisionType.WALL, None),
        DeathEvent(B, CollisionType.BODY, grid.cell(1, 1), A),
    )


def test_eating_defers_growth_to_the_next_move() -> None:
    grid = Grid(6, 3)
    food = grid.cell(2, 1)
    state = GameState(grid, (make_snake(grid, A, [(1, 1), (0, 1)]),), frozenset({food}))

    first = step(state, {A: Direction.RIGHT})
    assert first.eaten == {A: food}
    assert first.state.food == frozenset()
    assert first.state.snake(A).length == 2
    assert first.state.snake(A).pending_growth == 1

    second = step(first.state, {A: Direction.RIGHT})
    assert body_xy(grid, second.state.snake(A)) == [(3, 1), (2, 1), (1, 1)]
    assert second.state.snake(A).pending_growth == 0


def test_spawn_food_is_seeded_and_avoids_snakes() -> None:
    grid = Grid(4, 4)
    state = GameState(grid, (make_snake(grid, A, [(1, 1), (0, 1)]),))

    first = spawn_food(state, random.Random(7), 5)
    assert first.food == spawn_food(state, random.Random(7), 5).food
    assert len(first.food) == 5
    assert not first.food & state.snake(A).cells
    assert len(spawn_food(state, random.Random(7), 100).food) == grid.size - 2
