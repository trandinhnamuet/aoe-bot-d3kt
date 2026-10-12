"""Hidden-only: does the client's civ/team reach the host when sent with Ready?"""
import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby
L=print
pool=orchestrator.BotPool(r'D:\Game\AoE-HD', r'D:\Game\AoESolo\hook\aoehook.dll', log=lambda m: None)
pool.ensure(2)
t0=time.time()
while len(pool.parked)<2 and time.time()-t0<90: time.sleep(0.5)
host=procs.start(r'D:\Game\AoE-HD','AOEBOT.EXE',r'D:\Game\AoESolo\hook\aoehook.dll',True,job=True)
try:
    lobby.host_create(host, log=L)
    bots=pool.take(2)
    for k,b in enumerate(bots):
        lobby.join_from_list(b, log=L)
        t1=time.time()
        while lobby.present_players(host)<k+2 and time.time()-t1<5: time.sleep(0.2)
    time.sleep(1)
    def dump(gp, tag):
        scr=gp.mem.u32(lobby.ADDR_SCREEN)
        print(tag, 'fields', [gp.mem.u32(scr+o) for o in (0x72c,0x730,0x734,0x738,0x73c)])
    for k,b in enumerate(bots):
        slot=lobby.my_player_number(b)-1
        dump(b,'bot%d before slot=%d'%(k,slot))
        print(' host sees civ %s team %s'%(lobby.slot_civ(host,slot), lobby.slot_team(host,slot)))
        civ, team = (6, 2) if k==0 else (17, 2)
        scr=b.mem.u32(lobby.ADDR_SCREEN)
        lobby.host_set_civ(b, slot, civ, log=L); lobby.host_set_team(b, slot, team, log=L)
        b.mem.write(scr+0x72c, civ.to_bytes(4,'little')); b.mem.write(scr+0x738, (team+1).to_bytes(4,'little'))
        dump(b,' after write')
        t1=time.time()
        lobby.ready(b, False)
        for i in range(20):
            if lobby.slot_civ(host,slot)==civ and lobby.slot_team(host,slot)==team+1: break
            time.sleep(0.1)
        print(' after ready %.1fs: host sees civ %s team %s ; bot local civ %s team %s'%(time.time()-t1,
              lobby.slot_civ(host,slot), lobby.slot_team(host,slot), lobby.slot_civ(b,slot), lobby.slot_team(b,slot)))
        dump(b,' after ready')
    print('host all civs', [lobby.slot_civ(host,s) for s in range(4)], 'teams', [lobby.slot_team(host,s) for s in range(4)])
finally:
    for b in pool.parked + bots: b.kill()
    host.kill(); pool.shutdown()
