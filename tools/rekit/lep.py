"""Decoder for the "lep" bitmap format (Leyi engine pictures).

Layout (derived from the map tile libraries, see research/02-container-formats.md):

    0x00   4B   "lep\\0"
    0x04  44B   header fields; 0x04..0x2c not fully identified
    0x30   4N   row offset table, values relative to 0x30
    0x30+4N     row payload, rows may have different byte lengths

Rows are *clipped spans*: the format stores only the non-transparent run of
each scanline, which is why an offset table is needed at all. Row widths
therefore vary (a 2:1 isometric diamond grows 4px per row and shrinks back).

Pixel encoding is still being confirmed; several candidates are implemented
and can be compared by eye.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"lep\0"
HEADER_SIZE = 0x30


@dataclass
class LepImage:
    raw: bytes
    fields: tuple[int, ...]
    offsets: list[int]

    # -- parsing ---------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes) -> "LepImage":
        if not data.startswith(MAGIC):
            raise ValueError(f"not a lep file (magic={data[:4]!r})")
        if len(data) < HEADER_SIZE + 4:
            raise ValueError("truncated header")
        fields = tuple(struct.unpack_from("<12I", data, 0x00))
        first = struct.unpack_from("<I", data, HEADER_SIZE)[0]
        if first % 4 or first < 4:
            raise ValueError(f"bad table size probe: first offset {first:#x}")
        n = first // 4
        if HEADER_SIZE + first > len(data):
            raise ValueError("table runs past end of file")
        offsets = list(struct.unpack_from(f"<{n}I", data, HEADER_SIZE))
        return cls(data, fields, offsets)

    # -- rows ------------------------------------------------------------
    @property
    def row_count(self) -> int:
        return len(self.offsets)

    def row(self, i: int) -> bytes:
        base = HEADER_SIZE
        start = base + self.offsets[i]
        end = base + self.offsets[i + 1] if i + 1 < len(self.offsets) else len(self.raw)
        return self.raw[start:end]

    def rows(self):
        for i in range(self.row_count):
            yield self.row(i)

    def span(self, i: int) -> tuple[int, bytes]:
        """Deprecated single-run helper: returns (x_bytes, pixels) of run 0."""
        runs = self.runs(i)
        return runs[0] if runs else (0, b"")

    def runs(self, i: int) -> list[tuple[int, bytes]]:
        """Decode row i into [(x_bytes, pixel_bytes), ...].

        Row layout is a repeating triple plus a terminator::

            gap:u16  count:u16  pixels[count]  gap:u16  count:u16  ...  gap:u16

        Sum of all gaps and counts is constant per image (the scanline width),
        so the trailing gap is the distance to the right edge.
        """
        r = self.row(i)
        pos = 0
        x = 0
        out: list[tuple[int, bytes]] = []
        while pos + 2 <= len(r):
            gap = struct.unpack_from("<H", r, pos)[0]
            pos += 2
            x += gap
            if pos + 2 > len(r):
                break  # final gap: no run follows
            count = struct.unpack_from("<H", r, pos)[0]
            pos += 2
            if pos + count > len(r):
                count = len(r) - pos
            out.append((x, r[pos:pos + count]))
            pos += count
            x += count
        return out

    @property
    def canvas_bytes(self) -> int:
        """Full scanline width in bytes, max over all rows.

        Must use the same clamped run walk as :meth:`runs` -- reading a raw
        ``count`` without clamping lets a malformed/truncated tail run run off
        the end of the row and inflate the width by orders of magnitude (which
        collapses every render to a 1px dot).
        """
        best = 0
        for i in range(self.row_count):
            runs = self.runs(i)
            if not runs:
                continue
            xb, pix = runs[-1]
            best = max(best, xb + len(pix))
        return best

    def width_check(self) -> list[int]:
        """Return per-row scanline totals; they should all be identical."""
        totals = []
        for i in range(self.row_count):
            runs = self.runs(i)
            totals.append(runs[-1][0] + len(runs[-1][1]) if runs else 0)
        return totals

    @property
    def width_px(self) -> int:
        return self.canvas_bytes // 2

    # -- pixel formats ---------------------------------------------------
    def _unpack_565(self, b: int, fmt: str) -> tuple[int, int, int]:
        if fmt in ("rgb565", "bgr565"):
            r5 = (b >> 11) & 0x1F
            g6 = (b >> 5) & 0x3F
            b5 = b & 0x1F
            r, g, bl = r5 * 255 // 31, g6 * 255 // 63, b5 * 255 // 31
            return (bl, g, r) if fmt == "bgr565" else (r, g, bl)
        if fmt == "argb1555":
            r5 = (b >> 10) & 0x1F
            g5 = (b >> 5) & 0x1F
            b5 = b & 0x1F
            return r5 * 255 // 31, g5 * 255 // 31, b5 * 255 // 31
        raise ValueError(fmt)

    def to_rgba(self, fmt: str = "rgb565", center: bool = True):
        """Return (width, height, bytearray RGBA).

        Spans are placed at their stored left pad; `center` only affects rows
        that are inconsistent with the pad rule (kept as a fallback).
        """
        if fmt in ("rgb565", "bgr565", "argb1555"):
            bpp = 2
        elif fmt in ("indexed8", "gray8"):
            bpp = 1
        else:
            raise ValueError(fmt)

        h = self.row_count
        w = self.canvas_bytes // bpp
        out = bytearray(w * h * 4)
        for y in range(h):
            for xb, pix in self.runs(y):
                n = len(pix) // bpp
                x0 = xb // bpp
                if x0 >= w:
                    continue
                n = min(n, w - x0)
                for x in range(n):
                    off = x * bpp
                    if bpp == 2:
                        (v,) = struct.unpack_from("<H", pix, off)
                        r, g, b = self._unpack_565(v, fmt)
                        a = 255
                        if fmt == "argb1555" and not (v & 0x8000):
                            a = 0
                    else:
                        v = pix[off]
                        r = g = b = v
                        a = 0 if v == 0 else 255
                    p = ((y * w) + x0 + x) * 4
                    out[p:p + 4] = bytes((r, g, b, a))
        return w, h, out

    def save_png(self, path: str, fmt: str = "rgb565", center: bool = True, scale: int = 1) -> None:
        from PIL import Image
        w, h, buf = self.to_rgba(fmt, center)
        img = Image.frombytes("RGBA", (w, h), bytes(buf))
        if scale != 1:
            img = img.resize((w * scale, h * scale), Image.NEAREST)
        img.save(path)


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="decode lep files to PNG")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--fmt", default="rgb565",
                    choices=["rgb565", "bgr565", "argb1555", "indexed8", "gray8"])
    ap.add_argument("--scale", type=int, default=1)
    args = ap.parse_args(argv)

    from pathlib import Path
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    for p in args.inputs:
        data = Path(p).read_bytes()
        img = LepImage.parse(data)
        dst = out / (Path(p).stem + f".{args.fmt}.png")
        img.save_png(str(dst), args.fmt, scale=args.scale)
        print(f"{Path(p).name}: rows={img.row_count} max_row_bytes={img.width_px} -> {dst}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
