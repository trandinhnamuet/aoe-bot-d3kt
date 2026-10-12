"""How gazelles react to villagers, measured on real recorded games (AoE-MapCap .aoerec).

For every gazelle we follow its position at 25 samples/s. A "flee" starts when it begins to move after
standing still; at that moment we note the nearest villager (any player), whether it was just hit,
then follow the run until it stands again: trigger distance, run length, run time, direction error
(run direction vs. the direction away from the villager).

python gazelle_study.py [N_FILES=9] -> tools/learned/gazelle_events.json + printed statistics
"""
import json
import math
import os
import pickle
import statistics as st
import struct
import sys
import zlib

import numpy as np

sys.path.insert(0, r"D:\Game\AoE-MapCap")
from mapcap.rawrec import MAGIC  # noqa: E402

RAW = os.environ.get("AOEREC_DIR", r"D:\Game\AoE-MapCap\dist\Video\Raw")   # AOEREC_DIR=... for the arena recordings
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 9
GAZELLE = 65
VILLAGERS = {83, 118, 120, 122, 123, 251, 124, 259, 156}
TC = 109
MOVE_EPS = 0.06          # tiles per sample (40 ms) = moving
STILL_SAMPLES = 20       # 0.8 s standing still before a flee counts as a new one


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


def study(path):
    defs = {}
    gaz = {}            # uid -> (x, y, hp)
    vil = {}            # uid -> (x, y, owner)
    tcs = {}            # owner -> (x, y)
    track = {}          # uid -> state dict
    events = []
    for tag, pl in records(path):
        if tag == b"D":
            for rec in pl:
                defs[rec[0]] = rec[4]
            continue
        if tag != b"F":
            continue
        t = pl["t"]
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
                gaz[uid] = (float(r["x"]), float(r["y"]), float(r["hp"]))
            elif did in VILLAGERS:
                vil[uid] = (float(r["x"]), float(r["y"]), int(r["owner"]))
            elif did == TC:
                tcs.setdefault(int(r["owner"]), (float(r["x"]), float(r["y"])))
            else:
                gaz.pop(uid, None)          # it died: the uid now holds something else
                vil.pop(uid, None)
        if not gaz:
            continue
        va = np.array([(x, y) for x, y, _ in vil.values()]) if vil else None
        vo = [o for _, _, o in vil.values()]
        for uid, (x, y, hp) in gaz.items():
            s = track.get(uid)
            if va is not None and len(va):
                d2 = (va[:, 0] - x) ** 2 + (va[:, 1] - y) ** 2
                k = int(np.argmin(d2))
                nd, nv, no = math.sqrt(d2[k]), (va[k, 0], va[k, 1]), vo[k]
            else:
                nd, nv, no = 99.0, None, None
            if s is None:
                track[uid] = {"x": x, "y": y, "hp": hp, "still": 0, "run": None, "hp_hist": [(t, hp)]}
                continue
            step = math.hypot(x - s["x"], y - s["y"])
            s["hp_hist"] = [(tt, h) for tt, h in s["hp_hist"] if t - tt < 1000] + [(t, hp)]
            moving = step > MOVE_EPS
            if s["run"] is None:
                if moving and s["still"] >= STILL_SAMPLES:
                    hit = any(h > hp + 0.5 for _, h in s["hp_hist"])
                    s["run"] = {"t0": t, "x0": s["x"], "y0": s["y"], "d": nd, "vx": nv[0] if nv else None,
                                "vy": nv[1] if nv else None, "owner": no, "hit": hit, "hp0": hp, "path": 0.0}
                s["still"] = 0 if moving else s["still"] + 1
            else:
                run = s["run"]
                run["path"] += step
                if moving:
                    s["still"] = 0
                else:
                    s["still"] += 1
                    if s["still"] >= 5:                     # 0.2 s still: the run is over
                        dx, dy = x - run["x0"], y - run["y0"]
                        ev = {"t": round(run["t0"] / 1000, 2), "trigger_d": round(run["d"], 2), "hit": run["hit"],
                              "hp": run["hp0"], "run_len": round(math.hypot(dx, dy), 2), "path": round(run["path"], 2),
                              "dur": round((t - run["t0"]) / 1000 - 0.2, 2)}
                        if run["vx"] is not None and math.hypot(dx, dy) > 0.3:
                            ax, ay = run["x0"] - run["vx"], run["y0"] - run["vy"]
                            a1 = math.atan2(dy, dx)
                            a2 = math.atan2(ay, ax)
                            ev["dir_err_deg"] = round(math.degrees(abs((a1 - a2 + math.pi) % (2 * math.pi) - math.pi)), 1)
                        tc = tcs.get(run["owner"])
                        if tc:
                            ev["tc_d0"] = round(math.hypot(run["x0"] - tc[0], run["y0"] - tc[1]), 1)
                            ev["tc_d1"] = round(math.hypot(x - tc[0], y - tc[1]), 1)
                        events.append(ev)
                        s["run"] = None
            s["x"], s["y"], s["hp"] = x, y, hp
    return events


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def main():
    files = sorted([f for f in os.listdir(RAW) if f.endswith(".aoerec")], reverse=True)[:N]
    allev = []
    for f in files:
        ev = study(os.path.join(RAW, f))
        print(f, len(ev), "flee runs", flush=True)
        allev += ev
    json.dump(allev, open(os.path.join(OUT, "gazelle_events.json"), "w"), indent=0)
    near = [e for e in allev if e["trigger_d"] < 12]
    for label, sel in (("not hit", [e for e in near if not e["hit"]]), ("hit", [e for e in near if e["hit"]])):
        if not sel:
            continue
        print("\n== %s: %d runs" % (label, len(sel)))
        for k in ("trigger_d", "run_len", "path", "dur", "dir_err_deg"):
            xs = [e[k] for e in sel if e.get(k) is not None]
            if xs:
                print("  %-11s p10 %5.2f  p25 %5.2f  median %5.2f  p75 %5.2f  p90 %5.2f" % (
                    k, q(xs, .1), q(xs, .25), st.median(xs), q(xs, .75), q(xs, .9)))
    nh = [e for e in near if not e["hit"]]
    if nh:
        print("\ntrigger distance histogram (not hit):")
        for lo in range(0, 12):
            n = sum(1 for e in nh if lo <= e["trigger_d"] < lo + 1)
            print("  %2d-%2d: %s %d" % (lo, lo + 1, "#" * (n // 3), n))
    home = [e for e in allev if e.get("tc_d0") is not None and e["tc_d1"] < e["tc_d0"] - 0.5 and e["trigger_d"] < 6]
    print("\nruns that brought the gazelle closer to its pusher's TC: %d (median gain %.1f tiles)" % (
        len(home), st.median([e["tc_d0"] - e["tc_d1"] for e in home]) if home else 0))


if __name__ == "__main__":
    main()
