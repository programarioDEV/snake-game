import hashlib
import os

import pytest

os.environ["SDL_VIDEODRIVER"] = "dummy"

from snake_arena.agents import AggressiveAIController, BaseAgent, GreedyAgent  # noqa: E402
from snake_arena.engine import GameResult, MatchConfig  # noqa: E402
from snake_arena.record.recorder import MatchRecorder, RecordOptions  # noqa: E402
from support import Circler  # noqa: E402

END_HOLD = round(1.5 * 15)
REPLAY_HOLD = round(2.5 * 15)


class FakeWriter:
    """Keeps only digests, so the test itself never accumulates frames either."""

    def __init__(self) -> None:
        self.calibrations: list[tuple[int, int]] = []
        self.frames: list[tuple[str, int]] = []
        self.lengths: set[int] = set()

    def calibrate(self, sample: bytes, height: int) -> None:
        self.calibrations.append((len(sample), height))

    def write(self, frame: bytes, repeat: int = 1) -> None:
        assert self.calibrations, "the palette must be calibrated before the first frame"
        self.lengths.add(len(frame))
        self.frames.append((hashlib.sha256(frame).hexdigest(), repeat))

    def close(self) -> None:
        pass


def agents() -> list[BaseAgent]:
    return [GreedyAgent(), AggressiveAIController()]


SMALL = MatchConfig(width=13, height=13, arena="open", max_ticks=30, seed=1)
LETHAL = MatchConfig(width=15, height=15, arena="cross", max_ticks=400, seed=37)


def test_each_tick_becomes_one_rgb_frame_and_the_last_one_is_held() -> None:
    recorder = MatchRecorder(SMALL, agents(), RecordOptions(cell=8))
    writer = FakeWriter()
    summary = recorder.record(writer)

    width, height = recorder.size
    assert width % 2 == 0 and height % 2 == 0
    assert writer.lengths == {width * height * 3}
    [(sample_length, sample_height)] = writer.calibrations
    assert sample_height > height and sample_length == width * sample_height * 3
    assert len(writer.frames) == summary.ticks + 2
    assert writer.frames[-1][1] == END_HOLD
    assert summary.frames == summary.ticks + 1 + END_HOLD
    assert summary.duration == summary.frames / 15


def test_same_seed_and_agents_render_identical_frames() -> None:
    first = FakeWriter()
    second = FakeWriter()
    MatchRecorder(SMALL, agents(), RecordOptions(cell=8)).record(first)
    MatchRecorder(SMALL, agents(), RecordOptions(cell=8)).record(second)
    assert first.frames == second.frames


def test_overlay_presets_change_the_rendered_pixels() -> None:
    plain = FakeWriter()
    full = FakeWriter()
    MatchRecorder(SMALL, agents(), RecordOptions(cell=8, overlays="none")).record(plain)
    MatchRecorder(SMALL, agents(), RecordOptions(cell=8, overlays="all")).record(full)
    assert len(plain.frames) == len(full.frames)
    assert plain.frames[5] != full.frames[5]


def test_lethal_cut_ending_is_replayed_before_the_final_hold() -> None:
    writer = FakeWriter()
    summary = MatchRecorder(LETHAL, agents(), RecordOptions(cell=8, highlight_lethal=True)).record(writer)

    assert summary.lethal_ending is not None and summary.replayed
    assert (summary.ticks, summary.lethal_ending.tick) == (27, 23)
    replay, final = writer.frames[-2], writer.frames[-1]
    assert (replay[1], final[1]) == (REPLAY_HOLD, END_HOLD)
    assert replay[0] not in {digest for digest, _ in writer.frames[:-2]}
    assert summary.frames == summary.ticks + 1 + REPLAY_HOLD + END_HOLD


def test_lethal_ending_is_reported_but_not_replayed_without_the_flag() -> None:
    writer = FakeWriter()
    summary = MatchRecorder(LETHAL, agents(), RecordOptions(cell=8)).record(writer)
    assert summary.lethal_ending is not None and not summary.replayed
    assert writer.frames[-1][1] == END_HOLD
    assert len(writer.frames) == summary.ticks + 2


def test_max_ticks_caps_the_recording() -> None:
    config = MatchConfig(width=13, height=13, arena="open", max_ticks=6, seed=2)
    summary = MatchRecorder(config, agents(), RecordOptions(cell=8)).record(FakeWriter())
    assert summary.ticks == 6


def test_a_looping_match_is_recorded_until_the_cycle_draw() -> None:
    config = MatchConfig(width=13, height=13, arena="open", food_count=0)
    writer = FakeWriter()
    summary = MatchRecorder(config, [Circler(), Circler()], RecordOptions(cell=8)).record(writer)
    assert summary.ending is GameResult.DRAW_CYCLE
    assert (summary.winner, summary.ticks) == (None, 10)
    assert len(writer.frames) == summary.ticks + 2


def test_unknown_overlay_preset_is_rejected() -> None:
    with pytest.raises(ValueError):
        MatchRecorder(SMALL, agents(), RecordOptions(overlays="path"))
