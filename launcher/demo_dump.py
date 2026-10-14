"""Demo dumps for the handbook (tests only, AOESOLO_DEMO_DIR=<folder>): at the moment an algorithm runs, the
bot writes what it saw and computed to a JSON file, so a real case can be drawn afterwards."""
import json
import os

import gamestate as gs

LIMIT = {"granary": 1, "pit": 1, "wall": 1, "villagers": 1, "army": 1, "lure": 2, "vis": 2}


def enabled():
    return bool(os.environ.get("AOESOLO_DEMO_DIR"))


def write(b, kind, data):
    d = os.environ.get("AOESOLO_DEMO_DIR")
    if not d:
        return
    done = b.__dict__.setdefault("_demo_done", {})
    n = done.get(kind, 0)
    if n >= LIMIT.get(kind, 1):
        return
    done[kind] = n + 1
    try:
        os.makedirs(d, exist_ok=True)
        data.update(kind=kind, player=b.me, t=round(b.now(), 1), W=b.r.W, H=b.r.H)
        tc = b.tc()
        if tc is not None:
            data.setdefault("tc", [tc.x, tc.y])
        path = os.path.join(d, "P%d_%s_%d.json" % (b.me, kind, n))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        b.say("DEMO dump %s -> %s" % (kind, path))
    except Exception as e:  # noqa: BLE001
        b.say("DEMO dump %s failed: %r" % (kind, e))


def obj_row(o):
    return [o.type, o.kind, o.cls, round(o.x, 2), round(o.y, 2), round(o.rx, 2), round(o.ry, 2), o.owner,
            o.name, round(float(o.amount or 0), 1), round(float(o.hp or 0), 1)]


def window(b, cx, cy, r):
    """The tiles and the known objects within r tiles of (cx, cy): blk rows (1 = blocked), explored rows."""
    W, H = b.r.W, b.r.H
    x0, y0 = max(0, int(cx - r)), max(0, int(cy - r))
    x1, y1 = min(W, int(cx + r) + 1), min(H, int(cy + r) + 1)
    blk = [[b.pm.blk[y * W + x] for x in range(x0, x1)] for y in range(y0, y1)]
    exp = [[1 if b.s.explored(x, y) else 0 for x in range(x0, x1)] for y in range(y0, y1)]
    elev = [[b.r.elev_at(x, y) for x in range(x0, x1)] for y in range(y0, y1)]
    shape = [[1 if b.r.shape_at(x, y) else 0 for x in range(x0, x1)] for y in range(y0, y1)]
    s = b.s
    objs = [obj_row(o) for o in s.mine + s.gaia + s.enemy + s.enemy_buildings_seen
            if x0 - 2 <= o.x < x1 + 2 and y0 - 2 <= o.y < y1 + 2]
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "blk": blk, "explored": exp, "elev": elev, "slope": shape, "objs": objs}


def lure_sample(b, w):
    """Fast loop: positions of every running lure ~3 times a second; the record is written when the lure ends."""
    import time
    rec = b.__dict__.setdefault("_demo_lures", {})
    now = time.time()
    for key, task in list(b.ntasks.items()):
        if key[0] != "lure":
            continue
        R = rec.setdefault(key, {"samples": [], "last": 0.0, "written": False, "eid": task.eid})
        if R["written"]:
            continue
        if task.done or getattr(task, "failed", False):
            R["written"] = True
            hx, hy = task._home(w)
            write(b, "lure", {"eid": task.eid, "home": [hx, hy], "result": "done" if task.done else
                              "failed: %s" % getattr(task, "reason", "?"), "samples": R["samples"]})
            continue
        if now - R["last"] < 0.3:
            continue
        R["last"] = now
        try:
            hx, hy = task._home(w)
            R["home"] = [hx, hy]
        except Exception:  # noqa: BLE001
            pass
        e = w.track(task.eid)
        lu = w.unit(task.lurer)
        ws = []
        for i in task.waiters:
            u = w.unit(i)
            if u is not None:
                ws.append([i, round(u.x, 2), round(u.y, 2), round(u.hp, 1)])
        R["samples"].append({
            "t": round(w.now, 2), "state": task.state,
            "ele": [round(e.x, 2), round(e.y, 2), round(e.hp, 1)] if e is not None else None,
            "lurer": [task.lurer, round(lu.x, 2), round(lu.y, 2), round(lu.hp, 1)] if lu is not None else None,
            "waiters": ws, "chasing": w.target_of(task.eid)})
    # (a finished lure leaves b.ntasks at once - its record is written when its key is gone)
    for key, R in rec.items():
        if not R["written"] and key not in b.ntasks and R["samples"]:
            R["written"] = True
            write(b, "lure", {"eid": R["eid"], "home": R.get("home"), "result": "ended", "samples": R["samples"]})
