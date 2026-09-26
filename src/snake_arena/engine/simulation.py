from __future__ import annotations

import random
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from ..agents import BaseAgent, Decision, TacticalMode
from ..core import DeathEvent, GameState, SnakeId, TickResult, spawn_food, step
from .config import MatchConfig


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

    @property
    def is_over(self) -> bool:
        return self.state.is_over or self.state.tick >= self.config.max_ticks

    @property
    def winner(self) -> SnakeId | None:
        """Last snake standing, or the strictly longest survivor when the tick limit is hit."""
        if not self.is_over:
            return None
        if self.state.is_over:
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
        self.last = TickRecord(
            self.state, result, decisions, timings, (self._clock() - started) * 1000.0
        )
        return self.last

    def run(self) -> MatchSummary:
        while not self.is_over:
            self.tick()
        return self.summary()

    def summary(self) -> MatchSummary:
        return MatchSummary(
            winner=self.winner,
            ticks=self.state.tick,
            lengths=tuple(s.length for s in self.state.snakes),
            deaths=tuple(self.deaths),
            stats=tuple(replace(s, modes=Counter(s.modes)) for s in self.stats),
        )
