"""Launch the player's game through DirectPlay Lobby (straight into the multiplayer room as host).

DirectPlay finds the program to start through
HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\DirectPlay\\Applications\\<name> (needs admin once).
Our entry uses the original Rise of Rome GUID and a key name that sorts before the XArena / GameTV
entries, so RunApplication picks our copy of the game; the session keeps the standard GUID, which
lets the hidden bots find and join it from the normal multiplayer menu.
"""
import ctypes
import os
import subprocess
import tempfile
import time
import winreg

import psutil

APP_KEY = r"SOFTWARE\WOW6432Node\Microsoft\DirectPlay\Applications\!AoESolo"
ROR_GUID = "{8701C5C1-337B-11d2-839B-00609707F508}"
EXE = "EMPIRESX.EXE"
CMDLINE = "lobby nostartup"


def registered_dir():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, APP_KEY, 0, winreg.KEY_READ) as k:
            return winreg.QueryValueEx(k, "Path")[0]
    except OSError:
        return None


def is_registered(game_dir):
    d = registered_dir()
    return bool(d) and os.path.normcase(os.path.abspath(d)) == os.path.normcase(os.path.abspath(game_dir))


def register(game_dir, timeout=120, log=print):
    """Write the DirectPlay application entry with one UAC prompt. Returns True when registered."""
    game_dir = os.path.abspath(game_dir)
    esc = game_dir.replace("\\", "\\\\")
    reg = ("Windows Registry Editor Version 5.00\r\n\r\n"
           "[HKEY_LOCAL_MACHINE\\%s]\r\n" % APP_KEY.replace("\\", "\\") +
           '"Guid"="%s"\r\n"File"="%s"\r\n"CommandLine"="%s"\r\n"Path"="%s"\r\n"CurrentDirectory"="%s"\r\n'
           % (ROR_GUID, EXE, CMDLINE, esc, esc))
    path = os.path.join(tempfile.gettempdir(), "aoesolo_dplay.reg")
    with open(path, "w", encoding="utf-16") as f:
        f.write(reg)
    log("asking for administrator rights to register AoESolo with DirectPlay")
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "reg.exe", 'import "%s"' % path, None, 0)
    if rc <= 32:
        log("registration was not started (ShellExecute %d)" % rc)
        return False
    t0 = time.time()
    while time.time() - t0 < timeout:
        if is_registered(game_dir):
            log("DirectPlay registration done")
            return True
        time.sleep(0.5)
    log("DirectPlay registration not confirmed (UAC declined?)")
    return False


def launch_host(helper, game_dir, player_name, session_name="AoESolo", log=print, timeout=40):
    """Start the game hosting a TCP/IP room. Returns the psutil.Process of the new game."""
    target = os.path.normcase(os.path.join(os.path.abspath(game_dir), EXE))
    before = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == EXE.lower()}
    proc = subprocess.Popen([helper, "host", player_name, session_name],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=0x08000000)               # CREATE_NO_WINDOW
    t0 = time.time()
    while time.time() - t0 < timeout:
        for p in psutil.process_iter(["name", "exe"]):
            if p.pid in before or (p.info["name"] or "").lower() != EXE.lower():
                continue
            try:
                if os.path.normcase(p.info["exe"] or "") == target:
                    log("lobby launched %s pid=%d" % (EXE, p.pid))
                    return p, proc
            except (psutil.Error, TypeError):
                continue
        if proc.poll() not in (None, 0):
            out = proc.stdout.read().decode("latin-1", "replace") if proc.stdout else ""
            raise RuntimeError("dplaunch failed (%s): %s" % (proc.returncode, out.strip()))
        time.sleep(0.3)
    raise RuntimeError("the game did not start through DirectPlay Lobby")
