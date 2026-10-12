"""AI-vs-AI test match at game speed x2, recorded with AoE-MapCap.

python t_match_rec.py <minutes> [map_type] [map_size] [civ1] [civ2]
The recording lands in D:\\Game\\AoE-MapCap\\Video\\Raw\\*.aoerec (open it in AoE-MapCap / AoE-Replay).
"""
import os
import sys
import threading
import time

sys.path.insert(0, r"D:\Game\AoESolo\launcher")
sys.path.insert(0, r"D:\Game\AoE-MapCap")
import psutil

import aoemem
import d3kt
import gamestate as gs
import lobby
import procs

GAME = r"D:\Game\AoE-HD"
DLL = r"D:\Game\AoESolo\hook\aoehook.dll"
mins = float(sys.argv[1]) if len(sys.argv) > 1 else 30
mtype = sys.argv[2] if len(sys.argv) > 2 else "Hill Country"
msize = sys.argv[3] if len(sys.argv) > 3 else "Large"
civ1 = int(sys.argv[4]) if len(sys.argv) > 4 else 10
civ2 = int(sys.argv[5]) if len(sys.argv) > 5 else 4

logf = None
lk = threading.Lock()


def L(m):
    with lk:
        logf.write(time.strftime("%H:%M:%S ") + m + "\n")
        logf.flush()


# ---------------------------------------------------------------- setup
def main():
    global host_pid, logf
    logf = open(r"D:\Game\AoESolo\tools\match.log", "w", encoding="utf-8")
    lobby.write_settings(GAME, map_size=msize, map_type=mtype, pop_limit=200)
    lobby.reg_set(lobby.REG_SERVICE, "Internet TCP/IP Connection For DirectPlay")
    bots = []
    try:
        host = procs.start(GAME, "AOEBOT.EXE", DLL, True, log=L, job=False)
        bots.append(host)
        lobby.host_create(host, log=L, name="AI 1 D3KT")
        c = procs.start(GAME, "AOEBOT.EXE", DLL, True, log=L, job=False)
        bots.append(c)
        slot = lobby.client_join(c, log=L, name="AI 2 D3KT") - 1
        lobby.choose_civ(host, 0, civ1, log=L)
        lobby.choose_civ(c, slot, civ2, log=L)
        lobby.ready(c, False)
        lobby.ready(host, True)
        lobby.start_match(host, 2, log=L)
    finally:
        pass
    open(r"D:\Game\AoESolo\tools\pids.txt", "w").write("%d %d" % (host.pid, c.pid))

    # ---------------------------------------------------------------- recorder (AoE-MapCap, from the host's view)
    import mapcap.engine as mce

    host_pid = host.pid


    def _find_host():
        for p in psutil.process_iter(["name", "exe"]):
            if p.pid == host_pid:
                return p
        return None


    mce.find_game_process = _find_host
    cfg = mce.load_config()
    rec_stop = threading.Event()
    rec_log = mce.Logger(os.path.join(r"D:\Game\AoESolo\tools", "mapcap.log"))
    rec_thread = threading.Thread(target=lambda: mce.Engine(cfg, rec_log, rec_stop).run(), daemon=True)
    rec_thread.start()
    L("AoE-MapCap recording host pid %d into %s" % (host_pid, cfg.raw_dir()))

    # ---------------------------------------------------------------- bots (at once, like the app)
    t0 = time.time()
    stop_flag = [False]
    stop = lambda: stop_flag[0] or time.time() - t0 > mins * 60
    games = {}
    ths = []
    for gp in (host, c):
        me = lobby.my_player_number(gp)
        g = aoemem.Game(gp.mem, gp.hook)
        games[me] = g
        th = threading.Thread(target=d3kt.run, args=(g, me, [x for x in (1, 2) if x != me]),
                              kwargs=dict(log=L, stop=stop, pop_limit=200), daemon=True)
        th.start()
        ths.append(th)

    games[1].set_speed(2.0)                          # tests always run at x2 (host command)
    L("game speed set to x2")
    time.sleep(2)
    w0 = games[1].world()
    gt0 = host.mem.u32(w0 + 4)
    time.sleep(30)
    gt1 = host.mem.u32(games[1].world() + 4)
    L("game speed check: %.2fx (game ms %d in 30 s)" % ((gt1 - gt0) / 30000.0, gt1 - gt0))

    # end early when one side has lost its town center and almost everything else
    while not stop():
        time.sleep(10)
        try:
            for me, g in games.items():
                units = g.units(me)
                if not any(u.type == gs.TOWN_CENTER for u in units) and len(units) < 5:
                    L("player %d is beaten, ending the test" % me)
                    stop_flag[0] = True
        except Exception as e:  # game closed
            L("monitor: %r" % (e,))
            stop_flag[0] = True
    for th in ths:
        th.join(15)
    L("bots stopped, finalising the recording")
    time.sleep(5)
    rec_stop.set()
    rec_thread.join(120)
    for b in bots:
        b.kill()
    L("test finished")
    # bot decision log next to the recording (times in [P# game-seconds])
    import glob
    import shutil
    recs = sorted(glob.glob(os.path.join(cfg.raw_dir(), "*.aoerec")), key=os.path.getmtime)
    if recs:
        logf.flush()
        shutil.copyfile(r"D:\Game\AoESolo\tools\match.log", os.path.splitext(recs[-1])[0] + ".d3kt.log")


if __name__ == "__main__":
    main()
