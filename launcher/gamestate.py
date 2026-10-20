"""Per-tick snapshot of the match as seen by one player (fog of war respected)."""
import math
import struct

import aoemem as am

# master "kind" byte
KIND_STATIC = 10
KIND_ANIMATED = 20
KIND_DOPPEL = 30
KIND_MOVING = 40
KIND_ACTION = 50
KIND_COMBAT = 70
KIND_TREE = 90
KIND_BUILDING = 80

# unit classes (master +0x14)
CLS_VILLAGER = 4
CLS_DEAD = 11            # dead units: a killed animal turns into a NEW object of this class (the meat)
CLS_TREE = 15

# unit / building ids
VILLAGER = 83
TOWN_CENTER = 109
HOUSE = 70
GRANARY = 68
STORAGE_PIT = 103
BARRACKS = 12
MARKET = 84
STABLE = 101
GOVERNMENT_CENTER = 82    # "nhà BC": Nobility (+15 % hp for horse units)
TEMPLE = 104
SIEGE_WORKSHOP = 49
ARCHERY_RANGE = 87
PRIEST = 125
STONE_THROWER = 35
TECH_IRON_AGE = 103
FARM = 50
DOCK = 45
SCOUT = 299
CAVALRY = 37
CHARIOT = 40             # "Soldier-Chariot1": stable, needs the Wheel (28): food + wood, no gold
CAMEL = 338
CLUBMAN = 73
AXEMAN = 74
ACADEMY = 0              # "BY" (empires.dat: Academy = 0; Phalanx research location 0)
HOPLITE = 93             # Soldier-Phal1 (94 Phalanx, 291 Centurion): 60 food 40 gold
BOWMAN = 4
IMPROVED_BOWMAN = 5      # "cung A" (needs Improved Bow 56): 40 food 20 gold
COMPOSITE_BOWMAN = 6     # "cung C" (Iron, Composite Bow 57)
HORSE_ARCHER = 39        # "horse" = Soldier-Cavalry3_Arch (archery range, Iron): 50 food 70 gold
HEAVY_HORSE_ARCHER = 281 # "horse thần" = Soldier-Cavalry4 (after Advanced Horse Archer 38)
SCYTHE_CHARIOT = 339     # "đạp đôi" = Soldier-Hvy_Chariot (the chariot after Heavy Chariots 126)
PHALANX = 94             # "Y đẹp" (after Phalanx 73)
CENTURION = 291          # "Y thần" (after Centurion 79)
CATAPULT = 36            # "K" = Soldier-Catapult2 (after Heavy Catapult 54 - the research that upgrades the stone thrower)
HEAVY_CATAPULT = 280     # "K thần" = Soldier-Catapult3 (after Massive Catapult 36)
CHARIOT_ARCHER = 41      # "cung R" = "Soldier-Chariot2", archery range, needs the Wheel (28). (It was 40 - the
                         # stable chariot - so every chariot archer order was refused: recordings 13/10)

TECH_TOOL_AGE = 101
TECH_BRONZE_AGE = 102

FORAGE = 59
GAZELLE = 65
ELEPHANT = 48
DEAD_GAZELLE = 262
DEAD_ELEPHANT = 335
DEAD_LION = 369
MEAT = (DEAD_GAZELLE, DEAD_ELEPHANT)
GOLD_MINE = 66
STONE_MINE = 102

# resource attribute indices
FOOD, WOOD, STONE, GOLD, HEADROOM, AGE = 0, 1, 2, 3, 4, 6

WATER_TERRAINS = {1, 4, 22, 23}   # water, shallows, deep water variants
FOREST_TERRAINS = {10, 13, 19, 20}

O_STATE = 0x48      # byte: 0 foundation, 2 alive, >=3 dying/dead
O_CARRY = 0x44      # float carried amount / resource left on gaia objects
O_CARRY_TYPE = 0x4C  # short
O_ACTIONS = 0x184   # RGE_Action_List*
O_PRODUCING = 0x394  # building: non-zero while training/researching
M_RADIUS = 0x30     # float x-radius, +0x34 y-radius
M_HP = 0x26         # short max hp

PLAYER_VISMAP = 0x38


class Obj:
    __slots__ = ("ptr", "id", "type", "cls", "kind", "name", "owner", "hp", "maxhp", "x", "y",
                 "state", "amount", "carry_type", "rx", "ry", "master")

    def dist(self, x, y):
        return math.hypot(self.x - x, self.y - y)

    def __repr__(self):
        return "<%s#%d p%d (%.1f,%.1f)>" % (self.name, self.id, self.owner, self.x, self.y)


class MasterInfo:
    __slots__ = ("kind", "name", "type", "cls", "rx", "ry", "maxhp")


