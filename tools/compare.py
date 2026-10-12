"""Per-minute comparison of an arena log with the recorded players' profile.
python compare.py [arena log]   (default: the newest tools/arena/*.log)"""
import glob
import json
import os
import re
import sys

D = os.path.dirname(os.path.abspath(__file__))
log = sys.argv[1] if len(sys.argv) > 1 else max(glob.glob(os.path.join(D, "arena", "*.log")), key=os.path.getmtime)
prof = json.load(open(os.path.join(D, "learned", "profile.json")))["minutes"]
text = open(log, encoding="utf-8").read()
players = sorted(set(int(p) for p in re.findall(r"\[P(\d+) +\d+s\] STAT", text)))
print(os.path.basename(log))
print("min | players: vil berry hunt wood (food) || " + " | ".join("P%d vil be hu wo build scout (food)" % p for p in players))
rows = {}
for p in players:
    for m in re.finditer(r"\[P%d +(\d+)s\] STAT .*?vil=(\d+) food=(\d+).*?roles=(\S*)" % p, text):
        t, vil, food, roles = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        r = dict((k, int(v)) for k, v in (kv.split(":") for kv in roles.split(",") if ":" in kv))
        rows.setdefault(t // 60, {}).setdefault(p, (vil, r, food))
for mi in range(0, 17):
    pr = prof.get(str(mi))
    if not pr:
        continue
    cells = []
    for p in players:
        v = rows.get(mi, {}).get(p)
        if v:
            vil, r, food = v
            cells.append("%3d %2d %2d %2d %2d %2d (%4d)" % (vil, r.get("berry", 0), r.get("hunt", 0), r.get("wood", 0),
                                                       r.get("build", 0), r.get("scout", 0) + r.get("search", 0), food))
        else:
            cells.append(" " * 25)
    print("%3d | %4.0f %4.0f %4.0f %4.0f (%4.0f) || %s" % (mi, pr["vil"], pr["berry"], pr["hunt"], pr["wood"],
                                                    pr["res_food"] or 0, " | ".join(cells)))
