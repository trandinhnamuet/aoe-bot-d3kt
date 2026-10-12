"""WorldModel: what the brain knows (KIEN_TRUC_AI.md 3). Built from gamestate.Snapshot every tick,
plus memory of everything seen (bushes, animals, herds, lions, enemy villagers / buildings / working
areas) and the zones tasks reserve. It is also the World / Orders the tasks run against (the same
pointer-fresh reads as brain.adapter.GameWorld)."""
import math

import gamestate as gs
from brain import geom
from brain.adapter import GameWorld, kind_of


class Herd:
    """A cluster of gazelles seen within 8 tiles of each other (the plan decides what to do with it)."""
    __slots__ = ("key", "ids", "x", "y", "seen_t")

    def __init__(self, key, x, y, t):
        self.key, self.ids, self.x, self.y, self.seen_t = key, set(), x, y, t


class WorldModel(GameWorld):
    ANIMAL_MEMORY_S = 240.0
    LION_MEMORY_S = 180.0
    ENEMY_VIL_MEMORY_S = 90.0

    def __init__(self, reader, game, me):
        super().__init__(self, game)        # GameWorld reads through self.b == self
        self.r = reader
        self.me = me
        self.s = None
        self.pm = None
        self.tc_anchor = None
        self.t = 0.0
        self._by_id = {}
        self._gaia_by_id = {}
        self.anim_cache = {}                # animal id -> last snapshot object (pointer) for tracking in the fog
        self.animal_pos = {}                # animal id -> (x, y, type, t) last seen
        self.bushes_seen = {}               # bush id -> (x, y)
        self.herds = {}                     # key -> Herd
        self.lions = {}                     # id -> (x, y, t)
        self.enemy_vils_seen = {}           # id -> (x, y, t)
        self.enemy_sites = {}               # (x//8, y//8) -> dict(x, y, seen, eco, visit, bld)
        self.enemy_base = None
        self.zones = {}                     # key -> (x, y, r, until, owner ids)
        self.log = []

    # ---------------------------------------------------------------- per tick
    @property
    def now(self):
        return self.t

    def update(self, snap, pm, tc_anchor):
        from d3kt import game_s
        self.s, self.pm = snap, pm
        self.t = game_s(snap)
        self._by_id = {o.id: o for o in snap.mine}
        self._gaia_by_id = {o.id: o for o in snap.gaia}
        if tc_anchor:
            self.tc_anchor = tc_anchor
        self._learn()

    def _learn(self):
        s, t = self.s, self.t
        for b in s.gaia:
            if b.type == gs.FORAGE and b.amount > 0:
                self.bushes_seen[b.id] = (b.x, b.y)
        for a in s.gaia:
            if a.kind != gs.KIND_COMBAT or a.cls == gs.CLS_DEAD:
                continue
            k = kind_of(a)
            if k == "lion":
                if a.hp > 0 and s.visible(a.x, a.y):
                    self.lions[a.id] = (a.x, a.y, t)
                elif a.hp <= 0:
                    self.lions.pop(a.id, None)
                continue
            if k not in ("gazelle", "elephant") or not s.visible(a.x, a.y):
                continue
            if a.hp <= 0:
                self.animal_pos.pop(a.id, None)
                continue
            self.animal_pos[a.id] = (a.x, a.y, a.type, t)
            self.anim_cache[a.id] = a
            if k == "gazelle":
                herd = None
                for h in self.herds.values():
                    if a.id in h.ids or math.hypot(h.x - a.x, h.y - a.y) < 8:
                        herd = h
                        break
                if herd is None:
                    key = (int(a.x) // 8, int(a.y) // 8)
                    herd = self.herds.setdefault(key, Herd(key, a.x, a.y, t))
                herd.ids.add(a.id)
                herd.x, herd.y, herd.seen_t = 0.8 * herd.x + 0.2 * a.x, 0.8 * herd.y + 0.2 * a.y, t
        for lid in [k for k, v in self.lions.items() if t - v[2] > self.LION_MEMORY_S]:
            del self.lions[lid]
        for aid in [k for k, v in self.animal_pos.items() if t - v[3] > self.ANIMAL_MEMORY_S]:
            del self.animal_pos[aid]
        for e in s.enemy:
            if e.cls == gs.CLS_VILLAGER and e.hp > 0:
                self.enemy_vils_seen[e.id] = (e.x, e.y, t)
                key = (int(e.x) // 8, int(e.y) // 8)
                st = self.enemy_sites.setdefault(key, {"x": e.x, "y": e.y, "seen": t, "eco": 0.0, "visit": 0.0, "bld": 0})
                st["seen"], st["eco"] = t, t
        for eid in [k for k, v in self.enemy_vils_seen.items() if t - v[2] > self.ENEMY_VIL_MEMORY_S]:
            del self.enemy_vils_seen[eid]
        for b in s.enemy_buildings_seen:
            key = (int(b.x) // 8, int(b.y) // 8)
            st = self.enemy_sites.setdefault(key, {"x": b.x, "y": b.y, "seen": t, "eco": 0.0, "visit": 0.0, "bld": 0})
            st["seen"], st["bld"] = max(st["seen"], t), 1
        if s.enemy_buildings_seen and self.enemy_base is None and self.tc_anchor:
            b = min(s.enemy_buildings_seen, key=lambda o: o.dist(*self.tc_anchor))
            self.enemy_base = (b.x, b.y)
            self.log.append((t, "enemy base found at (%.0f,%.0f)" % self.enemy_base))
        for key in [k for k, z in self.zones.items() if z[3] < t]:
            del self.zones[key]

    # ---------------------------------------------------------------- queries
    def tc_obj(self):
        tcs = [o for o in self.s.mine if o.type == gs.TOWN_CENTER and o.state == 2]
        return tcs[0] if tcs else None

    def villagers(self):
        return sorted(self.s.villagers, key=lambda v: v.id)         # birth order

    def berry_clusters(self, live_only=True):
        """[(cx, cy, [(id, x, y)])] bushes within 5 tiles of each other."""
        if live_only:
            items = [(b.id, b.x, b.y) for b in self.s.gaia if b.type == gs.FORAGE and b.amount > 0]
        else:
            items = [(i, x, y) for i, (x, y) in self.bushes_seen.items()]
        clusters = []
        for it in items:
            for c in clusters:
                if any(math.hypot(it[1] - o[1], it[2] - o[2]) < 5 for o in c[2]):
                    c[2].append(it)
                    n = len(c[2])
                    c[0] = sum(o[1] for o in c[2]) / n
                    c[1] = sum(o[2] for o in c[2]) / n
                    break
            else:
                clusters.append([it[1], it[2], [it]])
        return clusters

    def elephants_near(self, rng, exclude=()):
        """Live elephants seen (now or remembered) within rng of the TC: [(id, x, y)]."""
        if not self.tc_anchor:
            return []
        out = []
        for aid, (x, y, ty, _) in self.animal_pos.items():
            if ty == gs.ELEPHANT and aid not in exclude and math.hypot(x - self.tc_anchor[0], y - self.tc_anchor[1]) <= rng:
                tr = self.track(aid)
                if tr is None:
                    continue
                out.append((aid, tr.x, tr.y))
        return out

    def herd_live(self, h):
        return [u for u in (self.animal(gid) for gid in list(h.ids)) if u is not None]

    def carcasses(self, x, y, r):
        return [o for o in self.s.gaia if o.amount > 0 and o.dist(x, y) <= r and (
            (o.cls == gs.CLS_DEAD and o.type in gs.MEAT) or (o.type == gs.GAZELLE and o.hp <= 0))]

    def lion_near(self, x, y, r):
        return any(math.hypot(lx - x, ly - y) < r for (lx, ly, _) in self.lions.values())

    def against_obstacle(self, x, y):
        """A gazelle standing against a wall / the forest / the map edge (left alone, the user's rule)."""
        blocked = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                      if (dx or dy) and not self.passable(int(x) + dx, int(y) + dy))
        return blocked >= 3 or min(x, y, self.W - 1 - x, self.H - 1 - y) < 3.0

    # ---------------------------------------------------------------- reservations
    def reserve(self, key, x, y, r, seconds, owners=()):
        """A zone other tasks keep out of (a herd being pushed, a lured elephant's path)."""
        self.zones[key] = (x, y, r, self.t + seconds, set(owners))

    def release(self, key):
        self.zones.pop(key, None)

    def zone_blocking(self, vid, x, y):
        """The zone that (x, y) lies in and `vid` may not enter, or None."""
        for key, (zx, zy, r, _, owners) in self.zones.items():
            if vid not in owners and math.hypot(zx - x, zy - y) < r:
                return key
        return None

    def detour(self, vid, x0, y0, x1, y1):
        """Walking from (x0,y0) to (x1,y1) through a zone `vid` may not enter: a waypoint round it."""
        for key, (zx, zy, r, _, owners) in self.zones.items():
            if vid in owners:
                continue
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((zx - x0) * dx + (zy - y0) * dy) / L2))
            px, py = x0 + k * dx, y0 + k * dy
            if math.hypot(px - zx, py - zy) < r:
                ax, ay = geom.unit(px - zx, py - zy) if (px, py) != (zx, zy) else geom.unit(-dy, dx)
                return zx + ax * (r + 1.0), zy + ay * (r + 1.0)
        return None
