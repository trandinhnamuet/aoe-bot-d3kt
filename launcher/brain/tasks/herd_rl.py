"""The herd push driven by the learned policy (rl/policies/herd_push.json): the same observation,
frame and actions as the training environment (rl.features / rl.herd_env), one decision per pusher
every 0.5 game seconds; the kill at the TC and every state transition / failure rule stay the
hand-coded HerdPush. Enabled from d3kt when the policy file exists and AOESOLO_HERD_RL is not "0"."""
import math

from brain import geom
from brain.tasks import herd as H
from brain.tasks.herd import HerdPush
from rl import features as F
from rl.policy import Policy

DECISION = 0.5
SPEAR_RANGE = 3.0


class HerdPushRL(HerdPush):
    _policy = None

    @classmethod
    def policy(cls):
        if cls._policy is None:
            cls._policy = Policy.find("herd_push")
        return cls._policy

    def __init__(self, gids, pushers, policy=None):
        super().__init__(gids, pushers)
        self.pol = policy or self.policy()
        self.t_dec = None
        self.prevp = {}                 # gazelle id -> (x, y, t) at the last decision (hop detection)
        self.pend = {}                  # pusher id -> [gid, hp0, t_order, stop_at, stop_sent]
        self.t_push0 = None

    # ---------------------------------------------------------------- the herd as the policy sees it
    def _members_rl(self, w):
        out = []
        for gid in list(self.gids):
            tr = w.track(gid)
            if tr is None or tr.hp <= 0:
                continue                                    # members() (the tick) removes the dead
            a = w.animal(gid)
            if a is not None:
                x, y, age = a.x, a.y, 0.0
            else:
                ls = w.last_seen(gid)
                if not ls or w.now - ls[2] >= H.GHOST_S:
                    continue
                x, y, age = ls[0], ls[1], w.now - ls[2]
            pv = self.prevp.get(gid)
            hop = pv is not None and w.now - pv[2] > 0.05 and math.hypot(x - pv[0], y - pv[1]) / (w.now - pv[2]) > H.HOP_SPEED
            out.append((gid, x, y, age, hop, a))
        return out

    # ---------------------------------------------------------------- fast (the push only)
    def micro(self, w, o):
        if self.state != "push" or self.pol is None:
            return super().micro(w, o)
        now = w.now
        self._spear_stops(w, o)
        if self.t_dec is not None and now - self.t_dec < DECISION:
            return
        self.t_dec = now
        if self.t_push0 is None:
            self.t_push0 = now
        mem = self._members_rl(w)
        if not mem:
            self.mode = "search"
            return
        fresh = [m for m in mem if m[3] < H.FRESH_S] or mem
        cx = sum(m[1] for m in fresh) / len(fresh)
        cy = sum(m[2] for m in fresh) / len(fresh)
        dx, dy = self.push_dir(w, cx, cy)
        rear = min(fresh, key=lambda m: (m[1] - cx) * dx + (m[2] - cy) * dy)
        members = [(m[1], m[2], m[3], m[4]) for m in mem]
        if not self.behind_t:
            self.behind_t = now                             # the push proper: the stuck clock runs
        self.not_behind_since = None
        self.mode = "rl"
        t_frac = min(1.0, (now - self.t_push0) / 150.0)
        lag = getattr(w, "lag", 1.0)
        units = {vid: w.unit(vid) for vid in self.pushers}
        for k, vid in enumerate(self.pushers):
            v = units.get(vid)
            if v is None:
                continue
            other = None
            if len(self.pushers) > 1:
                ov = units.get(self.pushers[1 - k])
                other = (ov.x, ov.y) if ov is not None else None
            obs, mirror = F.pusher_obs(v.x, v.y, other, members, cx, cy, dx, dy, w.tc, w.passable, t_frac, lag)
            a = self.pol.act(obs)
            pend = self.pend.get(vid)
            if pend is not None and not pend[4]:
                continue                                    # a nudge spear on its way
            if a == F.A_SPEAR:
                g = rear[5]
                if g is not None and g.id not in self.speared and g.hp >= g.maxhp - 0.01 and pend is None:
                    o.attack([vid], g.id)
                    d = math.hypot(v.x - g.x, v.y - g.y)
                    self.pend[vid] = [g.id, g.hp, now, now + 1.0 + max(0.0, d - (SPEAR_RANGE - 0.3)) / 1.1, False]
                    self.speared.add(g.id)
                    self.say(w, "RL: one spear at gazelle #%d" % g.id)
            elif a == F.A_STOP:
                o.stop([vid])
            else:
                tx, ty = F.move_target(a, (rear[1], rear[2]), cx, cy, dx, dy, mirror)
                ux, uy, run = geom.open_dir(w.passable, v.x, v.y, *geom.unit(tx - v.x, ty - v.y), far=1.5,
                                            max_len=max(0.3, math.hypot(tx - v.x, ty - v.y)))
                o.move([vid], v.x + ux * run, v.y + uy * run)
                self.mt[vid] = (now, (v.x + ux * run, v.y + uy * run))
        for m in mem:
            self.prevp[m[0]] = (m[1], m[2], now)
        if not self.recent(w, ("hdbg",), 5.0):
            self.mark(w, ("hdbg",))
            self.say(w, "HERDDBG push rl: %d gazelles (%d fresh) centre %.1f tiles from the TC edge | %s" % (
                len(mem), len(fresh), geom.tc_edge_dist(cx, cy, *w.tc),
                " | ".join("#%d(%.1f,%.1f)" % (vid, u.x, u.y) for vid, u in units.items() if u is not None)))

    def _spear_stops(self, w, o):
        for vid, pend in list(self.pend.items()):
            gid, hp0, t0, stop_at, sent = pend
            g = w.track(gid)
            v = w.unit(vid)
            hit = g is None or g.hp < hp0 - 0.01
            if not sent and w.now >= stop_at and (g is None or v is None or math.hypot(v.x - g.x, v.y - g.y) <= SPEAR_RANGE + 0.3):
                o.stop([vid])
                pend[4] = True
            if hit or w.now - t0 > 5.0:
                if not pend[4]:
                    o.stop([vid])
                if not hit:
                    self.speared.discard(gid)
                del self.pend[vid]
