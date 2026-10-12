"""Inject aoehook.dll into a 32-bit (WOW64) game process and talk to it over its pipe."""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import time

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT_RESERVE = 0x3000
PAGE_READWRITE = 0x04
LIST_MODULES_32BIT = 0x01

kernel32.OpenProcess.restype = wt.HANDLE
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
kernel32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.CreateRemoteThread.restype = wt.HANDLE
kernel32.CreateRemoteThread.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]


def _modules32(h):
    arr = (ctypes.c_void_p * 1024)()
    need = wt.DWORD()
    if not psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(need), LIST_MODULES_32BIT):
        return {}
    mods = {}
    for i in range(need.value // ctypes.sizeof(ctypes.c_void_p)):
        buf = ctypes.create_unicode_buffer(260)
        psapi.GetModuleFileNameExW(h, arr[i], buf, 260)
        mods[buf.value.lower()] = arr[i]
    return mods


def _export_rva(dll_path, name):
    d = open(dll_path, "rb").read()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    optsz = struct.unpack_from("<H", d, pe + 20)[0]
    opt = pe + 24
    exp_rva, exp_sz = struct.unpack_from("<II", d, opt + 96)
    secs = [struct.unpack_from("<8sIIII", d, opt + optsz + i * 40) for i in range(nsec)]

    def r2o(rva):
        for _, vs, va, rs, ro in secs:
            if va <= rva < va + max(vs, rs):
                return rva - va + ro
        raise ValueError(hex(rva))

    eo = r2o(exp_rva)
    nfun, nnames, afun, anames, aord = struct.unpack_from("<IIIII", d, eo + 20)
    for i in range(nnames):
        so = r2o(struct.unpack_from("<I", d, r2o(anames) + 4 * i)[0])
        if d[so:d.index(b"\0", so)].decode() == name:
            ordi = struct.unpack_from("<H", d, r2o(aord) + 2 * i)[0]
            rva = struct.unpack_from("<I", d, r2o(afun) + 4 * ordi)[0]
            if exp_rva <= rva < exp_rva + exp_sz:
                raise ValueError(name + " is a forwarder")
            return rva
    raise KeyError(name)


def inject(pid, dll_path, timeout=15):
    dll_path = os.path.abspath(dll_path)
    h = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        raise OSError("OpenProcess failed %d" % ctypes.get_last_error())
    try:
        t0 = time.time()
        k32 = None
        while time.time() - t0 < timeout:
            mods = _modules32(h)
            k32 = next((b for p, b in mods.items() if p.endswith("\\kernel32.dll")), None)
            if k32:
                if any(p.endswith("\\aoehook.dll") for p in mods):
                    return True
                break
            time.sleep(0.2)
        if not k32:
            raise OSError("kernel32 not found in target")
        sysk32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", "kernel32.dll")
        load_library = k32 + _export_rva(sysk32, "LoadLibraryA")
        raw = dll_path.encode("mbcs") + b"\0"
        mem = kernel32.VirtualAllocEx(h, None, len(raw), MEM_COMMIT_RESERVE, PAGE_READWRITE)
        kernel32.WriteProcessMemory(h, mem, raw, len(raw), None)
        th = kernel32.CreateRemoteThread(h, None, 0, load_library, mem, 0, None)
        if not th:
            raise OSError("CreateRemoteThread failed %d" % ctypes.get_last_error())
        kernel32.WaitForSingleObject(th, 10000)
        code = wt.DWORD()
        kernel32.GetExitCodeThread(th, ctypes.byref(code))
        kernel32.CloseHandle(th)
        if not code.value:
            raise OSError("LoadLibraryA returned NULL in target")
        return True
    finally:
        kernel32.CloseHandle(h)


class Hook:
    """Client for the aoehook pipe of one game process."""

    def __init__(self, pid, timeout=10):
        self.pid = pid
        name = r"\\.\pipe\aoehook_%d" % pid
        t0 = time.time()
        while True:
            try:
                self.f = open(name, "r+b", buffering=0)
                break
            except OSError:
                if time.time() - t0 > timeout:
                    raise
                time.sleep(0.2)

    def cmd(self, line):
        self.f.write((line + "\n").encode())
        out = b""
        while not out.endswith(b"\n"):
            ch = self.f.read(1)
            if not ch:
                raise EOFError("pipe closed")
            out += ch
        return out.decode().strip()

    def click(self, x, y, button="l"):
        return self.cmd("click %d %d %s" % (x, y, button))

    def tap(self, vk):
        return self.cmd("tap %d" % vk)

    def type_text(self, text):
        for ch in text:
            self.cmd("char %d" % ord(ch))

    def call(self, conv, addr, *args):
        r = self.cmd(" ".join([conv, hex(addr)] + [hex(a & 0xFFFFFFFF) for a in args]))
        if not r.startswith("ok"):
            raise RuntimeError(r)
        return int(r.split()[1])

    def close(self):
        try:
            self.f.close()
        except OSError:
            pass


class Mem:
    """Read/write memory of a 32-bit game process."""

    def __init__(self, pid):
        self.h = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not self.h:
            raise OSError("OpenProcess failed")

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
            return None
        return buf.raw[: got.value]

    def write(self, addr, data):
        return bool(kernel32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), data, len(data), None))

    def u32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<I", b)[0] if b and len(b) == 4 else None

    def i32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<i", b)[0] if b and len(b) == 4 else None

    def u16(self, addr):
        b = self.read(addr, 2)
        return struct.unpack("<H", b)[0] if b and len(b) == 2 else None

    def u8(self, addr):
        b = self.read(addr, 1)
        return b[0] if b else None

    def f32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<f", b)[0] if b and len(b) == 4 else None

    def cstr(self, addr, n=64):
        b = self.read(addr, n)
        return b.split(b"\0")[0].decode("latin-1") if b else None

    def close(self):
        kernel32.CloseHandle(self.h)
