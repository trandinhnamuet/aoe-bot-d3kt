"""Random hunting scenarios and batch runs: the success rates that gate a change before the arena.

python -m sim.scenarios lure [N=200]      elephant 10-30 tiles out, random forests
python -m sim.scenarios herd [N=200]      herd of 3-5 gazelles 12-25 tiles out, 1 or 2 pushers
python -m sim.scenarios herd 50 --show    prints the task log of every failure
"""
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain import geom                      # noqa: E402
from brain.tasks.herd import HerdPush       # noqa: E402
from brain.tasks.lure import Lure           # noqa: E402
from sim.sim import Sim                     # noqa: E402


def scene(seed, forests=3):
    params = {}
    if os.environ.get("SIM_LAG"):                # e.g. SIM_LAG=1.5: the arena runs at x1.5 (lag in game seconds)
        params["LAG"] = float(os.environ["SIM_LAG"])
    sim = Sim(seed=seed, params=params)
    r = sim.rng
    for _ in range(forests):
        for _try in range(30):
            cx, cy = r.uniform(4, sim.W - 4), r.uniform(4, sim.H - 4)
            if math.hypot(cx - sim.tc[0], cy - sim.tc[1]) > 7:
                sim.add_forest(cx, cy, r.uniform(2, 4))
                break
    return sim


def spot(sim, dmin, dmax):
    r = sim.rng
    for _ in range(100):
        d, a = r.uniform(dmin, dmax), r.uniform(0, 2 * math.pi)
        x, y = sim.tc[0] + math.cos(a) * d, sim.tc[1] + math.sin(a) * d
        if 3 < x < sim.W - 3 and 3 < y < sim.H - 3 and sim.passable(int(x), int(y)):
            return x, y
    return sim.tc[0] + dmin, sim.tc[1]


def run_lure(seed, max_t=240):
    sim = scene(seed)
    home = sim.tc
    if os.environ.get("SIM_LURE_HOME") == "pit":        # the nearest dropsite is a pit 12-20 tiles from the TC
        px, py = spot(sim, 12, 20)
        px, py = int(px) + 0.5, int(py) + 0.5
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                sim.block(int(px) + dx, int(py) + dy)
        home = (px, py)
    r = sim.rng
    for _ in range(100):
        d, a = r.uniform(10, 30), r.uniform(0, 2 * math.pi)
        ex, ey = home[0] + math.cos(a) * d, home[1] + math.sin(a) * d
        if 3 < ex < sim.W - 3 and 3 < ey < sim.H - 3 and sim.passable(int(ex), int(ey)):
            break
    eid = sim.add_elephant(ex, ey)
    lurer = sim.add_villager(home[0] + 2.5, home[1] + 2.5)
    n_wait = int(os.environ.get("SIM_LURE_WAITERS", "3"))     # 0 = the lurer kills it alone round the home
    waiters = [sim.add_villager(home[0] - 2.5 + i, home[1] + 2.5) for i in range(n_wait)]
    task = Lure(eid, lurer, waiters, home=None if home == sim.tc else home)
    sim.run([task], max_t=max_t)
    ele = sim.ents[eid]
    vils = [sim.ents[i] for i in [lurer] + waiters]
    deaths = sum(1 for v in vils if not v.alive)
    who = [("lurer" if v.id == lurer else "waiter") + "@" + next((e[1] for e in sim.events if e[0] >= 0 and False), task.state)
           for v in vils if not v.alive]
    dead_t = [ev[0] for ev in sim.events if ev[1] == "dead" and ev[2] == "villager"]
    kill_t = next((t for t, m in task.log if "everybody attacks" in m), None)
    phase = ["kill" if kill_t is not None and t >= kill_t else "run" for t in dead_t]
    edge = geom.tc_edge_dist(ele.x, ele.y, *home)
    near = edge <= 9.0
    ok = task.done and not ele.alive and near
    # the user's standard: dead within 4 tiles of the home building's edge, nobody dead, <= 150 s
    strict = task.done and not ele.alive and edge <= 4.0 and deaths == 0 and sim.t <= 150.0
    return dict(seed=seed, ok=ok, strict=strict, edge=round(edge, 1), t=round(sim.t, 1), deaths=deaths,
                lurer_hp=round(sim.ents[lurer].hp, 1),
                dead_lurer=int(not sim.ents[lurer].alive), dead_phase=phase,
                reason=task.reason if task.failed else ("" if strict else "elephant died %.1f from home, %d deaths, %.0f s" %
                                                        (edge, deaths, sim.t)),
                dist0=round(math.hypot(ex - home[0], ey - home[1]), 1), log=task.log)


