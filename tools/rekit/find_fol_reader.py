"""Find short engine strings (`cj`, `slr`, `mb`, `fol`) and who references them.

The `.fol` extension is only 3 characters, so the usual "4+ printable run" string
dump misses it.  These four names sit next to each other in `.rdata`, which means
the engine builds a path such as ``%s\\%s.fol`` from them.

    py tools/rekit/find_fol_reader.py
"""
from __future__ import annotations

import struct
import sys

EXE = r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\rework\ComeOn.exe"
BASE = 0x400000


def sections(data: bytes):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    so = pe + 24 + optsz
    out = []
    for i in range(nsec):
        name = data[so + i * 40: so + i * 40 + 8].rstrip(b"\0").decode("latin1")
        vs, va, rs, ro = struct.unpack_from("<IIII", data, so + i * 40 + 8)
        out.append((name, va, vs, ro, rs))
    return out


def main(argv=None) -> int:
    data = open(EXE, "rb").read()
    secs = sections(data)
    print("sections:", [(n, hex(va), hex(rs)) for n, va, vs, ro, rs in secs])

    def r2o(rva: int) -> int | None:
        for _n, va, vs, ro, rs in secs:
            if va <= rva < va + max(vs, rs):
                return ro + (rva - va)
        return None

    def o2r(off: int) -> int | None:
        for _n, va, vs, ro, rs in secs:
            if ro <= off < ro + rs:
                return va + (off - ro)
        return None

    want = [b"cj\0", b"slr\0", b"mb\0", b"fol\0", b"Slr\\\0", b"cj\\\0", b"Zy\\\0"]
    found = []
    for w in want:
        start = 0
        while True:
            i = data.find(w, start)
            if i < 0:
                break
            rva = o2r(i)
            if rva is not None:
                found.append((w, i, rva))
            start = i + 1
    for w, off, rva in found:
        print(f"  {w!r:<10} file=0x{off:06X}  VA=0x{rva + BASE:08X}")

    print("\nreferences (dword push of the VA, or a 4-byte pointer table entry):")
    for w, off, rva in found:
        va = rva + BASE
        pat = struct.pack("<I", va)
        hits = []
        s = 0
        while True:
            j = data.find(pat, s)
            if j < 0:
                break
            hits.append(o2r(j))
            s = j + 1
        if hits:
            print(f"  {w!r:<10} VA=0x{va:08X}  {len(hits)} refs: "
                  + ", ".join(f"0x{(h + BASE) if h else 0:08X}" for h in hits[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
