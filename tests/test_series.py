import pytest

from snake_arena.agents import AggressiveAIController, BaseAgent, Decision, GreedyAgent
from snake_arena.core import GameState, SnakeId
from snake_arena.engine import MatchConfig, MatchSeries, SimulationEngine

FIRST, SECOND = SnakeId(0), SnakeId(1)


class Straight(BaseAgent):
    def decide(self, state: GameState, me: SnakeId) -> Decision:
        return Decision(state.snake(me).direction)


def quick_engine(*agents: BaseAgent, seed: int = 3) -> SimulationEngine:
    config = MatchConfig(width=13, height=13, arena="open", max_ticks=20, seed=seed)
    return SimulationEngine(config, list(agents) or [Straight(), Straight()])


def test_result_is_recorded_once_and_next_round_waits_for_the_delay() -> None:
    engine = quick_engine(GreedyAgent(), Straight())
    series = MatchSeries(engine, restart_delay=1.0)
    engine.run()

    assert not series.update(0.5)
    assert series.stats.matches == 1
    assert series.stats.wins[FIRST] == 1
    assert series.stats.win_rate(FIRST) == 1.0
    assert series.restart_in == 1.0

    assert not series.update(0.6)
    assert series.restart_in == pytest.approx(0.4)
    assert series.update(0.6)
    assert (series.round, engine.config.seed, engine.state.tick) == (2, 4, 0)
    assert not engine.is_over
    assert series.stats.matches == 1


def test_series_stops_after_the_requested_rounds() -> None:
    series = MatchSeries(quick_engine(), rounds=2, restart_delay=0.0)
    for _ in range(100):
        if not series.engine.is_over:
            series.engine.tick()
        series.update(0.1)

    assert series.finished
    assert series.restart_in is None
    assert (series.round, series.stats.matches, series.stats.draws) == (2, 2, 2)
    assert series.stats.draw_rate == 1.0
    assert series.stats.mean_ticks == 10.0
    assert series.stats.results == [None, None]


def test_skip_replays_a_running_round_and_advances_a_finished_one() -> None:
    engine = quick_engine()
    series = MatchSeries(engine, restart_delay=2.0)
    engine.tick()
    series.skip()
    assert (series.round, engine.state.tick, series.stats.matches) == (1, 0, 0)

    engine.run()
    series.skip()
    assert (series.round, engine.state.tick, series.stats.matches) == (2, 0, 1)


def test_mode_mix_counts_the_live_match_without_double_counting() -> None:
    engine = quick_engine(GreedyAgent(), AggressiveAIController())
    series = MatchSeries(engine)
    engine.tick()
    engine.tick()
    assert sum(series.mode_mix(SECOND).values()) == 2
    assert not series.mode_mix(FIRST)

    engine.run()
    series.update(0.0)
    assert sum(series.mode_mix(SECOND).values()) == engine.stats[SECOND].decisions


@pytest.mark.parametrize(("rounds", "delay"), [(0, 1.0), (None, -0.5)])
def test_invalid_series_settings_are_rejected(rounds: int | None, delay: float) -> None:
    with pytest.raises(ValueError):
        MatchSeries(quick_engine(), rounds=rounds, restart_delay=delay)
