"""Lists every window (shown or hidden) of the AOEBOT.EXE processes on the user's desktop and on the hidden bot
desktop, with class and title, and screenshots each one to a folder: what is a stalled hidden game showing?
Read-only: nothing is clicked or killed.

    .venv/Scripts/python tools/winlist.py <out_dir>"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "launcher"))
import psutil  # noqa: E402

import gamewin  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(out, exist_ok=True)
gamewin.bot_desktop()
for p in psutil.process_iter(["name", "pid"]):
    if (p.info["name"] or "").upper() != "AOEBOT.EXE":
        continue
    pid = p.info["pid"]
    mods = []
    try:
        mods = sorted({os.path.basename(m.path).lower() for m in p.memory_maps()})
    except Exception as e:  # noqa: BLE001
        mods = ["(memory_maps: %r)" % (e,)]
    print("pid %d modules of interest: %s" % (pid, [m for m in mods if m in ("meme.dll", "exwe.dll", "ddraw.dll", "aoehook.dll", "dsound.dll")]))
    for hwnd, title, cls in gamewin.windows_of_pid(pid, visible_only=False):
        vis = gamewin.user32.IsWindowVisible(hwnd)
        (l, t, r, b), _ = gamewin.rects(hwnd)
        print("  hwnd %x vis=%d class=%r title=%r rect=%s" % (hwnd, vis, cls, title, (l, t, r, b)))
        if r - l > 50 and b - t > 30:
            path = os.path.join(out, "%d_%x.png" % (pid, hwnd))
            try:
                gamewin.screenshot(hwnd, path)
                print("    shot", path)
            except Exception as e:  # noqa: BLE001
                print("    shot failed %r" % (e,))
