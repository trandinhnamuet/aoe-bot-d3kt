"""2D simulator for the hunting micro: villagers, gazelles, elephants, forests, the TC, and the
lockstep order lag - with the numbers measured in the user's recorded games (tools/speed_study.py,
tools/gazelle_study.py, arena LUREDBG lines). It implements the World / Orders interface of
brain.iface, so the real task code runs here unchanged, a thousand times in a few seconds.

    sim = Sim(seed=1); sim.add_forest(40, 20, 3); e = sim.add_elephant(45, 30)
    v = sim.add_villager(31, 32); task = Lure(e, v, waiters=[...]); sim.run([task], max_t=240)
"""
import math
import random

from brain import geom
from brain.iface import U

PARAMS = dict(
    DT=0.05,            # simulation step, game seconds
    LAG=1.0,            # an order reaches the game this many game seconds after it is given (x1 speed)
    VIL_SPEED=1.10, VIL_HP=25.0, VIL_LOS=4.0,
    SPEAR_RANGE=3.0, SPEAR_DMG=4.0, SPEAR_WINDUP=0.5, SPEAR_RELOAD=1.5,
    GAZ_HP=8.0, GAZ_SPEED=1.85, GAZ_FLEE_R=(2.1, 0.5, 1.3, 2.9), GAZ_HOP=(2.75, 0.5, 1.5, 4.0),
    GAZ_DIR_NOISE=8.0, GAZ_REST=0.4,
    ELE_HP=45.0, ELE_SPEED=1.00, ELE_HIT_R=2.0, ELE_DMG=10.0, ELE_RELOAD=1.0, ELE_LOSE_R=4.4,
    ELE_TURN=0.5,       # an elephant turning on a new target stands this long first (turn / acceleration)
    TC_LOS=7.0,
)
KIND_TYPE = {"villager": 83, "gazelle": 65, "elephant": 48, "lion": 126}


class Ent:
    __slots__ = ("id", "kind", "x", "y", "hp", "maxhp", "alive", "st", "action", "reload", "windup")

    def __init__(self, id, kind, x, y, hp):
        self.id, self.kind, self.x, self.y, self.hp, self.maxhp = id, kind, x, y, hp, hp
        self.alive, self.st, self.action, self.reload, self.windup = True, {}, ("idle",), 0.0, 0.0

    def view(self):
        return U(self.id, self.x, self.y, self.hp, self.maxhp, KIND_TYPE.get(self.kind, 0), self.kind)


