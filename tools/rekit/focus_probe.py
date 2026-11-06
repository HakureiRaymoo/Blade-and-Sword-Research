"""Wait for the game window to become foreground, then probe draw functions.

!!! UNSAFE BY DEFAULT -- requires --yes !!!
Installing hardware breakpoints the instant the game regains focus coincided
with a crash on this title. The callbacks fire thousands of times per second
on hot paths, and the game is a 2003 DirectDraw build under WOW64 plus the
dgVoodoo translation layer. Prefer memory scans; if breakpoints are truly
needed, use one narrow function at a time.

The game skips rendering while it is not the active window, so breakpoints on
the draw path never fire. This job waits (up to --timeout seconds) for the
game to get focus, then runs the probe automatically -- the user only has to
click the game once.

    py tools/rekit/focus_probe.py --timeout 600 --out out/probe/focus.txt
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

from ce_client import CEClient  # noqa: E402

TITLE_HINTS = ("DaojianServer", "ComeOn")
EXCLUDE = ("DeepSeek", "Harness", "Chrome", "Edge")

CANDS = [
    ("0x51AD90", "image blit B+12"),
    ("0x51A050", "image draw A+16"),
    ("0x506700", "A+12"),
    ("0x518AA0", "A+12 target"),
    ("0x51A5B0", "B+16"),
    ("0x517840", "A+44"),
]

user32 = ctypes.WinDLL("user32", use_last_error=True)


def find_hwnd() -> tuple[int, int, str] | None:
    found: list[tuple[int, int, str]] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _l):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            t = buf.value
            if any(h.lower() in t.lower() for h in TITLE_HINTS) and \
               not any(x.lower() in t.lower() for x in EXCLUDE):
                pid = wt.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found.append((int(hwnd), int(pid.value), t))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def foreground() -> int:
    return int(user32.GetForegroundWindow())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default="out/probe/focus.txt")
    ap.add_argument("--yes", action="store_true",
                    help="required: acknowledge the breakpoint risk described in the docstring")
    args = ap.parse_args(argv)

    if not args.yes:
        print("refusing to install breakpoints without --yes (see module docstring)")
        return 3

    hit = find_hwnd()
    if not hit:
        print("no game window found")
        return 1
    hwnd, pid, title = hit
    log = open(args.out, "w", encoding="utf-8")

    def say(msg: str) -> None:
        print(msg)
        log.write(msg + "\n")
        log.flush()

    say(f"game window {title!r} hwnd={hwnd} pid={pid}")
    say("waiting for the game to become foreground ...")

    deadline = time.time() + args.timeout
    while time.time() < deadline and foreground() != hwnd:
        time.sleep(0.25)

    if foreground() != hwnd:
        say("timed out without focus")
        return 2

    say("game is foreground -- attaching")
    c = CEClient()
    c.lua(f"return tostring(openProcess({pid}))")
    c.call("debug_process", {})
    threads = (c.call("get_thread_list", {"offset": 0, "limit": 1}).get("result") or {}).get("total")
    say(f"threads={threads}")
    say(f"foreground guard holds: {foreground() == hwnd}")

    for addr, tag in CANDS:
        if foreground() != hwnd:
            say("focus lost, aborting probe")
            break
        bid = "f" + addr[2:]
        c.call("set_breakpoint", {"address": addr, "id": bid, "capture_registers": True,
                                  "capture_stack": True, "stack_depth": 10})
        time.sleep(0.4)
        r = (c.call("get_breakpoint_hits", {"id": bid, "offset": 0, "limit": 3}).get("result") or {})
        n = r.get("total", 0)
        hits = r.get("hits") or []
        c.call("remove_breakpoint", {"id": bid})
        msg = f"{addr} {tag:<16} hits={n}"
        if hits:
            h = hits[0]
            msg += "  regs=" + str({k: v for k, v in (h.get("registers") or {}).items() if k in ("ECX", "EDX", "ESI", "EDI")})
            msg += "  stack=" + str(h.get("stack"))
        say(msg)

    c.close()
    log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

