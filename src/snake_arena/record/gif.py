from __future__ import annotations

from pathlib import Path

from PIL import GifImagePlugin, Image, ImageChops

TRANSPARENT = 255
_COLORS = 255
_CHANGED = [0] + [255] * 255


class GifWriter:
    """Streaming GIF89a encoder: global palette, transparent delta frames, merged duplicates."""

    def __init__(self, path: Path, size: tuple[int, int], fps: int) -> None:
        if not 1 <= fps <= 50:
            raise ValueError("GIF delays are centiseconds and browsers clamp < 2 cs: use 1-50 fps")
        self.size = size
        self.fps = fps
        self.encoded_frames = 0
        self._file = path.open("wb")
        self._palette: Image.Image | None = None
        self._previous: bytes | None = None
        self._pending: tuple[Image.Image, tuple[int, int], bool] | None = None
        self._pending_cs = 0
        self._ticks = 0

    def calibrate(self, sample: bytes, height: int) -> None:
        """Fix the global palette from a representative RGB sample (full frame width)."""
        if self._palette is not None:
            raise RuntimeError("the palette is already fixed")
        probe = Image.frombytes("RGB", (self.size[0], height), sample)
        quantized = probe.quantize(
            colors=_COLORS, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
        )
        # Pillow pads unused entries with black; keep only real colors so none is spurious.
        used = max(index for index, count in enumerate(quantized.histogram()) if count) + 1
        colors = (quantized.getpalette() or [])[: used * 3]
        self._palette = Image.new("P", (1, 1))
        self._palette.putpalette(colors)
        canvas = Image.new("P", self.size)
        canvas.putpalette(colors + [0] * (_COLORS * 3 - len(colors)) + [0, 0, 0])
        header, _ = GifImagePlugin.getheader(canvas, info={"loop": 0})
        for chunk in header:
            self._file.write(chunk)

    def write(self, frame: bytes, repeat: int = 1) -> None:
        if repeat < 1:
            raise ValueError("repeat must be at least 1")
        if self._palette is None:
            raise RuntimeError("calibrate() must fix the palette before the first frame")
        rgb = Image.frombytes("RGB", self.size, frame)
        indexed = rgb.quantize(palette=self._palette, dither=Image.Dither.NONE)
        raw = indexed.tobytes()
        delay = self._advance(repeat)
        if raw == self._previous:
            self._pending_cs += delay
            return
        self._flush()
        self._pending = self._delta(indexed, raw)
        self._pending_cs = delay
        self._previous = raw

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            self._flush()
            if self._palette is not None:
                self._file.write(b";")
        finally:
            self._file.close()

    def _advance(self, repeat: int) -> int:
        # Rounded cumulative timestamps keep the average rate exact at fps that do not divide 100.
        start = round(self._ticks * 100 / self.fps)
        self._ticks += repeat
        return round(self._ticks * 100 / self.fps) - start

    def _delta(self, indexed: Image.Image, raw: bytes) -> tuple[Image.Image, tuple[int, int], bool]:
        if self._previous is None:
            return indexed, (0, 0), False
        before = Image.frombytes("L", self.size, self._previous)
        after = Image.frombytes("L", self.size, raw)
        changed = ImageChops.difference(before, after)
        bbox = changed.getbbox()
        assert bbox is not None
        delta = Image.new("P", self.size, TRANSPARENT)
        delta.paste(indexed, mask=changed.point(_CHANGED))
        return delta.crop(bbox), (bbox[0], bbox[1]), True

    def _flush(self) -> None:
        if self._pending is None:
            return
        image, offset, transparent = self._pending
        params = {"duration": self._pending_cs * 10, "disposal": 1}
        if transparent:
            params["transparency"] = TRANSPARENT
        for chunk in GifImagePlugin.getdata(image, offset, **params):
            self._file.write(chunk)
        self._pending = None
        self.encoded_frames += 1
