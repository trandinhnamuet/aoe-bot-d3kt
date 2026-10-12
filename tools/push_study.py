"""Why do the bots' herd pushes stall where the players' do not? Measured on recordings:

For every villager-gazelle encounter (villager within REACT_R of a live gazelle) we note whether the
gazelle hopped within REACT_S seconds, the villager's distance at that moment, and where the villager
stood relative to the gazelle's way home (angle between gazelle->villager and gazelle->TC: 180 = the
villager is straight behind it, the hop goes home). Also "stalls": a villager standing within 2.5 tiles
of a gazelle for more than STALL_S seconds while the gazelle does not move.

python push_study.py [N_FILES=4]      (AOEREC_DIR=... selects the arena recordings)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gazelle_study import RAW, records, VILLAGERS, TC, GAZELLE  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
REACT_R, REACT_S, STALL_S, MOVE_EPS = 3.5, 2.5, 4.0, 0.06


def q(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None


def main():
    files = sorted(f for f in os.listdir(RAW) if f.endswith(".aoerec"))[-N:]
    enc = []            # encounters: dict(d, angle, reacted)
    stalls = 0
    hops_home = hops_all = 0
    for fn in files:
        defs, gaz, vil, tcs = {}, {}, {}, {}
        enc_open = {}   # (vid, gid) -> dict(t0, d, angle, gx, gy)
        still = {}      # (vid, gid) -> since
        for tag, pl in records(os.path.join(RAW, fn)):
            if tag == b"D":
                for rec in pl:
                    defs[rec[0]] = rec[4]
                continue
            if tag != b"F":
                continue
            t = pl["t"] / 1000.0
            if pl["full_units"]:
                gaz.clear()
                vil.clear()
            else:
                for u in pl["removed"].tolist():
                    gaz.pop(int(u), None)
                    vil.pop(int(u), None)
            for r in pl["units"]:
                did = defs.get(int(r["def"]))
                uid = int(r["uid"])
                if did == GAZELLE:
                    prev = gaz.get(uid)
                    gaz[uid] = (float(r["x"]), float(r["y"]), float(r["hp"]), prev[0] if prev else float(r["x"]),
                                prev[1] if prev else float(r["y"]))
                elif did in VILLAGERS:
                    vil[uid] = (float(r["x"]), float(r["y"]), int(r["owner"]))
                elif did == TC:
                    tcs.setdefault(int(r["owner"]), (float(r["x"]), float(r["y"])))
                else:
                    gaz.pop(uid, None)
                    vil.pop(uid, None)
            if not gaz or not vil:
                continue
            for gid, (gx, gy, ghp, pgx, pgy) in gaz.items():
                if ghp <= 0:
                    continue
                moved = math.hypot(gx - pgx, gy - pgy) > MOVE_EPS
                for vid, (vx, vy, owner) in vil.items():
                    d = math.hypot(vx - gx, vy - gy)
                    key = (vid, gid)
                    if d <= REACT_R:
                        if key not in enc_open:
                            tc = tcs.get(owner)
                            ang = None
                            if tc:
                                a1 = math.atan2(vy - gy, vx - gx)
                                a2 = math.atan2(tc[1] - gy, tc[0] - gx)
                                ang = abs((a1 - a2 + math.pi) % (2 * math.pi) - math.pi) * 180 / math.pi
                            enc_open[key] = {"t0": t, "d": d, "angle": ang, "gx": gx, "gy": gy, "owner": owner, "reacted": False}
                        e = enc_open[key]
                        if not e["reacted"] and math.hypot(gx - e["gx"], gy - e["gy"]) > 0.8:
                            e["reacted"] = True
                            e["react_t"] = t - e["t0"]
                            tc = tcs.get(owner)
                            if tc:
                                hops_all += 1
                                if math.hypot(gx - tc[0], gy - tc[1]) < math.hypot(e["gx"] - tc[0], e["gy"] - tc[1]) - 0.3:
                                    hops_home += 1
                        if d <= 2.5 and not moved:
                            still.setdefault(key, t)
                            if t - still[key] > STALL_S:
                                stalls += 1
                                still[key] = t + 999
                        else:
                            still.pop(key, None)
                    else:
                        if key in enc_open:
                            e = enc_open.pop(key)
                            if t - e["t0"] >= REACT_S or e["reacted"]:
                                enc.append(e)
                        still.pop(key, None)
    print("files:", files)
    print("encounters (villager within %.1f tiles of a live gazelle): %d" % (REACT_R, len(enc)))
    for lo, hi in ((0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 3.5)):
        sub = [e for e in enc if lo <= e["d"] < hi]
        if sub:
            r = sum(1 for e in sub if e["reacted"]) / len(sub)
            rt = q([e["react_t"] for e in sub if e["reacted"]], .5)
            print("  first seen at %.1f-%.1f tiles: n=%4d  gazelle hopped within %.0fs: %3.0f%%  (median %s s)" % (
                lo, hi, len(sub), REACT_S, 100 * r, rt))
    angs = [e["angle"] for e in enc if e["reacted"] and e["angle"] is not None]
    print("villager's angle off the gazelle's way home when it hopped (180 = straight behind it): p25 %s median %s p75 %s" % (
        q(angs, .25), q(angs, .5), q(angs, .75)))
    print("hops that brought the gazelle closer to the TC: %d of %d (%.0f%%)" % (hops_home, hops_all, 100.0 * hops_home / max(1, hops_all)))
    print("stalls (villager <= 2.5 tiles, gazelle still for > %.0f s): %d" % (STALL_S, stalls))


if __name__ == "__main__":
    main()
