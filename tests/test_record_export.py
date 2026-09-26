import sys
from pathlib import Path

import pytest

from snake_arena.record.writers import RecorderDependencyError, open_writer, resolve_format


@pytest.mark.parametrize(
    ("name", "forced", "expected"),
    [("clip.gif", None, "gif"), ("CLIP.MP4", None, "mp4"), ("clip.bin", "gif", "gif"), ("clip.gif", "mp4", "mp4")],
)
def test_format_comes_from_the_extension_unless_forced(name: str, forced: str | None, expected: str) -> None:
    assert resolve_format(Path(name), forced) == expected


@pytest.mark.parametrize(("name", "forced"), [("clip.webm", None), ("clip", None), ("clip.gif", "avi")])
def test_unknown_formats_are_rejected(name: str, forced: str | None) -> None:
    with pytest.raises(ValueError):
        resolve_format(Path(name), forced)


@pytest.mark.parametrize(
    ("fmt", "blocked", "writer_module"),
    [("gif", "PIL", "snake_arena.record.gif"), ("mp4", "imageio_ffmpeg", "snake_arena.record.mp4")],
)
def test_missing_dependencies_point_to_the_record_extra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fmt: str, blocked: str, writer_module: str
) -> None:
    monkeypatch.delitem(sys.modules, writer_module, raising=False)
    monkeypatch.setitem(sys.modules, blocked, None)
    with pytest.raises(RecorderDependencyError, match=r'pip install "snake-arena\[record\]"'):
        open_writer(tmp_path / f"clip.{fmt}", fmt, (16, 8), 10)


def test_mp4_stream_decodes_to_every_frame_and_is_reproducible(tmp_path: Path) -> None:
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    from snake_arena.record.mp4 import Mp4Writer

    size = (16, 8)
    frames = [bytes([shade, 40, 255 - shade]) * (size[0] * size[1]) for shade in (0, 80, 160, 240)]
    for name in ("a.mp4", "b.mp4"):
        writer = Mp4Writer(tmp_path / name, size, 10)
        writer.calibrate(b"", 0)
        for data in frames:
            writer.write(data)
        writer.write(frames[-1], repeat=3)
        writer.close()

    reader = imageio_ffmpeg.read_frames(str(tmp_path / "a.mp4"))
    meta = next(reader)
    assert tuple(meta["size"]) == size
    assert sum(1 for _ in reader) == len(frames) + 3
    assert (tmp_path / "a.mp4").read_bytes() == (tmp_path / "b.mp4").read_bytes()


def test_mp4_rejects_odd_frame_sizes(tmp_path: Path) -> None:
    pytest.importorskip("imageio_ffmpeg")
    from snake_arena.record.mp4 import Mp4Writer

    with pytest.raises(ValueError):
        Mp4Writer(tmp_path / "odd.mp4", (15, 8), 10)
