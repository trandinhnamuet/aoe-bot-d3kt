"""Automatic AI-vs-AI lab: one hidden 4-player match (2v2, Hill Country, Large - like the user's recorded
games) with every player run by the D3KT brain, recorded by AoE-MapCap, scored per player.

python arena.py [--players 4] [--minutes 16] [--speed 3] [--params cand.json] [--tag name] [--no-rec]

Writes tools/arena/<stamp>_<tag>.log (bot log) and appends one JSON line per player to
tools/arena/results.jsonl: tool / bronze click (game s), villagers at Tool, idle, deaths, watchdog fixes,
distance to the learned player profile. Stops early (exit 3) if League of Legends or the user's AoE starts.
"""
import argparse
import struct
import json
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.environ.get("AOESOLO_LAUNCHER", r"D:\Game\AoESolo\launcher"))
sys.path.insert(0, r"D:\Game\AoE-MapCap")
import psutil  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--players", type=int, default=4)
ap.add_argument("--minutes", type=float, default=16.0, help="game minutes to play")
ap.add_argument("--speed", type=float, default=2.0, help="the user plays multiplayer at x2 (the UI maximum): test at x2")
ap.add_argument("--params", default=None)
ap.add_argument("--tag", default="base")
ap.add_argument("--no-rec", action="store_true")
ap.add_argument("--civs", default="", help="comma list of civ names for P1, P2, ... (empty = random)")
ap.add_argument("--age", default="Default", help="starting age: Default, Tool Age, Bronze Age (micro tests)")
ap.add_argument("--resources", default="Default", help="Default, Medium, High")
ap.add_argument("--reveal", action="store_true", help="lobby Reveal Map (tests: every tile explored at the start)")
ap.add_argument("--cheats", action="store_true", help="lobby Allow Cheats (staged tests: the bots type STEROIDS / WOODSTOCK)")
ap.add_argument("--map", default="Hill Country", help="map type (lobby name)")
ap.add_argument("--size", default="Large", help="map size: Tiny, Small, Medium, Large, Huge, Gigantic")
ap.add_argument("--teams", default="", help="comma list of teams for P1, P2, ... (2v2: 1,1,2,2; empty = all alone)")
ap.add_argument("--game", default=r"D:\Game\AoE-HD", help="game folder (AoE HD or the normal AOE1R)")
ap.add_argument("--brain", default="new", choices=("old", "new"), help="new = brain.brain.NewBrain (one allocation table), old = d3kt.Brain")
args = ap.parse_args()
if args.params:
    os.environ["D3KT_PARAMS"] = os.path.abspath(args.params)

import aoemem  # noqa: E402
import brainproc  # noqa: E402
import d3kt  # noqa: E402
import lobby  # noqa: E402
import orchestrator  # noqa: E402

