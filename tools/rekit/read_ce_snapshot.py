"""Summarise a Cheat Engine snapshot produced by tools/ce/capture_runtime.lua.

    py tools/rekit/read_ce_snapshot.py out/ce/snapshot_*.txt
    py tools/rekit/read_ce_snapshot.py <file> --lib Spr --entry 901

Without --lib/--entry it prints a structural summary (counts, size histogram,
object types). With them it compares each dumped `data[]` preview against the
dwords of a library entry, so a runtime object can be matched back to the file
record it was parsed from.
"""
from __future__ import annotations

import argparse
import glob
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_assets import resolve  # noqa: E402
from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


def parse(path: str) -> dict:
    head: dict = {}
    imgs: list[dict] = []
    objs: list[dict] = []
    cur = None
    for raw in open(path, "r", encoding="utf-8", errors="replace"):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("  img "):
            parts = line.split()
            rec = {"addr": parts[1]}
            for kv in parts[2:]:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    rec[k] = v
            imgs.append(rec)
            cur = None
        elif line.startswith("  obj "):
            parts = line.split()
            rec = {"addr": parts[1], "data": [], "sub": []}
            for kv in parts[2:]:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    rec[k] = v
            objs.append(rec)
            cur = rec
        elif line.startswith("      data[]:"):
            if cur is not None:
                cur["data"] = [int(x) for x in line.split(":", 1)[1].split() if x.lstrip("-").isdigit()]
        elif line.startswith("      sub[]"):
            if cur is not None:
                cur["sub"] = line.split(":", 1)[1].split()
        elif ":" in line and not line.startswith("----"):
            k, v = line.split(":", 1)
            head[k.strip()] = v.strip()
    return {"head": head, "imgs": imgs, "objs": objs}


def entry_dwords(libname: str, entry: int, n: int) -> list[int]:
    from pathlib import Path

    with LeyiLib(resolve(Path(GAME), libname)) as lib:
        data = lib.read(entry)
    n = min(n, len(data) // 4)
    return list(struct.unpack_from(f"<{n}I", data, 0))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--lib")
    ap.add_argument("--entry", type=int)
    a = ap.parse_args(argv)

    files: list[str] = []
    for f in a.files:
        files.extend(sorted(glob.glob(f)) or [f])

    target = None
    if a.lib and a.entry is not None:
        target = entry_dwords(a.lib, a.entry, 24)
        print(f"target {a.lib}#{a.entry}: " + " ".join(str(x) for x in target))
        print()

    for path in files:
        if not os.path.exists(path):
            print(f"!! missing {path}")
            continue
        snap = parse(path)
        print(f"=== {os.path.basename(path)}")
        for k in ("time", "capture #", "pid", "ComeOn.exe", "ddraw.dll", "DDRAW.dll"):
            if k in snap["head"]:
                print(f"    {k:<10} {snap['head'][k]}")
        imgs, objs = snap["imgs"], snap["objs"]
        print(f"    images: {len(imgs)}   objects: {len(objs)}")
        if imgs:
            wh = Counter((i.get("d1C"), i.get("d20")) for i in imgs)
            print("    image sizes (d1C,d20) top:", wh.most_common(8))
            bpp = Counter(i.get("bpp") for i in imgs)
            print("    bpp:", bpp.most_common())
        if objs:
            types = Counter(o.get("type") for o in objs)
            print("    object type histogram:", types.most_common())
            nonzero = [o for o in objs if o.get("data")]
            print(f"    with data preview: {len(nonzero)}")
            if target:
                hits = [o for o in nonzero if o["data"][: len(target)] == target]
                print(f"    !! exact data-preview match to target: {len(hits)}")
                for h in hits[:8]:
                    print("       ", h["addr"], "sub=" + str(h.get("sub")))
                # looser: same first dword and same length
                loose = [o for o in nonzero
                         if o["data"] and target and o["data"][0] == target[0]]
                print(f"    ~ first-dword match: {len(loose)}")
                for h in loose[:8]:
                    print("       ", h["addr"], h["data"][:6])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
