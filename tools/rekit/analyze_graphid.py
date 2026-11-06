"""Analyse the 图形ID column of Role.txt against the combined lib index space.

`zy/idx.lib` lists 14 libraries; the engine concatenates their entry tables into
one global index space (BugLog: "Init CombineLibEnd"). If 图形ID values are
indices into that space, every role's 图形ID must fall inside a lib that holds
sprite bundles.
"""
from __future__ import annotations

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


def build_space():
    spans = []
    gbase = 0
    for n in ORDER:
        p = lib_path(n)
        if not p:
            continue
        with LeyiLib(p) as lib:
            c = lib.count
        spans.append((gbase, gbase + c - 1, n))
        gbase += c
    return spans


def locate(spans, idx):
    for lo, hi, n in spans:
        if lo <= idx <= hi:
            return n, idx - lo
    return None, None


def main() -> int:
    spans = build_space()
    for lo, hi, n in spans:
        print(f"{n:<14} {lo:>6} .. {hi:>6}  ({hi - lo + 1})")
    print()

    path = os.path.join(GAME, "bdh", "chs", "Role.txt")
    raw = open(path, "rb").read().decode("gbk", "replace")
    lines = [ln for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
    header = lines[0].split("\t")
    print("columns:", len(header))
    for i, h in enumerate(header):
        print(f"  [{i}] {h}")
    print()

    gi = header.index("图形ID") if "图形ID" in header else 4
    ni = 0
    print(f"{'name':<12}{'图形ID':>7}  {'lib':<12}{'local':>7}")
    rows = []
    for ln in lines[1:]:
        f = ln.split("\t")
        if len(f) <= gi:
            continue
        try:
            v = int(f[gi])
        except ValueError:
            continue
        lib, local = locate(spans, v)
        rows.append((f[ni], v, lib, local))
    for name, v, lib, local in rows[:60]:
        print(f"{name:<12}{v:>7}  {str(lib):<12}{str(local):>7}")
    print(f"... {len(rows)} rows total")
    vals = [r[1] for r in rows]
    print("图形ID min/max:", min(vals), max(vals))
    from collections import Counter
    print("by lib:", Counter(r[2] for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