GAME = args.game
DLL = r"D:\Game\AoESolo\hook\aoehook.dll"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena")
PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned", "profile.json")
os.makedirs(OUT, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")
logpath = os.path.join(OUT, "%s_%s.log" % (stamp, args.tag))
logf = open(logpath, "w", encoding="utf-8") if __name__ == "__main__" else None   # (brain child processes re-import this file)
lk = threading.Lock()


def L(m):
    if logf is None:
        return
    with lk:
        logf.write(time.strftime("%H:%M:%S ") + m + "\n")
        logf.flush()


def user_busy():
    for p in psutil.process_iter(["name"]):
        n = (p.info["name"] or "").lower()
        if n.startswith("league of legends") or n == "empiresx.exe" or n.startswith("aoesolo"):
            return n
    return None


def score(logtext, me, params):
    """Per-player metrics from the bot log lines [P<me> <t>s] ..."""
    tag = r"\[P%d +(\d+)s\] " % me
    tool = re.search(tag + r"Tool Age clicked with (\d+)", logtext)
    bronze = re.search(tag + r"Bronze Age clicked", logtext)
    stats = [(int(m.group(1)), m.group(2)) for m in re.finditer(tag + r"STAT (.*)", logtext)]
    idle = []
    vil_by_min = {}
    jobs_by_min = {}
    wdfix = 0
    for t, line in stats:
        mi = re.search(r"idle=(\d+)", line)
        if mi:
            idle.append(int(mi.group(1)))
        mv = re.search(r"vil=(\d+)", line)
        mw = re.search(r"wdfix=(\d+)", line)
        if mw:
            wdfix = int(mw.group(1))
        mr = re.search(r"roles=(\S*)", line)
        if mv and mr:
            vil_by_min[t // 60] = int(mv.group(1))
            jobs_by_min[t // 60] = dict((k, int(v)) for k, v in (kv.split(":") for kv in mr.group(1).split(",") if ":" in kv))
    # distance to the recorded players' profile (villagers + jobs per minute, minutes 1..10)
    dist = None
    if os.path.exists(PROFILE):
        prof = json.load(open(PROFILE))["minutes"]
        tot = 0.0
        n = 0
        for m in range(1, 11):
            p = prof.get(str(m))
            if not p or m not in vil_by_min:
                continue
            j = jobs_by_min.get(m, {})
            tot += abs(vil_by_min[m] - p["vil"]) + abs(j.get("wood", 0) - p["wood"]) + \
                abs(j.get("berry", 0) + j.get("hunt", 0) + j.get("farm", 0) - p["berry"] - p["hunt"] - p["farm"])
            n += 1
        dist = round(tot / n, 2) if n else None
    deaths = 0
    vils = [int(re.search(r"vil=(\d+)", line).group(1)) for _, line in stats if re.search(r"vil=(\d+)", line)]
    for a, b in zip(vils, vils[1:]):
        deaths += max(0, a - b)
    if "DEATH villager" in logtext:                 # newer bots log every death (lurers marked)
        deaths = len(re.findall(tag + r"DEATH villager", logtext))
    return {"player": me, "tool": int(tool.group(1)) if tool else None, "vil_at_tool": int(tool.group(2)) if tool else None,
            "bronze": int(bronze.group(1)) if bronze else None, "idle_avg": round(sum(idle) / len(idle), 2) if idle else None,
            "wdfix": wdfix, "profile_dist": dist, "deaths": deaths,
            "lurer_deaths": len(re.findall(tag + r"DEATH villager #\d+ \(\w+, lurer", logtext)),
            "watchdog_msgs": len(re.findall(tag + r"WATCHDOG", logtext)),
            "errors": len(re.findall(tag + r"tick error", logtext)) + len(re.findall(r"tick error", logtext)) * 0}


def main():
    if user_busy():
        print("user busy:", user_busy())
        sys.exit(3)
    import os as _os
    _os.environ["AOESOLO_BRAIN"] = args.brain                # d3kt.run picks the brain from this
    used = d3kt.load_params()
    L("params %s" % json.dumps(d3kt.current_params()))
    lobby.reg_set(lobby.REG_SERVICE, "Internet TCP/IP Connection For DirectPlay")
    n_ai = args.players - 1
    pool = orchestrator.BotPool(GAME, DLL, log=lambda m: None)
    pool.ensure(n_ai)
    t0 = time.time()
    while len(pool.parked) < n_ai and time.time() - t0 < 180:
        time.sleep(0.5)
    cfg = orchestrator.Config()
    cfg.num_ai = n_ai
    cfg.map_type, cfg.map_size, cfg.pop_limit = args.map, args.size, 200
    civs = [c.strip() for c in args.civs.split(",") if c.strip()]
    vals = [(lobby.CIVS.index(c) + 1) if c in lobby.CIVS else 0 for c in civs]
    cfg.player_civ = vals[0] if vals else 0
    cfg.ai_civs = (vals[1:] + [0] * 7)[:7]
    cfg.ai_team_mode = "ffa"
    cfg.teams = [int(x) for x in args.teams.split(",") if x.strip()] if args.teams else []
    cfg.age, cfg.resources = args.age, args.resources
    cfg.reveal_map = bool(args.reveal)
    cfg.cheats = bool(args.cheats)
    s = orchestrator.Session(r"D:\Game\AoESolo", cfg, log=L, status=lambda m: None, dll=DLL,
                             dplaunch=r"D:\Game\AoESolo\hook\dplaunch.exe", pool=pool)
    s.game_dir = GAME
    s.test_hidden_player = True
    rec_stop = threading.Event()
    rec_thread = None
    games = {}
    ths = []
    stop_flag = [False]
    invalid = [False]
    try:
        s.run()
        host = s.player
        if os.environ.get("AOESOLO_SEED"):
            # the match seed (map AND random civs come from it, 16/10): the host's comm object caches it at
            # +0x170c and hands it to the civ draw and the world init; written before Start, the clients get it
            # in the start settings
            seed = int(os.environ["AOESOLO_SEED"], 0) & 0xFFFFFFFF
            comm = host.mem.u32(0x585DF8)
            ok = bool(comm) and host.mem.write(comm + 0x170C, struct.pack("<I", seed))
            L("match seed %d written to the host (%s)" % (seed, "ok" if ok else "FAILED"))
        import ctypes
        import datetime
        L("START clock=%s tgt=%d" % (datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3], ctypes.windll.winmm.timeGetTime()))
        lobby.start_match(host, args.players, log=L)
        if not args.no_rec:
            import mapcap.engine as mce
            # (AoE-MapCap 13/10 18:24 calls find_game_process(exclude=...): the old no-argument lambda raised
            #  at once and no match was recorded - ab4 / ab5)
            mce.find_game_process = lambda *a, **kw: next((p for p in psutil.process_iter(["name", "exe"])
                                                           if p.pid == host.pid), None)
            cfgm = mce.load_config()
            rec_log = mce.Logger(os.path.join(OUT, "mapcap.log"))
            rec_thread = threading.Thread(target=lambda: mce.Engine(cfgm, rec_log, rec_stop).run(), daemon=True)
            rec_thread.start()
        numbers = {}
        for gp in [host] + s.bots:
            numbers[gp.pid] = lobby.my_player_number(gp)
        allp = sorted(numbers.values())
        game_limit = args.minutes * 60
        team_of = {}
        for i, gp in enumerate([host] + s.bots):
            team_of[numbers[gp.pid]] = cfg.teams[i] if len(cfg.teams) > i else 0
        for gp in [host] + s.bots:
            me = numbers[gp.pid]
            foes = [x for x in allp if x != me and (team_of.get(x, 0) == 0 or team_of.get(x) != team_of.get(me))]
            g = aoemem.Game(gp.mem, gp.hook)
            games[me] = g
            period = 0.6 / max(1.0, args.speed / 2.0)
            if brainproc.enabled():
                th = brainproc.start(gp.pid, me, foes, L, period=period, pop_limit=200, limit_s=game_limit)
            else:
                stop = (lambda gg=g, mm=gp.mem: stop_flag[0] or
                        (bool(gg.world()) and (mm.u32(gg.world() + 4) or 0) / 1000.0 > game_limit))
                th = threading.Thread(target=d3kt.run, args=(g, me, foes),
                                      kwargs=dict(log=L, stop=stop, pop_limit=200, period=period), daemon=True)
                th.start()
            ths.append(th)
        L("brains: %s" % ("one process each" if brainproc.enabled() else "threads of this process"))
        games[allp[0]].set_speed(args.speed)
        L("game speed set to x%.1f" % args.speed)
        try:
            gm = host.mem.u32(0x585E88)
            cm = host.mem.u32(0x585DF8)
            L("SEEDINFO comm_seed=%d game30=%d civs=%s flags=%s" % (
                host.mem.u32(cm + 0x170C), host.mem.u32(gm + 0x30), list(host.mem.read(gm + 0xA94, 8)),
                list(struct.unpack("<8I", host.mem.read(gm + 0xA58, 32)))))
        except Exception as e:  # noqa: BLE001
            L("SEEDINFO failed: %r" % (e,))
        grant = os.environ.get("AOESOLO_GRANT", "")
        if grant:
            # DO NOT USE (kept as a record): resources written into every game process at once - the match clock
            # froze at the first food write (stage10, 15/10), as it does after a cheat command (stage8/9/11)
            RES_I = {"food": 0, "wood": 1, "stone": 2, "gold": 3}
            floors = {RES_I[k.strip()]: float(v) for k, v in (kv.split("=") for kv in grant.split(",") if "=" in kv)}
            names = {v: k for k, v in RES_I.items()}

            def pump():
                g0 = games[allp[0]]
                while not stop_flag[0]:
                    try:
                        if g0.world():
                            for pn in allp:
                                have = g0.resources(pn)
                                for ri, floor in floors.items():
                                    if have[ri] < floor / 3:
                                        n = sum(1 for gg in games.values() if gg.set_resource(pn, ri, floor))
                                        L("GRANT P%d %s %.0f -> %.0f in %d games" % (pn, names[ri], have[ri], floor, n))
                    except Exception as e:  # noqa: BLE001
                        L("GRANT error %r" % (e,))
                    time.sleep(2)
            threading.Thread(target=pump, daemon=True).start()
            L("resource grant on: %s" % grant)
        # a match whose game runs slow (seen: x0.5 instead of x3) is not comparable: measure, give up
        w = games[allp[0]].world()
        g0, r0 = host.mem.u32(w + 4) or 0, time.time()
        time.sleep(20)
        g1 = host.mem.u32(games[allp[0]].world() + 4) or 0
        eff = (g1 - g0) / 1000.0 / (time.time() - r0)
        L("measured game speed x%.2f" % eff)
        invalid[0] = eff < 0.75 * args.speed and not os.environ.get("AOESOLO_KEEP_SLOW")   # (KEEP_SLOW: inspect a stalled game)
        if invalid[0]:
            L("SLOW GAME x%.2f: match invalid, stopping" % eff)
            stop_flag[0] = True
        while any(th.is_alive() for th in ths):
            time.sleep(5)
            if user_busy():
                L("user started %s: stopping" % user_busy())
                stop_flag[0] = True
                break
    finally:
        stop_flag[0] = True
        for th in ths:
            if hasattr(th, "stop"):
                th.stop()
        for th in ths:
            th.join(15)
            if hasattr(th, "kill"):
                th.kill()
        if rec_thread:
            time.sleep(3)
            rec_stop.set()
            rec_thread.join(120)
        s.shutdown()
        pool.shutdown()
        if s.player:
            s.player.kill()
    text = open(logpath, encoding="utf-8").read()
    res = []
    for me in sorted(games):
        r = score(text, me, used)
        r.update({"stamp": stamp, "tag": args.tag, "params": args.params, "speed": args.speed, "invalid": invalid[0]})
        res.append(r)
    with open(os.path.join(OUT, "results.jsonl"), "a", encoding="utf-8") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
    for r in res:
        print(json.dumps(r))
    sys.exit(3 if user_busy() else (4 if invalid[0] else 0))


if __name__ == "__main__":
    main()
