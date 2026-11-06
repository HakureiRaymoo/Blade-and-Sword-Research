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

    def runs(self, i: int, limit_x: int | None = None) -> list[tuple[int, bytes]]:
        """Decode row i into [(x_bytes, pixel_bytes), ...].

        Row layout is a repeating triple plus a terminator::

            gap:u16  count:u16  pixels[count]  gap:u16  count:u16  ...  gap:u16

        For map and UI pictures the sum of all gaps and counts is constant per
        image (the scanline width).  Diamond-shaped isometric sprites instead
        vary per row, so the invariant is only "no row is wider than the
        canvas".

        The last row of a picture has no following offset to bound it, and some
        entries carry extra payload after the picture, so `limit_x` lets the
        caller stop the walk once the scanline width is reached.
        """
        r = self.row(i)
        pos = 0
        x = 0
        out: list[tuple[int, bytes]] = []
        while pos + 2 <= len(r):
            gap = struct.unpack_from("<H", r, pos)[0]
            pos += 2
            if limit_x is not None and x + gap > limit_x:
                break
            x += gap
            if pos + 2 > len(r):
                break  # final gap: no run follows
            count = struct.unpack_from("<H", r, pos)[0]
            pos += 2
            if limit_x is not None and x + count > limit_x:
                count = max(0, limit_x - x)
                out.append((x, r[pos:pos + count]))
                break
            if pos + count > len(r):
                count = len(r) - pos
            out.append((x, r[pos:pos + count]))
            pos += count
            x += count
        return out

    @property
    def canvas_bytes(self) -> int:
        """Full scanline width in bytes.

        Rows 0..n-2 are bounded by the next row offset, so they are reliable.
        The last row is only used when the picture has a single row, because
        for that one the table gives no end and the entry may carry extra
        payload (see the docstring of `runs`).
        """
        n = self.row_count
        best = 0
        for i in range(max(1, n - 1)):
            runs = self.runs(i)
            if runs:
                xb, pix = runs[-1]
                best = max(best, xb + len(pix))
        return best

    def width_check(self) -> list[int]:
        """Per-row scanline totals, each bounded by the canvas width."""
        limit = self.canvas_bytes
        totals = []
        for i in range(self.row_count):
            runs = self.runs(i, limit)
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
            for xb, pix in self.runs(y, self.canvas_bytes):
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
