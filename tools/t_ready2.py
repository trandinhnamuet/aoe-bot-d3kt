import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher'); sys.path.insert(0, '.')
import procs, lobby, snapdiff
GAME=r'D:\Game\AoE-HD'; DLL=r'D:\Game\AoESolo\hook\aoehook.dll'
host=procs.start(GAME,'AOEBOT.EXE',DLL,True,job=False); lobby.host_create(host)
c=procs.start(GAME,'AOEBOT.EXE',DLL,True,job=False); lobby.client_join(c)
open('ready_pids.txt','w').write('%d %d'%(host.pid,c.pid))
time.sleep(2)
s0=snapdiff.snap(c.mem); lobby.ready(c,False); time.sleep(2)
s1=snapdiff.snap(c.mem); lobby.ready(c,False); time.sleep(2)
s2=snapdiff.snap(c.mem); lobby.ready(c,False); time.sleep(2)
s3=snapdiff.snap(c.mem)
a=snapdiff.diff(s0,s1,0,1)&snapdiff.diff(s1,s2,1,0)&snapdiff.diff(s2,s3,0,1)
print('client ready flag candidates', [hex(x) for x in sorted(a)][:30])
g=c.mem.u32(lobby.ADDR_GAME); cm=c.mem.u32(lobby.ADDR_COMM)
for x in sorted(a)[:30]:
    print(hex(x), 'game+%x'%(x-g) if 0<=x-g<0x4000 else '', 'comm+%x'%(x-cm) if 0<=x-cm<0x4000 else '')
