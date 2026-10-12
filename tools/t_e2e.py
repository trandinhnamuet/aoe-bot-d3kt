import sys, time, threading
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import orchestrator, aoemem, gamewin as gw, lobby
SH=r'C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad'
log=open(r'D:\Game\AoESolo\tools\e2e.log','w',encoding='utf-8')
import ctypes
from PIL import ImageGrab
_n=[0]
def fgname():
    u=ctypes.windll.user32; h=u.GetForegroundWindow(); b=ctypes.create_unicode_buffer(128); u.GetWindowTextW(h,b,128); return b.value
def L(m):
    log.write(time.strftime('%H:%M:%S ')+m+'   [fg=%s]\n'%fgname()); log.flush()
    try:
        _n[0]+=1; ImageGrab.grab(all_screens=True).resize((960,540)).save(SH+'\\desk_%02d.png'%_n[0])
    except Exception: pass
cfg=orchestrator.Config(); cfg.num_ai=int(sys.argv[1]) if len(sys.argv)>1 else 1; cfg.player_civ=13
s=orchestrator.Session(r'D:\Game\AoESolo', cfg, log=L, status=lambda m: L('STATUS '+m), dll=r'D:\Game\AoESolo\hook\aoehook.dll', dplaunch=r'D:\Game\AoESolo\hook\dplaunch.exe')
s.game_dir=r'D:\Game\AoE-HD'
try:
    s.run()
    try: gw.screenshot(s.player.hwnd, SH+r'\e2e_lobby.png')
    except Exception as e: L('shot failed %r'%e)
    L('screen before start: %s'%lobby.current_screen(s.player))
    th=threading.Thread(target=s.wait_and_play,daemon=True); th.start()
    time.sleep(2)
    s.player.hook.cmd('vin 1'); s.player.hook.click(628,728); s.player.hook.cmd('vin 0')   # "the user presses Start Game"
    th.join(60)
    g=aoemem.Game(s.player.mem, s.player.hook)
    L('names: %s'%[g.player_name(i) for i in range(len(g.players()))])
    L('player fg=%s'%(gw.user32.GetForegroundWindow()==s.player.hwnd))
    time.sleep(20)
    try: gw.screenshot(s.player.hwnd, SH+r'\e2e_game.png')
    except Exception as e: L('shot failed %r'%e)
finally:
    s.shutdown()
    if s.player: s.player.kill()
    L('closed')
