"""Trace one scenario second by second: python -m sim.trace lure|herd SEED [every=1.0]"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain import geom                      # noqa: E402
from brain.tasks.herd import HerdPush       # noqa: E402
from brain.tasks.lure import Lure           # noqa: E402
from sim import scenarios                   # noqa: E402


def main():
    what, seed = sys.argv[1], int(sys.argv[2])
    every = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    sim = scenarios.scene(seed)
    if what == "lure":
        ex, ey = scenarios.spot(sim, 10, 30)
        eid = sim.add_elephant(ex, ey)
        lurer = sim.add_villager(sim.tc[0] + 2.5, sim.tc[1] + 2.5)
        import os
        n_wait = int(os.environ.get("SIM_LURE_WAITERS", "3"))
        waiters = [sim.add_villager(sim.tc[0] - 2.5 + i, sim.tc[1] + 2.5) for i in range(n_wait)]
        task = Lure(eid, lurer, waiters)
        watch = [eid]
    else:
        n = sim.rng.randint(3, 5)
        hx, hy = scenarios.spot(sim, 12, 25)
        watch = sim.add_herd(hx, hy, n)
        for g in watch:
            sim.seen[g] = (sim.ents[g].x, sim.ents[g].y, 0.0)
        two = sim.rng.random() < 0.5
        pushers = [sim.add_villager(sim.tc[0] + 2.5, sim.tc[1] + 2.5)]
        if two:
            pushers.append(sim.add_villager(sim.tc[0] - 2.5, sim.tc[1] + 2.5))
        task = HerdPush(watch, pushers)
    print("TC", sim.tc)
    next_t, ev_i = 0.0, 0
    n_tick = int(round(0.5 / sim.p["DT"]))
    i = 0
    while sim.t < 240 and not (task.done or task.failed):
        sim._step()
        if i % n_tick == 0:
            task.tick(sim, sim)
        task.micro(sim, sim)
        i += 1
        if sim.t >= next_t:
            next_t += every
            vils = " ".join("v%d(%.1f,%.1f)%s%.0f" % (e.id, e.x, e.y, "*" if e.id == getattr(task, "lurer", None) else "", e.hp)
                            for e in sim.ents.values() if e.kind == "villager")
            ani = " ".join("%s%d(%.1f,%.1f)%.0f%s" % (e.kind[0], e.id, e.x, e.y, e.hp,
                                                      ("/" + e.st["mode"]) if e.kind == "elephant" else "")
                           for e in sim.ents.values() if e.kind != "villager" and e.alive)
            lu = getattr(task, "lurer", None)
            extra = ""
            if lu and sim.ents.get(lu) and sim.ents.get(watch[0]):
                extra = " d=%.1f" % math.hypot(sim.ents[lu].x - sim.ents[watch[0]].x, sim.ents[lu].y - sim.ents[watch[0]].y)
            print("%6.1f %-8s %s%s | %s | %s" % (sim.t, task.state + "/" + getattr(task, "mode", ""), ani, extra, vils,
                                                 " ".join(e.action[0][0] for e in sim.ents.values() if e.kind == "villager")))
            while ev_i < len(sim.events):
                print("        ev", sim.events[ev_i])
                ev_i += 1
    for t, m in task.log:
        print("log %6.1f %s" % (t, m))
    print("end", task.state, task.reason)


if __name__ == "__main__":
    main()
