"""Where the hidden bots' exe (AOEBOT.EXE) runs from.

The bots run windowed off screen through cnc-ddraw (the [AOEBOT] section of its ddraw.ini). A game folder
without cnc-ddraw (a cafe's "G:\\Games Off\\Aoe-HD", 07/11, 1.2.26) left every hidden bot on native
DirectDraw: the window appeared, the game never reached its main menu (screen None) and no room filled.
Then AOEBOT.EXE goes to a folder of AoESolo's own together with the bundled cnc-ddraw (third_party/),
while the bot still starts in the game folder (cwd), so it reads the game's data from there. The DLLs a
Windows folder would otherwise shadow (dplayx.dll) are copied next to it. The player's folder and the
player's own game stay untouched."""
import hashlib
import os
import shutil
import sys

DDRAW = "ddraw.dll"
_MARKS = ("cnc-ddraw".encode("utf-16-le"), b"cnc-ddraw")
SHADOWED = ("dplayx.dll",)       # game-folder DLLs that also exist in System32 (the exe folder wins over both)


def ddraw_kind(game_dir):
    """'cnc-ddraw', 'other' (another wrapper), 'none' (native DirectDraw) or 'unreadable'."""
    p = os.path.join(game_dir, DDRAW)
    if not os.path.exists(p):
        return "none"
    try:
        with open(p, "rb") as f:
            data = f.read()
    except OSError:
        return "unreadable"
    return "cnc-ddraw" if any(m in data for m in _MARKS) else "other"


def bundled_dir():
    root = getattr(sys, "_MEIPASS", None)
    if root:
        return os.path.join(root, "bin", "cnc-ddraw")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "third_party", "cnc-ddraw")


def separate(game_dir):
    force = os.environ.get("AOESOLO_BOT_DIR", "")       # tests: "separate" / "game"
    if force in ("separate", "game"):
        return force == "separate"
    return ddraw_kind(game_dir) != "cnc-ddraw"


def bot_dir(game_dir):
    if not separate(game_dir):
        return game_dir
    norm = os.path.normcase(os.path.abspath(game_dir))
    tag = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:8]
    name = "".join(c if c.isalnum() or c in "-_." else "_" for c in os.path.basename(os.path.normpath(game_dir)))
    # (AOESOLO_BOTEXE_ROOT: tests from the Microsoft Store Python, whose writes to LOCALAPPDATA are redirected
    #  into its package - a game started from there saw no ddraw.dll and hung like the cafe)
    root = os.environ.get("AOESOLO_BOTEXE_ROOT") or os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AoESolo", "botexe")
    return os.path.join(root, "%s-%s" % (name or "game", tag))


def _write_if_changed(path, data):
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return
    except OSError:
        pass
    with open(path, "wb") as f:
        f.write(data)


def prepare_separate(game_dir, d, bot_ini_section):
    """cnc-ddraw (+ its ddraw.ini with the bots' section) and the shadowed game DLLs in the bot folder d."""
    os.makedirs(d, exist_ok=True)
    src = bundled_dir()
    with open(os.path.join(src, DDRAW), "rb") as f:
        _write_if_changed(os.path.join(d, DDRAW), f.read())
    with open(os.path.join(src, "ddraw.ini"), "rb") as f:
        ini = f.read()
    _write_if_changed(os.path.join(d, "ddraw.ini"), ini + bot_ini_section.replace("\n", "\r\n").encode("latin-1"))
    for n in SHADOWED:
        s = os.path.join(game_dir, n)
        t = os.path.join(d, n)
        if os.path.exists(s):
            if not os.path.exists(t) or os.path.getsize(t) != os.path.getsize(s) or \
                    os.path.getmtime(t) < os.path.getmtime(s):
                shutil.copy2(s, t)
        elif os.path.exists(t):
            os.remove(t)
