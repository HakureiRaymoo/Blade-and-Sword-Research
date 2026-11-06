"""Probe the three `.fol` containers (cj / mb / slr).

Nothing in `ComeOn.exe` or `ComeOn.dll` mentions the string "fol", so the
container is at minimum not opened by a plain name.  This tool looks at the
bytes from several angles: entropy, common n-grams (the raw dumps show runs like
``xx B6 7B`` where the low byte ascends), and whether a standard decompressor
can make sense of it.

    py tools/rekit/fol_probe.py
    py tools/rekit/fol_probe.py --file slr.fol --grams 3
"""
from __future__ import annotations

import argparse
import bz2
import collections
import lzma
import math
import os
import sys
import zlib

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"
FILES = ("slr.fol", "mb.fol", "cj.fol")


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = collections.Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def try_decompress(data: bytes) -> list[str]:
    out = []
    for name, fn in (("zlib", zlib.decompress),
                     ("gzip", lambda d: zlib.decompress(d, 16 + zlib.MAX_WBITS)),
                     ("bz2", bz2.decompress),
                     ("lzma", lzma.decompress)):
        try:
            got = fn(data)
            out.append(f"{name}: OK -> {len(got)} bytes")
        except Exception as exc:  # noqa: BLE001
            out.append(f"{name}: {type(exc).__name__}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--file", default="")
    ap.add_argument("--grams", type=int, default=2)
    a = ap.parse_args(argv)

    names = [a.file] if a.file else list(FILES)
    for name in names:
        path = os.path.join(a.game, name)
        if not os.path.exists(path):
            print(f"!! missing {path}")
            continue
        data = open(path, "rb").read()
        print(f"=== {name}  {len(data):,} bytes")
        print(f"  head: {data[:32].hex(' ')}")
        print(f"  tail: {data[-16:].hex(' ')}")
        print(f"  entropy (whole): {entropy(data):.3f} bits/byte")
        body = data[8:]
        print(f"  entropy (after 8B header): {entropy(body):.3f}")
        for chunk in (64, 4096):
            print(f"  entropy (first {chunk}B of body): {entropy(body[:chunk]):.3f}")
        hist = collections.Counter(data)
        print("  most common bytes:", [(f"{b:02X}", c) for b, c in hist.most_common(8)])
        print("  " + "\n  ".join(try_decompress(body)))
        if a.grams:
            g = collections.Counter(
                data[i:i + a.grams] for i in range(0, min(len(data), 65536) - a.grams)
            )
            print(f"  top {a.grams}-grams in first 64 KiB:",
                  [(x.hex(), c) for x, c in g.most_common(6)])
        # how often does the last byte of a dword look like a fixed high byte?
        print("  dword-stride byte classes (first 24 dwords):")
        for i in range(0, min(24, len(data) // 4)):
            d = data[i * 4:i * 4 + 4]
            print(f"    {i:>2} {d.hex(' ')}  u32le={int.from_bytes(d,'little'):>12}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
