"""Read/dump the game's memory through the Cheat Engine bridge.

The agent sandbox is Low integrity and cannot OpenProcess, but CE (launched by
the user at medium integrity) can, and the bridge relays calls to it. All of
these operations are pure reads, so the game keeps focus and is never paused.

    py tools/rekit/ce_read.py --pid 20716 read-hex 0x04144D70 128
    py tools/rekit/ce_read.py scan-dump 0x04144D70 --around 16
    py tools/rekit/ce_read.py scan "6C 65 70 00" --limit 5 --around 8
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ce_client import CEClient  # noqa: E402


def open_pid(c: CEClient, pid: int | None) -> int:
    if pid:
        c.lua(f"return tostring(openProcess({pid}))")
    cur = c.lua("return tostring(getOpenedProcessID())")
    try:
        return int(cur)
    except ValueError:
        return 0


def read_bytes(c: CEClient, addr: int, n: int) -> bytes:
    out = bytearray()
    step = 64
    a = addr
    while len(out) < n:
        k = min(step, n - len(out))
        res = c.lua(f'''
local s = {{}}
for i = 0, {k} - 1 do
  local b = readBytes({a} + i, 1)
  if b == nil then return "" end
  s[#s+1] = string.format("%02X", b)
end
return table.concat(s, "")
''')
        if not res:
            break
        out += bytes.fromhex(res)
        a += k
    return bytes(out)


def read_dwords(c: CEClient, addr: int, n: int) -> list[int | None]:
    res = c.lua(f'''
local t = {{}}
for i = 0, {n} - 1 do
  local v = readInteger({addr} + i*4)
  if v then t[#t+1] = string.format("%d", v) else t[#t+1] = "x" end
end
return table.concat(t, ",")
''')
    vals: list[int | None] = []
    for x in res.split(","):
        vals.append(None if x in ("x", "") else int(x))
    return vals


def fmt_dwords(base: int, vals: list[int | None], per: int = 8) -> str:
    lines = []
    for i in range(0, len(vals), per):
        cells = " ".join("????????" if v is None else f"{v & 0xFFFFFFFF:08X}" for v in vals[i:i + per])
        lines.append(f"  {base + i * 4:08X}  {cells}")
    return "\n".join(lines)


def cmd_read_hex(c: CEClient, addr: int, n: int) -> int:
    data = read_bytes(c, addr, n)
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexs = " ".join(f"{b:02X}" for b in chunk)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {addr + off:08X}  {hexs:<48}  {text}")
    return 0


def cmd_scan(c: CEClient, pattern: str, limit: int, around: int) -> int:
    res = c.lua(f'''
local sl = AOBScan("{pattern}", "+W")
if sl == nil then return "none" end
local n = sl.Count
local out = {{}}
for i = 0, math.min(n - 1, {limit - 1}) do out[#out+1] = sl[i] end
sl.destroy()
return n .. "|" .. table.concat(out, ",")
''')
    if res.startswith("none"):
        print("no hits")
        return 0
    count, addrs = res.split("|", 1)
    hits = [int(x, 16) for x in addrs.split(",") if x]
    print(f"hits: {count}")
    for h in hits:
        print(f"--- hit 0x{h:08X} ---")
        if around:
            vals = read_dwords(c, h - around * 4, around * 2)
            print(fmt_dwords(h - around * 4, vals))
    return 0


def cmd_scan_dump(c: CEClient, value: int, limit: int, around: int) -> int:
    """Scan for pointers equal to `value` and dump the surrounding dwords."""
    pat = " ".join(f"{(value >> (8 * i)) & 0xFF:02X}" for i in range(4))
    return cmd_scan(c, pat, limit, around)


def cmd_find(c: CEClient, value: int, limit: int) -> int:
    pat = " ".join(f"{(value >> (8 * i)) & 0xFF:02X}" for i in range(4))
    res = c.lua(f'''
local sl = AOBScan("{pat}", "+W")
if sl == nil then return "none" end
local n = sl.Count
local out = {{}}
for i = 0, math.min(n - 1, {limit - 1}) do out[#out+1] = sl[i] end
sl.destroy()
return n .. "|" .. table.concat(out, ",")
''')
    print(f"{res}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("read-hex")
    p.add_argument("addr")
    p.add_argument("n", type=int, default=128)

    p = sub.add_parser("read-dwords")
    p.add_argument("addr")
    p.add_argument("n", type=int, default=32)

    p = sub.add_parser("scan")
    p.add_argument("pattern")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--around", type=int, default=8)

    p = sub.add_parser("scan-dump")
    p.add_argument("value")
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--around", type=int, default=12)

    p = sub.add_parser("find")
    p.add_argument("value")
    p.add_argument("--limit", type=int, default=20)

    a = ap.parse_args(argv)
    c = CEClient()
    try:
        pid = open_pid(c, a.pid)
        print(f"process: {pid}")
        if a.cmd == "read-hex":
            return cmd_read_hex(c, int(a.addr, 16), a.n)
        if a.cmd == "read-dwords":
            vals = read_dwords(c, int(a.addr, 16), a.n)
            print(fmt_dwords(int(a.addr, 16), vals))
            return 0
        if a.cmd == "scan":
            return cmd_scan(c, a.pattern, a.limit, a.around)
        if a.cmd == "scan-dump":
            return cmd_scan_dump(c, int(a.value, 16), a.limit, a.around)
        if a.cmd == "find":
            return cmd_find(c, int(a.value, 16), a.limit)
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
