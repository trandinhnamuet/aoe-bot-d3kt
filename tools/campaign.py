"""A test campaign: several arena games in a row with a CPU sampler, pausing while the user plays.

    .venv/Scripts/python tools/campaign.py <plan.json> <tag>

plan.json: {"games": [{"name": "1v1a", "args": ["--players", "2", "--size", "Large", "--minutes", "25"]}, ...]}
Writes tools/arena/campaign_<tag>.log (what ran, when) and tools/arena/campaign_<tag>_cpu.csv
(time, game, system cpu %, AOEBOT.EXE total %, python total %, AOEBOT count, python count, RAM MB)."""
import json
import os
import subprocess
import sys
import threading
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
OUT = os.path.join(HERE, "arena")
BUSY = ("aoesolo.exe", "empiresx.exe", "league of legends.exe", "leagueclient.exe")

plan = json.load(open(sys.argv[1], encoding="utf-8"))
tag = sys.argv[2]
logp = os.path.join(OUT, "campaign_%s.log" % tag)
csvp = os.path.join(OUT, "campaign_%s_cpu.csv" % tag)
cur = {"game": "-"}
stop = threading.Event()


def L(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(logp, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def user_busy():
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() in BUSY:
            return p.info["name"]
    return None


def sampler():
    psutil.cpu_percent(None)
    procs = {}
    with open(csvp, "a", encoding="utf-8") as f:
        f.write("time,game,sys_cpu,aoebot_cpu,python_cpu,n_aoebot,n_python,ram_mb\n")
    while not stop.is_set():
        time.sleep(10)
        sys_cpu = psutil.cpu_percent(None)
        bot = py = 0.0
        nb = npy = 0
        ram = 0
        for p in psutil.process_iter(["name", "pid"]):
            n = (p.info["name"] or "").lower()
            if n != "aoebot.exe" and not n.startswith("python"):      # (the Store Python runs as python3.10.exe)
                continue
            try:
                h = procs.get(p.pid)
                if h is None:
                    h = procs[p.pid] = psutil.Process(p.pid)
                    h.cpu_percent(None)
                    continue
                c = h.cpu_percent(None) / max(1, psutil.cpu_count())
                ram += h.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                procs.pop(p.pid, None)
                continue
            if n == "aoebot.exe":
                bot += c
                nb += 1
            else:
                py += c
                npy += 1
        with open(csvp, "a", encoding="utf-8") as f:
            f.write("%s,%s,%.1f,%.1f,%.1f,%d,%d,%d\n" % (time.strftime("%H:%M:%S"), cur["game"], sys_cpu, bot, py, nb, npy, ram // 1048576))


threading.Thread(target=sampler, daemon=True).start()
L("campaign %s: %d games" % (tag, len(plan["games"])))
for g in plan["games"]:
    while user_busy():
        L("user busy (%s): waiting" % user_busy())
        time.sleep(60)
    cur["game"] = g["name"]
    cmd = [PY, os.path.join(HERE, "arena.py"), "--no-rec", "--tag", "%s_%s" % (tag, g["name"])] + g["args"]
    L("start %s: %s" % (g["name"], " ".join(g["args"])))
    t0 = time.time()
    env = dict(os.environ, **{k: str(v) for k, v in (g.get("env") or {}).items()})   # (per game: AOESOLO_SEED...)
    rc = subprocess.call(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    L("end %s: exit %d after %.0f s" % (g["name"], rc, time.time() - t0))
    cur["game"] = "-"
    if rc == 3:
        L("stopped by the user's game: the game is repeated after the pause")
        plan["games"].append(g)
    time.sleep(15)
stop.set()
L("campaign done")
