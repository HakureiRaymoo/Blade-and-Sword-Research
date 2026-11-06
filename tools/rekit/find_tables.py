"""Find and extract `.txt` data tables from the game's combined libraries.

The engine keeps its GBK TSV tables inside the .lib containers (see idx.lib for
the combined order). This lists every entry whose name looks like a table and
can extract one by name.

    py tools/rekit/find_tables.py --list
    py tools/rekit/find_tables.py --extract Role.txt --out out/tables
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"
ZY = os.path.join(GAME, "zy")

ORDER = ("Spr Res00 ResPrior ResPlayer1 ResBoss ResNpc2 ResJM ResPlayer2 "
         "ResPlayer3 ResNpc3 ResExNpc1 ResExPlayer1 ResExPlayer2 ResEx01").split()


def lib_path(name: str) -> str | None:
    for cand in (name + ".lib", name + ".Lib", name + ".Lib.chs"):
        p = os.path.join(ZY, cand)
        if os.path.exists(p):
            return p
    return None


def load_all():
    out = []
    gbase = 0
    for n in ORDER:
        p = lib_path(n)
        if not p:
            print(f"!! missing {n}", file=sys.stderr)
            continue
        lib = LeyiLib(p)
        out.append((n, gbase, lib))
        gbase += lib.count
    return out


def entry_name(lib: LeyiLib, i: int) -> str:
    try:
        return lib.entry(i)[0]
    except Exception:
        return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--extract")
    ap.add_argument("--out", default=r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\out\tables")
    a = ap.parse_args(argv)

    libs = load_all()
    if a.list:
        for n, gbase, lib in libs:
            names = [entry_name(lib, i) for i in range(lib.count)]
            txt = [(i, s) for i, s in enumerate(names) if s.lower().endswith((".txt", ".ini"))]
            print(f"{n:<14} count={lib.count:<6} base={gbase:<6} tables={len(txt)}")
            for i, s in txt:
                print(f"    local={i:<6} global={gbase + i:<6} {s}")
        return 0

    if a.extract:
        want = a.extract.lower()
        os.makedirs(a.out, exist_ok=True)
        for n, gbase, lib in libs:
            for i in range(lib.count):
                if entry_name(lib, i).lower() == want:
                    data = lib.read(i)
                    p = os.path.join(a.out, f"{a.extract}")
                    open(p, "wb").write(data)
                    print(f"{a.extract} <- {n} local={i} global={gbase + i} bytes={len(data)}")
                    return 0
        print(f"{a.extract}: not found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
