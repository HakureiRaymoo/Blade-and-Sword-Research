"""Render a composite animation table (a `Spr` entry) to PNG contact sheets.

This is the end-to-end reconstruction: no game needed.

    composite entry  = u16 frameCount
                       per frame: u32 nSub, u32 ?, u32 stride(=7)
                       per sub  : dword flag, ?, ref, A, B, C, D
    ref              = frame<<24 | lib<<20 | localIndex
    frame selector f -> element[f-1]  (0 means "first"), per FUN_005051e0
    draw offset      = (A - C, B - D)  per FUN_0050b3f0

    py tools/rekit/render_composite.py --lib Spr --entry 896 --out out/shots/npc896.png
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve, split_bundle  # noqa: E402
from lep import LepImage  # noqa: E402
from leylib import LeyiLib  # noqa: E402
from scan_composite import LIBS, decode, looks_composite  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


class Pool:
    """Lazily opened libraries, keyed by name."""

    def __init__(self, game) -> None:
        self.game = game
        self._libs: dict[str, LeyiLib] = {}

    def get(self, name: str) -> LeyiLib | None:
        if name not in self._libs:
            p = resolve(self.game, name)
            self._libs[name] = LeyiLib(p) if p else None
        return self._libs[name]

    def image_bytes(self, libname: str, index: int, frame: int) -> bytes | None:
        lib = self.get(libname)
        if lib is None or not 0 <= index < lib.count:
            return None
        data = lib.read(index)
        frames = split_bundle(data)
        if frames:
            k = 0 if frame == 0 else frame - 1
            return frames[k] if 0 <= k < len(frames) else None
        if data[:4] == b"lep\0":
            return data
        return None

    def close(self) -> None:
        for lib in self._libs.values():
            if lib:
                lib.close()


def main(argv=None) -> int:
    from pathlib import Path
    from PIL import Image

    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--lib", default="Spr")
    ap.add_argument("--entry", type=int, required=True)
    ap.add_argument("--frames", type=int, default=0, help="0 = all")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--fmt", default="rgb565")
    ap.add_argument("--pad", type=int, default=6)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    pool = Pool(Path(a.game))
    try:
        lib = pool.get(a.lib)
        if lib is None:
            print(f"library not found: {a.lib}", file=sys.stderr)
            return 1
        data = lib.read(a.entry)
        if not looks_composite(data):
            print(f"{a.lib}#{a.entry} is not a composite table", file=sys.stderr)
            return 1
        frames = decode(data)
        if a.frames:
            frames = frames[: a.frames]
        print(f"{a.lib}#{a.entry}: {len(frames)} frames, "
              f"layers/frame={sorted({len(f) for f in frames})}")

        # decode every (lib, index, frame) pair once
        cache: dict[tuple[str, int, int], Image.Image | None] = {}
        for fr in frames:
            for s in fr:
                key = (s["lib"], s["index"], s["frame"])
                if key in cache:
                    continue
                raw = pool.image_bytes(*key)
                img = None
                if raw:
                    try:
                        w, h, buf = LepImage.parse(raw).to_rgba(a.fmt)
                        img = Image.frombytes("RGBA", (w, h), bytes(buf))
                    except Exception as exc:  # noqa: BLE001
                        print(f"  !! {key}: {exc}", file=sys.stderr)
                cache[key] = img

        # normalise each frame onto a shared canvas
        prepared = []
        for fr in frames:
            items = []
            for s in fr:
                img = cache.get((s["lib"], s["index"], s["frame"]))
                if img is None:
                    continue
                items.append((s["off"][0], s["off"][1], img))
            if not items:
                prepared.append(None)
                continue
            minx = min(o[0] for o in items)
            miny = min(o[1] for o in items)
            maxx = max(o[0] + o[2].width for o in items)
            maxy = max(o[1] + o[2].height for o in items)
            canvas = Image.new("RGBA", (maxx - minx, maxy - miny), (0, 0, 0, 0))
            for ox, oy, img in items:
                canvas.alpha_composite(img, (ox - minx, oy - miny))
            prepared.append((minx, miny, canvas))

        ok = [p for p in prepared if p]
        if not ok:
            print("nothing decoded", file=sys.stderr)
            return 1
        cw = max(p[2].width for p in ok) + a.pad
        ch = max(p[2].height for p in ok) + a.pad
        cols = a.cols
        rows = (len(prepared) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * cw, rows * ch), (26, 26, 30, 255))
        for i, p in enumerate(prepared):
            if not p:
                continue
            _, _, img = p
            sheet.alpha_composite(img, ((i % cols) * cw + a.pad // 2,
                                        (i // cols) * ch + a.pad // 2))
        if a.scale != 1:
            sheet = sheet.resize((sheet.width * a.scale, sheet.height * a.scale),
                                 Image.NEAREST)
        outdir = os.path.dirname(os.path.abspath(a.out))
        os.makedirs(outdir, exist_ok=True)
        sheet.save(a.out)
        print(f"-> {a.out}  {sheet.width}x{sheet.height}")
    finally:
        pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
