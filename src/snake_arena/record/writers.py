from __future__ import annotations

from pathlib import Path
from typing import Protocol

FORMATS = ("gif", "mp4")
OVERLAY_PRESETS: dict[str, tuple[bool, bool, bool, bool]] = {
    "all": (True, True, True, True),
    "voronoi": (True, False, False, False),
    "chokepoints": (False, False, False, True),
    "none": (False, False, False, False),
}
INSTALL_HINT = 'pip install "snake-arena[record]"'


class RecorderDependencyError(RuntimeError):
    """An optional export dependency (Pillow, imageio-ffmpeg) is missing."""


class FrameWriter(Protocol):
    """Streaming sink for raw RGB24 frames; implementations never hold the whole video."""

    def calibrate(self, sample: bytes, height: int) -> None: ...

    def write(self, frame: bytes, repeat: int = 1) -> None: ...

    def close(self) -> None: ...


def resolve_format(path: Path, forced: str | None = None) -> str:
    if forced is not None:
        if forced not in FORMATS:
            raise ValueError(f"unsupported format {forced!r}; choose one of {', '.join(FORMATS)}")
        return forced
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in FORMATS:
        raise ValueError(f"cannot infer the video format from '{path.name}'; pass --format gif|mp4")
    return suffix


def open_writer(path: Path, fmt: str, size: tuple[int, int], fps: int) -> FrameWriter:
    if fmt == "gif":
        try:
            from .gif import GifWriter
        except ModuleNotFoundError as exc:
            raise RecorderDependencyError(
                f"GIF export needs Pillow ('{exc.name}' is not installed): {INSTALL_HINT}"
            ) from exc
        return GifWriter(path, size, fps)
    if fmt == "mp4":
        try:
            from .mp4 import Mp4Writer
        except ModuleNotFoundError as exc:
            raise RecorderDependencyError(
                f"MP4 export needs imageio-ffmpeg ('{exc.name}' is not installed): {INSTALL_HINT}"
            ) from exc
        return Mp4Writer(path, size, fps)
    raise ValueError(f"unsupported format {fmt!r}")
