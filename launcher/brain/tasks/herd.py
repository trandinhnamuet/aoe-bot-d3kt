"""Gazelle herd push (the user's rules, LUAT_D3KT.md):

Measured on 894 runs: a gazelle flees when a villager comes closer than ~2.1 tiles (1.3-2.9), hops
~2.75 tiles in ~1.7 s straight away from the villager. So the pusher gets BEHIND the rearmost
gazelle (opposite the TC), keeping outside the other gazelles' flee circles on the way, and steps
in: it hops towards the TC, into the herd; the next rearmost follows... the herd rolls home as a
whole. On the way every full-hp gazelle gets ONE spear (half hp: one more spear kills it at the
TC before it can run) - one spear in the air at a time, confirmed, then back into position.
The herd is killed only right next to the TC (HERD_KILL_NEAR).

states: push (approach / around / behind / push / spear per pusher) -> kill -> done | failed(reason)
"""
import math
import os

from brain import geom
from brain.iface import Task

KEEP_OUT = 3.2           # the pusher keeps this far from the other gazelles while getting behind the herd
PUSH_IN = 1.5            # first step-in distance behind the rearmost gazelle (then closer if it ignores us)
BEHIND = 2.6             # the waiting point is this far straight behind the rearmost gazelle
HERD_SPREAD = 7.0        # gazelles further than this from the herd's middle are left out
HERD_KILL_NEAR = 4.0     # tiles from the TC edge: kill (players kill ~5.4 tiles from the TC centre)
STUCK_KILL_D = 8.5       # a push that stalls this close to the TC centre is finished there (buildings in the way)
TIMEOUT = 150.0
STUCK_S = 40.0           # behind the herd and no progress for this long -> give up
AROUND_GIVE_UP = 45.0    # not behind the herd after this long -> give up
GHOST_S = 30.0           # a gazelle out of sight is still part of the herd for this long
FRESH_S = 8.0            # a position this recent is good enough to steer by (calm gazelles barely move;
                         # at 5 s a lone pusher kept losing the herd walking round it: sim seed 1)
SPEAR_WAIT = 5.0         # a spear ordered but not landed after this long is cancelled
STOP_AFTER = 1.0         # the stop after a nudge spear goes out this long after the attack order (the throw
                         # is at lag + 0.5, the second at lag + 2.0): waiting to SEE the hit is a lag too late
                         # at x2 and the second spear kills it out in the field (sim lag 2: 10 of 40 pushes)
SPEAR_RANGE = 3.0
KILL_STAGE = 3.6         # a killer on the TC side of its gazelle first walks round to this far behind it
KILL_ROUND = 3.0         # walking round the herd to its field side a killer keeps this far from the gazelles
                         # (flee radius up to 2.9: closer scatters them sideways)
KILL_KEEP = 2.0          # closing in from the field side: this far from the OTHER gazelles (a hop away from a
                         # field-side villager goes towards the TC, no harm); the push keep-out (3.2) made the
                         # spot behind a gazelle in a tight herd unreachable (kill-only sim: first spear at 50-66 s)
PAIR_WAIT = 5.0          # a killer in position waits this long for its partner, then throws alone
STEADY = os.environ.get("HERD_STEADY", "1") != "0"
AHEAD = float(os.environ.get("HERD_AHEAD", "0.8"))              # steady push: the move target is this far THROUGH the rear gazelle's spot towards the TC
STALL_SPEAR = 8.0        # steady push: no progress for this long with the pusher on its gazelle -> one spear
STEADY_FAR = float(os.environ.get("HERD_STEADY_FAR", "8.0"))   # steady only while the herd centre is further
                         # than this from the TC edge; the last tiles are stepped in carefully so the herd
                         # bunches against the TC instead of being chased round it
TRIG = 2.3               # a gazelle this close to the step-in point will hop (measured 2.1, p90 2.9)
HOP = 2.75               # a hop (measured)
HOP_SPEED = 1.0          # tiles/s: faster than this = in the air


