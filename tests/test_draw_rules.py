import pytest

from snake_arena.agents import AggressiveAIController, BaseAgent, Decision, GreedyAgent
from snake_arena.core import GameState, SnakeId
from snake_arena.engine import REPETITION_LIMIT, GameResult, MatchConfig, MatchSeries, SimulationEngine
from support import Circler


class Straight(BaseAgent):
    def decide(self, state: GameState, me: SnakeId) -> Decision:
        return Decision(state.snake(me).direction)


def starving(*, detect_cycles: bool = True, stall_ticks: int | None = None) -> MatchConfig:
    """Open 13x13 board with no food at all, so nobody can ever eat."""
    return MatchConfig(
        width=13,
        height=13,
        arena="open",
        food_count=0,
        detect_cycles=detect_cycles,
        stall_ticks=stall_ticks,
    )


def test_two_snakes_circling_without_eating_end_in_a_draw_by_cycle() -> None:
    engine = SimulationEngine(starving(), [Circler(), Circler()])
    summary = engine.run()

    assert summary.ending is engine.ending is GameResult.DRAW_CYCLE
    assert summary.winner is None
    assert not engine.deaths
    assert all(snake.alive for snake in engine.state.snakes)
    # Both loops close at tick 2 and repeat every 4 ticks: third sighting at 2 + 2 * 4.
    assert engine.cycle_period == 4
    assert summary.ticks == 2 + (REPETITION_LIMIT - 1) * 4


def test_the_cycle_is_caught_on_the_third_sighting_not_earlier() -> None:
    engine = SimulationEngine(starving(), [Circler(), Circler()])
    for _ in range(2 + (REPETITION_LIMIT - 1) * 4 - 1):
        engine.tick()
    assert not engine.is_over
    engine.tick()
    assert engine.ending is GameResult.DRAW_CYCLE


def test_a_match_without_food_ends_in_a_stalemate_at_the_stall_limit() -> None:
    config = MatchConfig(width=31, height=31, arena="open", food_count=0, stall_ticks=12)
    engine = SimulationEngine(config, [Straight(), Straight()])
    summary = engine.run()

    assert summary.ending is GameResult.DRAW_STALEMATE
    assert summary.winner is None
    assert summary.ticks == 12
    assert engine.ticks_without_food == 12
    assert not engine.deaths


def test_disabling_cycle_detection_leaves_only_the_stall_rule() -> None:
    engine = SimulationEngine(starving(detect_cycles=False, stall_ticks=40), [Circler(), Circler()])
    summary = engine.run()
    assert summary.ending is GameResult.DRAW_STALEMATE
    assert summary.ticks == 40
    assert engine.cycle_period is None


def test_the_default_stall_limit_scales_with_the_board_area() -> None:
    assert MatchConfig().max_stall_ticks == 1441
    assert MatchConfig(width=10, height=12).max_stall_ticks == 180
    assert MatchConfig(stall_ticks=150).max_stall_ticks == 150
    with pytest.raises(ValueError):
        MatchConfig(stall_ticks=0)


def test_eating_resets_the_stall_counter_and_the_repetition_table() -> None:
    config = MatchConfig(width=15, height=15, arena="open", seed=4, max_ticks=300)
    engine = SimulationEngine(config, [GreedyAgent(), AggressiveAIController()])
    idle, meals = 0, 0
    while not engine.is_over:
        record = engine.tick()
        meals += len(record.result.eaten)
        idle = 0 if record.result.eaten else idle + 1
        assert engine.ticks_without_food == idle
        # Positions before a meal can never recur (length + pending growth only increase),
        # so the table only spans the current foodless stretch.
        assert len(engine._seen) <= idle + 1
    assert meals > 0
    assert engine.ending in (GameResult.LAST_STANDING, GameResult.NO_SURVIVORS, GameResult.TICK_LIMIT)


def test_deaths_take_precedence_and_the_tick_limit_still_rewards_length() -> None:
    crash = SimulationEngine(MatchConfig(width=13, height=13, arena="open"), [Straight(), Straight()])
    crash.run()
    assert crash.ending is GameResult.NO_SURVIVORS

    capped = SimulationEngine(MatchConfig(max_ticks=2), [Straight(), Straight()])
    capped.run()
    assert capped.ending is GameResult.TICK_LIMIT


def test_series_counts_cycle_draws_and_restarts_after_the_delay() -> None:
    series = MatchSeries(SimulationEngine(starving(), [Circler(), Circler()]), rounds=2, restart_delay=1.0)
    started = 0
    for _ in range(200):
        if not series.engine.is_over:
            series.engine.tick()
        started += series.update(0.25)
        if series.finished:
            break

    assert series.finished
    assert started == 1
    assert (series.stats.matches, series.stats.draws) == (2, 2)
    assert series.stats.endings[GameResult.DRAW_CYCLE] == 2
    assert series.stats.results == [None, None]
