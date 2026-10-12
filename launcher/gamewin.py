"""Window helpers for driving the AoE game process: find window, screenshot, click, keys."""
import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
user32.SetProcessDPIAware()

WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP = 0x201, 0x202, 0x204, 0x205
WM_MOUSEMOVE, WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x200, 0x100, 0x101, 0x102
MK_LBUTTON, MK_RBUTTON = 0x1, 0x2
SW_RESTORE = 9

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def windows_of_pid(pid, visible_only=True):
    found = []

    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and (not visible_only or user32.IsWindowVisible(hwnd)):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append((hwnd, buf.value, cls.value))
        return True

    proc = EnumWindowsProc(cb)
    user32.EnumWindows(proc, 0)
    if BOT_DESKTOP:                              # hidden bots live on their own desktop (see bot_desktop)
        user32.EnumDesktopWindows(BOT_DESKTOP, proc, 0)
    return found


BOT_DESKTOP = None
BOT_DESKTOP_NAME = "AoESoloBots"


def bot_desktop():
    """A separate, never-shown desktop for the hidden bot games: their windows can never take the
    foreground, flash or cover the user's windows (they did for a moment at every bot start, before
    the hook could hide them). Name to pass as STARTUPINFO.lpDesktop, or None if it cannot be made."""
    global BOT_DESKTOP
    if BOT_DESKTOP is None:
        user32.CreateDesktopW.restype = wt.HANDLE
        user32.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD,
                                          ctypes.c_void_p]
        user32.EnumDesktopWindows.argtypes = [wt.HANDLE, EnumWindowsProc, wt.LPARAM]
        h = user32.CreateDesktopW(BOT_DESKTOP_NAME, None, None, 0, 0x10000000, None)   # GENERIC_ALL
        BOT_DESKTOP = h or 0
    return BOT_DESKTOP_NAME if BOT_DESKTOP else None


def main_window(pid, timeout=30):
    """The game's top-level window (by class), visible or hidden."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        ws = [w for w in windows_of_pid(pid, visible_only=False) if "Age of Empires" in w[2]]
        if ws:
            return ws[0][0]
        time.sleep(0.3)
    return None


def rects(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    c = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(c))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return (r.left, r.top, r.right, r.bottom), (pt.x, pt.y, pt.x + c.right, pt.y + c.bottom)


def screenshot(hwnd, path=None):
    """Capture the window's client area even when it is covered (PrintWindow)."""
    from PIL import Image
    gdi32 = ctypes.windll.gdi32
    c = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(c))
    w, h = c.right, c.bottom
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    PW_CLIENTONLY, PW_RENDERFULLCONTENT = 0x1, 0x2
    user32.PrintWindow(hwnd, mdc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]

    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)
    if path:
        img.save(path)
    return img


def focus(hwnd):
    """Bring the window to the foreground even from a background process."""
    fgw = user32.GetForegroundWindow()
    if fgw == hwnd:
        return True
    tid_fg = user32.GetWindowThreadProcessId(fgw, None)
    tid_me = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(tid_me, tid_fg, True)
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetActiveWindow(hwnd)
    user32.SetFocus(hwnd)
    user32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


def _lparam(x, y):
    return (y << 16) | (x & 0xFFFF)


def post_click(hwnd, x, y, button="left", hold=0.08):
    """Click at client coordinates via window messages (no focus needed)."""
    down, up, mk = (WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON) if button == "left" else (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON)
    lp = _lparam(x, y)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.03)
    user32.PostMessageW(hwnd, down, mk, lp)
    time.sleep(hold)
    user32.PostMessageW(hwnd, up, 0, lp)


def _send_input_mouse(flags, dx=0, dy=0):
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 8)]

    inp = INPUT(type=0, mi=MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=None))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def real_click(hwnd, x, y, button="left", hold=0.12):
    """Click at client coordinates with the real cursor. Returns False if the game is not foreground."""
    if not focus(hwnd):
        return False
    _, client = rects(hwnd)
    sx, sy = client[0] + x, client[1] + y
    user32.SetCursorPos(sx, sy)
    time.sleep(0.05)
    user32.mouse_event(0x0001, 1, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(0x0001, -1, 0, 0, 0)
    time.sleep(0.08)
    down, up = (0x0002, 0x0004) if button == "left" else (0x0008, 0x0010)
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(hold)
    user32.mouse_event(up, 0, 0, 0, 0)
    return True


def real_key(hwnd, vk, hold=0.06):
    """Press a key with real keyboard input (needs focus)."""
    if not focus(hwnd):
        return False
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(hold)
    user32.keybd_event(vk, 0, 0x0002, 0)
    return True


def key(hwnd, vk, hold=0.05):
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0xC0000000)


def modules32(pid):
    """Names of modules loaded in a 32-bit process."""
    PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x400, 0x10
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return []
    arr = (wt.HMODULE * 1024)()
    needed = wt.DWORD()
    psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(needed), 0x01)
    names = []
    for i in range(needed.value // ctypes.sizeof(wt.HMODULE)):
        buf = ctypes.create_unicode_buffer(260)
        psapi.GetModuleFileNameExW(h, arr[i], buf, 260)
        names.append(buf.value)
    kernel32.CloseHandle(h)
    return names
