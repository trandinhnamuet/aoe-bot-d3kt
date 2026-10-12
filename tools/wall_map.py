"""ASCII map of a player's town at given minutes of a recording: forest T, water ~, rock/static #,
house H (deleted later: h), other building B, farm f, TC C, villagers v, enemy soldiers e, open '.'.

python wall_map.py FILE PLAYER_NAME MIN[,MIN...] [R=26]
"""
import math
import os
import sys

sys.path.insert(0, r"D:\Game\AoE-MapCap")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapcap.rawrec import iter_records  # noqa: E402
import wall_study as WS  # noqa: E402


def main():
    path = sys.argv[1]
    if not os.path.exists(path):
        path = os.path.join(WS.RAW, path)
    who = sys.argv[2]
    mins = [float(m) for m in sys.argv[3].split(",")]
    R = int(sys.argv[4]) if len(sys.argv) > 4 else 26
    defs, hdr, units, statics = {}, None, {}, {}
    owner = None
    tc = None
    todo = sorted(m * 60000 for m in mins)
    for tag, pl in iter_records(path):
        if tag == b"H":
            hdr = pl
            owner = next(p[0] for p in hdr["players"] if p[3] == who)
        elif tag == b"D":
            for rec in pl:
                defs[rec[0]] = (rec[2], rec[3], rec[4], rec[5])
        elif tag == b"S":
            statics = {int(r["uid"]): r for r in pl["units"]}
        elif tag == b"Q":
            for u in pl["removed"].tolist():
                statics.pop(int(u), None)
            for r in pl["units"]:
                statics[int(r["uid"])] = r
        elif tag == b"F":
            if pl["full_units"]:
                units = {int(r["uid"]): r for r in pl["units"]}
            else:
                for u in pl["removed"].tolist():
                    units.pop(int(u), None)
                for r in pl["units"]:
                    units[int(r["uid"])] = r
            if tc is None:
                for r in units.values():
                    d = defs.get(int(r["def"]))
                    if d and d[2] == WS.TC and int(r["owner"]) == owner:
                        tc = (float(r["x"]), float(r["y"]))
            if todo and pl["t"] >= todo[0]:
                todo.pop(0)
                draw(hdr, defs, statics, units, owner, tc, pl["t"], R)
                if not todo:
                    return


def draw(hdr, defs, statics, units, owner, tc, t, R):
    W, H = hdr["map_w"], hdr["map_h"]
    cx, cy = int(tc[0]), int(tc[1])
    g = {}
    for yy in range(cy - R, cy + R + 1):
        for xx in range(cx - R, cx + R + 1):
            if not (0 <= xx < W and 0 <= yy < H):
                g[(xx, yy)] = " "
            elif int(hdr["terrain"][yy, xx]) in WS.WATER:
                g[(xx, yy)] = "~"
            else:
                g[(xx, yy)] = "."
    for r in list(statics.values()) + list(units.values()):
        d = defs.get(int(r["def"]))
        if not d:
            continue
        utype, name, dat, cls = d
        x, y = float(r["x"]), float(r["y"])
        if utype == 90:
            if int(r["status"]) <= 2 or float(r["ramount"]) > 0:
                if (int(x), int(y)) in g:
                    g[(int(x), int(y))] = "T"
        elif utype == 10 and cls != 14 and (int(x), int(y)) in g:
            g[(int(x), int(y))] = "#"
        elif utype == 80:
            s = WS.SIZE.get(dat, 2)
            ch = "H" if dat == WS.HOUSE else ("C" if dat == WS.TC else ("f" if dat == WS.FARM else "B"))
            if int(r["owner"]) != owner:
                ch = ch.lower() if ch != "f" else "f"
                ch = "x" if ch in "hcb" else ch
            x0, y0 = int(math.floor(x - s / 2 + 1e-3)), int(math.floor(y - s / 2 + 1e-3))
            for yy in range(y0, y0 + s):
                for xx in range(x0, x0 + s):
                    if (xx, yy) in g:
                        g[(xx, yy)] = ch
        elif utype == 70 and int(r["status"]) <= 2:
            k = (int(x), int(y))
            if k in g and g[k] == ".":
                g[k] = "v" if int(r["owner"]) == owner and name.lower().startswith(("man", "vill", "farmer", "lumber", "forager", "miner", "builder", "hunter", "fisher", "repair")) else \
                       ("e" if int(r["owner"]) not in (0, owner) else ("u" if int(r["owner"]) == owner else "a"))
    print("t=%d:%02d  TC (%d,%d)  rows y=%d..%d, cols x=%d..%d" % (t // 60000, (t // 1000) % 60, cx, cy, cy - R, cy + R, cx - R, cx + R))
    for yy in range(cy - R, cy + R + 1):
        print("%4d " % yy + "".join(g.get((xx, yy)) or "." for xx in range(cx - R, cx + R + 1)))
    print()


if __name__ == "__main__":
    main()