class Sim:
    def __init__(self, W=64, H=64, tc=(32.0, 32.0), seed=0, params=None):
        self.p = dict(PARAMS)
        if params:
            self.p.update(params)
        self.rng = random.Random(seed)
        self.W, self.H = W, H
        self.tc = (float(tc[0]), float(tc[1]))
        self.blk = bytearray(W * H)
        self.t = 0.0
        self.ents = {}
        self._next = 1
        self.pending = []
        self.seen = {}
        self.events = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                self.block(int(self.tc[0]) + dx, int(self.tc[1]) + dy)

    # ---------------------------------------------------------------- building the scene
    def block(self, x, y):
        if 0 <= x < self.W and 0 <= y < self.H:
            self.blk[y * self.W + x] = 1

    def add_forest(self, cx, cy, r):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            for y in range(int(cy - r) - 1, int(cy + r) + 2):
                if math.hypot(x + 0.5 - cx, y + 0.5 - cy) <= r:
                    self.block(x, y)

    def _add(self, kind, x, y, hp):
        e = Ent(self._next, kind, float(x), float(y), hp)
        self._next += 1
        self.ents[e.id] = e
        return e

    def add_villager(self, x, y, hp=None):
        return self._add("villager", x, y, hp or self.p["VIL_HP"]).id

    def add_gazelle(self, x, y, home=None):
        g = self._add("gazelle", x, y, self.p["GAZ_HP"])
        m, sd, lo, hi = self.p["GAZ_FLEE_R"]
        g.st = {"flee_r": min(hi, max(lo, self.rng.gauss(m, sd))), "hop": None, "rest": 0.0,
                "home": home or (x, y), "wt": self.rng.uniform(2, 8), "hit_by": None}
        return g.id

    def add_herd(self, cx, cy, n):
        ids = []
        for _ in range(n):
            for _try in range(50):
                x, y = cx + self.rng.uniform(-2.5, 2.5), cy + self.rng.uniform(-2.5, 2.5)
                if self.passable(int(x), int(y)):
                    ids.append(self.add_gazelle(x, y, (cx, cy)))
                    break
        return ids

    def add_elephant(self, x, y):
        e = self._add("elephant", x, y, self.p["ELE_HP"])
        e.st = {"mode": "idle", "target": None, "home": (x, y)}
        return e.id

    # ---------------------------------------------------------------- World
    @property
    def now(self):
        return self.t

    def passable(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H and not self.blk[y * self.W + x]

    def visible(self, x, y):
        if math.hypot(x - self.tc[0], y - self.tc[1]) <= self.p["TC_LOS"]:
            return True
        los = self.p["VIL_LOS"]
        return any(e.alive and e.kind == "villager" and math.hypot(e.x - x, e.y - y) <= los for e in self.ents.values())

    def units(self):
        return [e.view() for e in self.ents.values() if e.alive and e.kind == "villager"]

    def unit(self, i):
        e = self.ents.get(i)
        return e.view() if e and e.alive and e.kind == "villager" else None

    @property
    def lag(self):
        return self.p["LAG"]

    def animals(self):
        return [e.view() for e in self.ents.values() if e.alive and e.kind != "villager" and self.visible(e.x, e.y)]

    def animal(self, i):
        e = self.ents.get(i)
        return e.view() if e and e.alive and e.kind != "villager" and self.visible(e.x, e.y) else None

    def track(self, i):
        e = self.ents.get(i)
        return e.view() if e and e.alive and e.kind != "villager" else None

    def last_seen(self, i):
        return self.seen.get(i)

    def action_of(self, i):
        """What one of our units does now: ("attack", target_id) | ("move",) | ("idle",)."""
        e = self.ents.get(i)
        if not e or not e.alive:
            return None
        a = e.action
        return ("attack", a[1]) if a[0] == "attack" else (a[0],)

    def target_of(self, i):
        """Who an animal is attacking / chasing now (the game exposes the unit's action target)."""
        e = self.ents.get(i)
        if not e or not e.alive:
            return None
        if e.kind == "elephant" and e.st.get("mode") == "chase":
            return e.st.get("target")
        return None

    # ---------------------------------------------------------------- Orders (lockstep lag)
    def move(self, ids, x, y):
        self.pending.append((self.t + self.p["LAG"], "move", list(ids), (float(x), float(y))))

    def attack(self, ids, tid):
        self.pending.append((self.t + self.p["LAG"], "attack", list(ids), tid))

    def stop(self, ids):
        self.pending.append((self.t + self.p["LAG"], "stop", list(ids), None))

    def _apply_orders(self):
        due = [o for o in self.pending if o[0] <= self.t]
        if not due:
            return
        self.pending = [o for o in self.pending if o[0] > self.t]
        for _, kind, ids, arg in due:
            for i in ids:
                e = self.ents.get(i)
                if not e or not e.alive:
                    continue
                if kind == "move":
                    e.action = ("move", arg[0], arg[1])
                    e.st["path"] = self._path(e.x, e.y, arg[0], arg[1])
                elif kind == "attack":
                    e.action = ("attack", arg)
                    e.st["path"], e.st["path_t"] = None, -9.0
                else:
                    e.action = ("idle",)
                e.windup = 0.0

    # ---------------------------------------------------------------- pathing (game units path round obstacles)
    def _nearest_passable(self, x, y):
        if self.passable(x, y):
            return x, y
        for r in range(1, 8):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.passable(x + dx, y + dy):
                        return x + dx, y + dy
        return None

    def _path(self, sx, sy, tx, ty):
        """Tile-centre waypoints from (sx, sy) to (tx, ty) (or the nearest reachable tile), by BFS."""
        s0 = (int(sx), int(sy))
        goal = self._nearest_passable(int(tx), int(ty))
        if goal is None:
            return []
        if s0 == goal:
            return [(tx, ty)] if self.passable(int(tx), int(ty)) else [(goal[0] + 0.5, goal[1] + 0.5)]
        prev = {s0: None}
        frontier = [s0]
        found = False
        while frontier and not found:
            nxt = []
            for (x, y) in frontier:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if not (dx or dy):
                            continue
                        nx, ny = x + dx, y + dy
                        if (nx, ny) in prev or not self.passable(nx, ny):
                            continue
                        if dx and dy and not (self.passable(x + dx, y) and self.passable(x, y + dy)):
                            continue                      # no corner cutting
                        prev[(nx, ny)] = (x, y)
                        if (nx, ny) == goal:
                            found = True
                            break
                        nxt.append((nx, ny))
                    if found:
                        break
                if found:
                    break
            frontier = nxt
        if not found:
            return []
        path = []
        c = goal
        while c is not None and c != s0:
            path.append((c[0] + 0.5, c[1] + 0.5))
            c = prev[c]
        path.reverse()
        if self.passable(int(tx), int(ty)):
            path[-1] = (tx, ty)
        return path

    def _los(self, x0, y0, x1, y1):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 0.3))
        return all(self.passable(int(x0 + (x1 - x0) * i / n), int(y0 + (y1 - y0) * i / n)) for i in range(1, n + 1))

    def _follow(self, e, step):
        """Walk along e.st['path'] (string-pulled: skip waypoints in line of sight); True while there is
        somewhere to go."""
        path = e.st.get("path")
        while path and len(path) >= 2 and self._los(e.x, e.y, path[1][0], path[1][1]):
            path.pop(0)
        while path:
            wx, wy = path[0]
            if math.hypot(wx - e.x, wy - e.y) < 0.25:
                path.pop(0)
                continue
            if not self._walk(e, wx, wy, step):
                path.pop(0)
                continue
            return True
        return False

    # ---------------------------------------------------------------- physics
    def _walk(self, e, tx, ty, step):
        """Move e up to `step` towards (tx, ty); slides round a blocked tile. False if it could not move."""
        dx, dy = tx - e.x, ty - e.y
        L = math.hypot(dx, dy)
        if L < 1e-6:
            return False
        s = min(step, L)
        ux, uy = dx / L, dy / L
        for deg in (0, 45, -45, 90, -90):
            vx, vy = geom.rot(ux, uy, math.radians(deg))
            nx, ny = e.x + vx * s, e.y + vy * s
            if self.passable(int(nx), int(ny)):
                e.x, e.y = nx, ny
                return True
        return False

    def _damage(self, tgt, dmg, by):
        tgt.hp -= dmg
        self.events.append((round(self.t, 2), "hit", by.kind, by.id, tgt.kind, tgt.id, round(tgt.hp, 1)))
        if tgt.kind == "gazelle":
            tgt.st["hit_by"] = by.id
        elif tgt.kind == "elephant" and by.kind == "villager":
            if tgt.st.get("target") != by.id or tgt.st.get("mode") != "chase":
                tgt.st["turn"] = self.p["ELE_TURN"]
            tgt.st["mode"], tgt.st["target"] = "chase", by.id
            tgt.st.setdefault("attackers", {})[by.id] = self.t
        if tgt.hp <= 0:
            tgt.alive = False
            tgt.action = ("idle",)
            self.events.append((round(self.t, 2), "dead", tgt.kind, tgt.id, round(tgt.x, 1), round(tgt.y, 1)))

    def _step_villager(self, v, dt):
        p = self.p
        a = v.action
        if a[0] == "move":
            if not self._follow(v, p["VIL_SPEED"] * dt):
                v.action = ("idle",)
        elif a[0] == "attack":
            tgt = self.ents.get(a[1])
            if not tgt or not tgt.alive:
                v.action = ("idle",)
                return
            d = math.hypot(tgt.x - v.x, tgt.y - v.y)
            if d > p["SPEAR_RANGE"]:
                path = v.st.get("path")
                if not path or self.t - v.st.get("path_t", -9) > 1.0 or \
                        math.hypot(path[-1][0] - tgt.x, path[-1][1] - tgt.y) > 1.5:
                    v.st["path"], v.st["path_t"] = self._path(v.x, v.y, tgt.x, tgt.y), self.t
                self._follow(v, p["VIL_SPEED"] * dt)
                if d > p["SPEAR_RANGE"] + 0.6:
                    v.windup = 0.0                       # (aiming is kept while it just steps after it)
            elif v.reload <= 0:
                v.windup += dt
                if v.windup >= p["SPEAR_WINDUP"]:
                    self._damage(tgt, p["SPEAR_DMG"], v)
                    v.windup, v.reload = 0.0, p["SPEAR_RELOAD"]

    def _hop_target(self, x, y, dx, dy, L):
        for deg in (0, 35, -35, 70, -70, 110, -110):
            ux, uy = geom.rot(dx, dy, math.radians(deg))
            free = 0.0
            k = 0.25
            while k <= L:
                if not self.passable(int(x + ux * k), int(y + uy * k)):
                    break
                free = k
                k += 0.25
            if free >= min(L, 1.0):
                return x + ux * free, y + uy * free
        return None

    def _step_gazelle(self, g, dt):
        p, st = self.p, g.st
        if st["hop"] is not None:
            tx, ty, spd = st["hop"]
            moved = self._walk(g, tx, ty, spd * dt)
            if not moved or math.hypot(tx - g.x, ty - g.y) < 0.1:
                st["hop"], st["rest"] = None, p["GAZ_REST"]
            return
        if st["rest"] > 0:
            st["rest"] -= dt
        hit = st["hit_by"]
        st["hit_by"] = None
        threat = None
        if hit is not None and hit in self.ents:
            threat = (self.ents[hit].x, self.ents[hit].y)
        elif st["rest"] <= 0:
            best = st["flee_r"]
            for e in self.ents.values():
                if e.alive and e.kind == "villager":
                    d = math.hypot(e.x - g.x, e.y - g.y)
                    if d < best:
                        best, threat = d, (e.x, e.y)
        if threat is not None:
            ax, ay = geom.unit(g.x - threat[0], g.y - threat[1])
            if ax == 0 and ay == 0:
                ax, ay = 1.0, 0.0
            ax, ay = geom.rot(ax, ay, math.radians(self.rng.gauss(0, p["GAZ_DIR_NOISE"])))
            m, sd, lo, hi = p["GAZ_HOP"]
            L = min(hi, max(lo, self.rng.gauss(m, sd)))
            tgt = self._hop_target(g.x, g.y, ax, ay, L)
            if tgt is not None:
                st["hop"] = (tgt[0], tgt[1], p["GAZ_SPEED"])
            else:
                st["rest"] = p["GAZ_REST"]                 # cornered: it stays
            return
        st["wt"] -= dt
        if st["wt"] <= 0:
            st["wt"] = self.rng.uniform(4, 10)
            tx, ty = g.x + self.rng.uniform(-1.5, 1.5), g.y + self.rng.uniform(-1.5, 1.5)
            if self.passable(int(tx), int(ty)):
                st["hop"] = (tx, ty, 0.4)

    def _step_elephant(self, e, dt):
        p, st = self.p, e.st
        if st["mode"] == "chase":
            tgt = self.ents.get(st["target"])
            if not tgt or not tgt.alive or math.hypot(tgt.x - e.x, tgt.y - e.y) > p["ELE_LOSE_R"]:
                # the target is gone / got away: another recent attacker in reach, else go home
                others = [self.ents[i] for i, t0 in st.get("attackers", {}).items()
                          if i in self.ents and self.ents[i].alive and i != st["target"] and self.t - t0 < 6.0
                          and math.hypot(self.ents[i].x - e.x, self.ents[i].y - e.y) <= p["ELE_LOSE_R"]]
                if others:
                    st["target"] = min(others, key=lambda o: math.hypot(o.x - e.x, o.y - e.y)).id
                    st["turn"] = p["ELE_TURN"]
                    return
                st["mode"] = "return"
                self.events.append((round(self.t, 2), "ele_gave_up", e.id))
                return
            if st.get("turn", 0) > 0:
                st["turn"] -= dt
                return
            d = math.hypot(tgt.x - e.x, tgt.y - e.y)
            if d <= p["ELE_HIT_R"]:
                if e.reload <= 0:
                    self._damage(tgt, p["ELE_DMG"], e)
                    e.reload = p["ELE_RELOAD"]
            else:
                self._walk(e, tgt.x, tgt.y, p["ELE_SPEED"] * dt)
        elif st["mode"] == "return":
            hx, hy = st["home"]
            if math.hypot(hx - e.x, hy - e.y) < 0.3 or not self._walk(e, hx, hy, p["ELE_SPEED"] * 0.8 * dt):
                st["mode"] = "idle"

    def _step(self):
        dt = self.p["DT"]
        self._apply_orders()
        for e in list(self.ents.values()):
            if not e.alive:
                continue
            if e.reload > 0:
                e.reload -= dt
            if e.kind == "villager":
                self._step_villager(e, dt)
            elif e.kind == "gazelle":
                self._step_gazelle(e, dt)
            elif e.kind == "elephant":
                self._step_elephant(e, dt)
        for e in self.ents.values():
            if e.alive and e.kind != "villager" and self.visible(e.x, e.y):
                self.seen[e.id] = (e.x, e.y, self.t)
        self.t += dt

    # ---------------------------------------------------------------- run
    def run(self, tasks, max_t=240.0, tick_every=0.5):
        n_tick = max(1, int(round(tick_every / self.p["DT"])))
        i = 0
        while self.t < max_t:
            self._step()
            if i % n_tick == 0:
                for task in tasks:
                    if not (task.done or task.failed):
                        task.tick(self, self)
            for task in tasks:
                if not (task.done or task.failed):
                    task.micro(self, self)
            i += 1
            if all(task.done or task.failed for task in tasks):
                break
        return self.t
