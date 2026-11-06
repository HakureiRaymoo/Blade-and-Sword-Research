"""Measure how the engine places animation frames on screen.

Pipeline per screenshot:
  1. estimate the camera shift against the first shot (background patch),
  2. locate the best matching exported frame (masked NCC),
  3. remove the camera shift, then compare placement hypotheses:
       top-left     (x, y)
       bottom-centre (x + w/2, y + h)

If one of the two anchors has near-zero spread across frames of different
sizes, that is the engine's rule. If neither is stable but the residual is
smooth, the engine carries per-frame offsets.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from match_frames import Template, ncc_map, to_lum  # noqa: E402

REGION = (760, 420, 1124, 869)
BG_PATCH = (40, 40, 360, 260)   # static scenery, top-left
MAX_CAM = 48


def camera_shift(ref: np.ndarray, cur: np.ndarray) -> tuple[int, int]:
    x0, y0, x1, y1 = BG_PATCH
    a = ref[y0:y1, x0:x1]
    best = (1e18, 0, 0)
    pad = 16
    for dy in range(-MAX_CAM, MAX_CAM + 1, 2):
        for dx in range(-MAX_CAM, MAX_CAM + 1, 2):
            ys, xs = y0 + dy, x0 + dx
            if ys < 0 or xs < 0 or ys + (y1 - y0) > cur.shape[0] or xs + (x1 - x0) > cur.shape[1]:
                continue
            b = cur[ys:ys + (y1 - y0), xs:xs + (x1 - x0)]
            d = ((a - b) ** 2).mean()
            if d < best[0]:
                best = (d, dx, dy)
    return best[1], best[2]


def main(argv: list[str]) -> int:
    shots_dir, templates_dir = argv[0], argv[1]
    tmpls = []
    for f in sorted(os.listdir(templates_dir)):
        if f.endswith(".png"):
            t = Template(os.path.join(templates_dir, f))
            if t.usable and min(t.w, t.h) >= 12:
                tmpls.append(t)

    shots = sorted(f for f in os.listdir(shots_dir) if f.lower().endswith(".bmp"))
    lums = [to_lum(np.asarray(Image.open(os.path.join(shots_dir, s)).convert("RGB")).astype(np.float64))
            for s in shots]
    ref = lums[0]

    rows = []
    for name, lum in zip(shots, lums):
        cdx, cdy = camera_shift(ref, lum)
        x0, y0, x1, y1 = REGION
        sub = lum[y0:y1, x0:x1]
        best = (-2.0, None, 0, 0)
        for t in tmpls:
            if t.h >= sub.shape[0] or t.w >= sub.shape[1]:
                continue
            m = ncc_map(sub, t)
            idx = int(np.argmax(m))
            y, x = divmod(idx, m.shape[1])
            s = float(m[y, x])
            if s > best[0]:
                best = (s, t, x + x0, y + y0)
        score, t, x, y = best
        rows.append(dict(shot=name, ncc=score, t=os.path.basename(t.path),
                         x=x, y=y, w=t.w, h=t.h, camx=cdx, camy=cdy,
                         wx=x + cdx, wy=y + cdy))

    print(f"usable templates: {len(tmpls)}   shots: {len(rows)}\n")
    hdr = f"{'shot':<9} {'frame':<16} {'ncc':>5} {'x':>4} {'y':>4} {'w':>3} {'h':>3} {'cam':>7} {'wx':>5} {'wy':>5} {'cx':>5} {'by':>5}"
    print(hdr)
    for r in rows:
        print(f"{r['shot']:<9} {r['t']:<16} {r['ncc']:>5.3f} {r['x']:>4} {r['y']:>4} "
              f"{r['w']:>3} {r['h']:>3} {str((r['camx'], r['camy'])):>7} "
              f"{r['wx']:>5} {r['wy']:>5} {r['wx'] + r['w'] // 2:>5} {r['wy'] + r['h']:>5}")

    good = [r for r in rows if r['ncc'] > 0.62]
    if len(good) < 3:
        print("\nnot enough confident matches to judge")
        return 0
    tl_x = np.std([r['wx'] for r in good])
    tl_y = np.std([r['wy'] for r in good])
    bc_x = np.std([r['wx'] + r['w'] / 2 for r in good])
    bc_y = np.std([r['wy'] + r['h'] for r in good])
    print(f"\nconfident matches: {len(good)} / {len(rows)}")
    print(f"  top-left      spread: x={tl_x:.2f}  y={tl_y:.2f}")
    print(f"  bottom-centre spread: x={bc_x:.2f}  y={bc_y:.2f}")
    sizes = len({(r['w'], r['h']) for r in good})
    print(f"  distinct frame sizes: {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
