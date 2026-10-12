import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import procs, lobby
GAME=r'D:\Game\AoE-HD'; DLL=r'D:\Game\AoESolo\hook\aoehook.dll'
user=lobby.reg_get(lobby.REG_NAME,'Player')
lobby.write_settings(GAME, map_size='Small', map_type='Highland', pop_limit=50)
lobby.reg_set(lobby.REG_SERVICE,'Internet TCP/IP Connection For DirectPlay')
gps=[]
try:
    lobby.reg_set(lobby.REG_NAME,'AI 1'); lobby.reg_set(lobby.REG_GAMENAME,'AoESolo')
    host=procs.start(GAME,'AOEBOT.EXE',DLL,True); gps.append(host); time.sleep(2)
    lobby.host_create(host)
    lobby.reg_set(lobby.REG_NAME,'AI 2')
    c2=procs.start(GAME,'AOEBOT.EXE',DLL,True); gps.append(c2); time.sleep(2)
    s2=lobby.client_join(c2)-1
    lobby.reg_set(lobby.REG_NAME,user)
    pl=procs.start(GAME,'EMPIRESX.EXE',DLL,True); gps.append(pl); time.sleep(2)   # hidden only for this test
    s3=lobby.client_join(pl)-1
    lobby.choose_civ(host,0,10); lobby.set_team(host,0,1)
    lobby.choose_civ(c2,s2,4); lobby.set_team(c2,s2,1)
    lobby.choose_civ(pl,s3,13); lobby.set_team(pl,s3,2)
    lobby.ready(c2,False); lobby.ready(pl,False); lobby.ready(host,True)
    print('civs seen by host', [lobby.slot_civ(host,i) for i in range(3)], 'teams', [lobby.slot_team(host,i) for i in range(3)])
    lobby.start_match(host,3)
    open(r'D:\Game\AoESolo\tools\pids.txt','w').write(' '.join(str(g.pid) for g in gps))
finally:
    lobby.reg_set(lobby.REG_NAME,user)
