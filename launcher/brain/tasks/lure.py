"""Elephant lure ("kiting", the user's rules in LUAT_D3KT.md):

provoke  the lurer walks in and throws ONE spear. Every order reaches the game ~1 s late, so the
         run-home order is given the moment the lurer is in throwing range: it leaves right after
         the spear (0.5 s wind-up) and the elephant (1.00 tiles/s, hits from 2 tiles) never gets
         within reach of a villager (1.10 tiles/s).
run      towards the TC on open ground while the elephant chases (w.target_of tells us whom it
         chases); stand still once it gave up (beyond ~4.4 tiles it stops following); one more
         spear only when it stands 3-8 tiles away and the lurer still has HURT_HP; a hurt lurer
         hands over to a fresh waiter.
kill     inside KILL_NEAR of the TC the waiters attack from throwing range; the one the elephant
         turns on steps back (it is slower than a villager) while the others keep throwing - the
         user's "điều quân". The lurer keeps running while it is the one chased, and joins the kill
         below 30 % elephant hp or when the elephant chases somebody else.
"""
import math
import os

from brain import geom
from brain.iface import Task

KEEP_MIN = 4.3       # run while a chasing elephant is closer than this
KEEP_MAX = 3.0       # wait only once it stopped chasing and is further than this
SPEAR_RANGE = 3.0
KILL_NEAR = 3.2      # tiles from the home edge where the kill starts (lure11 at x2: kills starting at 4.5 ended at 4.5)
LURE_CIRCLE = 3.2    # the chased lurer circles the home this close so the elephant stays by it
HURT_HP = 20.0       # below this a lurer throws no more spears (an elephant hit is 10)
KITE_D = 4.0         # a killer the elephant turns on steps back when it is this close
WAIT_SPOTS = [(3.5, 0.0)]   # (along, lateral) from home: the arrival point (side spots at +-3.0 tried in the
                            # sim at x2: more lurer deaths and provoke hand-overs - not shipped untested)
SLALOM_D = 3.4       # gap beyond which the lurer runs at an angle (so the elephant keeps up and follows)
TIMEOUT = 150.0
PROVOKE_TIMEOUT = 60.0
SOLO = os.environ.get("LURE_SOLO", "0") == "1"   # the solo kill (nobody waiting): sim only, 0/60 there and
                                                 # lure14: the lurer drifted 20 tiles from home and died
MAX_HANDOVERS = 2
MAX_REPROVOKE = 12


