from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pygame

from ..agents import BaseAgent, DecisionTrace, HumanController
from ..core import Direction, SnakeId
from ..engine import MatchConfig, MatchSeries, SimulationEngine
from .board import OverlayToggles
from .scene import SceneRenderer, decision_traces, default_focus, match_result
from .theme import Theme

FPS_CAP = 120
MAX_CATCH_UP = 5

_STEER = {
    pygame.K_UP: Direction.UP,
    pygame.K_w: Direction.UP,
    pygame.K_RIGHT: Direction.RIGHT,
    pygame.K_d: Direction.RIGHT,
    pygame.K_DOWN: Direction.DOWN,
    pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT,
    pygame.K_a: Direction.LEFT,
}
_OVERLAYS = {pygame.K_v: "voronoi", pygame.K_p: "path", pygame.K_i: "intercept", pygame.K_c: "chokepoints"}
_FOCUS = {pygame.K_1: SnakeId(0), pygame.K_KP1: SnakeId(0), pygame.K_2: SnakeId(1), pygame.K_KP2: SnakeId(1)}


@dataclass(frozen=True, slots=True)
class ShowcaseOptions:
    rounds: int | None = None
    restart_delay: float = 1.5


class ArenaApp:
    """Pygame front end: fixed-rate ticks, free-running frames, focusable overlays, optional series."""

    def __init__(
        self,
        config: MatchConfig,
        agents: Sequence[BaseAgent],
        *,
        tick_rate: float = 10.0,
        cell: int = 22,
        showcase: ShowcaseOptions | None = None,
    ) -> None:
        pygame.init()
        self.engine = SimulationEngine(config, agents)
        self.human = next((a for a in agents if isinstance(a, HumanController)), None)
        self.series = (
            MatchSeries(self.engine, rounds=showcase.rounds, restart_delay=showcase.restart_delay)
            if showcase is not None
            else None
        )
        pygame.display.set_caption("Snake Arena - " + ("AI showcase" if self.series else "offensive AI"))
        self.labels = tuple(f"#{i + 1} {agent.name}" for i, agent in enumerate(self.engine.agents))
        self.focus = default_focus(self.engine.agents)
        self.scene = SceneRenderer(
            self.engine.state.grid,
            self.labels,
            cell=cell,
            theme=Theme(),
            series_column=self.series is not None,
        )
        self.screen = pygame.display.set_mode(self.scene.size)
        self.clock = pygame.time.Clock()
        self.toggles = OverlayToggles()
        self.tick_rate = tick_rate
        self.paused = False
        self.running = True
        self._accumulator = 0.0
        self._fps = 0
        self._fps_timer = 0.0

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(FPS_CAP) / 1000.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self.on_key(event.key)
                self.update(dt)
                self.render()
                pygame.display.flip()
        finally:
            pygame.quit()

    def on_key(self, key: int) -> None:
        if key in _STEER:
            if self.human is not None:
                self.human.push(_STEER[key])
        elif key in _FOCUS:
            self.focus = _FOCUS[key]
        elif key in _OVERLAYS:
            self.toggles.flip(_OVERLAYS[key])
        elif key == pygame.K_TAB:
            self.toggles.flip_all()
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key == pygame.K_n and self.paused and not self.engine.is_over:
            self.engine.tick()
        elif key == pygame.K_r:
            if self.series is not None:
                self.series.skip()
            else:
                self.engine.reset()
            self._accumulator = 0.0
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.tick_rate = min(60.0, self.tick_rate * 1.25)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.tick_rate = max(2.0, self.tick_rate / 1.25)
        elif key == pygame.K_ESCAPE:
            self.running = False

    def update(self, dt: float) -> None:
        self._fps_timer += dt
        if self._fps_timer >= 0.5:
            self._fps = round(self.clock.get_fps())
            self._fps_timer = 0.0
        if self.paused:
            self._accumulator = 0.0
            return
        if self.series is not None and self.series.update(dt):
            self._accumulator = 0.0
            return
        if self.engine.is_over:
            self._accumulator = 0.0
            return
        self._accumulator += dt
        interval = 1.0 / self.tick_rate
        steps = 0
        while self._accumulator >= interval and not self.engine.is_over:
            self.engine.tick()
            self._accumulator -= interval
            steps += 1
            if steps == MAX_CATCH_UP:
                self._accumulator = 0.0
                break

    def traces(self) -> dict[SnakeId, DecisionTrace]:
        return decision_traces(self.engine)

    def focus_trace(self) -> DecisionTrace | None:
        return self.traces().get(self.focus)

    def render(self) -> None:
        banner: tuple[str, str] | None = None
        if self.engine.is_over:
            banner = self._result_text()
        elif self.paused:
            banner = ("PAUSED", "[SPACE] resume  [N] single step")
        self.scene.draw(
            self.screen,
            self.engine,
            focus=self.focus,
            toggles=self.toggles,
            tick_rate=self.tick_rate,
            fps=self._fps,
            paused=self.paused,
            banner=banner,
            series=self.series,
        )

    def _result_text(self) -> tuple[str, str]:
        title, causes = match_result(self.engine, self.labels)
        series = self.series
        if series is None:
            return title, f"{causes}  -  [R] restart"
        if series.finished:
            stats = series.stats
            score = "  ".join(f"#{i + 1}: {stats.wins[SnakeId(i)]}" for i in range(len(self.labels)))
            return "SERIES COMPLETE", f"{score}  draws: {stats.draws}  -  [ESC] quit"
        wait = series.restart_in
        return title, causes if wait is None else f"{causes}  -  next round in {wait:.1f} s"


def run_app(
    config: MatchConfig,
    agents: Sequence[BaseAgent],
    *,
    tick_rate: float,
    cell: int,
    showcase: ShowcaseOptions | None = None,
) -> None:
    ArenaApp(config, agents, tick_rate=tick_rate, cell=cell, showcase=showcase).run()
