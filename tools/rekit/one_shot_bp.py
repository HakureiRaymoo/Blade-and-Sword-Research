"""One narrow breakpoint, short window, then clean up.

Waits for the game window to become foreground, attaches, installs a single
hardware breakpoint on one draw candidate, samples for a fraction of a second
and removes it immediately. Falls through to the next candidate only if the
previous one produced no hits.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time

sys.path.insert(0, r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\tools\rekit")
from ce_client import CEClient  # noqa: E402

CANDS = ["0x51AD90", "0x51A050", "0x506700"]
user32 = ctypes.WinDLL("user32", use_last_error=True)


def find_hwnd():
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _l):
        n = user32.GetWindowTextLengthW(h)
        if n:
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, b, n + 1)
            if "Daojian" in b.value or "ComeOn" in b.value:
                pid = wt.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                out.append((h, pid.value, b.value))
        return True

    user32.EnumWindows(cb, 0)
    return out[0] if out else None


def main() -> int:
    hit = find_hwnd()
    if not hit:
        print("no game window")
        return 1
    hwnd, pid, title = hit
    print(f"window {title!r} pid={pid}")
    print("waiting for focus (up to 30s) ...")
    deadline = time.time() + 30
    while time.time() < deadline and user32.GetForegroundWindow() != hwnd:
        time.sleep(0.2)
    focused = user32.GetForegroundWindow() == hwnd
    print("focused:", focused)
    if not focused:
        return 2

    c = CEClient()
    c.lua(f"return tostring(openProcess({pid}))")
    c.call("debug_process", {})
    print("threads:", (c.call("get_thread_list", {"offset": 0, "limit": 1}).get("result") or {}).get("total"))

    try:
        for addr in CANDS:
            if user32.GetForegroundWindow() != hwnd:
                print("focus lost, stopping")
                break
            bid = "n" + addr[2:]
            print(f"bp {addr} ...", end=" ", flush=True)
            c.call("set_breakpoint", {"address": addr, "id": bid, "capture_registers": True,
                                      "capture_stack": True, "stack_depth": 12})
            time.sleep(0.35)
            r = (c.call("get_breakpoint_hits", {"id": bid, "offset": 0, "limit": 20}).get("result") or {})
            c.call("remove_breakpoint", {"id": bid})
            total = r.get("total", 0)
            print(f"hits={total}")
            if total:
                for h in (r.get("hits") or [])[:10]:
                    regs = h.get("registers") or {}
                    print("   this=%s edx=%s stack=%s" % (regs.get("ECX"), regs.get("EDX"), h.get("stack")))
                break
    finally:
        c.call("clear_all_breakpoints", {})
        c.close()
        print("breakpoints cleared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