def run_herd(seed, max_t=200, two=None, helpers=False):
    sim = scene(seed)
    n = sim.rng.randint(3, 5)
    d0, d1 = [float(x) for x in os.environ.get("SIM_HERD_D", "12,25").split(",")]   # herd distance range
    hx, hy = spot(sim, d0, d1)
    gids = sim.add_herd(hx, hy, n)
    for g in gids:                                   # a scout saw the herd: the task starts from memory
        sim.seen[g] = (sim.ents[g].x, sim.ents[g].y, 0.0)
    if two is None:
        two = sim.rng.random() < 0.5
    pushers = [sim.add_villager(sim.tc[0] + 2.5, sim.tc[1] + 2.5)]
    if two:
        pushers.append(sim.add_villager(sim.tc[0] - 2.5, sim.tc[1] + 2.5))
    task = HerdPush(gids, pushers)
    if helpers:                                      # two villagers at the TC join the kill (the brain's helpers)
        task.helpers = [sim.add_villager(sim.tc[0] + 3.0, sim.tc[1] - 2.0), sim.add_villager(sim.tc[0] - 3.0, sim.tc[1] - 2.0)]
    sim.run([task], max_t=max_t)
    dead_home = sum(1 for g in gids if not sim.ents[g].alive and geom.tc_edge_dist(sim.ents[g].x, sim.ents[g].y, *sim.tc) <= 6.5)
    dead_out = sum(1 for g in gids if not sim.ents[g].alive) - dead_home
    home = sum(1 for g in gids if sim.ents[g].alive and geom.tc_edge_dist(sim.ents[g].x, sim.ents[g].y, *sim.tc) <= 6.5)
    ok = dead_home >= max(2, (len(gids) + 1) // 2)
    # the user's standard: EVERY gazelle dies within 4 tiles of the TC edge, none out in the field,
    # the whole push (first order to last kill) within 120 s
    dead_home4 = sum(1 for g in gids if not sim.ents[g].alive and geom.tc_edge_dist(sim.ents[g].x, sim.ents[g].y, *sim.tc) <= 4.0)
    strict = dead_home4 == len(gids) and sim.t <= 120.0
    return dict(seed=seed, ok=ok, strict=strict, dead_home4=dead_home4, t=round(sim.t, 1), n=len(gids), two=two, dead_home=dead_home, dead_out=dead_out,
                alive_home=home, reason=task.reason, mode=task.mode, dist0=round(math.hypot(hx - sim.tc[0], hy - sim.tc[1]), 1),
                log=task.log)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "lure"
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 200
    show = "--show" in sys.argv
    two = True if "--two" in sys.argv else (False if "--one" in sys.argv else None)
    helpers = "--helpers" in sys.argv
    rows = [run_lure(s) if what == "lure" else run_herd(s, two=two, helpers=helpers) for s in range(n)]
    oks = [r for r in rows if r["ok"]]
    print("%s: %d/%d ok (%.0f%%)" % (what, len(oks), n, 100.0 * len(oks) / n))
    if what == "lure":
        phases = [p for r in rows for p in r["dead_phase"]]
        print("deaths %d (lurers %d; in run %d, in kill %d) | lurer hp at the end p50 %.0f | time p50 %.0f s (ok runs)" % (
            sum(r["deaths"] for r in rows), sum(r["dead_lurer"] for r in rows), phases.count("run"), phases.count("kill"),
            st.median(r["lurer_hp"] for r in rows), st.median(r["t"] for r in oks) if oks else 0))
        sok = [r for r in rows if r["strict"]]
        print("STRICT (dead <= 4 tiles from the home edge, 0 deaths, <= 150 s): %d/%d | edge p50 %.1f p90 %.1f | too far %d, deaths %d, slow %d, not done %d" % (
            len(sok), n, st.median(r["edge"] for r in rows), sorted(r["edge"] for r in rows)[int(0.9 * n)],
            sum(1 for r in rows if r["ok"] and r["edge"] > 4.0), sum(1 for r in rows if r["deaths"]),
            sum(1 for r in rows if r["ok"] and r["t"] > 150), sum(1 for r in rows if not r["ok"])))
    else:
        print("gazelles killed at home %d, killed out in the field %d, alive at home %d | time p50 %.0f s (ok runs)" % (
            sum(r["dead_home"] for r in rows), sum(r["dead_out"] for r in rows), sum(r["alive_home"] for r in rows),
            st.median(r["t"] for r in oks) if oks else 0))
        for lab, flag in (("one pusher", False), ("two pushers", True)):
            sub = [r for r in rows if r["two"] == flag]
            if sub:
                print("  %s: %d/%d ok | STRICT (all dead <= 4 tiles from the TC edge, <= 120 s): %d/%d; all dead at home but slow: %d; gazelles %d, dead <= 4 tiles %d" % (
                    lab, sum(1 for r in sub if r["ok"]), len(sub), sum(1 for r in sub if r["strict"]), len(sub),
                    sum(1 for r in sub if r["dead_home4"] == r["n"] and not r["strict"]),
                    sum(r["n"] for r in sub), sum(r["dead_home4"] for r in sub)))
    reasons = {}
    for r in rows:
        if not r["ok"]:
            key = r["reason"].split(" after ")[0].split(" (")[0] or "not enough killed at home"
            reasons[key] = reasons.get(key, 0) + 1
    for k, c in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print("  fail: %-45s %d" % (k, c))
    if show:
        for r in rows:
            if not r["ok"]:
                print("--- seed %d dist0 %s %s" % (r["seed"], r["dist0"], {k: v for k, v in r.items() if k not in ("log", "seed", "dist0")}))
                for t, m in r["log"][-8:]:
                    print("   %6.1f %s" % (t, m))


if __name__ == "__main__":
    main()
