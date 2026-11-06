"""Inspect a `lep` image's header, row table and first rows -- format debugging.

    py tools/rekit/lep_probe.py --lib Res00 --entry 5943
    py tools/rekit/lep_probe.py --lib Res00 --entry 4153 --rows 3
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve  # noqa: E402
from lep import LepImage  # noqa: E402
from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


def main(argv=None) -> int:
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--lib", required=True)
    ap.add_argument("--entry", type=int, required=True)
    ap.add_argument("--rows", type=int, default=3)
    a = ap.parse_args(argv)

    with LeyiLib(resolve(Path(a.game), a.lib)) as lib:
        data = lib.read(a.entry)

    img = LepImage.parse(data)
    print(f"{a.lib}#{a.entry}: size={len(data)} rows={img.row_count} "
          f"header={[hex(x) for x in img.fields[:10]]}")
    print(f"  offsets[:12] = {img.offsets[:12]}")
    print(f"  offsets[-4:] = {img.offsets[-4:]}  (payload < size-0x30: {img.offsets[-1] < len(data) - 0x30})")
    totals = img.width_check()
    print(f"  row totals: min={min(totals)} max={max(totals)} distinct={sorted(set(totals))[:8]}")
    for i in range(min(a.rows, img.row_count)):
        r = img.row(i)
        print(f"  row{i}: len={len(r)}")
        print(f"    hex  : {r[:56].hex(' ')}")
        print(f"    runs : {[(xb, len(p)) for xb, p in img.runs(i)][:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
