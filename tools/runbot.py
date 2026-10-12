import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import inject, aoemem, d3kt
pid=int(open(sys.argv[1]).read()); me=int(sys.argv[2]); enemies=[int(x) for x in sys.argv[3].split(',')]
dur=float(sys.argv[4]) if len(sys.argv)>4 else 600
logf=open(sys.argv[5] if len(sys.argv)>5 else 'bot.log','w',encoding='utf-8')
def log(m):
    logf.write(m+'\n'); logf.flush()
g=aoemem.Game(inject.Mem(pid), inject.Hook(pid))
t0=time.time()
d3kt.run(g, me, enemies, log=log, stop=lambda: time.time()-t0>dur)
log('runner finished')
