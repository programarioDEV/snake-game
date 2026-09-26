from snake_arena.agents import BaseAgent, Decision
from snake_arena.core import Direction, GameState, Grid, Snake, SnakeId


class Circler(BaseAgent):
    """Turns clockwise every tick: a length-4 snake settles into a 2x2 loop chasing its own tail."""

    def decide(self, state: GameState, me: SnakeId) -> Decision:
        return Decision(Direction((state.snake(me).direction + 1) % 4))


def make_snake(
    grid: Grid, sid: SnakeId, coords: list[tuple[int, int]], pending_growth: int = 0
) -> Snake:
    direction = Direction.RIGHT
    if len(coords) > 1:
        (hx, hy), (nx, ny) = coords[0], coords[1]
        direction = next(d for d in Direction if d.delta == (hx - nx, hy - ny))
    return Snake(sid, tuple(grid.cell(x, y) for x, y in coords), direction, pending_growth)


def body_xy(grid: Grid, snake: Snake) -> list[tuple[int, int]]:
    return [grid.xy(c) for c in snake.body]


def walled(width: int, height: int, walls: list[tuple[int, int]]) -> Grid:
    probe = Grid(width, height)
    return Grid(width, height, frozenset(probe.cell(x, y) for x, y in walls))
