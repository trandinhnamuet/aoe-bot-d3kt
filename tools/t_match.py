"""Bot-vs-bot multiplayer test: python t_match.py <minutes> [map_type] [map_size]"""
import sys, time, threading
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import procs, lobby, aoemem, d3kt
GAME=r'D:\Game\AoE-HD'; DLL=r'D:\Game\AoESolo\hook\aoehook.dll'
mins=float(sys.argv[1]) if len(sys.argv)>1 else 10
mtype=sys.argv[2] if len(sys.argv)>2 else 'Highland'
msize=sys.argv[3] if len(sys.argv)>3 else 'Small'
log=open(r'D:\Game\AoESolo\tools\match.log','w',encoding='utf-8')
lk=threading.Lock()
def L(m):
    with lk: log.write(m+'\n'); log.flush()
lobby.write_settings(GAME, map_size=msize, map_type=mtype, pop_limit=50)
host=procs.start(GAME,'AOEBOT.EXE',DLL,True,log=L,job=False); time.sleep(2)
lobby.host_create(host,log=L)
c=procs.start(GAME,'AOEBOT.EXE',DLL,True,log=L,job=False); time.sleep(2)
slot=lobby.client_join(c,log=L)-1
lobby.choose_civ(host,0,10,log=L); lobby.choose_civ(c,slot,4,log=L)
lobby.ready(c,False); lobby.ready(host,True)
lobby.start_match(host,2,log=L)
open(r'D:\Game\AoESolo\tools\pids.txt','w').write('%d %d'%(host.pid,c.pid))
time.sleep(5)
t0=time.time(); stop=lambda: time.time()-t0>mins*60
ths=[]
for gp in (host,c):
    me=lobby.my_player_number(gp)
    g=aoemem.Game(gp.mem,gp.hook)
    en=[1,2]; en.remove(me)
    th=threading.Thread(target=d3kt.run,args=(g,me,en),kwargs=dict(log=L,stop=stop,pop_limit=50),daemon=True)
    th.start(); ths.append(th)
for th in ths: th.join()
L('test finished')
