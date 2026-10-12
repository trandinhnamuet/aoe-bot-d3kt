import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import procs, lobby
GAME=r'D:\Game\AoE-HD'; DLL=r'D:\Game\AoESolo\hook\aoehook.dll'
host=procs.start(GAME,'AOEBOT.EXE',DLL,True,job=False); time.sleep(1.5); lobby.host_create(host)
c=procs.start(GAME,'AOEBOT.EXE',DLL,True,job=False); time.sleep(1.5); lobby.client_join(c)
open('ready_pids.txt','w').write('%d %d'%(host.pid,c.pid))
def rd(gp): g=gp.mem.u32(lobby.ADDR_GAME); return gp.mem.read(g,0x2000)
a_h=rd(host); a_c=rd(c)
lobby.ready(c, False); time.sleep(1.5)
b_h=rd(host); b_c=rd(c)
lobby.ready(c, False); time.sleep(1.5)
c_h=rd(host); c_c=rd(c)
for name,(a,b,cc) in (('host',(a_h,b_h,c_h)),('client',(a_c,b_c,c_c))):
    for i in range(0x2000):
        if a[i]!=b[i] and b[i]!=cc[i] and a[i]==cc[i]: print(name,'game+%x: %d -> ready %d -> unready %d'%(i,a[i],b[i],cc[i]))
lobby.ready(c, False); time.sleep(1); lobby.ready(host, True); time.sleep(1)
d_h=rd(host)
for i in range(0x2000):
    if c_h[i]!=d_h[i]: print('host after both ready: game+%x %d -> %d'%(i,c_h[i],d_h[i]))
