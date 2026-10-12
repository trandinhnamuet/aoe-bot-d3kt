"""Hidden-only full Session.run timing (player = hidden AOEBOT host). python t_fastsetup.py [n]"""
import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, lobby
n=int(sys.argv[1]) if len(sys.argv)>1 else 3
T0=time.time()
L=lambda m: print('%6.2f %s'%(time.time()-T0, m))
pool=orchestrator.BotPool(r'D:\Game\AoE-HD', r'D:\Game\AoESolo\hook\aoehook.dll', log=lambda m: None)
pool.ensure(n)
while len(pool.parked)<n and time.time()-T0<120: time.sleep(0.5)
L('parked %d'%len(pool.parked))
cfg=orchestrator.Config(); cfg.num_ai=n; cfg.player_civ=13; cfg.ai_civs=[0,5,9,0,0,0,0]; cfg.ai_team_mode='together'
s=orchestrator.Session(r"D:\Game\AoESolo", cfg, log=L, status=lambda m: None, dll=r"D:\Game\AoESolo\hook\aoehook.dll",
                       dplaunch=r"D:\Game\AoESolo\hook\dplaunch.exe", pool=pool)
s.game_dir=r"D:\Game\AoE-HD"; s.test_hidden_player=True
import struct
_bad = pool.parked[0]
_orig = lobby.join_from_list
def _join(gp, log=print, retries=8):
    if gp is _bad:
        time.sleep(1); raise RuntimeError("sabotaged: could not join")
    return _orig(gp, log, retries)
lobby.join_from_list = _join
L("sabotaged %s" % _bad.bot_name)
try:
    t=time.time(); s.run(); L('RUN %.1f s'%(time.time()-t))
    pl=s.player
    L('host civs %s teams %s'%([lobby.slot_civ(pl,i) for i in range(n+1)],[lobby.slot_team(pl,i) for i in range(n+1)]))
finally:
    s.shutdown(); pool.shutdown()
    if s.player: s.player.kill()
