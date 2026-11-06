"""Generic Cheat Engine helpers driven from the agent side.

All calls go through the user's CE instance (see `ce_client`) so no `OpenProcess`
from this sandbox is needed. A memory scan is a pure read, so the game keeps its
focus and never needs to be paused.

    py tools/rekit/ce_mem.py scan "37 17 10 00 38 17 10 00 39 17 10 00"
    py tools/rekit/ce_mem.py read 0x12345678 64
    py tools/rekit/ce_mem.py module ComeOn.exe
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from attach import find_game_window  # noqa: E402
from ce_client import CEClient  # noqa: E402


def ensure_open(c: CEClient) -> int:
    pid = c.lua("return tostring(getOpenedProcessID())")
    try:
        cur = int(pid)
    except ValueError:
        cur = 0
    if cur:
        return cur
    found = find_game_window()
    if not found:
        raise SystemExit("no game window and CE has no process open")
    pid = found[0]
    c.lua(f"return tostring(openProcess({pid}))")
    return pid


def cmd_scan(c: CEClient, pattern: str, limit: int, context: int) -> int:
    res = c.lua(f'''
local sl = AOBScan("{pattern}")
if sl == nil then return "none" end
local n = sl.Count
local out = {{}}
for i = 0, math.min(n - 1, {limit - 1}) do out[#out+1] = sl[i] end
sl.destroy()
return n .. "|" .. table.concat(out, ",")
''')
    if "none" in res:
        print("no hits")
        return 0
    count, addrs = res.split("|", 1)
    print(f"hits: {count}")
    for a in [x for x in addrs.split(",") if x]:
        addr = int(a, 16)
        if context <= 0:
            print(f"  {addr:08X}")
            continue
        dump = c.lua(f'''
local t = {{}}
for i = 0, {context // 4 - 1} do
  local v = readInteger({addr} + i * 4)
  t[#t+1] = v and string.format("%d", v) or "?"
end
return table.concat(t, " ")
''')
        print(f"  {addr:08X}: {dump}")
    return 0


def cmd_read(c: CEClient, addr: int, n: int) -> int:
    dump = c.lua(f'''
local t = {{}}
for i = 0, {n // 4 - 1} do
  local v = readInteger({addr} + i * 4)
  t[#t+1] = v and string.format("%d", v) or "?"
end
return table.concat(t, " ")
''')
    print(f"{addr:08X}: {dump}")
    return 0


def cmd_module(c: CEClient, name: str) -> int:
    print(c.lua(f"local b = getAddress('{name}'); return b and string.format('%X', b) or 'not loaded'"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("pattern")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--context", type=int, default=64)
    p = sub.add_parser("read")
    p.add_argument("addr")
    p.add_argument("n", type=int, default=64)
    p = sub.add_parser("module")
    p.add_argument("name")
    a = ap.parse_args(argv)

    c = CEClient()
    try:
        pid = ensure_open(c)
        print(f"process: {pid}")
        if a.cmd == "scan":
            return cmd_scan(c, a.pattern, a.limit, a.context)
        if a.cmd == "read":
            return cmd_read(c, int(a.addr, 16), a.n)
        if a.cmd == "module":
            return cmd_module(c, a.name)
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
