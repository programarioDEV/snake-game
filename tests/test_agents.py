from snake_arena.agents import BaseAgent, Decision
from snake_arena.core import Direction, GameState, Grid, Snake, SnakeId, step


class Straight(BaseAgent):
    def decide(self, state: GameState, me: SnakeId) -> Decision:
        return Decision(state.snake(me).direction)


def test_agents_drive_the_rules_until_game_over() -> None:
    grid = Grid(8, 3)
    agents = {SnakeId(0): Straight(), SnakeId(1): Straight()}
    state = GameState(
        grid,
        (
            Snake.spawn(grid, SnakeId(0), grid.cell(2, 0), Direction.RIGHT, 2),
            Snake.spawn(grid, SnakeId(1), grid.cell(5, 2), Direction.LEFT, 2),
        ),
    )
    while not state.is_over:
        moves = {
            sid: agent.decide(state, sid).direction
            for sid, agent in agents.items()
            if state.snake(sid).alive
        }
        state = step(state, moves).state

    assert state.tick == 6
    assert state.winner is None
    assert agents[SnakeId(0)].name == "Straight"
