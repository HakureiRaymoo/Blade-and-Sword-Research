"""Classify the `Spr` composite tables that belong to the player character.

Every character is not one table but a *set* of tables, one per body part.  All
of them reference `ResPlayer1` (lib index 3), so the 82 `Spr` entries that do so
are the player's action tables.  This tool summarises each of them (frame count,
layer count, layer image sizes, referenced bundle range) so they can be grouped
into parts.

    py tools/rekit/player_parts.py
    py tools/rekit/player_parts.py --sizes
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve, split_bundle  # noqa: E402
from lep import LepImage  # noqa: E402
from leylib import LeyiLib  # noqa: E402
from scan_composite import decode, looks_composite  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


def main(argv=None) -> int:
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--target", default="ResPlayer1")
    ap.add_argument("--sizes", action="store_true", help="also decode layer image sizes")
    a = ap.parse_args(argv)

    game = Path(a.game)
    spr = LeyiLib(resolve(game, "Spr"))
    pools: dict[str, LeyiLib] = {}

    def pool(name: str) -> LeyiLib:
        if name not in pools:
            p = resolve(game, name)
            pools[name] = LeyiLib(p) if p else None
        return pools[name]

    def size_of(libname: str, index: int, frame: int) -> tuple[int, int] | None:
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
            img = LepImage.parse(data)
            return img.width_px, img.row_count
        except Exception:  # noqa: BLE001
            return None

    rows = []
    for i in range(spr.count):
        d = spr.read(i)
        if not looks_composite(d):
            continue
        frames = decode(d)
        libs = {s["lib"] for fr in frames for s in fr}
        if a.target not in libs:
            continue
        nsub = Counter(len(fr) for fr in frames)
        idxs = sorted({s["index"] for fr in frames for s in fr if s["lib"] == a.target})
        f0 = frames[0]
        sizes = []
        if a.sizes:
            for s in f0:
                sz = size_of(s["lib"], s["index"], s["frame"])
                sizes.append(sz)
        rows.append({
            "entry": i, "frames": len(frames), "nsub": dict(nsub),
            "spans": sorted(libs), "idx_min": idxs[0] if idxs else -1,
            "idx_max": idxs[-1] if idxs else -1, "n_idx": len(idxs),
            "layers0": [(s["index"], s["frame"], s["off"]) for s in f0],
            "sizes": sizes,
        })

    print(f"{len(rows)} Spr entries reference {a.target}\n")
    print(f"{'Spr':>5} {'frames':>7} {'nSub':>14} {'bundle range':>18} {'n':>4}  layer0 (index,frame,off)")
    for r in rows:
        ns = ",".join(f"{k}x{v}" for k, v in sorted(r["nsub"].items()))
        rng = f"{r['idx_min']}..{r['idx_max']}" if r["idx_min"] >= 0 else "-"
        lay = " ".join(f"({i},f{f},{o})" for i, f, o in r["layers0"][:4])
        print(f"{r['entry']:>5} {r['frames']:>7} {ns:>14} {rng:>18} {r['n_idx']:>4}  {lay}")
        if a.sizes and r["sizes"]:
            print(f"        sizes: {r['sizes']}")

    for lib in pools.values():
        if lib:
            lib.close()
    spr.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
