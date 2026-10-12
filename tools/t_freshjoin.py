"""Hidden-only: host first, then bots join the moment they park. python t_freshjoin.py n"""
import sys, time, threading
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby
n=int(sys.argv[1])
T0=time.time()
L=lambda m: print('%6.2f %s'%(time.time()-T0, m), flush=True)
host=procs.start(r'D:\Game\AoE-HD','AOEBOT.EXE',r'D:\Game\AoESolo\hook\aoehook.dll',True,job=True)
lobby.host_create(host, log=L)
pool=orchestrator.BotPool(r'D:\Game\AoE-HD', r'D:\Game\AoESolo\hook\aoehook.dll', log=lambda m: None)
pool.ensure(n)
bots=[]; res={}
def join(b):
    try: lobby.join_from_list(b, log=lambda m: None, retries=2); res[b.bot_name]='ok'
    except Exception as e: res[b.bot_name]=repr(e)
ths=[]
try:
    while len(bots)<n and time.time()-T0<120:
        b=pool.take(1)[0]; bots.append(b); L('%s parked -> join now'%b.bot_name)
        th=threading.Thread(target=join,args=(b,)); th.start(); ths.append(th)
    [t.join(30) for t in ths]
    L('results %s present %d'%(res, lobby.present_players(host)))
    for b in bots:
        if lobby.current_screen(b)!='MP Setup Screen':
            L('STUCK %s screen %s popups %s states %s'%(b.bot_name, lobby.current_screen(b), lobby.open_popups(b), lobby.session_states(b)))
finally:
    for b in pool.parked+bots: b.kill()
    host.kill(); pool.shutdown()
