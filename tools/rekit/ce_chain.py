"""Walk the engine's part-table chain for the live player character.

Every parsed `Spr` entry is an object whose

    +0x08  -> next object in the draw/layer chain
    +0x0C  -> previous object

so the chain *is* the character's layer order.  Reading it from the running game
gives the part list and its stacking order directly, which is exactly the last
missing piece for reconstructing a character.

    py tools/rekit/ce_chain.py --pid 20716 --start 177
    py tools/rekit/ce_chain.py --dump-frame 0
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ce_client import CEClient  # noqa: E402

SPR_DESC = 0x0EB200C4


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--start", type=int, default=None, help="Spr index to start walking from")
    ap.add_argument("--limit", type=int, default=64)
    ap.add_argument("--dump-frame", type=int, default=None,
                    help="also print +0x30..+0x4C of each member (candidate frame state)")
    a = ap.parse_args(argv)

    c = CEClient()
    try:
        if a.pid:
            c.lua(f"return tostring(openProcess({a.pid}))")
        print("process:", c.lua("return tostring(getOpenedProcessID())"))

        # index <-> object map for the whole Spr library
        res = c.lua(f'''
local desc = {SPR_DESC}
local cache = readInteger(desc + 4)
local cnt = readInteger(desc + 0x48)
local out = {{}}
for i = 0, cnt - 1 do
  local v = readInteger(cache + i*4)
  if v and v ~= 0 then out[#out+1] = i .. "=" .. string.format("%X", v) end
end
return table.concat(out, ",")
''')
        objs: dict[int, int] = {}
        for tok in res.split(","):
            if "=" in tok:
                k, v = tok.split("=", 1)
                objs[int(k)] = int(v, 16)
        rev = {v: k for k, v in objs.items()}
        print(f"parsed Spr entries: {len(objs)}")

        if not objs:
            return 1
        start = a.start if a.start is not None else min(objs)
        if start not in objs:
            print(f"Spr#{start} not parsed; parsed: {sorted(objs)}", file=sys.stderr)
            return 1

        chain = []
        seen = set()
        cur = objs[start]
        while cur and len(chain) < a.limit:
            idx = rev.get(cur)
            if idx is None:
                chain.append((None, cur))
                break
            if idx in seen:
                break
            seen.add(idx)
            chain.append((idx, cur))
            nxt = c.lua(f"return tostring(readInteger({cur} + 8))")
            cur = None if nxt == "nil" else int(nxt)

        print(f"\nchain starting at Spr#{start} ({len(chain)} members, draw order):")
        for pos, (idx, obj) in enumerate(chain):
            extra = ""
            if a.dump_frame is not None:
                vals = c.lua(f'''
local t = {{}}
for i = 0, 8 do
  local v = readInteger({obj} + 0x30 + i*4)
  t[#t+1] = v and string.format("%d", v) or "?"
end
return table.concat(t, " ")
''')
                extra = "  +0x30: " + vals
            print(f"  {pos:>2}  Spr#{idx if idx is not None else '?'}  obj={obj:08X}{extra}")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
