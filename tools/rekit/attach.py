"""Attach the Cheat Engine bridge to the running game, robust to restarts.

The game's PID changes every restart and its window title is not stable, so
this helper locates the window by several candidates, pulls the PID from the
window itself (process enumeration is filtered in the agent sandbox), then
asks CE to open and debug the process.

    py tools/rekit/attach.py            # attach
    py tools/rekit/attach.py --status   # just report
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

from ce_client import CEClient  # noqa: E402

TITLE_HINTS = ("DaojianServer", "ComeOn")
TITLE_EXCLUDE = ("DeepSeek", "Harness", "Chrome", "Edge", "Obsidian", "Code", "Visual Studio")


def find_game_window() -> tuple[int, str] | None:
    """Return (pid, title) of the first window whose title matches a hint."""
    import os
    me = os.getpid()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    results: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if any(h.lower() in title.lower() for h in TITLE_HINTS) and \
               not any(x.lower() in title.lower() for x in TITLE_EXCLUDE):
                pid = wt.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if int(pid.value) != me:
                    results.append((int(pid.value), title))
        return True

    user32.EnumWindows(cb, 0)
    return results[0] if results else None


def main(argv: list[str]) -> int:
    found = find_game_window()
    if not found:
        print("no game window found (titles tried: %s)" % ", ".join(TITLE_HINTS))
        return 1
    pid, title = found
    print(f"window: {title!r}  pid={pid}")

    c = CEClient()
    try:
        if "--status" in argv:
            print("ce pid :", c.lua("return tostring(getOpenedProcessID())"))
            print("threads:", (c.call("get_thread_list", {"offset": 0, "limit": 1}).get("result") or {}).get("total"))
            return 0

        ok = c.lua(f"return tostring(openProcess({pid}))")
        print("openProcess:", ok)
        print("debug      :", (c.call("debug_process", {}).get("result") or {}).get("success"))
        threads = (c.call("get_thread_list", {"offset": 0, "limit": 1}).get("result") or {}).get("total")
        print("threads    :", threads)
        mz = c.lua("return string.format('%04X', readInteger('ComeOn.exe'))")
        print("module MZ  :", mz, "(expect 5A4D)")
        if not threads:
            print("!! debugger has no threads -- breakpoints will not fire")
            return 2
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
