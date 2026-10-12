"""Unit speeds, spear range, elephant hits - measured on the user's recorded games (.aoerec, 25 samples/s).

python speed_study.py [N_FILES=3]
"""
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gazelle_study import RAW, records, VILLAGERS  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
TYPES = {"villager": VILLAGERS, "elephant": {48}, "gazelle": {65}, "scout": {299}, "cavalry": {37},
         "camel": {338}, "clubman": {73}, "bowman": {4}, "lion": set()}
EPS = 0.04


def q(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None


def main():
    files = sorted(f for f in os.listdir(RAW) if f.endswith(".aoerec"))[-N:]
    speeds = {k: [] for k in TYPES}
    spear_d, ele_hits, ele_hit_gap = [], [], []
    for fn in files:
        defs, names = {}, {}
        pos = {}            # uid -> (x, y, hp, kind, t)
        hist = {}           # uid -> list of (t, x, y) while moving continuously
        last_hit = {}
        for tag, pl in records(os.path.join(RAW, fn)):
            if tag == b"D":
                for rec in pl:
                    defs[rec[0]] = rec[4]
                    names[rec[0]] = str(rec[1]) if len(rec) > 1 else ""
                    if "lion" in str(rec[1:4]).lower():
                        TYPES["lion"].add(rec[4])
                continue
            if tag != b"F":
                continue
            t = pl["t"] / 1000.0
            if pl["full_units"]:
                pos.clear()
                hist.clear()
            else:
                for u in pl["removed"].tolist():
                    pos.pop(int(u), None)
                    hist.pop(int(u), None)
            cur = {}
            for r in pl["units"]:
                tid = defs.get(int(r["def"]))
                kind = next((k for k, ids in TYPES.items() if tid in ids), None)
                if kind is None:
                    continue
                uid = int(r["uid"])
                cur[uid] = (float(r["x"]), float(r["y"]), float(r["hp"]), kind, t)
            vils = [(x, y) for (x, y, hp, k, _) in cur.values() if k == "villager"]
            for uid, (x, y, hp, kind, _) in cur.items():
                p = pos.get(uid)
                if p is None or p[3] != kind:
                    hist[uid] = [(t, x, y)]
                else:
                    step = math.hypot(x - p[0], y - p[1])
                    if step > EPS and t - p[4] < 0.1:
                        hist.setdefault(uid, []).append((t, x, y))
                        h = hist[uid]
                        if h[-1][0] - h[0][0] >= 1.0:          # a full second of continuous motion
                            dt = h[-1][0] - h[0][0]
                            speeds[kind].append(math.hypot(h[-1][1] - h[0][1], h[-1][2] - h[0][2]) / dt)
                            hist[uid] = h[-3:]
                    else:
                        hist[uid] = [(t, x, y)]
                    if hp < p[2] - 0.5:
                        if kind == "elephant" and vils:        # spear range: nearest villager when hit
                            spear_d.append(min(math.hypot(x - vx, y - vy) for vx, vy in vils))
                        if kind == "villager":                 # hit by an elephant?
                            eles = [(ex, ey) for (ex, ey, _, k, _) in cur.values() if k == "elephant"]
                            if eles and min(math.hypot(x - ex, y - ey) for ex, ey in eles) < 3.5:
                                ele_hits.append(round(p[2] - hp, 1))
                                if uid in last_hit:
                                    ele_hit_gap.append(round(t - last_hit[uid], 2))
                                last_hit[uid] = t
            pos.update(cur)                                # deltas: units not in this record keep their state
    print("files:", files)
    for k, xs in speeds.items():
        if xs:
            print("%-9s n=%5d  tiles/s p50 %.2f  p90 %.2f  p97 %.2f" % (k, len(xs), q(xs, .5), q(xs, .9), q(xs, .97)))
    print("spear thrown at elephant: distance villager-elephant p10 %s p50 %s p90 %s (n=%d)" % (
        q(spear_d, .1), q(spear_d, .5), q(spear_d, .9), len(spear_d)))
    print("elephant hit on villager: damage %s (n=%d); gap between hits p50 %s" % (
        sorted(set(ele_hits))[:6], len(ele_hits), q(ele_hit_gap, .5)))


if __name__ == "__main__":
    main()
