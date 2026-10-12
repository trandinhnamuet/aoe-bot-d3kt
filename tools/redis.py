import sys, struct, re
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
EXE = r'D:\Game\AoE-HD\EMPIRESX.EXE'
d = open(EXE, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3c)[0]; nsec = struct.unpack_from('<H', d, pe+6)[0]; optsz = struct.unpack_from('<H', d, pe+20)[0]
opt = pe+24; BASE = struct.unpack_from('<I', d, opt+28)[0]
imp_rva, _ = struct.unpack_from('<II', d, opt+96+8); so = opt+optsz
secs = [struct.unpack_from('<8sIIII', d, so+i*40) for i in range(nsec)]
def r2o(rva):
    for n, vs, va, rs, ro in secs:
        if va <= rva < va+max(vs, rs): return rva-va+ro
def va2o(va): return r2o(va-BASE)
def o2va(o):
    for n, vs, va, rs, ro in secs:
        if ro <= o < ro+rs: return o-ro+va+BASE
IAT = {}
o = r2o(imp_rva)
while True:
    ilt, ts, fc, name, iat = struct.unpack_from('<IIIII', d, o)
    if name == 0: break
    no = r2o(name); dll = d[no:d.index(b'\0', no)].decode()
    t = r2o(ilt or iat); k = 0
    while True:
        v = struct.unpack_from('<I', d, t)[0]
        if v == 0: break
        if not v & 0x80000000:
            fo = r2o(v)+2; IAT[BASE+iat+4*k] = d[fo:d.index(b'\0', fo)].decode()
        else:
            IAT[BASE+iat+4*k] = '%s#%d' % (dll, v & 0xffff)
        t += 4; k += 1
    o += 20
md = Cs(CS_ARCH_X86, CS_MODE_32)
def sstr(va):
    off = va2o(va)
    if off is None: return None
    s = d[off:off+80].split(b'\0')[0]
    if len(s) >= 3 and all(32 <= c < 127 or c in (9, 10, 13) for c in s): return s.decode()
def annotate(ins):
    t = ins.op_str
    for m in re.finditer(r'0x[0-9a-f]+', t):
        v = int(m.group(), 16)
        if v in IAT: return ' ; ' + IAT[v]
        s = sstr(v)
        if s: return ' ; "%s"' % s[:60]
    return ''
def dis(va, n=60, out=True):
    off = va2o(va); res = []
    for ins in md.disasm(d[off:off+n*8], va):
        line = '%08x  %-8s %s%s' % (ins.address, ins.mnemonic, ins.op_str, annotate(ins))
        res.append((ins, line))
        if out: print(line)
        if len(res) >= n: break
    return res
def calls_to(name):
    addr = [a for a, n in IAT.items() if n == name]
    out = []
    for a in addr:
        for pat in (b'\xff\x15' + struct.pack('<I', a), b'\x8b\x35' + struct.pack('<I', a), b'\x8b\x3d' + struct.pack('<I', a), b'\x8b\x1d' + struct.pack('<I', a), b'\xa1' + struct.pack('<I', a)):
            for m in re.finditer(re.escape(pat), d):
                out.append(o2va(m.start()))
    return sorted(out)
def xrefs_imm(va):
    """Find code locations referencing an absolute address (push/mov imm32)."""
    return sorted(o2va(m.start()) for m in re.finditer(re.escape(struct.pack('<I', va)), d))
def calls_target(target):
    """Find E8 rel32 calls to target."""
    res = []
    text = [s for s in secs if s[0].startswith(b'.text')][0]
    _, vs, va, rs, ro = text
    blob = d[ro:ro+rs]
    for m in re.finditer(b'\xe8', blob):
        i = m.start()
        if i+5 > len(blob): continue
        rel = struct.unpack_from('<i', blob, i+1)[0]
        src = BASE+va+i
        if src+5+rel == target: res.append(src)
    return res
def find_func_start(va, back=0x2000):
    """Heuristic: scan backwards for a function prologue preceded by padding."""
    off = va2o(va)
    for i in range(off, off-back, -1):
        if d[i-1] in (0x90, 0xCC, 0xC3) and d[i:i+1] in (b'\x55', b'\x83', b'\x81', b'\x53', b'\x56', b'\x57', b'\x6a', b'\x64', b'\x8b', b'\xa1', b'\x51'):
            if d[i-1] in (0x90, 0xCC) or (d[i-1] == 0xC3):
                return o2va(i)
    return None
if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'calls':
        for n in sys.argv[2:]: print(n, [hex(x) for x in calls_to(n)])
    elif cmd == 'dis':
        dis(int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 60)
    elif cmd == 'str':
        for s in sys.argv[2:]:
            for m in re.finditer(re.escape(s.encode()), d):
                va = o2va(m.start()); print(repr(s), hex(va), 'refs', [hex(x) for x in xrefs_imm(va)][:10])
    elif cmd == 'callers':
        print([hex(x) for x in calls_target(int(sys.argv[2], 16))])
