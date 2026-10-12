"""Aggregate tools/learned/*.json (from learn_rec.py) into the target economic profile the bot follows:
per minute of game time, the median number of villagers and of each job across all recorded players,
plus age-up and first-building timings. Writes tools/learned/profile.json and prints a table."""
import glob
import json
import os
import statistics as st

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned")
JOBS = ("berry", "hunt", "wood", "build", "farm", "gold", "idle/walk", "hunt_dist_x10")


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(q * len(xs)))]


players = []
for f in glob.glob(os.path.join(D, "*.aoerec.json")):
    players += json.load(open(f, encoding="utf-8"))["players"]

rows = {}
for p in players:
    for (t, nvil, jobs, food, wood) in p["timeline"]:
        m = t // 60
        r = rows.setdefault(m, {"vil": [], "res_food": [], "res_wood": [], **{j: [] for j in JOBS}})
        r["vil"].append(nvil)
        r["res_food"].append(food)
        r["res_wood"].append(wood)
        for j in JOBS:
            if j == "hunt_dist_x10":
                if j in jobs:
                    r[j].append(jobs[j] / 10.0)
            else:
                r[j].append(jobs.get(j, 0))

prof = {"n_players": len(players), "minutes": {}, "milestones": {}}
print("players:", len(players))
print("min  vil  berry hunt wood build farm gold idle | food wood | hunters' distance to TC")
for m in sorted(rows):
    if m > 16:
        break
    r = rows[m]
    line = {k: med(v) for k, v in r.items()}
    prof["minutes"][m] = line
    print("%3d %5s %5s %5s %5s %5s %5s %5s %5s | %5s %5s | %s" % (
        m, line["vil"], line["berry"], line["hunt"], line["wood"], line["build"], line["farm"], line["gold"],
        line["idle/walk"], line["res_food"], line["res_wood"], line["hunt_dist_x10"]))

tool = [p["tool_click"] for p in players]
bronze = [p["bronze_click"] for p in players]
vil_tool = [p["vil_at_tool"] for p in players]
gap = [b - a for a, b in zip(tool, bronze) if a and b]


def first(p, name, k=0):
    ts = [b["t"] for b in p["first_buildings"] if b["b"] == name]
    return ts[k] if len(ts) > k else None


ms = {
    "tool_click": tool, "bronze_click": bronze, "vil_at_tool": vil_tool, "tool_to_bronze": gap,
    "granary_1": [first(p, "Granary") for p in players],
    "pit_1": [first(p, "Storage Pit") for p in players],
    "pit_2": [first(p, "Storage Pit", 1) for p in players],
    "granary_2": [first(p, "Granary", 1) for p in players],
    "house_2": [first(p, "House", 1) for p in players],
    "market": [first(p, "Market") for p in players],
    "stable": [first(p, "Stable") for p in players],
}
print("\nmilestone        p10   median  p90")
for k, xs in ms.items():
    prof["milestones"][k] = {"p10": pct(xs, 0.1), "median": med(xs), "p90": pct(xs, 0.9)}
    print("%-14s %6s %8s %6s" % (k, pct(xs, 0.1), med(xs), pct(xs, 0.9)))
gr = [b for p in players for b in p["first_buildings"][:6] if b["b"] == "Granary"]
pits = [b for p in players for b in p["first_buildings"][:9] if b["b"] == "Storage Pit"]
print("\nfirst granary: d_tc median %s, bushes within 5 median %s, nearest bush median %s" % (
    med([g.get("d_tc") for g in gr]), med([g.get("bushes_within5") for g in gr]), med([g.get("nearest_bush") for g in gr])))
print("first pit: d_tc median %s, trees within 5 median %s" % (
    med([b.get("d_tc") for b in pits]), med([b.get("trees_within5") for b in pits])))
techs = {}
for p in players:
    for t, k in p.get("techs", []):
        techs.setdefault(k, []).append(t)
print("\ntechs (id: n players, median time s):", {k: (len(v), med(v)) for k, v in sorted(techs.items()) if len(v) >= 4})
json.dump(prof, open(os.path.join(D, "profile.json"), "w"), indent=1)