class Reader:
    """Reads the world for player `me`. Keeps caches between ticks."""

    def __init__(self, game, me):
        self.g = game
        self.m = game.m
        self.me = me
        self._masters = {}
        self._owners = {}
        self.W = self.H = 0
        self.terrain = b""
        self.elev = b""
        self.shape = b""
        self._static_cache = {}   # ptr -> Obj (gaia static resources)
        self._tick = 0

    # ------------------------------------------------------------ static map data
    def load_map(self):
        w = self.g.world()
        mp = self.m.u32(w + 0x28)
        self.W = self.m.u32(mp + 8)
        self.H = self.m.u32(mp + 0xC)
        tiles = self.m.u32(mp + 4)
        raw = self.m.read(tiles, self.W * self.H * 24) or b""
        # tile byte 5 = bits 0-4 terrain id + bits 5-7 ELEVATION (the whole byte was taken for the terrain id: on
        # raised ground - 60 % of a Hill Country map - water / forest were never recognised); byte 4 = slope shape
        # (0 = flat)
        n = self.W * self.H
        self.terrain = bytes(raw[i * 24 + 5] & 31 for i in range(n)) if raw else b""
        self.elev = bytes(raw[i * 24 + 5] >> 5 for i in range(n)) if raw else b""
        self.shape = bytes(raw[i * 24 + 4] for i in range(n)) if raw else b""

    def elev_at(self, x, y):
        if not (0 <= x < self.W and 0 <= y < self.H) or not self.elev:
            return 0
        return self.elev[int(y) * self.W + int(x)]

    def shape_at(self, x, y):
        if not (0 <= x < self.W and 0 <= y < self.H) or not self.shape:
            return 0
        return self.shape[int(y) * self.W + int(x)]

    def terrain_at(self, x, y):
        if not (0 <= x < self.W and 0 <= y < self.H) or not self.terrain:
            return 255
        return self.terrain[int(y) * self.W + int(x)]

    def vismap(self):
        p = self.g.player_ptr(self.me)
        vm = self.m.u32(p + PLAYER_VISMAP)
        data = self.m.u32(vm + 0x10)
        return self.m.read(data, self.W * self.H) or b"\xff" * (self.W * self.H)

    # ------------------------------------------------------------ objects
    def _master(self, mptr):
        mi = self._masters.get(mptr)
        if mi is None:
            raw = self.m.read(mptr, 0x38)
            if not raw:
                return None
            mi = MasterInfo()
            mi.kind = raw[4]
            mi.name = self.m.cstr(struct.unpack_from("<I", raw, 8)[0], 32) or "?"
            mi.type = struct.unpack_from("<h", raw, 0x10)[0]
            mi.cls = struct.unpack_from("<h", raw, 0x14)[0]
            mi.maxhp = struct.unpack_from("<h", raw, M_HP)[0]
            mi.rx, mi.ry = struct.unpack_from("<ff", raw, M_RADIUS)
            self._masters[mptr] = mi
        return mi

    def _owner(self, pptr):
        v = self._owners.get(pptr)
        if v is None:
            v = self.m.u16(pptr + am.P_ID)
            v = -1 if v is None else v
            self._owners[pptr] = v
        return v

    def _make(self, ptr, raw):
        mptr, optr = struct.unpack_from("<II", raw, am.O_MASTER)
        mi = self._master(mptr)
        if mi is None:
            return None
        o = Obj()
        o.ptr = ptr
        o.id = struct.unpack_from("<i", raw, am.O_ID)[0]
        o.master = mptr
        o.kind, o.name, o.type, o.cls = mi.kind, mi.name, mi.type, mi.cls
        o.rx, o.ry, o.maxhp = mi.rx, mi.ry, mi.maxhp
        o.owner = self._owner(optr) if optr else -1
        o.hp, = struct.unpack_from("<f", raw, am.O_HP)
        o.x, o.y = struct.unpack_from("<ff", raw, am.O_X)
        o.amount, = struct.unpack_from("<f", raw, O_CARRY)
        o.state = raw[O_STATE]
        o.carry_type = struct.unpack_from("<H", raw, O_CARRY_TYPE)[0]
        return o

    def objects(self):
        """All objects. Static gaia resources are re-read only every few ticks."""
        self._tick += 1
        phase = self._tick % 8                   # each static object is re-read every 8th tick, 1/8 per tick
        w = self.g.world()
        tbl = self.m.u32(w + am.W_OBJ_TABLE)
        n = self.m.u32(w + am.W_OBJ_TABLE_SIZE) or 0
        raw = self.m.read(tbl, 4 * n)
        if not raw:
            return []
        ptrs = struct.unpack("<%dI" % n, raw)
        out = []
        live = set()
        for ptr in ptrs:
            if not ptr:
                continue
            live.add(ptr)
            cached = self._static_cache.get(ptr)
            if cached is not None and (ptr >> 4) % 8 != phase:
                out.append(cached)
                continue
            r = self.m.read(ptr, 0x50)
            if not r:
                continue
            o = self._make(ptr, r)
            if o is None:
                continue
            if o.owner == 0 and o.kind in (KIND_STATIC, KIND_DOPPEL, KIND_TREE):
                self._static_cache[ptr] = o
            elif cached is not None:
                # the static object is gone and the game reused its memory for a new unit (often a
                # villager): without this the cache hid that unit 7 ticks out of 8, for minutes
                del self._static_cache[ptr]
            out.append(o)
        if len(live) != getattr(self, "_n_live", -1) or phase == 0:
            self._n_live = len(live)
            for p in list(self._static_cache):
                if p not in live:
                    del self._static_cache[p]
        return out

    def action(self, o):
        """(action_type, target_ptr, state) of the unit's current action, or None when it has none.
        state: 3 = finished, 4 = moving to target, 7 = working, 0x0B = walking."""
        al = self.m.u32(o.ptr + O_ACTIONS)
        if not al:
            return None
        node = self.m.u32(al + 8)
        if not node:
            return None
        a = self.m.u32(node)
        raw = self.m.read(a, 0x18) if a else None
        if not raw:
            return None
        return struct.unpack_from("<H", raw, 4)[0], struct.unpack_from("<I", raw, 0x10)[0], raw[0x0C]

    def busy(self, o):
        a = self.action(o)
        return a is not None and a[2] > 3

    def producing(self, building):
        """Training or researching: buildings keep the make/research action in their action list."""
        al = self.m.u32(building.ptr + O_ACTIONS)
        return bool(al) and bool(self.m.u32(al + 8))

    def owner_of_ptr(self, ptr):
        optr = self.m.u32(ptr + am.O_OWNER)
        return self._owner(optr) if optr else -1


