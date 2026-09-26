from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum, auto

from .grid import Cell, Direction
from .snake import Snake, SnakeId
from .state import GameState


class CollisionType(Enum):
    WALL = auto()
    SELF = auto()
    BODY = auto()
    HEAD_TO_HEAD = auto()


@dataclass(frozen=True, slots=True)
class DeathEvent:
    snake_id: SnakeId
    cause: CollisionType
    cell: Cell | None
    other: SnakeId | None = None


@dataclass(frozen=True, slots=True)
class TickResult:
    state: GameState
    directions: Mapping[SnakeId, Direction]
    deaths: tuple[DeathEvent, ...]
    eaten: Mapping[SnakeId, Cell]


def effective_direction(snake: Snake, requested: Direction | None) -> Direction:
    """A missing move or a 180-degree reversal keeps the current heading."""
    if requested is None or (snake.length > 1 and requested == snake.direction.opposite):
        return snake.direction
    return requested


def step(
    state: GameState,
    requested: Mapping[SnakeId, Direction],
    *,
    growth_per_food: int = 1,
) -> TickResult:
    """Moves all live snakes simultaneously; collisions are judged on the post-move board."""
    grid = state.grid
    movers = state.alive_snakes()
    directions = {s.id: effective_direction(s, requested.get(s.id)) for s in movers}
    targets = {s.id: grid.step(s.head, directions[s.id]) for s in movers}
    lengths = {s.id: s.next_length for s in movers}

    # Snakes dying this tick still block: outcomes must not depend on processing order.
    body_owner: dict[Cell, SnakeId] = {}
    for s in movers:
        body_owner.update(dict.fromkeys(s.retained_body, s.id))
    head_owner = {s.head: s.id for s in movers}
    arrivals: defaultdict[Cell, list[SnakeId]] = defaultdict(list)
    for sid, target in targets.items():
        if target is not None:
            arrivals[target].append(sid)

    deaths: list[DeathEvent] = []
    for s in movers:
        target = targets[s.id]
        if target is None:
            deaths.append(DeathEvent(s.id, CollisionType.WALL, None))
            continue

        # Two heads swapping cells crossed head-on, so it is a frontal clash, not a neck hit.
        partner = head_owner.get(target)
        if partner is not None and targets[partner] != s.head:
            partner = None

        owner = body_owner.get(target)
        if owner is not None and owner != partner:
            if owner == s.id:
                deaths.append(DeathEvent(s.id, CollisionType.SELF, target))
            else:
                deaths.append(DeathEvent(s.id, CollisionType.BODY, target, owner))
            continue

        rivals = [o for o in arrivals[target] if o != s.id]
        if partner is not None:
            rivals.append(partner)
        stronger = [o for o in rivals if lengths[o] >= lengths[s.id]]
        if stronger:
            killer = max(stronger, key=lengths.__getitem__)
            deaths.append(DeathEvent(s.id, CollisionType.HEAD_TO_HEAD, target, killer))

    dead = {event.snake_id for event in deaths}
    food = set(state.food)
    eaten: dict[SnakeId, Cell] = {}
    snakes = list(state.snakes)
    for s in movers:
        target = targets[s.id]
        if s.id in dead or target is None:
            snakes[s.id] = s.killed()
            continue
        ate = target in food
        if ate:
            food.remove(target)
            eaten[s.id] = target
        snakes[s.id] = s.advanced(target, directions[s.id], growth_per_food if ate else 0)

    next_state = GameState(grid, tuple(snakes), frozenset(food), state.tick + 1)
    return TickResult(next_state, directions, tuple(deaths), eaten)


def spawn_food(state: GameState, rng: random.Random, target_count: int) -> GameState:
    """Tops food up to target_count on free cells; deterministic for a seeded rng."""
    missing = target_count - len(state.food)
    if missing <= 0:
        return state
    free = state.free_cells()
    if not free:
        return state
    placed = rng.sample(free, min(missing, len(free)))
    return replace(state, food=state.food | frozenset(placed))
