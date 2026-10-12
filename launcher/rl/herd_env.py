"""The herd-push environment: the 2D sim with a herd of 3-5 gazelles 12-25 tiles from the TC, two
pushers under the policy (one decision every 0.5 game seconds each), the hand-coded kill (brain.tasks
.herd.HerdPush, kill state) once the herd is at the TC, two helpers at the TC for that kill.

Reward = the user's standard for the push: every gazelle dead within 4 tiles of the TC edge, none dead
out in the field, the whole thing within 120 s - plus shaping for progress / scatter / time.

    env = HerdEnv(); obs = env.reset(seed)        # obs: (2, OBS_DIM), one row per pusher
    obs, r, done, info = env.step((a0, a1))        # actions 0..N_ACTIONS-1 (rl.features)
    env.score()                                    # the outcome by the strict criterion
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain import geom                                   # noqa: E402
from brain.tasks import herd as H                        # noqa: E402
from brain.tasks.herd import HerdPush                    # noqa: E402
from rl import features as F                             # noqa: E402
from sim.sim import Sim                                  # noqa: E402

SPEAR_RANGE = 3.0


class HerdEnv:
    OBS_DIM = F.OBS_DIM
    N_ACTIONS = F.N_ACTIONS

    def __init__(self, lags=((2.0, 0.7), (1.0, 0.3)), d_range=(12.0, 25.0), max_t=150.0, decision=0.5,
                 helpers=True, n_range=(3, 5), forests=3, seed=0):
        self.lags = lags
        self.d_range = d_range
        self.max_t = max_t
        self.decision = decision
        self.helpers_on = helpers
        self.n_range = n_range
        self.forests = forests
        self.rng = random.Random(seed)
        self.sim = None

    # ---------------------------------------------------------------- scene
    def build(self, seed, lag=None):
        rng = random.Random(seed)
        if lag is None:
            r = rng.random()
            acc = 0.0
            lag = self.lags[-1][0]
            for L, p in self.lags:
                acc += p
                if r < acc:
                    lag = L
                    break
        sim = Sim(seed=seed, params={"LAG": lag})
        r = sim.rng
        for _ in range(self.forests):
            for _try in range(30):
                cx, cy = r.uniform(4, sim.W - 4), r.uniform(4, sim.H - 4)
                if math.hypot(cx - sim.tc[0], cy - sim.tc[1]) > 7:
                    sim.add_forest(cx, cy, r.uniform(2, 4))
                    break
        n = r.randint(*self.n_range)
        hx, hy = sim.tc[0] + self.d_range[0], sim.tc[1]
        for _ in range(100):
            d, a = r.uniform(*self.d_range), r.uniform(0, 2 * math.pi)
            x, y = sim.tc[0] + math.cos(a) * d, sim.tc[1] + math.sin(a) * d
            if 3 < x < sim.W - 3 and 3 < y < sim.H - 3 and sim.passable(int(x), int(y)):
                hx, hy = x, y
                break
        gids = sim.add_herd(hx, hy, n)
        for g in gids:
            sim.seen[g] = (sim.ents[g].x, sim.ents[g].y, 0.0)
        pushers = [sim.add_villager(sim.tc[0] + 2.5, sim.tc[1] + 2.5), sim.add_villager(sim.tc[0] - 2.5, sim.tc[1] + 2.5)]
        helpers = []
        if self.helpers_on:
            helpers = [sim.add_villager(sim.tc[0] + 3.2, sim.tc[1] - 2.0), sim.add_villager(sim.tc[0] - 3.2, sim.tc[1] - 2.0)]
        return sim, gids, pushers, helpers, lag, (hx, hy)

    def reset(self, seed=None, lag=None):
        if seed is None:
            seed = self.rng.randrange(1 << 30)
        self.seed = seed
        self.sim, self.gids, self.pushers, self.helpers, self.lag, self.herd0 = self.build(seed, lag)
        self.task = None                     # the hand-coded kill once the herd is home
        self.killer = HerdPush(self.gids, self.pushers)   # for push_dir / members (never ticked in push)
        self.killer.helpers = list(self.helpers)
        self.prev_pos = {}
        self.speared = set()
        self.pending = {}                    # pusher id -> (gid, hp0, t_order, stop_at, stop_sent)
        self.strays = set()
        self.field_dead = set()
        self.dead_edge = {}
        self.steps = 0
        self.d_prev = None
        self.spread_prev = None
        self.mode = "push"
        self.escapes = 0
        self.last_frame = None
        self.best_d = None                   # (best herd-centre distance, t): the game's stuck rule
        return self._obs()

    # ---------------------------------------------------------------- herd geometry
    def _members(self):
        """[(gid, x, y, age, hopping)] of the living gazelles, in sight (age 0) or remembered."""
        out = []
        sim = self.sim
        for gid in self.gids:
            e = sim.ents[gid]
            if not e.alive:
                continue
            if sim.visible(e.x, e.y):
                x, y, age = e.x, e.y, 0.0
            else:
                ls = sim.seen.get(gid)
                if ls is None:
                    continue
                x, y, age = ls[0], ls[1], sim.t - ls[2]
            pv = self.prev_pos.get(gid)
            hop = pv is not None and math.hypot(x - pv[0], y - pv[1]) / max(1e-6, sim.t - pv[2]) > H.HOP_SPEED
            out.append((gid, x, y, age, hop))
        return out

    def _frame(self, mem):
        """Herd centre and push direction from the fresh members (else all remembered)."""
        fresh = [m for m in mem if m[3] < H.FRESH_S] or mem
        if not fresh:
            return None
        cx = sum(m[1] for m in fresh) / len(fresh)
        cy = sum(m[2] for m in fresh) / len(fresh)
        dx, dy = self.killer.push_dir(self.sim, cx, cy)
        return cx, cy, dx, dy, fresh

    def _obs(self):
        sim = self.sim
        mem = self._members()
        fr = self._frame(mem)
        if fr is None:
            fr = (self.herd0[0], self.herd0[1], *geom.unit(sim.tc[0] - self.herd0[0], sim.tc[1] - self.herd0[1]), [])
        cx, cy, dx, dy, fresh = fr
        self.last_frame = (cx, cy, dx, dy)
        members = [(m[1], m[2], m[3], m[4]) for m in mem]
        rows, mirrors = [], []
        for k, vid in enumerate(self.pushers):
            v = sim.ents[vid]
            o = sim.ents[self.pushers[1 - k]]
            other = (o.x, o.y) if o.alive else None
            if not v.alive:
                rows.append([0.0] * F.OBS_DIM)
                mirrors.append(False)
                continue
            obs, mirror = F.pusher_obs(v.x, v.y, other, members, cx, cy, dx, dy, sim.tc, sim.passable,
                                       min(1.0, sim.t / self.max_t), self.lag)
            rows.append(obs)
            mirrors.append(mirror)
        self.mirrors = mirrors
        return rows

    # ---------------------------------------------------------------- one decision step
    def step(self, actions):
        sim = self.sim
        mem = self._members()
        fr = self._frame(mem)
        if self.mode == "push" and fr is not None:
            cx, cy, dx, dy, fresh = fr
            rear = min(fresh, key=lambda m: (m[1] - cx) * dx + (m[2] - cy) * dy)
            for k, vid in enumerate(self.pushers):
                v = sim.ents[vid]
                if not v.alive:
                    continue
                a = int(actions[k])
                pend = self.pending.get(vid)
                if pend is not None and not pend[4]:
                    continue                                   # a spear on its way: no new order yet
                if a == F.A_SPEAR:
                    g = sim.ents[rear[0]]
                    if g.alive and g.id not in self.speared and g.hp >= g.maxhp - 0.01 and pend is None:
                        sim.attack([vid], g.id)
                        d = math.hypot(v.x - g.x, v.y - g.y)
                        self.pending[vid] = [g.id, g.hp, sim.t, sim.t + 1.0 + max(0.0, d - (SPEAR_RANGE - 0.3)) / 1.1, False]
                        self.speared.add(g.id)
                elif a == F.A_STOP:
                    sim.stop([vid])
                else:
                    tx, ty = F.move_target(a, (rear[1], rear[2]), cx, cy, dx, dy, self.mirrors[k])
                    ux, uy, run = geom.open_dir(sim.passable, v.x, v.y, *geom.unit(tx - v.x, ty - v.y), far=1.5,
                                                max_len=max(0.3, math.hypot(tx - v.x, ty - v.y)))
                    sim.move([vid], v.x + ux * run, v.y + uy * run)
        # the clock: decision seconds of sim steps, the hand-coded kill ticking when it is on
        n_sub = max(1, int(round(self.decision / sim.p["DT"])))
        tick_every = max(1, int(round(0.5 / sim.p["DT"])))
        for i in range(n_sub):
            sim._step()
            self._spear_stops()
            if self.task is not None and not (self.task.done or self.task.failed):
                if (self.steps * n_sub + i) % tick_every == 0:
                    self.task.tick(sim, sim)
                self.task.micro(sim, sim)
        self.steps += 1
        for m in mem:
            self.prev_pos[m[0]] = (m[1], m[2], sim.t - self.decision)
        # mode switches: push -> kill at the TC; kill -> push if the gazelles got away
        mem2 = self._members()
        fr2 = self._frame(mem2)
        if self.mode == "push" and fr2 is not None:
            cx, cy = fr2[0], fr2[1]
            near = [m for m in mem2 if m[3] == 0.0 and geom.tc_edge_dist(m[1], m[2], *sim.tc) <= H.HERD_KILL_NEAR]
            seen_now = any(m[3] == 0.0 for m in mem2)
            if seen_now and (geom.tc_edge_dist(cx, cy, *sim.tc) <= H.HERD_KILL_NEAR or len(near) * 2 >= len(mem2)):
                self.mode = "kill"
                alive = [g for g in self.gids if sim.ents[g].alive]
                self.task = HerdPush(alive, self.pushers)
                self.task.helpers = list(self.helpers)
                self.task.state = "kill"
                self.task.t0 = self.task.t_start = sim.t
                self.task.speared = set(self.speared)
                for vid in self.pushers:                        # clear a pending nudge
                    self.pending.pop(vid, None)
        elif self.mode == "kill" and self.task is not None:
            if self.task.state == "push":                        # got away: back to the policy
                self.escapes += 1
                self.mode = "push"
                self.task = None
                self.best_d = None
        # the hand-coded kill gave up with gazelles alive: the policy pushes them again (3 times at most)
        if self.task is not None and (self.task.done or self.task.failed):
            if any(sim.ents[g].alive for g in self.gids) and self.escapes < 3 and sim.t < self.max_t:
                self.escapes += 1
                self.mode = "push"
                self.task = None
                self.best_d = None
        # reward
        reward, done, info = self._reward(mem, mem2, fr, fr2)
        # the game's stuck rule (HerdPush.tick): no progress of the herd centre for STUCK_S seconds in
        # the push -> the push is abandoned there (the policy must keep the herd moving)
        if fr2 is not None and self.mode == "push":
            d_now = geom.tc_edge_dist(fr2[0], fr2[1], *sim.tc)
            if self.best_d is None or d_now < self.best_d[0] - 1.5:
                self.best_d = (d_now, sim.t)
            elif sim.t - self.best_d[1] > H.STUCK_S:
                done = True
                info["stuck"] = True
        if sim.t >= self.max_t or all(not sim.ents[g].alive for g in self.gids) \
                or (self.task is not None and (self.task.done or self.task.failed)):
            done = True
        if done:
            sc = self.score()
            reward += 4.0 * sc["home4"] + 1.0 * sc["near"] - 3.0 * sc["alive"] + (8.0 if sc["strict"] else 0.0)
            info.update(sc)
        return self._obs(), reward, done, info

    def _spear_stops(self):
        sim = self.sim
        for vid, pend in list(self.pending.items()):
            gid, hp0, t0, stop_at, sent = pend
            g = sim.ents.get(gid)
            v = sim.ents[vid]
            hit = g is None or not g.alive or g.hp < hp0 - 0.01
            if not sent and sim.t >= stop_at and (g is None or not g.alive or math.hypot(v.x - g.x, v.y - g.y) <= SPEAR_RANGE + 0.3):
                sim.stop([vid])
                pend[4] = True
            if hit or sim.t - t0 > 5.0:
                if not pend[4]:
                    sim.stop([vid])
                if not hit:
                    self.speared.discard(gid)
                del self.pending[vid]

    def _reward(self, mem, mem2, fr, fr2):
        sim = self.sim
        r = -0.02
        info = {}
        if fr is not None and fr2 is not None:
            d0 = geom.tc_edge_dist(fr[0], fr[1], *sim.tc)
            d1 = geom.tc_edge_dist(fr2[0], fr2[1], *sim.tc)
            if len(mem) == len(mem2):
                r += (d0 - d1)                                   # progress of the herd centre, tiles
            # scatter: the herd getting wider than 4 tiles
            def spread(fr_):
                cx, cy, dx, dy, fresh = fr_
                if len(fresh) < 2:
                    return 0.0
                return max(math.hypot(m[1] - cx, m[2] - cy) for m in fresh)
            s0, s1 = spread(fr), spread(fr2)
            if s1 > 4.0:
                r -= 0.1 * max(0.0, s1 - max(s0, 4.0))
            # a stray: further than HERD_SPREAD from the centre (once per gazelle)
            for m in mem2:
                if m[0] not in self.strays and math.hypot(m[1] - fr2[0], m[2] - fr2[1]) > H.HERD_SPREAD:
                    self.strays.add(m[0])
                    r -= 1.0
        # shaping from what we know: a pusher behind the rear gazelle, on the push line, is where the
        # push happens (small, so the progress term still dominates)
        if fr2 is not None and self.mode == "push":
            cx, cy, dx, dy, fresh = fr2
            if fresh:
                rear = min(fresh, key=lambda m: (m[1] - cx) * dx + (m[2] - cy) * dy)
                nx, ny = -dy, dx
                for vid in self.pushers:
                    v = sim.ents[vid]
                    if not v.alive:
                        continue
                    rel = (v.x - rear[1]) * dx + (v.y - rear[2]) * dy
                    lat = (v.x - rear[1]) * nx + (v.y - rear[2]) * ny
                    if -3.5 <= rel <= -0.5 and abs(lat) <= 1.5:
                        r += 0.03
        # deaths this step
        for g in self.gids:
            e = sim.ents[g]
            if not e.alive and g not in self.dead_edge:
                edge = geom.tc_edge_dist(e.x, e.y, *sim.tc)
                self.dead_edge[g] = edge
                if edge > 6.5:
                    self.field_dead.add(g)
                    r -= 6.0
        return r, False, info

    # ---------------------------------------------------------------- the outcome
    def score(self):
        sim = self.sim
        home4 = near = field = alive = 0
        for g in self.gids:
            e = sim.ents[g]
            if e.alive:
                alive += 1
                continue
            edge = self.dead_edge.get(g, geom.tc_edge_dist(e.x, e.y, *sim.tc))
            if edge <= 4.0:
                home4 += 1
            elif edge <= 6.5:
                near += 1
            else:
                field += 1
        n = len(self.gids)
        return dict(n=n, home4=home4, near=near, field=field, alive=alive, t=round(sim.t, 1), lag=self.lag,
                    strict=(home4 == n and sim.t <= 120.0), all_home=(home4 == n))

    # ---------------------------------------------------------------- imitation data
    def record_handcoded(self, seed, lag=None):
        """Runs the hand-coded HerdPush on this scene and records, per 0.5-s decision of the push
        phase, (obs rows, the actions nearest to what it ordered): [(obs(2 x OBS_DIM), [a0, a1])]."""
        self.reset(seed, lag)
        sim = self.sim
        task = HerdPush(self.gids, self.pushers)
        task.helpers = list(self.helpers)
        orders = {}                                   # pusher id -> last order in the window

        def rec(kind):
            orig = getattr(sim, kind)

            def f(ids, *a):
                for i in ids:
                    if i in self.pushers:
                        orders[i] = (kind, a)
                return orig(ids, *a)
            return f
        sim.move, sim.attack, sim.stop = rec("move"), rec("attack"), rec("stop")
        data = []
        n_sub = max(1, int(round(self.decision / sim.p["DT"])))
        tick_every = max(1, int(round(0.5 / sim.p["DT"])))
        last_act = {vid: F.A_STOP for vid in self.pushers}
        k = 0
        while sim.t < self.max_t and not (task.done or task.failed) and task.state == "push":
            mem = self._members()
            fr = self._frame(mem)
            obs = self._obs()
            orders.clear()
            for i in range(n_sub):
                if (k * n_sub + i) % tick_every == 0:
                    task.tick(sim, sim)
                task.micro(sim, sim)
                sim._step()
            k += 1
            for m in mem:
                self.prev_pos[m[0]] = (m[1], m[2], sim.t - self.decision)
            if fr is None:
                continue
            cx, cy, dx, dy, fresh = fr
            rear = min(fresh, key=lambda m: (m[1] - cx) * dx + (m[2] - cy) * dy)
            acts = []
            for j, vid in enumerate(self.pushers):
                od = orders.get(vid)
                if od is None:
                    a = last_act[vid]
                elif od[0] == "attack":
                    a = F.A_SPEAR
                elif od[0] == "stop":
                    a = F.A_STOP
                else:
                    tx, ty = od[1]
                    to_f, _ = F.frame(cx, cy, dx, dy, self.mirrors[j])
                    ra, rl = to_f(rear[1], rear[2])
                    ta, tl = to_f(tx, ty)
                    da, dl = ta - ra, tl - rl
                    a = min(range(len(F.MOVES)), key=lambda q: (F.MOVES[q][0] - da) ** 2 + (F.MOVES[q][1] - dl) ** 2)
                last_act[vid] = a
                acts.append(a)
            data.append((obs, acts))
        return data

    # ---------------------------------------------------------------- the hand-coded push on the same scene
    def rollout_handcoded(self, seed, lag=None):
        """The existing HerdPush (push + kill) on exactly this scene: the baseline."""
        self.reset(seed, lag)
        sim = self.sim
        task = HerdPush(self.gids, self.pushers)
        task.helpers = list(self.helpers)
        sim.run([task], max_t=self.max_t)
        for g in self.gids:
            e = sim.ents[g]
            if not e.alive:
                self.dead_edge[g] = geom.tc_edge_dist(e.x, e.y, *sim.tc)
        return self.score()