class HerdPush(Task):
    name = "herd"

    def __init__(self, gids, pushers):
        super().__init__()
        self.gids = list(gids)
        self.pushers = list(pushers)[:2]
        self.killed = set()
        self.speared = set()
        self.pst = {}                 # per pusher control state
        self.mt = {}                  # per pusher: (t, (x, y)) of the last move order
        self.state = "push"
        self.t0 = None
        self.behind_t = None
        self.not_behind_since = None
        self.best_d = None            # (dist, t) herd centre to TC
        self.last_seen = None         # (x, y, t) herd centre when last in sight
        self.at_spot_since = None
        self.kill_tgt = {}            # pusher id -> gazelle id it is killing (no target thrash)
        self.mode = "-"
        self.cx = self.cy = None
        self.helpers = []             # killers the brain lends for the kill at the TC
        self.prev = {}                # gazelle id -> (x, y, t) last position seen (hop detection)
        self.dead_edge = []           # tiles from the TC edge where each gazelle of the herd died (diag)
        self.t_start = None
        self.hop = {}                 # gazelle id -> (x0, y0, dx, dy, t0) of the hop in progress

    def owned(self):
        return list(self.pushers)

    # ---------------------------------------------------------------- the herd
    def members(self, w):
        """[(gazelle U or None, x, y, age)] of the herd now: in sight (age 0), or seen in the last
        GHOST_S seconds."""
        out = []
        for gid in list(self.gids):
            tr = w.track(gid)
            if tr is None or tr.hp <= 0:
                self.gids = [g for g in self.gids if g != gid]
                self.killed.add(gid)
                pos = (tr.x, tr.y) if tr is not None else (w.last_seen(gid) or (None,))[:2]
                if pos and pos[0] is not None:
                    edge = geom.tc_edge_dist(pos[0], pos[1], *w.tc)
                    self.dead_edge.append(edge)
                    self.say(w, "GAZDEAD gazelle #%d %s %.1f tiles from the TC edge after %.0f s (%s)" % (
                        gid, "died" if tr is not None else "gone", edge, w.now - (self.t0 or w.now), self.state))
                continue
            a = w.animal(gid)
            if a is not None:
                out.append((a, a.x, a.y, 0.0))
            else:
                ls = w.last_seen(gid)
                if ls and w.now - ls[2] < GHOST_S:
                    out.append((None, ls[0], ls[1], w.now - ls[2]))
        if len(out) >= 3:                                # strays far from the others are left behind
            mx = sorted(p[1] for p in out)[len(out) // 2]
            my = sorted(p[2] for p in out)[len(out) // 2]
            out = [p for p in out if math.hypot(p[1] - mx, p[2] - my) <= HERD_SPREAD] or out
        return out

    def predict(self, w, p):
        """(px, py) where the gazelle of member p will be: its landing point when it is in the air
        (a hop is HOP tiles straight on), else where it stands."""
        a, x, y, age = p
        if a is None:
            return x, y
        now = w.now
        pv = self.prev.get(a.id)
        self.prev[a.id] = (x, y, now)
        if pv is None or now - pv[2] <= 0.0:
            return x, y
        sp = math.hypot(x - pv[0], y - pv[1]) / (now - pv[2])
        h = self.hop.get(a.id)
        if sp > HOP_SPEED:
            if h is None or now - h[4] > 2.5:
                h = (pv[0], pv[1], *geom.unit(x - pv[0], y - pv[1]), now)
                self.hop[a.id] = h
        elif h is not None and now - h[4] > 0.4:
            self.hop.pop(a.id, None)
            h = None
        if h is None:
            return x, y
        gone = math.hypot(x - h[0], y - h[1])
        if gone >= HOP - 0.2:
            return x, y
        return h[0] + h[2] * HOP, h[1] + h[3] * HOP

    def push_point(self, w, vx, vy, part, fwd, pin, rear):
        """The step-in point: behind one of the gazelles (predicted positions), within +-40 deg of
        the push line, pin or pin+0.5 tiles out; scored by how well every gazelle it triggers will
        hop towards the TC (minimal scatter), more triggered at once is better, backwards is not."""
        dx, dy = fwd
        best = None
        for (_al, _lat, p, gx, gy) in part:
            for deg in (0, -10, 10, -20, 20, -30, 30, -40, 40):
                bx, by = geom.rot(dx, dy, math.radians(deg))
                for r in (pin, pin + 0.5):
                    px, py = gx - bx * r, gy - by * r
                    if not w.passable(int(px), int(py)):
                        continue
                    trig = [(qx, qy) for (_a, _l, _q, qx, qy) in part if math.hypot(qx - px, qy - py) < TRIG]
                    if not trig:
                        continue
                    cost = 0.0
                    for qx, qy in trig:
                        ux, uy = geom.unit(qx - px, qy - py)
                        c = ux * dx + uy * dy
                        cost += (1.0 - c) + (1.5 if c < 0.3 else 0.0)
                    cost += -0.25 * len(trig) + 0.12 * math.hypot(px - vx, py - vy)
                    cost += 0.15 * max(0.0, ((gx - rear[0]) * dx + (gy - rear[1]) * dy))   # the rear first
                    if best is None or cost < best[0]:
                        best = (cost, px, py)
        if best is None:
            return rear[0] - dx * pin, rear[1] - dy * pin
        return best[1], best[2]

    def push_dir(self, w, gx, gy):
        """Unit direction the herd should run: towards the TC, turned away from trees / cliffs so the
        next hop lands on open ground."""
        bx, by = geom.unit(w.tc[0] - gx, w.tc[1] - gy)
        for deg in (0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75):
            dx, dy = geom.rot(bx, by, math.radians(deg))
            ahead = all(w.passable(int(gx + dx * k), int(gy + dy * k)) for k in (1.0, 2.0, 3.0))
            behind = all(w.passable(int(gx - dx * k), int(gy - dy * k)) for k in (PUSH_IN, BEHIND))
            if ahead and behind:
                return dx, dy
        return bx, by

    # ---------------------------------------------------------------- slow
    def tick(self, w, o):
        if self.t0 is None:
            self.t0 = w.now
        if self.t_start is None:
            self.t_start = w.now
        mem = self.members(w)
        if not self.gids:
            self._herdok(w, 0)
            self.finish(w, "herd done: %d killed" % len(self.killed))
            return
        gone = self.__dict__.setdefault("gone", {})
        for p in list(self.pushers):
            if w.unit(p) is None:
                gone[p] = gone.get(p, 0) + 1
                if gone[p] >= 2:                         # missing on two ticks running: really gone
                    self.pushers = [q for q in self.pushers if q != p]
            else:
                gone.pop(p, None)
        if not self.pushers:
            self.fail(w, "no pusher left")
            return
        seen_now = any(p[0] is not None for p in mem)
        if mem:
            self.cx = sum(p[1] for p in mem) / len(mem)
            self.cy = sum(p[2] for p in mem) / len(mem)
            if seen_now:
                self.last_seen = (self.cx, self.cy, w.now)
        if self.state == "push":
            if self.cx is None:
                self.fail(w, "never seen")
                return
            dist = math.hypot(self.cx - w.tc[0], self.cy - w.tc[1])
            if self.best_d is None or dist < self.best_d[0] - 1.5:
                self.best_d = (dist, w.now)
            at_spot = any(w.unit(p) and w.unit(p).dist(self.cx, self.cy) < 2.5 for p in self.pushers)
            if seen_now or not at_spot:
                self.at_spot_since = None
            elif self.at_spot_since is None:
                self.at_spot_since = w.now
            why = None
            if self.at_spot_since is not None and w.now - self.at_spot_since > 6:
                why = "lost from sight"
            elif w.now - self.t0 > TIMEOUT:
                why = "timed out"
            elif self.behind_t and w.now - self.behind_t > STUCK_S and w.now - self.best_d[1] > STUCK_S:
                if seen_now and dist <= STUCK_KILL_D:
                    self.state = "kill"                  # stalled among the houses, close enough: kill here
                    self.say(w, "herd stalled %.1f tiles from the TC: kill it here" % dist)
                    return
                why = "stuck (no progress for %.0f s)" % STUCK_S
            elif self.not_behind_since is not None and w.now - self.not_behind_since > AROUND_GIVE_UP:
                why = "no way behind it (edge / cliffs)"
            if why:
                self.fail(w, "%s after %.0f s (mode %s), herd %.0f tiles from the TC" % (
                    why, w.now - self.t0, self.mode, dist))
                return
            near = [p for p in mem if p[0] is not None and geom.tc_edge_dist(p[1], p[2], *w.tc) <= HERD_KILL_NEAR]
            if seen_now and (geom.tc_edge_dist(self.cx, self.cy, *w.tc) <= HERD_KILL_NEAR or len(near) * 2 >= len(mem)):
                self.state = "kill"
                self.say(w, "herd pushed home in %.0f s (%d gazelles, %.1f tiles from the TC): kill" % (
                    w.now - self.t0, len(mem), geom.tc_edge_dist(self.cx, self.cy, *w.tc)))
        if self.state == "kill":
            near = [p[0] for p in mem if p[0] is not None
                    and geom.tc_edge_dist(p[1], p[2], *w.tc) <= HERD_KILL_NEAR + 2.0]
            if not near:
                self.escapes = getattr(self, "escapes", 0) + 1
                if mem and self.escapes <= 3:
                    self.state = "push"                  # the ones that got away are pushed again
                    self.t0, self.behind_t, self.best_d = w.now, None, None
                    self.not_behind_since = None
                    self.say(w, "%d gazelles got away: push again" % len(mem))
                else:
                    self._herdok(w, len(mem))
                    self.finish(w, "herd done: %d killed, %d got away for good" % (len(self.killed), len(mem)))
                return
            killers = [i for i in list(self.pushers) + [h for h in self.helpers if h not in self.pushers]
                       if w.unit(i) is not None]
            # the user: at least two spears land on one gazelle at once (8 hp, 4 per spear) so it
            # drops where it stands instead of hopping off; weakest first, then the nearest to the TC
            # sticky targets: a killer keeps its gazelle while it lives and stays near (re-sorting every
            # tick sent the killers walking back and forth round the herd); free killers are paired on
            # the weakest / nearest gazelle that has the fewest killers
            near_ids = {a.id: a for a in near}
            self.kill_tgt = {i: g for i, g in self.kill_tgt.items() if i in killers and g in near_ids}
            load = {}
            for g in self.kill_tgt.values():
                load[g] = load.get(g, 0) + 1
            free = [i for i in killers if i not in self.kill_tgt]
            while free:
                g = min(near, key=lambda a: (load.get(a.id, 0) >= 2, load.get(a.id, 0), a.hp,
                                             geom.tc_edge_dist(a.x, a.y, *w.tc)))
                for i in free[:2]:
                    self.kill_tgt[i] = g.id              # the orders: kill_micro (from the field side)
                load[g.id] = load.get(g.id, 0) + len(free[:2])
                free = free[2:]

    def _herdok(self, w, away):
        """One summary line per herd (the user's standard: every gazelle dead within 4 tiles of the
        TC edge, the whole push within 120 s)."""
        near = sum(1 for d in self.dead_edge if d <= 4.0)
        far = len(self.dead_edge) - near
        t = w.now - (self.t_start or w.now)
        self.say(w, "HERDOK %d gazelles: %d dead <= 4 tiles, %d dead far (%s), %d got away, %.0f s%s" % (
            near + far + away, near, far, " ".join("%.1f" % d for d in self.dead_edge if d > 4.0) or "-", away, t,
            "" if (far == 0 and away == 0 and t <= 120) else " - NOT the standard"))

    # ---------------------------------------------------------------- getting round the herd
    @staticmethod
    def _seg_clear(x0, y0, x1, y1, obs, r):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        for (ox, oy) in obs:
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((ox - x0) * dx + (oy - y0) * dy) / L2))
            if math.hypot(x0 + k * dx - ox, y0 + k * dy - oy) < r:
                return False
        return True

    def steer(self, w, st, vx, vy, gx, gy, obs, now, fwd, keep=KEEP_OUT):
        """Next move target towards (gx, gy) keeping `keep` from the gazelles in `obs`: straight
        when clear, else along a tangent of the first blocking gazelle - preferring the tangent
        that does not lead forward (`fwd` = the push direction) through the herd."""
        if self._seg_clear(vx, vy, gx, gy, obs, keep):
            st.pop("side_t", None)
            return gx, gy
        dgx, dgy = geom.unit(gx - vx, gy - vy)
        block = min((o for o in obs if not self._seg_clear(vx, vy, gx, gy, [o], keep)),
                    key=lambda o: math.hypot(o[0] - vx, o[1] - vy))
        ox, oy = block
        d = math.hypot(ox - vx, oy - vy)
        R = keep + 0.3
        if d <= R:                                        # inside its circle: straight out first
            ax, ay = geom.unit(vx - ox, vy - oy)
            return vx + ax * 2.0, vy + ay * 2.0
        base = math.atan2(oy - vy, ox - vx)
        half = math.asin(min(1.0, R / d))
        cands = []
        for side in (1, -1):
            a = base + side * half
            tx, ty = math.cos(a), math.sin(a)
            score = tx * dgx + ty * dgy - 0.6 * max(0.0, tx * fwd[0] + ty * fwd[1])
            cands.append((side, tx, ty, score))
        side = st.get("side")
        if side is None or now - st.get("side_t", 0) > 8.0:
            side = max(cands, key=lambda c: c[3])[0]
            st["side"], st["side_t"] = side, now
        _, tx, ty, _ = next(c for c in cands if c[0] == side)
        leg = min(3.0, max(1.5, d))
        return vx + tx * leg, vy + ty * leg

    # ---------------------------------------------------------------- fast (20 Hz)
    @staticmethod
    def _stop_at(now, d):
        """When the stop after a nudge spear goes out: STOP_AFTER after the order, plus the walk into range."""
        return now + STOP_AFTER + max(0.0, d - (SPEAR_RANGE - 0.3)) / 1.1

    def kill_micro(self, w, o):
        """The kill at the TC: every killer spears its gazelle from the FIELD side, so the hop after a
        hit goes towards the TC (blocked there) and not out into the field. A killer on the TC side
        (the helpers come from there) first walks round the herd to the point behind its gazelle."""
        now = w.now
        mem = self.members(w)
        gpos = [(p[1], p[2]) for p in mem]
        old = bool(os.environ.get("HERD_KILL_OLD"))                    # A/B in the sim: attack from anywhere
        # who is in position (field side, in range) for which gazelle: a pair throws together so the
        # two spears (4 + 4 = 8 hp) land before it hops; alone only after PAIR_WAIT
        ready, info = {}, {}
        for vid, gid in list(self.kill_tgt.items()):
            v, g = w.unit(vid), w.track(gid)
            if v is None or g is None or g.hp <= 0:
                continue
            ux, uy = geom.unit(g.x - w.tc[0], g.y - w.tc[1])           # out of the TC through the gazelle
            side = 1.0 if old else (v.x - g.x) * ux + (v.y - g.y) * uy  # > 0: on the field side of it
            d = v.dist(g.x, g.y)
            ok = side >= -0.2 and d <= SPEAR_RANGE + 0.3
            info[vid] = (v, g, ux, uy, side, d, ok)
            ready.setdefault(gid, []).append((vid, ok))
        for vid, (v, g, ux, uy, side, d, ok) in info.items():
            gid = g.id
            st = self.pst.setdefault(vid, {})
            if ok:
                mates = [m for m, k in ready.get(gid, []) if m != vid]
                all_ready = all(k for m, k in ready.get(gid, []))
                if not mates or all_ready or g.hp < g.maxhp - 0.01 or old:
                    go = True
                else:
                    t_ok = st.setdefault("ready_t", now)
                    go = now - t_ok > PAIR_WAIT
                if go:
                    st.pop("ready_t", None)
                    if w.action_of(vid) != ("attack", gid) and not self.recent(w, ("atk", vid, gid), 1.5):
                        o.attack([vid], gid)
                        self.mark(w, ("atk", vid, gid))
                elif w.action_of(vid)[0] != "idle" and not self.recent(w, ("hold", vid), 1.0):
                    o.stop([vid])                                      # hold position until the partner is set
                    self.mark(w, ("hold", vid))
                continue
            st.pop("ready_t", None)
            if st.get("fieldside") != gid and side >= 0.5:
                st["fieldside"] = gid                                  # hysteresis: once round, close in
            elif st.get("fieldside") == gid and side < -0.2:
                st.pop("fieldside", None)
            if st.get("fieldside") == gid:
                tx, ty = g.x + ux * 2.5, g.y + uy * 2.5               # the right side already: close in
                obs = [q for q in gpos if math.hypot(q[0] - g.x, q[1] - g.y) > 0.5]
                keep = KILL_KEEP
            else:
                tx, ty = g.x + ux * KILL_STAGE, g.y + uy * KILL_STAGE   # round it, keeping clear of them all
                obs = gpos
                keep = KILL_ROUND
            tx, ty = self.steer(w, st, v.x, v.y, tx, ty, obs, now, (-ux, -uy), keep=keep)
            ox, oy, run = geom.open_dir(w.passable, v.x, v.y, *geom.unit(tx - v.x, ty - v.y), far=1.5,
                                        max_len=max(0.5, math.hypot(tx - v.x, ty - v.y)))
            tx, ty = v.x + ox * run, v.y + oy * run
            last = self.mt.get(vid, (0.0, None))
            if now - last[0] > 0.25 and (last[1] is None or math.hypot(tx - last[1][0], ty - last[1][1]) > 0.4
                                         or now - last[0] > 1.5):
                o.move([vid], tx, ty)
                self.mt[vid] = (now, (tx, ty))

    def micro(self, w, o):
        if self.state == "kill":
            self.kill_micro(w, o)
            return
        if self.state != "push":
            return
        now = w.now
        mem = self.members(w)
        if not mem:
            self.mode = "search"
            return
        cx = sum(p[1] for p in mem) / len(mem)
        cy = sum(p[2] for p in mem) / len(mem)
        fresh = [p for p in mem if p[3] < FRESH_S]
        if not fresh:
            # only old remembered positions: walk there (from the flank, so we arrive beside the herd)
            for vid in self.pushers:
                v = w.unit(vid)
                if v is None or now - self.mt.get(vid, (0.0, None))[0] < 1.5:
                    continue
                bx, by = geom.unit(cx - w.tc[0], cy - w.tc[1])
                side = 1 if vid == self.pushers[0] else -1
                tx, ty = cx - bx * 2.5 + (-by) * 3.5 * side, cy - by * 2.5 + bx * 3.5 * side
                if v.dist(tx, ty) < 1.5:
                    tx, ty = cx, cy
                o.move([vid], tx, ty)
                self.mt[vid] = (now, (tx, ty))
            self.mode = "approach"
            return
        dx, dy = self.push_dir(w, cx, cy)
        nx, ny = -dy, dx
        pred = [(p, *self.predict(w, p)) for p in fresh]
        proj = [((px - cx) * dx + (py - cy) * dy, (px - cx) * nx + (py - cy) * ny, p, px, py) for p, px, py in pred]
        halves = {self.pushers[0]: proj}
        if len(self.pushers) == 2:
            left = [q for q in proj if q[1] <= 0]
            right = [q for q in proj if q[1] > 0]
            halves = {self.pushers[0]: left or proj, self.pushers[1]: right or proj}
        any_behind = False
        for vid, part in halves.items():
            v = w.unit(vid)
            if v is None:
                continue
            vx, vy = v.x, v.y
            st = self.pst.setdefault(vid, {})
            # ---- one spear on its way? wait for it to land, then back into position
            sp = st.get("spear")
            if sp is not None:
                g = w.track(sp[0])
                hit = g is None or g.hp < sp[1] - 0.01
                v_ = w.unit(vid)
                if not st.get("stop_sent") and now >= sp[3] and (g is None or v_ is None
                                                                 or v_.dist(g.x, g.y) <= SPEAR_RANGE + 0.3):
                    # (and only once it is seen within range: a walk estimate that was too short -
                    #  the gazelle moved - cancelled the throw and cost 7 s per miss)
                    o.stop([vid])                        # no second spear: it would kill it out there
                    st["stop_sent"] = True
                if hit or now - sp[2] > SPEAR_WAIT:
                    if hit:
                        self.speared.add(sp[0])
                    else:
                        self.speared.discard(sp[0])      # missed: may be thrown at again
                    st.pop("spear", None)
                    st["next_spear"] = now + (1.5 if hit else 2.0)
                    if not st.pop("stop_sent", False):
                        o.stop([vid])
                    self.mt[vid] = (0.0, None)
                else:
                    continue
            # the rearmost gazelle of this pusher's part (predicted position), everything relative to it
            # the rearmost gazelle of this pusher's part - sticky: kept while it is within 1.5 tiles of
            # the rear (sim x2: the rear changed every 4 s per pusher, each change a new waiting point)
            best = min(part, key=lambda q: q[0])
            cur = next((q for q in part if q[2][0] is not None and q[2][0].id == st.get("rear_id")), None)
            if cur is not None and cur[0] <= best[0] + 1.5:
                best = cur
            r_proj, r_lat, (rg, _rx0, _ry0, rage), rx, ry = best
            st["rear_id"] = rg.id if rg is not None else None
            rel = (vx - rx) * dx + (vy - ry) * dy        # > 0: level with / ahead of it
            lat = (vx - rx) * nx + (vy - ry) * ny
            others = [(px, py) for (_a, _l, p, px, py) in proj if p[0] is not rg and not (px == rx and py == ry)]
            wx, wy = rx - dx * BEHIND, ry - dy * BEHIND   # the waiting point straight behind it
            steady = STEADY and geom.tc_edge_dist(cx, cy, *w.tc) > STEADY_FAR
            # hysteresis; in the steady push the pusher walks through the gazelle's spot and draws
            # level with it before it hops: still "behind" up to 0.9 ahead (else a detour round it)
            behind = rel < ((0.9 if steady else -0.3) if st.get("behind") else -0.8)
            st["behind"] = behind
            if behind and not steady and now >= st.get("next_spear", 0.0):
                busy = any(s.get("spear") for k, s in self.pst.items() if k != vid)
                # (only a gazelle nearly straight ahead: a spear makes it hop straight away from the
                #  thrower, so one off to the side would hop out of the herd - scatter)
                cands = [] if busy else [q for q in part if q[2][0] is not None and q[2][0].id not in self.speared
                                         and (q[2][1] - vx) * dx + (q[2][2] - vy) * dy > 0.5
                                         and abs((q[2][1] - vx) * nx + (q[2][2] - vy) * ny) < 1.0
                                         and math.hypot(q[2][1] - vx, q[2][2] - vy) < 4.5]
                for q in sorted(cands, key=lambda q: math.hypot(q[2][1] - vx, q[2][2] - vy)):
                    g = q[2][0]
                    if g.hp < g.maxhp - 0.01:
                        self.speared.add(g.id)           # already hurt: not again
                        continue
                    o.attack([vid], g.id)
                    st["spear"] = (g.id, g.hp, now, self._stop_at(now, math.hypot(q[2][1] - vx, q[2][2] - vy)))
                    self.speared.add(g.id)               # reserved at once (two pushers must not both throw)
                    self.mode = "spear"
                    self.say(w, "one spear at gazelle #%d (%.0f hp)" % (g.id, g.hp))
                    break
                if st.get("spear") is not None:
                    continue
            if not behind:
                # level with or in front of the rearmost: round the herd to the point behind it
                obs = others + [(rx, ry)]
                tx, ty = self.steer(w, st, vx, vy, wx, wy, obs, now, (dx, dy))
                mode = "around"
            elif abs(lat) > (2.0 if steady else 1.0) and math.hypot(vx - wx, vy - wy) > 0.8:
                # behind but off its line: slide to the waiting point (round the other gazelles)
                # (the steady push corrects a small offset by walking at the target: 68 % of the push
                #  went on sliding / detours at x2 in the sim)
                any_behind = True
                tx, ty = self.steer(w, st, vx, vy, wx, wy, others, now, (dx, dy))
                mode = "behind"
            elif steady:
                # on its line behind it: walk through its spot towards the TC and keep walking (see
                # the module note) - the order is refreshed as the spot moves
                any_behind = True
                if not self.behind_t:
                    self.behind_t = now                  # the push proper starts now
                tx, ty = rx + dx * AHEAD, ry + dy * AHEAD
                st["tgt"] = (tx, ty)
                mode = "push"
                stalled = self.best_d is not None and now - self.best_d[1] > STALL_SPEAR
                if stalled and rg is not None and math.hypot(vx - rx, vy - ry) < 2.2 and rg.id not in self.speared \
                        and now - st.get("hit_t", 0) > 6 and rg.hp >= rg.maxhp - 0.01:
                    o.attack([vid], rg.id)               # one spear: it jumps ~3 tiles straight away
                    st["spear"] = (rg.id, rg.hp, now, self._stop_at(now, math.hypot(rx - vx, ry - vy)))
                    self.speared.add(rg.id)
                    st["hit_t"] = now
                    continue
            else:
                # on its line behind it: step in. It hops towards the TC, into the herd. If it does
                # not react, come closer; still nothing after a few tries -> one spear (full hp only)
                any_behind = True
                gp = st.get("gpos")
                rid = rg.id if rg is not None else -1
                if gp is None or gp[3] != rid or math.hypot(rx - gp[0], ry - gp[1]) > 1.0:
                    st["gpos"], st["pin"], st["stall"] = (rx, ry, now, rid), PUSH_IN, 0
                pin = st.get("pin", PUSH_IN)
                tx, ty = self.push_point(w, vx, vy, part, (dx, dy), pin, (rx, ry))
                st["tgt"] = (tx, ty)
                gp = st["gpos"]
                if math.hypot(vx - tx, vy - ty) > 0.6:
                    # still on the way to the step-in point: the stall clock waits (at x2 lag the
                    # pusher never got there before it ran out and threw a spear instead - 0.2 tiles/s)
                    st["gpos"] = (gp[0], gp[1], now, gp[3])
                elif now - gp[2] > 1.5:
                    st["pin"] = max(0.3, pin - 0.4)
                    st["gpos"] = (gp[0], gp[1], now - 1.0, gp[3])
                    st["stall"] = st.get("stall", 0) + 1
                mode = "push"
                if not self.behind_t:
                    self.behind_t = now                  # the push proper starts now
                if st.get("stall", 0) >= 4 and rg is not None and rg.id not in self.speared \
                        and now - st.get("hit_t", 0) > 6 and rg.hp >= rg.maxhp - 0.01:
                    o.attack([vid], rg.id)               # one spear: it jumps ~3 tiles straight away
                    st["spear"] = (rg.id, rg.hp, now, self._stop_at(now, math.hypot(rx - vx, ry - vy)))
                    self.speared.add(rg.id)
                    st["hit_t"], st["stall"] = now, 0
                    continue
            ux, uy, run = geom.open_dir(w.passable, vx, vy, *geom.unit(tx - vx, ty - vy), far=1.5,
                                        max_len=max(0.5, math.hypot(tx - vx, ty - vy)))
            tx, ty = vx + ux * run, vy + uy * run
            last = self.mt.get(vid, (0.0, None))
            refresh = 1.0 if (STEADY and mode == "push") else 1.5
            if now - last[0] > 0.25 and (last[1] is None or math.hypot(tx - last[1][0], ty - last[1][1]) > 0.4
                                         or now - last[0] > refresh):
                o.move([vid], tx, ty)
                self.mt[vid] = (now, (tx, ty))
            self.mode = mode
        if any_behind:
            self.not_behind_since = None
        elif self.not_behind_since is None:
            self.not_behind_since = now
        if not self.recent(w, ("hdbg",), 5.0):
            # in-game push diagnostics (the game log had no view of the push dynamics): the herd and
            # each pusher's geometry every 5 s
            self.mark(w, ("hdbg",))
            parts = []
            for vid in self.pushers:
                v = w.unit(vid)
                st = self.pst.get(vid, {})
                if v is None:
                    continue
                tg = st.get("tgt")
                parts.append("#%d(%.1f,%.1f)%s%s tgt=%s act=%s" % (
                    vid, v.x, v.y, "B" if st.get("behind") else "-", " SP" if st.get("spear") else "",
                    "-" if tg is None else "(%.1f,%.1f)" % tg, (w.action_of(vid) or ("?",))[0]))
            self.say(w, "HERDDBG %s %s: %d gazelles (%d fresh) centre %.1f tiles from the TC edge, dir (%.2f,%.2f) | %s" % (
                self.state, self.mode, len(mem), len(fresh), geom.tc_edge_dist(cx, cy, *w.tc), dx, dy, " | ".join(parts)))
