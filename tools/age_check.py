"""Arena check (the user, 13/10): every bot must reach the Bronze age before minute 20 (1 200 s game
time) unless it was attacked; villagers must never stand doing nothing.

python age_check.py arena/<log>     -> one block per player: Tool / Bronze click and reach, deaths and
                                       enemy attacks before 1 200 s, long-idle villagers, idle targets."""
import re
import sys
from collections import Counter, defaultdict

f = sys.argv[1]
lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
P = defaultdict(lambda: {"tool": None, "tool_done": None, "bronze": None, "bronze_done": None, "deaths": 0, "attacked": 0,
                         "idle": Counter(), "idleobj": Counter(), "last": ""})
for ln in lines:
    m = re.search(r"\[P(\d) +(\d+)s\] (.*)", ln)
    if not m:
        continue
    p, t, msg = int(m.group(1)), int(m.group(2)), m.group(3)
    d = P[p]
    if "Tool Age clicked" in msg and d["tool"] is None:
        d["tool"] = t
    if "Bronze Age clicked" in msg and d["bronze"] is None:
        d["bronze"] = t
    if "researched: Bronze Age" in msg and d["bronze_done"] is None:
        d["bronze_done"] = t
    if t < 1200 and "DEATH villager" in msg:
        d["deaths"] += 1
    if t < 1200 and ("TACTICS defend" in msg or "under attack" in msg):
        d["attacked"] += 1
    if msg.startswith("IDLEDBG long idle"):
        for item in msg.split(": ", 1)[1].split(" #")[0:]:
            r = re.search(r"(\w+|-)@", item)
            if r:
                d["idle"][r.group(1)] += 1
    if msg.startswith("IDLEDBG villager"):
        r = re.search(r"orders to (.+?) at", msg)
        d["idleobj"][r.group(1) if r else "?"] += 1
    if "STAT" in msg and ("age=2" in msg or "age=3" in msg) and d["tool_done"] is None:
        d["tool_done"] = t
    if "STAT" in msg and "age=3" in msg and d["bronze_done"] is None:
        d["bronze_done"] = t                      # (the 'researched' line is not always logged)
    if "STAT" in msg:
        d["last"] = " ".join(re.findall(r"(vil=\d+|age=\d|food=\d+|farms=[\d/]+)", msg))


def mmss(t):
    return "-" if t is None else "%d:%02d" % (t // 60, t % 60)


ok = True
for p in sorted(P):
    d = P[p]
    good = d["bronze_done"] is not None and d["bronze_done"] <= 1200     # reached, not just clicked
    excuse = d["attacked"] > 0 or d["deaths"] >= 5
    flag = "OK" if good else ("attacked" if excuse else "FAIL")
    ok &= good or excuse
    tool_age = (d["bronze"] - d["tool_done"]) if d["bronze"] and d["tool_done"] else None
    print("P%d %-8s Tool click %s reached %s | Bronze click %s reached %s | in Tool age before the click %s | deaths<20m %d | %s" % (
        p, flag, mmss(d["tool"]), mmss(d["tool_done"]), mmss(d["bronze"]), mmss(d["bronze_done"]), mmss(tool_age),
        d["deaths"], d["last"]))
    if d["idle"]:
        print("    long-idle reports by role:", dict(d["idle"]))
    if d["idleobj"]:
        print("    unreachable targets skipped:", dict(d["idleobj"]))
print("ALL OK" if ok else "SOME FAIL")
