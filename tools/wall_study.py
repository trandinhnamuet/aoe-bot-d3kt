"""How real players wall in (bo nhà) and open / close it, from AoE-MapCap recordings (.aoerec).

python wall_study.py [N_LATEST=5] [RAW_DIR]        (system python: numpy)

Per player: every house (and other building) with build time and place; houses that vanished with hp
left (deleted = a gate opened) and whether a house came back on the same spot (gate closed) and how
long it stayed open; what touches each house (forest / cliff / water / map edge / other buildings /
open ground); and every 60 s whether the town is sealed (flood fill from the TC that never reaches 25
tiles out), how big the enclosed area is and how many houses / buildings close it.
Writes tools/learned/walls_<file>.json and prints a summary."""
import collections
import json
import math
import os
import sys

sys.path.insert(0, r"D:\Game\AoE-MapCap")
import numpy as np  # noqa: E402
from mapcap.rawrec import iter_records  # noqa: E402

RAW = sys.argv[2] if __name__ == "__main__" and len(sys.argv) > 2 else r"D:\Game\AoE-MapCap\dist\Video\Raw"
N = int(sys.argv[1]) if __name__ == "__main__" and len(sys.argv) > 1 else 5
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned")
WATER = {1, 22, 23}
HOUSE, TC, FARM = 70, 109, 50
SIZE = {70: 2, 109: 3, 68: 3, 103: 3, 84: 3, 101: 3, 12: 3, 87: 3, 104: 3, 49: 3, 0: 3, 82: 3, 45: 3, 79: 1, 199: 1,
        276: 3, 71: 3, 141: 3, 142: 3, 143: 3, 25: 3}
NAMES = {70: "house", 109: "TC", 68: "granary", 103: "pit", 84: "market", 101: "stable", 12: "barracks", 87: "range",
         104: "temple", 49: "siege", 0: "academy", 45: "dock", 79: "tower", 199: "wall", 50: "farm", 276: "wonder"}
SEAL_R = 25.0


def study(path):
    defs = {}
    hdr = None
    units = {}
    statics = {}
    houses = {}                  # uid -> dict
    blds = {}                    # uid -> (dat, owner, x, y, t)
    last_seen = {}               # uid -> (t, hp, status)
    seals = collections.defaultdict(list)
    t = 0
    next_seal = 60000
    for tag, pl in iter_records(path):
        if tag == b"H":
            hdr = pl
        elif tag == b"D":
            for rec in pl:
                defs[rec[0]] = (rec[2], rec[3], rec[4], rec[5])      # utype, name, dat, cls
        elif tag == b"S":
            statics = {int(r["uid"]): r for r in pl["units"]}
        elif tag == b"Q":
            for u in pl["removed"].tolist():
                statics.pop(int(u), None)
            for r in pl["units"]:
                statics[int(r["uid"])] = r
        elif tag == b"F" and hdr is not None:
            t = pl["t"]
            if pl["full_units"]:
                gone = set(units) - {int(r["uid"]) for r in pl["units"]}
                units = {int(r["uid"]): r for r in pl["units"]}
            else:
                gone = {int(u) for u in pl["removed"].tolist()}
                for u in gone:
                    units.pop(u, None)
                for r in pl["units"]:
                    units[int(r["uid"])] = r
            for u in gone:
                h = houses.get(u)
                if h is not None and h["end"] is None:
                    ls = last_seen.get(u, (t, 0, 3))
                    h["end"] = t
                    h["deleted"] = ls[1] > 0 and ls[2] <= 2 and ls[1] >= 0.5 * h.get("maxhp", 75)
            for uid, r in units.items():
                d = defs.get(int(r["def"]))
                if not d:
                    continue
                utype, name, dat, cls = d
                owner = int(r["owner"])
                if owner <= 0 or utype != 80:
                    continue
                last_seen[uid] = (t, float(r["hp"]), int(r["status"]))
                if uid not in blds:
                    blds[uid] = (dat, owner, float(r["x"]), float(r["y"]), t)
                if dat == HOUSE and uid not in houses:
                    houses[uid] = dict(uid=uid, owner=owner, x=float(r["x"]), y=float(r["y"]), t=t, end=None, deleted=False,
                                       maxhp=max(1.0, float(r["hp"])))
                elif dat == HOUSE:
                    houses[uid]["maxhp"] = max(houses[uid]["maxhp"], float(r["hp"]))
            if t >= next_seal:
                next_seal += 60000
                grid = passmap(hdr, defs, statics, units)
                for owner, (tx, ty) in tcs(blds, units).items():
                    seals[owner].append((round(t / 1000),) + sealed(grid, tx, ty))
    if hdr is None:
        return None
    grid0 = passmap(hdr, defs, statics, {})
    W, H = hdr["map_w"], hdr["map_h"]
    terr = hdr["terrain"]
    tree_tiles = set()
    for r in statics.values():
        d = defs.get(int(r["def"]))
        if d and d[0] == 90:
            tree_tiles.add((int(r["x"]), int(r["y"])))
    # touching analysis: the 12 tiles round a 2x2 house
    bld_tiles = {}
    for uid, (dat, owner, x, y, t0) in blds.items():
        s = SIZE.get(dat, 0)
        if not s or dat == FARM:
            continue
        x0, y0 = int(math.floor(x - s / 2 + 1e-3)), int(math.floor(y - s / 2 + 1e-3))
        for yy in range(y0, y0 + s):
            for xx in range(x0, x0 + s):
                bld_tiles[(xx, yy)] = (uid, dat)
    players = {int(p[0]): p[3] for p in hdr["players"] if p[0] > 0}
    out = {"file": os.path.basename(path), "players": {}}
    for owner, name in players.items():
        hs = [h for h in houses.values() if h["owner"] == owner]
        tc = tcs(blds, {}).get(owner)
        touch_tot = collections.Counter()
        rows = []
        for h in hs:
            x0, y0 = int(math.floor(h["x"] - 1 + 1e-3)), int(math.floor(h["y"] - 1 + 1e-3))
            c = collections.Counter()
            for (xx, yy) in ring(x0, y0, 2):
                if not (0 <= xx < W and 0 <= yy < H):
                    c["edge"] += 1
                elif int(terr[yy, xx]) in WATER:
                    c["water"] += 1
                elif (xx, yy) in tree_tiles:
                    c["forest"] += 1
                elif (xx, yy) in bld_tiles and bld_tiles[(xx, yy)][0] != h["uid"]:
                    c["house" if bld_tiles[(xx, yy)][1] == HOUSE else "building"] += 1
                elif not grid0[yy, xx]:
                    c["cliff/rock"] += 1
                else:
                    c["open"] += 1
            touch_tot.update(c)
            rows.append(dict(t=round(h["t"] / 1000), x=round(h["x"], 1), y=round(h["y"], 1),
                             d_tc=round(math.hypot(h["x"] - tc[0], h["y"] - tc[1]), 1) if tc else None,
                             end=None if h["end"] is None else round(h["end"] / 1000), deleted=h["deleted"], touch=dict(c)))
        # gates: a deleted house and a house built again within 1 tile of it
        gates = []
        for h in hs:
            if not h["deleted"]:
                continue
            back = [g for g in hs if g["t"] > h["end"] and abs(g["x"] - h["x"]) < 1.1 and abs(g["y"] - h["y"]) < 1.1]
            gates.append(dict(t=round(h["end"] / 1000), x=round(h["x"], 1), y=round(h["y"], 1),
                              d_tc=round(math.hypot(h["x"] - tc[0], h["y"] - tc[1]), 1) if tc else None,
                              open_s=round((min(g["t"] for g in back) - h["end"]) / 1000) if back else None))
        others = collections.Counter(NAMES.get(b[0], str(b[0])) for b in blds.values() if b[1] == owner)
        out["players"][name] = dict(index=owner, tc=tc, houses=len(hs), houses_touch=dict(touch_tot), gates=gates,
                                    seal=seals.get(owner, []), buildings=dict(others), house_rows=sorted(rows, key=lambda r: r["t"]))
    return out


