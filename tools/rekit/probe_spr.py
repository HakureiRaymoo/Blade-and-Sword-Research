"""Guess the record layout of the `Spr` library entries.

`Spr` entries are not images: they look like sprite/animation descriptor blocks
(the engine's `slr` module reads them, per the "Slr Init End" log line). This
script probes candidate strides so the real record size can be recovered from
the total payload length.
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve  # noqa: E402
from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


def main() -> int:
    from pathlib import Path

    with LeyiLib(resolve(Path(GAME), "Spr")) as lib:
        for idx in (0, 1, 5, 101, 201, 655, 800, 901, 902, 904, 1789):
            d = lib.read(idx)
            v = struct.unpack_from("<%dI" % (len(d) // 4), d)
            print(f"=== entry {idx} size={len(d)} dwords={len(d)//4}")
            print("   head:", " ".join(f"{x:#x}" for x in v[:8]))
            fits = []
            for p in range(4, 129, 4):
                for hdr in (4, 8, 12, 16):
                    if (len(d) - hdr) % p == 0 and (len(d) - hdr) // p == v[0]:
                        fits.append((hdr, p, v[0]))
                    if (len(d) - hdr) % p == 0 and (len(d) - hdr) // p == v[1]:
                        fits.append((hdr, p, v[1]))
            print("   stride fits (hdr,stride,count):", fits[:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
