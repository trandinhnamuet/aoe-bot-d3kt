import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby
L=print
pool=orchestrator.BotPool(r'D:\Game\AoE-HD', r'D:\Game\AoESolo\hook\aoehook.dll', log=L)
pool.ensure(2)
t0=time.time()
while len(pool.parked)<2 and time.time()-t0<90: time.sleep(0.5)
print('parked', len(pool.parked), [lobby.current_screen(b) for b in pool.parked])
host=procs.start(r'D:\Game\AoE-HD','AOEBOT.EXE',r'D:\Game\AoESolo\hook\aoehook.dll',True,job=True)
lobby.host_create(host, log=L)
print('host states', lobby.session_states(host))
bots=pool.take(2)
for b in bots:
    try:
        lobby.join_from_list(b, log=L)
    except Exception as e: print('join error', e)
    print('after join: bot screen', lobby.current_screen(b), 'bot states', lobby.session_states(b), 'host states', lobby.session_states(host), 'present', lobby.present_players(host))
time.sleep(3)
print('final host present', lobby.present_players(host), lobby.session_states(host))
for b in bots: b.kill()
host.kill(); pool.shutdown()
