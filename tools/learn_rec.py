"""Learn from real matches recorded by AoE-MapCap (.aoerec): for every player, the timeline the bot is
compared against - villager count and jobs (AoE1 renames villagers by task), buildings in order with
their place relative to the town center / berries / trees, Tool and Bronze click times.

python learn_rec.py [N_LATEST=9] [RAW_DIR]  -> tools/learned/<file>.json + tools/learned/summary.txt
Run with the system python (numpy).
"""
import collections
import json
import math
import os
import pickle
import struct
import sys
import zlib

sys.path.insert(0, r"D:\Game\AoE-MapCap")
import numpy as np  # noqa: E402
from mapcap.rawrec import MAGIC  # noqa: E402

RAW = sys.argv[2] if len(sys.argv) > 2 else r"D:\Game\AoE-MapCap\dist\Video\Raw"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 9
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned")
TOOL_TIME, BRONZE_TIME = 120.0, 140.0            # research seconds (empires.dat)
TECH_TOOL, TECH_BRONZE = 101, 102
SAMPLE_MS = 5000

# by empires.dat id (the recording keeps the internal names: "Storage_Pit1", "Man", ...)
JOBS = {83: "idle/walk", 118: "build", 120: "berry", 122: "hunt", 123: "wood", 251: "gold", 124: "stone",
        259: "farm", 156: "repair", 56: "fish", 57: "fish"}
BUILDINGS = {109: "Town Center", 70: "House", 68: "Granary", 103: "Storage Pit", 84: "Market", 101: "Stable",
             12: "Barracks", 87: "Archery Range", 50: "Farm", 104: "Temple", 45: "Dock", 82: "Government Center",
             79: "Watch Tower", 72: "Wall", 49: "Siege Workshop", 0: "Academy"}
MILITARY = {299: "scout", 37: "cavalry", 338: "camel", 41: "chariot", 4: "archer", 73: "clubman", 75: "axe",
            93: "short sword", 5: "bowman", 25: "elephant archer", 39: "horse archer", 11: "war elephant",
            125: "priest", 40: "chariot archer"}


