"""NewBrain: the restructured brain, grown out of the old one (KIEN_TRUC_AI.md, step 2).

It subclasses d3kt.Brain and replaces the villager allocation (desired_role / allocate /
assign_leads / berry_six, scattered over six places) with ONE table: brain.plan.demands() ->
brain.jobs.Allocator. The old placement, building, town-centre and military code is kept until its
own step replaces it. Select it with d3kt.Brain = NewBrain before d3kt.run() (arena: --brain new).
"""
import time

import d3kt
import gamestate as gs
from brain import plan
from brain.jobs import Allocator


class NewBrain(d3kt.Brain):
    FOOD_ITEMS_WANTED = d3kt.FOOD_ITEMS_WANTED
    GOLD_PER_STABLE = d3kt.GOLD_PER_STABLE

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.alloc = Allocator()
        self.jobs = {}                      # villager id -> demand name (last tick)
        self.say("NewBrain: one allocation table (brain.plan) drives the villagers")

    # ---------------------------------------------------------------- the villager step
    def villagers(self):
        s = self.s
        vs = sorted(s.villagers, key=lambda v: v.id)
        tc = self.tc()
        if not tc:
            return
        ids = {v.id for v in vs}
        for k in list(self.role):
            if k not in ids:
                del self.role[k]
        if getattr(self, "far_food", False):
            self.food_emergency = True              # sticky (the watchdog clears it): far berries / herds / scouts
        sub = []
        for step in (self.granaries, self.storage_pits, self.hunting_plan):
            t1 = time.time()
            step()
            sub.append((time.time() - t1, step.__name__))
        # the leads of lure / push sites are whoever the allocator gave the site (not assign_leads)
        active = {k for (k, x, y, st) in self.sites if st in ("provoke", "run", "push", "pushed")}
        for vid, k in list(self.leads.items()):
            if k not in active or self.obj_by_id(vid) is None:
                del self.leads[vid]
        try:
            dem = plan.demands(self)
        except Exception as e:  # noqa: BLE001
            self.say("plan error: %r" % (e,))
            return
        jobs = self.alloc.assign(vs, dem, self.jobs)
        self.jobs = jobs
        import demo_dump
        if demo_dump.enabled() and self.now() >= 330 and not self.__dict__.get("_demo_done", {}).get("villagers"):
            rows = []
            by_ptr = {o.ptr: o for o in self.s.gaia + self.s.mine}
            for i, v in enumerate(vs):
                act = self.r.action(v)
                tg = by_ptr.get(act[1]) if act and act[1] else None
                j = jobs.get(v.id)
                rows.append({"id": v.id, "idx": i, "x": round(v.x, 2), "y": round(v.y, 2), "type": v.type,
                             "job": list(j) if isinstance(j, tuple) else j, "amount": round(float(v.amount or 0), 1),
                             "act": [act[0], act[2]] if act else None,
                             "target": [tg.type, round(tg.x, 2), round(tg.y, 2)] if tg is not None else None})
            cnt = {}
            for j in jobs.values():
                k = j[0] if isinstance(j, tuple) else j
                cnt[k] = cnt.get(k, 0) + 1
            tc_ = self.tc()
            demo_dump.write(self, "villagers", {
                "vils": rows, "counts": cnt,
                "demands": [[d.name if isinstance(d.name, str) else list(d.name), d.min, d.max, d.prio] for d in dem],
                "sites": [[list(k) if isinstance(k, tuple) else k, x, y, st] for (k, x, y, st) in self.sites],
                "res": {"food": self.res(0), "wood": self.res(1), "gold": self.res(3)},
                "win": demo_dump.window(self, tc_.x, tc_.y, 26)})
        t_work = time.time()
        counts = {}
        for v in vs:
            d = jobs.get(v.id, "wood")
            if d in ("build", "busy"):
                continue                                # building / chasing / fleeing: driven elsewhere
            if isinstance(d, tuple):                    # ("hunt", site key)
                key = d[1]
                self.hunt_site[v.id] = key
                st = next((st for (k, x, y, st) in self.sites if k == key), None)
                if st in ("provoke", "run", "push") and key not in self.leads.values():
                    self.leads[v.id] = key
                role = "hunt"
            else:
                role = "berry" if d == "berry2" else d
            r = self.role.get(v.id)
            if isinstance(r, tuple) and r[0] == "build":
                continue
            counts[role] = counts.get(role, 0) + 1
            changed = r is not None and r != role and not self.recent(v.id, within=5)
            if r != role:
                self.role[v.id] = role
            t1 = time.time()
            self.work(v, role, force=changed)
            if time.time() - t1 > 0.3:
                sub.append((time.time() - t1, "work:%s" % role))
        sub.append((time.time() - t_work, "all work"))
        if sum(x for x, n in sub if n != "all work") + sub[-1][0] > 0.8:
            sub.sort(reverse=True)
            self.say("SLOW villagers: " + ", ".join("%s %.2f" % (n, x) for x, n in sub[:5]))
