"""Start game instances (visible for the player, hidden for bots) and attach the hook."""
import os
import subprocess
import time

import gamewin as gw
import inject

SW_HIDE = 0
SW_SHOWNORMAL = 1

import ctypes
import ctypes.wintypes as wt

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateJobObjectW.restype = wt.HANDLE
_k32.OpenProcess.restype = wt.HANDLE
_job = None


def _kill_on_close_job():
    """All bot processes live in a job that Windows kills when the launcher exits (even on a crash)."""
    global _job
    if _job:
        return _job

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("Basic", BASIC), ("Io", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    job = _k32.CreateJobObjectW(None, None)
    info = EXTENDED()
    info.Basic.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    _k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    _job = job
    return job


def _attach_to_job(pid):
    h = _k32.OpenProcess(0x1F0FFF, False, pid)
    if h:
        _k32.AssignProcessToJobObject(_kill_on_close_job(), h)
        _k32.CloseHandle(h)


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR), ("lpTitle", wt.LPWSTR),
                ("dwX", wt.DWORD), ("dwY", wt.DWORD), ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD),
                ("dwXCountChars", wt.DWORD), ("dwYCountChars", wt.DWORD), ("dwFillAttribute", wt.DWORD),
                ("dwFlags", wt.DWORD), ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wt.HANDLE), ("hStdOutput", wt.HANDLE),
                ("hStdError", wt.HANDLE)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE), ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


def _start_on_desktop(args, cwd, desktop, env=None):
    """CreateProcess on another desktop (subprocess cannot set lpDesktop). Returns a Popen-like object."""
    import psutil
    si = _STARTUPINFOW()
    si.cb = ctypes.sizeof(si)
    si.lpDesktop = desktop
    si.dwFlags = 1                               # STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    pi = _PROCESS_INFORMATION()
    cmd = ctypes.create_unicode_buffer(subprocess.list2cmdline(args))
    _k32.CreateProcessW.argtypes = [wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL, wt.DWORD,
                                    ctypes.c_void_p, wt.LPCWSTR, ctypes.POINTER(_STARTUPINFOW),
                                    ctypes.POINTER(_PROCESS_INFORMATION)]
    block = None
    if env is not None:                          # CREATE_UNICODE_ENVIRONMENT block "k=v\0...\0\0"
        block = ctypes.create_unicode_buffer("".join("%s=%s\0" % kv for kv in sorted(env.items())) + "\0")
    if not _k32.CreateProcessW(None, cmd, None, None, False, 0x400 if block is not None else 0, block, cwd,
                               ctypes.byref(si), ctypes.byref(pi)):
        raise OSError("CreateProcess on desktop %s failed %d" % (desktop, ctypes.get_last_error()))
    _k32.CloseHandle(pi.hThread)
    _k32.CloseHandle(pi.hProcess)
    return _PsProc(psutil.Process(pi.dwProcessId))


class GameProc:
    def __init__(self, popen, hwnd, hook, mem, hidden):
        self.p = popen
        self.pid = popen.pid
        self.hwnd = hwnd
        self.hook = hook
        self.mem = mem
        self.hidden = hidden

    def alive(self):
        return self.p.poll() is None

    def kill(self):
        try:
            self.p.kill()
        except OSError:
            pass


class _PsProc:
    """Popen-like wrapper for a process we did not start ourselves (e.g. launched by DirectPlay Lobby)."""

    def __init__(self, ps):
        self.ps = ps
        self.pid = ps.pid

    def poll(self):
        try:
            return None if self.ps.is_running() and self.ps.status() != "zombie" else 0
        except Exception:
            return 0

    def kill(self):
        try:
            self.ps.kill()
        except Exception:
            pass


def attach(ps, dll, log=print, timeout=40):
    """Hook an already running (visible) player game."""
    hwnd = gw.main_window(ps.pid, timeout)
    if not hwnd:
        raise RuntimeError("game window did not appear (pid %d)" % ps.pid)
    inject.inject(ps.pid, dll)
    hook = inject.Hook(ps.pid)
    hook.cmd("vin 1")
    hook.cmd("autodlg 127.0.0.1")
    log("attached to pid=%d" % ps.pid)
    return GameProc(_PsProc(ps), hwnd, hook, inject.Mem(ps.pid), False)


def start(game_dir, exe, dll, hidden, log=print, timeout=40, job=True):
    """Launch one instance, inject the hook and (for bots) keep it hidden and inert to real input."""
    if hidden:
        # Only the current foreground process (the launcher) may change the foreground while locked.
        gw.user32.LockSetForegroundWindow(1)
    args = [os.path.join(game_dir, exe), "nostartup"] + (["nosound"] if hidden else [])
    env = None
    if os.path.normcase(os.path.dirname(os.path.abspath(args[0]))) != os.path.normcase(os.path.abspath(game_dir)):
        # exe outside the game folder (botdir.py): the game's own DLLs (ExWE.dll, language.dll...) are found through
        # PATH - the cafe's Windows does not search the working folder ("ExWE.dll was not found", 07/11, 1.2.27)
        env = dict(os.environ)
        env["PATH"] = os.path.abspath(game_dir) + os.pathsep + env.get("PATH", "")
    desk = gw.bot_desktop() if hidden and os.environ.get("AOESOLO_BOT_DESKTOP", "1") != "0" else None
    old_mode = None
    if hidden:
        # a bot that cannot start must not put a Windows "System Error" box in front of the player (the cafe's
        # "ExWE.dll was not found", 07/11): SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX, inherited by the child
        old_mode = _k32.SetErrorMode(0x8001)
        _k32.SetErrorMode(old_mode | 0x8001)
    try:
        if desk:
            p = _start_on_desktop(args, game_dir, desk, env)
        else:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = SW_HIDE if hidden else SW_SHOWNORMAL
            p = subprocess.Popen(args, cwd=game_dir, startupinfo=si, env=env)
    finally:
        if old_mode is not None:
            _k32.SetErrorMode(old_mode)
    if hidden and job:
        _attach_to_job(p.pid)
    t0 = time.time()
    hwnd = None
    while time.time() - t0 < timeout:
        hwnd = gw.main_window(p.pid, 1.0)
        if hwnd:
            break
        if p.poll() is not None:
            raise RuntimeError("%s exited at start (a missing DLL?)" % exe)
    if not hwnd:
        p.kill()
        raise RuntimeError("game window did not appear for %s" % exe)
    inject.inject(p.pid, dll)
    hook = inject.Hook(p.pid)
    if hidden:
        hook.cmd("noreg 1")        # bots never overwrite the player's settings (name, resolution...)
        hook.cmd("hide 1")
    hook.cmd("vin 1")              # virtual input during automation
    hook.cmd("autodlg 127.0.0.1")  # DirectPlay locate dialog: fill and confirm offscreen
    if hidden:
        gw.user32.LockSetForegroundWindow(2)
    log("started %s pid=%d hidden=%s" % (exe, p.pid, hidden))
    gp = GameProc(p, hwnd, hook, inject.Mem(p.pid), hidden)
    set_menu_scale(gp, game_dir)
    return gp


def set_menu_scale(gp, game_dir):
    """The normal AoE (AOE1R) draws its menus at a fixed 800x600 in the top-left corner whatever the
    resolution; the HD build stretches them to the screen. Lobby coordinates are written for 1366x768."""
    try:
        import gamedir
        normal = gamedir.edition_of(game_dir) == gamedir.NORMAL
    except Exception:  # noqa: BLE001
        normal = False
    gp.menu_fixed = normal
    if normal:
        gp.sx, gp.sy = 800 / 1366.0, 600 / 768.0
