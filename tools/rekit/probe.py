"""Quick header probe for unknown game containers.

Usage:
    py tools/rekit/probe.py <path> [more paths...] [-n 256]

Prints size, first N bytes as hex + ascii, and a few derived stats.
Deliberately dependency-free so it runs before any toolchain decisions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def hexdump(data: bytes, base: int = 0, width: int = 16) -> str:
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        hexpart = f"{hexpart:<{width * 3 - 1}}"
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{base + off:08x}  {hexpart}  |{text}|")
    return "\n".join(lines)


def probe(path: Path, n: int) -> None:
    size = path.stat().st_size
    with path.open("rb") as fh:
        head = fh.read(n)

    print(f"\n=== {path.name}  ({size:,} bytes) ===")
    print(f"magic4 : {head[:4].hex(' ')}  ascii={head[:4]!r}")
    if len(head) >= 8:
        print(f"u32[0..3]: {[int.from_bytes(head[i*4:i*4+4], 'little') for i in range(4)]}")
        print(f"u32be[0..3]: {[int.from_bytes(head[i*4:i*4+4], 'big') for i in range(4)]}")
    print(hexdump(head, 0, 16))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-n", type=int, default=256)
    args = ap.parse_args(argv)
    for p in args.paths:
        path = Path(p)
        if not path.exists():
            print(f"!! missing: {p}", file=sys.stderr)
            continue
        probe(path, args.n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
