from __future__ import annotations

import random
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from ..agents import BaseAgent, Decision, TacticalMode
from ..core import Cell, DeathEvent, GameState, Snake, SnakeId, TickResult, spawn_food, step
from .config import MatchConfig

REPETITION_LIMIT = 3
"""Sightings of the same position that end the match, as in chess's threefold repetition."""

# The board without the tick counter: bodies, headings, pending growth, liveness and food.
Position = tuple[tuple[Snake, ...], frozenset[Cell]]


class GameResult(StrEnum):
    """Why a match ended."""

    LAST_STANDING = "last snake standing"
    NO_SURVIVORS = "no survivors"
    TICK_LIMIT = "tick limit"
    DRAW_CYCLE = "loop detected"
    DRAW_STALEMATE = "stalemate"


@dataclass(frozen=True, slots=True)
class TickRecord:
    state: GameState
    result: TickResult
    decisions: Mapping[SnakeId, Decision]
    compute_ms: Mapping[SnakeId, float]
    tick_ms: float


@dataclass(slots=True)
class AgentStats:
    decisions: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    nodes_expanded: int = 0
    modes: Counter[TacticalMode] = field(default_factory=Counter)

    @property
    def mean_ms(self) -> float:
        return self.total_ms / self.decisions if self.decisions else 0.0

    def record(self, elapsed_ms: float, decision: Decision) -> None:
        self.decisions += 1
        self.total_ms += elapsed_ms
        self.max_ms = max(self.max_ms, elapsed_ms)
        if decision.trace is not None:
            self.nodes_expanded += decision.trace.nodes_expanded
            self.modes[decision.trace.mode] += 1

    def merge(self, other: AgentStats) -> None:
        self.decisions += other.decisions
        self.total_ms += other.total_ms
        self.max_ms = max(self.max_ms, other.max_ms)
        self.nodes_expanded += other.nodes_expanded
        self.modes.update(other.modes)


@dataclass(frozen=True, slots=True)
class MatchSummary:
    winner: SnakeId | None
    ending: GameResult | None
    ticks: int
    lengths: tuple[int, ...]
    deaths: tuple[DeathEvent, ...]
    stats: tuple[AgentStats, ...]


class SimulationEngine:
    """Deterministic match loop (agents -> rules -> seeded food) with per-agent timing; no I/O."""

    def __init__(
        self,
        config: MatchConfig,
        agents: Sequence[BaseAgent],
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.config = config
        self.agents = tuple(agents)
        self._clock = clock
        self.reset()

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.config = replace(self.config, seed=seed)
        self._rng = random.Random(self.config.seed)
        self.state = self.config.initial_state(self._rng)
        if len(self.agents) != len(self.state.snakes):
            raise ValueError(f"expected {len(self.state.snakes)} agents, got {len(self.agents)}")
        self.last: TickRecord | None = None
        self.deaths: list[DeathEvent] = []
        self.stats = tuple(AgentStats() for _ in self.agents)
        for agent in self.agents:
            agent.reset()
        self.ticks_without_food = 0
        self.cycle_period: int | None = None
        # Position -> (sightings, last tick seen) since the last meal.
        self._seen: dict[Position, tuple[int, int]] = {}
        self._remember()
        self.ending: GameResult | None = self._judge()

    @property
    def is_over(self) -> bool:
        return self.ending is not None

    @property
    def winner(self) -> SnakeId | None:
        """Last snake standing, or the strictly longest survivor at the tick limit; loops and stalls draw."""
        if self.ending is not GameResult.TICK_LIMIT:
            return self.state.winner
        alive = sorted(self.state.alive_snakes(), key=lambda s: s.length, reverse=True)
        if len(alive) > 1 and alive[0].length == alive[1].length:
            return None
        return alive[0].id

    def tick(self) -> TickRecord:
        if self.is_over:
            raise RuntimeError("the match is already over")
        started = self._clock()
        decisions: dict[SnakeId, Decision] = {}
        timings: dict[SnakeId, float] = {}
        for snake in self.state.alive_snakes():
            before = self._clock()
            decision = self.agents[snake.id].decide(self.state, snake.id)
            elapsed = (self._clock() - before) * 1000.0
            decisions[snake.id] = decision
            timings[snake.id] = elapsed
            self.stats[snake.id].record(elapsed, decision)

        result = step(
            self.state,
            {sid: d.direction for sid, d in decisions.items()},
            growth_per_food=self.config.growth_per_food,
        )
        self.state = spawn_food(result.state, self._rng, self.config.food_count)
        self.deaths.extend(result.deaths)
        if result.eaten:
            # A meal raises length + pending growth for good, so no earlier position can recur.
            self.ticks_without_food = 0
            self._seen.clear()
        else:
            self.ticks_without_food += 1
        self._remember()
        self.ending = self._judge()
        self.last = TickRecord(
            self.state, result, decisions, timings, (self._clock() - started) * 1000.0
        )
        return self.last

    def run(self) -> MatchSummary:
        while not self.is_over:
            self.tick()
        return self.summary()

    def _remember(self) -> None:
        if not self.config.detect_cycles:
            return
        position: Position = (self.state.snakes, self.state.food)
        sightings, last_seen = self._seen.get(position, (0, self.state.tick))
        self._seen[position] = (sightings + 1, self.state.tick)
        if sightings + 1 >= REPETITION_LIMIT:
            self.cycle_period = self.state.tick - last_seen

    def _judge(self) -> GameResult | None:
        state = self.state
        if state.is_over:
            return GameResult.LAST_STANDING if state.winner is not None else GameResult.NO_SURVIVORS
        if self.cycle_period is not None:
            return GameResult.DRAW_CYCLE
        if self.ticks_without_food >= self.config.max_stall_ticks:
            return GameResult.DRAW_STALEMATE
        if state.tick >= self.config.max_ticks:
            return GameResult.TICK_LIMIT
        return None

    def summary(self) -> MatchSummary:
        return MatchSummary(
            winner=self.winner,
            ending=self.ending,
            ticks=self.state.tick,
            lengths=tuple(s.length for s in self.state.snakes),
            deaths=tuple(self.deaths),
            stats=tuple(replace(s, modes=Counter(s.modes)) for s in self.stats),
        )
