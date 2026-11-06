"""Render a range of library entries into a labelled contact sheet PNG.

Each cell shows the first frame of the entry (or the single `lep` image), scaled
to fit, with the entry index drawn in the corner. Used to eyeball what a region
of a library actually contains.

    py tools/rekit/contact_sheet.py --lib Spr --start 880 --count 40 \
        --out out/shots/spr_880.png
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve, split_bundle  # noqa: E402
from lep import LepImage  # noqa: E402
from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


def first_frame(data: bytes) -> bytes | None:
    frames = split_bundle(data)
    if frames:
        return frames[0]
    if data[:4] == b"lep\0":
        return data
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--lib", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--cell", type=int, default=140)
    ap.add_argument("--fmt", default="rgb565")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    from PIL import Image, ImageDraw

    path = resolve(__import__("pathlib").Path(a.game), a.lib)
    if path is None:
        print(f"library not found: {a.lib}", file=sys.stderr)
        return 1

    cols = a.cols
    rows = (a.count + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * a.cell, rows * a.cell), (24, 24, 28, 255))
    draw = ImageDraw.Draw(sheet)

    with LeyiLib(path) as lib:
        for k in range(a.count):
            idx = a.start + k
            if idx >= lib.count:
                break
            cx = (k % cols) * a.cell
            cy = (k // cols) * a.cell
            draw.rectangle([cx, cy, cx + a.cell - 1, cy + a.cell - 1], outline=(70, 70, 80, 255))
            data = lib.read(idx)
            payload = first_frame(data)
            if payload is None:
                draw.text((cx + 6, cy + 6), f"{idx} raw", fill=(255, 120, 120, 255))
                continue
            try:
                w, h, buf = LepImage.parse(payload).to_rgba(a.fmt)
            except Exception as exc:  # noqa: BLE001
                draw.text((cx + 6, cy + 6), f"{idx} err", fill=(255, 120, 120, 255))
                print(f"{idx}: {exc}", file=sys.stderr)
                continue
            img = Image.frombytes("RGBA", (w, h), bytes(buf))
            scale = min((a.cell - 18) / max(w, 1), (a.cell - 18) / max(h, 1), 4.0)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            img = img.resize((nw, nh), Image.NEAREST)
            sheet.alpha_composite(img, (cx + (a.cell - nw) // 2, cy + a.cell - nh - 4))
            nf = len(split_bundle(data) or [1]) if data[:4] != b"lep\0" else 1
            draw.text((cx + 4, cy + 3), f"{idx}x{nf}", fill=(220, 220, 120, 255))

    outdir = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(outdir, exist_ok=True)
    sheet.save(a.out)
    print(f"{a.out}  {sheet.size[0]}x{sheet.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
