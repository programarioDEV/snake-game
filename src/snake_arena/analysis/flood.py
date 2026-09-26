from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..core import Cell, Grid, SnakeId

UNREACHED = -1
NEUTRAL = -1


def reach_times(
    grid: Grid, free_at: Sequence[int], source: Cell, start_time: int = 0
) -> list[int]:
    """Time-aware BFS: arrival tick per cell, entering a cell only once its occupant has left."""
    times = [UNREACHED] * grid.size
    times[source] = start_time
    adjacency = grid.adjacency
    queue = deque((source,))
    while queue:
        cell = queue.popleft()
        arrival = times[cell] + 1
        for neighbor in adjacency[cell]:
            if times[neighbor] == UNREACHED and free_at[neighbor] <= arrival:
                times[neighbor] = arrival
                queue.append(neighbor)
    return times


def reachable_count(times: Sequence[int]) -> int:
    """Cells reached by a reach_times run, its source excluded."""
    return len(times) - times.count(UNREACHED) - 1


def backtrack(grid: Grid, times: Sequence[int], source: Cell, target: Cell) -> tuple[Cell, ...]:
    """Shortest route recovered from reach_times output, source excluded."""
    if target == source or times[target] == UNREACHED:
        return ()
    adjacency = grid.adjacency
    path = [target]
    cell = target
    while cell != source:
        previous = times[cell] - 1
        cell = next(n for n in adjacency[cell] if times[n] == previous)
        path.append(cell)
    path.pop()
    path.reverse()
    return tuple(path)


@dataclass(frozen=True, slots=True)
class Source:
    owner: SnakeId
    cell: Cell
    start_time: int = 0
    strength: int = 0


@dataclass(frozen=True, slots=True)
class VoronoiResult:
    owner: tuple[int, ...]
    times: tuple[int, ...]
    counts: Mapping[SnakeId, int]

    def share(self, snake_id: SnakeId) -> float:
        total = sum(self.counts.values())
        return self.counts.get(snake_id, 0) / total if total else 0.0


def voronoi(grid: Grid, free_at: Sequence[int], sources: Sequence[Source]) -> VoronoiResult:
    """Multi-source time-aware partition; ties go to the stronger (longer) snake, else neutral."""
    size = grid.size
    adjacency = grid.adjacency
    times = [UNREACHED] * size
    owner = [NEUTRAL] * size
    strength: dict[int, int] = {s.owner: s.strength for s in sources}
    seeds = {s.cell for s in sources}
    pending = deque(sorted(sources, key=lambda s: s.start_time))
    for source in pending:
        times[source.cell] = source.start_time
        owner[source.cell] = source.owner

    t = pending[0].start_time if pending else 0
    frontier: list[Cell] = []
    while pending and pending[0].start_time == t:
        frontier.append(pending.popleft().cell)

    while frontier or pending:
        t += 1
        reached: list[Cell] = []
        for cell in frontier:
            claimant = owner[cell]
            for neighbor in adjacency[cell]:
                arrival = times[neighbor]
                if arrival == UNREACHED:
                    if free_at[neighbor] <= t:
                        times[neighbor] = t
                        owner[neighbor] = claimant
                        reached.append(neighbor)
                elif arrival == t and owner[neighbor] != claimant and neighbor not in seeds:
                    owner[neighbor] = _contest(owner[neighbor], claimant, strength)
        while pending and pending[0].start_time == t:
            reached.append(pending.popleft().cell)
        frontier = reached

    tally = Counter(owner)
    for source in sources:
        tally[source.owner] -= 1
    counts = {s.owner: tally[s.owner] for s in sources}
    return VoronoiResult(tuple(owner), tuple(times), counts)


def _contest(current: int, challenger: int, strength: Mapping[int, int]) -> int:
    if current == NEUTRAL or challenger == NEUTRAL:
        return NEUTRAL
    held, attack = strength[current], strength[challenger]
    if held == attack:
        return NEUTRAL
    return current if held > attack else challenger
