"""Find and decode "composite frame" entries (the nSub format with anchors).

Two payload kinds live in the libraries side by side:

  * ``lep`` bundles -- ``u32 count | u32 off[count] | lep frames`` (no placement
    data; this is what `split_bundle` handles)
  * composite frames -- ``u16 count`` then per frame
    ``{u32 nSub, u32 ?, u32 strideInts}`` followed by ``nSub`` records of
    ``strideInts`` dwords: ``flag, ?, ref, A, B, C, D``

The second kind is the one that carries placement: `FUN_0050b3f0` draws at
``pos + (A - C, B - D)``, and `FUN_0050cd30` decodes ``ref`` through
``FUN_00505750`` into (library, local index).

    py tools/rekit/scan_composite.py --lib Res00 --limit 14341
    py tools/rekit/scan_composite.py --lib ResPlayer1 --show 3
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve  # noqa: E402
from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"

LIBS = ("Spr Res00 ResPrior ResPlayer1 ResBoss ResNpc2 ResJM ResPlayer2 "
        "ResPlayer3 ResNpc3 ResExNpc1 ResExPlayer1 ResExPlayer2 ResEx01").split()


def looks_composite(data: bytes) -> tuple[int, int, int] | None:
    """Return (count, nSub of frame 0, stride) when the entry looks composite."""
    if len(data) < 16 or data[:4] == b"lep\0":
        return None
    (count,) = struct.unpack_from("<H", data, 0)
    if not 1 <= count <= 4000:
        return None
    nsub, _f1, stride = struct.unpack_from("<III", data, 4)
    if not 1 <= nsub <= 64 or stride not in (7, 8):
        return None
    need = 4 + 12 + nsub * stride * 4
    if need > len(data):
        return None
    return count, nsub, stride


def decode(data: bytes, libs=LIBS) -> list[dict]:
    (count,) = struct.unpack_from("<H", data, 0)
    p = 4
    frames = []
    for _ in range(count):
        if p + 12 > len(data):
            break
        nsub, _f1, stride = struct.unpack_from("<III", data, p)
        p += 12
        if not 1 <= nsub <= 64 or stride not in (7, 8):
            break
        subs = []
        for _j in range(nsub):
            if p + stride * 4 > len(data):
                break
            vals = struct.unpack_from(f"<{stride}I", data, p)
            p += stride * 4
            flag, _x, ref, A, B, C, D = vals[:7]
            lib = (ref >> 20) & 0xF
            idx = ref & 0xFF0FFFFF
            subs.append({
                "flag": flag, "ref": ref,
                "lib": libs[lib] if lib < len(libs) else f"lib{lib}",
                "index": idx, "frame": (ref >> 24) & 0xFF,
                "A": A & 0xFFFF, "B": B & 0xFFFF,
                "C": C & 0xFFFF, "D": D & 0xFFFF,
                "off": ((A & 0xFFFF) - (C & 0xFFFF), (B & 0xFFFF) - (D & 0xFFFF)),
            })
        frames.append(subs)
    return frames


def main(argv=None) -> int:
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--lib", default="Res00")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--show", type=int, default=0, help="decode and print the first N hits")
    a = ap.parse_args(argv)

    with LeyiLib(resolve(Path(a.game), a.lib)) as lib:
        stop = min(a.limit or lib.count, lib.count)
        hits = []
        for i in range(stop):
            try:
                head = lib.read(i)
            except Exception:  # noqa: BLE001
                continue
            info = looks_composite(head)
            if info:
                hits.append((i, info, len(head)))
        print(f"{a.lib}: scanned {stop} entries, composite-looking: {len(hits)}")
        for i, info, size in hits[:30]:
            print(f"  #{i:<6} size={size:<8} count={info[0]:<5} frame0 nSub={info[1]} stride={info[2]}")
        for i, info, size in hits[: a.show]:
            data = lib.read(i)
            frames = decode(data)
            print(f"\n--- {a.lib}#{i}: {len(frames)} frames ---")
            for fi, subs in enumerate(frames[:16]):
                desc = "  ".join(
                    f"{s['lib']}#{s['index']}@{s['off']}" for s in subs)
                print(f"  f{fi:<3} n={len(subs):<2} {desc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
