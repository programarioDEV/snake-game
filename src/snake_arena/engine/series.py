from __future__ import annotations

from collections import Counter

from ..agents import TacticalMode
from ..core import CollisionType, SnakeId
from .simulation import AgentStats, MatchSummary, SimulationEngine


class SeriesStats:
    """Scoreboard aggregated over finished matches."""

    def __init__(self, players: int) -> None:
        self.matches = 0
        self.draws = 0
        self.total_ticks = 0
        self.wins: Counter[SnakeId] = Counter()
        self.deaths: Counter[tuple[SnakeId, CollisionType]] = Counter()
        self.length_totals = [0] * players
        self.agents = [AgentStats() for _ in range(players)]
        self.results: list[SnakeId | None] = []

    def record(self, summary: MatchSummary) -> None:
        self.matches += 1
        self.total_ticks += summary.ticks
        self.results.append(summary.winner)
        if summary.winner is None:
            self.draws += 1
        else:
            self.wins[summary.winner] += 1
        for death in summary.deaths:
            self.deaths[(death.snake_id, death.cause)] += 1
        for index, length in enumerate(summary.lengths):
            self.length_totals[index] += length
        for merged, stats in zip(self.agents, summary.stats):
            merged.merge(stats)

    def win_rate(self, snake_id: SnakeId) -> float:
        return self.wins[snake_id] / self.matches if self.matches else 0.0

    @property
    def draw_rate(self) -> float:
        return self.draws / self.matches if self.matches else 0.0

    @property
    def mean_ticks(self) -> float:
        return self.total_ticks / self.matches if self.matches else 0.0

    def mean_length(self, snake_id: SnakeId) -> float:
        return self.length_totals[snake_id] / self.matches if self.matches else 0.0


class MatchSeries:
    """Back-to-back matches on one engine: record the result, wait, re-seed, restart."""

    def __init__(
        self, engine: SimulationEngine, *, rounds: int | None = None, restart_delay: float = 1.5
    ) -> None:
        if rounds is not None and rounds < 1:
            raise ValueError("rounds must be at least 1")
        if restart_delay < 0:
            raise ValueError("restart_delay cannot be negative")
        self.engine = engine
        self.rounds = rounds
        self.restart_delay = restart_delay
        self.base_seed = engine.config.seed
        self.stats = SeriesStats(len(engine.agents))
        self.round = 1
        self._recorded = False
        self._waited = 0.0

    @property
    def finished(self) -> bool:
        return self._recorded and self.rounds is not None and self.round >= self.rounds

    @property
    def restart_in(self) -> float | None:
        """Seconds until the next round starts, or None while a match is being played."""
        if not self._recorded or self.finished:
            return None
        return max(0.0, self.restart_delay - self._waited)

    def update(self, dt: float) -> bool:
        """Advance the post-match countdown by dt seconds; True when a new round has started."""
        if not self.engine.is_over:
            return False
        if not self._recorded:
            self._record()
            return False
        if self.finished:
            return False
        self._waited += dt
        if self._waited < self.restart_delay:
            return False
        self._next_round()
        return True

    def skip(self) -> None:
        """Replay the current round if it is still running, otherwise start the next one now."""
        if not self.engine.is_over:
            self.engine.reset()
            return
        if not self._recorded:
            self._record()
        if not self.finished:
            self._next_round()

    def mode_mix(self, snake_id: SnakeId) -> Counter[TacticalMode]:
        """Tactics used across the series, including the match still in progress."""
        mix = Counter(self.stats.agents[snake_id].modes)
        if not self._recorded:
            mix.update(self.engine.stats[snake_id].modes)
        return mix

    def _record(self) -> None:
        self.stats.record(self.engine.summary())
        self._recorded = True
        self._waited = 0.0

    def _next_round(self) -> None:
        self.engine.reset(seed=self.base_seed + self.round)
        self.round += 1
        self._recorded = False
        self._waited = 0.0
