from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import imageio_ffmpeg

from .writers import INSTALL_HINT, RecorderDependencyError

_OUTPUT_PARAMS = [
    "-crf", "18",
    "-preset", "medium",
    "-tune", "animation",
    "-fflags", "+bitexact",
    "-flags:v", "+bitexact",
    "-map_metadata", "-1",
]


class Mp4Writer:
    """Pipes raw RGB24 frames straight into ffmpeg (H.264, yuv420p) via imageio-ffmpeg."""

    def __init__(self, path: Path, size: tuple[int, int], fps: int) -> None:
        if size[0] % 2 or size[1] % 2:
            raise ValueError("H.264 with yuv420p needs even frame dimensions")
        try:
            imageio_ffmpeg.get_ffmpeg_exe()
        except RuntimeError as exc:
            raise RecorderDependencyError(f"no ffmpeg binary available: {INSTALL_HINT}") from exc
        self.size = size
        self.fps = fps
        self._stream: Generator[None, bytes | None, None] = imageio_ffmpeg.write_frames(
            str(path),
            size,
            fps=fps,
            codec="libx264",
            pix_fmt_in="rgb24",
            pix_fmt_out="yuv420p",
            quality=None,
            macro_block_size=2,
            ffmpeg_log_level="error",
            output_params=list(_OUTPUT_PARAMS),
        )
        self._stream.send(None)
        self._closed = False

    def calibrate(self, sample: bytes, height: int) -> None:
        """H.264 has no palette to prepare."""

    def write(self, frame: bytes, repeat: int = 1) -> None:
        for _ in range(repeat):
            self._stream.send(frame)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._stream.close()