def ring(x0, y0, s):
    for xx in range(x0 - 1, x0 + s + 1):
        yield (xx, y0 - 1)
        yield (xx, y0 + s)
    for yy in range(y0, y0 + s):
        yield (x0 - 1, yy)
        yield (x0 + s, yy)


def tcs(blds, units):
    out = {}
    for uid, (dat, owner, x, y, t0) in sorted(blds.items(), key=lambda kv: kv[1][4]):
        if dat == TC and owner not in out:
            out[owner] = (x, y)
    return out


def passmap(hdr, defs, statics, units):
    W, H = hdr["map_w"], hdr["map_h"]
    grid = np.ones((H, W), dtype=bool)
    terr = hdr["terrain"]
    for v in WATER:
        grid[terr == v] = False
    for r in list(statics.values()) + list(units.values()):
        d = defs.get(int(r["def"]))
        if not d:
            continue
        utype, name, dat, cls = d
        if int(r["status"]) >= 3 and utype != 90:
            continue
        if utype == 90 or (utype == 10 and cls != 14):
            x, y = int(r["x"]), int(r["y"])
            if 0 <= x < W and 0 <= y < H:
                grid[y, x] = False
        elif utype == 80 and dat != FARM:
            s = SIZE.get(dat, 2)
            x0, y0 = int(math.floor(float(r["x"]) - s / 2 + 1e-3)), int(math.floor(float(r["y"]) - s / 2 + 1e-3))
            grid[max(0, y0):min(H, y0 + s), max(0, x0):min(W, x0 + s)] = False
    return grid


def sealed(grid, tx, ty):
    """(sealed?, enclosed tiles) - 4-neighbour flood fill from the TC within SEAL_R."""
    H, W = grid.shape
    seen = set()
    stack = []
    for yy in range(int(ty) - 3, int(ty) + 4):
        for xx in range(int(tx) - 3, int(tx) + 4):
            if 0 <= xx < W and 0 <= yy < H and grid[yy, xx]:
                seen.add((xx, yy))
                stack.append((xx, yy))
    while stack:
        x, y = stack.pop()
        if math.hypot(x + 0.5 - tx, y + 0.5 - ty) >= SEAL_R:
            return (False, len(seen))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and grid[ny, nx] and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return (True, len(seen))


def main():
    files = sorted([f for f in os.listdir(RAW) if f.endswith(".aoerec")], reverse=True)[:N]
    os.makedirs(OUT, exist_ok=True)
    for f in files:
        res = study(os.path.join(RAW, f))
        if res is None:
            continue
        json.dump(res, open(os.path.join(OUT, "walls_" + f + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("==", f)
        for name, p in res["players"].items():
            first_seal = next((s for s in p["seal"] if s[1]), None)
            tt = sum(p["houses_touch"].values()) or 1
            print("  %-16s houses %2d | touch: %s | gates %d (open s: %s) | sealed first at %s (%s tiles) | %s" % (
                name, p["houses"], " ".join("%s %d%%" % (k, 100 * v // tt) for k, v in sorted(p["houses_touch"].items(), key=lambda kv: -kv[1])),
                len(p["gates"]), [g["open_s"] for g in p["gates"]][:8],
                first_seal[0] if first_seal else "-", first_seal[2] if first_seal else "-",
                " ".join("%s:%d" % kv for kv in sorted(p["buildings"].items()))))


if __name__ == "__main__":
    main()
