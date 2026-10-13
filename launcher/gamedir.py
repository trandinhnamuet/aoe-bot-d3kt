"""Where the player's own AoE (Rise of Rome, AoE-HD build) is installed.

find() tries, in order: the folder chosen last time (HKCU\\Software\\AoESolo GameDir), an AoE-HD folder
next to AoESolo.exe, the game's own install keys (InstallationDirectory / CDPath under
...\\Microsoft\\Games\\Age of Empires\\1.00 - XArena and the original installer write them), common
install paths, and a shallow look at every drive. A folder counts when it holds EMPIRESX.EXE.
remember(path) stores the player's choice. known_build(path) says whether EMPIRESX.EXE is the build the
bots were made for (the hook calls functions at fixed addresses of that build)."""
import hashlib
import os
import string

try:
    import winreg
except ImportError:  # noqa: BLE001
    winreg = None

EXE = "EMPIRESX.EXE"
APP_KEY = r"Software\AoESolo"
AOE_KEYS = [r"SOFTWARE\WOW6432Node\Microsoft\Games\Age of Empires\1.00",
            r"SOFTWARE\Microsoft\Games\Age of Empires\1.00"]
KNOWN_SHA1 = {"0d10456e458e3487f99c814583ec37745507ce47"}      # the AoE-HD build the addresses were found in
COMMON = [r"Program Files\XArena\Game\AoE-HD", r"Program Files (x86)\XArena\Game\AoE-HD",
          r"Program Files (x86)\Microsoft Games\Age of Empires", r"Program Files\Microsoft Games\Age of Empires",
          r"AoE-HD", r"Game\AoE-HD", r"Games\AoE-HD", r"AoE", r"Games\AoE", r"Age of Empires"]


def has_game(path):
    return bool(path) and os.path.isfile(os.path.join(path, EXE))


def _reg(root, key, name):
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, key) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def remembered():
    return _reg(winreg.HKEY_CURRENT_USER, APP_KEY, "GameDir") if winreg else None


def remember(path):
    if winreg is None:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_KEY) as k:
            winreg.SetValueEx(k, "GameDir", 0, winreg.REG_SZ, path)
    except OSError:
        pass


def _drives():
    out = []
    for d in string.ascii_uppercase:
        root = d + ":\\"
        if os.path.exists(root):
            out.append(root)
    return out


def candidates(base_dir):
    seen = []

    def add(p):
        if p:
            p = os.path.normpath(str(p).strip().strip('"'))
            if p not in seen:
                seen.append(p)
    add(remembered())
    add(os.path.join(base_dir, "AoE-HD"))
    add(base_dir)
    if winreg is not None:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for key in AOE_KEYS:
                for name in ("InstallationDirectory", "CDPath", "EXE Path"):
                    add(_reg(root, key, name))
    for drive in _drives():
        for rel in COMMON:
            add(os.path.join(drive, rel))
    return seen


def _shallow(drive, depth=2):
    """Folders up to `depth` levels under a drive root that hold the game (skips Windows / system dirs)."""
    skip = {"windows", "$recycle.bin", "system volume information", "programdata", "users", "recovery"}
    level = [drive]
    for _ in range(depth):
        nxt = []
        for d in level:
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for n in names:
                p = os.path.join(d, n)
                if n.lower() in skip or not os.path.isdir(p):
                    continue
                if has_game(p):
                    return p
                nxt.append(p)
        level = nxt[:400]
    return None


def find(base_dir, deep=True):
    for p in candidates(base_dir):
        if has_game(p):
            return p
    if deep:
        for drive in _drives():
            p = _shallow(drive)
            if p:
                return p
    return None


def known_build(path):
    try:
        h = hashlib.sha1()
        with open(os.path.join(path, EXE), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest() in KNOWN_SHA1
    except OSError:
        return False


SKIP_DIRS = {"savegame", "scenario", "learn", "campaign", "History"}


def writable(path):
    try:
        test = os.path.join(path, ".aoesolo_write_test")
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return True
    except OSError:
        return False


def local_copy_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AoESolo", "AoE-HD")


def copy_local(src, progress=lambda n, tot: None):
    """Copy the player's own install to a folder AoESolo may write in (the bot copy of the exe and the
    game settings live in the game folder; Program Files needs admin rights). Returns the new path."""
    import shutil
    dst = local_copy_dir()
    files = []
    for d, dirs, names in os.walk(src):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for n in names:
            files.append(os.path.join(d, n))
    for i, f in enumerate(files):
        rel = os.path.relpath(f, src)
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if not os.path.exists(out) or os.path.getsize(out) != os.path.getsize(f):
            shutil.copy2(f, out)
        if i % 50 == 0:
            progress(i, len(files))
    for n in SKIP_DIRS:
        os.makedirs(os.path.join(dst, n), exist_ok=True)
    return dst