def records(path):
    with open(path, "rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            return
        while True:
            head = f.read(5)
            if len(head) < 5:
                return
            n = struct.unpack("<I", head[1:])[0]
            data = f.read(n)
            if len(data) < n:
                return
            try:
                yield head[:1], pickle.loads(zlib.decompress(data))
            except Exception:
                return


def analyse(path):
    defs = {}                                    # def index -> (name, cls)
    units = {}                                   # uid -> record
    hdr = None
    statics = None
    tech_t = collections.defaultdict(dict)       # player -> {tech: t_ms}
    attrs = {}
    first_seen = {}                              # uid -> (t, name, owner, x, y)
    tcs_pos = {}
    timeline = collections.defaultdict(list)     # player -> [(t_s, n_vil, {job: n}, food, wood)]
    last = -SAMPLE_MS
    t = 0
    for tag, pl in records(path):
        if tag == b"H":
            hdr = pl
        elif tag == b"D":
            for rec in pl:
                defs[rec[0]] = (rec[3], rec[5], rec[4])
        elif tag == b"S" and statics is None:
            statics = pl["units"]                # the map at the start (bushes get eaten later)
        elif tag == b"F" and hdr is not None:
            t = pl["t"]
            if pl["full_units"]:
                units = {int(r["uid"]): r for r in pl["units"]}
            else:
                for u in pl["removed"].tolist():
                    units.pop(int(u), None)
                for r in pl["units"]:
                    units[int(r["uid"])] = r
            for idx, (a, techs) in pl.get("pstate", {}).items():
                attrs[idx] = a
                if techs is not None:
                    for tid in techs:
                        tech_t[idx].setdefault(tid, t)
            if t - last < SAMPLE_MS:
                continue
            last = t
            per = collections.defaultdict(collections.Counter)
            hunt_d = collections.defaultdict(list)
            for uid, (bt, bn, bo, bx, by) in first_seen.items():
                if bn == "Town Center":
                    tcs_pos.setdefault(bo, (bx, by))
            for uid, r in units.items():
                d = defs.get(int(r["def"]))
                if not d:
                    continue
                did = d[2]
                owner = int(r["owner"])
                if did in JOBS:
                    per[owner][JOBS[did]] += 1
                    if did == 122 and owner in tcs_pos:
                        hunt_d[owner].append(math.hypot(float(r["x"]) - tcs_pos[owner][0], float(r["y"]) - tcs_pos[owner][1]))
                elif did in (48, 65) and owner == 0 and int(r["status"]) <= 2:
                    pass
                elif did in MILITARY:
                    per[owner]["mil:" + MILITARY[did]] += 1
                if did in BUILDINGS and uid not in first_seen and owner > 0:
                    first_seen[uid] = (t, BUILDINGS[did], owner, float(r["x"]), float(r["y"]))
            for owner, ds in hunt_d.items():
                per[owner]["hunt_dist_x10"] = round(10 * sorted(ds)[len(ds) // 2])
            for owner, c in per.items():
                a = attrs.get(owner, ())
                timeline[owner].append((round(t / 1000), sum(v for k, v in c.items() if k in JOBS.values()), dict(c),
                                        round(a[0]) if a else None, round(a[1]) if a else None))
    if hdr is None:
        return None
    # static gaia: berries and trees for placement analysis
    bushes, trees = [], []
    if statics is not None:
        for r in statics:
            d = defs.get(int(r["def"]))
            if not d:
                continue
            if d[2] == 59:
                bushes.append((float(r["x"]), float(r["y"])))
            elif d[1] == 15:
                trees.append((float(r["x"]), float(r["y"])))
    players = {}
    for p in hdr["players"]:
        idx, name = p[0], p[3]
        players[idx] = name
    out = {"file": os.path.basename(path), "map": "%dx%d" % (hdr["map_w"], hdr["map_h"]),
           "match": {k: v for k, v in (hdr.get("match") or {}).items() if k != "raw"},
           "players": []}
    for idx, name in sorted(players.items()):
        if idx == 0:
            continue
        tl = timeline.get(idx, [])
        tt = tech_t.get(idx, {})
        tool_done = tt.get(TECH_TOOL)
        bronze_done = tt.get(TECH_BRONZE)
        tool_click = tool_done / 1000 - TOOL_TIME if tool_done else None
        bronze_click = bronze_done / 1000 - BRONZE_TIME if bronze_done else None
        blds = sorted([v for v in first_seen.values() if v[2] == idx])
        tcs = [b for b in blds if b[1] == "Town Center"]
        tc = (tcs[0][3], tcs[0][4]) if tcs else None

        def vil_at(ts):
            best = None
            for row in tl:
                if row[0] <= ts:
                    best = row
            return best
        order = []
        for (bt, bn, _, bx, by) in blds:
            if bn in ("Town Center",):
                continue
            item = {"t": round(bt / 1000), "b": bn, "x": round(bx, 1), "y": round(by, 1)}
            if tc:
                item["d_tc"] = round(math.hypot(bx - tc[0], by - tc[1]), 1)
            if bn == "Granary" and bushes:
                ds = sorted(math.hypot(bx - x, by - y) for x, y in bushes)
                item["bushes_within5"] = sum(1 for d in ds if d <= 5)
                item["nearest_bush"] = round(ds[0], 1)
            if bn == "Storage Pit" and trees:
                item["trees_within5"] = sum(1 for x, y in trees if math.hypot(bx - x, by - y) <= 5)
            order.append(item)
        row_tool = vil_at(tool_click) if tool_click else None
        out["players"].append({
            "index": idx, "name": name,
            "tool_click": round(tool_click) if tool_click else None,
            "bronze_click": round(bronze_click) if bronze_click else None,
            "vil_at_tool": row_tool[1] if row_tool else None,
            "jobs_at_tool": row_tool[2] if row_tool else None,
            "first_buildings": order[:25],
            "techs": sorted((round(v / 1000), k) for k, v in tt.items() if v > 0),
            "timeline": [r for r in tl if r[0] % 30 < 5][:80],
        })
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted([f for f in os.listdir(RAW) if f.endswith(".aoerec")], reverse=True)[:N]
    lines = []
    for f in files:
        res = analyse(os.path.join(RAW, f))
        if not res:
            continue
        json.dump(res, open(os.path.join(OUT, f + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        lines.append("== %s %s %s" % (f, res["map"], res["match"].get("map_type", "")))
        for p in res["players"]:
            fb = [(b["t"], b["b"]) for b in p["first_buildings"][:8]]
            lines.append("  %-16s tool=%s (%s vil %s) bronze=%s  first: %s" % (
                p["name"], p["tool_click"], p["vil_at_tool"], p["jobs_at_tool"], p["bronze_click"], fb))
        print("\n".join(lines[-(1 + len(res["players"])):]), flush=True)
    open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
