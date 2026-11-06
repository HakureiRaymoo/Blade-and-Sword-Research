"""Probe *why* the game stops animating while it is not the foreground window.

Compares window captures taken while the game is unfocused before and after
posting focus-related window messages (WM_ACTIVATEAPP / WM_ACTIVATE) from inside
Cheat Engine, which runs at a higher integrity level than this agent and can
therefore post to the game window at all.

    py tools/rekit/bg_probe.py                 # baseline only
    py tools/rekit/bg_probe.py --post 0x1C     # post WM_ACTIVATEAPP(TRUE) then retest
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from attach import find_game_window  # noqa: E402
from ce_client import CEClient  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURE = os.path.join(HERE, "capture_window.ps1")
OUT = r"D:\DSH WORK SPACE\Blade-and-Sword-Modernized\out\shots"

user32 = ctypes.WinDLL("user32", use_last_error=True)


def click_window(title_substr: str, dx: int = 200, dy: int = 12) -> str:
    """Bring a window to the foreground by clicking its title bar."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _l):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_substr.lower() in buf.value.lower():
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        return f"no window matching {title_substr!r}"
    hwnd, title = found[0]
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x, y = rect.left + dx, rect.top + dy
    user32.SetCursorPos(x, y)
    time.sleep(0.12)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    return f"clicked {title!r} at {x},{y}"


def foreground() -> str:
    h = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, buf, n + 1)
    return buf.value


def capture(tag: str, n: int = 2, interval: int = 800) -> list[str]:
    base = os.path.join(OUT, tag)
    subprocess.run([
        "pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", CAPTURE,
        "-Title", "DaojianServer", "-Out", base + ".bmp",
        "-Count", str(n), "-IntervalMs", str(interval),
    ], check=True, capture_output=True)
    return [f"{base}_{i}.bmp" for i in range(n)]


def diff(paths: list[str]) -> tuple[float, int]:
    from PIL import Image
    import numpy as np

    a = np.asarray(Image.open(paths[0]).convert("RGB")).astype(np.int16)
    worst = 0.0
    changed = 0
    for p in paths[1:]:
        b = np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
        d = np.abs(b - a)
        worst = max(worst, float(d.mean()))
        changed = max(changed, int((d.sum(2) > 12).sum()))
    return worst, changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", default=None, help="hex window message to post, e.g. 0x1C")
    ap.add_argument("--wparam", type=int, default=1)
    ap.add_argument("--focus-window", default="DeepSeek Harness")
    ap.add_argument("--shots", type=int, default=3)
    a = ap.parse_args(argv)

    print(click_window(a.focus_window))
    time.sleep(0.8)
    print("foreground:", foreground())

    paths = capture("bgp_before", a.shots)
    mean, changed = diff(paths)
    print(f"before: mean|d|={mean:.4f} changed_px={changed}")

    if a.post:
        found = find_game_window()
        if not found:
            print("game window not found", file=sys.stderr)
            return 1
        c = CEClient()
        try:
            c.lua(f"return tostring(openProcess({found[0]}))")
            res = c.lua(f'''
local hwnd = findWindow("DaojianServer")
if hwnd == nil then return "no hwnd" end
local ok = postMessage(hwnd, {int(a.post, 16)}, {a.wparam}, 0)
return string.format("hwnd=%X ok=%s", hwnd, tostring(ok))
''')
            print("post:", res)
        finally:
            c.close()
        time.sleep(0.5)
        paths = capture("bgp_after", a.shots)
        mean, changed = diff(paths)
        print(f"after : mean|d|={mean:.4f} changed_px={changed}")

    print("foreground:", foreground())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
