"""Dump ASCII + GBK strings from the game exe and grep them.

Used to find data-file names the engine opens (combine/slr/mdl/.fol/.lib).
"""
from __future__ import annotations

import re
import sys

EXE = r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\rework\ComeOn.exe"
BASE = 0x400000


def strings(data: bytes, minlen: int = 4):
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
        yield m.start() + BASE, m.group().decode("latin1")


def gbk_strings(data: bytes, minlen: int = 3):
    """Runs of bytes that decode cleanly as GBK and are mostly non-ASCII."""
    pat = re.compile(rb"(?:[\xb0-\xf7][\xa1-\xfe]|[\x20-\x7e]){%d,}" % minlen)
    for m in pat.finditer(data):
        raw = m.group()
        if len(raw) < minlen * 2:
            continue
        try:
            s = raw.decode("gbk")
        except UnicodeDecodeError:
            continue
        if sum(1 for c in s if ord(c) > 0x7F) >= 2:
            yield m.start() + BASE, s


def main(argv):
    data = open(EXE, "rb").read()
    pats = argv[1:] or ["combine", "slr", "mdl", "fol", "lib", "txt"]
    seen = set()
    for va, s in list(strings(data)) + list(gbk_strings(data)):
        low = s.lower()
        if any(p.lower() in low for p in pats):
            key = (va, s)
            if key in seen:
                continue
            seen.add(key)
            try:
                print(f"0x{va:08X}  {s}")
            except UnicodeEncodeError:
                print(f"0x{va:08X}  <gbk>")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
