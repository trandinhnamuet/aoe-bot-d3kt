import sys, collections
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import inject, aoemem, gamestate as gs
pid=int(open(sys.argv[1]).read()); me=int(sys.argv[2])
g=aoemem.Game(inject.Mem(pid), inject.Hook(pid))
r=gs.Reader(g,me); r.load_map()
s=gs.Snapshot(r,set())
print('game time %.0fs  age %d  res food %.0f wood %.0f gold %.0f stone %.0f headroom %.0f'%(s.time/1000, s.res[6], s.res[0], s.res[1], s.res[3], s.res[2], s.res[4]))
c=collections.Counter((o.name, o.state) for o in s.mine)
print(sorted(c.items()))
idle=[v for v in s.villagers if r.action(v) is None]
print('villagers', len(s.villagers), 'idle', len(idle), [ (v.name, round(v.x),round(v.y)) for v in idle][:8])
