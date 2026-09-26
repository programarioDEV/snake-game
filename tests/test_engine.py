from itertools import count

from snake_arena.agents import AggressiveAIController, BaseAgent, Decision, GreedyAgent
from snake_arena.core import GameState, SnakeId
from snake_arena.engine import MatchConfig, SimulationEngine, format_report, run_benchmark


class Straight(BaseAgent):
    def decide(self, state: GameState, me: SnakeId) -> Decision:
        return Decision(state.snake(me).direction)


def test_headless_matches_are_reproducible_from_the_seed() -> None:
    config = MatchConfig(width=15, height=15, arena="open", seed=5, max_ticks=300)
    first = SimulationEngine(config, [GreedyAgent(), AggressiveAIController()]).run()
    second = SimulationEngine(config, [GreedyAgent(), AggressiveAIController()]).run()
    assert (first.ticks, first.lengths, first.deaths, first.winner) == (
        second.ticks,
        second.lengths,
        second.deaths,
        second.winner,
    )


def test_tick_records_per_agent_timing_with_an_injected_clock() -> None:
    ticks = count()
    engine = SimulationEngine(
        MatchConfig(seed=2), [GreedyAgent(), AggressiveAIController()], clock=lambda: next(ticks) / 1000
    )
    record = engine.tick()

    assert record.compute_ms == {SnakeId(0): 1.0, SnakeId(1): 1.0}
    assert record.tick_ms == 5.0
    assert record.state is engine.state
    ai_stats = engine.stats[1]
    assert ai_stats.decisions == 1
    assert sum(ai_stats.modes.values()) == 1
    assert record.decisions[SnakeId(1)].trace is not None


def test_tick_limit_ends_the_match_as_a_draw_between_equal_lengths() -> None:
    engine = SimulationEngine(MatchConfig(max_ticks=2), [Straight(), Straight()])
    summary = engine.run()
    assert summary.ticks == 2
    assert summary.winner is None
    assert engine.is_over


def test_reset_restores_the_initial_board() -> None:
    engine = SimulationEngine(MatchConfig(seed=9), [GreedyAgent(), AggressiveAIController()])
    initial = engine.state
    for _ in range(5):
        engine.tick()
    engine.reset()
    assert engine.state == initial
    assert engine.last is None
    assert engine.stats[0].decisions == 0


def test_benchmark_report_lists_both_agents() -> None:
    config = MatchConfig(width=13, height=13, arena="open", max_ticks=150)
    report = run_benchmark(config, 2, (GreedyAgent, AggressiveAIController))
    text = format_report(report)
    assert report.series.matches == 2
    assert "#1 GreedyAgent" in text and "#2 Offensive AI" in text
