"""Memory scanning helpers for a 32-bit game process."""
import ctypes, ctypes.wintypes as wt, struct, sys, re
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import inject

k32 = inject.kernel32


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_uint64), ('AllocationBase', ctypes.c_uint64), ('AllocationProtect', wt.DWORD),
                ('__a1', wt.DWORD), ('RegionSize', ctypes.c_uint64), ('State', wt.DWORD), ('Protect', wt.DWORD),
                ('Type', wt.DWORD), ('__a2', wt.DWORD)]


k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t


def regions(mem, writable_only=True):
    addr = 0x10000
    out = []
    while addr < 0x7FFF0000:
        mbi = MBI()
        if not k32.VirtualQueryEx(mem.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress, mbi.RegionSize
        prot = mbi.Protect
        ok = mbi.State == 0x1000 and not (prot & 0x100) and not (prot & 0x01)
        if writable_only:
            ok = ok and (prot & (0x04 | 0x08 | 0x40 | 0x80))
        if ok:
            out.append((base, size))
        addr = base + size
    return out


def scan(mem, pattern, writable_only=True, maxhits=200, align=1):
    hits = []
    pat = re.compile(re.escape(pattern)) if isinstance(pattern, bytes) else pattern
    for base, size in regions(mem, writable_only):
        data = mem.read(base, size)
        if not data:
            continue
        for m in pat.finditer(data):
            if m.start() % align == 0:
                hits.append(base + m.start())
                if len(hits) >= maxhits:
                    return hits
    return hits


def find_ptrs(mem, value, writable_only=False, maxhits=200):
    return scan(mem, struct.pack('<I', value), writable_only, maxhits, align=4)
