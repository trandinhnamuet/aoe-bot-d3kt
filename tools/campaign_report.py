"""Summary of a campaign (tools/campaign.py): per game and per player the age clicks, villagers / farms / army /
buildings at minutes 10, 15, 20, 25, 30, 35 (farms also at the end), deaths, tick times, and the CPU use while the game ran.

    .venv/Scripts/python tools/campaign_report.py <tag> [out.json]"""
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "arena")
tag = sys.argv[1]
MARKS = (10, 15, 20, 25, 30, 35)


def per_player(text, me):
    pre = r"\[P%d +(\d+)s\] " % me
    stats = [(int(m.group(1)), m.group(2)) for m in re.finditer(pre + r"STAT (.*)", text)]
    if not stats:
        return None

    def at(minute, key):
        best = None
        if stats[-1][0] < minute * 60 - 40:
            return None                                   # (the game did not reach that minute)
        for t, line in stats:
            if t <= minute * 60 + 20:
                m = re.search(key + r"=(\d+)", line)
                if m:
                    best = int(m.group(1))
        return best
    ticks = [(float(m.group(2)), float(m.group(3))) for m in re.finditer(pre + r"STAT .*tick=(\d+)/(\d+)ms", text)]   # (group 1 = the time)
    ticks = [(a, b) for a, b in ticks if a > 0]

    def click(name):
        m = re.search(pre + name, text)
        return int(m.group(1)) if m else None
    return {
        "player": me,
        "tool": click(r"Tool Age clicked"), "bronze": click(r"Bronze Age clicked"), "iron": click(r"Iron Age clicked"),
        "vil": {m: at(m, "vil") for m in MARKS}, "army": {m: at(m, "army") for m in MARKS}, "bldg": {m: at(m, "bldg") for m in MARKS},
        "farms": {m: at(m, "farms") for m in MARKS}, "farms_end": at(99, "farms"),       # (the user, 20/10: farms per bot)
        "age_end": at(99, "age"),
        "deaths": len(re.findall(pre + r"DEATH villager", text)),
        "soldier_deaths": len(re.findall(pre + r"SOLDIERDEATH", text)),
        "slow_ticks": len(re.findall(pre + r"SLOW tick", text)),
        "tick_avg_ms": round(sum(a for a, b in ticks) / len(ticks)) if ticks else None,
        "tick_max_ms": round(max(b for a, b in ticks)) if ticks else None,
        "last_s": stats[-1][0],
    }


def cpu_for(game):
    rows = []
    for path in (os.path.join(OUT, "campaign_%s_cpu2.csv" % tag), os.path.join(OUT, "campaign_%s_cpu.csv" % tag)):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                rows = [r for r in csv.DictReader(f) if r["game"] == game]
            if rows:
                break
    if not rows:
        return None
    keys = [k for k in rows[0] if k not in ("time", "game")]
    return {k: round(sum(float(r[k]) for r in rows) / len(rows), 2) for k in keys} | {"samples": len(rows)}


games = []
for ln in open(os.path.join(OUT, "campaign_%s.log" % tag), encoding="utf-8"):
    m = re.search(r"start (\S+): (.*)", ln)
    if m:
        games.append({"name": m.group(1), "args": m.group(2), "players": []})
for g in games:
    logs = sorted(glob.glob(os.path.join(OUT, "*_%s_%s.log" % (tag, g["name"]))), key=os.path.getsize)
    if not logs:
        continue
    text = open(logs[-1], encoding="utf-8").read()
    g["log"] = os.path.basename(logs[-1])
    m = re.search(r"measured game speed x([\d.]+)", text)
    g["speed"] = float(m.group(1)) if m else None
    g["stopped"] = bool(re.search(r"SLOW GAME|user started", text))
    n = int(re.search(r"--players (\d+)", g["args"]).group(1))
    for me in range(1, n + 1):
        p = per_player(text, me)
        if p:
            g["players"].append(p)
    g["cpu"] = cpu_for(g["name"])
if len(sys.argv) > 2:
    json.dump(games, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
for g in games:
    print("== %s (%s) speed x%s%s  cpu %s" % (g["name"], g["args"], g.get("speed"), " STOPPED" if g.get("stopped") else "", g.get("cpu")))
    for p in g["players"]:
        print("  P%d tool %s bronze %s iron %s | vil %s | farms %s end %s | army %s | bldg %s | deaths %d sold %d | tick %s/%s ms slow %d | end %ds" % (
            p["player"], p["tool"], p["bronze"], p["iron"], [p["vil"][m] for m in MARKS], [p["farms"][m] for m in MARKS], p["farms_end"],
            [p["army"][m] for m in MARKS], [p["bldg"][m] for m in MARKS], p["deaths"], p["soldier_deaths"], p["tick_avg_ms"],
            p["tick_max_ms"], p["slow_ticks"], p["last_s"]))