class Snapshot:
    """What one player knows this tick."""

    def __init__(self, reader, enemies):
        r = reader
        self.r = r
        self.me = r.me
        self.time = r.m.u32(r.g.world() + 4) or 0
        self.res = r.g.resources(r.me, 8)
        self.vis = r.vismap()
        W = r.W
        allobjs = r.objects()
        self.mine = [o for o in allobjs if o.owner == r.me and o.state <= 2]
        self.enemy = []
        self.gaia = []
        self.enemy_buildings_seen = []
        # every enemy object whatever its visibility: what the achievements screen tells a player
        # (villagers, army, buildings per enemy) - the doctrine sizes the army from this
        self.enemy_all = [o for o in allobjs if o.owner in enemies and o.state <= 2]
        # allied town centres (team games share the map with the ally: its berries, herds and elephants
        # are seen at once - ms8: the Palmyran bot built its first granary in its ally's town, 110 tiles away)
        self.ally_tcs = [(o.x, o.y) for o in allobjs if o.owner not in enemies and o.owner not in (0, r.me)
                         and o.type == TOWN_CENTER and o.state <= 2]
        self.ally_ids = sorted({o.owner for o in allobjs if o.owner not in enemies and o.owner not in (0, r.me)
                                and o.owner > 0})
        for o in allobjs:
            if o.owner == r.me:
                continue
            if o.x != o.x or o.y != o.y:                 # NaN position (an object being removed): wall5 tick error
                continue
            xi, yi = int(o.x), int(o.y)
            if not (0 <= xi < W and 0 <= yi < r.H):
                continue
            v = self.vis[yi * W + xi]
            if v == 255:
                continue                       # never explored: unknown to us
            if o.owner == 0:
                if o.kind in (KIND_STATIC, KIND_DOPPEL, KIND_TREE) or (v > 0 and o.kind == KIND_COMBAT) or                         (o.cls == CLS_DEAD and o.amount > 0):
                    self.gaia.append(o)
            elif o.owner in enemies:
                if o.kind == KIND_BUILDING:
                    self.enemy_buildings_seen.append(o)   # buildings stay known once explored
                    if v > 0:
                        self.enemy.append(o)
                elif v > 0:
                    self.enemy.append(o)       # mobile units only while currently visible

    def visible(self, x, y):
        xi, yi = int(x), int(y)
        if not (0 <= xi < self.r.W and 0 <= yi < self.r.H):
            return False
        v = self.vis[yi * self.r.W + xi]
        return v != 255 and v > 0

    def explored(self, x, y):
        xi, yi = int(x), int(y)
        if not (0 <= xi < self.r.W and 0 <= yi < self.r.H):
            return False
        return self.vis[yi * self.r.W + xi] != 255

    def of_type(self, t, include_foundations=True):
        return [o for o in self.mine if o.type == t and (include_foundations or o.state == 2)]

    @property
    def villagers(self):
        return [o for o in self.mine if o.cls == CLS_VILLAGER and o.kind == KIND_COMBAT]
