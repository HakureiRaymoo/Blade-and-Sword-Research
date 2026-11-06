"""AOB-scan the running game for a known `Spr` entry body.

`Spr` library entries are not images; they look like sprite/animation descriptor
tables (the engine's `slr` module consumes them, hence the "Slr Init End" log).
If the engine keeps the file bytes verbatim in memory, an exact byte scan finds
the loaded copy, and reading around it tells us whether any field was rewritten
into a pointer (i.e. what the real record layout is).

    py tools/rekit/ce_spr_scan.py --entry 901
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from attach import find_game_window  # noqa: E402
from ce_client import CEClient  # noqa: E402
from export_assets import resolve  # noqa: E402
from leylib import LeyiLib  # noqa: E402

GAME = r"D:\STEAM\steamapps\common\刀剑封魔录外传：上古传说"


def hexpat(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="Spr")
    ap.add_argument("--entry", type=int, default=901)
    ap.add_argument("--bytes", type=int, default=24, help="pattern length taken from entry start")
    ap.add_argument("--window", type=int, default=160, help="bytes to read around each hit")
    a = ap.parse_args(argv)

    from pathlib import Path

    with LeyiLib(resolve(Path(GAME), a.lib)) as lib:
        data = lib.read(a.entry)
    pat = hexpat(data[: a.bytes])
    print(f"entry {a.entry}: {len(data)} bytes, pattern {pat}")

    found = find_game_window()
    if not found:
        print("no game window", file=sys.stderr)
        return 1
    pid, title = found
    print(f"window {title!r} pid={pid}")

    c = CEClient()
    try:
        print("openProcess:", c.lua(f"return tostring(openProcess({pid}))"))
        res = c.lua(f'''
local sl = AOBScan("{pat}")
if sl == nil then return "none" end
local out = {{}}
for i = 0, math.min(sl.Count - 1, 15) do
  local addr = tonumber("0x" .. sl[i])
  out[#out+1] = string.format("%X", addr)
end
local n = sl.Count
sl.destroy()
return n .. "|" .. table.concat(out, ",")
''')
        print("scan:", res)
        if "none" in res:
            return 0
        count, addrs = res.split("|")
        print("hits:", count)
        for a in addrs.split(","):
            if not a:
                continue
            addr = int(a, 16)
            dump = c.lua(f'''
local addr = {addr}
local t = {{}}
for i = 0, {a.window // 4 - 1} do
  local v = readInteger(addr + i * 4)
  if v then t[#t+1] = string.format("%d", v) else t[#t+1] = "?" end
end
return table.concat(t, " ")
''')
            print(f"  @{addr:08X}: {dump}")
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
