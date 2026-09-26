from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pygame

from ..agents import BaseAgent, TacticalMode
from ..core import Cell, CollisionType, SnakeId
from ..engine import GameResult, MatchConfig, SimulationEngine
from ..view.board import OverlayToggles
from ..view.scene import SceneRenderer, default_focus, match_result
from ..view.theme import Theme
from .writers import OVERLAY_PRESETS, FrameWriter

LETHAL_WINDOW = 150


@dataclass(frozen=True, slots=True)
class RecordOptions:
    fps: int = 15
    cell: int = 22
    overlays: str = "all"
    highlight_lethal: bool = False
    end_hold: float = 1.5
    replay_hold: float = 2.5


@dataclass(frozen=True, slots=True)
class LethalMoment:
    agent: SnakeId
    cell: Cell
    tick: int
    rationale: str


@dataclass(frozen=True, slots=True)
class RecordingSummary:
    size: tuple[int, int]
    fps: int
    frames: int
    ticks: int
    winner: SnakeId | None
    ending: GameResult | None
    lethal_ending: LethalMoment | None
    replayed: bool

    @property
    def duration(self) -> float:
        return self.frames / self.fps


class MatchRecorder:
    """Plays one match off-screen and streams each tick as an RGB24 frame to a FrameWriter."""

    def __init__(
        self, config: MatchConfig, agents: Sequence[BaseAgent], options: RecordOptions | None = None
    ) -> None:
        self.options = options or RecordOptions()
        if self.options.overlays not in OVERLAY_PRESETS:
            raise ValueError(f"unknown overlay preset {self.options.overlays!r}")
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.font.init()
        self.engine = SimulationEngine(config, agents)
        self.labels = tuple(f"#{i + 1} {agent.name}" for i, agent in enumerate(self.engine.agents))
        self.focus = default_focus(self.engine.agents)
        self.toggles = OverlayToggles(*OVERLAY_PRESETS[self.options.overlays])
        self.scene = SceneRenderer(
            self.engine.state.grid, self.labels, cell=self.options.cell, theme=Theme()
        )
        width, height = self.scene.size
        self.size = (width + width % 2, height + height % 2)
        self.frame = pygame.Surface(self.size)
        self._moments: dict[SnakeId, LethalMoment] = {}
        self._replays: dict[SnakeId, pygame.Surface] = {}

    def record(
        self, writer: FrameWriter, progress: Callable[[int], None] | None = None
    ) -> RecordingSummary:
        fps = self.options.fps
        opening = self._render()
        self.engine.tick()
        latest = self._render()
        self._track_lethal()
        writer.calibrate(*self._palette_probe())
        writer.write(opening)
        writer.write(latest)
        del opening
        frames = 2
        while not self.engine.is_over:
            self.engine.tick()
            latest = self._render()
            writer.write(latest)
            frames += 1
            self._track_lethal()
            if progress is not None:
                progress(self.engine.state.tick)

        ending = self._lethal_ending()
        replayed = ending is not None and ending.agent in self._replays
        if ending is not None and replayed:
            self.frame.blit(self._replays[ending.agent], (0, 0))
            self.scene.draw_replay(self.frame, ending.cell, f"#{ending.agent + 1}: {ending.rationale}")
            hold = max(1, round(self.options.replay_hold * fps))
            writer.write(pygame.image.tobytes(self.frame, "RGB"), repeat=hold)
            frames += hold
        hold = max(1, round(self.options.end_hold * fps))
        writer.write(latest, repeat=hold)
        frames += hold
        return RecordingSummary(
            size=self.size,
            fps=fps,
            frames=frames,
            ticks=self.engine.state.tick,
            winner=self.engine.winner,
            ending=self.engine.ending,
            lethal_ending=ending,
            replayed=replayed,
        )

    def _render(self) -> bytes:
        banner = match_result(self.engine, self.labels) if self.engine.is_over else None
        self.scene.draw(
            self.frame,
            self.engine,
            focus=self.focus,
            toggles=self.toggles,
            tick_rate=self.options.fps,
            banner=banner,
            show_timing=False,
        )
        return pygame.image.tobytes(self.frame, "RGB")

    def _track_lethal(self) -> None:
        record = self.engine.last
        if record is None:
            return
        for sid, decision in sorted(record.decisions.items()):
            trace = decision.trace
            if trace is None or trace.mode is not TacticalMode.CONSTRICT or trace.lethal_cut is None:
                continue
            self._moments[sid] = LethalMoment(sid, trace.lethal_cut, self.engine.state.tick, trace.rationale)
            if self.options.highlight_lethal:
                if sid not in self._replays:
                    self._replays[sid] = pygame.Surface(self.size)
                self._replays[sid].blit(self.frame, (0, 0))

    def _lethal_ending(self) -> LethalMoment | None:
        """The winner's last lethal seal, if the loser then died trapped (not head-on) soon after."""
        winner = self.engine.winner
        if winner is None or winner not in self._moments:
            return None
        moment = self._moments[winner]
        losses = [d for d in self.engine.deaths if d.snake_id != winner]
        if not losses or any(d.cause is CollisionType.HEAD_TO_HEAD for d in losses):
            return None
        if self.engine.state.tick - moment.tick > LETHAL_WINDOW:
            return None
        return moment

    def _palette_probe(self) -> tuple[bytes, int]:
        """Frame plain, veiled and with the replay marker, plus theme swatches, to seed the palette."""
        width, height = self.size
        swatches = self.scene.palette_swatches(width)
        probe = pygame.Surface((width, 3 * height + swatches.get_height()))
        for row in range(3):
            probe.blit(self.frame, (0, row * height))
        self.scene.draw_banner(probe.subsurface((0, height, width, height)), "#2 PROBE WINS", "#1 BODY")
        head = self.engine.state.snake(self.focus).head
        self.scene.draw_replay(probe.subsurface((0, 2 * height, width, height)), head, "seal (0,0)")
        probe.blit(swatches, (0, 3 * height))
        return pygame.image.tobytes(probe, "RGB"), probe.get_height()
