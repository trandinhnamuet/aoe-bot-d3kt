"""Hidden-only: find the Join Screen's session list count. Show with 0 rooms, 1 room, then with a
killed room + a live room."""
import sys, time, struct
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby
L=print
GD=r'D:\Game\AoE-HD'; DLL=r'D:\Game\AoESolo\hook\aoehook.dll'
pool=orchestrator.BotPool(GD, DLL, log=lambda m: None)
pool.ensure(1)
t0=time.time()
while len(pool.parked)<1 and time.time()-t0<90: time.sleep(0.5)
b=pool.take(1)[0]
def snap():
    scr=b.mem.u32(lobby.ADDR_SCREEN)
    words=struct.unpack('<512I', b.mem.read(scr,2048))
    kids={}
    for i,w in enumerate(words):
        if 0x01000000 < w < 0x7f000000:
            d=b.mem.read(w,0x300)
            if d and len(d)==0x300: kids[i*4]=struct.unpack('<192I',d)
    return words,kids
def show(tag):
    b.hook.click(*lobby.GAMES_SHOW); time.sleep(0.3)
    return snap()
s0=show('none')
h1=procs.start(GD,'AOEBOT.EXE',DLL,True,job=True); lobby.host_create(h1,log=L)
s1=show('one')
def diff(a,b_,tag):
    out=[]
    for i,(x,y) in enumerate(zip(a[0],b_[0])):
        if x!=y and x<50 and y<50: out.append(('scr+%x'%(i*4),x,y))
    for off in a[1]:
        if off in b_[1]:
            for j,(x,y) in enumerate(zip(a[1][off],b_[1][off])):
                if x!=y and x<50 and y<50: out.append(('[scr+%x]+%x'%(off,j*4),x,y))
    print(tag, out[:60])
diff(s0,s1,'none->one')
h1.kill(); time.sleep(1)
h2=procs.start(GD,'AOEBOT.EXE',DLL,True,job=True); lobby.host_create(h2,log=L)
s2=show('dead+live')
diff(s1,s2,'one->dead+live')
s3=show('again'); time.sleep(3); s4=show('later')
diff(s1,s4,'one->later')
lobby._click(b, lobby.GAMES_FIRST_ROW, 0.05); lobby._click(b, lobby.GAMES_JOIN, 0)
print('first-row join ->', lobby.wait_screen(b,'MP Setup Screen',4,poll=0.05), lobby.current_screen(b))
b.kill(); h2.kill(); pool.shutdown()
