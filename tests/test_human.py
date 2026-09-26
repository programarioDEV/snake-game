from snake_arena.agents import HumanController
from snake_arena.core import Direction, GameState, Grid, SnakeId, step
from support import make_snake

ME = SnakeId(0)


def board() -> GameState:
    grid = Grid(8, 8)
    return GameState(grid, (make_snake(grid, ME, [(3, 3), (2, 3), (1, 3)]),))


def test_quick_double_turn_is_spread_over_two_ticks() -> None:
    human = HumanController()
    state = board()
    human.push(Direction.UP)
    human.push(Direction.LEFT)

    first = human.decide(state, ME).direction
    state = step(state, {ME: first}).state
    second = human.decide(state, ME).direction
    assert (first, second) == (Direction.UP, Direction.LEFT)


def test_reversal_and_repeated_keys_are_dropped() -> None:
    human = HumanController()
    human.push(Direction.LEFT)
    human.push(Direction.RIGHT)
    assert human.decide(board(), ME).direction is Direction.RIGHT


def test_without_input_the_snake_keeps_its_heading() -> None:
    human = HumanController()
    human.push(Direction.DOWN)
    human.reset()
    assert human.decide(board(), ME).direction is Direction.RIGHT
