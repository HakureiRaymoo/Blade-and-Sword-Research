"""Attach first, then fire a single breakpoint within milliseconds of focus.

The coordination problem: the user must click the game, but any command the
agent runs starts only after the user is back in the chat window. So attach
ahead of time and let a lightweight watcher fire the instant the game becomes
foreground, sampling for a fraction of a second only.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time

sys.path.insert(0, r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\tools\rekit")
from ce_client import CEClient  # noqa: E402

CANDS = ["0x51AD90", "0x51A050", "0x506700", "0x518AA0"]
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
    print(f"window {title!r} pid={pid}", flush=True)

    c = CEClient()
    c.lua(f"return tostring(openProcess({pid}))")
    c.call("debug_process", {})
    threads = (c.call("get_thread_list", {"offset": 0, "limit": 1}).get("result") or {}).get("total")
    print(f"attached, threads={threads}, waiting for focus (180s) ...", flush=True)

    deadline = time.time() + 180
    while time.time() < deadline:
        if user32.GetForegroundWindow() == hwnd:
            break
        time.sleep(0.03)
    else:
        print("never got focus")
        return 2

    print("focus detected -- firing", flush=True)
    t0 = time.time()
    try:
        for addr in CANDS:
            bid = "w" + addr[2:]
            c.call("set_breakpoint", {"address": addr, "id": bid, "capture_registers": True,
                                      "capture_stack": True, "stack_depth": 12})
            time.sleep(0.30)
            r = (c.call("get_breakpoint_hits", {"id": bid, "offset": 0, "limit": 12}).get("result") or {})
            c.call("remove_breakpoint", {"id": bid})
            n = r.get("total", 0)
            print(f"  {addr} hits={n}  (t+{time.time()-t0:.2f}s)", flush=True)
            if n:
                for h in (r.get("hits") or [])[:8]:
                    regs = h.get("registers") or {}
                    print("     this=%s edx=%s stack=%s" % (regs.get("ECX"), regs.get("EDX"), h.get("stack")), flush=True)
                break
    finally:
        c.call("clear_all_breakpoints", {})
        c.close()
        print("cleared", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
