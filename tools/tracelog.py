"""Read aoehook trace records. Usage: tracelog.py [pidfile] [last N]"""
import sys, struct
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import inject
pidfile = sys.argv[1] if len(sys.argv) > 1 else 'probe.pid'
last = int(sys.argv[2]) if len(sys.argv) > 2 else 10
pid = int(open(pidfile).read())
h = inject.Hook(pid); m = inject.Mem(pid)
info = dict(kv.split('=') for kv in h.cmd('traceinfo').split()[1:])
buf, n, cap, rs = int(info['buf']), int(info['n']), int(info['cap']), int(info['recsize'])
print('records', n)
def in_exe(v): return 0x401000 <= v < 0x54b000
for i in range(max(0, n - last), n):
    raw = m.read(buf + (i % cap) * rs, rs)
    w = struct.unpack('<%dI' % (rs // 4), raw)
    fn, edi, esi, ebp, esp, ebx, edx, ecx, eax, efl = w[:10]
    st = w[10:]
    rets = [hex(v) for v in st if in_exe(v)]
    print('#%d fn=%x ecx=%x ret=%x args=%s' % (i, fn, ecx, st[0], ' '.join('%x' % a for a in st[1:7])))
    print('   exe addrs on stack:', rets[:16])
