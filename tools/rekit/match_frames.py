"""Locate exported animation frames inside live game screenshots.

Masked normalized cross-correlation (NCC), implemented with numpy FFT so no
OpenCV is needed. NCC is used instead of raw SSD because it is invariant to
the game's lighting/contrast and does not get fooled by flat regions such as
the character's shadow.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

EPS = 1e-9


def corr2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Valid-region cross correlation: out[y,x] = sum a[y+u, x+v] * b[u,v]."""
    shape = (a.shape[0] + b.shape[0] - 1, a.shape[1] + b.shape[1] - 1)
    fa = np.fft.rfft2(a, shape)
    fb = np.fft.rfft2(b, shape)
    c = np.fft.irfft2(fa * np.conj(fb), shape)
    return c[: a.shape[0] - b.shape[0] + 1, : a.shape[1] - b.shape[1] + 1]


def to_lum(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.3 + rgb[..., 1] * 0.6 + rgb[..., 2] * 0.1


class Template:
    def __init__(self, path: str) -> None:
        img = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
        self.path = path
        self.mask = (img[..., 3] > 0).astype(np.float64)
        self.area = self.mask.sum()
        self.lum = to_lum(img[..., :3])
        self.sum = (self.lum * self.mask).sum()
        self.sq = (self.lum ** 2 * self.mask).sum()
        self.var = self.sq - self.sum ** 2 / max(self.area, 1.0)
        self.h, self.w = self.lum.shape

    @property
    def usable(self) -> bool:
        return self.area >= 600 and self.var > 2000


def ncc_map(image: np.ndarray, t: Template) -> np.ndarray:
    m = t.mask
    c_i = corr2(image, m)                      # sum M*I
    c_ii = corr2(image ** 2, m)                # sum M*I^2
    c_it = corr2(image, t.lum * m)             # sum M*I*T
    num = c_it - (c_i * t.sum) / t.area
    var_i = c_ii - (c_i * c_i) / t.area
    den = np.sqrt(np.maximum(var_i, 0.0) * max(t.var, EPS))
    return num / np.maximum(den, EPS)


def main(argv: list[str]) -> int:
    shots_dir, templates_dir = argv[0], argv[1]
    region = (820, 480, 1124, 869)
    tmpls = []
    for f in sorted(os.listdir(templates_dir)):
        if not f.endswith(".png"):
            continue
        t = Template(os.path.join(templates_dir, f))
        if t.usable:
            tmpls.append(t)
    print(f"usable templates: {len(tmpls)} / {len(os.listdir(templates_dir))}")

    x0, y0, x1, y1 = region
    rows = []
    for shot in sorted(f for f in os.listdir(shots_dir) if f.lower().endswith(".bmp")):
        rgb = np.asarray(Image.open(os.path.join(shots_dir, shot)).convert("RGB")).astype(np.float64)
        sub = to_lum(rgb[y0:y1, x0:x1])
        scored = []
        for t in tmpls:
            if t.h >= sub.shape[0] or t.w >= sub.shape[1]:
                continue
            ncc = ncc_map(sub, t)
            idx = int(np.argmax(ncc))
            y, x = divmod(idx, ncc.shape[1])
            scored.append((float(ncc[y, x]), t, x + x0, y + y0))
        scored.sort(key=lambda s: -s[0])
        best = scored[0]
        rows.append((shot, best))
        top3 = ", ".join(f"{os.path.basename(t.path)}@{x},{y}({s:.3f})" for s, t, x, y in scored[:3])
        print(f"{shot}: {top3}")

    print("\nbest match bbox geometry (x, y, w, h, x+w/2, y+h):")
    for shot, (s, t, x, y) in rows:
        print(f"  {shot:<10} {os.path.basename(t.path):<18} x={x:<5} y={y:<5} w={t.w:<3} h={t.h:<3} "
              f"cx={x + t.w // 2:<5} by={y + t.h:<5} ncc={s:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
