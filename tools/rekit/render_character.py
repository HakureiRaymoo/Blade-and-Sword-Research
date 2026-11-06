"""Assemble a whole character from all of its part tables.

Every `Spr` entry that references `ResPlayer1` is one *body part* with a
512-frame timeline.  The action columns in `Role.txt` (初始态 0, 平休1 16,
平时走路 48, 跑步 80, …) all fit inside 0..511, so a frame index is simply a
position on that shared timeline: combining all parts at the same index should
give one complete character pose.

    py tools/rekit/render_character.py --frame 0 --out out/shots/char_f0.png
    py tools/rekit/render_character.py --frames 0,16,48,80 --cols 4
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve, split_bundle  # noqa: E402
from lep import LepImage  # noqa: E402
from leylib import LeyiLib  # noqa: E402
from scan_composite import decode, looks_composite  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"
TARGET = "ResPlayer1"


def collect_parts(spr: LeyiLib, target: str = TARGET) -> list[dict]:
    parts = []
    for i in range(spr.count):
        d = spr.read(i)
        if not looks_composite(d):
            continue
        frames = decode(d)
        if not any(s["lib"] == target for fr in frames for s in fr):
            continue
        idxs = {s["index"] for fr in frames for s in fr if s["lib"] == target}
        parts.append({"entry": i, "frames": frames, "n_idx": len(idxs),
                      "span": (min(idxs), max(idxs)) if idxs else (-1, -1)})
    return parts
def main(argv=None) -> int:
    from PIL import Image

    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--frames", default="", help="comma list, overrides --frame")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--min-parts", type=int, default=50,
                    help="only use tables that reference at least this many bundle indices")
    ap.add_argument("--only", default="", help="comma list of Spr entries to force")
    ap.add_argument("--target", default=TARGET,
                    help="which library the part tables must reference (default ResPlayer1)")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    from pathlib import Path

    game = Path(a.game)
    spr = LeyiLib(resolve(game, "Spr"))
    pools: dict[str, LeyiLib] = {}

    def pool(name: str) -> LeyiLib | None:
        if name not in pools:
            p = resolve(game, name)
            pools[name] = LeyiLib(p) if p else None
        return pools[name]

    def frame_image(libname: str, index: int, frame: int):
        lib = pool(libname)
        if lib is None or not 0 <= index < lib.count:
            return None
        data = lib.read(index)
        frames = split_bundle(data)
        if frames:
            k = 0 if frame == 0 else frame - 1
            if not 0 <= k < len(frames):
                return None
            data = frames[k]
        if data[:4] != b"lep\0":
            return None
        try:
            w, h, buf = LepImage.parse(data).to_rgba("rgb565")
            return Image.frombytes("RGBA", (w, h), bytes(buf))
        except Exception:  # noqa: BLE001
            return None

    parts = collect_parts(spr, a.target)
    if a.only:
        wanted = {int(x) for x in a.only.split(",") if x.strip()}
        parts = [p for p in parts if p["entry"] in wanted]
    else:
        parts = [p for p in parts if p["n_idx"] >= a.min_parts]
    print(f"using {len(parts)} part tables: {[p['entry'] for p in parts]}")

    want = [int(x) for x in a.frames.split(",")] if a.frames else [a.frame]

    cache: dict[tuple[str, int, int], object] = {}
    tiles = []
    for fi in want:
        items = []
        for p in parts:
            if fi >= len(p["frames"]):
                continue
            for s in p["frames"][fi]:
                key = (s["lib"], s["index"], s["frame"])
                if key not in cache:
                    cache[key] = frame_image(*key)
                img = cache[key]
                if img is not None:
                    items.append((s["off"][0], s["off"][1], img))
        if not items:
            tiles.append(None)
            continue
        minx = min(o[0] for o in items)
        miny = min(o[1] for o in items)
        maxx = max(o[0] + o[2].width for o in items)
        maxy = max(o[1] + o[2].height for o in items)
        canvas = Image.new("RGBA", (maxx - minx, maxy - miny), (0, 0, 0, 0))
        for ox, oy, img in items:
            canvas.alpha_composite(img, (ox - minx, oy - miny))
        tiles.append(canvas)
        print(f"  frame {fi}: {len(items)} layers, canvas {canvas.width}x{canvas.height}")

    ok = [t for t in tiles if t]
    if not ok:
        print("nothing assembled", file=sys.stderr)
        return 1
    cw = max(t.width for t in ok) + 8
    ch = max(t.height for t in ok) + 8
    cols = min(a.cols, max(1, len(tiles)))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (26, 26, 30, 255))
    for i, t in enumerate(tiles):
        if t:
            sheet.alpha_composite(t, ((i % cols) * cw + 4, (i // cols) * ch + 4))
    if a.scale != 1:
        sheet = sheet.resize((sheet.width * a.scale, sheet.height * a.scale), Image.NEAREST)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f"-> {a.out}  {sheet.width}x{sheet.height}")

    for lib in pools.values():
        if lib:
            lib.close()
    spr.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