class Lure(Task):
    name = "lure"

    def __init__(self, eid, lurer, waiters=(), anywhere=False, home=None):
        super().__init__()
        self.anywhere = anywhere        # kill it where it is (too far to lure): no run, no TC distance
        self.dprev = {}                 # lurer id -> (distance to the elephant, t): closing speed
        self.d_prov = None              # (t_state, distance) at the start of the current provoke
        self.none_since = None          # since when the elephant has not been tracked (grace before "down")
        self.home = home                # (x, y) of the dropsite it is lured to; None = the TC
        self.eid = eid
        self.lurer = lurer
        self.waiters = [w for w in waiters if w != lurer]
        self.hurt = set()
        self.handovers = 0
        self.reprovoke = 0
        self.state = "kill" if anywhere else "provoke"
        self.t0 = None
        self.t_state = None
        self.hp0 = self.vhp0 = None
        self.epos = None             # (x, y, t) of the elephant 0.3 s ago
        self.last_move_t = None
        self.coming = False
        self.moving = False
        self.spear = None            # (ele hp, lurer hp, t) while one spear is on its way

    def owned(self):
        return [self.lurer] + self.waiters

    # ---------------------------------------------------------------- helpers
    def _home(self, w):
        return self.home if self.home is not None else w.tc

    def _enter(self, w, state):
        self.state, self.t_state = state, w.now
        self.hp0 = self.vhp0 = None
        self.spear = None
        self.moving = False

    def _hand_over(self, w, o, v, why):
        self.hurt.add(v.id)
        hx, hy = self._home(w)
        o.move([v.id], hx + 2.5, hy + 2.5)
        fresh = [i for i in self.waiters if i not in self.hurt and w.unit(i) and w.unit(i).hp >= HURT_HP]
        self.handovers += 1
        if not fresh and self.state == "run" and self.handovers <= MAX_HANDOVERS:
            # nobody to take over yet: it keeps running home with the elephant in tow and circles
            # there (the plan sends the killers to the kill site); no more spears from it
            if not self.recent(w, ("nofresh",), 20.0):
                self.mark(w, ("nofresh",))
                self.say(w, "%s and the lurer #%d is hurt (%.0f hp), nobody fresh yet: it runs home" % (why, v.id, v.hp))
            self.handovers -= 1
            self.moving = True
            return
        if not fresh or self.handovers > MAX_HANDOVERS:
            self.fail(w, "%s and the lurer #%d is hurt (%.0f hp), nobody fresh" % (why, v.id, v.hp))
            return
        new = fresh[0]
        self.waiters.remove(new)
        self.waiters.append(v.id)
        self.say(w, "%s and the lurer #%d is hurt (%.0f hp): #%d takes over" % (why, v.id, v.hp, new))
        self.lurer = new
        self._enter(w, "provoke")

    def _away_dir(self, w, v, e, toward_tc=True):
        ax, ay = geom.unit(v.x - e.x, v.y - e.y)
        if not toward_tc:
            return ax, ay, ax, ay
        hx, hy = self._home(w)
        bx, by = geom.unit(hx - v.x, hy - v.y)
        dx, dy = geom.unit(ax + 1.2 * bx, ay + 1.2 * by)
        if dx * ax + dy * ay < 0.5:                  # the TC is behind the elephant: round it, sideways
            px, py = -ay, ax
            if px * bx + py * by < 0:
                px, py = -px, -py
            dx, dy = geom.unit(ax + px, ay + py)
        return dx, dy, ax, ay

    def _flee(self, w, o, v, e, solo=False):
        """Away from the elephant, towards the TC, on open ground; a long leg so one order lasts.
        A villager (1.10) outruns an elephant (1.00) and it gives up beyond ~4.4 tiles, while a
        villager that stops needs the order lag to get going again: so the lurer never stops but
        runs at an angle (slalom) once the gap is comfortable, keeping it at 2.8-3.6 tiles.
        solo (the kill round the home): within 7 tiles of the home the pull towards it is OFF - it
        would turn the lurer back into the elephant once the home is behind it."""
        hx, hy = self._home(w)
        dh = math.hypot(v.x - hx, v.y - hy)
        pull = not (solo and dh < 10.0)
        dx, dy, ax, ay = self._away_dir(w, v, e, toward_tc=pull)
        if solo and dh < 4.5:
            # next to the building the flee gets turned round its footprint and the elephant cuts the
            # corner (sim: the lurer died 59/60 times there): get clear of the building first
            ox, oy = geom.unit(v.x - hx, v.y - hy)
            dx, dy = geom.unit(ax + 0.8 * ox, ay + 0.8 * oy)
        d = v.dist(e.x, e.y)
        # the slalom keeps the elephant interested (it gives up beyond ~4.4): at 40 degrees the away-
        # speed is 1.1 * cos 40 = 0.84 < its 1.0, fine when the next order comes a second later; at x2
        # it closed 3.0 -> 0.6 during one leg (lure14 #5702) - the angle flattens with the lag so the
        # away-speed stays at its 1.0 (25 degrees at L = 2)
        slalom_deg = max(20.0, 40.0 - 15.0 * max(0.0, getattr(w, "lag", 1.0) - 1.0))
        if d > SLALOM_D and pull:
            hx, hy = self._home(w)
            bx, by = geom.unit(hx - v.x, hy - v.y)
            best = None
            for deg in (slalom_deg, -slalom_deg):
                rx, ry = geom.rot(dx, dy, math.radians(deg))
                score = rx * bx + ry * by
                if best is None or score > best[0]:
                    best = (score, rx, ry)
            dx, dy = best[1], best[2]
        ux, uy, run = geom.open_dir(w.passable, v.x, v.y, dx, dy, ax, ay, max_len=6.0 if solo else 3.5)
        o.move([v.id], v.x + ux * run, v.y + uy * run)
        self.mark(w, ("mv", v.id))
        self.moving = True

    def _circle(self, w, o, v, e):
        """Round the TC on the side away from the elephant (kill state, the lurer is chased)."""
        ax, ay = geom.unit(v.x - e.x, v.y - e.y)
        hx, hy = self._home(w)
        rx, ry = geom.unit(v.x - hx, v.y - hy)
        tx, ty = -ry, rx
        if tx * ax + ty * ay < 0:
            tx, ty = -tx, -ty
        pull = (LURE_CIRCLE - math.hypot(v.x - hx, v.y - hy)) * 0.3
        dx, dy = geom.unit(tx + 0.6 * ax + pull * rx, ty + 0.6 * ay + pull * ry)
        if dx * ax + dy * ay < 0.2:
            dx, dy = geom.unit(dx + ax, dy + ay)
        ux, uy, run = geom.open_dir(w.passable, v.x, v.y, dx, dy, ax, ay, far=3.0, max_len=4.0)
        o.move([v.id], v.x + ux * run, v.y + uy * run)
        self.mark(w, ("mv", v.id))
        self.moving = True

    def _throw_once(self, w, o, v, e, d, run=None):
        """One spear and away: attack, and the run-home order as soon as we are in throwing range
        (it lands ~1 s later, right after the spear). Returns True while the spear is pending.
        `run` = the move issued after the throw (default: flee home; the solo kill circles)."""
        run = run or self._flee
        if self.spear is None:
            if d < 2.6 and w.target_of(self.eid) == v.id:
                # it is already on us (lure18: a re-provoke at 2.5 tiles, two hits, the lurer died):
                # no throw is worth a hit - run now, the chase is what we wanted anyway
                self.spear = (e.hp, v.hp, w.now)
                run(w, o, v, e)
                return True
            act = w.action_of(v.id)
            # (re)issue the attack only when the lurer is not already on its way: every order costs the
            # unit ~1 s standing still (lockstep), and in the fog the game does not report the target
            if act != ("attack", self.eid) and not (act == ("move",) and self.recent(w, ("atk", v.id), 15.0))                     and not self.recent(w, ("atk", v.id), 2.5):
                o.attack([v.id], self.eid)
                self.mark(w, ("atk", v.id))
            # the run order must LAND between the throw (arrival in range + 0.5) and the elephant's
            # first hit (arrival + ~2.0), whatever the lag L: it goes out when the lurer is L - 1 s of
            # closing-in from range (L = 1: on arrival, as before; x2 / L = 2: one second before -
            # issued on arrival the hit came first, lure13: 4 hand-overs in 8), and not within 0.6 s
            # of the attack order itself (the throw is 0.5 s after that lands)
            L = getattr(w, "lag", 1.0)
            pv = self.dprev.get(v.id)
            self.dprev[v.id] = (d, w.now)
            closing = 0.0
            if pv is not None and 0.15 <= w.now - pv[1] <= 1.5:
                closing = (pv[0] - d) / (w.now - pv[1])
            elif pv is not None and w.now - pv[1] < 0.15:
                self.dprev[v.id] = pv                         # keep the older sample for a real rate
            left = max(0.0, d - (SPEAR_RANGE + 0.25))
            soon = left <= 0.0 or (closing > 0.3 and left / closing <= max(0.0, L - 1.0))
            hold = w.now - self._last.get(("atk", v.id), -1e9) < 0.6 and d > 2.3
            if soon and not hold:
                self.spear = (e.hp, v.hp, w.now)
                run(w, o, v, e)
            return True
        if e.hp < self.spear[0] - 0.01 or v.hp < self.spear[1] - 0.01:
            self.spear = None
            return False                                  # it landed (or we were hit): go
        if w.now - self.spear[2] > 3.0:
            self.spear = None                             # nothing happened (it walked off): again
            self.mark(w, ("atk", v.id))
            self._last[("atk", v.id)] = w.now - 2.5
        return True

    def _kite(self, w, o, u, e):
        """A killer the elephant turns on steps back out of its reach, on open ground, towards the TC."""
        dx, dy, ax, ay = self._away_dir(w, u, e)
        ux, uy, run = geom.open_dir(w.passable, u.x, u.y, dx, dy, ax, ay, far=3.0, max_len=4.0)
        o.move([u.id], u.x + ux * run, u.y + uy * run)
        self.mark(w, ("mv", u.id))

    # ---------------------------------------------------------------- slow
    def tick(self, w, o):
        if self.t0 is None:
            self.t0 = self.t_state = w.now
        e = w.track(self.eid)
        if e is None and self.state != "done":
            # not tracked for a moment (fog / a stale read) is not dead: lure17 #5526 was finished
            # "down" at 33 hp and re-lured 3 minutes later - gone for 3 s before it counts as down
            if self.none_since is None:
                self.none_since = w.now
            if w.now - self.none_since < 3.0:
                return
        else:
            self.none_since = None
        if e is None or e.hp <= 0:
            self.finish(w, "elephant #%d down after %.0f s" % (self.eid, w.now - self.t0))
            return
        v = w.unit(self.lurer)
        if v is None:
            self.waiters = [i for i in self.waiters if w.unit(i)]
            fresh = [i for i in self.waiters if i not in self.hurt]
            if not fresh:
                self.fail(w, "the lurer died and nobody fresh is left")
                return
            self.say(w, "lurer #%d is gone: #%d takes over" % (self.lurer, fresh[0]))
            self.lurer = fresh[0]
            self.waiters.remove(fresh[0])
            self._enter(w, "provoke")
            return
        if self.t0 == w.now or getattr(self, "d0", None) is None:
            hx0, hy0 = self._home(w)
            self.d0 = math.hypot(e.x - hx0, e.y - hy0)   # how far it is lured from: the time limit scales
        limit = TIMEOUT + max(0.0, self.d0 - 25.0) * 2.0
        if self.state in ("provoke", "run") and w.now - self.t0 > limit:
            self.fail(w, "lure took over %.0f s (from %.0f tiles)" % (limit, self.d0))
            return
        if self.d_prov is None or self.d_prov[0] != self.t_state:
            self.d_prov = (self.t_state, v.dist(e.x, e.y))       # the walk at the start of this provoke
        if self.state == "provoke" and w.now - self.t_state > PROVOKE_TIMEOUT + self.d_prov[1] / 1.0:
            self.fail(w, "elephant does not react")
            return
        if self.state != "kill":
            # the waiters stand at the home building on the elephant's side, ready before it arrives -
            # to the SIDES of its line (3 tiles out = spear range), not on it: bunched on the arrival
            # point they threw from half a tile and the first one targeted died before its step back
            # could land (sim x2)
            hx, hy = self._home(w)
            ux, uy = geom.unit(e.x - hx, e.y - hy)
            nx, ny = -uy, ux
            for k, i in enumerate(self.waiters):
                along, lat = WAIT_SPOTS[min(k, len(WAIT_SPOTS) - 1)]
                wx, wy = hx + ux * along + nx * lat, hy + uy * along + ny * lat
                if not w.passable(int(wx), int(wy)):
                    wx, wy = hx + ux * along - nx * lat, hy + uy * along - ny * lat
                u = w.unit(i)
                if u is not None and u.dist(wx, wy) > 2.0 and not self.recent(w, ("mv", i), 4.0):
                    o.move([i], wx, wy)
                    self.mark(w, ("mv", i))

    def _run_step(self, w, o, v, e, d, tgt, stopped, solo):
        """Flee while chased, stop once it gave up, one more spear when it stands 3-8 tiles away.
        solo: the kill round the home with nobody waiting (the user: one spear, move on, round the
        building until it dies) - no hand-over, no limit on spears, the flee stays by the home."""
        if self.spear is not None:                        # one more spear on its way
            if not self._throw_once(w, o, v, e, d):
                self.moving = True
            return
        chasing = tgt == v.id
        if chasing and d < KEEP_MIN:
            if not self.recent(w, ("mv", v.id), 0.4) or (d < 3.0 and not self.recent(w, ("mv", v.id), 0.15)):
                self._flee(w, o, v, e, solo=solo)
        elif not chasing and d < 2.6 and self.coming:
            if not self.recent(w, ("mv", v.id), 0.4):
                self._flee(w, o, v, e, solo=solo)        # on top of us (a target flicker): away anyway
        elif self.moving and not chasing and not self.recent(w, ("stop", v.id), 0.5):
            # it gave up: stand right here and wait for it / spear it again at once (the user: without
            # the wait the lurer ran on to 6-7 tiles and it walked back home every time)
            o.stop([v.id])
            self.mark(w, ("stop", v.id))
            self.moving = False
        elif not chasing and tgt is None and d <= 9.0 and (solo or stopped > 0.3 or d >= 3.0):
            if v.hp < HURT_HP and not solo:
                self._hand_over(w, o, v, "it stopped following")
            elif not self.recent(w, ("rehit", v.id), 2.0):
                if solo:
                    hx, hy = self._home(w)
                    he = math.hypot(hx - e.x, hy - e.y)
                    if he > 2.5:
                        ux, uy = geom.unit(hx - e.x, hy - e.y)
                        side = ((v.x - e.x) * ux + (v.y - e.y) * uy) / max(d, 0.1)
                        if side < 0.6 and not self.recent(w, ("pos", v.id), 2.0):
                            # stand between the elephant and the home first: the spear-and-flee then
                            # drags it towards the home instead of away from it
                            px, py = e.x + ux * 3.2, e.y + uy * 3.2
                            o.move([v.id], px, py)
                            self.mark(w, ("pos", v.id))
                            self.mark(w, ("mv", v.id))
                            return
                self.reprovoke += 1
                if self.reprovoke > MAX_REPROVOKE and not solo:
                    if e.hp <= 15.0 and not self.anywhere:
                        # a far one that keeps giving up has taken 12 spears: nearly dead - killed where
                        # it stands by the lurer and the waiters walking out (lure22: two 37-47-tile
                        # lures failed "does not follow" and left 1-5-hp elephants in the field)
                        self.anywhere = True
                        self.say(w, "elephant #%d (%.0f hp) will not follow after %d spears: killed where it stands" % (
                            self.eid, e.hp, self.reprovoke))
                        self._enter(w, "kill")
                        return
                    self.fail(w, "elephant does not follow")
                    return
                self.mark(w, ("rehit", v.id))
                self._last.pop(("atk", v.id), None)
                self._throw_once(w, o, v, e, d, run=(lambda w_, o_, v_, e_: self._flee(w_, o_, v_, e_, solo=True)) if solo else None)
        elif d > 9.0 and tgt is None and not self.recent(w, ("mv", v.id), 1.5):
            o.move([v.id], e.x, e.y)                      # far behind and not coming: walk back to it
            self.mark(w, ("mv", v.id))

    # ---------------------------------------------------------------- fast (20 Hz)
    def micro(self, w, o):
        if self.state not in ("provoke", "run", "kill", "solo"):
            return
        e = w.track(self.eid)
        v = w.unit(self.lurer)
        if e is None or v is None or e.hp <= 0:
            if not self.recent(w, ("dbg0",), 5.0):
                self.mark(w, ("dbg0",))
                self.say(w, "LUREDBG micro idle: elephant %s, lurer #%s %s" % (
                    "None" if e is None else ("hp %.0f" % e.hp), self.lurer, "None" if v is None else "ok"))
            return
        d = v.dist(e.x, e.y)
        tgt = w.target_of(self.eid)
        if self.epos is None or w.now - self.epos[2] >= 0.3:
            if self.epos is not None:
                mx, my = e.x - self.epos[0], e.y - self.epos[1]
                moved = math.hypot(mx, my) > 0.1
                self.coming = (tgt == v.id) or (moved and (v.x - e.x) * mx + (v.y - e.y) * my > 0)
                if moved:
                    self.last_move_t = w.now
            self.epos = (e.x, e.y, w.now)
        if self.last_move_t is None:
            self.last_move_t = w.now
        stopped = w.now - self.last_move_t

        if self.state == "provoke":
            if not self.recent(w, ("dbg", v.id), 5.0):
                self.mark(w, ("dbg", v.id))
                self.say(w, "LUREDBG provoke: lurer #%d (%.1f,%.1f) %.0f hp, elephant (%.1f,%.1f) %.0f hp, d=%.1f, act=%s, chasing=%s" % (
                    v.id, v.x, v.y, v.hp, e.x, e.y, e.hp, d, w.action_of(v.id), tgt))
            if not self.recent(w, ("lion", v.id), 1.0):
                self.mark(w, ("lion", v.id))
                lion = next((a for a in w.animals() if a.kind == "lion" and a.hp > 0 and v.dist(a.x, a.y) <= 5.0), None)
                if lion is not None:
                    # a lion on the way kills the lurer (lure13: #4717 at 0.4 tiles): home, try later
                    hx, hy = self._home(w)
                    o.move([v.id], hx + 2.5, hy + 2.5)
                    self.fail(w, "lion #%d %.1f tiles from the lurer on the way" % (lion.id, v.dist(lion.x, lion.y)))
                    return
            if self.hp0 is None:
                self.hp0, self.vhp0 = e.hp, v.hp
                if v.hp < HURT_HP:
                    self._hand_over(w, o, v, "no more spears")
                    return
            if not self._throw_once(w, o, v, e, d):
                self.say(w, "elephant #%d hit once (%.0f/%.0f): run home" % (self.eid, e.hp, e.maxhp))
                self._enter(w, "run")
                self.moving = True
            return

        hx, hy = self._home(w)
        if SOLO and self.state == "run" and geom.tc_edge_dist(e.x, e.y, hx, hy) <= KILL_NEAR + 4.0                 and not any(w.unit(i) is not None for i in self.waiters):
            # nobody assigned to wait at home (the user): the lurer kills it alone - spear and flee in the
            # open ground around the home; next to the building the flee gets cornered (sim: 59/60 deaths).
            # Waiters assigned but still walking in are no reason for solo (tdiag: an 8-tile lure reached
            # home before its waiters, the lurer went solo and died): the kill phase circles the home
            # until they arrive
            self.say(w, "elephant #%d is %.1f tiles from home, nobody waiting: the lurer kills it alone" % (
                self.eid, geom.tc_edge_dist(e.x, e.y, hx, hy)))
            self._enter(w, "solo")
            return
        if self.state == "run" and geom.tc_edge_dist(e.x, e.y, hx, hy) <= KILL_NEAR:
            self.say(w, "elephant #%d is %.1f tiles from home after %.0f s: everybody attacks" % (
                self.eid, geom.tc_edge_dist(e.x, e.y, hx, hy), w.now - self.t0))
            self._enter(w, "kill")
            return
        if self.state == "solo":
            self._run_step(w, o, v, e, d, tgt, stopped, solo=True)
            return

        if self.state in ("run", "kill") and v.hp <= 15.0 and not self.anywhere and self.waiters:
            # one blow from death (an elephant hit is 10): no more luring with this one - a fresh waiter
            # takes over (lure9 at x2: 3 lurers died at 5 hp waiting for the next hand-over point).
            # The fresh one must be near: while it walks out, the hurt lurer keeps running home with
            # the elephant in tow (lure13: the elephant followed the hurt one anyway, the fresh one
            # walked 36 tiles out to provoke it again and the 43-tile lure timed out)
            fresh = [i for i in self.waiters if i not in self.hurt and w.unit(i) is not None and w.unit(i).hp >= HURT_HP]
            fresh.sort(key=lambda i: w.unit(i).dist(e.x, e.y))
            if self.state == "kill":
                # the circling role passes to a fresh killer, no provoke (the elephant is already on
                # us and the killers keep throwing); nobody fresh: the hurt one circles on
                self.hurt.add(v.id)
                if fresh:
                    new = fresh[0]
                    self.waiters.remove(new)
                    self.waiters.append(v.id)
                    self.say(w, "the circling lurer #%d is hurt (%.0f hp): #%d circles instead" % (v.id, v.hp, new))
                    self.lurer = new
                    self._kite(w, o, v, e)
                return
            if not fresh or w.unit(fresh[0]).dist(e.x, e.y) <= 8.0:
                self.waiters = fresh + [i for i in self.waiters if i not in fresh]
                self._hand_over(w, o, v, "one blow from death")
                return
            if not self.recent(w, ("meet", fresh[0]), 3.0):
                self.mark(w, ("meet", fresh[0]))
                o.move([fresh[0]], e.x, e.y)                  # comes to meet it: takes over at 8 tiles
        if self.state == "run":
            if not self.recent(w, ("dbgr", v.id), 5.0):
                self.mark(w, ("dbgr", v.id))
                self.say(w, "LUREDBG run: lurer #%d (%.1f,%.1f) %.0f hp, elephant (%.1f,%.1f) %.0f hp, d=%.1f, home %.1f, coming=%s, stopped=%.1f, chasing=%s, reprovoke=%d" % (
                    v.id, v.x, v.y, v.hp, e.x, e.y, e.hp, d, geom.tc_edge_dist(e.x, e.y, hx, hy), self.coming, stopped, tgt, self.reprovoke))
            self._run_step(w, o, v, e, d, tgt, stopped, solo=False)
            return

        # ---- kill: the waiters throw from range, whoever is chased steps back; the lurer leads
        near_tc = self.anywhere or geom.tc_edge_dist(e.x, e.y, hx, hy) <= KILL_NEAR + 2
        kst = self.__dict__.setdefault("kst", {})
        for i in self.waiters:
            u = w.unit(i)
            if u is None:
                continue
            du = u.dist(e.x, e.y)
            st = kst.setdefault(i, {})
            sp = st.get("spear")
            if sp is not None and (e.hp < sp[0] - 0.01 or w.now - sp[1] > 4.0):
                st.pop("spear", None)                     # it landed (or nothing came of it): throw again
                st.pop("stepped", None)
                sp = None
            L = getattr(w, "lag", 1.0)
            # (a "hurt waiters never throw" rule was tried here: sim x1 56/60 -> 34/60, x2 no gain - removed)
            if tgt == i and du < KITE_D + 1.0 * max(0.0, L - 1.0):
                if not self.recent(w, ("mv", i), 0.4):
                    self._kite(w, o, u, e)
            elif L >= 1.5 and sp is not None and not st.get("stepped") and w.now >= sp[2]:
                # throw-and-step (x2): the step back goes out so that it lands right after the spear
                # and before the elephant, turning on the thrower, reaches it (see the module note)
                self._kite(w, o, u, e)
                st["stepped"] = True
            elif near_tc and (du <= 7.0 or self.anywhere) and w.action_of(i) != ("attack", self.eid)                     and not self.recent(w, ("atk", i), 1.5) and (sp is None or L < 1.5):
                o.attack([i], self.eid)
                self.mark(w, ("atk", i))
                st["spear"] = (e.hp, w.now, w.now + 1.0 + max(0.0, du - (SPEAR_RANGE - 0.3)) / 1.1)
                st.pop("stepped", None)
        chased = tgt == v.id
        live_waiters = [i for i in self.waiters if w.unit(i) is not None and w.unit(i).dist(e.x, e.y) <= 9.0]
        if not live_waiters and not self.anywhere:
            if SOLO:
                # solo kill round the home (the user): the same spear-and-away loop as the run, kept by
                # the home by the flee's pull towards it; the elephant (1.00) never catches the lurer
                self._run_step(w, o, v, e, d, tgt, stopped, solo=True)
                return
            # nobody here yet: circle the home and keep it interested until the killers arrive
            if chased and d < KEEP_MIN and not self.recent(w, ("mv", v.id), 0.4):
                self._circle(w, o, v, e)
            elif not chased and stopped > 2.5 and 3.0 <= d <= 9.0 and not self.recent(w, ("rehit", v.id), 6.0):
                self.mark(w, ("rehit", v.id))
                self._last.pop(("atk", v.id), None)
                self._throw_once(w, o, v, e, d)           # it lost interest: one spear, run again
            return
        if chased and e.hp > 0.3 * e.maxhp and not self.anywhere:
            if d < KEEP_MIN and not self.recent(w, ("mv", v.id), 0.4):
                self._circle(w, o, v, e)
        elif chased and d < KITE_D:
            if not self.recent(w, ("mv", v.id), 0.4):
                self._kite(w, o, v, e)
        elif w.action_of(v.id) != ("attack", self.eid) and not self.recent(w, ("atk", v.id), 1.5):
            o.attack([v.id], self.eid)
            self.mark(w, ("atk", v.id))
