from snake_arena.core import Direction, Grid, Snake, SnakeId


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
