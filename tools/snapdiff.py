import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import inject, memscan
def snap(m):
    out={}
    for b,s in memscan.regions(m):
        if s>64*1024*1024: continue
        r=m.read(b,s)
        if r: out[b]=r
    return out
def diff(a,b,frm,to):
    res=set()
    for base,ra in a.items():
        rb=b.get(base)
        if not rb or len(rb)!=len(ra) or ra==rb: continue
        for i in range(len(ra)):
            if ra[i]==frm and rb[i]==to: res.add(base+i)
    return res
