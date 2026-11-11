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
KNOWN_SHA1 = {"0d10456e458e3487f99c814583ec37745507ce47",       # AoE HD (XArena) - the addresses were found here
              "7bb06b0cd465b2639cc90a10f12533ee002e3a0c",                               # the same code unsigned, data\empires.dat (cafe G:)
              "0a9c9bf528da8fd678abc5db0391436809a977d9"}       # AoE (AOE1R): same layout, only resolution patches
HD, NORMAL = "AoE HD", "AoE thường (AOE1R)"
EDITIONS = [HD, NORMAL]
EDITION_SHA1 = {"0d10456e458e3487f99c814583ec37745507ce47": HD, "7bb06b0cd465b2639cc90a10f12533ee002e3a0c": HD, "0a9c9bf528da8fd678abc5db0391436809a977d9": NORMAL}
EDITION_KEY = {HD: "GameDirHD", NORMAL: "GameDirNormal"}
COMMON = [r"Game Online\XArena\Game\AoE-HD", r"XArena\Game\AoE-HD", r"Game Online\XArena\Game\AOE1R",
          r"XArena\Game\AOE1R",                      # (the cafe's XArena, 07/11: H:\Game Online\XArena\Game\AoE-HD)
          r"Program Files\XArena\Game\AoE-HD", r"Program Files (x86)\XArena\Game\AoE-HD",
          r"Program Files\XArena\Game\AOE1R", r"Program Files (x86)\XArena\Game\AOE1R",
          r"AOE1R", r"Game\AOE1R", r"Games\AOE1R",
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
    # the full package (AoESolo_full.zip, 12/11) ships a Games folder next to AoESolo.exe: the game is in it or
    # in one of its subfolders
    games = os.path.join(base_dir, "Games")
    add(games)
    try:
        for n in sorted(os.listdir(games)):
            if os.path.isdir(os.path.join(games, n)):
                add(os.path.join(games, n))
    except OSError:
        pass
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


def quality(p):
    """2 for the bots' known build + 1 for cnc-ddraw: the same game on native DirectDraw ran ~10x slower in an
    8-player match (the cafe's G: "Games Off" copy, 07/11: 48 game seconds in 8 minutes, bots dropped)."""
    try:
        import botdir
        dd = botdir.ddraw_kind(p) == "cnc-ddraw"
    except Exception:  # noqa: BLE001
        dd = False
    return 2 * known_build(p) + dd


def manual_choice():
    return _reg(winreg.HKEY_CURRENT_USER, APP_KEY, "GameDirManual") if winreg else None


def remember_manual(path):
    """A folder the player picked himself is kept even when a better one is found."""
    if winreg is None:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_KEY) as k:
            winreg.SetValueEx(k, "GameDirManual", 0, winreg.REG_SZ, path or "")
    except OSError:
        pass


def _is_manual(p):
    m = manual_choice()
    return bool(m) and os.path.normcase(os.path.normpath(m)) == os.path.normcase(os.path.normpath(p))


def best(paths):
    """The player's own pick if among them, else the best quality (ties: the first)."""
    paths = [p for p in paths if has_game(p)]
    for p in paths:
        if _is_manual(p):
            return p
    return max(paths, key=lambda p: (quality(p), -paths.index(p))) if paths else None


def find(base_dir, deep=True):
    p = best(candidates(base_dir))
    if p:
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


def local_copy_dir(src=None):
    """%LOCALAPPDATA%\AoESolo\<the source folder's name> (one folder per edition)."""
    name = os.path.basename(os.path.normpath(src)) if src else "AoE-HD"
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AoESolo", name or "AoE-HD")


def copy_local(src, progress=lambda n, tot: None):
    """Copy the player's own install to a folder AoESolo may write in (the bot copy of the exe and the
    game settings live in the game folder; Program Files needs admin rights). Returns the new path."""
    import shutil
    dst = local_copy_dir(src)
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


def _sha1(path):
    try:
        h = hashlib.sha1()
        with open(os.path.join(path, EXE), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


_EDITION_CACHE = {}


def edition_of(path):
    """AoE HD / AoE thường by the exe's hash, else by the folder name; None when it is neither."""
    key = os.path.normcase(os.path.normpath(path or ""))
    if key in _EDITION_CACHE:
        return _EDITION_CACHE[key]
    e = _edition_of(path)
    _EDITION_CACHE[key] = e
    return e


def _edition_of(path):
    e = EDITION_SHA1.get(_sha1(path) or "")
    if e:
        return e
    n = os.path.basename(os.path.normpath(path)).lower()
    if "hd" in n:
        return HD
    if "1r" in n or "aoe" in n:
        return NORMAL
    return None


def remember_edition(edition, path):
    if winreg is None:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_KEY) as k:
            winreg.SetValueEx(k, EDITION_KEY[edition], 0, winreg.REG_SZ, path)
            winreg.SetValueEx(k, "Edition", 0, winreg.REG_SZ, edition)
    except OSError:
        pass


def remembered_edition():
    return _reg(winreg.HKEY_CURRENT_USER, APP_KEY, "Edition") if winreg else None


def find_editions(base_dir, deep=False):
    """{edition: folder} of every install found (the remembered ones first)."""
    out = {}
    if winreg is not None:
        for e, key in EDITION_KEY.items():
            p = _reg(winreg.HKEY_CURRENT_USER, APP_KEY, key)
            if has_game(p):
                out[e] = os.path.normpath(p)
    paths = [p for p in candidates(base_dir) if has_game(p)]
    if deep:
        for drive in _drives():
            p = _shallow(drive)
            if p:
                paths.append(p)
    by_ed = {}
    for p in paths:
        e = edition_of(p)
        if e:
            by_ed.setdefault(e, []).append(p)
    for e, ps in by_ed.items():
        if e in out and (_is_manual(out[e]) or quality(out[e]) >= max(quality(p) for p in ps)):
            continue
        out[e] = best(([out[e]] if e in out else []) + ps)
    return out
