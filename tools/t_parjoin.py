"""Hidden-only: parallel Show + staggered joins. python t_parjoin.py n stagger"""
import sys, time, threading
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby
n=int(sys.argv[1]); stg=float(sys.argv[2])
T0=time.time()
L=lambda m: print('%6.2f %s'%(time.time()-T0, m))
pool=orchestrator.BotPool(r'D:\Game\AoE-HD', r'D:\Game\AoESolo\hook\aoehook.dll', log=lambda m: None)
pool.ensure(n)
while len(pool.parked)<n and time.time()-T0<120: time.sleep(0.5)
host=procs.start(r'D:\Game\AoE-HD','AOEBOT.EXE',r'D:\Game\AoESolo\hook\aoehook.dll',True,job=True)
bots=[]
try:
    lobby.host_create(host, log=L)
    bots=pool.take(n)
    t=time.time()
    def show(b): b.hook.click(*lobby.GAMES_SHOW)
    ths=[threading.Thread(target=show,args=(b,)) for b in bots]; [x.start() for x in ths]; [x.join() for x in ths]
    L('all shown %.2f'%(time.time()-t))
    def join(b, k):
        time.sleep(k*stg)
        tj=time.time(); b.hook.click(*lobby.GAMES_FIRST_ROW); time.sleep(0.05); b.hook.click(*lobby.GAMES_JOIN)
        lobby.wait_screen(b,"MP Setup Screen",5,poll=0.05)
        L('bot%d screen %s (join %.2f s)'%(k,lobby.current_screen(b),time.time()-tj))
    ths=[threading.Thread(target=join,args=(b,k)) for k,b in enumerate(bots)]; [x.start() for x in ths]; [x.join() for x in ths]
    while lobby.present_players(host)<n+1 and time.time()-t<10: time.sleep(0.05)
    L('host present %d after %.2f s ; states %s'%(lobby.present_players(host), time.time()-t, lobby.session_states(host)))
    import gamewin as gw
    SH = r"C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad"
    for k, b in enumerate(bots):
        if lobby.current_screen(b) != 'MP Setup Screen':
            L('bot%d stuck on %s; windows %s' % (k, lobby.current_screen(b), gw.windows_of_pid(b.pid, False)))
            L('alive %s popups %s' % (b.alive(), lobby.open_popups(b)))
            for vk in (13, 27):
                b.hook.tap(vk); time.sleep(0.3)
                L('after vk %d: popups %s screen %s' % (vk, lobby.open_popups(b), lobby.current_screen(b)))
            try:
                tr=time.time(); lobby.reopen_list(b, log=L); L('reopened list %.2f s, screen %s' % (time.time()-tr, lobby.current_screen(b)))
            except Exception as e: L('reopen %r' % e)
            try: lobby.join_from_list(b, log=L, retries=2)
            except Exception as e: L('rejoin %r' % e)
    time.sleep(2); L('2s later present %d, bot numbers %s'%(lobby.present_players(host), [lobby.my_player_number(b) for b in bots]))
finally:
    for b in pool.parked + bots: b.kill()
    host.kill(); pool.shutdown()
