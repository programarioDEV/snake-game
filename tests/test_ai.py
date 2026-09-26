import random

import pytest

from snake_arena.agents import AggressiveAIController, TacticalMode
from snake_arena.core import Direction, GameState, Grid, SnakeId
from snake_arena.engine import MatchConfig, SimulationEngine
from support import make_snake, walled

PLAYER = SnakeId(0)
AI = SnakeId(1)


def test_seals_a_chokepoint_that_traps_the_opponent() -> None:
    grid = walled(9, 7, [(x, 2) for x in range(9) if x != 4])
    player = make_snake(
        grid,
        PLAYER,
        [(2, 1), (1, 1), (0, 1), (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0)],
    )
    ai = make_snake(grid, AI, [(4, 4), (4, 5), (4, 6)])
    decision = AggressiveAIController().decide(GameState(grid, (player, ai)), AI)

    assert decision.direction is Direction.UP
    assert decision.trace is not None
    assert decision.trace.mode is TacticalMode.CONSTRICT
    gate = grid.cell(4, 2)
    assert decision.trace.intercept_point == gate
    assert decision.trace.chokepoints[gate] < player.length
    assert decision.trace.planned_path == (grid.cell(4, 3), gate)


def test_refuses_a_head_on_it_would_lose_even_for_food() -> None:
    grid = Grid(7, 7)
    player = make_snake(grid, PLAYER, [(5, 3), (6, 3), (6, 4), (6, 5), (6, 6)])
    ai = make_snake(grid, AI, [(3, 3), (2, 3), (1, 3)])
    state = GameState(grid, (player, ai), frozenset({grid.cell(4, 3)}))
    decision = AggressiveAIController().decide(state, AI)

    assert decision.direction is not Direction.RIGHT
    assert decision.trace is not None
    assert "safety" in decision.trace.rationale


def test_never_steers_into_a_wall_when_an_exit_exists() -> None:
    grid = Grid(5, 5)
    ai = make_snake(grid, SnakeId(0), [(4, 0), (3, 0), (2, 0)])
    decision = AggressiveAIController().decide(GameState(grid, (ai,)), SnakeId(0))
    assert decision.direction is Direction.DOWN


def test_trace_is_fully_populated_on_a_real_board() -> None:
    config = MatchConfig(seed=1)
    state = config.initial_state(random.Random(config.seed))
    decision = AggressiveAIController().decide(state, AI)
    trace = decision.trace

    assert trace is not None
    assert set(trace.utilities) == set(TacticalMode)
    assert trace.mode is max(trace.utilities, key=lambda m: trace.utilities[m])
    assert trace.rationale
    assert trace.planned_path and trace.path_cost is not None and trace.nodes_expanded > 0
    assert trace.opponent_goal is not None and trace.opponent_path
    assert trace.territory is not None and len(trace.territory) == state.grid.size
    assert trace.territory_ratio is not None and 0.0 < trace.territory_ratio < 1.0


def test_mirror_agents_publish_the_same_voronoi_partition() -> None:
    for seed in range(3):
        engine = SimulationEngine(
            MatchConfig(seed=seed), [AggressiveAIController(), AggressiveAIController()]
        )
        for _ in range(25):
            if engine.is_over:
                break
            record = engine.tick()
        first = record.decisions[PLAYER].trace
        second = record.decisions[AI].trace
        assert first is not None and second is not None
        assert first.territory == second.territory
        assert first.territory_ratio is not None and second.territory_ratio is not None
        assert first.territory_ratio + second.territory_ratio == pytest.approx(1.0)


def test_decisions_are_deterministic() -> None:
    config = MatchConfig(seed=4)
    state = config.initial_state(random.Random(config.seed))
    first = AggressiveAIController().decide(state, AI)
    second = AggressiveAIController().decide(state, AI)
    assert first == second
