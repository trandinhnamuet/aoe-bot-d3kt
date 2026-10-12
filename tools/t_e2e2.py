"""E2E test of the fast flow: pre-warmed bot pool, lobby launch, direct civ/team. python t_e2e2.py [num_ai]"""
import ctypes
import sys
import threading
import time

sys.path.insert(0, r"D:\Game\AoESolo\launcher")
from PIL import ImageGrab

import aoemem
import gamewin as gw
import lobby
import orchestrator

SH = r"C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad"
log = open(r"D:\Game\AoESolo\tools\e2e.log", "w", encoding="utf-8")
shots = [0]


def fg():
    u = ctypes.windll.user32
    b = ctypes.create_unicode_buffer(128)
    u.GetWindowTextW(u.GetForegroundWindow(), b, 128)
    return b.value


def L(m):
    log.write(time.strftime("%H:%M:%S ") + m + "   [fg=%s]\n" % fg())
    log.flush()


def shooter(stop):
    while not stop[0]:
        shots[0] += 1
        try:
            ImageGrab.grab(all_screens=True).resize((960, 540)).save(SH + "\\fast_%03d.png" % shots[0])
        except Exception:
            pass
        time.sleep(0.5)


n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
pool = orchestrator.BotPool(r"D:\Game\AoE-HD", r"D:\Game\AoESolo\hook\aoehook.dll", log=L)
t0 = time.time()
pool.ensure(n)
while len(pool.parked) < n and time.time() - t0 < 120:
    time.sleep(0.5)
L("pool: %d bots parked after %.1f s" % (len(pool.parked), time.time() - t0))

cfg = orchestrator.Config()
cfg.num_ai = n
cfg.player_civ = 13
cfg.ai_civs = [0, 5, 9, 0, 0, 0, 0]
s = orchestrator.Session(r"D:\Game\AoESolo", cfg, log=L, status=lambda m: L("STATUS " + m),
                         dll=r"D:\Game\AoESolo\hook\aoehook.dll", dplaunch=r"D:\Game\AoESolo\hook\dplaunch.exe",
                         pool=pool)
s.game_dir = r"D:\Game\AoE-HD"
stop = [False]
th = threading.Thread(target=shooter, args=(stop,), daemon=True)
th.start()
try:
    t1 = time.time()
    s.run()
    L("CLICK -> ROOM READY: %.1f s" % (time.time() - t1))
    L("player slot civ %s team %s" % (lobby.slot_civ(s.player, 0), lobby.slot_team(s.player, 0)))
    time.sleep(2)
    w = threading.Thread(target=s.wait_and_play, daemon=True)
    w.start()
    s.player.hook.cmd("vin 1")
    s.player.hook.click(628, 728)          # "the player presses Start Game"
    s.player.hook.cmd("vin 0")
    w.join(60)
    g = aoemem.Game(s.player.mem, s.player.hook)
    L("names: %s" % [g.player_name(i) for i in range(len(g.players()))])
    time.sleep(10)
finally:
    stop[0] = True
    s.shutdown()
    pool.shutdown()
    if s.player:
        s.player.kill()
    L("closed after %d screenshots" % shots[0])
