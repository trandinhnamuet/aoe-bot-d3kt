import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, procs, lobby, dplobby
L=print
GD=r'D:\Game\AoE-HD'
print('registered for dist:', dplobby.is_registered(GD))
pool=orchestrator.BotPool(GD, r'D:\Game\AoESolo\hook\aoehook.dll', log=L)
pool.ensure(1)
t0=time.time()
while len(pool.parked)<1 and time.time()-t0<90: time.sleep(0.5)
ps,_=dplobby.launch_host(r'D:\Game\AoESolo\hook\dplaunch.exe', GD, 'TranKhoaCu', 'AoESolo', log=L)
pl=procs.attach(ps, r'D:\Game\AoESolo\hook\aoehook.dll', log=L)
print('player screen', lobby.wait_screen(pl,'MP Setup Screen',40), 'host states', lobby.session_states(pl))
b=pool.take(1)[0]
for wait in (0, 3):
    time.sleep(wait)
    try:
        lobby.join_from_list(b, log=L)
    except Exception as e: print('join error', e)
    time.sleep(1.5)
    print('wait', wait, 'bot screen', lobby.current_screen(b), 'bot states', lobby.session_states(b), 'HOST states', lobby.session_states(pl), 'present', lobby.present_players(pl))
    if lobby.present_players(pl) >= 2: break
    # go back to the list for the second try
    lobby._click(b, (1055, 728), 2.0); print('bot back on', lobby.current_screen(b))
b.kill(); pl.kill(); pool.shutdown()
