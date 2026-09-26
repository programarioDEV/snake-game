import os

import pytest

pytest.importorskip("pygame")
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from snake_arena.agents import AggressiveAIController, GreedyAgent, HumanController  # noqa: E402
from snake_arena.core import SnakeId  # noqa: E402
from snake_arena.engine import MatchConfig  # noqa: E402
from snake_arena.view.app import ArenaApp, ShowcaseOptions  # noqa: E402
from snake_arena.view.scene import HUD_WIDTH, SERIES_WIDTH  # noqa: E402

FIRST, SECOND = SnakeId(0), SnakeId(1)


@pytest.fixture(autouse=True)
def _quit_pygame() -> object:
    yield
    pygame.quit()


def test_play_mode_runs_headless_with_every_overlay() -> None:
    app = ArenaApp(MatchConfig(seed=3), [HumanController(), AggressiveAIController()])
    assert app.focus == SECOND
    assert app.scene.series_panel is None
    for _ in range(3):
        app.update(0.1)
        app.render()
    trace = app.focus_trace()
    assert trace is not None and trace.territory is not None

    for key in (pygame.K_v, pygame.K_p, pygame.K_i, pygame.K_c):
        app.on_key(key)
    assert app.toggles.as_tuple() == (False, False, False, False)
    app.render()

    app.on_key(pygame.K_SPACE)
    tick = app.engine.state.tick
    app.update(1.0)
    assert app.engine.state.tick == tick
    app.on_key(pygame.K_n)
    assert app.engine.state.tick == tick + 1

    app.on_key(pygame.K_SPACE)
    for _ in range(30):
        app.update(0.1)
        app.render()
    assert app.engine.is_over
    assert app.engine.deaths[0].snake_id == FIRST


def test_watch_mode_plays_the_requested_rounds_and_restarts_by_itself() -> None:
    config = MatchConfig(width=13, height=13, arena="open", max_ticks=25, seed=7)
    showcase = ShowcaseOptions(rounds=2, restart_delay=1.0)
    app = ArenaApp(config, [AggressiveAIController(), AggressiveAIController()], showcase=showcase)
    assert app.series is not None
    assert app.screen.get_width() == app.scene.board.size[0] + HUD_WIDTH + SERIES_WIDTH

    seeds = {app.engine.config.seed}
    for _ in range(200):
        app.update(0.1)
        app.render()
        seeds.add(app.engine.config.seed)
        if app.series.finished:
            break

    assert app.series.finished
    assert app.series.stats.matches == 2
    assert seeds == {7, 8}
    assert app.engine.is_over


def test_focus_keys_switch_the_inspected_agent_but_keep_the_voronoi_map() -> None:
    config = MatchConfig(seed=2)
    app = ArenaApp(config, [GreedyAgent(), AggressiveAIController()], showcase=ShowcaseOptions())
    for _ in range(5):
        app.update(0.1)
    assert app.focus == SECOND
    ai_trace = app.focus_trace()
    assert ai_trace is not None

    app.on_key(pygame.K_1)
    assert app.focus == FIRST
    assert app.focus_trace() is None
    assert app.scene.board._territory_trace(app.focus, app.traces()) is ai_trace
    app.render()

    app.on_key(pygame.K_2)
    assert app.focus == SECOND
    app.render()
