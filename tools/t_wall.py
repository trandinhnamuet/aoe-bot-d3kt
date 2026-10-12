import sys, time, math
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import inject, aoemem, gamestate as gs, pathing, walling
pid=int(open(r'D:\Game\AoESolo\tools\probe.pid').read())
g=aoemem.Game(inject.Mem(pid), inject.Hook(pid))
r=gs.Reader(g,1); r.load_map()
# reveal-like test: use full explored? just current knowledge
s=gs.Snapshot(r,set())
tc=[o for o in s.mine if o.type==109][0]
t0=time.time(); pm=pathing.PassMap(s); t1=time.time()
d=pm.bfs([(int(tc.x),int(tc.y))]); t2=time.time()
print('passmap %.0f ms, bfs %.0f ms'%((t1-t0)*1000,(t2-t1)*1000))
gate=( (tc.x-r.W/2), (tc.y-r.H/2) ); n=math.hypot(*gate) or 1; gate=(gate[0]/n,gate[1]/n)
for R in (8,10,12,14,16):
    t0=time.time(); p=walling.plan(pm,[(tc.x,tc.y)],R,gate,keep_clear=[(tc.x,tc.y,6.5)]); print(R,p,'%.0f ms'%((time.time()-t0)*1000))
p=walling.plan(pm,[(tc.x,tc.y)],12,gate,keep_clear=[(tc.x,tc.y,6.5)])
slot={}
for i,(x0,y0,sz) in enumerate(p.slots):
    for yy in range(y0,y0+sz):
        for xx in range(x0,x0+sz): slot[(xx,yy)]=chr(ord('a')+i%26)
cx,cy=int(tc.x),int(tc.y)
for yy in range(cy-16,cy+17):
    row=''
    for xx in range(cx-16,cx+17):
        if (xx,yy)==p.gate: ch='G'
        elif (xx,yy) in slot: ch=slot[(xx,yy)]
        elif abs(xx-tc.x)<1.6 and abs(yy-tc.y)<1.6: ch='T'
        elif not s.explored(xx,yy): ch=' '
        elif not pm.passable(xx,yy): ch='#'
        else: ch='.'
        row+=ch
    print(row)
