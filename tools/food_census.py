"""How much natural food each player has around its town center at the start of a recorded match:
berry bushes, gazelles, elephants within 20 / 30 / 40 tiles. Compares the players' games with the bots'.

python food_census.py <raw dir> [n files]"""
import math
import os
import pickle
import statistics as st
import struct
import sys
import zlib

sys.path.insert(0, r"D:\Game\AoE-MapCap")
from mapcap.rawrec import MAGIC  # noqa: E402

RAW = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 9
KINDS = {59: "bush", 65: "gazelle", 48: "elephant"}


def census(path):
    defs = {}
    statics = None
    tcs = {}
    animals = []
    with open(path, "rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            return None
        nf = 0
        while nf < 60:
            head = f.read(5)
            if len(head) < 5:
                break
            n = struct.unpack("<I", head[1:])[0]
            data = f.read(n)
            tag = head[:1]
            if tag not in (b"D", b"S", b"F"):
                continue
            pl = pickle.loads(zlib.decompress(data))
            if tag == b"D":
                for rec in pl:
                    defs[rec[0]] = rec[4]
            elif tag == b"S" and statics is None:
                statics = pl["units"]
            elif tag == b"F":
                nf += 1
                if pl["full_units"] or not animals:
                    for r in pl["units"]:
                        d = defs.get(int(r["def"]))
                        if d == 109 and int(r["owner"]) > 0:
                            tcs.setdefault(int(r["owner"]), (float(r["x"]), float(r["y"])))
                        elif d in (65, 48):
                            animals.append((KINDS[d], float(r["x"]), float(r["y"])))
    items = list(animals)
    if statics is not None:
        for r in statics:
            if defs.get(int(r["def"])) == 59:
                items.append(("bush", float(r["x"]), float(r["y"])))
    out = {}
    for p, (tx, ty) in tcs.items():
        c = {}
        for kind, x, y in items:
            d = math.hypot(x - tx, y - ty)
            for R in (20, 30, 40):
                if d <= R:
                    c[(kind, R)] = c.get((kind, R), 0) + 1
        out[p] = c
    return out


files = sorted([f for f in os.listdir(RAW) if f.endswith(".aoerec")], reverse=True)[:N]
rows = []
for f in files:
    res = census(os.path.join(RAW, f))
    if not res:
        continue
    for p, c in res.items():
        rows.append(c)
        print(f[:17], "P%d" % p, " ".join("%s<%d:%d" % (k[0][:4], k[1], c.get(k, 0))
                                         for k in [("bush", 30), ("gazelle", 20), ("gazelle", 30), ("gazelle", 40),
                                                   ("elephant", 20), ("elephant", 30), ("elephant", 40)]))
print("\nmedian over %d players:" % len(rows))
for kind in ("bush", "gazelle", "elephant"):
    print("  %-8s" % kind, "  ".join("<%d: %s" % (R, st.median([r.get((kind, R), 0) for r in rows])) for R in (20, 30, 40)))
