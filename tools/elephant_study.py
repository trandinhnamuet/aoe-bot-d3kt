"""How an elephant lure/kill really goes in the user's recorded games: hp lost by the elephant per
spear, time from the first hit to death, villager hp lost around it meanwhile, how many villagers
were within 4 tiles when it died, and how far from the owner's TC.

python elephant_study.py [N_FILES=4]
"""
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gazelle_study import RAW, records, VILLAGERS, TC  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
ELEPHANT = 48


def q(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None


def main():
    files = sorted(f for f in os.listdir(RAW) if f.endswith(".aoerec"))[-N:]
    spear = []
    lures = []
    for fn in files:
        defs = {}
        pos = {}
        tcs = {}
        ele = {}           # uid -> dict(first_hit, hits, vil_hp_lost, last_vil_hp)
        for tag, pl in records(os.path.join(RAW, fn)):
            if tag == b"D":
                for rec in pl:
                    defs[rec[0]] = rec[4]
                continue
            if tag != b"F":
                continue
            t = pl["t"] / 1000.0
            if pl["full_units"]:
                pos.clear()
            else:
                for u in pl["removed"].tolist():
                    pos.pop(int(u), None)
            cur = {}
            for r in pl["units"]:
                tid = defs.get(int(r["def"]))
                if tid == TC:
                    tcs.setdefault(int(r["owner"]), (float(r["x"]), float(r["y"])))
                    continue
                kind = "ele" if tid == ELEPHANT else ("vil" if tid in VILLAGERS else None)
                if kind is None:
                    continue
                cur[int(r["uid"])] = (float(r["x"]), float(r["y"]), float(r["hp"]), kind, int(r["owner"]))
            for uid, (x, y, hp, kind, owner) in cur.items():
                p = pos.get(uid)
                if p is None or p[3] != kind:
                    continue
                if kind == "ele" and hp < p[2] - 0.5:
                    spear.append(round(p[2] - hp, 1))
                    e = ele.setdefault(uid, {"t0": t, "hits": 0, "vhp": 0.0, "x": x, "y": y, "owner": None})
                    e["hits"] += 1
                    e["x"], e["y"], e["t1"] = x, y, t
                    # whose villagers are around: the owner of the nearest villager
                    near = [(math.hypot(vx - x, vy - y), o) for (vx, vy, _, k, o) in cur.values() if k == "vil"]
                    if near:
                        e["owner"] = min(near)[1]
                    if hp <= 0:
                        e["dead"] = t
                        n4 = sum(1 for (vx, vy, _, k, _) in cur.values() if k == "vil" and math.hypot(vx - x, vy - y) <= 4)
                        tc = tcs.get(e["owner"])
                        lures.append({"dur": round(t - e["t0"], 1), "hits": e["hits"], "vil_hp_lost": e["vhp"],
                                      "vils_near": n4, "tc_d": round(math.hypot(x - tc[0], y - tc[1]), 1) if tc else None})
                        del ele[uid]
                if kind == "vil" and hp < p[2] - 0.5:
                    for e in ele.values():
                        if math.hypot(e["x"] - x, e["y"] - y) <= 3.5:
                            e["vhp"] += p[2] - hp
            pos.update(cur)
    print("files:", files)
    print("elephant hp lost per spear: %s (n=%d)" % (sorted(set(spear)), len(spear)))
    print("kills: n=%d | first hit -> death p50 %.0f s | spears p50 %s | villager hp lost per kill p50 %s p90 %s | "
          "villagers within 4 tiles at death p50 %s | distance to TC p50 %s p90 %s" % (
              len(lures), st.median(l["dur"] for l in lures) if lures else 0, q([l["hits"] for l in lures], .5),
              q([l["vil_hp_lost"] for l in lures], .5), q([l["vil_hp_lost"] for l in lures], .9),
              q([l["vils_near"] for l in lures], .5),
              q([l["tc_d"] for l in lures if l["tc_d"] is not None], .5), q([l["tc_d"] for l in lures if l["tc_d"] is not None], .9)))
    for l in sorted(lures, key=lambda l: l["dur"])[:12]:
        print("  ", l)


if __name__ == "__main__":
    main()
