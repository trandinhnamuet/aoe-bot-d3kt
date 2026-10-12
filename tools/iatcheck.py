import sys, ctypes, struct, os
import ctypes.wintypes as wt
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw, inject
pid=int(open('probe.pid').read()); hwnd=gw.main_window(pid,5)
u=ctypes.windll.user32
u.GetClassLongW.restype=ctypes.c_uint32; u.GetWindowLongW.restype=ctypes.c_uint32
cp=u.GetClassLongW(hwnd,-24); wp=u.GetWindowLongW(hwnd,-4)
h=inject.kernel32.OpenProcess(0x1F0FFF,False,pid)
mods=inject._modules32(h)
class MI(ctypes.Structure): _fields_=[('base',ctypes.c_void_p),('size',wt.DWORD),('entry',ctypes.c_void_p)]
inject.psapi.GetModuleInformation.argtypes=[wt.HANDLE,ctypes.c_void_p,ctypes.POINTER(MI),wt.DWORD]
ranges=[]
for name,b in mods.items():
    mi=MI(); inject.psapi.GetModuleInformation(h,b,ctypes.byref(mi),ctypes.sizeof(mi)); ranges.append((mi.base,mi.size,os.path.basename(name)))
def where(a):
    for b,s,n in ranges:
        if b<=a<b+s: return n
    return '?'
print('classproc',hex(cp),where(cp),'windowproc',hex(wp),where(wp))
m=inject.Mem(pid)
d=open(r'D:\Game\AoE-HD\EMPIRESX.EXE','rb').read()
pe=struct.unpack_from('<I',d,0x3c)[0]; nsec=struct.unpack_from('<H',d,pe+6)[0]; optsz=struct.unpack_from('<H',d,pe+20)[0]
opt=pe+24; imp_rva,_=struct.unpack_from('<II',d,opt+96+8); so=opt+optsz
secs=[struct.unpack_from('<8sIIII',d,so+i*40) for i in range(nsec)]
def r2o(rva):
    for n,vs,va,rs,ro in secs:
        if va<=rva<va+max(vs,rs): return rva-va+ro
o=r2o(imp_rva)
want=set(sys.argv[1:]) or {'GetCursorPos','PeekMessageA','GetMessageA','GetAsyncKeyState','GetForegroundWindow','DispatchMessageA','SetCursorPos','GetKeyState'}
while True:
    ilt,ts,fc,name,iat=struct.unpack_from('<IIIII',d,o)
    if name==0: break
    no=r2o(name); dll=d[no:d.index(b'\0',no)].decode()
    t=r2o(ilt or iat); k=0
    while True:
        v=struct.unpack_from('<I',d,t)[0]
        if v==0: break
        if not v&0x80000000:
            fo=r2o(v)+2; fn=d[fo:d.index(b'\0',fo)].decode()
            if fn in want:
                val=m.u32(0x400000+iat+4*k); print(dll,fn,'iat@',hex(0x400000+iat+4*k),'->',hex(val),where(val))
        t+=4;k+=1
    o+=20
