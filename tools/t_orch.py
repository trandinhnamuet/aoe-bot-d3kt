import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, aoemem
log=open(r'D:\Game\AoESolo\tools\orch.log','w',encoding='utf-8')
def L(m): log.write(m+'\n'); log.flush()
cfg=orchestrator.Config(); cfg.num_ai=int(sys.argv[1]) if len(sys.argv)>1 else 2; cfg.map_size='Small'; cfg.map_type='Inland'
cfg.player_civ=13; cfg.ai_civs=[0,5,0,0,0,0,0]
s=orchestrator.Session(r'D:\Game\AoESolo', cfg, log=L, status=lambda m: L('STATUS '+m), dll=r'D:\Game\AoESolo\hook\aoehook.dll')
s.game_dir=r'D:\Game\AoE-HD'
s.test_hidden_player=True
s.run()
g=aoemem.Game(s.player.mem, s.player.hook)
L('names: %s'%[g.player_name(i) for i in range(len(g.players()))])
open(r'D:\Game\AoESolo\tools\orch_pids.txt','w').write(' '.join(str(b.pid) for b in s.bots+[s.player]))
time.sleep(float(sys.argv[2]) if len(sys.argv)>2 else 120)
s.shutdown(); s.player.kill(); L('done')
