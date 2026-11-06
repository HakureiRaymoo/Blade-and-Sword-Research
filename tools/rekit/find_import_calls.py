"""Find call sites of imported Win32 functions by IAT slot.

Parses the PE import directory, records the IAT entry address for each named
import, then searches the file for `FF 15 <slot>` (call dword ptr [slot]) and
reports the calling VA. Used to locate the window setup / message pump code
without relying on Ghidra's external symbol naming.
"""
from __future__ import annotations

import struct
import sys

PATH = r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\rework\ComeOn.exe"
WANTED = {
    "RegisterClassA", "CreateWindowExA", "DispatchMessageA", "GetMessageA",
    "PeekMessageA", "ShowWindow", "SetWindowPos", "TranslateMessage",
    "DefWindowProcA", "SetCooperativeLevel", "GetForegroundWindow",
    "GetActiveWindow", "IsIconic", "SetWindowLongA",
}


def main() -> int:
    d = open(PATH, "rb").read()
    base_va = 0x400000
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    optsz = struct.unpack_from("<H", d, pe + 20)[0]
    opt = pe + 24
    imp_rva, _ = struct.unpack_from("<II", d, opt + 104)

    secs = []
    so = opt + optsz
    for i in range(nsec):
        name = d[so + i * 40: so + i * 40 + 8].rstrip(b"\0").decode("latin1")
        vs, va, rs, ro = struct.unpack_from("<IIII", d, so + i * 40 + 8)
        secs.append((va, vs, ro, rs, name))

    def r2o(rva: int) -> int | None:
        for va, vs, ro, rs, _n in secs:
            if va <= rva < va + max(vs, rs):
                return ro + (rva - va)
        return None

    slots: dict[str, int] = {}
    o = r2o(imp_rva)
    while True:
        ilt, _ts, _fc, name_rva, iat = struct.unpack_from("<IIIII", d, o)
        if name_rva == 0:
            break
        dll = d[r2o(name_rva):].split(b"\0", 1)[0].decode("latin1")
        thunk = r2o(ilt or iat)
        idx = 0
        while True:
            entry = struct.unpack_from("<I", d, thunk + idx * 4)[0]
            if entry == 0:
                break
            if not (entry & 0x80000000):
                nm = d[r2o(entry) + 2:].split(b"\0", 1)[0].decode("latin1")
                if nm in WANTED:
                    slots[nm] = iat + idx * 4
            idx += 1
        o += 20

    print("IAT slots:")
    for k in sorted(slots):
        print(f"  {k:<20} 0x{slots[k] + base_va:08X}")

    print("\ncall sites (call dword ptr [slot]):")
    for nm, slot in sorted(slots.items()):
        pat = b"\xFF\x15" + struct.pack("<I", slot + base_va)
        hits = []
        start = 0
        while True:
            i = d.find(pat, start)
            if i < 0:
                break
            hits.append(i + base_va)
            start = i + 1
        print(f"  {nm:<20} {len(hits):>2}  " + ", ".join(f"0x{h:08X}" for h in hits[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

