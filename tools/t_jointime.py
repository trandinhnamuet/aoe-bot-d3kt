"""Hidden-only: time each phase of a bot join."""
import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby
L=print
pool=orchestrator.BotPool(r'D:\Game\AoE-HD', r'D:\Game\AoESolo\hook\aoehook.dll', log=lambda m: None)
pool.ensure(2)
t0=time.time()
while len(pool.parked)<2 and time.time()-t0<90: time.sleep(0.5)
host=procs.start(r'D:\Game\AoE-HD','AOEBOT.EXE',r'D:\Game\AoESolo\hook\aoehook.dll',True,job=True)
bots=[]
try:
    bots=pool.take(2)
    import struct
    for b in bots:
        assert b.mem.read(0x428f62,5)==bytes([0x68,0xa0,0x0f,0,0]), b.mem.read(0x428f62,5)
        print('patch', b.mem.write(0x428f63, struct.pack('<I',400)), b.mem.read(0x428f62,5).hex())
    lobby.host_create(host, log=L); th=time.time()
    for k,b in enumerate(bots):
        t=time.time(); b.hook.click(*lobby.GAMES_SHOW); tc=time.time()-t
        r=b.hook.cmd("ping"); tp=time.time()-t
        print('bot%d show click returned %.2f s, ping %.2f s (%s)'%(k,tc,tp,r))
        for w in (0.2,0.4,0.6,0.8,1.0,1.5,2.0):
            lobby._click(b, lobby.GAMES_FIRST_ROW, 0.05); lobby._click(b, lobby.GAMES_JOIN, 0)
            t2=time.time()
            while lobby.current_screen(b)!='MP Setup Screen' and time.time()-t2<w: time.sleep(0.05)
            if lobby.current_screen(b)=='MP Setup Screen': break
        print('   joined=%s %.2f s after Show'%(lobby.current_screen(b),time.time()-t))
        time.sleep(1.5); print('   later', lobby.current_screen(b), lobby.present_players(host))
finally:
    for b in pool.parked + bots: b.kill()
    host.kill(); pool.shutdown()
