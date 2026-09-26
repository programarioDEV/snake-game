from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from snake_arena.record.gif import GifWriter  # noqa: E402

W, H = 6, 4
BG, RED, BLUE = (18, 21, 29), (255, 88, 102), (77, 163, 255)


def frame(*cells: tuple[int, int, tuple[int, int, int]]) -> bytes:
    pixels = bytearray(bytes(BG) * (W * H))
    for x, y, color in cells:
        start = (y * W + x) * 3
        pixels[start : start + 3] = bytes(color)
    return bytes(pixels)


def decode(path: Path) -> list[tuple[bytes, int, tuple[int, int, int, int]]]:
    frames = []
    with Image.open(path) as gif:
        for index in range(getattr(gif, "n_frames", 1)):
            gif.seek(index)
            extent = gif.tile[0][1]
            assert extent is not None
            frames.append((gif.convert("RGB").tobytes(), int(gif.info["duration"]), extent))
    return frames


def encode(path: Path, frames: list[bytes], fps: int = 10) -> None:
    writer = GifWriter(path, (W, H), fps)
    writer.calibrate(b"".join(frames), H * len(frames))
    for data in frames:
        writer.write(data)
    writer.close()


def test_frames_round_trip_exactly_and_only_changed_regions_are_encoded(tmp_path: Path) -> None:
    frames = [frame(), frame((1, 1, RED)), frame((1, 1, RED), (4, 2, BLUE))]
    encode(tmp_path / "clip.gif", frames)
    decoded = decode(tmp_path / "clip.gif")

    assert [pixels for pixels, _, _ in decoded] == frames
    assert [extent for _, _, extent in decoded] == [(0, 0, W, H), (1, 1, 2, 2), (4, 2, 5, 3)]
    assert [duration for _, duration, _ in decoded] == [100, 100, 100]


def test_identical_frames_merge_into_one_longer_delay(tmp_path: Path) -> None:
    path = tmp_path / "hold.gif"
    still, moved = frame(), frame((2, 2, RED))
    writer = GifWriter(path, (W, H), 10)
    writer.calibrate(still + moved, 2 * H)
    writer.write(still)
    writer.write(moved)
    writer.write(moved)
    writer.write(moved, repeat=3)
    writer.close()

    assert writer.encoded_frames == 2
    assert [duration for _, duration, _ in decode(path)] == [100, 500]


def test_fractional_frame_rates_keep_the_average_rate_exact(tmp_path: Path) -> None:
    frames = [frame(), frame((0, 0, RED)), frame((0, 0, BLUE))]
    encode(tmp_path / "fps15.gif", frames, fps=15)
    durations = [duration for _, duration, _ in decode(tmp_path / "fps15.gif")]
    assert durations == [70, 60, 70]
    assert sum(durations) == 200


def test_same_input_gives_byte_identical_files(tmp_path: Path) -> None:
    frames = [frame(), frame((3, 1, BLUE)), frame((3, 1, BLUE), (5, 3, RED))]
    encode(tmp_path / "a.gif", frames)
    encode(tmp_path / "b.gif", frames)
    assert (tmp_path / "a.gif").read_bytes() == (tmp_path / "b.gif").read_bytes()


def test_palette_only_holds_colors_present_in_the_sample(tmp_path: Path) -> None:
    near_black = (12, 12, 12)
    frames = [frame((0, 0, RED)), frame((0, 0, near_black))]
    encode(tmp_path / "sparse.gif", frames)
    assert [pixels for pixels, _, _ in decode(tmp_path / "sparse.gif")] == frames


def test_writing_before_calibration_is_an_error(tmp_path: Path) -> None:
    writer = GifWriter(tmp_path / "raw.gif", (W, H), 10)
    with pytest.raises(RuntimeError):
        writer.write(frame())
    writer.close()


@pytest.mark.parametrize("fps", [0, 51])
def test_frame_rates_outside_gif_delays_are_rejected(tmp_path: Path, fps: int) -> None:
    with pytest.raises(ValueError):
        GifWriter(tmp_path / "bad.gif", (W, H), fps)
