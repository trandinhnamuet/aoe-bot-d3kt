"""D3KT bot brain ("Đời 3 không thành"), v2 — the user's detailed play style.

Stone Age
  * Villagers train non-stop; a house whenever 2 pop slots remain. Houses stand away from the TC
    (the ring around it is kept for farms) and line up along the wall plan ("bo nhà").
  * The first house is built by 2 villagers while the 3rd searches; every later house by ONE villager.
    The early villagers search in growing circles around the TC (the 2 builders join once done). The first
    bush seen pulls every early villager there; the granary is placed only once >= 5 bushes of the
    patch are known, at the spot with the shortest walk for every bush and no blocked bush.
  * The building after the first granary is always the storage pit at the wood line, 6 on wood.
  * V7 and V9 scout until 5 food sources are known: a berry patch = 1, a gazelle herd = 1,
    2 elephants = 1. V8 wood, V10 builds a house then wood.
  * Hunting (only after the wood-line pit stands): elephants first - one villager lures it to the TC,
    it is killed only within 3 TC foundations (9 tiles) of the TC; the first gazelle near the TC
    (push < ~60 s, not standing against trees/walls) is pushed home and killed there; other herds
    are killed where they stand, then a pit is placed for the carcasses. Up to 3 hunting sites at
    once, 4-7 villagers each (by how many are near), the rest on other food.
  * Scouting villagers keep out of lions' attack range (7 tiles) and walk around them; one that a
    lion attacks fights back and scouts on if it survives.
  * The artifact cart scouts around the town; after 6 minutes it runs along the map edges.
  * 25 villagers -> Tool Age.
Tool Age: market + stable (placed to help the wall), farms one house-width away from the
  granary/TC with a short, unblocked walk, Bronze Age as soon as there is food.
Bronze: right after clicking, one scout to find enemy houses and villagers, then Tool Working and
  Leather Armor (cavalry); cavalry + camels after Bronze. Targets: villagers first, army second,
  buildings only when they block the way. Hit and run when hurt.
D3KT rules (until the enemy breaks one): no towers/walls/tower tech, no attack before clicking
  Bronze, at most one military unit before reaching Bronze, villagers never hit enemy villagers.
  Enemy soldiers attacking us may always be fought back; a lone enemy scout is attacked by every
  villager within 5 tiles of where it struck, until it is more than 4 tiles from that spot.
"""
import collections
import math
import os
import threading
import time

import aoemem
import gamestate as gs
from brain import knowledge as K
from brain import tactics
from brain.adapter import GameWorld
from brain.tasks.herd import HerdPush
from brain.tasks.herd_rl import HerdPushRL


def use_rl_push():
    """The learned herd push (rl/policies/herd_push.json) drives the pushers only with AOESOLO_HERD_RL=1
    (the training was dropped on 2026-10-12: the hand-coded push stays)."""
    return os.environ.get("AOESOLO_HERD_RL", "0") == "1" and HerdPushRL.policy() is not None
from brain.tasks.lure import Lure as LureTask
from aoemem import O_HP, O_X
import demo_dump
import pathing
import walling
from placement import Grid

FOOD_ITEMS_WANTED = 5
FOOD_ITEM_RANGE = 40     # food sources further than this do not count as "found"
STONE_VILLAGERS = 25     # the user's rule; 36 recorded real players: 23-27, median 25
HUNT_FROM_VILLAGER = 9   # the user: only from the 9th villager on are elephants lured / gazelles pushed
MAX_VILLAGERS = 60      # the user: in Bronze villagers keep coming for the long game (farms feed them)
ATTACK_GROUP = 2         # the user: two fighters go out at once; every new one joins them (non-stop pressure)
MAX_STABLES = 6          # as many stables as the economy keeps busy: one per ~12 villagers
WALL_FAR = 46            # the wall cut separates the town from the ring this far out (plan B, the user 15/10)
WALL_WIDE_R = 22         # the wide wall: nothing this close to the TC is cut (the enclosure is at least that disc)
WALL_WIDE_MAX = 24       # the wide wall is taken when it needs at most this many houses and at most 1.6 x the narrow one
FLEE_R = 10.0            # villagers this close to an enemy soldier run for the TC before it reaches them
FARM_RESET_S = 25.0      # the farm reset (Stop on farms + a villager) at most this often
FARM_RESET_BELOW = 12.0  # ... once some farm's field (unit+0x44, at most 15 in this build) is below this
REVISIT = 90.0           # a known enemy working area is raided again after this many seconds
GOLD_PER_STABLE = 2      # Bronze gold miners: 2 + 2 per stable. Farms bring food slower than mines
                         # bring gold and the TC eats food too: 2 + 4 per stable piled up 1000-1700 gold
CL_WAIT = 4.5            # the hunters' group waits this far from the target gazelle (out of the 2.1-2.9 hop range)
CL_ARC = 2.9             # ... then steps onto an arc this far from it: within spear range (3.0), all at one distance
SPEAR_REACH = 3.05        # a villager spears a gazelle from this far without walking closer
KITE_R = 3.5             # enemy melee this close to any archer of the group: the whole group steps back
KITE_STEP = 3.0          # ... this far
PULSE_MOVE = 1.0         # ... for this long (game s), then it shoots for one reload + 0.3 s
PULSE_STEP = 1.5         # the archers' side step during the reload (tiles)
CL_MAX = 6               # hunters on the arc at once (the rest wait behind the group)
CL_GAP = 0.6             # tiles between two hunters of the group (the user: within 1.5 of each other)
FOOD_PER_VILLAGER = 70   # a food site keeps one villager per 70 food left at most (the user)
AGING_WOOD_MAX = 7       # choppers before the Bronze click (players: 5-9 at the Tool click)
WOOD_FLOOR = 4           # villagers always on wood (the user: houses and the wall always need some)
FARM_RING = 6.5          # no houses closer than this to the TC centre (farms go there)
FARM_GAP = 2             # one house foundation between a farm and its granary / TC
PUSH_RANGE = 16          # herds closer than this are pushed home (the user: further = a pit, the push is too slow)
MAX_PUSHES = 2           # gazelles being pushed at the same time
PUSH_CIRCLE = 3.6        # the pusher circles round a gazelle this far away (it flees below ~2.1-2.9)
PUSH_IN = 1.5            # ... and steps in this close behind it to make it hop towards the TC
PUSH_TIMEOUT = 150.0     # a push not home by then is given up
GUARD_FROM_VILLAGERS = 12    # a second pusher from 12 villagers (sim 12-16 tiles: one pusher 72 %, two 95 %)
GUARD_DRIFT = 1.0        # sideways drift (tiles) off the start->TC line before the guard blocks it
GUARD_SIDE = 2.6         # the guard stands this far to the side of the gazelle
HERD_SPREAD = 7.0        # gazelles further than this from the herd's middle are left out of the push
LURE_CIRCLE = 4.5        # the lurer runs round the TC this far from its centre while the elephant is killed
PUSH_DEBUG = False       # log the pusher's geometry every 2 s
LURE_DEBUG = False       # log the lurer's distance / hp every 0.4 s
KILL_NEAR_TC = 9.0       # a lured elephant is killed only within 3 TC foundations (3 x 3 tiles)
HERD_KILL_NEAR = 3.0     # a pushed herd is killed only right next to the TC (players: 2.5-3.4 tiles from its centre)
LURE_RANGE = 60          # elephants this close to the TC are lured home (the user: ALWAYS lured)
FAR_ELEPHANT = 60        # (the kill-where-it-stands path is off: nothing between LURE_RANGE and this)
HERD_RANGE = 48          # herds further than this are not hunted (the user's hunters: up to 46 tiles out)
HERD_NEAR = 25           # ... and further than this only when there is no other food
HERD_POOR = 75           # range when no hunting site exists at all
POOR_VILLAGERS = 20      # Tool Age at this many villagers when berries are the only food
BERRY_NEAR, BERRY_POOR = 55, 60   # granary range for a berry patch (players' 2nd granary: median 34, p75 52 tiles)
HUNT_SITE_MIN, HUNT_SITE_MAX = 4, 7      # villagers per hunting site, by how many are near it
HUNT_SITE_FAR_MAX = 10   # a far herd with its own pit is a group hunt (the user: 7-14 hunters)
MAX_HUNT_SITES = 3
ELEPHANT_EATERS = 5
WOOD_HARD_CAP = 8
EARLY_WOOD = 4           # before the first pit: this many on wood, then hunting at the TC        # before Bronze no more than this on wood (recorded players: 6-7)
# the lurer keeps running while a CHASING elephant is closer than KEEP_MIN; it waits only once the
# elephant stopped chasing and is further than KEEP_MAX. Measured in 22 lures: the elephant runs as
# fast as a villager, hits from ~2 tiles, gives up beyond ~4.4, and a stopped villager needs 2-3 game s
# to get going again (lockstep) -> stopping in front of a chasing elephant killed the lurer
KEEP_MIN, KEEP_MAX = 4.3, 3.0
LURE_TIMEOUT = 150.0     # a lure that has not brought the elephant home by then is given up
BERRY_SHARE_TILES = 2.5   # a bush already worked by one costs this many tiles of extra walk (2-3 may share)
BERRY_MAX_PER_BUSH = 3
WAIT_LIMIT = 30.0        # seconds villagers wait at far food for its granary / pit before just gathering      # villagers per elephant (killing at the TC, then eating)
EARLY_DEFENDERS = 5      # at most this many villagers fight one lone early unit
SCOUT_CALL_R = 8         # a lone Stone / Tool-age enemy unit: villagers this close to it join in (the user, 15/10)
SCOUT_TRIGGER_R = 3      # ... once it comes this close to one of our villagers
SCOUT_CHASE_R = 3        # ... until it is further than this from every worker: back to work
LION_SAFE = 7.0          # scouting villagers keep this far from lions (their attack trigger range)
GAZELLE_SAFE = 5.0       # ... and this far from gazelles, so the herd stays together for the hunt       # hunting sites at once (plus the berries: 2-4 food areas)
ARTIFACT_EDGE_AFTER = 360.0

TUNABLE = ("STONE_VILLAGERS", "POOR_VILLAGERS", "FARM_RING", "PUSH_RANGE", "MAX_PUSHES", "KILL_NEAR_TC",
           "LURE_RANGE", "HERD_RANGE", "HERD_NEAR", "HERD_POOR", "BERRY_NEAR", "BERRY_POOR", "HUNT_SITE_MIN",
           "HUNT_SITE_MAX", "MAX_HUNT_SITES", "ELEPHANT_EATERS", "WAIT_LIMIT", "KEEP_MIN", "KEEP_MAX",
           "LURE_TIMEOUT", "LION_SAFE", "GAZELLE_SAFE", "FOOD_ITEM_RANGE", "FOOD_ITEMS_WANTED", "ATTACK_GROUP",
           "WOOD_HARD_CAP", "EARLY_WOOD", "PUSH_CIRCLE", "PUSH_IN", "PUSH_TIMEOUT", "GUARD_FROM_VILLAGERS",
           "GUARD_DRIFT", "GUARD_SIDE")


def load_params(path=None):
    """Override the tunable constants above from a JSON file (the tuner's candidate). Path from the
    argument or the D3KT_PARAMS environment variable; unknown keys are ignored."""
    import json
    import os
    path = path or os.environ.get("D3KT_PARAMS")
    if not path:                                     # the tuner's best set, next to the exe or this file
        import sys
        for d in (os.path.dirname(sys.executable), os.path.dirname(os.path.abspath(__file__))):
            if os.path.exists(os.path.join(d, "params.json")):
                path = os.path.join(d, "params.json")
                break
    if not path or not os.path.exists(path):
        return {}
    vals = json.load(open(path, encoding="utf-8"))
    used = {}
    for k, v in vals.items():
        if k in TUNABLE:
            globals()[k] = type(globals()[k])(v) if not isinstance(globals()[k], tuple) else v
            used[k] = globals()[k]
    return used


def current_params():
    return {k: globals()[k] for k in TUNABLE}


TECH_TOOL_WORKING = 46
TECH_LEATHER_CAV = 42
TECH_WOODWORKING = 107
TECH_WHEEL = 28

BUILD_COST = {gs.HOUSE: 30, gs.GRANARY: 120, gs.STORAGE_PIT: 120, gs.MARKET: 150, gs.STABLE: 150, gs.TEMPLE: 200,
              gs.FARM: 75, gs.BARRACKS: 125, gs.ARCHERY_RANGE: 150, gs.SIEGE_WORKSHOP: 200, gs.ACADEMY: 150,
              gs.GOVERNMENT_CENTER: 175}
SIZES = {gs.HOUSE: 2, gs.FARM: 3, gs.GRANARY: 3, gs.STORAGE_PIT: 3, gs.MARKET: 3, gs.STABLE: 3,
         gs.BARRACKS: 3, gs.TOWN_CENTER: 3, gs.TEMPLE: 3, gs.ARCHERY_RANGE: 3, gs.SIEGE_WORKSHOP: 3, gs.ACADEMY: 3,
         gs.GOVERNMENT_CENTER: 3}
# building -> buildings that must stand first (the user: BB opens BL and BA, BL opens BY, BA opens BK, BC opens
# BN, BG opens BM)
PREREQ = {gs.STABLE: (gs.BARRACKS,), gs.ARCHERY_RANGE: (gs.BARRACKS,), gs.ACADEMY: (gs.STABLE,),
          gs.SIEGE_WORKSHOP: (gs.ARCHERY_RANGE,), gs.TOWN_CENTER: (gs.GOVERNMENT_CENTER,), gs.MARKET: (gs.GRANARY,)}
MILITARY_BUILDINGS = (gs.STABLE, gs.ACADEMY, gs.ARCHERY_RANGE, gs.SIEGE_WORKSHOP, gs.BARRACKS)


def game_s(snap):
    return snap.time / 1000.0


BRONZE_WORDS = ("cavalry", "cataphract", "camel", "chariot", "elephant", "hoplite", "phalanx", "centurion", "phal", "archer2", "archer3",
                "horse archer", "swordsman", "legion", "improved bowman", "composite", "priest", "stone thrower",
                "catapult", "ballista", "helepolis")


def bronze_unit(e):
    """A Bronze (or later) unit: villagers never fight it, they run (the user)."""
    n = (e.name or "").lower()
    return any(w in n for w in BRONZE_WORDS) or e.type in (gs.CAVALRY, gs.CAMEL, gs.CHARIOT, gs.CHARIOT_ARCHER, gs.HOPLITE)


def unit(vx, vy):
    n = math.hypot(vx, vy) or 1.0
    return vx / n, vy / n


_CUT_POOL = None


def _cut_pool():
    """One process pool for every bot's wall cuts (2 workers: the cuts of 4-7 bots queue up, the ticks never wait)."""
    global _CUT_POOL
    if _CUT_POOL is None:
        import concurrent.futures
        _CUT_POOL = concurrent.futures.ProcessPoolExecutor(max_workers=int(os.environ.get("AOESOLO_CUT_WORKERS", "2")))
    return _CUT_POOL


class Pending:
    def __init__(self, btype, x, y, ids, t, purpose):
        self.btype, self.x, self.y, self.ids, self.t, self.purpose = btype, x, y, list(ids), t, purpose
        self.confirmed = False
        self.obj_id = None


class Herd:
    def __init__(self, key, x, y):
        self.key = key
        self.x, self.y = x, y
        self.ids = set()
        self.state = "new"        # new -> push -> kill -> eat
        self.push_id = None
        self.push_t0 = None
        self.pit_done = False


class Lure:
    def __init__(self, elephant_id):
        self.eid = elephant_id
        self.lurer = None
        self.state = "provoke"    # provoke -> run -> kill -> eat
        self.t = 0.0
        self.x = self.y = self.t0 = 0.0


class Brain:
    def __init__(self, game, me, enemies, log=print, pop_limit=200):
        self.pop_limit = pop_limit
        self.g = game
        self.me = me
        self.enemies = set(enemies)
        self.log = log
        self.r = gs.Reader(game, me)
        self.r.load_map()
        self.role = {}
        self.last_order = {}
        self.bad_spots = set()
        self.pending = []
        self.enemy_base = None
        self.tool_clicked = False
        self.bronze_clicked = False
        self.scout_trained = False
        self.techs_done = set()
        self._rp_fail, self._rp_fail_t, self._rp_pending = {}, {}, None
        self.rules_broken = False
        self.broken_reason = ""
        self.scout_goal = {}
        self.bad_goals = set()
        self.last_train = 0.0
        self.start_time = None
        self.tc_anchor = None
        self.attacking = False
        self.ticks = 0
        self.house_by_v10 = False
        # knowledge
        self.bushes_seen = {}       # id -> (x, y)
        self.herds = {}             # key -> Herd
        self.elephants_seen = set()
        self.animal_pos = {}        # id -> (x, y, type, t)
        self.enemy_vils_seen = {}   # id -> (x, y, t)
        self.berry_found_at = None  # (x, y) of the first bush seen
        self.lures = {}
        self.search_wp = {}         # villager id -> waypoint index
        self.wall = None            # active walling.Plan list
        self.gates = []             # open gaps in the sealed wall: dict(x, y, id, t, used)
        self.wall_sealed = False    # every wall slot built: units pass only through a deleted house
        self._sealed_t = -99.0
        self.wall_mode = None
        self.wall_t = -999.0
        self.last_wall_house = -999.0
        self.hp_prev = {}
        self.retreat_until = {}
        self.chase = {}             # unit id -> (target id, t0, d0)
        self.artifact_wp = {}
        self.woodline_placed = False
        self.hunt_site = {}         # villager id -> hunting site key
        self.sites, self.site_cap, self.site_load, self.hunt_capacity = [], {}, {}, 0
        self.lure_failed = set()
        self.lure_retry = {}            # elephant id -> game time from which it may be lured again
        self.wait_since = {}
        self.wd = {}                # watchdog timers
        self.diag_gaz, self.diag_ele = set(), set()   # gazelles / elephants seen in push / lure reach
        self.t_vil25 = None
        self.food_emergency = False
        self.food_desperate = False  # no food work at all: ranges unlimited
        self.food_short = False      # fewer food jobs than villagers off the wood line        # (kind, key) -> game time villagers started waiting there
        self.helpers = set()        # villagers pulled in to kill a lured elephant
        self.leads = {}             # villager id -> lure / push site it leads
        self.defenders = {}         # villager id -> enemy scout id it is chasing
        self.repairers = {}         # villager id -> (wall house id, since) repairing the wall under attack
        self.held = {}              # villager id -> (x, y, kind, since): full load, waiting for a near dropsite
        self._wall_hp = {}          # wall house id -> (hp, t) last seen
        self.scout_hunts = {}       # enemy scout id -> (x, y, t) where it attacked us
        self.attackers = []         # enemy soldiers attacking us right now
        self.enemy_army_seen = {}   # id -> (name, x, y, t): enemy soldiers seen (tactics)
        self.enemy_civs = {}        # player -> civ id
        self.my_civ = 0
        self.vil_cost = 50          # Palmyran: 75 (set when the civ is read)
        self.tactics = None
        self.lions = {}             # id -> (x, y, t) last seen
        self.meat_recs = {}         # meat site key -> record (pit_done)
        self.dodge_n = {}           # archer id -> sidesteps so far (alternating side)
        self.ntasks = {}            # ("lure", eid) / ("herd", key) -> brain.tasks task (new control code)
        self.anim_cache = {}        # animal id -> last snapshot object (pointer) for tracking in the fog
        self.wslow = GameWorld(self, self.g)
        self.wfast = None

    # ================================================================ helpers
    def say(self, msg):
        self.log("[P%d %5.0fs] %s" % (self.me, game_s(self.s) if hasattr(self, "s") else 0, msg))

    def now(self):
        return game_s(self.s)

    def recent(self, uid, key=None, within=4.0):
        lo = self.last_order.get(uid)
        if not lo:
            return False
        t, k = lo
        return self.now() - t < within and (key is None or k == key)

    def mark(self, units, key):
        t = self.now()
        for u in units:
            self.last_order[u.id] = (t, key)

    def order(self, units, target=None, x=None, y=None, key=None):
        units = [u for u in units if u]
        if not units:
            return
        if target is not None and hasattr(self, "on_target"):
            self.on_target[target.ptr] = self.on_target.get(target.ptr, 0) + len(units)
        gx, gy = (target.x, target.y) if target is not None else (x, y)
        if gx is not None and gy is not None:
            units = self.keep_from_raiders(units, gx, gy)
            if not units:
                return
            self.gate_request(units, gx, gy)
        self.g.order(units, target, x, y)
        self.mark(units, key or ("o", target.id if target else (round(x or 0), round(y or 0))))

    def keep_from_raiders(self, units, gx, gy):
        """Villagers are not sent to a target within FLEE_R of an enemy soldier (the user: villagers run from
        Bronze units) - they stay retreated instead (v10b: 30 villagers died per game, most of them re-sent to
        their wood line / farm / site 8 s after fleeing, with the raiders still there)."""
        raiders = getattr(self, "_raiders", None)
        if not raiders:
            return units
        if not any(math.hypot(e.x - gx, e.y - gy) < FLEE_R for e in raiders):
            return units
        t = self.now()
        tc = self.tc()
        out = []
        for u in units:
            if u.cls != gs.CLS_VILLAGER:
                out.append(u)
                continue
            if t >= self.retreat_until.get(u.id, 0) and tc is not None:
                self.retreat_until[u.id] = t + 8
                self.g.move([u], tc.x, tc.y)
                self.mark([u], ("flee",))
        return out

    def move(self, units, x, y):
        units = [u for u in units if u]
        if units:
            x = min(max(x, 1.0), self.r.W - 1.5)
            y = min(max(y, 1.0), self.r.H - 1.5)
            self.gate_request(units, x, y)
            self.g.move(units, x, y)
            self.mark(units, ("m", round(x), round(y)))

    def idle(self, u):
        return not self.r.busy(u) and not self.recent(u.id, within=3.0)

    def res(self, i):
        return self.s.res[i]

    def can_afford_unit(self, food=0, wood=0, gold=0, stone=0):
        """can_afford for a unit: what the next technology needs stays in the bank (research_plan)."""
        r = getattr(self, "research_reserve", None) or {}
        return self.can_afford(food=food + r.get("food", 0), wood=wood + r.get("wood", 0),
                               gold=gold + r.get("gold", 0), stone=stone)

    def can_afford(self, food=0, wood=0, gold=0, stone=0):
        return (self.res(gs.FOOD) >= food and self.res(gs.WOOD) >= wood and
                self.res(gs.GOLD) >= gold and self.res(gs.STONE) >= stone)

    @property
    def age(self):
        return int(round(self.res(gs.AGE)))

    def tc(self):
        tcs = self.s.of_type(gs.TOWN_CENTER, include_foundations=False)
        return tcs[0] if tcs else None

    def complete(self, btype):
        return [o for o in self.s.mine if o.type == btype and o.state == 2]

    def any_of(self, btype):
        return [o for o in self.s.mine if o.type == btype]

    def pending_of(self, btype):
        return [p for p in self.pending if p.btype == btype]

    def military(self):
        return [o for o in self.s.mine if o.kind == gs.KIND_COMBAT and o.cls != gs.CLS_VILLAGER
                and "Artifact" not in o.name]

    def obj_by_id(self, oid):
        return self._by_id.get(oid)

    def gaia_by_id(self, oid):
        return self._gaia_by_id.get(oid)

    def role_name(self, vid):
        r = self.role.get(vid)
        return r[0] if isinstance(r, tuple) else r

    def enemy_dir(self):
        """Unit vector from our TC towards where the enemy probably is."""
        tc = self.tc_anchor or (self.r.W / 2, self.r.H / 2)
        tgt = self.enemy_base or (self.r.W / 2.0, self.r.H / 2.0)
        if math.hypot(tgt[0] - tc[0], tgt[1] - tc[1]) < 3:
            tgt = (self.r.W - tc[0], self.r.H - tc[1])
        return unit(tgt[0] - tc[0], tgt[1] - tc[1])

    # ================================================================ main tick
    def tick(self):
        self.s = gs.Snapshot(self.r, self.enemies)
        s = self.s
        if not s.mine:
            return False
        self._by_id = {o.id: o for o in s.mine}
        self._gaia_by_id = {o.id: o for o in s.gaia}
        self.log_deaths()
        self.ticks += 1
        if self.start_time is None:
            self.start_time = self.now()
            try:
                st0 = self.g.research_states(self.me) or []
                self.civ_off = {i for i, v in enumerate(st0) if v == -1}
            except Exception:  # noqa: BLE001
                self.civ_off = set()
            miss = [n for i, n in ((59, "chariot archers"), (56, "improved bowmen"), (57, "composite bowmen"),
                    (68, "chariots"), (69, "cavalry"), (124, "camels"), (60, "horse archers"), (73, "phalanx"))
                    if i in self.civ_off]
            self.say("civ tree: no %s" % (", ".join(miss) if miss else "army unit missing"))
            if os.environ.get("AOESOLO_MASTER_DUMP") == "1":
                # (which master field says a unit is not in our civ's tree: compare the dumps of two civs)
                try:
                    pp = self.g.player_ptr(self.me)
                    ms = self.g.m.u32(pp + 0x24)
                    st = self.g.research_states(self.me)
                    self.say("STATEDUMP %s" % ",".join("%d:%d" % (i, v) for i, v in enumerate(st or [])))
                    for ut in ():
                        mp = self.g.m.u32(ms + 4 * ut) if ms else 0
                        raw = self.g.m.read(mp, 0x200) if mp else None
                        self.say("MASTERDUMP type %d ptr %x: %s" % (ut, mp or 0, raw.hex() if raw else "-"))
                except Exception as e:  # noqa: BLE001
                    self.say("MASTERDUMP failed: %r" % (e,))
            # a game started in a later age (tests: Bronze start, high resources): those clicks are done
            if self.age >= 2:
                self.tool_clicked = True
            if self.age >= 3:
                self.bronze_clicked = True
                self.bronze_click_t = self.start_time - 1000.0
        tc = self.tc()
        if tc and not self.tc_anchor:
            self.tc_anchor = (tc.x, tc.y)
        self.grid = Grid(s, self.bad_spots, checker=lambda t, x, y: self.g.can_place(self.me, t, x, y))
        self.pm = pathing.PassMap(s)
        # the ally's side of the map is the ally's: its resources (closer to an allied TC than to ours, and
        # within 45 tiles of it) are left out of everything we plan on
        tc_ = self.tc()
        if self.age >= 3 and str(self.me) in os.environ.get("AOESOLO_TEST_WRITING", "").split(",")                 and not self.any_of(gs.GOVERNMENT_CENTER) and self.can_afford(wood=175):
            try:                                     # (tests only: the BC before anything else)
                spot, why = self.building_spot(gs.GOVERNMENT_CENTER)
                if spot:
                    self.start_build(gs.GOVERNMENT_CENTER, spot, self.builders_near(3, *spot), "(test: Writing first) " + why)
            except Exception as e:  # noqa: BLE001
                self.say("test BC error: %r" % (e,))
        if demo_dump.enabled() and tc_ is not None:
            nvis = self.__dict__.get("_demo_done", {}).get("vis", 0)
            if (nvis == 0 and self.now() >= 60) or (nvis == 1 and self.now() >= 900):
                demo_dump.write(self, "vis", {"vis": s.vis.hex(), "ally_tcs": [list(a) for a in (s.ally_tcs or [])],
                                              "mine": [[o.x, o.y, o.kind] for o in s.mine],
                                              "enemy_seen": [[o.x, o.y, o.kind] for o in s.enemy],
                                              "enemy_bld_seen": [[o.x, o.y] for o in s.enemy_buildings_seen],
                                              "enemy_all": [[o.x, o.y, o.kind] for o in s.enemy_all]})
        if os.environ.get("AOESOLO_ORACLE") and tc_ is not None:
            try:
                self.oracle_diag(os.environ["AOESOLO_ORACLE"])
            except Exception as e:  # noqa: BLE001
                self.say("ORACLE error: %r" % (e,))
        if os.environ.get("AOESOLO_ETEST") and tc_ is not None:
            try:
                self.e_test()
            except Exception as e:  # noqa: BLE001
                self.say("ETEST error: %r" % (e,))
        if os.environ.get("AOESOLO_SQUEEZETEST") and tc_ is not None:
            try:
                self.squeeze_test(os.environ["AOESOLO_SQUEEZETEST"])
            except Exception as e:  # noqa: BLE001
                self.say("SQUEEZETEST error: %r" % (e,))
        if os.environ.get("AOESOLO_FARMWALK") and tc_ is not None:
            try:
                self.farm_walk_test(os.environ["AOESOLO_FARMWALK"])
            except Exception as e:  # noqa: BLE001
                self.say("FARMWALK error: %r" % (e,))
        if os.environ.get("AOESOLO_WALKTEST") and tc_ is not None:
            try:
                self.walk_test(os.environ["AOESOLO_WALKTEST"])
            except Exception as e:  # noqa: BLE001
                self.say("WALKTEST error: %r" % (e,))
        if os.environ.get("AOESOLO_TERRAIN_DIAG") and tc_ is not None and self.now() >= 40:
            try:
                self.terrain_diag(os.environ["AOESOLO_TERRAIN_DIAG"])
            except Exception as e:  # noqa: BLE001
                self.say("TERRDIAG error: %r" % (e,))
        if os.environ.get("AOESOLO_VIS_DIAG") == "1":
            try:
                self.vis_diag()
            except Exception as e:  # noqa: BLE001
                self.say("VISDIAG error: %r" % (e,))
        if getattr(s, "ally_tcs", None) and tc_ is not None:
            def ally_side(o, A=s.ally_tcs, mx=tc_.x, my=tc_.y):
                d_me = math.hypot(o.x - mx, o.y - my)
                return any(math.hypot(o.x - ax, o.y - ay) < min(45.0, d_me) for ax, ay in A)
            s.gaia = [o for o in s.gaia if not ally_side(o)]
        self.on_target = {}                 # gaia ptr -> villagers working it (bushes, trees)
        for v in s.villagers:
            a = self.r.action(v)
            if a and a[1]:
                self.on_target[a[1]] = self.on_target.get(a[1], 0) + 1
        t0 = time.time()
        times = []
        steps = (self.learn, self.check_enemy_violations, self.update_pending, self.walls, self.houses,
                     self.town_center, self.villagers, self.run_tasks, self.farm_reset, self.hold_far_loads, self.gate_keeper, self.wall_leak_check, self.wall_repair, self.buildings_program, self.stables,
                     self.research_plan, self.army, self.e_trap, self.artifacts, self.self_defence, self.anti_trap, self.lion_defence, self.watchdogs, self.stats,
                     self.food_audit)
        if os.environ.get("AOESOLO_STAGE") in ("chase", "raid"):
            # (tests only: the staged chase - the economy runs, the army / wall / research programs are replaced)
            steps = (self.learn, self.update_pending, self.houses, self.town_center, self.villagers, self.run_tasks,
                     self.farm_reset, self.hold_far_loads, self.stage_cheats, self.stage_chase, self.e_trap, self.self_defence,
                     self.anti_trap, self.watchdogs, self.stats)
        for step in steps:
            t1 = time.time()
            step()
            times.append((time.time() - t1, step.__name__))
        if time.time() - t0 > 1.0:                   # find what makes a tick slow
            times.sort(reverse=True)
            self.say("SLOW tick %.1f s: %s" % (time.time() - t0, ", ".join("%s %.2f" % (n, d) for d, n in times[:4])))
        return True

    def log_deaths(self):
        """'DEATH' line for every villager gone since the last tick: where, what it did, what was near."""
        now = {v.id: (v.x, v.y, v.hp) for v in self.s.villagers}
        prev = getattr(self, "_vil_prev", {})
        for vid, (x, y, hp) in prev.items():
            if vid in now:
                continue
            o = self._by_id.get(vid)
            if o is not None:                            # still ours, just not a "villager" this tick
                k = (vid, o.type, o.state)
                if k not in getattr(self, "_flap_seen", set()):
                    self.__dict__.setdefault("_flap_seen", set()).add(k)
                    self.say("villager #%d not in the villager list: type %s (%s) state %s" % (vid, o.type, o.name, o.state))
                now[vid] = (x, y, hp)
                continue
            near = sorted(((math.hypot(o.x - x, o.y - y), o) for o in self.s.gaia
                           if o.hp > 0 and o.kind == gs.KIND_COMBAT and (o.type in (gs.ELEPHANT, gs.GAZELLE) or "lion" in o.name.lower())),
                          key=lambda q: q[0])[:1]
            foe = sorted(((math.hypot(o.x - x, o.y - y), o) for o in self.s.enemy),
                         key=lambda q: q[0])[:1]
            lure = [eid for eid, L in self.lures.items() if L.lurer == vid]
            self.say("DEATH villager #%d (%s%s) at (%.0f,%.0f), last hp %.0f; nearest animal %s; nearest enemy %s" % (
                vid, self.role_name(vid) or "-", ", lurer of %d" % lure[0] if lure else "", x, y, hp,
                "%s %.1f" % (near[0][1].name, near[0][0]) if near else "-",
                "%.1f" % foe[0][0] if foe else "-"))
        self._vil_prev = now
        # soldiers too (the archer duels: who dies, to what, while dodging or not)
        mil_now = {u.id: (u.x, u.y, u.hp, u.name) for u in self.military()}
        mprev = getattr(self, "_mil_prev", {})
        t = self.now()
        for uid, (x, y, hp, name) in mprev.items():
            if uid in mil_now or uid in self._by_id:
                continue
            foe = sorted(((math.hypot(o.x - x, o.y - y), o) for o in self.s.enemy if o.kind == gs.KIND_COMBAT),
                         key=lambda q: q[0])[:1]
            dodged = t - self.__dict__.get("_dodge_t", {}).get(uid, -99) < 6
            self.say("SOLDIERDEATH #%d (%s) at (%.0f,%.0f), last hp %.0f; nearest enemy %s; dodged in the last 6 s: %s" % (
                uid, name, x, y, hp, "%s %.1f" % (foe[0][1].name, foe[0][0]) if foe else "-", dodged))
        self._mil_prev = mil_now

    # ================================================================ farms never run out
    def farm_reset(self):
        """The user's "ruộng bất tử": the game resets a farm's food when a Stop command is given to a
        selection holding the farms and one villager (players group the farms, box-add a villager,
        press S twice). Done every FARM_RESET_S seconds once a farm is below half; the farms' food
        before / after is logged so the effect can be checked in the arena."""
        t = self.now()
        if t - getattr(self, "_farm_reset_t", -999) < FARM_RESET_S:
            return
        farms = self.complete(gs.FARM)
        if not farms:
            return
        low = [f for f in farms if f.amount < FARM_RESET_BELOW]
        if not low:
            return
        v = next((v for v in self.s.villagers if self.role_name(v.id) == "farm"), None) or \
            (self.s.villagers[0] if self.s.villagers else None)
        if v is None:
            return
        self._farm_reset_t = t
        before = round(sum(f.amount for f in farms), 1)
        act = self.r.action(v)                       # the villager's farm: re-ordered right after the Stop
        back = next((f for f in farms if act and f.ptr == act[1]), None)
        try:
            self.g.stop(farms + [v])
            self.g.stop(farms + [v])
            if back is not None:
                self.order([v], back)
        except Exception as e:  # noqa: BLE001
            self.say("farm reset failed: %r" % (e,))
            return
        self._farm_reset_before = (t, before, len(farms))
        self.say("farm reset: Stop on %d farms + villager #%d (fields sum before: %s)" % (len(farms), v.id, before))

    def farm_fields(self, f):
        """DIAG: plausible 'food left' fields of a farm object: floats in 0..300 by offset."""
        import struct
        raw = self.g.m.read(f.ptr, 0x200)
        out = {}
        if raw:
            for off in range(0, len(raw) - 3, 4):
                v, = struct.unpack_from("<f", raw, off)
                if 0.5 <= v <= 300.0 and v == v:
                    out["%x" % off] = round(v, 1)
                iv, = struct.unpack_from("<i", raw, off)
                if 20 <= iv <= 300 and off not in (0x04,):
                    out["i%x" % off] = iv
        return out

    # ================================================================ new task runner
    def run_tasks(self):
        """tick() of the brain.tasks tasks (lure / herd push), their log lines into ours, and the
        old Lure / Herd records kept in step with them."""
        w = self.wslow
        if self.ntasks and self.now() - getattr(self, "_tasks_say_t", -99) > 10:
            self._tasks_say_t = self.now()
            self.say("TASKS slow: %s (id %x)" % (" ".join("%s/%s:%s" % (k[0], k[1], getattr(t, "state", "?")) for k, t in self.ntasks.items()), id(self.ntasks)))
        fr = getattr(self, "_farm_reset_before", None)
        if fr and self.now() - fr[0] > 6:
            self._farm_reset_before = None
            farms = self.complete(gs.FARM)
            after = round(sum(f.amount for f in farms), 1)
            self.say("farm reset: fields sum after 6 s: %s (before %s, %d farms, %d at 15)" % (
                after, fr[1], len(farms), sum(1 for f in farms if f.amount >= 14.9)))
            fd = getattr(self, "_farm_dump", None)
            if fd:
                self._farm_dump = None
                f = next((f for f in self.complete(gs.FARM) if f.ptr == fd[1]), None)
                if f is not None:
                    now_fields = self.farm_fields(f)
                    diff = {k: (fd[2].get(k), v) for k, v in now_fields.items() if fd[2].get(k) != v}
                    self.say("FARMDIAG ptr %x before %s after %s changed %s" % (fd[1], fd[2], now_fields, diff))
        for key, task in list(self.ntasks.items()):
            if not (task.done or task.failed):
                try:
                    task.tick(w, w)
                except Exception as e:  # noqa: BLE001
                    self.say("task %s tick error: %r" % (key, e))
            # every line since the last drain: the fast thread's lines (hit once / everybody attacks /
            # solo / LUREDBG) land between two ticks and were lost when only the tick's lines were taken
            n0 = getattr(task, "_drained", 0)
            lines = task.log[n0:]
            task._drained = n0 + len(lines)
            for _, msg in lines:
                self.say("%s %s: %s" % (task.name, key[1], msg))
            if key[0] == "lure":
                L = self.lures.get(key[1])
                if L is not None:
                    L.lurer = task.lurer
                    if task.state in ("provoke", "run", "kill"):
                        L.state = task.state
                    e = w.track(key[1])
                    if e is not None:
                        L.x, L.y = e.x, e.y
                if task.failed:
                    if "lion" in task.reason:
                        self.lure_retry[key[1]] = self.now() + 90     # the lion wanders off: try again
                    elif "nobody fresh" in task.reason or "no more spears" in task.reason:
                        self.lure_retry[key[1]] = self.now() + 60     # with fresh villagers: try again
                    else:
                        self.lure_failed.add(key[1])
                    self.lures.pop(key[1], None)
                    del self.ntasks[key]
                elif task.done:
                    del self.ntasks[key]                 # the old eat path takes the carcass from here
            else:
                h = self.herds.get(key[1])
                if h is None:
                    del self.ntasks[key]
                    continue
                if task.failed:
                    h.state, h.pusher, h.guard = "new", None, None
                    h.no_push_until = self.now() + 15
                    h.fails = getattr(h, "fails", 0) + (2 if "no way" in task.reason else 1)
                    if "no way" in task.reason:
                        # against the forest / the edge: never pushed again this game - a pit and eat
                        # there (the user's rule; human1: the same lone gazelle was tried 3 times)
                        h.state, h.no_push_until = "kill", self.now() + 900
                        self.say("herd %s: no way behind it - hunted where it stands from now on" % (h.key,))
                    del self.ntasks[key]
                elif task.done:
                    h.state = "eat" if self.herd_carcasses(h) else "done"
                    h.pusher = h.guard = None
                    del self.ntasks[key]
                else:
                    h.state = "pushed" if task.state == "kill" else "push"
                    h.mode = task.mode

    # ================================================================ watchdogs
    def test_delete(self):
        """AOESOLO_TEST_DELETE=1: at 150 s delete one finished house and log the house count after 6 s
        (verifies the Delete command 0x4EBBF0 in a bots-only arena match)."""
        t = self.now()
        st = self.__dict__.setdefault("_tdel", {})
        houses = self.complete(gs.HOUSE)
        if "t0" not in st and t >= 150 and houses:
            h0 = houses[0]
            st["t0"], st["n0"], st["id"] = t, len(houses), h0.id
            try:
                self.g.delete(h0)
                self.say("TESTDELETE sent for house #%d at (%.1f,%.1f); %d houses" % (h0.id, h0.x, h0.y, len(houses)))
            except Exception as e:  # noqa: BLE001
                self.say("TESTDELETE failed: %r" % (e,))
        elif "t0" in st and "done" not in st and t - st["t0"] > 6:
            st["done"] = True
            gone = not any(h.id == st["id"] for h in houses)
            self.say("TESTDELETE result: house #%d %s; houses %d -> %d" % (st["id"], "GONE" if gone else "still there", st["n0"], len(houses)))

    def watchdogs(self):
        if os.environ.get("AOESOLO_TEST_DELETE") == "1":
            self.test_delete()
        """Safety nets that do not depend on the rest of the logic being right: they catch a stuck
        economy (no house while pop-capped, an age-up never clicked, nobody on food, idle villagers)
        and fix it, and log what they did so the cause can be found."""
        t = self.now()
        tc = self.tc()
        if not tc:
            return
        wd = self.wd
        # 1. pop-capped with no house coming
        capped = self.res(gs.HEADROOM) < 1 and 4 + 4 * len(self.any_of(gs.HOUSE)) < self.pop_limit
        if capped and not self.pending_of(gs.HOUSE):
            wd.setdefault("capped", t)
            if t - wd["capped"] > 8 and self.can_afford(wood=30):
                spot, why = self.house_spot()
                b = self.builders_near(1, *spot) if spot else []
                if spot and b and self.start_build(gs.HOUSE, spot, b, "(watchdog: pop capped) " + why):
                    self.say("WATCHDOG pop capped %.0f s without a house: built one" % (t - wd["capped"]))
                wd.pop("capped", None)
        else:
            wd.pop("capped", None)
        # 1b. the first pit was "placed" but never appeared
        if self.woodline_placed and not self.any_of(gs.STORAGE_PIT) and not self.pending_of(gs.STORAGE_PIT):
            self.woodline_placed = False
            self.say("WATCHDOG wood-line pit missing: placing it again")
        # 2. an age-up that could be clicked
        busy = self.r.producing(tc)
        can_tool = (self.age == 1 and not self.tool_clicked and self.complete(gs.GRANARY)
                    and self.second_stone_building()
                    and self.can_afford(food=500) and len(self.s.villagers) >= 16)
        can_bronze = (self.age == 2 and not self.bronze_clicked and self.complete(gs.MARKET)
                      and self.complete(self.second_building()) and self.can_afford(food=800))
        if can_tool or can_bronze:
            wd.setdefault("age", t)
            if t - wd["age"] > 15 and not busy and getattr(self, "trained_tick", -1) != self.ticks:
                tech = gs.TECH_TOOL_AGE if can_tool else gs.TECH_BRONZE_AGE
                self.g.research(tc, tech)
                self.last_train = t
                if can_tool:
                    self.tool_clicked = True
                else:
                    self.bronze_clicked = True
                    self.bronze_click_t = t
                self.say("%s Age clicked with %d villagers (WATCHDOG: possible for %.0f s)" % (
                    "Tool" if can_tool else "Bronze", len(self.s.villagers), t - wd["age"]))
                wd.pop("age", None)
        else:
            wd.pop("age", None)
        # 2b. a villager boxed in (houses / buildings / trees round it): the nearest of our houses goes
        self.free_trapped()
        # 2c. every gatherer checked: carrying the same amount for 45 s = it neither gathers nor delivers
        self.check_gatherers()
        # 2d. a builder whose site is gone (finished, deleted, dropped) gets its job back (age4: 3-4
        #     'builders' stood 165 s by a pit finished long before)
        in_sites = {vid for p in self.pending for vid in p.ids}
        for v in self.s.villagers:
            r = self.role.get(v.id)
            if isinstance(r, tuple) and r[0] == "build" and v.id not in in_sites and not self.r.busy(v):
                self.role.pop(v.id, None)
                self.say("WORKDBG villager #%d at (%.0f,%.0f): builder of a site that is gone - back to work" % (v.id, v.x, v.y))
        # 3. nobody on food before Bronze
        food_roles = ("hunt", "berry", "farm")
        n_food = sum(1 for v in self.s.villagers if self.role_name(v.id) in food_roles)
        # nobody on food with a dozen villagers: food anywhere on the map (herds, berries, elephants at any
        # range, four scouts) until three villagers eat again
        desperate = (not self.bronze_clicked and len(self.s.villagers) >= 12 and n_food == 0)
        # ... or the near food is all gone with a town to feed (night1 match 2: 18 villagers on wood,
        # 1600 wood, berries only, a 6-bush patch at 63 tiles and herds beyond 60 tiles ignored)
        if not self.bronze_clicked and len(self.s.villagers) >= 18 and self.hunt_capacity <= 2 and self.food_short:
            self._food_dry_since = getattr(self, "_food_dry_since", None) or self.now()
            if self.now() - self._food_dry_since > 30:
                desperate = True
        else:
            self._food_dry_since = None
        if desperate and not self.food_desperate:
            self.say("WATCHDOG no food work in reach (%d on food): food at any range, 4 scouts" % n_food)
        self.food_desperate = desperate or (self.food_desperate and (n_food < 3 or self.hunt_capacity < 4))
        if not self.bronze_clicked and len(self.s.villagers) >= 8 and n_food == 0:
            wd.setdefault("nofood", t)
            if t - wd["nofood"] > 20 and not self.food_emergency:
                self.food_emergency = True
                self.say("WATCHDOG nobody on food for %.0f s: far food allowed, extra scouts out" % (t - wd["nofood"]))
        else:
            wd.pop("nofood", None)
            if n_food >= 3:
                self.food_emergency = False
        # 4. villagers idle for long
        idle_since = wd.setdefault("idle", {})
        for v in self.s.villagers:
            r = self.role.get(v.id)
            if self.r.busy(v) or isinstance(r, tuple) or v.id in self.defenders or v.id in self.helpers \
                    or v.id in self.repairers or v.id in self.held:
                idle_since.pop(v.id, None)
                continue
            t0 = idle_since.setdefault(v.id, t)
            if t - t0 > 5:
                idle_since[v.id] = t
                self.work(v, r, force=True)
                wd["idle_fixes"] = wd.get("idle_fixes", 0) + 1
                rep = wd.setdefault("idle_rep", {})
                c = rep.get(v.id)
                if c is None or math.hypot(v.x - c[1], v.y - c[2]) > 2 or t - c[3] > 60:
                    rep[v.id] = c = [0, v.x, v.y, t]
                c[0] += 1
                if c[0] == 4 and self.role_name(v.id) == "hunt" and self.waiting_hunter(v):
                    rep.pop(v.id, None)                  # (a lure waiter waits: that is its job)
                elif c[0] == 4:
                    # (the user: every villager checked often - one that stays idle after 4 re-orders is
                    #  given up by its job: its hunt site / role is dropped so the allocator moves it)
                    self.say("IDLEFIX villager #%d (%s) at (%.0f,%.0f) still idle after 4 re-orders in %.0f s: role dropped"
                             % (v.id, self.role_name(v.id), v.x, v.y, t - c[3]))
                    rname = self.role_name(v.id)
                    self.hunt_site.pop(v.id, None)
                    if not isinstance(r, tuple):
                        self.role.pop(v.id, None)
                        if rname:
                            self.__dict__.setdefault("role_ban", {})[v.id] = (rname, t + 60)
                    rep.pop(v.id, None)

    def food_audit(self):
        """Every 5 s: every gazelle / elephant / carcass / bush on explored ground is followed.
          gazelle: first hit (hp below max) -> death: seconds and tiles it ran in between ("hops");
          carcass: food eaten (went down with one of ours on it) vs rotted (went down with nobody on it,
                   or vanished with meat left);
          known food nobody works on (40 tiles from the TC), scouting, explored ground.
        A FOODAUDIT line every 60 s and at the Tool / Bronze clicks; tools/food_audit.py sums them up."""
        t = self.now()
        if t - getattr(self, "_fa_t", -99) < 5:
            return
        self._fa_t = t
        A = self.__dict__.setdefault("_fa", {"gaz": {}, "car": {}, "eaten": 0.0, "rot": 0.0, "hits": 0,
                                             "dead": 0, "hop_s": [], "hop_d": [], "alive_left": 0, "bush0": {},
                                             "bush_eaten": 0.0})
        tc = self.tc()
        if not tc:
            return
        explored = self.s.explored
        occ = self.target_counts()
        seen_ids = set()
        for o in self.s.gaia:
            if not explored(o.x, o.y):
                continue
            if o.type == gs.GAZELLE and o.cls != gs.CLS_DEAD:
                seen_ids.add(("g", o.id))
                g = A["gaz"].setdefault(o.id, {"t0": t, "hit": None, "hx": None, "hy": None, "dead": False})
                if g["hit"] is None and 0 < o.hp < (o.maxhp or 8) - 0.01:
                    g["hit"], g["hx"], g["hy"] = t, o.x, o.y
                    A["hits"] += 1
                if not g["dead"] and o.hp <= 0:
                    g["dead"] = True
                    A["dead"] += 1
                    if g["hit"] is not None:
                        A["hop_s"].append(t - g["hit"])
                        A["hop_d"].append(math.hypot(o.x - g["hx"], o.y - g["hy"]))
                g["x"], g["y"] = o.x, o.y
            elif (o.cls == gs.CLS_DEAD and o.type in gs.MEAT) or (o.type == gs.GAZELLE and o.hp <= 0) \
                    or (o.type == gs.ELEPHANT and o.hp <= 0):
                if o.amount <= 0:
                    continue
                seen_ids.add(("c", o.ptr))
                c = A["car"].get(o.ptr)
                if c is not None and o.amount < c["amt"] - 0.01:
                    d = c["amt"] - o.amount
                    if occ.get(o.ptr, 0) > 0 or c.get("worked"):
                        A["eaten"] += d
                    else:
                        A["rot"] += d
                A["car"][o.ptr] = {"amt": o.amount, "x": o.x, "y": o.y, "worked": occ.get(o.ptr, 0) > 0}
            elif o.type == gs.FORAGE and o.amount > 0:
                b0 = A["bush0"].get(o.ptr)
                if b0 is not None and o.amount < b0 - 0.01:
                    A["bush_eaten"] += b0 - o.amount
                A["bush0"][o.ptr] = o.amount
        for ptr, c in list(A["car"].items()):
            if ("c", ptr) not in seen_ids:
                if c["amt"] > 5 and self.s.explored(c["x"], c["y"]):
                    A["rot"] += c["amt"]                 # vanished with meat left = rotted away
                del A["car"][ptr]
        say_now = t - getattr(self, "_fa_say", -99) >= 60
        for flag in ("tool_clicked", "bronze_clicked"):
            if getattr(self, flag) and not A.get(flag):
                A[flag] = True
                say_now = True
        if not say_now:
            return
        self._fa_say = t
        R = 40
        hunted = {k for k in self.hunt_site.values()}
        alive_g = [(gid, g) for gid, g in A["gaz"].items() if not g["dead"] and ("g", gid) in seen_ids
                   and math.hypot(g["x"] - tc.x, g["y"] - tc.y) <= R]
        hit_alive = sum(1 for _gid, g in alive_g if g["hit"] is not None and t - g["hit"] > 10)
        eles = [o for o in self.s.gaia if o.type == gs.ELEPHANT and o.hp > 0 and explored(o.x, o.y)
                and o.dist(tc.x, tc.y) <= R]
        bushes = [o for o in self.s.gaia if o.type == gs.FORAGE and o.amount > 0 and explored(o.x, o.y)
                  and o.dist(tc.x, tc.y) <= R]
        idle_bush = sum(o.amount for o in bushes if occ.get(o.ptr, 0) == 0)
        cars = [c for c in A["car"].values() if math.hypot(c["x"] - tc.x, c["y"] - tc.y) <= R]
        idle_meat = sum(c["amt"] for c in cars if not c["worked"])
        # explored share of the disc of radius 30 round the TC
        W, H = self.r.W, self.r.H
        tot = ex = 0
        for yy in range(max(0, int(tc.y) - 30), min(H, int(tc.y) + 31), 3):
            for xx in range(max(0, int(tc.x) - 30), min(W, int(tc.x) + 31), 3):
                if (xx - tc.x) ** 2 + (yy - tc.y) ** 2 <= 900:
                    tot += 1
                    ex += 1 if explored(xx, yy) else 0
        roles = collections.Counter(self.role_name(v.id) for v in self.s.villagers)
        hs = sorted(A["hop_s"])
        med_s = hs[len(hs) // 2] if hs else 0
        hd = sorted(A["hop_d"])
        med_d = hd[len(hd) // 2] if hd else 0
        far_hop = sum(1 for d in A["hop_d"] if d > 3)
        self.say("FOODAUDIT gazelles: %d hit, %d dead (hit->death median %.0f s, %.1f tiles, %d ran 3+ tiles), "
                 "%d alive within %d (%d hit and still alive 10+ s) | elephants alive within %d: %d | meat eaten %.0f, "
                 "rotted %.0f, lying unworked %.0f | bushes eaten %.0f, unworked within %d: %.0f food on %d bushes | "
                 "scouts %d, explored %d%% of r30 | hunt sites %d | food %d" % (
                     A["hits"], A["dead"], med_s, med_d, far_hop, len(alive_g), R, hit_alive, R, len(eles),
                     A["eaten"], A["rot"], idle_meat, A["bush_eaten"], R, idle_bush,
                     sum(1 for o in bushes if occ.get(o.ptr, 0) == 0), roles.get("scout", 0),
                     100 * ex // max(1, tot), len(hunted), self.res(gs.FOOD)))

    def stats(self):
        """One line every 20 game seconds: the numbers needed to tune the economy."""
        t = self.now()
        if t - getattr(self, "_stat_t", -99) < 20:
            return
        self._stat_t = t
        roles = {}
        for v in self.s.villagers:
            r = self.role_name(v.id) or "-"
            roles[r] = roles.get(r, 0) + 1
        idle_roles = {}
        isince = self.__dict__.setdefault("_idle_since", {})
        long_idle = []
        alive_ids = set()
        for v in self.s.villagers:
            alive_ids.add(v.id)
            if not self.r.busy(v):
                r = self.role_name(v.id) or "-"
                idle_roles[r] = idle_roles.get(r, 0) + 1
                t0 = isince.setdefault(v.id, (t, v.x, v.y))
                if math.hypot(v.x - t0[1], v.y - t0[2]) > 3:
                    isince[v.id] = t0 = (t, v.x, v.y)
                if t - t0[0] >= 40:
                    long_idle.append("#%d %s@%.0f,%.0f %.0fs" % (v.id, r, v.x, v.y, t - t0[0]))
            else:
                isince.pop(v.id, None)
        for vid in [k for k in isince if k not in alive_ids]:
            del isince[vid]
        if long_idle:
            # (the user: no villager may stand doing nothing - every one idle 40+ s at the same spot)
            self.say("IDLEDBG long idle: %s" % " ".join(long_idle[:10]))
        idle = "%d(%s)" % (sum(idle_roles.values()), ",".join("%s:%d" % kv for kv in sorted(idle_roles.items())))
        tk = getattr(self, "tick_times", [])
        acc = getattr(self, "tc_idle_acc", {})
        tcs = "tc_food=%.0f tc_pop=%.0f " % (acc.get("food", 0), acc.get("pop", 0))
        self.tc_idle_acc = {}
        hs = {}
        for h in self.herds.values():
            hs[h.state] = hs.get(h.state, 0) + 1
        tcs += "herds=%s eles=%d " % (",".join("%s:%d" % kv for kv in sorted(hs.items())) or "0",
                                      sum(1 for (x, y, ty, _) in self.animal_pos.values() if ty == gs.ELEPHANT))
        try:
            attr36 = self.g.resources(self.me, 40)[36]      # (the player's "food per farm" attribute)
        except Exception:  # noqa: BLE001
            attr36 = -1
        self.say("STAT " + tcs + "wdfix=%d vil=%d food=%d wood=%d gold=%d age=%d farms=%d/%d farmfood=%.0f army=%d bldg=%d idle=%s roles=%s sites=%d hunt_cap=%d tick=%.0f/%.0fms" % (
            self.wd.get("idle_fixes", 0), len(self.s.villagers), self.res(gs.FOOD), self.res(gs.WOOD), self.res(gs.GOLD),
            self.age, len(self.complete(gs.FARM)), getattr(self, "farms_built", 0), attr36, len(self.military()),
            sum(1 for o in self.s.mine if o.kind == gs.KIND_BUILDING and o.hp > 2), idle,
            ",".join("%s:%d" % kv for kv in sorted(roles.items())), len(self.sites), self.hunt_capacity,
            1000 * sum(tk) / len(tk) if tk else 0, 1000 * max(tk) if tk else 0))
        self.tick_times = []
        if int(t) // 60 != int(t - 20) // 60:
            self.say("DIAG gaz_near=%d ele_near=%d t25=%s" % (len(self.diag_gaz), len(self.diag_ele),
                                                               "%.0f" % self.t_vil25 if self.t_vil25 else "-"))
        tc = self.tc()
        if self.sites and tc:
            parts = []
            for key, x, y, state in self.sites:
                n = sum(1 for v in self.s.villagers if self.hunt_site.get(v.id) == key)
                parts.append("%s%s:%s d=%.0f n=%d/%d" % (key[0], key[1] if key[0] == "lure" else "", state,
                                                      math.hypot(x - tc.x, y - tc.y), n, self.site_cap.get(key, 0)))
            self.say("SITES " + " | ".join(parts))
        if tc:
            grans = self.complete(gs.GRANARY)
            bparts = []
            for cx, cy, items in self.berry_clusters():
                cov = any(math.hypot(g0.x - cx, g0.y - cy) < 8 for g0 in grans) or math.hypot(cx - tc.x, cy - tc.y) < 8
                bparts.append("(%.0f,%.0f) d=%.0f n=%d%s" % (cx, cy, math.hypot(cx - tc.x, cy - tc.y), len(items),
                                                            "" if cov else " no-BG"))
            bv = [v for v in self.s.villagers if self.role_name(v.id) == "berry"]
            tgt = []
            for v in bv[:6]:
                a = self.r.action(v)
                tgt.append("%s@%.0f,%.0f" % ("g" if a and a[1] else "-", v.x, v.y))
            self.say("BERRIES cap=%d %s | vils %s" % (self.berry_capacity(), " ".join(bparts), " ".join(tgt)))

    # ================================================================ knowledge
    def learn(self):
        s = self.s
        t = self.now()
        for b in s.gaia:
            if b.type == gs.FORAGE and b.amount > 0:
                if b.id not in self.bushes_seen and self.berry_found_at is None:
                    self.berry_found_at = (b.x, b.y)
                    self.say("first berry bush seen at (%.0f,%.0f)" % (b.x, b.y))
                self.bushes_seen[b.id] = (b.x, b.y)
        for a in s.gaia:
            if a.type not in (gs.GAZELLE, gs.ELEPHANT) or a.hp <= 0 or not s.visible(a.x, a.y):
                continue
            self.animal_pos[a.id] = (a.x, a.y, a.type, t)
            self.anim_cache[a.id] = a                    # tracked by pointer later, even in the fog
            if self.tc_anchor:                           # diagnostics: food that came in reach
                d_tc = math.hypot(a.x - self.tc_anchor[0], a.y - self.tc_anchor[1])
                if a.type == gs.GAZELLE and d_tc <= PUSH_RANGE:
                    self.diag_gaz.add(a.id)
                elif a.type == gs.ELEPHANT and d_tc <= LURE_RANGE:
                    self.diag_ele.add(a.id)
            if a.type == gs.ELEPHANT:
                self.elephants_seen.add(a.id)
            else:
                herd = None
                for h in self.herds.values():
                    if a.id in h.ids or math.hypot(h.x - a.x, h.y - a.y) < 8:
                        herd = h
                        break
                if herd is None:
                    key = (int(a.x) // 8, int(a.y) // 8)
                    herd = self.herds.setdefault(key, Herd(key, a.x, a.y))
                herd.ids.add(a.id)
                herd.x, herd.y = 0.8 * herd.x + 0.2 * a.x, 0.8 * herd.y + 0.2 * a.y
        for a in s.gaia:
            if "lion" in a.name.lower() and a.kind == gs.KIND_COMBAT:
                if a.hp > 0 and s.visible(a.x, a.y):
                    if a.id not in self.lions:
                        self.say("lion #%d seen at (%.0f,%.0f): scouts keep %.0f tiles away" % (a.id, a.x, a.y, LION_SAFE))
                    self.lions[a.id] = (a.x, a.y, t)
                elif a.hp <= 0:
                    self.lions.pop(a.id, None)
        for lid in [k for k, v in self.lions.items() if t - v[2] > 180]:
            del self.lions[lid]
        for aid in [k for k, v in self.animal_pos.items() if t - v[3] > 240]:
            del self.animal_pos[aid]
        for e in s.enemy:
            if e.kind == gs.KIND_COMBAT and e.cls != gs.CLS_VILLAGER and e.hp > 0 and "Artifact" not in e.name:
                self.enemy_army_seen[e.id] = (e.name, e.x, e.y, t)
        for eid in [k for k, v in self.enemy_army_seen.items() if t - v[3] > 240]:
            del self.enemy_army_seen[eid]
        if not self.enemy_civs:
            try:
                self.my_civ = self.g.civ(self.me)
                self.vil_cost = 75 if tactics.civ_name(self.my_civ) == "Palmyran" else 50
                self.enemy_civs = {e: self.g.civ(e) for e in self.enemies}
                self.say("civs: ours %s, enemies %s" % (tactics.civ_name(self.my_civ),
                                                       {e: tactics.civ_name(c) for e, c in self.enemy_civs.items()}))
            except Exception as ex:  # noqa: BLE001
                self.enemy_civs = {e: 0 for e in self.enemies}
                self.say("civs unknown: %r" % (ex,))
        for e in s.enemy:
            if e.cls == gs.CLS_VILLAGER and e.hp > 0:
                self.enemy_vils_seen[e.id] = (e.x, e.y, t)
        for eid in [k for k, v in self.enemy_vils_seen.items() if t - v[2] > 90]:
            del self.enemy_vils_seen[eid]
        self.note_enemy_sites(t)
        if s.enemy_buildings_seen and self.enemy_base is None:
            b = min(s.enemy_buildings_seen, key=lambda o: o.dist(*self.tc_anchor) if self.tc_anchor else 0)
            self.enemy_base = (b.x, b.y)
            self.say("enemy base found at (%.0f,%.0f)" % self.enemy_base)

    def berry_clusters(self, live_only=True):
        """[(cx, cy, [bush objects or (id, x, y)])] clusters of bushes 5 tiles apart."""
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

    def bush_food(self, it):
        """Food left on one item of berry_clusters() ((id, x, y) tuples, not objects - age10: read as
        objects every bush counted 0 food, the patch kept ONE picker and the Stone age never ended)."""
        b = self.gaia_by_id(it[0]) if isinstance(it, tuple) else it
        amt = getattr(b, "amount", None) if b is not None else None
        return float(amt) if amt is not None else 150.0

    def known_food(self, rng=60.0):
        """Food we know of within `rng` of the TC: bushes (their amount), live gazelles (150 each),
        elephants not given up (300 each), carcasses with meat left."""
        tc = self.tc()
        if not tc:
            return 0.0
        f = 0.0
        for cx, cy, items in self.berry_clusters():
            if math.hypot(cx - tc.x, cy - tc.y) <= rng:
                f += sum(self.bush_food(b) for b in items)
        for aid, (x, y, ty, _) in self.animal_pos.items():
            if math.hypot(x - tc.x, y - tc.y) > rng:
                continue
            if ty == gs.GAZELLE:
                f += 150
            elif ty == gs.ELEPHANT and aid not in self.lure_failed:
                f += 300
        f += sum(m.amount for m in self.meat() if math.hypot(m.x - tc.x, m.y - tc.y) <= rng)
        return f

    def food_needed(self):
        """Food still to be gathered for the Tool and Bronze ages and the villagers to come."""
        need = (0 if self.tool_clicked else 500) + (0 if self.bronze_clicked else 800)
        need += self.vil_cost * max(0, self.stone_target() - len(self.s.villagers))
        return need - self.res(gs.FOOD)

    def food_items(self):
        """Food sources worth having found: live berry patches, herds not eaten yet and live elephants
        (2 = 1 item), all within FOOD_ITEM_RANGE of the TC."""
        tc = self.tc()
        if not tc:
            return 0
        R = FOOD_ITEM_RANGE
        n = sum(1 for cx, cy, _ in self.berry_clusters() if math.hypot(cx - tc.x, cy - tc.y) <= R)
        n += sum(1 for h in self.herds.values() if h.state != "done" and math.hypot(h.x - tc.x, h.y - tc.y) <= R)
        eles = sum(1 for aid, (x, y, ty, _) in self.animal_pos.items()
                   if ty == gs.ELEPHANT and aid not in self.lure_failed and math.hypot(x - tc.x, y - tc.y) <= R)
        return n + eles // 2

    # ================================================================ D3KT rule enforcement
    def check_enemy_violations(self):
        if self.rules_broken:
            return
        s = self.s
        for e in s.enemy + s.enemy_buildings_seen:
            n = e.name.lower()
            if "tower" in n or "wall" in n:
                return self.break_rules("enemy built %s" % e.name)
        mine_ptrs = {o.ptr for o in s.mine}
        enemy_mil = {}
        for e in s.enemy:
            if e.kind != gs.KIND_COMBAT:
                continue
            act = self.r.action(e)
            if act and act[1] in mine_ptrs:
                if e.cls == gs.CLS_VILLAGER:
                    tgt_owner = None
                    for o in s.mine:
                        if o.ptr == act[1]:
                            tgt_owner = o
                            break
                    if tgt_owner is not None and tgt_owner.kind == gs.KIND_COMBAT:
                        return self.break_rules("enemy villager %s attacked us" % e)
                else:
                    enemy_age = int(round(self.g.resources(e.owner, 8)[gs.AGE]))
                    if enemy_age < 3 and e.type != gs.SCOUT:
                        return self.break_rules("enemy %s attacked before Bronze Age" % e.name)
            if e.cls != gs.CLS_VILLAGER and "Artifact" not in e.name:
                enemy_mil.setdefault(e.owner, []).append(e)
        for owner, units in enemy_mil.items():
            enemy_age = int(round(self.g.resources(owner, 8)[gs.AGE]))
            if enemy_age < 3 and len(units) > 1:
                return self.break_rules("enemy P%d has %d military units before Bronze Age" % (owner, len(units)))

    def break_rules(self, why):
        # (the user, 13/10: the Bronze click and a Bronze army stay the goal - no barracks, no clubmen,
        #  no early army; only the villagers next to the one hit fight back, see self_defence)
        self.rules_broken = True
        self.broken_reason = why
        self.say("D3KT broken by enemy (%s) -> villagers near the attack fight back, the economy goes on" % why)

    # ================================================================ construction bookkeeping
    def start_build(self, btype, spot, builders, purpose=""):
        if not spot or not builders:
            return False
        # the game's building tree, as a player has it (the user, 13/10): the build command does not check it
        # - the bots built stables / ranges with no barracks. Nothing is built before its prerequisite stands.
        need = [bt for bt in PREREQ.get(btype, ()) if not self.complete(bt)]
        if need:
            if self.now() - self.__dict__.setdefault("_prereq_say", {}).get(btype, -99) > 60:
                self._prereq_say[btype] = self.now()
                self.say("PREREQ %d not built: %s first" % (btype, ", ".join(str(b) for b in need)))
            return False
        x, y = spot
        cost = BUILD_COST.get(btype, 0)
        unseen = sum(BUILD_COST.get(p.btype, 0) for p in self.pending if not p.confirmed)
        if self.s.res[gs.WOOD] - unseen < cost:
            return False
        if any(math.hypot(e.x - x, e.y - y) < FLEE_R + 2 for e in (getattr(self, "_raiders", None) or ())):
            return False                                 # (enemy soldiers at the spot: later)
        self.gate_request(builders, x, y)          # (builders sent across the sealed wall: a gate opens)
        self.g.build(builders, btype, x, y)
        self.s.res[gs.WOOD] -= cost
        self.mark(builders, ("b", btype))
        for b in builders:
            self.role[b.id] = ("build", btype)
        self.pending.append(Pending(btype, x, y, [b.id for b in builders], self.now(), purpose))
        self.grid.mark(x, y, btype)
        size = SIZES.get(btype, 3)
        x0, y0, x1, y1 = pathing.rect_of(x, y, size)
        self.pm.block_rect(x0, y0, x1, y1)
        self.say("build %d at (%.1f,%.1f) with %d villagers %s" % (btype, x, y, len(builders), purpose))
        return True

    def update_pending(self):
        t = self.now()
        keep = []
        for p in self.pending:
            obj = None
            if p.obj_id is not None:
                obj = self.obj_by_id(p.obj_id)
            else:
                for o in self.s.mine:
                    if o.type == p.btype and abs(o.x - p.x) < 1.01 and abs(o.y - p.y) < 1.01:
                        obj = o
                        p.obj_id = o.id
                        p.confirmed = True
                        break
            if not p.confirmed:
                if t - p.t > 6:
                    self.bad_spots.add((round(p.x, 1), round(p.y, 1), p.btype))
                    # the game's own answer for that spot now: (code, id of the blocking object) - the 4-6 % of
                    # flat, object-free footprints it refuses have no explanation yet (15/10)
                    why, bo = "", None
                    try:
                        ok_now = self.g.can_place(self.me, p.btype, p.x, p.y)
                        code, blocker = getattr(self.g, "last_place_reason", (None, None))
                        bo = self.obj_by_id(blocker) if blocker else None
                        why = " | can_place now %s code %s blocker %s%s" % (
                            ok_now, code, blocker, (" = %s (%.1f,%.1f)" % (bo.name, bo.x, bo.y)) if bo is not None else "")
                    except Exception:  # noqa: BLE001
                        pass
                    self.say("placement failed for %d at (%.1f,%.1f)%s" % (p.btype, p.x, p.y, why))
                    if bo is not None and bo.owner == self.me and bo.kind == gs.KIND_COMBAT:
                        self.bad_spots.discard((round(p.x, 1), round(p.y, 1), p.btype))   # (one of ours stood there: the spot is fine)
                    if "outside the wall" in (p.purpose or ""):
                        of = self.__dict__.setdefault("_outside_fail", {})
                        of[p.btype] = (of.get(p.btype, (0, t))[0] + 1, t)
                    self.release_builders(p)
                    if p.purpose == "(wood line)" and not self.any_of(gs.STORAGE_PIT):
                        self.woodline_placed = False             # try the wood line pit again elsewhere
                    self.s.res[gs.WOOD] += BUILD_COST.get(p.btype, 0)
                    continue
                keep.append(p)
                continue
            if obj is None or obj.state == 2:
                self.release_builders(p)
                continue
            alive = [self.obj_by_id(vid) for vid in p.ids]
            alive = [v for v in alive if v is not None and self.role_name(v.id) == "build"]
            raided = any(math.hypot(e.x - p.x, e.y - p.y) < FLEE_R + 2 for e in (getattr(self, "_raiders", None) or ()))
            if raided:
                # enemy soldiers at the site: nobody is sent, the builders there run (v10e: a wall house at (15,17)
                # took a new builder six times in 47 s, 17 Persian builders shot by chariot archers one after another)
                if alive and t - getattr(p, "raid_say", -99) > 30:
                    p.raid_say = t
                    self.say("site %d at (%.0f,%.0f) raided: builders released" % (p.btype, p.x, p.y))
                self.release_builders(p)
                keep.append(p)
                continue
            if not alive or (t - p.t > 45 and len(alive) < 2 and t - getattr(p, "helped", -99) > 45):
                # its builder died or was taken away, or it is taking too long: send the nearest villager
                extra = [v for v in self.builders_near(1, p.x, p.y) if v.id not in p.ids]
                if extra:
                    p.ids.append(extra[0].id)
                    p.helped = t
                    self.role[extra[0].id] = ("build", p.btype)
                    alive.append(extra[0])
                    self.say("foundation %d at (%.1f,%.1f) gets villager #%d" % (p.btype, p.x, p.y, extra[0].id))
            progress = False
            # builders that neither reach the site nor move (a build action on it, no path - v10b: 4 villagers
            # 5 tiles from a herd pit for 584 s) count as stuck too
            still = getattr(p, "still", {})
            moved = False
            for v in alive:
                lx, ly, lt = still.get(v.id, (v.x, v.y, t))
                if math.hypot(v.x - lx, v.y - ly) > 0.7 or v.dist(p.x, p.y) <= 3.5:
                    still[v.id] = (v.x, v.y, t)
                    moved = True
                elif t - lt > 20:
                    still[v.id] = (v.x, v.y, t)
                    p.stuck = getattr(p, "stuck", 0) + 1
            p.still = still
            for v in alive:
                if self.idle(v) or not self.recent(v.id, within=8):
                    act = self.r.action(v)
                    if not act or act[1] != obj.ptr:
                        self.order([v], obj, key=("o", obj.id))
                        if self.idle(v) and v.dist(p.x, p.y) > 3.5:
                            p.stuck = getattr(p, "stuck", 0) + 1   # ordered again and still standing far off
                else:
                    progress = True
            if progress and moved:
                p.stuck = 0
            if getattr(p, "stuck", 0) >= 4 and t - p.t > 40:
                # nobody can get there (the user's 1v2: the Shang bot's wood-line pit 40 tiles out, 5
                # builders idle for 1 700 s): the foundation is deleted and the spot is not tried again
                self.say("site %d at (%.1f,%.1f) unreachable (%d idle re-orders): dropped" % (p.btype, p.x, p.y, p.stuck))
                try:
                    self.g.delete(obj)
                except Exception as e:  # noqa: BLE001
                    self.say("site delete failed: %r" % (e,))
                self.bad_spots.add((round(p.x, 1), round(p.y, 1), p.btype))
                self.release_builders(p)
                if p.purpose == "(wood line)" and not self.any_of(gs.STORAGE_PIT):
                    self.woodline_placed = False
                continue
            keep.append(p)
        self.pending = keep

    def release_builders(self, p):
        for vid in p.ids:
            r = self.role.get(vid)
            if r and r[0] == "build":
                self.role.pop(vid, None)

    def task_owned(self):
        """Villagers a running task (lure / push) owns: never pulled away to build (lure3: a lurer was
        taken as a builder, stood next to the elephant and died)."""
        out = set()
        for task in self.ntasks.values():
            try:
                out.update(task.owned())
            except Exception:  # noqa: BLE001
                pass
        return out

    def builders_near(self, n, x, y, roles=("wood", "hunt", "berry", "farm", None)):
        owned = self.task_owned()
        vs = [v for v in self.s.villagers if self.role_name(v.id) in roles and v.id not in owned]
        vs.sort(key=lambda v: v.dist(x, y))
        return vs[:n]

    # ================================================================ footprint scoring helpers
    def explored_rect(self, x0, y0, size):
        return all(self.s.explored(x0 + dx, y0 + dy) for dx in range(size) for dy in range(size))

    def footprint_ok(self, btype, x0, y0, keep_clear=()):
        size = SIZES.get(btype, 3)
        if not self.grid.free(x0, y0, size, 0):
            return False
        if not self.explored_rect(x0, y0, size):
            return False                             # no foundation on unexplored ground
        for kx, ky, kr in keep_clear:
            for yy in range(y0, y0 + size):
                for xx in range(x0, x0 + size):
                    if (xx + 0.5 - kx) ** 2 + (yy + 0.5 - ky) ** 2 < kr * kr:
                        return False
        cx, cy = x0 + size / 2.0, y0 + size / 2.0
        if (round(cx, 1), round(cy, 1), btype) in self.bad_spots:
            return False
        # one of our villagers standing on the footprint: the game refuses the foundation (v10c, 15/10: every
        # unexplained refusal was "code 6, blocker = Builder / Lumberjack")
        for v in self.s.villagers:
            if x0 - 0.3 <= v.x < x0 + size + 0.3 and y0 - 0.3 <= v.y < y0 + size + 0.3:
                return False
        return True

    def place_checked(self, btype, cands):
        """cands: [(score, x0, y0)] -> best centre the game accepts, else None."""
        size = SIZES.get(btype, 3)
        cands.sort()
        tried = 0
        for _, x0, y0 in cands:
            if tried >= 15:
                break
            cx, cy = x0 + size / 2.0, y0 + size / 2.0
            # the game refuses foundations on unexplored ground (its own check does not test that)
            if not all(self.s.explored(x0 + dx, y0 + dy) for dx in range(size) for dy in range(size)):
                continue
            tried += 1
            if self.g.can_place(self.me, btype, cx, cy):
                return (cx, cy)
            self.bad_spots.add((round(cx, 1), round(cy, 1), btype))
        return None

    def keep_clear(self):
        kc = []
        tc = self.tc()
        if tc:
            kc.append((tc.x, tc.y, FARM_RING))
        for gr in self.any_of(gs.GRANARY):
            kc.append((gr.x, gr.y, 1.5 + FARM_GAP + 3))
        return kc

    def wall_keep_clear(self):
        """What the wall must enclose (the cut costs more through these discs): the farm ring plus two
        farm rows round the TC, the berries round each granary, the pits near home. The user's 1v2: an
        r=14 cut hugged the TC's 6.5-tile disc - 117 tiles inside, 18 houses - farms, pit and berries all
        outside, and the user's army walked into the working area untouched."""
        kc = []
        tc = self.tc()
        if not tc:
            return kc
        kc.append((tc.x, tc.y, FARM_RING + 4.5))
        for gr in self.any_of(gs.GRANARY):
            if gr.dist(tc.x, tc.y) <= 30:
                kc.append((gr.x, gr.y, 7.5))
        for pit in self.any_of(gs.STORAGE_PIT):
            if pit.dist(tc.x, tc.y) <= 30:
                kc.append((pit.x, pit.y, 5.0))
        return kc

    # ================================================================ walls ("bo nhà")
    def walls(self):
        """The wall plan (the user, 15/10: "plan B"): the cheapest cut between the town and the far world - the
        ring WALL_FAR tiles out, the map edge being a wall of its own - with forests, water, buildings and mines
        free and a house tile at 100 + distance (+50 unexplored). No disc of radii: the enclosure is whatever the
        terrain masses make cheapest, joined by the fewest houses. Planned every 20 s from 25 s (the barracks and
        the market stand on its line), fixed at the Bronze click and re-cut only when the ground round the town
        changes (a tree cut, a house built)."""
        t = self.now()
        tc = self.tc()
        jobs = self.__dict__.get("_cut_jobs", {})
        ready = any(j["done"] for j in jobs.values())     # (a cut finished: use it now, not 20 s later)
        every = 20 if self.bronze_clicked else 40     # (a 46-tile cut is 2-4 s of Python sharing the GIL with the tick:
                                                     #  the preliminary plan every 40 s - planb1: 135 slow ticks against 26)
        if not tc or (t - self.wall_t < every and not ready) or t < 25:
            return
        self.wall_t = t
        kc = self.wall_keep_clear()
        anchors_needed = [(p.x, p.y) for p in self.any_of(gs.STORAGE_PIT)[:1]] + \
                         [(g0.x, g0.y) for g0 in self.any_of(gs.GRANARY)[:1]]
        refused = [(x0, y0, x0 + 2, y0 + 2) for (x0, y0), n in self.__dict__.get("slot_fail", {}).items() if n >= 2]
        # never a ring hugging the TC: the TC and 3 tiles round it cannot be cut
        tx0, ty0 = int(math.floor(tc.x - 1.5)), int(math.floor(tc.y - 1.5))
        refused.append((tx0 - 5, ty0 - 5, tx0 + 8, ty0 + 8))   # (the TC + 2 tiles + the ring of 12 farms: never cut - the
                                                               #  narrow wall holds at least that 13x13, the user 15/10)
        explored = lambda x, y: bool(self.s.explored(x, y))   # noqa: E731
        # our farms: a wall may lean on one already there (troops cannot cross a farm) but it falls fast -
        # a cut through farm tiles costs a little under a new house, the free terrain stays first (the user, 14/10)
        soft = set()
        for f in self.any_of(gs.FARM):
            fx0, fy0, fx1, fy1 = pathing.footprint(f)
            soft |= {(xx, yy) for yy in range(fy0, fy1) for xx in range(fx0, fx1)}
        FAR = WALL_FAR
        cx, cy = tc.x, tc.y
        sink = lambda x, y: math.hypot(x + 0.5 - cx, y + 0.5 - cy) >= FAR - 3   # noqa: E731
        anchors_R = [(ax, ay) for ax, ay in anchors_needed if math.hypot(ax - tc.x, ay - tc.y) <= FAR - 8]
        fixed = self.bronze_clicked
        prev = getattr(self, "_wall_same", None)
        sig = None
        if fixed:
            r0 = int(FAR) + 3
            sig = (hash(bytes(self.pm.blk[max(0, int(tc.y) - r0) * self.pm.W:min(self.pm.H, int(tc.y) + r0 + 1) * self.pm.W])),
                   tuple(refused), int(sum(1 for (x, y) in getattr(self, "_wall_cut_tiles", ()) if self.s.explored(x, y))))
        plan = None
        if fixed and prev is not None and prev[0] == sig:
            plan = prev[1]                               # nothing changed round the town: the same plan
        else:
            # two plans, computed in turn: N (narrow, the cheapest cut) and W (wide: nothing within WALL_WIDE_R of the
            # TC is cut, a house nearer the TC costs a little more, so the cut goes to the far masses). The wide one is
            # taken when it is affordable (the user, 15/10: the working area matters more than the wood)
            vis = bytes(self.s.vis) if getattr(self.s, "vis", None) else b""
            common = dict(keep_clear=kc, uncuttable_rects=refused, soft=sorted(soft), explored_bytes=(vis, self.r.W),
                          sink_far=(tc.x, tc.y, FAR - 3))
            resN = self.cut_async(("N", 0), sig, self.pm, (tc.x, tc.y), anchors_R, FAR, **common)
            if resN is not None:
                self._wall_N = resN
            resW = self.cut_async(("W", 0), sig, self.pm, (tc.x, tc.y), anchors_R, FAR, wide=(2, 40),
                                  uncuttable_discs=[(tc.x, tc.y, WALL_WIDE_R)], **common)
            if resW is not None:
                self._wall_W = resW
            pN, pW = getattr(self, "_wall_N", None), getattr(self, "_wall_W", None)
            if pN is None:
                plan = prev[1] if prev is not None else None
            else:
                plan = pN
                if pW is not None and pW.flow < walling.INF and len(pW.leaks) <= len(pN.leaks) and \
                        len(pW.slots) <= min(WALL_WIDE_MAX, int(1.6 * len(pN.slots)) + 2):
                    plan = pW
                plan.kind = "W" if plan is pW else "N"
                if pW is not None and (resN is not None or resW is not None):
                    # (remembered only once both plans are in: planb3 froze the N plan before W had been computed)
                    self._wall_same = (sig, plan)
                    self._wall_cut_tiles = list(getattr(plan, "cut", []))
        if plan is None:
            return
        if plan.flow >= walling.INF:
            if t - getattr(self, "_wall_inf_say", -999) > 120:
                self._wall_inf_say = t
                self.say("wall: no cut closes the town within %d tiles (unexplored all round?)" % FAR)
            self.wall = []
            return
        if fixed and getattr(self, "wall_fixed_R", None) is None:
            self.wall_fixed_R = FAR
            pN, pW = getattr(self, "_wall_N", None), getattr(self, "_wall_W", None)
            self.say("wall: plan %s fixed at the Bronze click: %d houses, %d leaks, %d tiles inside, cut %d tiles (N %s houses / %s inside, W %s / %s)" % (
                getattr(plan, "kind", "?"), len(plan.slots), len(plan.leaks), plan.region_size, len(getattr(plan, "cut", [])),
                len(pN.slots) if pN else "-", pN.region_size if pN else "-", len(pW.slots) if pW else "-", pW.region_size if pW else "-"))
            if demo_dump.enabled():
                demo_dump.write(self, "wall", {
                    "R": FAR, "slots": [list(sl) for sl in plan.slots], "cut": [list(c) for c in getattr(plan, "cut", [])],
                    "leaks": [list(c) for c in plan.leaks], "inside": [list(c) for c in sorted(getattr(plan, "inside", []) or [])],
                    "cands": {}, "win": demo_dump.window(self, tc.x, tc.y, FAR + 2)})
        if t - getattr(self, "_known_say", -999) > 120:
            self._known_say = t
            cut_tiles = getattr(plan, "cut", None) or []
            seen = sum(1 for (xx, yy) in cut_tiles if self.s.explored(xx, yy))
            self.say("wall: plan %s%s: %d houses, %d leaks, %d tiles inside, %d of %d cut tiles explored" % (
                getattr(plan, "kind", "?"), " (fixed)" if fixed else "", len(plan.slots), len(plan.leaks), plan.region_size, seen, len(cut_tiles)))
        mode = "wide"
        if mode != self.wall_mode:
            self.say("wall plan -> %s %s" % (mode, [plan]))
        self.wall_mode = mode
        self.wall = [plan]
        rects = self.__dict__.setdefault("wall_rects", set())
        for (x0, y0, sz) in plan.slots:
            rects.add((x0, y0, sz))                      # every footprint ever planned: the wall houses

    def wall_reach(self):
        """The equivalent radius of the planned enclosure (the military cluster leans on it)."""
        for p in self.wall or []:
            n = getattr(p, "region_size", 0) or len(getattr(p, "inside", ()) or ())
            if n:
                return max(12.0, min(40.0, math.sqrt(n / math.pi) + 3))
        return 26.0

    def wall_shot(self, when):
        """Tests only (AOESOLO_DEMO_DIR): what the bot sees round its town and the wall plans it would make now,
        at the Tool click and at the Bronze click (the user, 15/10: 8 towns to review and propose the standard wall)."""
        try:
            tc = self.tc()
            if tc is None:
                return
            kc = self.wall_keep_clear()
            refused = [(x0, y0, x0 + 2, y0 + 2) for (x0, y0), n in self.__dict__.get("slot_fail", {}).items() if n >= 2]
            tx0, ty0 = int(math.floor(tc.x - 1.5)), int(math.floor(tc.y - 1.5))
            refused.append((tx0 - 3, ty0 - 3, tx0 + 6, ty0 + 6))
            explored = lambda x, y: bool(self.s.explored(x, y))   # noqa: E731
            soft = set()
            for f in self.any_of(gs.FARM):
                fx0, fy0, fx1, fy1 = pathing.footprint(f)
                soft |= {(xx, yy) for yy in range(fy0, fy1) for xx in range(fx0, fx1)}
            anchors = [(p.x, p.y) for p in self.any_of(gs.STORAGE_PIT)[:1]] + [(g0.x, g0.y) for g0 in self.any_of(gs.GRANARY)[:1]]
            plans = {}
            for R in (14, 20, 26, 33, 40):
                anchors_R = [(ax, ay) for ax, ay in anchors if math.hypot(ax - tc.x, ay - tc.y) <= R - 3]
                p = walling.plan_cut(self.pm.copy(), (tc.x, tc.y), anchors_R, R, keep_clear=kc, uncuttable_rects=refused,
                                     explored=explored, soft=soft)
                plans[str(R)] = {"slots": [list(sl) for sl in p.slots], "cut": [list(c) for c in getattr(p, "cut", [])],
                                 "leaks": [list(c) for c in p.leaks], "inside": [list(c) for c in sorted(getattr(p, "inside", []) or [])],
                                 "soft_cut": [list(c) for c in getattr(p, "soft_cut", [])], "flow": p.flow,
                                 "cost": len(p.slots) + 3 * len(p.leaks), "region": p.region_size}
            cx, cy = tc.x, tc.y
            pB = walling.plan_cut(self.pm.copy(), (tc.x, tc.y), [], WALL_FAR, keep_clear=kc, uncuttable_rects=refused,
                                  explored=explored, soft=soft,
                                  sink=lambda x, y: math.hypot(x + 0.5 - cx, y + 0.5 - cy) >= WALL_FAR - 3)
            plans["B"] = {"slots": [list(sl) for sl in pB.slots], "cut": [list(c) for c in getattr(pB, "cut", [])],
                          "leaks": [list(c) for c in pB.leaks], "inside": [list(c) for c in sorted(getattr(pB, "inside", []) or [])],
                          "soft_cut": [list(c) for c in getattr(pB, "soft_cut", [])], "flow": pB.flow,
                          "cost": len(pB.slots) + 3 * len(pB.leaks), "region": pB.region_size}
            refN = refused + [(tx0 - 5, ty0 - 5, tx0 + 8, ty0 + 8)]
            for key, hc, discs in (("N", None, []), ("W", lambda x, y, d: 100 + 2 * max(0, 40 - d), [(tc.x, tc.y, WALL_WIDE_R)])):
                pk = walling.plan_cut(self.pm.copy(), (tc.x, tc.y), [], WALL_FAR, keep_clear=kc, uncuttable_rects=refN,
                                      explored=explored, soft=soft, house_cost=hc, uncuttable_discs=discs,
                                      sink=lambda x, y: math.hypot(x + 0.5 - cx, y + 0.5 - cy) >= WALL_FAR - 3)
                plans[key] = {"slots": [list(sl) for sl in pk.slots], "cut": [list(c) for c in getattr(pk, "cut", [])],
                              "leaks": [list(c) for c in pk.leaks], "inside": [list(c) for c in sorted(getattr(pk, "inside", []) or [])],
                              "soft_cut": [list(c) for c in getattr(pk, "soft_cut", [])], "flow": pk.flow,
                              "cost": len(pk.slots) + 3 * len(pk.leaks), "region": pk.region_size}
            fixed = getattr(self, "wall_fixed_R", None)
            demo_dump.write(self, "wallshot", {
                "when": when, "tc": [tc.x, tc.y], "fixed_R": fixed, "houses": len(self.any_of(gs.HOUSE)),
                "wall_rects": [list(r) for r in self.__dict__.get("wall_rects", set())],
                "plans": plans, "win": demo_dump.window(self, tc.x, tc.y, 46)})
            self.say("WALLSHOT %s: plans %s" % (when, {R: (len(v["slots"]), len(v["leaks"]), v["region"]) for R, v in plans.items()}))
        except Exception as e:  # noqa: BLE001
            self.say("WALLSHOT error: %r" % (e,))

    def cut_async(self, key, tag, pm, *a, **kw):
        """walling.plan_cut in a worker thread, one at a time per bot (a 40-tile cut is 2-9 s of Python:
        the tick - every villager order - used to wait for it). Returns the finished Plan for `key` (once;
        plan.job_tag = the tag it was started with), None while it is computed or another cut runs."""
        J = self.__dict__.setdefault("_cut_jobs", {})
        j = J.get(key)
        if j is not None:
            if not j["done"]:
                return None
            del J[key]
            if j.get("err") is not None:
                self.say("wall cut failed: %r" % (j["err"],))
                return None
            res = j["res"]
            res.job_tag = j["tag"]
            return res
        if any(not o["done"] for o in J.values()):
            return None
        j = J[key] = {"done": False, "res": None, "tag": tag, "err": None}
        # a worker PROCESS, not a thread: a 46-tile cut is 2-4 s of pure Python and a thread shares the GIL with the
        # tick (planb3: 365 slow ticks, 8 s each, three towns never reached Bronze)
        try:
            fut = _cut_pool().submit(walling.cut_job, pm.W, pm.H, bytes(pm.blk), a, kw)
        except Exception as e:  # noqa: BLE001
            j["err"], j["done"] = e, True
            return None

        def done_cb(f, j=j):
            try:
                j["res"] = f.result()
            except Exception as e:  # noqa: BLE001
                j["err"] = e
            j["done"] = True
        fut.add_done_callback(done_cb)
        return None

    # ---------------------------------------------------------------- the sealed wall's gate
    def wall_inside(self, x, y):
        """Inside the town the wall plans enclose (the cut plan's enclosed tiles, else their discs)."""
        for p in self.wall or []:
            inside = getattr(p, "inside", None)
            if inside is not None:
                if (int(x), int(y)) in inside:
                    return True
                continue
            if math.hypot(x - p.center[0], y - p.center[1]) < p.radius - 0.5:
                return True
        return False

    def wall_slots(self):
        return [(x0 + 1.0, y0 + 1.0) for p in (self.wall or []) for (x0, y0, sz) in p.slots if sz == 2]

    def wall_houses(self):
        """The houses standing on the chosen ring (a band of the ring radius +- 2.5 around the plan's
        centre; the recomputed plan lists only the slots still open, never the houses already built)."""
        rects = self.__dict__.get("wall_rects", set())
        if rects:
            return [h for h in self.complete(gs.HOUSE)
                    if any(sz == 2 and abs(h.x - (x0 + 1.0)) < 0.6 and abs(h.y - (y0 + 1.0)) < 0.6 for (x0, y0, sz) in rects)]
        slots = self.wall_slots()
        return [h for h in self.complete(gs.HOUSE)
                if any(abs(h.x - cx) < 1.2 and abs(h.y - cy) < 1.2 for cx, cy in slots)]

    def gate_request(self, units, gx, gy):
        """Units ordered across the sealed wall: delete the wall house nearest their way (the user:
        delete a house to pass, close it again at once). At most two gaps open at a time."""
        if not self.wall:
            return
        tc0 = self.tc()
        if tc0 is not None and any(e.dist(tc0.x, tc0.y) < 30 for e in (getattr(self, "_raiders", None) or ())):
            return                                       # (enemy soldiers near the town: no hole in the wall - v11a,
                                                         #  a house deleted at 1118 s, 3 cavalry in the town at 1146 s)
        if not self.wall_sealed:
            # (not sealed as a whole, but the stretch between the unit and its target may be: v10b, 4 gold
            #  miners inside the north wall, the mine 6 tiles beyond it, "idle after 6 orders" for 3 minutes)
            if not any(self.wall_inside(u.x, u.y) != self.wall_inside(gx, gy) for u in units if u is not None and hasattr(u, "x")):
                return
            cache = self.__dict__.setdefault("_gate_bfs", {})
            k = (int(gx), int(gy), self.ticks)
            if k not in cache:
                dist = self.pm.bfs([(int(gx), int(gy))], max_cost=10 * 70)
                cache.clear()
                cache[k] = dist
            dist = cache[k]
            if any(dist[int(u.y) * self.pm.W + int(u.x)] >= 0 for u in units if u is not None and hasattr(u, "x")
                   and 0 <= int(u.x) < self.pm.W and 0 <= int(u.y) < self.pm.H):
                return                                   # a way round exists: no hole needed
        slots = self.wall_slots()
        if any(abs(gx - cx) < 2.5 and abs(gy - cy) < 2.5 for cx, cy in slots):
            return                                       # building / repairing the wall itself
        t = self.now()
        for u in units:
            if u is None or not hasattr(u, "x") or self.wall_inside(u.x, u.y) == self.wall_inside(gx, gy):
                continue
            straight = math.hypot(gx - u.x, gy - u.y)
            g = next((g for g in self.gates if math.hypot(g["x"] - u.x, g["y"] - u.y) +
                      math.hypot(g["x"] - gx, g["y"] - gy) < straight + 8), None)
            if g is not None:
                g["used"] = t                            # a gap on its way is already open: keep it
                continue
            if len(self.gates) >= 1:
                continue                                 # one hole in the wall at a time (gate16: 41 openings in 6 min)
            hs = self.wall_houses()
            if not hs:
                continue
            h = min(hs, key=lambda h: math.hypot(h.x - u.x, h.y - u.y) + math.hypot(h.x - gx, h.y - gy))
            try:
                self.g.delete(h)
            except Exception as e:  # noqa: BLE001
                self.say("gate: delete failed: %r" % (e,))
                return
            self.gates.append(dict(x=h.x, y=h.y, id=h.id, t=t, used=t))
            self.say("gate: wall house #%d at (%.0f,%.0f) deleted for %d unit(s) heading to (%.0f,%.0f)" % (
                h.id, h.x, h.y, len(units), gx, gy))

    def wall_repair(self):
        """The sealed wall under attack (a wall house losing hp, or an enemy unit acting on it): 2 villagers
        per attacked house (6 at most) run and repair it - idle first, then wood, then food, then gold
        (the user). They go back to their work once the house is whole or nobody has hit it for 12 s."""
        if not self.wall_sealed:
            if self.repairers:
                self.repairers.clear()
            return
        t = self.now()
        hs = {h.id: h for h in self.wall_houses()}
        enemy_tgt = set()
        for e in self.s.enemy:
            if e.kind == gs.KIND_COMBAT and e.hp > 0:
                a = self.r.action(e)
                if a and a[1]:
                    enemy_tgt.add(a[1])
        hit = {}
        for hid, h in hs.items():
            prev = self._wall_hp.get(hid)
            losing = prev is not None and h.hp < prev[0] - 0.01
            self._wall_hp[hid] = (h.hp, t if (losing or h.ptr in enemy_tgt) else (prev[1] if prev else -99))
            if (losing or h.ptr in enemy_tgt) or (t - self._wall_hp[hid][1] < 12 and h.hp < h.maxhp - 0.5):
                hit[hid] = h
        # release: house whole, gone, or quiet for 12 s
        for vid, (hid, since) in list(self.repairers.items()):
            h = hs.get(hid)
            # (released only when it is whole AND nobody aims at it: repair1 re-sent new villagers to the
            #  same targeted house every 3 s because a full-hp house released them at once)
            if h is None or hid not in hit or self.obj_by_id(vid) is None:
                del self.repairers[vid]
        if not hit:
            return
        rank = {None: 0, "idle": 0, "wood": 1, "berry": 2, "hunt": 2, "farm": 2, "berry2": 2, "gold": 3}
        busy = set(self.task_owned()) | set(self.defenders) | set(self.helpers)
        for hid, h in sorted(hit.items(), key=lambda kv: kv[1].hp):
            have = [vid for vid, (h2, _) in self.repairers.items() if h2 == hid]
            need = 2 - len(have)
            if need <= 0 or len(self.repairers) >= 6:
                continue
            cands = [v for v in self.s.villagers if v.id not in self.repairers and v.id not in busy
                     and self.role_name(v.id) in rank and t >= self.retreat_until.get(v.id, 0)]
            cands.sort(key=lambda v: (0 if self.idle(v) else rank.get(self.role_name(v.id), 4), v.dist(h.x, h.y)))
            for v in cands[:need]:
                self.repairers[v.id] = (hid, t)
                self.order([v], h)                       # right-click on our own building = repair
            if cands[:need]:
                self.say("wall house #%d at (%.0f,%.0f) under attack (%.0f/%.0f hp): %d villager(s) repair it" % (
                    hid, h.x, h.y, h.hp, h.maxhp, len(cands[:need])))
        for vid, (hid, since) in self.repairers.items():
            v, h = self.obj_by_id(vid), hs.get(hid)
            if v is not None and h is not None and self.idle(v):
                self.order([v], h)

    def wall_leak_check(self):
        """Every 30 s, the sealed wall is tested on the real map (the user: a hole opened mid-game stayed
        open to the end): a walk out of the TC with diagonal steps between two corner-touching blocks
        allowed (the planner cuts 4-connected - a squeeze it never sees). A way out = WALLLEAK: a house
        goes on the outside tile of a corner squeeze, an open side makes the plan be made again."""
        t = self.now()
        R = getattr(self, "wall_fixed_R", None)
        tc = self.tc()
        if R is None or not self.wall_sealed or not tc or t - getattr(self, "_leak_t", -99) < 30:
            return
        self._leak_t = t
        pm = self.pm
        W, H = pm.W, pm.H
        cx, cy = tc.x, tc.y
        lim2 = (R + 4.0) ** 2
        out2 = (R + 2.0) ** 2
        x0, y0 = int(cx - 1.5), int(cy - 1.5)
        start = [(xx, yy) for (xx, yy) in pm.ring_tiles(x0, y0, x0 + 3, y0 + 3) if pm.passable(xx, yy)]
        parent = {st: None for st in start}
        stack = list(start)
        found = None
        while stack and found is None:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in parent or not pm.passable(nx, ny):
                    continue
                if dx and dy and not (pm.passable(x + dx, y) and pm.passable(x, y + dy)):
                    # (no step between two blocks touching at a corner: SQUEEZETEST 15/10, a villager sent
                    #  1.4 tiles across two such corners never got through - the "corner squeeze" leaks were
                    #  false alarms, the wall flipped sealed / leaking dozens of times a game)
                    continue
                if (nx + 0.5 - cx) ** 2 + (ny + 0.5 - cy) ** 2 > lim2:
                    continue
                parent[(nx, ny)] = (x, y)
                if (nx + 0.5 - cx) ** 2 + (ny + 0.5 - cy) ** 2 > out2:
                    found = (nx, ny)
                    break
                stack.append((nx, ny))
        if found is None:
            return
        # the step where the way crosses the wall: the first one leaving the plan's inside
        inside = set()
        for p in self.wall or []:
            inside |= getattr(p, "inside", set()) or set()
        path = []
        node = found
        while node is not None:
            path.append(node)
            node = parent[node]
        path.reverse()
        cross = None
        for a, b in zip(path, path[1:]):
            if a in inside and b not in inside:
                cross = (a, b)
                break
        if cross is None:
            cross = (path[-2], path[-1]) if len(path) >= 2 else (found, found)
        (ax, ay), (bx, by) = cross
        if any(math.hypot(g["x"] - bx, g["y"] - by) < 4 for g in self.gates):
            return                                       # an open gate: on purpose
        squeeze = ax != bx and ay != by and not pm.passable(ax, by) and not pm.passable(bx, ay)
        if squeeze and os.environ.get("AOESOLO_SQUEEZETEST"):
            self.__dict__.setdefault("_sq_cands", []).append((ax, ay, bx, by))
        self.say("WALLLEAK the sealed wall leaks at (%d,%d)->(%d,%d)%s" % (
            ax, ay, bx, by, " (a corner squeeze)" if squeeze else " - the plan is made again"))
        self.wall_sealed = False
        if not squeeze:
            self._wall_same = None                       # (re-planned on the real map next walls() call)
            self.wall_t = -99
            return
        # (one patch a minute, and a squeeze patched twice that is still there is given up - ab3: the same
        #  squeeze reported 21 times, 40 patch houses)
        tries = self.__dict__.setdefault("_squeeze_tries", {})
        k = (ax, ay, bx, by)
        if tries.get(k, 0) >= 2 or t - getattr(self, "_squeeze_t", -99) < 60:
            return
        if not self.can_afford(wood=30):
            return
        tries[k] = tries.get(k, 0) + 1
        self._squeeze_t = t
        for fx, fy in ((bx, by), (bx - 1, by), (bx, by - 1), (bx - 1, by - 1),
                       (ax, ay), (ax - 1, ay), (ax, ay - 1), (ax - 1, ay - 1)):
            if self.footprint_ok(gs.HOUSE, fx, fy):
                spot = (fx + 1.0, fy + 1.0)
                b = self.builders_near(1, *spot)
                if b and self.start_build(gs.HOUSE, spot, b, "(wall) (corner squeeze)"):
                    self.__dict__.setdefault("wall_rects", set()).add((fx, fy, 2))
                return

    def gate_keeper(self):
        """Every wall slot built = the town is sealed; an open gap is closed (the house rebuilt) once
        none of ours has been within 4 tiles of it for 5 s."""
        t = self.now()
        if self.wall and t - self._sealed_t > 5:
            self._sealed_t = t
            # a wall slot that failed can_place once (a unit standing on it) stayed in bad_spots for
            # ever -> the last 11 slots of a ring were never retried (gate8: 27 of 38 built, then
            # houses went to the 'strip'). While the ring is unsealed, house spots are forgiven every 60 s
            if getattr(self, "wall_fixed_R", None) is not None and not self.wall_sealed                     and t - getattr(self, "_bad_purge_t", -999) > 60:
                self._bad_purge_t = t
                for k in [k for k in self.bad_spots if k[2] == gs.HOUSE]:
                    self.bad_spots.discard(k)
            # sealed = the plan recomputed from the real map finds no opening left (the built houses
            # are obstacles now, so counting 'wall houses' against the current slots was meaningless)
            sealed = getattr(self, "wall_fixed_R", None) is not None and \
                not any(p.openings or p.leaks or p.slots or getattr(p, "flow", 0) >= walling.INF for p in self.wall)
            if sealed != self.wall_sealed:
                self.say("wall %s (%d wall houses, leaks %d)" % ("SEALED - a house is deleted to pass" if sealed else "open",
                                                              len(self.wall_houses()), sum(len(p.leaks) for p in self.wall)))
            self.wall_sealed = sealed
            if not sealed and getattr(self, "wall_fixed_R", None) is not None and t - getattr(self, "_wall_stat_t", -999) > 60:
                self._wall_stat_t = t
                slots = self.wall_slots()
                hs = self.wall_houses()
                free = [c for c in slots if not any(abs(h.x - c[0]) < 1.2 and abs(h.y - c[1]) < 1.2 for h in hs)]
                refused = sum(1 for n in self.__dict__.get("slot_fail", {}).values() if n >= 2)
                leaks = [t for p in self.wall for t in p.leaks]
                self.say("wall status: %d slots left (%s), openings %d, leaks %d (%s), refused %d, wood %d" % (
                    len(slots), " ".join("(%.0f,%.0f)" % c for c in free[:6]),
                    sum(len(p.openings) for p in self.wall), len(leaks), " ".join("(%d,%d)" % t for t in leaks[:6]),
                    refused, self.res(gs.WOOD)))
        if not self.gates:
            return
        mine = list(self.s.villagers) + self.military()
        for g in list(self.gates):
            if any(o.dist(g["x"], g["y"]) < 4.0 for o in mine) or any(
                    o.dist(g["x"], g["y"]) < 14.0 and not self.wall_inside(o.x, o.y) for o in self.s.villagers):
                g["used"] = t                            # (a villager still out there, e.g. at a mine 6 tiles beyond the
                                                         #  wall, keeps it open: v10e, deleted and rebuilt every trip)
            if t - g["t"] > 240:
                self.gates.remove(g)                     # lost track: the wall program refills the slot
                continue
            tc0 = self.tc()
            raid = tc0 is not None and any(e.dist(tc0.x, tc0.y) < 30 for e in (getattr(self, "_raiders", None) or ()))
            if (raid or (t - g["used"] > 5 and t - g["t"] > 15)) and self.can_afford(wood=30):
                if self.start_build(gs.HOUSE, (g["x"], g["y"]), self.builders_near(1, g["x"], g["y"]), "(gate closed)"):
                    self.gates.remove(g)
                    self.say("gate: wall house at (%.0f,%.0f) rebuilt" % (g["x"], g["y"]))

    def enemy_threat(self):
        for owner in self.enemies:
            try:
                if int(round(self.g.resources(owner, 8)[gs.AGE])) >= 3:
                    return True
            except Exception:
                pass
        tc = self.tc()
        for e in self.s.enemy:
            if e.kind == gs.KIND_COMBAT and e.cls != gs.CLS_VILLAGER and tc and e.dist(tc.x, tc.y) < 30:
                return True
        return False

    def next_wall_slot(self, btype=gs.HOUSE):
        """Next free footprint of the active wall plan for a house, or a 3x3 building slot."""
        if not self.wall:
            return None
        if btype == gs.HOUSE:
            for p in self.wall:
                for (x0, y0, sz) in p.slots:
                    if sz != 2:
                        continue
                    if not self.footprint_ok(gs.HOUSE, x0, y0) and self.explored_rect(x0, y0, 2):
                        # the placement grid refuses a slot the cut planner thinks is free (forest
                        # terrain, a decoration, a unit parked there...): after ~2 minutes of that the
                        # cut goes round it (tech3: one slot skipped silently for 25 minutes)
                        ff = self.__dict__.setdefault("slot_ffail", {})
                        ff[(x0, y0)] = ff.get((x0, y0), 0) + 1
                        if ff[(x0, y0)] == 12:
                            sf = self.__dict__.setdefault("slot_fail", {})
                            sf[(x0, y0)] = max(2, sf.get((x0, y0), 0))
                            self.say("wall slot (%d,%d) never placeable: planned around from now on" % (x0, y0))
                        continue
                    if self.footprint_ok(gs.HOUSE, x0, y0):
                        c = (x0 + 1.0, y0 + 1.0)
                        if not self.house_allowed(*c):
                            # (too near the TC / in a herd's way: counted like a placement refusal, the
                            #  cut goes round it after a while - wall5: the last slot of two rings sat
                            #  in the farm ring for 10 minutes with 600-975 wood in the bank)
                            ff = self.__dict__.setdefault("slot_ffail", {})
                            ff[(x0, y0)] = ff.get((x0, y0), 0) + 1
                            if ff[(x0, y0)] == 12:
                                sf = self.__dict__.setdefault("slot_fail", {})
                                sf[(x0, y0)] = max(2, sf.get((x0, y0), 0))
                                self.say("wall slot (%d,%d) not allowed for a house: planned around from now on" % (x0, y0))
                            continue
                        if self.g.can_place(self.me, gs.HOUSE, *c):
                            return c
                        self.bad_spots.add((round(c[0], 1), round(c[1], 1), gs.HOUSE))
                        sf = self.__dict__.setdefault("slot_fail", {})
                        sf[(x0, y0)] = sf.get((x0, y0), 0) + 1
                        if sf[(x0, y0)] == 2:
                            self.say("wall slot (%d,%d) refused twice by the game: planned around from now on" % (x0, y0))
            return None
        for p in self.wall:
            slot = walling.best_building_slot(self.pm, p, 3, keep_clear=self.keep_clear())
            if slot:
                c = (slot[0] + 1.5, slot[1] + 1.5)
                if self.explored_rect(slot[0], slot[1], 3) and self.g.can_place(self.me, btype, *c):
                    return c
        return None

    # ================================================================ houses
    def house_allowed(self, cx, cy):
        """The user: no house right next to the TC (elephants and gazelles are killed there and the
        houses of the wall plan blocked a herd's way home), nor in the way of a herd being pushed."""
        tc = self.tc()
        if tc is None:
            return True
        if math.hypot(cx - tc.x, cy - tc.y) < FARM_RING + 0.5:
            return False
        for h in self.herds.values():
            if h.state not in ("push", "pushed", "new") or not self.herd_live(h):
                continue
            if math.hypot(h.x - tc.x, h.y - tc.y) > PUSH_RANGE:
                continue
            # the corridor from the herd to the TC, 3 tiles either side
            ux, uy = h.x - tc.x, h.y - tc.y
            L2 = ux * ux + uy * uy
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((cx - tc.x) * ux + (cy - tc.y) * uy) / L2))
            if math.hypot(tc.x + k * ux - cx, tc.y + k * uy - cy) < 3.0 + 1.0:
                return False
        return True

    def house_spot(self):
        spot = self.next_wall_slot(gs.HOUSE)
        if spot:
            return spot, "(wall)"
        tc = self.tc()
        houses = self.any_of(gs.HOUSE)
        kc = self.keep_clear()
        # a strip: next to the previous houses, outside the farm ring, towards the enemy
        ex, ey = self.enemy_dir()
        anchors = [(h.x, h.y) for h in houses] or [(tc.x + ex * 8, tc.y + ey * 8)]
        cands = []
        for ax, ay in anchors:
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x0, y0 = int(ax + dx - 1), int(ay + dy - 1)
                    if not self.footprint_ok(gs.HOUSE, x0, y0, kc):
                        continue
                    cx, cy = x0 + 1.0, y0 + 1.0
                    d_tc = math.hypot(cx - tc.x, cy - tc.y)
                    if d_tc < FARM_RING + 0.5 or d_tc > 18 or not self.house_allowed(cx, cy):
                        continue
                    touch = min(math.hypot(cx - hx, cy - hy) for hx, hy in anchors)
                    cands.append((touch * 2 + abs(d_tc - 9) + self._near_resources_penalty(cx, cy), x0, y0))
        if not cands:
            # nothing next to the strip yet (unexplored): anywhere on the 7-9 ring, enemy side first
            for dy in range(-10, 11):
                for dx in range(-10, 11):
                    x0, y0 = int(tc.x + dx - 1), int(tc.y + dy - 1)
                    cx, cy = x0 + 1.0, y0 + 1.0
                    d_tc = math.hypot(cx - tc.x, cy - tc.y)
                    if not (FARM_RING + 0.5 <= d_tc <= 9.5) or not self.footprint_ok(gs.HOUSE, x0, y0, kc) \
                            or not self.house_allowed(cx, cy):
                        continue
                    face = (cx - tc.x) * ex + (cy - tc.y) * ey
                    cands.append((-face * 0.5 + abs(d_tc - 8) + self._near_resources_penalty(cx, cy), x0, y0))
        spot = self.place_checked(gs.HOUSE, cands)
        return spot, "(strip)"

    def houses(self):
        s = self.s
        tc = self.tc()
        # one house at a time normally; while the wall is being filled (Bronze clicked) three builders
        # work on three wall houses at once (gate5: 15-17 of 27 wall houses in 30 min with one)
        filling = self.wall and self.age >= 2 and self.res(gs.WOOD) >= 60 and (self.bronze_clicked or self.enemy_threat())
        if not tc or len(self.pending_of(gs.HOUSE)) >= (3 if filling else 1):
            return
        houses = self.any_of(gs.HOUSE)
        room = 3 + (len(self.complete(gs.STABLE)) if self.age >= 3 else 0)   # every stable + TC eat room fast
        need_pop = (4 + 4 * len(houses) < self.pop_limit) and (self.res(gs.HEADROOM) <= room or not houses)
        ring = getattr(self, "wall_fixed_R", None) is not None
        # before the Bronze click the wall houses come after the Bronze buildings and the first farms (ms1: 12-21
        # wall houses, 360-630 wood, in the Tool age - the market / stable and the farms waited, 5 minutes there)
        # (and after the farms the step plans: every planned farm's 75 wood stays in the bank - 1v4 of 14/10,
        #  Yamato: 15 wall houses in the Tool age, the farms waited for wood, Bronze clicked 7 minutes after Tool)
        farms_left = max(0, getattr(self, "_farms_want", 0) - len(self.any_of(gs.FARM)) - len(self.pending_of(gs.FARM)))
        tool_ok = self.tool_wood_free(60) and (self.res(gs.WOOD) >= 300 or
                                               (len(self.any_of(gs.FARM)) >= 4 and self.res(gs.WOOD) >= 60 + 75 * farms_left))
        # the user (15/10): the wall is built after the Bronze click, and after the 4-8 farms the free villagers
        # can man; before the click only the compulsory buildings stand on the wall line (an enemy soldier
        # near the town is the one exception)
        farms_after = 0
        if self.bronze_clicked:
            wild = sum(self.site_cap.get(k, 0) for (k, _x, _y, _st) in self.sites) + self.berry_capacity()
            # the wall waits for the first 4 farms only (the user: 4-8 farms first, by the free villagers) - planb2: with
            # all 8 the wall waited for 600 wood and 3 of 4 towns were still open at minute 24
            farms_after = max(0, min(4, min(8, 12 - wild)) - len(self.any_of(gs.FARM)) - len(self.pending_of(gs.FARM)))
        tc0 = tc
        raid_near = any(e.dist(tc0.x, tc0.y) < 30 for e in (getattr(self, "_raiders", None) or ()))
        wall_fill = (self.wall and self.res(gs.WOOD) >= 60 and self.now() - self.last_wall_house > 8
                     and ((self.bronze_clicked and (farms_after == 0 or self.res(gs.WOOD) >= 60 + 75 * farms_after))
                          or raid_near)                 # (not enemy_threat(): true once ANY enemy is in Bronze -
                                                         #  rules2: Greek filled 25 wall houses before its own click)
                     and len(houses) < 45)
        if not (need_pop or wall_fill) or not self.can_afford(wood=30):
            return
        if (not self.woodline_placed and self.any_of(gs.GRANARY) and houses
                and self.res(gs.HEADROOM) > 1 and 90 <= self.res(gs.WOOD) < 150):
            return                                  # almost the first pit's 120 wood: the pit comes first
        if (houses and not self.any_of(gs.GRANARY) and self.berry_found_at and self.res(gs.HEADROOM) >= 1
                and self.res(gs.WOOD) - 30 < 120):
            return                                  # the first granary's 120 wood first (ab1: 110 left, no granary)
        spot, why = self.house_spot()
        if not spot:
            return
        if not need_pop and "(wall)" not in why:
            return                                  # filling the wall: a wall slot or nothing
        vs = sorted(s.villagers, key=lambda v: v.id)
        if not houses:
            b = vs[:2]                      # first house: 2 builders (the 3rd searches); later houses: 1
            why = "(first house) " + why
        elif len(vs) == 10 and not self.house_by_v10:
            b = vs[9:10]
            self.house_by_v10 = True
        else:
            b = self.builders_near(1, *spot)
        if b and self.start_build(gs.HOUSE, spot, b, why if need_pop else why + " (fill the wall)"):
            if not need_pop:
                self.last_wall_house = self.now()

    def _near_resources_penalty(self, cx, cy):
        pen = 0.0
        for o in self.s.gaia:
            if o.type in (gs.FORAGE, gs.GOLD_MINE, gs.STONE_MINE) and math.hypot(o.x - cx, o.y - cy) < 4:
                pen += 3
        return pen

    # ================================================================ town center
    # gather rates per villager per game second, walking included (measured by players: berries
    # ~0.3, hunting ~0.45, farms ~0.4, wood ~0.4 with a pit close by)
    RATE_FOOD, RATE_WOOD = 0.38, 0.40

    def eco_forecast(self):
        """What the current step still costs, beyond the stock, and how many of the gatherers should chop
        so that the food and the wood are both there at the same moment.
        Stone age: the Tool click (500 food), the villagers still to make (50 each), their houses, the
        granary / pit still missing, the wall houses left, and half of the Tool age's wood (market and
        second building - built the moment the Tool age comes). Tool age: the Bronze click (800 food),
        market, second building, 8 farms, the wall houses left.
        Returns dict(need_food, need_wood, gatherers, wood_n) or None (no forecast for this stage)."""
        if getattr(self, "_eco_tick", None) == self.ticks:
            return self._eco
        self._eco_tick = self.ticks
        self._eco = None
        n = len(self.s.villagers)
        if self.bronze_clicked or self.age >= 3:
            return None
        wall_left = 0
        if getattr(self, "wall_fixed_R", None) is not None and not self.wall_sealed:
            wall_left = len(self.wall_slots())
        has = lambda bt: bool(self.any_of(bt))   # noqa: E731
        if self.age == 1 and not self.tool_clicked:
            if not self.woodline_placed:
                return None                      # (until the first pit every spare villager chops)
            left = max(0, self.stone_target() - n)
            food = 500 + self.vil_cost * left
            houses_want = max(0, -(-(self.stone_target() + 2 - 4) // 4) - len(self.any_of(gs.HOUSE)))
            wood = 30 * houses_want + (0 if has(gs.GRANARY) else 120) + (0 if self.second_stone_building() else 120)
            # the next berry patch's granary once one is known (players: the 2nd granary at 6:15-7:35, 9-11 on
            # berries at the Tool click; ms5: 8:35 for want of wood)
            # (the next patch's granary is NOT added here: it raised the Stone wood need and took food workers -
            #  ms11-ms14 Tool clicks 13:12 on average against 11:55)
            # half of the wall in the Stone age, the rest in the Tool age (age6: the whole wall's 800 wood
            # in the Stone forecast put 12 on wood, 5 hunting with room for 15, Tool clicked at 12:12)
            wood += 15 * wall_left
            wood += 0.5 * ((0 if has(gs.MARKET) else 150) + (0 if has(self.second_building()) else 150))
        elif not self.bronze_clicked:
            food = 800
            wood = (0 if has(gs.MARKET) else 150) + (0 if has(self.second_building()) else 150)
            wood += 0 if has(gs.BARRACKS) else 125               # (BB opens BL / BA)
            wood += 30 * wall_left
            # the farms' wood: as many farms as the natural food left does not cover (4 farmers on wild food =
            # 4 farms fewer). Once the market stands, and already during the Tool research when the wild food
            # is nearly gone (the user's 1v4 of 14/10, Yamato: herds done, no farm wood banked at the Tool age,
            # 2 farms 1.5 minutes later, 9 farms 5.5 minutes later, Bronze clicked 7 minutes after Tool - the
            # chopper cap below keeps this from the age5 case: 18 on wood, food stuck at 131)
            wild = sum(self.site_cap.get(k, 0) for (k, _x, _y, _st) in self.sites) + self.berry_capacity()
            farms_want = max(0, min(8, 12 - wild))
            self._farms_want = farms_want
            if has(gs.MARKET) or wild <= 4:
                wood += 75 * max(0, farms_want - len(self.any_of(gs.FARM)))
        else:
            return None
        # (the user: there is always a house or a wall house to build - a little wood too many does no
        #  harm, too little is a big problem: 150 wood kept on top of the step's needs)
        wood += 150
        need_f = max(0.0, food - self.res(gs.FOOD))
        need_w = max(0.0, wood - self.res(gs.WOOD))
        busy = sum(1 for v in self.s.villagers if isinstance(self.role.get(v.id), tuple)
                   or self.role_name(v.id) in ("scout", "search", "gold") or v.id in self.task_owned())
        gatherers = max(0, n - busy)
        tf, tw = need_f / self.RATE_FOOD, need_w / self.RATE_WOOD
        if tf + tw <= 0:
            wood_n = WOOD_FLOOR
        else:
            wood_n = int(round(gatherers * tw / (tf + tw)))
        # never fewer than 4 on wood, even with wood to spare (the user); re-computed every tick, so the
        # choppers come back the moment a house / the wall / the farms need wood again
        # players at the Tool click (recordings 13/10, 16 player-games): 5-9 on wood, 17-20 on food -
        # never more than AGING_WOOD_MAX choppers before the Bronze click, whatever the wood forecast says
        # (when the farms are the food - the wild food has room for fewer than the food workers - their 75
        #  wood each is the bottleneck: up to 10 then; army1: 7 choppers, 2-58 wood, 9-12 farmers on 3-5
        #  farms, 0.25 food/s for the whole town)
        wild = sum(self.site_cap.get(k, 0) for (k, _x, _y, _st) in self.sites) + self.berry_capacity()
        wmax = AGING_WOOD_MAX if (wild >= gatherers - wood_n or not self.any_of(gs.MARKET)) else 10
        if self.age == 2 and self.any_of(gs.MARKET):
            wmax = 10        # (Tool age, the market placed: the farms' wood - army3: no farm done for 4 minutes)
        wood_n = max(min(WOOD_FLOOR, gatherers), min(wood_n, wmax, gatherers))
        self._eco = dict(need_food=need_f, need_wood=need_w, gatherers=gatherers, wood_n=wood_n,
                         eta=max(tf / max(1, gatherers - wood_n), tw / max(1, wood_n)) if gatherers else 0)
        t = self.now()
        if t - getattr(self, "_eco_say", -99) >= 30:
            self._eco_say = t
            on_food = sum(1 for v in self.s.villagers if self.role_name(v.id) in ("berry", "hunt", "farm", "berry2"))
            on_wood = sum(1 for v in self.s.villagers if self.role_name(v.id) == "wood")
            self.say("ECO step needs food %.0f wood %.0f (stock %d / %d): %d gatherers -> %d wood, %d food "
                     "(now %d wood, %d food), both in ~%.0f s" % (
                         need_f, need_w, self.res(gs.FOOD), self.res(gs.WOOD), gatherers, wood_n,
                         gatherers - wood_n, on_wood, on_food, self._eco["eta"]))
        return self._eco

    def stone_target(self):
        """Villagers to make before Tool Age: as many as there is food work for (hunting sites, berries)
        plus the 6 on wood, 2 scouts and a builder - between 16 and 22. Every villager beyond that
        costs 50 food and 20 s of the Tool Age click."""
        poor = self.pit_finished() and not self.sites and not self.lures
        full = 19 if self.vil_cost > 50 else STONE_VILLAGERS      # the user: Palmyran stops at 19 (75 food each)
        if not self.pit_finished():
            return full
        return min(full, POOR_VILLAGERS) if poor and not self.food_left() else full

    def tc_idle(self, why):
        """Accounting of TC time not spent training (shown in the STAT line)."""
        t = self.now()
        last = getattr(self, "_tci_t", t)
        self._tci_t = t
        acc = self.__dict__.setdefault("tc_idle_acc", {})
        acc[why] = acc.get(why, 0.0) + (t - last)

    def town_center(self):
        tc = self.tc()
        if not tc:
            return
        nvil = len(self.s.villagers)
        t = self.now()
        if self.t_vil25 is None and nvil >= self.stone_target():
            self.t_vil25 = t
            self.say("DIAG stone villagers (%d) reached at %.0f s with food %d" % (nvil, t, self.res(gs.FOOD)))
        if self.r.producing(tc):
            self.tc_idle("busy")
            # stuck queue: "producing" for long without a new villager (seen once: food 50, nothing came out)
            st = getattr(self, "_tc_watch", None)
            if st is None or st[1] != nvil:
                self._tc_watch = (t, nvil)
            elif self.age == 1 and not self.tool_clicked and t - st[0] > 35:
                act = self.r.action(tc)
                self.say("WATCHDOG TC busy %.0f s without a villager (action %s, food %d, headroom %.0f, houses %d): stopping it" % (
                    t - st[0], act, self.res(gs.FOOD), self.res(gs.HEADROOM), len(self.any_of(gs.HOUSE))))
                self.g.stop([tc])
                self._tc_watch = (t, nvil)
                self.queued = False
            # the stone target reached and the Tool Age affordable while a villager still trains: stop it,
            # the Tool click comes next tick (players click the moment the 500 food is there)
            self.tool_second_building(nvil)
            if (self.age == 1 and not self.tool_clicked and nvil >= self.stone_target() and self.complete(gs.GRANARY)
                    and self.second_stone_building() and self.can_afford(food=500)
                    and t - self.last_train > 2):
                self.g.stop([tc])
                self.last_train = t
                self.say("TC stopped: %d villagers and 500 food, the Tool Age comes first" % nvil)
            # keep the next villager queued behind the one in training (players never let the TC idle)
            if (self.age == 1 and not self.tool_clicked and nvil + 2 <= self.stone_target()
                    and t - self.last_train > 6 and not getattr(self, "queued", False)
                    and self.res(gs.HEADROOM) >= 2 and self.can_afford(food=2 * self.vil_cost)):
                self.g.train(tc, gs.VILLAGER)
                self.queued = True
                self.last_train = t
            return
        self.queued = False
        self._tc_watch = None            # (the busy-watch counts only one uninterrupted production)
        # an age-up the game did not take (not enough food at that moment...): the TC is not researching
        for flag, need_age, name in (("tool_clicked", 1, "Tool"), ("bronze_clicked", 2, "Bronze")):
            if getattr(self, flag) and self.age == need_age and 8 < t - self.last_train < 100:
                setattr(self, flag, False)
                self.say("%s Age click did not start (TC idle): clicking again when possible" % name)
        if t - self.last_train < 1.5:
            self.tc_idle("busy")
            return
        if (not self.tool_clicked and self.age == 1 and nvil >= self.stone_target()
                and self.complete(gs.GRANARY)
                and self.second_stone_building() and self.can_afford(food=500)):
            self.g.research(tc, gs.TECH_TOOL_AGE)
            self.tool_clicked = True
            self.last_train = t
            self.say("Tool Age clicked with %d villagers" % nvil)
            if demo_dump.enabled():
                self.wall_shot("tool")
            return
        A = self.tactics
        if (A and A.get("want_iron") and self.age == 3 and not getattr(self, "iron_clicked", False)
                and self.complete(gs.TEMPLE) and self.complete(gs.SIEGE_WORKSHOP) and self.can_afford(food=1000, gold=800)):
            self.g.research(tc, gs.TECH_IRON_AGE)
            self.iron_clicked = True
            self.last_train = t
            self.say("Iron Age clicked (the user: when Bronze does not end it)")
            return
        if (not self.bronze_clicked and self.age == 2 and self.complete(gs.MARKET) and self.complete(self.second_building())
                and self.can_afford(food=800)):
            self.g.research(tc, gs.TECH_BRONZE_AGE)
            self.bronze_clicked = True
            self.last_train = t
            self.say("Bronze Age clicked")
            if demo_dump.enabled():
                self.wall_shot("bronze")
            self.bronze_click_t = t
            return
        if self.age == 1 and not self.tool_clicked:
            want = nvil < self.stone_target()
        elif self.age == 1 or (self.age == 2 and not self.bronze_clicked):
            # Tool Age researching / Tool Age: no villagers - except a poor-map start that clicked Tool
            # at 20: it still makes its 25 (the user's number) when there is food to spare
            # (only from food beyond the Bronze click's 800 - ffa3: Tool clicked at 20, five villagers made in the
            #  Tool age took 250 food and the Bronze click came 5:44 after the Tool age)
            want = nvil < self.stone_target() and self.res(gs.FOOD) >= 800 + 150
        else:
            want = nvil < MAX_VILLAGERS
            if self.age == 2:
                # Bronze researching: the food is kept for the scout and the first soldiers (the user:
                # the army is the first thing in Bronze)
                want = want and self.res(gs.FOOD) >= 400
            ut = self.unit_tech_needed() if self.age >= 3 else None
            if ut is not None:
                # the user: an archer town banks the Wheel's 175 food + 75 wood (Improved Bow: 140 + 80) the
                # moment Bronze is in - no villager until it is started (age 1v4: the Assyrian bot made
                # villagers first, its chariot archers came late)
                c = K.TECHS[ut][3]
                if not self.can_afford(food=c.get("food", 0) + self.vil_cost, wood=c.get("wood", 0)):
                    want = False
            if self.age >= 3:
                # the user: the army first. Every military building of ours (stables, ranges, academies)
                # busy, or the idle ones still paid for, before a villager; once 8 soldiers are out the TC
                # takes every 3rd chance anyway
                mil_b = [b for bt in (gs.STABLE, gs.ARCHERY_RANGE, gs.ACADEMY) for b in self.complete(bt)]
                idle_b = [b for b in mil_b if not self.r.producing(b)]
                self._tc_turn = getattr(self, "_tc_turn", 0) + 1
                army_n = len(self.military())
                if idle_b and not self.can_afford(food=50 + 70 * len(idle_b)):
                    if army_n < 8 or self._tc_turn % 3:
                        want = False
                # (a building busy with a unit still needs the next one's food: with fewer than 8 soldiers
                #  the villager only when a unit per military building stays paid - army2: the stable always
                #  busy, the TC took every 50 food, 25 -> 37 villagers and 2 camels in 10 minutes)
                if mil_b and army_n < 8 and not self.can_afford(food=self.vil_cost + 70 * len(mil_b)):
                    want = False
        if not want:
            self.tc_idle("done")
            return
        if self.res(gs.HEADROOM) < 1:
            self.tc_idle("pop")
            return
        if (self.can_afford_unit(food=self.vil_cost) if (self.age >= 3 and len(self.s.villagers) >= 35)
                else self.can_afford(food=self.vil_cost)):
            self.g.train(tc, gs.VILLAGER)
            self.last_train = t
            self.trained_tick = self.ticks
            self.s.res[gs.FOOD] -= self.vil_cost
            self.tc_idle("busy")
        else:
            self.tc_idle("food")

    # ================================================================ villagers
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
        sub = []
        for step in (self.granaries, self.storage_pits, self.hunting_plan, self.assign_leads):
            t1 = time.time()
            step()
            sub.append((time.time() - t1, step.__name__))
        t_work = time.time()
        counts = {}
        for i, v in enumerate(vs):
            r = self.role.get(v.id)
            if isinstance(r, tuple):            # building or a hunting job
                if r[0] == "build":
                    continue
            if v.id in self.defenders or v.id in self.helpers or v.id in self.repairers                     or v.id in self.__dict__.get("lion_helpers", {}):
                continue                        # chasing an enemy scout / killing a lured elephant / a lion
            if self.now() < self.retreat_until.get(v.id, 0):
                continue                        # running from an enemy soldier (self_defence)
            d = "hunt" if v.id in self.leads else self.desired_role(i, v)
            if d is None:
                d = self.allocate(v, counts)
            counts[d] = counts.get(d, 0) + 1
            changed = r is not None and r != d and not self.recent(v.id, within=5)
            if r != d:
                self.role[v.id] = d
            t1 = time.time()
            self.work(v, d, force=changed)
            if time.time() - t1 > 0.3:
                sub.append((time.time() - t1, "work:%s" % d))
        sub.append((time.time() - t_work, "all work"))
        if sum(x for x, n in sub if n != "all work") + sub[-1][0] > 0.8:
            sub.sort(reverse=True)
            self.say("SLOW villagers: " + ", ".join("%s %.2f" % (n, x) for x, n in sub[:5]))

    def desired_role(self, idx, v):
        if idx < 6:
            if self.berry_clusters() and (self.berry_capacity() > 0 or not self.any_of(gs.GRANARY)):
                return "berry"
            if not self.any_of(gs.GRANARY):
                return "search"             # circles around the TC until the first bush is seen
            return None
        if idx in (6, 8) and self.food_items() < FOOD_ITEMS_WANTED                 and self.now() - (self.start_time or 0) < 720 and not self.tool_clicked:
            return "scout"
        if idx == 7 and not self.any_of(gs.STORAGE_PIT):
            return "wood"
        return None

    def wood_target(self):
        """Villagers the wood line needs now."""
        if not self.woodline_placed:
            return 99                                    # until the first pit every spare villager chops
        if self.age == 1 and not self.tool_clicked:
            return 6                                     # exactly 6 at the first pit, the rest on food
        if not self.bronze_clicked:
            need = (0 if self.any_of(gs.MARKET) else 150) + (0 if self.any_of(self.second_building()) else 150) + 60
            if self.complete(gs.MARKET) or self.any_of(gs.MARKET):
                # farms right after the market (4 at least - fix1v2b: the Persian bot had 7 choppers,
                # 20-90 wood, one farm finished 120 s after the market)
                need += 75 * max(0, 4 - len(self.any_of(gs.FARM)))
            if self.complete(gs.MARKET) and not self.food_left():
                need += 150                              # more farms are coming
            wood = self.res(gs.WOOD)
            return 10 if wood < need - 150 else (7 if wood < need else 5)
        wood = self.res(gs.WOOD)
        if self.age >= 3:
            return 4 if wood > 500 else (6 if wood > 200 else 8)   # farms, houses, stables
        return 4 if wood > 600 else (6 if wood > 250 else 8)

    def food_left(self):
        """Natural food still worth sending villagers to (hunts or berries)."""
        return bool(self.sites) or bool(self.berry_clusters())

    def berry_range(self):
        """How far a berry patch may be for a granary: 22 tiles, or 60 when nothing closer is left
        to eat (no hunt, no berries next to a granary or the TC)."""
        if getattr(self, "_br_tick", None) == self.ticks:
            return self._br
        self._br_tick, self._br = self.ticks, BERRY_NEAR
        if not self.bronze_clicked and (self.far_food_open() or self.food_emergency or self.food_short):
            self._br = 999                               # (the user: a patch anywhere while aging, nearest first)
            return self._br
        if self.food_emergency or self.food_short:
            self._br = 999 if self.food_desperate else BERRY_POOR
            return self._br
        if not self.sites and self.pit_finished():
            grans = self.complete(gs.GRANARY)
            tc = self.tc()
            near = False
            for cx, cy, items in self.berry_clusters():
                if any(math.hypot(g0.x - cx, g0.y - cy) < 8 for g0 in grans) or                         (tc and math.hypot(cx - tc.x, cy - tc.y) <= BERRY_NEAR):
                    near = True
                    break
            if not near:
                self._br = BERRY_POOR
        return self._br

    def site_food_left(self, key):
        """Food still to take at a hunting site: carcasses' meat, live gazelles of its herd (150 each), a
        live elephant being killed (300). None when unknown."""
        if key[0] == "meat":
            return sum(m.amount for m in self.meat_groups.get(key, []))
        if key[0] == "herd" and key[1] in self.herds:
            h = self.herds[key[1]]
            return sum(c.amount for c in self.herd_carcasses(h)) + 150.0 * len(self.herd_live(h))
        if key[0] == "lure":
            e = self.gaia_by_id(key[1])
            if e is not None and e.hp > 0:
                return 300.0
            L = self.lures.get(key[1])
            if L is not None:
                car = [m for m in self.meat() if m.type == gs.DEAD_ELEPHANT and m.dist(L.x, L.y) < 6]
                if car:
                    return sum(m.amount for m in car)
        return None

    def far_food_open(self):
        return bool(getattr(self, "far_food", False))

    def berry_capacity(self):
        cap = 0
        grans = self.complete(gs.GRANARY)
        tc = self.tc()
        all_grans = self.any_of(gs.GRANARY)
        first_gran = min(all_grans, key=lambda g0: g0.id) if all_grans else None
        for cx, cy, items in self.berry_clusters():
            # (70 food a villager at least - the user: fewer pickers on an almost empty patch; never on the
            #  first patch, its six stay to the last bush - the user)
            first_patch = (first_gran is not None and math.hypot(first_gran.x - cx, first_gran.y - cy) < 8) or                 (tc is not None and math.hypot(cx - tc.x, cy - tc.y) < 8)
            fcap = 6 if first_patch else max(1, int(sum(self.bush_food(b) for b in items) // FOOD_PER_VILLAGER))
            if any(math.hypot(g0.x - cx, g0.y - cy) < 8 for g0 in grans) or (not self.any_of(gs.GRANARY)):
                cap += min(6, len(items), fcap)
            elif tc and math.hypot(cx - tc.x, cy - tc.y) <= self.berry_range():
                cap += min(6, len(items), fcap)          # waits at the patch until its granary is built
        return cap

    def allocate(self, v, counts):
        wood_n = counts.get("wood", 0)
        gold_want = (2 + GOLD_PER_STABLE * max(1, len(self.complete(gs.STABLE)))) if self.age >= 3 else 6
        if self.bronze_clicked and counts.get("gold", 0) < gold_want and self.known_gold():
            return "gold"
        leads = sum(1 for (k, x, y, st) in self.sites if st in ("provoke", "run", "push"))
        if leads and len(self.s.villagers) >= 7 and counts.get("hunt", 0) < leads:
            return "hunt"                            # one lurer / pusher per elephant / gazelle, before anything else
        tc = self.tc()
        home_meat = tc and any(st in ("eat", "pushed", "kill") and math.hypot(x - tc.x, y - tc.y) <= 12
                               for (k, x, y, st) in self.sites if k[0] in ("meat", "herd", "lure"))
        if home_meat and wood_n >= 2 and counts.get("hunt", 0) < self.hunt_capacity:
            return "hunt"                            # meat at the TC first (new villagers come out right there)
        if not self.woodline_placed and wood_n >= EARLY_WOOD and counts.get("hunt", 0) < self.hunt_capacity:
            return "hunt"                            # before the first pit: elephants / gazelles brought home
        if wood_n < self.wood_target():
            return "wood"
        if self.age >= 2 and counts.get("farm", 0) < len(self.complete(gs.FARM)):
            return "farm"
        if counts.get("hunt", 0) < self.hunt_capacity:
            return "hunt"
        if counts.get("berry", 0) < self.berry_capacity():
            return "berry"
        if self.age >= 2 and self.complete(gs.MARKET):
            return "farm"
        if (self.age == 1 and not self.tool_clicked and self.woodline_placed and self.res(gs.WOOD) > 250
                and counts.get("scout", 0) < 4 and (self.food_items() < FOOD_ITEMS_WANTED or self.food_emergency)):
            return "scout"                          # no food to send them to: look for more
        if self.woodline_placed and wood_n >= WOOD_HARD_CAP and counts.get("scout", 0) < 6 and self.age <= 2:
            return "scout"                          # players never put more than ~7 on wood: find food instead
        return "wood"

    def known_gold(self):
        return [o for o in self.s.gaia if o.type == gs.GOLD_MINE and o.amount > 0]

    # ---------------------------------------------------------------- per-role work
    def work(self, v, role, force=False):
        if v.id in self.held:
            return                                      # full load, waiting for its dropsite (hold_far_loads)
        if role == "scout":
            # while aging: the unexplored ground nearest home first, then further out (the user)
            return self.scout(v, near_home=not self.bronze_clicked)
        if role == "search":
            return self.search(v)
        if role == "hunt":
            return self.work_hunt(v, force)
        if role == "farm":
            return self.work_farm(v, force)
        if not force and not self.idle(v):
            return
        if role == "berry":
            t = self.nearest_berry(v)
            if t:
                if self.idle_reorder(v, t):
                    t = self.nearest_berry(v)
                    if not t:
                        return self.work_wood(v)
                return self.order([v], t)
            w = self.berry_wait_spot()
            if w:                                   # a patch without its granary yet: wait there for the wood
                if v.dist(*w) > 3:
                    self.move([v], *w)
                return
            return self.search(v)
        if role == "wood":
            return self.work_wood(v)
        if role == "gold":
            mines = self.known_gold()
            mines = [m for m in mines if not self.bad_target(m)]
            if mines:
                anchor = self.pit_near(gs.GOLD_MINE) or (v.x, v.y)
                t = min(mines, key=lambda o: o.dist(*anchor))
                self.idle_reorder(v, t)
                return self.order([v], t)
            return self.work_wood(v)
        if role == "farm":
            return self.work_farm(v)
        return self.work_wood(v)

    def waiting_hunter(self, v):
        """A hunter whose site is a lure on its way home or a herd being pushed: standing still with
        nothing in hand is its job (it waits for the elephant / the herd at the home)."""
        key = self.hunt_site.get(v.id)
        if not key:
            return False
        st = next((st for (k, _x, _y, st) in self.sites if k == key), None)
        return st in ("provoke", "run", "push", "pushed")

    def hold_far_loads(self):
        """The user: a berry / meat villager whose way back to a dropsite is longer than 12 tiles and whose
        granary / pit is not there yet gathers its load (10) and waits by the food until the dropsite stands
        - no 30-tile walks with 10 food. Released once a dropsite of its kind is within 12 tiles of the
        spot (it then gathers on and drops there), or after 180 s."""
        t = self.now()
        tc = self.tc()
        if not tc:
            return
        owned = self.task_owned()
        spots = self.__dict__.setdefault("_gather_spot", {})
        grans = self.complete(gs.GRANARY)
        pits = self.complete(gs.STORAGE_PIT)

        def drop_d(x, y, kind):
            ds = [tc] + (grans if kind == "berry" else pits)
            return min(max(0.0, d.dist(x, y) - 1.5) for d in ds)
        by_ptr = None
        alive = set()
        choppers = sum(1 for o in self.s.villagers if self.role_name(o.id) == "wood")
        can_come = bool(self.any_of(gs.GRANARY)) and (self.res(gs.WOOD) >= 120 or choppers >= 2)
        brange = self.berry_range()

        def site_ok(x, y, kind):
            """A dropsite will ever be built there (civ1: four pickers of a 2-bush patch 31 tiles out waited
            minutes for a granary - granaries() never builds one for < 3 bushes or past berry_range)."""
            # (civ1: seven hunters held 180 s for a herd pit that the Tool-age wood reserve - market,
            #  second building, BB - never let be paid, right through the Tool research)
            if kind == "berry":
                if self.pending_of(gs.GRANARY):
                    return True
                n = sum(1 for g in self.s.gaia if g.type == gs.FORAGE and g.amount > 0 and g.dist(x, y) < 6)
                d = math.hypot(x - tc.x, y - tc.y)
                return n >= 3 and d <= brange and (self.tool_wood_free(120) or n >= 4 and d > 15)
            if self.pending_of(gs.STORAGE_PIT):
                return True
            food = sum(g.amount for g in self.s.gaia if g.amount > 0 and g.dist(x, y) < 6
                       and (g.cls == gs.CLS_DEAD and g.type in gs.MEAT or g.type == gs.GAZELLE))
            return food >= 150 and self.tool_wood_free(120)
        for v in self.s.villagers:
            alive.add(v.id)
            name = self.role_name(v.id)
            if name not in ("berry", "berry2", "hunt") or v.id in owned or isinstance(self.role.get(v.id), tuple):
                self.held.pop(v.id, None)
                continue
            act = self.r.action(v)
            tgt_ptr = act[1] if act else None
            if tgt_ptr and v.amount < 9.5:
                if by_ptr is None:
                    by_ptr = {g.ptr: g for g in self.s.gaia}
                o = by_ptr.get(tgt_ptr)
                if o is not None and (o.type == gs.FORAGE or o.cls == gs.CLS_DEAD or o.type == gs.GAZELLE):
                    spots[v.id] = (o.x, o.y, "berry" if o.type == gs.FORAGE else "meat")
            sp = spots.get(v.id)
            if sp is None:
                continue
            x, y, kind = sp
            if v.id in self.held:
                hx, hy, hk, since = self.held[v.id]
                if drop_d(hx, hy, hk) <= 12 or t - since > 180 or not can_come or not site_ok(hx, hy, hk):
                    del self.held[v.id]                  # a dropsite came (or too long): back to work
                    food = [g for g in self.s.gaia if g.amount > 0 and g.dist(hx, hy) < 4 and
                            (g.type == gs.FORAGE if hk == "berry" else (g.cls == gs.CLS_DEAD and g.type in gs.MEAT))]
                    if food:
                        self.order([v], min(food, key=lambda g: g.dist(v.x, v.y)))
                    self.say("HOLD villager #%d released (%s)" % (v.id, "dropsite near" if t - since <= 180 else "waited 180 s"))
                continue
            # only while the dropsite can come: a granary already stands (never before the first one) and
            # the wood is there or is being chopped (cr2v2b: 110 wood, nobody chopping, six pickers waiting
            # for a granary that could never be paid - 7 villagers and 0 food for the whole game)
            if can_come and v.amount >= 9.5 and drop_d(x, y, kind) > 12 and v.dist(x, y) < 5 and site_ok(x, y, kind):
                self.held[v.id] = (x, y, kind, t)
                self.g.stop([v])
                if t - getattr(self, "_hold_say", -99) > 20:
                    self._hold_say = t
                    self.say("HOLD villager #%d (%s) full at (%.0f,%.0f): %.0f tiles to a dropsite - waits for the %s"
                             % (v.id, name, x, y, drop_d(x, y, kind), "granary" if kind == "berry" else "pit"))
        for vid in [k for k in self.held if k not in alive]:
            del self.held[vid]

    def check_gatherers(self):
        """The user: every villager checked, often. A gatherer (berries, meat, farm, wood, gold) whose
        carried amount has not changed for 45 s is not working, busy or not (age4: 9-13 'meat eaters'
        for 120 s and the food did not move by one): its target is skipped for 120 s, its job dropped
        (60 s ban) so the allocator gives it another one, and the line says where it stood."""
        t = self.now()
        if t - getattr(self, "_gath_t", -99) < 5:
            return
        self._gath_t = t
        track = self.__dict__.setdefault("_gath", {})
        owned = self.task_owned()
        seen = set()
        stuck = []
        for v in self.s.villagers:
            r = self.role.get(v.id)
            name = self.role_name(v.id)
            if name not in ("berry", "berry2", "hunt", "farm", "wood", "gold") or isinstance(r, tuple)                     or v.id in owned or v.id in self.defenders or v.id in self.helpers or v.id in self.repairers                     or v.id in self.held or (name == "hunt" and self.waiting_hunter(v)):
                track.pop(v.id, None)
                continue
            seen.add(v.id)
            amt = round(v.amount, 2)
            rec = track.get(v.id)
            # (walking to a far patch is work too - age5: 108 'stuck' reports, most of them villagers on
            #  their way: only one standing within 3 tiles of where the count started is stuck)
            if rec is None or rec[0] != amt or rec[2] != name or math.hypot(v.x - rec[3], v.y - rec[4]) > 3:
                track[v.id] = (amt, t, name, v.x, v.y)
                continue
            if t - rec[1] >= 45:
                stuck.append((v, t - rec[1]))
                track[v.id] = (amt, t, name, v.x, v.y)
        for vid in [k for k in track if k not in seen]:
            del track[vid]
        for v, dt in stuck[:4]:
            act = self.r.action(v)
            tgt = None
            if act and act[1]:
                tgt = next((o for o in self.s.gaia if o.ptr == act[1]), None) or                       next((o for o in self.s.mine if o.ptr == act[1]), None)
            if tgt is not None and tgt.type != gs.FARM:
                self.__dict__.setdefault("_bad_targets", {})[tgt.ptr] = t + 120
            name = self.role_name(v.id)
            self.say("WORKDBG villager #%d (%s) at (%.0f,%.0f) carrying %.1f for %.0f s, action %s on %s: job dropped"
                     % (v.id, name, v.x, v.y, v.amount, dt, act[0] if act else None,
                        ("%s at (%.0f,%.0f)" % (tgt.name, tgt.x, tgt.y)) if tgt is not None else "-"))
            key = self.hunt_site.pop(v.id, None)
            self.role.pop(v.id, None)
            self.__dict__.setdefault("role_ban", {})[v.id] = (name, t + 60)
            if key is not None:
                # two stuck hunters of one site within a minute: the site itself goes for 120 s
                sb = self.__dict__.setdefault("_site_stuck", {})
                hits = [x for x in sb.get(key, []) if t - x < 60] + [t]
                sb[key] = hits
                if len(hits) >= 2:
                    self.__dict__.setdefault("_site_ban", {})[key] = t + 120
                    self.say("WORKDBG hunt site %s: %d stuck hunters - left alone for 120 s" % (key, len(hits)))

    def free_trapped(self):
        """A villager idle 60+ s on one spot whose walkable area is tiny is shut in (the user: villagers
        locked inside the wall never deleted a house to get out; age1: one stood 500 s at (82,34) through
        four roles). Our nearest house next to its pocket is deleted - the wall puts it back later."""
        t = self.now()
        if t - getattr(self, "_trap_t", -99) < 20:
            return
        self._trap_t = t
        isince = self.__dict__.get("_idle_since", {})
        pm = self.pm
        W = pm.W
        for v in self.s.villagers:
            rec = isince.get(v.id)
            if not rec or t - rec[0] < 60 or v.id in self.task_owned():
                continue
            x, y = int(v.x), int(v.y)
            start = [(xx, yy) for xx in range(x - 1, x + 2) for yy in range(y - 1, y + 2) if pm.passable(xx, yy)]
            if not start:
                continue
            dist = pm.bfs(start, max_cost=10 * 40)
            reach = [(i % W, i // W) for i, d in enumerate(dist) if d >= 0]
            if len(reach) >= 150:
                continue                                 # free to walk: idle for another reason
            houses = [h for h in self.s.mine if h.type == gs.HOUSE and h.hp > 0]
            if not houses:
                continue

            def gap(h):
                return min(abs(h.x - rx) + abs(h.y - ry) for rx, ry in reach)
            h = min(houses, key=gap)
            if gap(h) > 3.5:
                continue
            try:
                self.g.delete(h)
            except Exception as e:  # noqa: BLE001
                self.say("trapped: delete failed: %r" % (e,))
                return
            isince.pop(v.id, None)
            self.say("TRAPPED villager #%d (%s) at (%.0f,%.0f) idle %.0f s in a %d-tile pocket: house #%d at (%.0f,%.0f) deleted"
                     % (v.id, self.role_name(v.id), v.x, v.y, t - rec[0], len(reach), h.id, h.x, h.y))
            return                                       # one at a time

    def bad_target(self, o):
        return self.now() < self.__dict__.get("_bad_targets", {}).get(o.ptr, -1)

    def idle_reorder(self, v, tgt):
        """A villager ordered to the same target again and again while it stays idle cannot reach it
        (fix1v2b: 6 berry pickers stood by their granary for 1 100 s, ordered to bushes they could not
        get to, the patch never shrank): after 4 idle orders in 15+ s the target is skipped for 180 s.
        Returns True when the target was just given up."""
        t = self.now()
        io = self.__dict__.setdefault("_idle_orders", {})
        rec = io.get(v.id)
        if rec is None or rec[0] != tgt.ptr or t - rec[2] > 60:
            io[v.id] = (tgt.ptr, 1, t, v.x, v.y)
            return False
        moved = math.hypot(v.x - rec[3], v.y - rec[4]) > 2.0
        if moved:
            io[v.id] = (tgt.ptr, 1, t, v.x, v.y)
            return False
        n = rec[1] + 1
        io[v.id] = (tgt.ptr, n, rec[2], rec[3], rec[4])
        if n >= 4 and t - rec[2] >= 15:
            self.__dict__.setdefault("_bad_targets", {})[tgt.ptr] = t + 180
            del io[v.id]
            self.say("IDLEDBG villager #%d (%s) at (%.0f,%.0f) idle after %d orders to %s at (%.0f,%.0f) in %.0f s: "
                     "target skipped for 180 s" % (v.id, self.role_name(v.id), v.x, v.y, n, tgt.name, tgt.x, tgt.y, t - rec[2]))
            return True
        return False

    def search(self, v):
        """Find the first berries: each early villager heads for the nearest unexplored ground in its
        own direction (the search grows outwards like a circle, never through known ground)."""
        tc = self.tc()
        if not tc:
            return
        if self.flee_lion(v):
            return
        if self.berry_found_at:
            bx, by = self.berry_found_at
            if v.dist(bx, by) > 3 and not self.recent(v.id, within=4):
                self.move([v], bx, by)          # everybody to the first bush; the patch reveals itself
            return
        self.scout(v, local=True, max_r=34, near_home=True)

    def tree_capacity(self, t):
        return 2 if t.amount >= 60 else 1

    def work_wood(self, v):
        """Before the first pit: trees close to the TC (3 x 75 or 6 x 40, 2 x 40 = 1 x 75);
        always spread the villagers so no tree gets more than its share."""
        trees = [o for o in self.s.gaia if o.kind == gs.KIND_TREE and o.amount > 0] or                 [o for o in self.s.gaia if o.kind == gs.KIND_TREE]
        if not trees:
            return self.scout(v)
        pits = self.complete(gs.STORAGE_PIT) if self.woodline_placed else []
        tc = self.tc()
        anchors = [(p.x, p.y) for p in pits] or ([(tc.x, tc.y)] if tc else [(v.x, v.y)])
        a = self.r.action(v)
        mine = a[1] if a else None
        best = None
        for t in trees:
            n = self.on_target.get(t.ptr, 0) - (1 if t.ptr == mine else 0)
            full = n >= self.tree_capacity(t)
            d = min(math.hypot(t.x - ax, t.y - ay) for ax, ay in anchors) + 0.3 * t.dist(v.x, v.y)
            key = (1 if full else 0, n if full else 0, d)
            if best is None or key < best[0]:
                best = (key, t)
        self.order([v], best[1])

    def nearest_berry(self, v):
        """One villager per bush first; a second villager only when every bush already has one."""
        bushes = [o for o in self.s.gaia if o.type == gs.FORAGE and o.amount > 0]
        if not bushes:
            return None
        grans = self.any_of(gs.GRANARY)
        if grans:
            tc = self.tc()
            covered = [b for b in bushes if any(b.dist(g0.x, g0.y) < 8 for g0 in grans)
                       or (tc and b.dist(tc.x, tc.y) < 8)]
            if covered:
                bushes = covered
            elif self.berry_wait_spot() is not None:
                return None                         # wait at the new patch for its granary
        a = self.r.action(v)
        mine = a[1] if a else None
        trips = self.berry_trips()

        def load(b):
            n = self.on_target.get(b.ptr, 0)
            return n - 1 if b.ptr == mine else n

        bushes = [b for b in bushes if not self.bad_target(b)]
        if not bushes:
            return None

        def cost(b):
            # the walk bush -> food dropsite (tiles, real path) first; a shared bush costs SHARE_TILES
            # per villager already on it (one per bush when the next free one is not much further),
            # never more than 3 on one bush; the villager's own walk there only breaks ties
            n = load(b)
            if n >= BERRY_MAX_PER_BUSH:
                return 1e9
            trip = trips.get(b.ptr)
            if trip is None:
                trip = 2.0 * b.dist(v.x, v.y) + 30.0           # (no path known: last)
            return trip + BERRY_SHARE_TILES * n + 0.15 * b.dist(v.x, v.y)
        best = min(bushes, key=cost)
        return best if cost(best) < 1e9 else None

    def berry_trips(self):
        """{bush ptr: tiles of the walk from the bush to the nearest food dropsite (TC / granary)} along
        real paths (round trees, bushes, buildings), from one search out of the dropsites' edges; cached
        while the dropsites stay the same (30 s at most). An unreachable bush is left out."""
        tc = self.tc()
        drops = [g0 for g0 in self.complete(gs.GRANARY)] + ([tc] if tc else [])
        key = (tuple(sorted(d.id for d in drops)), int(self.now() // 30))
        cache = getattr(self, "_berry_trips", None)
        if cache is not None and cache[0] == key:
            return cache[1]
        pm = self.pm
        W = pm.W
        src = []
        for d in drops:
            x0, y0 = int(d.x - 1.5), int(d.y - 1.5)
            src += [(xx, yy) for (xx, yy) in pm.ring_tiles(x0, y0, x0 + 3, y0 + 3) if pm.passable(xx, yy)]
        out = {}
        if src:
            dist = pm.bfs(src, max_cost=10 * 45)
            for b in self.s.gaia:
                if b.type != gs.FORAGE or b.amount <= 0:
                    continue
                best = None
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                    tx, ty = int(b.x) + dx, int(b.y) + dy
                    if 0 <= tx < W and 0 <= ty < pm.H:
                        dd = dist[ty * W + tx]
                        if dd >= 0 and (best is None or dd < best):
                            best = dd
                if best is not None:
                    out[b.ptr] = best / 10.0
        self._berry_trips = (key, out)
        return out

    def berry_wait_spot(self):
        """The nearest berry patch (<= 22 tiles) that has no granary yet, where berry villagers wait
        (at most WAIT_LIMIT seconds per patch, then they gather and walk)."""
        tc = self.tc()
        grans = self.any_of(gs.GRANARY)
        if not tc or not grans:
            return None
        t = self.now()
        best = None
        for cx, cy, items in self.berry_clusters():
            if any(math.hypot(g0.x - cx, g0.y - cy) < 8 for g0 in grans):
                continue
            if math.hypot(cx - tc.x, cy - tc.y) < 8:
                continue                            # next to the TC: no granary needed
            d = math.hypot(cx - tc.x, cy - tc.y)
            key = (int(cx) // 6, int(cy) // 6)
            t0 = self.wait_since.setdefault(("berry", key), t)
            if t - t0 > WAIT_LIMIT and not self.pending_of(gs.GRANARY):
                continue
            if d <= self.berry_range() and (best is None or d < best[0]):
                best = (d, cx, cy)
        return (best[1], best[2]) if best else None

    def pit_near(self, resource_type):
        pits = self.any_of(gs.STORAGE_PIT)
        if not pits:
            return None
        if resource_type is None:
            return (pits[-1].x, pits[-1].y)
        res = [o for o in self.s.gaia if o.type == resource_type]
        if not res:
            return None
        best = min(pits, key=lambda p: min(r.dist(p.x, p.y) for r in res))
        return (best.x, best.y)

    # ---------------------------------------------------------------- farms
    def work_farm(self, v, force=False):
        """One farmer per farm: a free farm if there is one, else build one (never more farms than
        farmers waiting for one). Looked at again every few seconds even while the villager is busy
        elsewhere (a farmer chopping wood for want of a farm comes back as soon as one is free)."""
        farms = self.complete(gs.FARM)
        act0 = self.r.action(v)
        on_farm = bool(act0 and act0[1] and any(f.ptr == act0[1] for f in farms))
        building = isinstance(self.role.get(v.id), tuple)
        if not force and not self.idle(v) and (on_farm or building or self.recent(v.id, ("farmchk",), within=5)):
            return
        self.mark([v], ("farmchk",))
        # who works which target, read ONCE per tick (it was read for every villager by every farmer:
        # ~14 000 memory reads a tick with 60 villagers - half of a 1-4 s tick in the user's 1v7)
        occ = self.target_counts()
        act = self.r.action(v)
        mine = act[1] if act and act[1] else None
        taken = {ptr for ptr, n in occ.items() if n - (1 if ptr == mine else 0) > 0}
        if mine and any(f.ptr == mine for f in farms) and occ.get(mine, 0) - 1 == 0:
            return                                   # already alone on its farm
        free = [f for f in farms if f.ptr not in taken and f.amount > 0]
        if free:
            f = min(free, key=lambda f: f.dist(v.x, v.y))
            # (the count is read once a tick: the farm is marked taken at once, or the next farmer of the
            #  same tick picks it too - age5: two farmers on one farm, both standing 49 s with nothing)
            if mine:
                occ[mine] = max(0, occ.get(mine, 0) - 1)
            occ[f.ptr] = occ.get(f.ptr, 0) + 1
            return self.order([v], f)
        farmers = sum(1 for o in self.s.villagers if self.role_name(o.id) == "farm")
        if farmers <= len(farms) + len(self.pending_of(gs.FARM)):
            return self.work_wood(v)                 # every farm has its farmer already
        max_pending = 6 if self.res(gs.WOOD) < 400 else 12
        if getattr(self, "wall_fixed_R", None) is not None and not self.wall_sealed and self.res(gs.WOOD) < 250                 and self.bronze_clicked:
            max_pending = 2                          # the wall's houses first (the user: sealed before anything) -
                                                     # once Bronze is clicked; before it the farms are the click
        # the Bronze buildings come first: their wood is kept back from the farms (age3: the stable's
        # placement failed once, the farms took every 75 wood after it, the stable never came - 1 000
        # food banked and no Bronze click for 7 minutes)
        reserve = 0
        if self.age == 2 and not self.bronze_clicked:
            reserve += 0 if self.any_of(gs.MARKET) else 150
            reserve += 0 if self.any_of(self.second_building()) else 150
        if self.complete(gs.MARKET) and self.can_afford(wood=75 + reserve) and len(self.pending_of(gs.FARM)) < max_pending:
            spot = self.farm_spot(v)
            if spot:
                self.start_build(gs.FARM, spot, [v], "(farm)")
                self.farms_built = getattr(self, "farms_built", 0) + 1
                return
        return self.work_wood(v)

    def target_counts(self):
        """{target ptr: number of our villagers whose current action targets it}, once per snapshot."""
        key = id(self.s)
        cache = getattr(self, "_tc_cache", None)
        if cache is not None and cache[0] == key:
            return cache[1]
        occ = collections.Counter()
        for o in self.s.villagers:
            a = self.r.action(o)
            if a and a[1]:
                occ[a[1]] += 1
        self._tc_cache = (key, occ)
        return occ

    def farm_spot(self, v):
        """A farm one house foundation (2 tiles) away from a granary or the TC, reachable by a short
        walk, never closing the TC's exits."""
        tc = self.tc()
        drops = [g0 for g0 in self.complete(gs.GRANARY) if tc and g0.dist(tc.x, tc.y) <= 15] + [tc]
        cands = []
        for d in drops:
            if d is None:
                continue
            dr = pathing.rect_of(d.x, d.y, 3)
            for x0 in range(dr[0] - 3 - FARM_GAP - 2, dr[2] + FARM_GAP + 3):
                for y0 in range(dr[1] - 3 - FARM_GAP - 2, dr[3] + FARM_GAP + 3):
                    fr = (x0, y0, x0 + 3, y0 + 3)
                    gx = max(dr[0] - fr[2], fr[0] - dr[2], 0)
                    gy = max(dr[1] - fr[3], fr[1] - dr[3], 0)
                    if max(gx, gy) != FARM_GAP:
                        continue
                    if not self.grid.free(x0, y0, 3, 0) or not self.explored_rect(x0, y0, 3):
                        continue
                    if (round(x0 + 1.5, 1), round(y0 + 1.5, 1), gs.FARM) in self.bad_spots:
                        continue
                    cands.append((v.dist(x0 + 1.5, y0 + 1.5) * 0.2 + (0 if d.type == gs.GRANARY else 1), x0, y0, d))
        cands.sort(key=lambda c: c[0])
        for _, x0, y0, d in cands[:20]:
            if not self.farm_paths_ok(x0, y0, d):
                continue
            c = (x0 + 1.5, y0 + 1.5)
            if self.g.can_place(self.me, gs.FARM, *c):
                return c
            self.bad_spots.add((round(c[0], 1), round(c[1], 1), gs.FARM))
        return None

    def farm_paths_ok(self, x0, y0, drop):
        pm = self.pm.copy()
        pm.block_rect(x0, y0, x0 + 3, y0 + 3)
        dr = pathing.rect_of(drop.x, drop.y, 3)
        start = pm.ring_tiles(*dr)
        if not start:
            return False
        dist = pm.bfs(start, max_cost=400)
        ring = pm.ring_tiles(x0, y0, x0 + 3, y0 + 3)
        reach = [dist[ty * pm.W + tx] for tx, ty in ring if dist[ty * pm.W + tx] >= 0]
        if not reach or min(reach) > (FARM_GAP + 1) * 10 + 6:
            return False                     # walking back to the drop site would need a detour
        tc = self.tc()
        if tc:
            tr = pathing.rect_of(tc.x, tc.y, 3)
            exits = pm.ring_tiles(*tr)
            if not exits:
                return False
            far = pm.bfs(exits, max_cost=200)
            ok = False
            for ty in range(max(0, int(tc.y) - 12), min(pm.H, int(tc.y) + 13)):
                for tx in range(max(0, int(tc.x) - 12), min(pm.W, int(tc.x) + 13)):
                    if far[ty * pm.W + tx] >= 0 and math.hypot(tx - tc.x, ty - tc.y) >= 10:
                        ok = True
                        break
                if ok:
                    break
            if not ok:
                return False                 # new villagers could not leave the TC
        return True

    # ---------------------------------------------------------------- hunting
    def hunt_available(self):
        if self.lures:
            return True
        for h in self.herds.values():
            if h.state != "done":
                return True
        return any(a.type == gs.ELEPHANT and a.hp > 0 for a in self.s.gaia)

    def herd_live(self, h):
        out = []
        for gid in list(h.ids):
            a = self.gaia_by_id(gid)
            if a is not None and a.hp > 0 and self.s.visible(a.x, a.y):
                out.append(a)
        return out

    def meat(self):
        """Carcasses with meat left (a killed animal becomes a new 'Dead_*' object; while it is still
        falling it is the animal itself with hp <= 0)."""
        return [o for o in self.s.gaia if o.amount > 0 and (
            (o.cls == gs.CLS_DEAD and o.type in gs.MEAT) or (o.type == gs.GAZELLE and o.hp <= 0))]

    def herd_carcasses(self, h):
        out = {}
        for gid in list(h.ids):
            a = self.gaia_by_id(gid)
            if a is not None and a.hp <= 0 and a.amount > 0:
                out[a.id] = a
        for m in self.meat():
            if m.type == gs.DEAD_GAZELLE and m.dist(h.x, h.y) <= 8:
                out[m.id] = m
        return list(out.values())

    def pit_finished(self):
        """The first storage pit stands. Before it only hunts brought to the TC (lured elephants, pushed
        gazelles) are allowed - the user lifted the old no-hunting-before-the-pit rule on 2026-10-10."""
        return self.woodline_placed and bool(self.complete(gs.STORAGE_PIT))

    def tc_edge_dist(self, x, y):
        """Tiles from the TC's edge (the TC is 3x3)."""
        tc = self.tc()
        return max(0.0, math.hypot(x - tc.x, y - tc.y) - 1.5) if tc else 999.0

    def against_obstacle(self, a):
        """The user's rule: a gazelle standing right against a wall / the forest is left alone. That is
        half of its sides blocked, or no open way (within 45 deg of the TC direction) to push it home."""
        blocked = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (dx or dy) and not self.pm.passable(int(a.x) + dx, int(a.y) + dy):
                    blocked += 1                         # off the map counts as blocked
        if blocked >= 5:                                 # more than half its sides: boxed in
            return True
        if min(a.x, a.y, self.r.W - 1 - a.x, self.r.H - 1 - a.y) < 3.0:
            return True                                  # at the map edge: no way behind it
        tc = self.tc()
        if not tc:
            return False
        bx, by = unit(tc.x - a.x, tc.y - a.y)
        for deg in (0, 20, -20, 45, -45):
            r = math.radians(deg)
            dx, dy = bx * math.cos(r) - by * math.sin(r), bx * math.sin(r) + by * math.cos(r)
            if all(self.pm.passable(int(a.x + dx * k), int(a.y + dy * k)) for k in (1.0, 2.0, 3.0)) and                     all(self.pm.passable(int(a.x - dx * k), int(a.y - dy * k)) for k in (1.5, 3.6)):
                return False
        return True

    def elephant_targets(self, tc):
        """Live elephants we see or saw recently, within luring range of the TC: [(id, x, y)]."""
        out = {}
        for aid, (x, y, ty, _) in self.animal_pos.items():
            if ty == gs.ELEPHANT:
                out[aid] = (x, y)
        for a in self.s.gaia:
            if a.type == gs.ELEPHANT:
                if a.hp > 0 and self.s.visible(a.x, a.y):
                    out[a.id] = (a.x, a.y)
                elif a.hp <= 0:
                    out.pop(a.id, None)
        rng = LURE_RANGE if not self.food_desperate else 70
        if not self.bronze_clicked:
            rng = LURE_RANGE                             # (lured home up to 60 tiles; further: killed in place)
        t = self.now()
        # a lion within 8 tiles of the elephant kills the lurer on its way (lure7/8: 4 lurers) - that
        # elephant waits until the lion has wandered off
        lions = [(lx, ly) for (lx, ly, lt) in self.lions.values() if t - lt < 120]
        # contested: an enemy villager at it, or nearer to a known enemy building than to our TC - the
        # two lures pull it apart and it dies in the middle (lure12: #5558 died 32 / 37 tiles from both TCs)
        foes = [(e.x, e.y) for e in self.s.enemy if e.cls == gs.CLS_VILLAGER and e.hp > 0]
        fobs = [(b.x, b.y) for b in self.s.enemy_buildings_seen]

        def contested(x, y):
            if any(math.hypot(x - fx, y - fy) < 6 for fx, fy in foes):
                return True
            d_tc = math.hypot(x - tc.x, y - tc.y)
            return any(math.hypot(x - bx, y - by) < d_tc for bx, by in fobs)
        return [(aid, x, y) for aid, (x, y) in out.items()
                if math.hypot(x - tc.x, y - tc.y) <= rng and aid not in self.lure_failed
                and self.lure_retry.get(aid, 0) <= t
                and not any(math.hypot(x - lx, y - ly) < 8 for lx, ly in lions)
                and not contested(x, y)]

    def hunting_plan(self):
        """Pick the hunts: an elephant lure first (easiest), the first gazelle pushed home, herds
        killed where they stand. Several sites run at once, each with 4-7 villagers."""
        tc = self.tc()
        self.sites = []
        self.meat_groups = {}
        self.site_cap = {}
        self.site_load = {}
        self.hunt_capacity = 0
        if not tc:
            return
        home_only = not self.pit_finished()          # before the first pit: only hunts brought to the TC
        t = self.now()
        # 1. elephants: always lure one when there is one in range (it comes to us, the safest food)
        hunters_ok = len(self.s.villagers) >= HUNT_FROM_VILLAGER     # never before the 9th villager
        if self.age >= 3:
            hunters_ok = False      # (the user: in Bronze the food comes from the farms - no new lure / far kill)
        if hunters_ok and not any(L.state in ("provoke", "run") for L in self.lures.values()):
            eles = self.elephant_targets(tc)
            if eles:
                eid, x, y = min(eles, key=lambda e: math.hypot(e[1] - tc.x, e[2] - tc.y))
                if eid not in self.lures:
                    L = Lure(eid)
                    L.x, L.y, L.t0 = x, y, t
                    L.home = self.lure_home(x, y)         # (x, y, kind, roomy): the nearest dropsite
                    o = self._gaia_by_id.get(eid)
                    if o is not None:
                        L.eptr, L.emaxhp = o.ptr, o.maxhp
                        self.anim_cache[eid] = o
                    self.lures[eid] = L
                    self.say("lure elephant #%d (%.0f tiles away) to the TC" % (eid, math.hypot(x - tc.x, y - tc.y)))
        # 1b. an elephant too far to lure is killed where it stands, with a pit for the meat (players'
        #     "ăn voi xa"); one at a time, only once the wood-line pit exists
        if hunters_ok and not home_only and not any(getattr(L, "far", False) and L.state != "eat" for L in self.lures.values()):
            far = []
            for aid, (x, y, ty, _) in self.animal_pos.items():
                d = math.hypot(x - tc.x, y - tc.y)
                far_max = 999 if not self.bronze_clicked else FAR_ELEPHANT   # (the user: the whole map while aging)
                if ty == gs.ELEPHANT and aid not in self.lures and aid not in self.lure_failed and LURE_RANGE < d <= far_max:
                    tr = self.wslow.track(aid)
                    if tr is not None:
                        far.append((d, aid, tr.x, tr.y))
            if far:
                d, eid, x, y = min(far)
                L = Lure(eid)
                L.x, L.y, L.t0, L.state, L.far = x, y, t, "kill", True
                o = self._gaia_by_id.get(eid) or self.anim_cache.get(eid)
                if o is not None:
                    L.eptr, L.emaxhp = o.ptr, o.maxhp
                self.lures[eid] = L
                self.say("elephant #%d is %.0f tiles away: killed where it stands (pit for the meat)" % (eid, d))
        # 2. gazelle herds
        for h in self.herds.values():
            live = self.herd_live(h)
            if live:
                h.x = sum(o.x for o in live) / len(live)
                h.y = sum(o.y for o in live) / len(live)
            pushing = sum(1 for o in self.herds.values() if o.state == "push")
            if h.state == "skip" and t >= getattr(h, "skip_until", 0):
                h.state = "new"                          # look again: it may have wandered into the open
            if h.state == "new" and live and math.hypot(h.x - tc.x, h.y - tc.y) <= PUSH_RANGE:
                against = sum(1 for o in live if self.against_obstacle(o))
                if against * 2 >= len(live) or getattr(h, "fails", 0) >= 3:
                    # the user: gazelles against a wall / the forest / the map edge are left alone (and a
                    # herd that failed twice); looked at again in 60 s
                    h.state, h.skip_until = "skip", t + 60
                    h.fails = 0
                    self.say("herd %s left alone: %s" % (h.key, "%d of %d gazelles against the forest / a wall / "
                                                         "the map edge" % (against, len(live))
                                                         if against * 2 >= len(live) else "two pushes failed"))
            if h.state in ("new", "kill"):
                # a herd in reach is pushed home as a whole (the user: never one gazelle at a time)
                if (live and math.hypot(h.x - tc.x, h.y - tc.y) <= PUSH_RANGE and t >= getattr(h, "no_push_until", 0)
                        and self.push_way_clear(h, t)):
                    if pushing < MAX_PUSHES and hunters_ok:
                        h.state, h.push_t0, h.push_t1 = "push", t, None
                        h.start_xy, h.last_seen, h.best_d = (h.x, h.y), (h.x, h.y, t), (math.hypot(h.x - tc.x, h.y - tc.y), t)
                        h.pusher = h.guard = None
                        h.behind_t, h.cant_get_behind, h.pst, h.mt = None, False, {}, {}
                        self.say("push herd %s home (%d gazelles, %.0f tiles)" % (
                            h.key, len(live), math.hypot(h.x - tc.x, h.y - tc.y)))
                    # else: wait for a free pusher
                elif h.state == "new" and live and math.hypot(h.x - tc.x, h.y - tc.y) > PUSH_RANGE:
                    h.state = "kill"                     # too far: hunted where it stands (with a pit)
                elif h.state == "kill" and not live and self.herd_carcasses(h) and not self.herd_survivors(h):
                    h.state = "eat"                      # (the user: the whole herd dies first, then eat)
            elif h.state == "push":
                pass                                     # driven by the HerdPush task (run_tasks)
            elif h.state == "pushed":
                pass                                     # (kill phase of the HerdPush task)
            if h.state in ("kill", "eat"):
                # every hunter of the site idle 45+ s on one spot: the herd cannot be got at (age2: 7-9
                # hunters stood 300 s by the pit of a herd 43 tiles out, food stuck at 174) - left alone
                # for 120 s, the hunters go to other food
                isince = self.__dict__.get("_idle_since", {})
                hs_ = [v for v in self.s.villagers if self.hunt_site.get(v.id) == ("herd", h.key)]
                if hs_ and all(v.id in isince and t - isince[v.id][0] >= 45 for v in hs_):
                    h.state, h.skip_until = "skip", t + 120
                    for v in hs_:
                        self.hunt_site.pop(v.id, None)
                        isince.pop(v.id, None)
                    self.say("HERDSKIP herd %s: its %d hunters idle 45+ s - left alone for 120 s" % (h.key, len(hs_)))
                    continue
                if not h.pit_done and (h.state == "eat" or any(self.hunt_site.get(v.id) == ("herd", h.key)
                                                               for v in self.s.villagers)):
                    self.herd_pit(h)                 # retried until the wood-line pit exists
                if h.state == "eat" and not self.herd_carcasses(h) and not self.herd_live(h):
                    h.state = "done"                 # (a kill-state herd out of sight is NOT done)
        # 3. the active sites, nearest first, at most MAX_HUNT_SITES
        sites = []
        for eid, L in self.lures.items():
            e = self.gaia_by_id(eid)
            x, y = (e.x, e.y) if e is not None else (L.x, L.y)
            home = getattr(L, "home", None)
            if home and L.state in ("provoke", "run"):
                x, y = home[0], home[1]                   # the waiters gather at the home, not at the elephant
            sites.append((("lure", eid), x, y, L.state))
        for h in self.herds.values():
            if h.state in ("push", "pushed"):
                sites.append((("herd", h.key), h.x, h.y, h.state))
            elif h.state in ("kill", "eat"):
                if home_only:
                    continue                             # a far herd needs its pit: after the first one
                pts = [(a.x, a.y) for a in (self.herd_live(h) or self.herd_carcasses(h))]
                if not pts and h.state == "kill":         # out of sight now: where we saw its gazelles
                    pts = self.herd_remembered(h)
                rng = HERD_RANGE if self.bronze_clicked else 999   # (the user: no radius while aging - nearest first)
                if ((not sites and not self.sites) or self.food_emergency) and self.bronze_clicked:
                    rng = HERD_POOR if not self.food_desperate else 999   # a map without hunts close by
                if pts and min(math.hypot(x - tc.x, y - tc.y) for x, y in pts) <= rng:
                    sites.append((("herd", h.key), sum(x for x, _ in pts) / len(pts),
                                  sum(y for _, y in pts) / len(pts), h.state))
        covered = [(x, y) for (k, x, y, st) in sites]
        lure_spots = [(L.x, L.y) for L in self.lures.values()]
        groups = []
        for m in self.meat():
            if home_only and math.hypot(m.x - tc.x, m.y - tc.y) > 10:
                continue
            if any(math.hypot(m.x - x, m.y - y) < 8 for x, y in covered) or                     any(math.hypot(m.x - x, m.y - y) < 4 for x, y in lure_spots):
                continue
            if math.hypot(m.x - tc.x, m.y - tc.y) > (HERD_RANGE if (self.bronze_clicked and not self.food_desperate) else 999):
                continue
            for g in groups:
                if math.hypot(g[0] - m.x, g[1] - m.y) < 5:
                    g[2].append(m)
                    break
            else:
                groups.append([m.x, m.y, [m]])
        for gx, gy, ms in groups:
            key = ("meat", (int(gx) // 5, int(gy) // 5))
            self.meat_groups[key] = ms
            sites.append((key, gx, gy, "eat"))
        sites.sort(key=lambda s: (0 if s[0][0] == "lure" else 1, math.hypot(s[1] - tc.x, s[2] - tc.y)))
        ban = self.__dict__.get("_site_ban", {})
        if ban:
            sites = [st for st in sites if ban.get(st[0], -1) <= t]
        if self.age >= 3:
            # Bronze: farms first (the user) - only a lure already on its way, and meat lying at the TC or a
            # pit, are still worked; herds out in the field are left
            def home_site(st):
                key, x, y, state = st
                if key[0] == "lure" and state in ("provoke", "run", "kill"):
                    return True
                return state == "eat" and (math.hypot(x - tc.x, y - tc.y) <= 12 or self.meat_drop_near(x, y))
            sites = [st for st in sites if home_site(st)]
        self.sites = sites[:MAX_HUNT_SITES]
        for key, x, y, state in self.sites:
            if state == "push":
                cap = 2 if len(self.s.villagers) >= GUARD_FROM_VILLAGERS else 1   # pusher (+ side guard)
            elif state in ("provoke", "run"):
                cap = 1 + 3                              # the lurer + three waiters standing at the home (the user)
            elif state == "pushed":
                cap = max(2, min(6, len(self.herd_live(self.herds[key[1]])))) if key[1] in self.herds else 2
            elif key[0] == "lure" and state == "kill":
                cap = 1 + ELEPHANT_EATERS                # the killers
            elif key[0] == "lure" and state == "eat":
                cap = ELEPHANT_EATERS                    # villagers eat one elephant
            elif key[0] == "meat":
                ms = self.meat_groups.get(key, [])
                with_pit = self.meat_drop_near(x, y)
                cap = sum(ELEPHANT_EATERS if m.type == gs.DEAD_ELEPHANT else (3 if with_pit else 2) for m in ms)
                cap = max(2, min(HUNT_SITE_FAR_MAX if with_pit else HUNT_SITE_MAX, cap))
            elif key[0] == "herd" and math.hypot(x - tc.x, y - tc.y) > 12 and key[1] in self.herds:
                h = self.herds[key[1]]
                n_anim = len(self.herd_live(h)) + len(self.herd_carcasses(h))
                cap = min(HUNT_SITE_FAR_MAX, max(HUNT_SITE_MIN, 2 + 2 * n_anim))   # a far herd: a group hunt
            else:
                near = sum(1 for v in self.s.villagers if v.dist(x, y) <= 12)
                cap = min(HUNT_SITE_MAX, max(HUNT_SITE_MIN, near))
            if self.age == 1 and self.res(gs.WOOD) >= 300 and state in ("eat", "kill"):
                cap += 3                                 # wood piles up in Stone: the spare hands eat, not chop
            if state in ("eat", "kill"):
                # the user: under 70 food left per villager a site has too many - the extra ones go and
                # eat elsewhere (the allocator gives the places above the cap to other sites)
                food = self.site_food_left(key)
                if food is not None:
                    fcap = max(1, int(food // FOOD_PER_VILLAGER))
                    if fcap > cap and not self.bronze_clicked:
                        # while aging the spare hands eat, they do not chop (players: 17-20 on food at the
                        # Tool click): up to 4 more than the usual cap, one per 70 food left
                        cap = min(fcap, cap + 4)
                    if fcap < cap:
                        load = sum(1 for k in self.hunt_site.values() if k == key)
                        if load > fcap and t - self.__dict__.setdefault("_trim_say", {}).get(key, -99) > 30:
                            self._trim_say[key] = t
                            self.say("TRIM site %s: %.0f food left for %d villagers -> %d stay, the others eat elsewhere"
                                     % (key, food, load, fcap))
                        cap = fcap
            self.site_cap[key] = cap
            self.hunt_capacity += cap
        for vid in [k for k, key in self.hunt_site.items()
                    if key not in self.site_cap or (self.role_name(k) != "hunt" and k not in self.leads)]:
            del self.hunt_site[vid]
        # before the Tool click the players keep 6-7 on wood whatever the stock: more choppers than
        # that are villagers without food work (night4: 17 on wood, no herd known, nothing searched)
        wt = 7 if not self.tool_clicked else min(self.wood_target(), WOOD_HARD_CAP)
        need = len(self.s.villagers) - wt - 2
        cap = self.hunt_capacity + self.berry_capacity()
        short = self.pit_finished() and not self.bronze_clicked and (
            cap < need - 2 or (self.food_short and cap < need))       # off only once there is enough
        if short != self.food_short:
            self.say("food work for %d villagers, %d need it: %s" % (cap, need, "looking further" if short else "enough"))
        self.food_short = short
        # an elephant brought home: the villagers working next to the TC help to kill it
        self.helpers = set()
        for eid, L in self.lures.items():
            e = self.gaia_by_id(eid)
            if L.state != "kill" or e is None or e.hp <= 0:
                continue
            want = self.site_cap.get(("lure", eid), HUNT_SITE_MIN)
            hunters = [v for v in self.s.villagers if self.hunt_site.get(v.id) == ("lure", eid)]
            others = [v for v in self.s.villagers if v.dist(e.x, e.y) <= 8 and v not in hunters
                      and self.role_name(v.id) in ("wood", "farm", None) and v.id not in self.defenders]
            # (never the berry pickers: 6 on berries is priority no. 1, the user)
            others.sort(key=lambda v: v.dist(e.x, e.y))
            for v in others[:max(0, want - len(hunters))]:
                self.helpers.add(v.id)
                if not self.recent(v.id, ("o", e.id), within=3):
                    self.order([v], e)
        # a herd pushed home: two spears per gazelle at once (the user) - villagers around the TC
        # join the pushers for the kill; the task orders them
        for key, task in self.ntasks.items():
            if key[0] != "herd" or getattr(task, "state", "") != "kill" or key[1] not in self.herds:
                task_h = getattr(task, "helpers", None)
                if task_h:
                    task.helpers = []
                continue
            live = self.herd_live(self.herds[key[1]])
            want = min(6, 2 * len(live)) - len(task.pushers)
            if want <= 0 or not tc:
                task.helpers = []
                continue
            others = [v for v in self.s.villagers if v.dist(tc.x, tc.y) <= 10 and v.id not in task.pushers
                      and self.role_name(v.id) in ("wood", "farm", "hunt", None) and v.id not in self.defenders
                      and v.id not in self.helpers]
            others.sort(key=lambda v: v.dist(self.herds[key[1]].x, self.herds[key[1]].y))
            task.helpers = [v.id for v in others[:want]]
            self.helpers.update(task.helpers)


    def tool_wood_free(self, cost):
        """During the Tool research (and in Tool Age before the market + stable stand) a building only
        if the 300 wood for the market and the stable are still there afterwards."""
        if not self.tool_clicked or self.bronze_clicked:
            return True
        need = (0 if self.any_of(gs.MARKET) else 150) + (0 if self.any_of(self.second_building()) else 150)
        need += 0 if self.any_of(gs.BARRACKS) else 125          # (BB before BL / BA)
        return self.res(gs.WOOD) - cost >= need

    def herd_pit(self, h):
        """A pit at the spot with the shortest walk to the herd's carcasses - started with the kill
        (the user's hunters build it as they arrive), so the eaters never wait for it."""
        if h.pit_done or not self.woodline_placed:
            return                                   # the wood-line pit always comes first
        car = self.herd_carcasses(h) or self.herd_live(h)
        tc = self.tc()
        if not car or not tc:
            return
        cx = sum(a.x for a in car) / len(car)
        cy = sum(a.y for a in car) / len(car)
        if self.meat_drop_near(cx, cy):
            h.pit_done = True
            return
        if self.pending_of(gs.STORAGE_PIT) or not self.can_afford(wood=120) or not self.tool_wood_free(120):
            return                                   # the hunters wait at the carcasses for the wood
        spot = self.best_dropsite(gs.STORAGE_PIT, [(a.x, a.y) for a in car], extra=self.meat_extras(cx, cy))
        if spot:
            b = [v for v in self.s.villagers if self.hunt_site.get(v.id) == ("herd", h.key)]
            b.sort(key=lambda v: v.dist(cx, cy))
            if self.start_build(gs.STORAGE_PIT, spot, b[:4], "(gazelle herd)"):
                h.pit_done = True

    def meat_pit(self, key, pts, rec):
        """A pit next to far meat (the user: far hunts get a pit, the hunters wait by the meat for
        the wood). True when the meat can be carried somewhere (TC / pit near, built or coming)."""
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        if self.meat_drop_near(cx, cy):
            return True
        if getattr(rec, "pit_done", False) or not self.woodline_placed:
            return True
        if self.pending_of(gs.STORAGE_PIT) or not self.can_afford(wood=120) or not self.tool_wood_free(120):
            vs = [v for v in self.s.villagers if self.hunt_site.get(v.id) == key]
            for v in vs:
                if v.dist(cx, cy) > 3 and not self.recent(v.id, within=4):
                    self.move([v], cx, cy)              # wait by the meat until the wood is there
            return False
        spot = self.best_dropsite(gs.STORAGE_PIT, pts, extra=self.meat_extras(cx, cy))
        if spot:
            b = sorted([v for v in self.s.villagers if self.hunt_site.get(v.id) == key], key=lambda v: v.dist(cx, cy))
            if self.start_build(gs.STORAGE_PIT, spot, b[:4] or self.builders_near(2, cx, cy), "(far meat)"):
                rec.pit_done = True
                return True
        return False

    def lure_home(self, ex, ey):
        """(x, y, kind, roomy) of the food dropsite nearest to an elephant: TC, granary or storage pit.
        roomy = a villager can walk round it (a pit against the forest cannot host a solo kill)."""
        tc = self.tc()
        cands = []
        if tc:
            cands.append((tc.x, tc.y, "TC"))
        # (no granary: it takes no meat - the user, 12/10 22:30: AI 2 lured an elephant to one)
        for p in self.complete(gs.STORAGE_PIT):
            cands.append((p.x, p.y, "pit"))
        if not cands:
            return None
        pm = getattr(self, "pm", None)

        def roomy(x, y):
            if pm is None:
                return True
            x0, y0 = int(x - 1.5), int(y - 1.5)
            ring = pm.ring_tiles(x0 - 1, y0 - 1, x0 + 4, y0 + 4)
            free = sum(1 for (xx, yy) in ring if pm.passable(xx, yy))
            return free >= 0.75 * max(1, len(ring))

        best = min(cands, key=lambda c: math.hypot(c[0] - ex, c[1] - ey))
        return (best[0], best[1], best[2], roomy(best[0], best[1]))

    def meat_drop_near(self, x, y, r=8):
        """A TC or storage pit (built or being built) within r tiles: meat can be carried there."""
        tc = self.tc()
        if tc and math.hypot(x - tc.x, y - tc.y) < r:
            return True
        return any(p.dist(x, y) < r for p in self.any_of(gs.STORAGE_PIT))

    def assign_leads(self):
        """Every elephant lure / gazelle push needs ONE villager at once. Players use the scout that
        found it: the nearest scouting villager, else a woodcutter, a berry picker last."""
        active = {k for (k, x, y, st) in self.sites if st in ("provoke", "run", "push", "pushed")}
        for vid, k in list(self.leads.items()):
            if k not in active or self.obj_by_id(vid) is None:
                del self.leads[vid]
        # the user: priority no. 1 is 6 villagers on berries. Once a bush is known, the first six
        # villagers pick berries and never lead a push / lure; one that already leads is called back
        # (an elephant already chasing it is the exception: dropping it there would be dangerous)
        # the first 8 villagers (6 on berries, the 2 scouts, the first woodcutter) never lead a lure / push
        six = self.berry_six() | {v.id for v in sorted(self.s.villagers, key=lambda v: v.id)[:HUNT_FROM_VILLAGER - 1]}
        for vid, k in list(self.leads.items()):
            if vid not in six:
                continue
            if k[0] == "herd" and k[1] in self.herds:
                h = self.herds[k[1]]
                if h.state == "push":
                    h.state, h.pusher, h.guard, h.behind_t = "new", None, None, None
                    h.no_push_until = self.now() + 15
                elif getattr(h, "guard", None) == vid:
                    h.guard = None
            elif k[0] == "lure" and k[1] in self.lures:
                L = self.lures[k[1]]
                if L.state != "provoke":
                    continue
                if L.lurer == vid:
                    L.lurer = None
            del self.leads[vid]
            self.hunt_site.pop(vid, None)
            self.say("villager #%d leaves %s: berries need their 6 villagers first" % (vid, k))
        taken = set(self.leads.values())
        prio = {"scout": 0, "search": 0, "hunt": 0, None: 1, "wood": 1, "berry": 2}
        for (k, x, y, st) in self.sites:
            if st not in ("provoke", "run", "push", "pushed") or k in taken:
                continue
            cands = [v for v in self.s.villagers if v.id not in self.leads and v.id not in self.defenders
                     and v.id not in six and self.role_name(v.id) in prio and v.dist(x, y) < 45
                     and (k[0] != "lure" or (v.hp >= 20 and v.id not in getattr(self.lures.get(k[1]), "hurt", ())))]
            if not cands:
                continue
            v = min(cands, key=lambda v: prio[self.role_name(v.id)] * 15 + v.dist(x, y))
            self.leads[v.id] = k
            self.hunt_site[v.id] = k
            taken.add(k)
            self.say("villager #%d (%s) leads %s" % (v.id, self.role_name(v.id) or "-", k))
        # two-villager pushes: a herd of 3+ gets a second pusher (left / right halves)
        for h in self.herds.values():
            if h.state != "push":
                h.guard = None
                continue
            if len(self.s.villagers) < GUARD_FROM_VILLAGERS or len(self.herd_live(h)) < 3:
                continue
            g = getattr(h, "guard", None)
            if g and self.obj_by_id(g) is not None:
                continue
            key = ("herd", h.key)
            cands = [v for v in self.s.villagers if v.id not in self.leads and v.id not in self.defenders
                     and v.id not in six and self.role_name(v.id) in ("hunt", "wood", None, "scout")
                     and v.dist(h.x, h.y) < 30]
            if cands:
                v = min(cands, key=lambda v: v.dist(h.x, h.y))
                h.guard = v.id
                self.leads[v.id] = key
                self.hunt_site[v.id] = key
                self.say("villager #%d is the second pusher of herd %s" % (v.id, h.key))

    def berry_six(self):
        """Ids of the first six villagers (the berry pickers, see desired_role) once a bush is known."""
        if not (self.berry_clusters() and (self.berry_capacity() > 0 or not self.any_of(gs.GRANARY))):
            return set()
        return {v.id for v in sorted(self.s.villagers, key=lambda v: v.id)[:6]}

    def herd_survivors(self, h, within=15.0):
        """Live gazelles of the herd (tracked by pointer, in sight or not) still within `within` tiles
        of the herd: the user's rule - the whole herd dies before anybody eats."""
        out = []
        for gid in list(h.ids):
            u = self.wslow.track(gid)
            if u is not None and u.hp > 0 and math.hypot(u.x - h.x, u.y - h.y) <= within:
                out.append(u)
        return out

    def push_way_clear(self, h, t):
        """The user: a herd whose way home runs through the berry patch the villagers are picking (or a
        wood line / houses) scatters when pushed - such a herd is hunted where it stands with a pit.
        Checked once a minute. Elephants are not affected: they are always lured."""
        if t < getattr(h, "way_checked", -999) + 60:
            return not getattr(h, "way_blocked", False)
        h.way_checked = t
        tc = self.tc()
        ax, ay, bx, by = h.x, h.y, tc.x, tc.y
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        busy = []
        for g in self.complete(gs.GRANARY):
            if any(v.dist(g.x, g.y) < 9 for v in self.s.villagers if self.role_name(v.id) == "berry"):
                busy.append((g.x, g.y, 6.0, "berry patch"))
        for p_ in self.complete(gs.STORAGE_PIT):
            if any(v.dist(p_.x, p_.y) < 9 for v in self.s.villagers if self.role_name(v.id) == "wood"):
                busy.append((p_.x, p_.y, 5.0, "wood line"))
        for o in self.s.mine:
            if o.kind == gs.KIND_STATIC and o.type not in (gs.TOWN_CENTER, gs.GRANARY, gs.STORAGE_PIT):
                busy.append((o.x, o.y, 2.5, o.name))
        why = None
        for (x, y, r, name) in busy:
            if math.hypot(x - tc.x, y - tc.y) < 7:
                continue                                 # next to the TC: that is where the herd must end up
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
            if math.hypot(ax + k * dx - x, ay + k * dy - y) < r:
                why = name
                break
        h.way_blocked = why is not None
        if why:
            self.say("herd %s: the way home crosses the %s - not pushed, hunted there with a pit" % (h.key, why))
            h.state = "kill"
        return not h.way_blocked

    def herd_remembered(self, h):
        """Positions of a herd's gazelles seen in the last 2 minutes (they are in the fog now)."""
        t = self.now()
        out = []
        for gid in h.ids:
            p = self.animal_pos.get(gid)
            if p and p[2] == gs.GAZELLE and t - p[3] < 120:
                g = self.gaia_by_id(gid)
                if g is None or g.hp > 0:
                    out.append((p[0], p[1]))
        return out

    def herd_by_key(self, key):
        return self.herds.get(key)

    def pick_site(self, v):
        """Keep the villager's site while it has room, else the nearest site with room."""
        if v.id in self.leads:
            key = self.leads[v.id]
            self.site_load[key] = self.site_load.get(key, 0) + 1
            return key
        key = self.hunt_site.get(v.id)
        if key in self.site_cap and self.site_load.get(key, 0) < self.site_cap[key]:
            self.site_load[key] = self.site_load.get(key, 0) + 1
            return key
        free = [s for s in self.sites if self.site_load.get(s[0], 0) < self.site_cap[s[0]]]
        if not free:
            self.hunt_site.pop(v.id, None)
            return None
        s = min(free, key=lambda s: math.hypot(s[1] - v.x, s[2] - v.y))
        self.hunt_site[v.id] = s[0]
        self.site_load[s[0]] = self.site_load.get(s[0], 0) + 1
        return s[0]

    def work_hunt(self, v, force):
        tc = self.tc()
        key = self.pick_site(v)
        if key is None:                              # every site is full: the next food source
            if force or self.idle(v):
                t2 = self.nearest_berry(v) if self.berry_clusters() else None
                return self.order([v], t2) if t2 else self.work_wood(v)
            return
        if key[0] == "lure":
            return self.work_lure(v, key[1], force)
        if key[0] == "meat":
            ms = self.meat_groups.get(key, [])
            if ms and not self.meat_pit(key, [(m.x, m.y) for m in ms], self.meat_recs.setdefault(key, Pending(0, 0, 0, [], 0, ""))):
                return
            if ms and (force or self.idle(v)):
                self.order([v], min(ms, key=lambda m: m.dist(v.x, v.y)))
            return
        h = self.herd_by_key(key[1])
        if h is None:
            return
        if h.state in ("push", "pushed"):
            task = self.ntasks.get(("herd", h.key))
            if task is None:
                for gid in h.ids:
                    o = self._gaia_by_id.get(gid)
                    if o is not None:
                        self.anim_cache[gid] = o
                task = (HerdPushRL if use_rl_push() else HerdPush)(list(h.ids), [v.id])
                self.ntasks[("herd", h.key)] = task
                h.pusher = v.id
                self.mark([v], ("push",))
            elif v.id not in task.pushers and len(task.pushers) < 2 and self.obj_by_id(task.pushers[0]) is not None:
                task.pushers.append(v.id)
                h.guard = v.id
                self.say("villager #%d is the second pusher of herd %s" % (v.id, h.key))
            return
        if False:
            live = [o for o in self.herd_live(h) if self.tc_edge_dist(o.x, o.y) <= HERD_KILL_NEAR + 3]
            if live:
                act = self.r.action(v)
                if not (act and act[1] in {o.ptr for o in live}) and not self.recent(v.id, within=1.2):
                    self.order([v], min(live, key=lambda o: o.dist(v.x, v.y)))   # the whole herd dies first
            return
        if h.state == "kill" and self.herd_live(h):
            self.herd_cluster_step(h, key)              # (one group step per tick for the whole site)
            return
        if h.state == "kill":
            live = self.herd_live(h)
            if live:
                # the whole herd dies first, one gazelle at a time: every hunter of the site spears the
                # same one. The user: at least TWO spears must land at once (8 hp, 4 per spear) so it
                # drops where it stands - one spear only makes it hop and scatters the herd. So the
                # hunters gather at spear range (3.3 tiles, outside the 2.1 flee circle) and nobody
                # throws until two are there; then all in range throw in the same tick.
                tgt = next((a for a in live if a.id == getattr(h, "kill_tgt", None)), None)
                if tgt is None:
                    cx = sum(a.x for a in live) / len(live)
                    cy = sum(a.y for a in live) / len(live)
                    tgt = min(live, key=lambda a: a.dist(cx, cy))
                    h.kill_tgt, h.wait_t = tgt.id, self.now()
                hunters = [u for u in self.s.villagers if self.hunt_site.get(u.id) == key]
                ready = [u for u in hunters if u.dist(tgt.x, tgt.y) <= 3.6]
                alone_ok = len(hunters) < 2 and self.now() - getattr(h, "wait_t", self.now()) > 12
                # a gazelle wanders: two hunters at 3.6 tiles at the same moment may never happen (army2: 6-10
                # hunters at a herd, not one spear in 2 minutes) - after 15 s without a throw, all hunters
                # within 6 tiles throw together
                near6 = [u for u in hunters if u.dist(tgt.x, tgt.y) <= 6.0]
                stale = self.now() - getattr(h, "last_throw", getattr(h, "wait_t", self.now())) > 15
                if stale and len(near6) >= 2:
                    ready = near6
                if self.now() - getattr(h, "kdbg_t", -99) > 10:
                    h.kdbg_t = self.now()
                    self.say("KILLDBG herd %s: target #%d (%.1f,%.1f) %.0f hp, %d hunters, %d within 3.6, %d within 6, "
                             "last throw %.0f s ago | %s" % (
                                 h.key, tgt.id, tgt.x, tgt.y, tgt.hp, len(hunters),
                                 sum(1 for u in hunters if u.dist(tgt.x, tgt.y) <= 3.6), len(near6),
                                 self.now() - getattr(h, "last_throw", getattr(h, "wait_t", self.now())),
                                 " ".join("#%d@%.1f:%s" % (u.id, u.dist(tgt.x, tgt.y), (self.r.action(u) or ("-",))[0])
                                          for u in hunters[:6])))
                if len(ready) >= 2 or alone_ok:
                    h.last_throw = self.now()
                    for u in ready:
                        au = self.r.action(u)
                        if not (au and au[1] == tgt.ptr) and not self.recent(u.id, within=1.2):
                            self.order([u], tgt)
                    if v in ready:
                        return
                if v.dist(tgt.x, tgt.y) > 3.6:
                    ux, uy = unit(v.x - tgt.x, v.y - tgt.y)
                    px, py = tgt.x + ux * 3.3, tgt.y + uy * 3.3
                    if not self.recent(v.id, within=1.5):
                        self.move([v], px, py)
                elif self.r.busy(v) and not (self.r.action(v) and self.r.action(v)[1] == tgt.ptr):
                    pass
                return
            surv = self.herd_survivors(h)
            if surv:                                     # the whole herd dies first (the user): chase the rest
                s_ = min(surv, key=lambda u: u.dist(v.x, v.y))
                a = self.gaia_by_id(s_.id)
                if a is not None and self.s.visible(a.x, a.y):
                    if not self.recent(v.id, ("o", a.id), within=2.5):
                        self.order([v], a)
                elif v.dist(s_.x, s_.y) > 2.5 and not self.recent(v.id, within=3):
                    self.move([v], s_.x, s_.y)
                return
            mem = self.herd_remembered(h)
            car0 = self.herd_carcasses(h)
            if car0:
                h.first_kill_t = getattr(h, "first_kill_t", None) or self.now()
            # go where the rest was seen; with carcasses already down, up to 30 s (the user: the whole
            # herd dies first - but a carcass is gone 300 s after the kill, so not for ever)
            if mem and (not car0 or self.now() - h.first_kill_t < 30):
                x, y = min(mem, key=lambda p: math.hypot(p[0] - v.x, p[1] - v.y))
                if v.dist(x, y) > 2.5 and not self.recent(v.id, within=3):
                    self.move([v], x, y)
                return
        car = self.herd_carcasses(h)
        if not car:
            return
        cx = sum(a.x for a in car) / len(car)
        cy = sum(a.y for a in car) / len(car)
        tc = self.tc()
        ready = (tc and math.hypot(cx - tc.x, cy - tc.y) < 8) or any(
            p.dist(cx, cy) < 8 for p in self.complete(gs.STORAGE_PIT))
        t0 = self.wait_since.setdefault(("herd", h.key), self.now())
        if not ready and (self.now() - t0 <= WAIT_LIMIT or self.pending_of(gs.STORAGE_PIT)):
            if v.dist(cx, cy) > 3 and not self.recent(v.id, within=4):
                self.move([v], cx, cy)              # wait by the meat until its pit is built
            return
        if force or self.idle(v):
            self.order([v], min(car, key=lambda a: a.dist(v.x, v.y)))

    def herd_cluster_step(self, h, key):
        """The user's way to kill a herd where it stands. Phases (kept on the herd):
          gather  - every hunter of the site to a slot of a short line (0.6 tiles apart, within 1.5 of each
                    other) CL_WAIT tiles from the target, on the hunters' side, out of every gazelle's flee
                    distance; until all are on their slot (12 s at most);
          advance - every hunter to a slot of an arc round the target, all CL_ARC tiles from it (within spear
                    range, out of its 2.1-tile flee circle), 0.6 tiles apart;
          throw   - once all stand on the arc (4 s at most): all spear the target in the same tick;
          next    - the target down (or gone 6 s): the next gazelle nearest to the group, the group steps in
                    again (advance; gather first if it is further than CL_WAIT + 2)."""
        t = self.now()
        if getattr(h, "cl_tick", None) == self.ticks:
            return
        h.cl_tick = self.ticks
        live = self.herd_live(h)
        hunters = [u for u in self.s.villagers if self.hunt_site.get(u.id) == key]
        if not live or not hunters:
            return
        # the cluster = the hunters already at the herd (10 tiles), at most CL_MAX of them; the ones still
        # walking in (or the extra ones) wait on the far side of the cluster's line (civ2: 12 hunters, 7-11
        # "out of range" - hunters 20-30 tiles away pulled the arc's direction and made it 12 slots wide)
        hx = sum(a.x for a in live) / len(live)
        hy = sum(a.y for a in live) / len(live)
        near = sorted((u for u in hunters if u.dist(hx, hy) <= 10.0), key=lambda u: u.dist(hx, hy))
        if near:
            rest = [u for u in hunters if u not in near[:CL_MAX]]
            hunters = near[:CL_MAX]
            d0 = getattr(h, "cl_dir", None)
            if rest and d0 is not None:
                g = getattr(h, "cl_tgt", None)
                ta = next((a for a in live if a.id == g), None) or live[0]
                wx = min(self.r.W - 1.0, max(1.0, ta.x + d0[0] * (CL_WAIT + 1.5)))
                wy = min(self.r.H - 1.0, max(1.0, ta.y + d0[1] * (CL_WAIT + 1.5)))
                for u in rest:
                    if u.dist(wx, wy) > 1.5 and not self.recent(u.id, ("cl", "w"), within=2.0):
                        self.move([u], wx, wy)
                        self.mark([u], ("cl", "w"))
        cx = sum(u.x for u in hunters) / len(hunters)
        cy = sum(u.y for u in hunters) / len(hunters)
        tgt = next((a for a in live if a.id == getattr(h, "cl_tgt", None)), None)
        phase = getattr(h, "cl_phase", None)
        if tgt is None:
            # (civ2: two herd records (14,0) / (15,0) of one herd went for the same gazelle)
            taken = {getattr(o, "cl_tgt", None) for o in getattr(self, "herds", {}).values() if o is not h}
            tgt = min(live, key=lambda a: (a.id in taken, a.dist(cx, cy)))
            h.cl_tgt, h.cl_t = tgt.id, t
            phase = "gather" if (phase is None or tgt.dist(cx, cy) > CL_WAIT + 2) else "advance"
            h.cl_phase, h.cl_dir = phase, None
        ux, uy = unit(cx - tgt.x, cy - tgt.y)
        if getattr(h, "cl_dir", None) is None or phase == "gather":
            h.cl_dir = (ux, uy)
        ux, uy = h.cl_dir
        px, py = -uy, ux
        order = sorted(hunters, key=lambda u: ((u.x - tgt.x) * px + (u.y - tgt.y) * py))   # left to right
        n = len(order)

        W, H = self.r.W, self.r.H

        def on_map(x, y):
            return 0.6 <= x <= W - 0.6 and 0.6 <= y <= H - 0.6

        def slots(radius, arc):
            # (civ1: a herd on the map edge, y = 0.5 - the arc / line on the hunters' side fell off the map
            #  and 2-5 of 6 hunters were "not there after 4 s" every throw: the slots turn inward)
            base = math.atan2(uy, ux)
            first = None
            for dl in (0.0, 0.35, -0.35, 0.7, -0.7, 1.05, -1.05, 1.4, -1.4, 1.75, -1.75, 2.1, -2.1, 2.6, -2.6, math.pi):
                out = []
                vx, vy = math.cos(base + dl), math.sin(base + dl)
                for i, u in enumerate(order):
                    k = i - (n - 1) / 2.0
                    if arc:
                        a = base + dl + k * (CL_GAP / radius)
                        out.append((u, tgt.x + math.cos(a) * radius, tgt.y + math.sin(a) * radius))
                    else:
                        out.append((u, tgt.x + vx * radius - vy * k * CL_GAP, tgt.y + vy * radius + vx * k * CL_GAP))
                if all(on_map(x, y) for (_u, x, y) in out):
                    return out
                first = first or out
            return [(u, min(W - 0.6, max(0.6, x)), min(H - 0.6, max(0.6, y))) for (u, x, y) in first]
        if phase == "gather":
            sl = slots(CL_WAIT, False)
            far = [(u, x, y) for (u, x, y) in sl if u.dist(x, y) > 0.8]
            for (u, x, y) in far:
                if not self.recent(u.id, ("cl", "g"), within=1.5):
                    self.move([u], x, y)
                    self.mark([u], ("cl", "g"))
            if not far or t - h.cl_t > 12:
                h.cl_phase, h.cl_t = "advance", t
            return
        if t - getattr(h, "cl_dbg", -99) > 10:
            h.cl_dbg = t
            prevpos = getattr(h, "cl_tpos", None)
            moved = math.hypot(tgt.x - prevpos[0], tgt.y - prevpos[1]) if prevpos else 0.0
            h.cl_tpos = (tgt.x, tgt.y)
            sl_dbg = slots(CL_ARC if phase == "advance" else CL_WAIT, phase == "advance")
            self.say("CLDBG herd %s phase %s %.0f s, gazelle #%d (%.1f,%.1f) moved %.1f in 10 s | %s" % (
                h.key, phase, t - h.cl_t, tgt.id, tgt.x, tgt.y, moved,
                " ".join("#%d d%.1f slot%.1f %s" % (u.id, u.dist(tgt.x, tgt.y), u.dist(x, y), (self.r.action(u) or ("-",))[0])
                         for (u, x, y) in sl_dbg[:5])))
        if phase == "advance":
            sl = slots(CL_ARC, True)
            # (ready = every hunter within spear range of the target: the arc slots move with a wandering
            #  gazelle, 0.45 tiles of a slot was never met - ab4 / ab5: "N not there after 4 s" every time)
            # the group is the hunters within 8 tiles; one walking in from 25-40 tiles is not waited for
            # (ffa5: "out of range" every time - a newly assigned hunter far away was part of the wait)
            group = [(u, x, y) for (u, x, y) in sl if u.dist(tgt.x, tgt.y) <= 8.0]
            inr = [(u, x, y) for (u, x, y) in group if u.dist(tgt.x, tgt.y) <= SPEAR_REACH]
            far = [(u, x, y) for (u, x, y) in group if u.dist(tgt.x, tgt.y) > SPEAR_REACH]
            if group and (len(inr) >= 2 or (len(group) == 1 and inr)):
                far = []                                 # (two spears at once are enough to kill)
            # one of them is inside the hop range already (the gazelle is about to jump): throw now, everybody
            # within 3.3 - waiting for the rest lost every gazelle (ab8: "out of range after 6 s" 41 of 43)
            close = any(u.dist(tgt.x, tgt.y) < 2.4 for (u, _x, _y) in sl)
            for (u, x, y) in sl:
                if u.dist(x, y) > 0.5 and not self.recent(u.id, ("cl", "a"), within=1.0):
                    self.move([u], x, y)
                    self.mark([u], ("cl", "a"))
            if (group and not far) or close or t - h.cl_t > 4:
                throwers = [(u, x, y) for (u, x, y) in sl if u.dist(tgt.x, tgt.y) <= 3.3] or group or sl
                for (u, _x, _y) in throwers:            # everybody in the same tick (the user)
                    self.order([u], tgt)
                h.cl_phase, h.cl_t = "throw", t
                h.last_throw = t
                if t - getattr(h, "cl_say", -99) > 20:
                    h.cl_say = t
                    self.say("CLUSTER herd %s: %d hunters throw at gazelle #%d together (%s)" % (
                        h.key, len(sl), tgt.id, "%d in spear range" % len(inr) if not far else "%d out of range after 4 s" % len(far)))
            return
        if phase == "throw":
            if tgt.hp <= 0 or t - h.cl_t > 6:
                h.cl_tgt = None                          # the next one: chosen at the next step
                h.cl_phase = "next"
            return
        if phase == "next":
            h.cl_tgt = None

    def work_lure(self, v, eid, force):
        """One villager hits the elephant and runs to the TC; it is killed only once it is within
        3 TC foundations of the TC, by the villagers waiting there."""
        tc = self.tc()
        t = self.now()
        L = self.lures.get(eid)
        if L is None:
            return
        e = self.gaia_by_id(eid)
        carcass = self.gaia_by_id(getattr(L, "carcass", -1))
        if carcass is None and (e is None or e.hp <= 0) and L.state in ("kill", "eat", "run"):
            # (the carcass looked for round its last known spot AND round the home, 10 tiles: age13 eaters
            #  stood by a spot 6+ tiles from where it fell, idle for minutes)
            spots = [(L.x, L.y)] + ([(L.home[0], L.home[1])] if getattr(L, "home", None) else [])
            near = [m for m in self.meat() if m.type == gs.DEAD_ELEPHANT and min(m.dist(x, y) for x, y in spots) <= 10
                    and not any(getattr(o, "carcass", None) == m.id for o in self.lures.values() if o is not L)]
            if near:
                carcass = min(near, key=lambda m: min(m.dist(x, y) for x, y in spots))
                L.carcass = carcass.id
        if carcass is not None:
            e = carcass                                  # eat the Dead_Elephant object
        if e is not None and (e.hp <= 0 or carcass is not None):
            if L.state != "eat" and not getattr(L, "ok_said", False):
                L.ok_said = True                          # once (the task's 3-s grace kept resetting L.state)
                home = getattr(L, "home", None) or (tc.x, tc.y, "TC", True)
                self.say("elephant #%d down after %.0f s" % (eid, t - L.t0))
                self.say("LUREOK elephant #%d died %.1f tiles from the %s edge after %.0f s" % (
                    eid, max(0.0, max(abs(e.x - home[0]), abs(e.y - home[1])) - 1.5), home[2], t - L.t0))
            L.state = "eat"
            self.lure_failed.add(eid)                # never lured again
            self.animal_pos.pop(eid, None)
        if L.state == "eat":
            if e is not None:
                L.seen = t
                if not self.meat_pit(("lure", eid), [(e.x, e.y)], L):
                    return
            if e is None and not hasattr(L, "seen"):
                L.seen = t                               # (else a carcass never found kept the site for ever)
            if (e is not None and e.amount <= 0) or (e is None and t - getattr(L, "seen", t) > 20):
                del self.lures[eid]
                return
            if e is None:
                if v.dist(L.x, L.y) > 2 and not self.recent(v.id, within=4):
                    self.move([v], L.x, L.y)
                return
            if force or self.idle(v):
                self.order([v], e)
            return
        task = self.ntasks.get(("lure", eid))
        if task is None:
            if e is None and self.anim_cache.get(eid) is None:
                self.lure_failed.add(eid)
                del self.lures[eid]
                self.say("elephant #%d not found any more: lure dropped" % eid)
                return
            home = getattr(L, "home", None)
            hxy = None
            if home and home[2] != "TC":
                hxy = (home[0], home[1])
                if not home[3]:                          # no walk round it: the lurer could not kill alone there
                    waiting = [u for u in self.s.villagers if self.hunt_site.get(u.id) == ("lure", eid) and u.id != v.id]
                    if not waiting and tc:
                        hxy = None
                        L.home = (tc.x, tc.y, "TC", True)
            task = LureTask(eid, v.id, [], anywhere=getattr(L, "far", False), home=hxy)
            self.ntasks[("lure", eid)] = task
            L.lurer = v.id
            if home:
                self.say("lure %d: home = %s at (%.0f,%.0f), %.0f tiles from the elephant%s" % (
                    eid, L.home[2], L.home[0], L.home[1], math.hypot(L.home[0] - L.x, L.home[1] - L.y),
                    "" if L.home[3] else " (no walk round it)"))
        elif v.id != task.lurer and v.id not in task.waiters:
            task.waiters.append(v.id)
        return

    def push_dir(self, gx, gy):
        """Unit direction the herd should run: towards the TC, turned away from trees/cliffs/water so
        the next hop lands on open ground."""
        tcx, tcy = self.tc_anchor
        bx, by = unit(tcx - gx, tcy - gy)
        pm = getattr(self, "pm", None)
        if pm is None:
            return bx, by
        for deg in (0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75):
            a = math.radians(deg)
            dx, dy = bx * math.cos(a) - by * math.sin(a), bx * math.sin(a) + by * math.cos(a)
            ahead = all(pm.passable(int(gx + dx * k), int(gy + dy * k)) for k in (1.0, 2.0, 3.0))
            behind = all(pm.passable(int(gx - dx * k), int(gy - dy * k)) for k in (PUSH_IN, PUSH_CIRCLE))
            if ahead and behind:
                return dx, dy
        return bx, by

    def herd_members_live(self, h):
        """[(gazelle, x, y)] of the herd's visible live gazelles, positions read now."""
        import struct
        out = []
        for gid in list(h.ids):
            o = self._gaia_by_id.get(gid)
            if o is None or o.hp <= 0 or o.type != gs.GAZELLE:
                continue
            r = self.g.m.read(o.ptr + O_X, 8)
            if r and len(r) == 8:
                x, y = struct.unpack("<ff", r)
                out.append((o, x, y))
        seen = {o.id for o, _, _ in out}
        t = self.now()
        ghosts = []
        for gid in h.ids:
            p = self.animal_pos.get(gid)
            if gid not in seen and p and p[2] == gs.GAZELLE and t - p[3] < 30:
                o = self._gaia_by_id.get(gid)
                if o is None or o.hp > 0:
                    ghosts.append((None, p[0], p[1]))
        out = out + ghosts if out else []
        if len(out) >= 3:                                # strays far from the others are left behind
            cx = sorted(p[1] for p in out)[len(out) // 2]
            cy = sorted(p[2] for p in out)[len(out) // 2]
            out = [p for p in out if math.hypot(p[1] - cx, p[2] - cy) <= HERD_SPREAD] or out
        return out

    def micro_herd(self, h, now, mg):
        import struct
        pushers = [vid for vid in (getattr(h, "pusher", None), getattr(h, "guard", None)) if vid]
        if not pushers:
            return
        mem = self.herd_members_live(h)
        mt = h.__dict__.setdefault("mt", {})
        if not mem:                                       # out of sight: go where the herd was last seen
            ls = getattr(h, "last_seen", None)
            for vid in pushers:
                v = self._by_id.get(vid)
                if v is not None and ls and now - mt.get(vid, (0.0, None))[0] > 1.0:
                    mg.move([v], ls[0], ls[1])
                    mt[vid] = (now, (ls[0], ls[1]))
            h.mode = "search"
            return
        cx = sum(p[1] for p in mem) / len(mem)
        cy = sum(p[2] for p in mem) / len(mem)
        dx, dy = self.push_dir(cx, cy)
        nx, ny = -dy, dx
        proj = [((p[1] - cx) * dx + (p[2] - cy) * dy, (p[1] - cx) * nx + (p[2] - cy) * ny, p) for p in mem]
        back = min(q[0] for q in proj)                   # the herd's rear edge (along the push direction)
        radius = max(math.hypot(p[1] - cx, p[2] - cy) for p in mem) + PUSH_CIRCLE
        # two pushers: left / right halves of the herd
        halves = {pushers[0]: proj}
        if len(pushers) == 2:
            left = [q for q in proj if q[1] <= 0]
            right = [q for q in proj if q[1] > 0]
            halves = {pushers[0]: left or proj, pushers[1]: right or proj}
        for vid, part in halves.items():
            v = self._by_id.get(vid)
            if v is None:
                continue
            rv = self.g.m.read(v.ptr + O_X, 8)
            if not rv or len(rv) < 8:
                continue
            vx, vy = struct.unpack("<ff", rv)
            v_proj = (vx - cx) * dx + (vy - cy) * dy
            v_lat = (vx - cx) * nx + (vy - cy) * ny
            seen_part = [q for q in part if q[2][0] is not None] or [q for q in proj if q[2][0] is not None]
            if not seen_part:
                continue
            rear = min(seen_part, key=lambda q: q[0])    # the rearmost (visible) gazelle of this part
            r_proj, r_lat, (rg, rx, ry) = rear
            st = h.__dict__.setdefault("pst", {}).setdefault(vid, {})
            sp = st.get("spear")
            if sp is not None:                           # one spear thrown? then straight back to pushing
                rh = self.g.m.read(sp[3] + O_HP, 4)
                ghp = struct.unpack("<f", rh)[0] if rh and len(rh) == 4 else 0.0
                # the user: one spear per full-hp gazelle, then wait to see it hit, get back into position,
                # and only then throw again
                hit = ghp < sp[1] - 0.01
                if hit or now - sp[2] > 3.0:
                    if hit:
                        h.__dict__.setdefault("speared", set()).add(sp[0])
                    else:
                        h.__dict__.setdefault("speared", set()).discard(sp[0])   # missed: may be thrown at again
                    st.pop("spear", None)
                    st["next_spear"] = now + (1.5 if hit else 2.0)             # back into position first
                    mg.stop([v])                         # no second spear: it would kill it out there
                    mt[vid] = (0.0, None)                # the next move goes out at once
                else:
                    continue
            if v_proj <= back - 1.2 and now >= st.get("next_spear", 0.0):
                # players hit every gazelle once on the way (the user): it keeps half its hp, hops
                # ~3 tiles straight away (towards the TC, we are behind it) and at the TC one more
                # spear kills it before it can run. Only gazelles ahead of us and nearly in line.
                speared = h.__dict__.setdefault("speared", set())
                cands = [q for q in seen_part if q[2][0].id not in speared and q[0] > v_proj + 0.5
                         and abs(q[1] - v_lat) < 2.0 + 0.4 * (q[0] - v_proj)
                         and math.hypot(q[2][1] - vx, q[2][2] - vy) < 5.0]
                busy = any(o.get("spear") for k, o in h.__dict__.get("pst", {}).items() if k != vid)
                for q in ([] if busy else sorted(cands, key=lambda q: math.hypot(q[2][1] - vx, q[2][2] - vy))):
                    g = q[2][0]
                    rh = self.g.m.read(g.ptr + O_HP, 4)
                    ghp = struct.unpack("<f", rh)[0] if rh and len(rh) == 4 else 0.0
                    if ghp < g.maxhp - 0.01:
                        speared.add(g.id)                # already hurt: not again
                        continue
                    mg.order([v], g, None, None)
                    st["spear"] = (g.id, ghp, now, g.ptr)
                    speared.add(g.id)                    # reserved at once: two pushers threw at one
                    h.mode = "spear"
                    self.say("push herd %s: one spear at gazelle #%d (%.0f hp)" % (h.key, g.id, ghp))
                    break
                if st.get("spear") is not None:
                    continue
            if v_proj > back - 1.2:
                # not behind the herd yet: walk round it on a circle that keeps away from every gazelle
                cur = math.atan2(vy - cy, vx - cx)
                goal = math.atan2(-dy, -dx)
                off = (cur - goal + math.pi) % (2 * math.pi) - math.pi
                cd = st.get("cdir")
                if cd is None:
                    cd = -1 if off > 0 else 1
                    pm = getattr(self, "pm", None)

                    def bad(a):
                        px, py = cx + math.cos(a) * (radius + 2.0), cy + math.sin(a) * (radius + 2.0)
                        return any(math.hypot(px - p[1], py - p[2]) < 3.2 for p in mem) or \
                            (pm is not None and not pm.passable(int(px), int(py)))
                    if bad(cur + 0.8 * cd) and not bad(cur - 0.8 * cd):
                        cd = -cd
                    st["cdir"] = cd
                prog = st.get("cprog")
                if prog is None:
                    st["cprog"] = (now, abs(off))
                    st.setdefault("circle_t0", now)
                elif now - prog[0] > 4.0:
                    if abs(off) > prog[1] - 0.25:        # no way round this side for 4 s: the other side
                        st["cdir"] = cd = -cd
                    st["cprog"] = (now, abs(off))
                if now - st.get("circle_t0", now) > 25:
                    h.cant_get_behind = True             # the tick gives this herd up
                d_c = math.hypot(vx - cx, vy - cy)
                wide = radius + 2.0
                if d_c > wide + 3.0:                     # far: to the circle, but on the herd's flank
                    a = cur + 0.9 * cd
                    tx, ty = cx + math.cos(a) * wide, cy + math.sin(a) * wide
                    mode = "approach"
                else:
                    a = cur + 0.7 * cd
                    tx, ty = cx + math.cos(a) * wide, cy + math.sin(a) * wide
                    mode = "circle"
            elif abs(v_lat - r_lat) > 1.2:
                # behind the herd: slide along the line behind it to the rearmost gazelle
                line = back - (PUSH_CIRCLE - 0.6)
                tx, ty = cx + dx * line + nx * r_lat, cy + dy * line + ny * r_lat
                mode = "sweep"
                st.pop("cdir", None)
                st.pop("circle_t0", None)
                st.pop("cprog", None)
            else:
                # step in behind the rearmost one: it hops towards the TC, into the herd. If it does not
                # react, come closer; still nothing after a few tries -> one spear (full hp only)
                gp = st.get("gpos")
                if gp is None or gp[3] != rg.id or math.hypot(rx - gp[0], ry - gp[1]) > 0.3:
                    st["gpos"], st["pin"], st["stall"] = (rx, ry, now, rg.id), PUSH_IN, 0
                elif now - gp[2] > 1.5:
                    st["pin"] = max(0.3, st.get("pin", PUSH_IN) - 0.4)
                    st["gpos"] = (gp[0], gp[1], now - 1.0, gp[3])
                    st["stall"] = st.get("stall", 0) + 1
                pin = st.get("pin", PUSH_IN)
                tx, ty = rx - dx * pin, ry - dy * pin
                mode = "push"
                st.pop("cdir", None)
                st.pop("circle_t0", None)
                st.pop("cprog", None)
                if not getattr(h, "behind_t", None):
                    h.behind_t = now                     # the push proper starts now
                if st.get("stall", 0) >= 4 and rg.id not in h.__dict__.setdefault("speared", set()) \
                        and now - st.get("hit_t", 0) > 6:
                    rh = self.g.m.read(rg.ptr + O_HP, 4)
                    ghp = struct.unpack("<f", rh)[0] if rh and len(rh) == 4 else 0.0
                    if ghp >= rg.maxhp - 0.01:
                        mg.order([v], rg, None, None)    # one spear: it jumps ~3 tiles straight away
                        st["spear"] = (rg.id, ghp, now, rg.ptr)
                        h.__dict__.setdefault("speared", set()).add(rg.id)
                        st["hit_t"], st["stall"] = now, 0
                        continue
            last = mt.get(vid, (0.0, None))
            if now - last[0] > 0.25 and (last[1] is None or math.hypot(tx - last[1][0], ty - last[1][1]) > 0.4
                                         or now - last[0] > 1.5):
                mg.move([v], tx, ty)
                mt[vid] = (now, (tx, ty))
            h.mode = mode
        self.keep_off_herd(h, mem, cx, cy, pushers, now, mg)
        if PUSH_DEBUG and now - getattr(h, "dbg_t", 0) > 2.0:
            h.dbg_t = now
            tcx, tcy = self.tc_anchor
            self.say("PUSHDBG herd %s n=%d mode=%s c->tc=%.1f back=%.1f" % (
                h.key, len(mem), getattr(h, "mode", "-"), math.hypot(cx - tcx, cy - tcy), back))

    @staticmethod
    def segment_near_herd(x0, y0, x1, y1, mem, r):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        for p in mem:
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[1] - x0) * dx + (p[2] - y0) * dy) / L2))
            if math.hypot(x0 + k * dx - p[1], y0 + k * dy - p[2]) < r:
                return True
        return False

    def keep_off_herd(self, h, mem, cx, cy, pushers, now, mg):
        """The user: a villager walking through the herd being pushed makes it jump all over the place.
        Any other villager of ours coming within ~3.2 tiles of one of its gazelles is sent round the
        herd instead, on the side of where it was going (its next order brings it back to work)."""
        import struct
        hr = max(math.hypot(p[1] - cx, p[2] - cy) for p in mem)
        ring = hr + 4.5
        dt = self.__dict__.setdefault("_detour_t", {})
        for v in list(self.s.villagers):
            if v.id in pushers or v.id in self.leads or v.id in self.defenders                     or any(L.lurer == v.id for L in self.lures.values())                     or math.hypot(v.x - cx, v.y - cy) > ring + 6 or now - dt.get(v.id, 0) < 0.8:
                continue
            rv = self.g.m.read(v.ptr + O_X, 8)
            if not rv or len(rv) < 8:
                continue
            vx, vy = struct.unpack("<ff", rv)
            vp = self.__dict__.setdefault("_vprev", {})
            prev = vp.get(v.id)
            vp[v.id] = (vx, vy, now)
            near = min(math.hypot(vx - p[1], vy - p[2]) for p in mem)
            if near > 5.0:
                continue                                  # (orders reach the game late: act from 5 tiles)
            dest = None
            act = self.r.action(v)
            if act and act[1] and act[2] in (4, 0x0B):   # walking to a target object
                rd = self.g.m.read(act[1] + O_X, 8)
                if rd and len(rd) == 8:
                    dest = struct.unpack("<ff", rd)
            if dest is None and prev is not None and 0.05 < now - prev[2] < 1.5:
                sx, sy = (vx - prev[0]) / (now - prev[2]), (vy - prev[1]) / (now - prev[2])
                if math.hypot(sx, sy) > 0.3:             # a plain move: carry on the way it walks
                    dest = (vx + sx * 8, vy + sy * 8)
            if dest is None:
                continue                                  # standing / working: leave it
            if near > 3.2 and math.hypot(dest[0] - cx, dest[1] - cy) > math.hypot(vx - cx, vy - cy) \
                    and not self.segment_near_herd(vx, vy, dest[0], dest[1], mem, 3.2):
                continue                                  # 3-5 tiles away and not walking into it
            if any(abs(dest[0] - p[1]) < 0.6 and abs(dest[1] - p[2]) < 0.6 for p in mem):
                continue                                  # it was sent at the herd itself
            a_v = math.atan2(vy - cy, vx - cx)
            a_d = math.atan2(dest[1] - cy, dest[0] - cx)
            turn = (a_d - a_v + math.pi) % (2 * math.pi) - math.pi
            a = a_v + max(-1.0, min(1.0, turn))
            tx, ty = cx + math.cos(a) * ring, cy + math.sin(a) * ring
            mg.move([v], tx, ty)
            dt[v.id] = now
            if now - getattr(self, "_detour_say", 0) > 10:
                self._detour_say = now
                self.say("villager #%d sent round herd %s (it walked into it)" % (v.id, h.key))

    # ---------------------------------------------------------------- fast control loop
    def micro(self, mg=None):
        """Runs on its own thread (~20 times a second, own hook connection `mg`), independent of the
        brain tick: the fast control of the brain.tasks tasks (herd pushers, the lurer, the killers)."""
        if not self.tc_anchor or not hasattr(self, "_by_id"):
            return
        if mg is not None and self.wfast is None:
            self.wfast = GameWorld(self, mg)
        w = self.wfast if mg is not None else self.wslow
        now = time.time()
        if os.environ.get("AOESOLO_LAG_PROBE") == "1":
            try:
                self.lag_probe_step(w.g)
            except Exception as e:  # noqa: BLE001
                if now - getattr(self, "_lagp_err_t", 0) > 10:
                    self._lagp_err_t = now
                    self.say("lag probe error: %r" % (e,))
        if demo_dump.enabled():
            try:
                demo_dump.lure_sample(self, w)
            except Exception as e:  # noqa: BLE001
                if now - getattr(self, "_demo_err_t", 0) > 10:
                    self._demo_err_t = now
                    self.say("DEMO lure sample error: %r" % (e,))
        try:
            self.pulse_step(w.g)
        except Exception as e:  # noqa: BLE001
            if now - getattr(self, "_pulse_err_t", 0) > 10:
                self._pulse_err_t = now
                self.say("pulse error: %r" % (e,))
        for key, task in list(self.ntasks.items()):
            if task.done or task.failed:
                continue
            try:
                task.micro(w, w)
            except Exception as e:  # noqa: BLE001
                if now - getattr(self, "_micro_err_t", 0) > 10:
                    self._micro_err_t = now
                    self.say("task %s micro error: %r" % (key, e))
                continue
            if key[0] == "herd" and task.state == "push":
                h = self.herds.get(key[1])
                try:
                    mem = [(None, x, y) for (_, x, y, _) in task.members(w)]
                except Exception:  # noqa: BLE001
                    mem = []
                if h is not None and mem:
                    cx = sum(p[1] for p in mem) / len(mem)
                    cy = sum(p[2] for p in mem) / len(mem)
                    self.keep_off_herd(h, mem, cx, cy, task.pushers, now, mg or self.g)

    def oracle_diag(self, outdir):
        import json
        import types
        D = self.__dict__.setdefault("_oracle", {"next": [100, 300, 600], "out": []})
        t = self.now()
        if not D["next"] or t < D["next"][0]:
            return
        D["next"].pop(0)
        r, tc, W, H = self.r, self.tc(), self.r.W, self.r.H
        allobjs = r.objects()
        full = types.SimpleNamespace(
            r=r, mine=[o for o in allobjs if o.owner == self.me],
            gaia=[o for o in allobjs if o.owner == 0 and o.kind in (gs.KIND_STATIC, gs.KIND_DOPPEL, gs.KIND_TREE)],
            enemy=[], enemy_buildings_seen=[o for o in allobjs if o.owner not in (0, self.me) and o.kind == gs.KIND_BUILDING])
        pm_full = pathing.PassMap(full)
        # the black ground within 40 tiles of the TC: what the oracle says about it
        un = enterable = blocked = 0
        for y in range(max(0, int(tc.y) - 40), min(H, int(tc.y) + 41)):
            for x in range(max(0, int(tc.x) - 40), min(W, int(tc.x) + 41)):
                if (x + 0.5 - tc.x) ** 2 + (y + 0.5 - tc.y) ** 2 > 1600 or self.s.explored(x, y):
                    continue
                un += 1
                if pm_full.passable(x, y):
                    enterable += 1
                else:
                    blocked += 1
        kc = self.wall_keep_clear()
        tx0, ty0 = int(math.floor(tc.x - 1.5)), int(math.floor(tc.y - 1.5))
        refused = [(tx0 - 3, ty0 - 3, tx0 + 6, ty0 + 6)]
        rows = {}
        for R in (14, 26, 40):
            p_bot = walling.plan_cut(self.pm, (tc.x, tc.y), [], R, keep_clear=kc, uncuttable_rects=refused,
                                     explored=lambda x, y: bool(self.s.explored(x, y)))
            p_or = walling.plan_cut(pm_full, (tc.x, tc.y), [], R, keep_clear=kc, uncuttable_rects=refused,
                                    explored=lambda x, y: True)
            cb = {tuple(c) for c in getattr(p_bot, "cut", [])}
            co = {tuple(c) for c in getattr(p_or, "cut", [])}
            unx = sum(1 for (x, y) in cb if not self.s.explored(x, y))
            rows[str(R)] = {"bot": [len(p_bot.slots), len(p_bot.leaks), p_bot.region_size, len(cb), unx],
                            "oracle": [len(p_or.slots), len(p_or.leaks), p_or.region_size, len(co)],
                            "cut_overlap": len(cb & co)}
        rec = {"t": round(t, 1), "black_r40": un, "black_enterable": enterable, "black_blocked": blocked, "plans": rows}
        D["out"].append(rec)
        self.say("ORACLE t=%.0f black within 40: %d (enterable %d, blocked %d) | %s" % (t, un, enterable, blocked, json.dumps(rows)))
        os.makedirs(outdir, exist_ok=True)
        json.dump(D["out"], open(os.path.join(outdir, "P%d_oracle.json" % self.me), "w"))

    def e_test(self):
        """Tests only (AOESOLO_ETEST): the house-foundation trap's facts. A villager 10+ tiles away is ordered to
        build a house: when does the foundation appear? Then the foundation is deleted: how much wood comes back?"""
        D = self.__dict__.setdefault("_etest", {"phase": "wait", "n": 0})
        t = self.now()
        if D["phase"] == "wait":
            if t < 90 + 40 * D["n"] or D["n"] >= 4 or not self.can_afford(wood=40):
                return
            tc = self.tc()
            vs = sorted(self.s.villagers, key=lambda v: -v.dist(tc.x, tc.y))
            if not vs:
                return
            v = vs[0]
            spot = None
            for dx in range(-12, 13):
                for dy in range(-12, 13):
                    x0, y0 = int(tc.x + dx), int(tc.y + dy)
                    if 6 <= math.hypot(dx, dy) <= 12 and self.footprint_ok(gs.HOUSE, x0, y0) and                             math.hypot(x0 + 1 - v.x, y0 + 1 - v.y) >= 10 and self.g.can_place(self.me, gs.HOUSE, x0 + 1.0, y0 + 1.0):
                        spot = (x0 + 1.0, y0 + 1.0)
                        break
                if spot:
                    break
            if not spot:
                return
            D.update(phase="placed", t0=t, wall0=time.time(), spot=spot, vid=v.id, wood0=self.res(gs.WOOD), vdist=v.dist(*spot), seen=None)
            self.g.build([v], gs.HOUSE, spot[0], spot[1])
            self.say("ETEST %d: build ordered at (%.1f,%.1f), villager #%d %.1f tiles away, wood %d" % (D["n"], spot[0], spot[1], v.id, D["vdist"], D["wood0"]))
            return
        spot = D["spot"]
        found = [o for o in self.s.mine if o.type == gs.HOUSE and abs(o.x - spot[0]) < 1.1 and abs(o.y - spot[1]) < 1.1]
        if D["phase"] == "placed":
            if found and D["seen"] is None:
                D["seen"] = t
                D["obj"] = found[0].id
                v = self._by_id.get(D["vid"])
                self.say("ETEST %d: foundation exists after %.2f s game / %.2f s real (villager %.1f tiles away, hp %.0f), wood %d (was %d)" % (
                    D["n"], t - D["t0"], time.time() - D["wall0"], v.dist(*spot) if v else -1, found[0].hp, self.res(gs.WOOD), D["wood0"]))
                # the villager goes back to work at once: does the foundation stay?
                if v is not None:
                    self.g.move([v], v.x, v.y)
            if D["seen"] is not None and t - D["seen"] >= 6:
                if found:
                    D.update(phase="deleted", t1=t, wood1=self.res(gs.WOOD), hp1=found[0].hp)
                    self.g.delete(found[0])
                    self.say("ETEST %d: foundation still there after 6 s (hp %.0f), deleting; wood %d" % (D["n"], found[0].hp, D["wood1"]))
                else:
                    self.say("ETEST %d: foundation GONE within 6 s of the villager being sent back" % D["n"])
                    D.update(phase="wait", n=D["n"] + 1)
            elif t - D["t0"] > 15 and D["seen"] is None:
                self.say("ETEST %d: no foundation 15 s after the order (refused?)" % D["n"])
                D.update(phase="wait", n=D["n"] + 1)
        elif D["phase"] == "deleted":
            if not found or t - D["t1"] > 4:
                self.say("ETEST %d: after delete: foundation %s, wood %d (before delete %d, before order %d) -> refund %d" % (
                    D["n"], "gone" if not found else "STILL THERE", self.res(gs.WOOD), D["wood1"], D["wood0"], self.res(gs.WOOD) - D["wood1"]))
                D.update(phase="wait", n=D["n"] + 1)

    def squeeze_test(self, outdir):
        """Tests only: can a villager slip diagonally between two obstacles that touch at a corner? It is
        taken to the inside tile of a corner squeeze the leak check found, then sent to the outside tile next
        to it diagonally (1.4 tiles): through the squeeze that is ~2 s; round the wall it is long or never."""
        import json
        D = self.__dict__.setdefault("_sq", {"trial": None, "done": [], "used": set()})
        t = self.now()
        if D["trial"] is None:
            if len(D["done"]) >= 6:
                return
            for k in self.__dict__.get("_sq_cands", []):
                if k in D["used"]:
                    continue
                D["used"].add(k)
                ax, ay, bx, by = k
                vs = sorted(self.s.villagers, key=lambda v: math.hypot(v.x - ax, v.y - ay))
                if not vs or math.hypot(vs[0].x - ax, vs[0].y - ay) > 25:
                    continue
                D["trial"] = {"vid": vs[0].id, "a": (ax + 0.5, ay + 0.5), "b": (bx + 0.5, by + 0.5), "phase": "go", "t0": t}
                self.g.move([vs[0]], ax + 0.5, ay + 0.5)
                return
            return
        tr = D["trial"]
        v = self._by_id.get(tr["vid"])
        if v is None:
            D["trial"] = None
            return
        if tr["phase"] == "go":
            if math.hypot(v.x - tr["a"][0], v.y - tr["a"][1]) < 0.6:
                tr["phase"], tr["t1"] = "cross", t
                self.g.move([v], tr["b"][0], tr["b"][1])
            elif t - tr["t0"] > 40:
                D["trial"] = None
            else:
                self.g.move([v], tr["a"][0], tr["a"][1])
            return
        d = math.hypot(v.x - tr["b"][0], v.y - tr["b"][1])
        if d < 0.6 or t - tr["t1"] > 15:
            tr["arrived"], tr["secs"] = d < 0.6, round(t - tr["t1"], 1)
            D["done"].append(tr)
            D["trial"] = None
            self.say("SQUEEZETEST corner squeeze (%.1f,%.1f)->(%.1f,%.1f): %s after %.1f s -> %s" % (
                tr["a"][0], tr["a"][1], tr["b"][0], tr["b"][1], "arrived" if tr["arrived"] else "not arrived", tr["secs"],
                "SLIPPED THROUGH" if tr["arrived"] and tr["secs"] < 5 else ("went round" if tr["arrived"] else "blocked")))
            os.makedirs(outdir, exist_ok=True)
            json.dump(D["done"], open(os.path.join(outdir, "P%d_squeeze.json" % self.me), "w"), default=list)
        else:
            self.g.move([v], tr["b"][0], tr["b"][1])

    def farm_walk_test(self, outdir):
        """Tests only: does a villager walk ACROSS a farm or round it? One of ours goes to a point 3 tiles on one
        side of a finished farm, then is sent to the point 3 tiles on the opposite side; the nearest it came to
        the farm's centre on the way says it (on the farm: < 1; round it: > 1.6)."""
        import json
        D = self.__dict__.setdefault("_fw", {"trial": None, "done": [], "used": set(), "t_next": 0.0})
        t = self.now()
        if D["trial"] is None:
            if t < D["t_next"] or len(D["done"]) >= 8:
                return
            farms = [f for f in self.complete(gs.FARM) if f.id not in D["used"]]
            vs = [v for v in self.s.villagers if self.role_of(v) == "wood"] if hasattr(self, "role_of") else []
            vs = vs or sorted(self.s.villagers, key=lambda v: v.id)[-3:]
            if not farms or not vs:
                return
            for f in farms:
                for ax, ay in ((1, 0), (0, 1)):
                    a = (f.x - 3.2 * ax, f.y - 3.2 * ay)
                    b = (f.x + 3.2 * ax, f.y + 3.2 * ay)
                    if self.pm.passable(int(a[0]), int(a[1])) and self.pm.passable(int(b[0]), int(b[1])):
                        D["used"].add(f.id)
                        v = vs[0]
                        D["trial"] = {"vid": v.id, "farm": [f.x, f.y], "a": a, "b": b, "phase": "go", "t0": t, "min": 99.0}
                        self.g.move([v], a[0], a[1])
                        return
                D["used"].add(f.id)
            return
        tr = D["trial"]
        v = self._by_id.get(tr["vid"])
        if v is None:
            D["trial"] = None
            return
        if tr["phase"] == "go":
            if math.hypot(v.x - tr["a"][0], v.y - tr["a"][1]) < 0.8:
                tr["phase"], tr["t1"] = "cross", t
                self.g.move([v], tr["b"][0], tr["b"][1])
            elif t - tr["t0"] > 25:
                D["trial"] = None
            else:
                self.g.move([v], tr["a"][0], tr["a"][1])
            return
        tr["min"] = min(tr["min"], math.hypot(v.x - tr["farm"][0], v.y - tr["farm"][1]))
        if math.hypot(v.x - tr["b"][0], v.y - tr["b"][1]) < 0.8 or t - tr["t1"] > 20:
            tr["arrived"] = math.hypot(v.x - tr["b"][0], v.y - tr["b"][1]) < 0.8
            tr["secs"] = round(t - tr["t1"], 1)
            D["done"].append(tr)
            D["trial"] = None
            D["t_next"] = t + 3
            self.say("FARMWALK farm (%.1f,%.1f): nearest to its centre %.2f tiles, %s in %.1f s -> %s" % (
                tr["farm"][0], tr["farm"][1], tr["min"], "arrived" if tr["arrived"] else "not arrived", tr["secs"],
                "WALKED ACROSS the farm" if tr["min"] < 1.0 else ("went round it" if tr["min"] > 1.6 else "unclear")))
            os.makedirs(outdir, exist_ok=True)
            json.dump(D["done"], open(os.path.join(outdir, "P%d_farmwalk.json" % self.me), "w"), default=list)
        else:
            self.g.move([v], tr["b"][0], tr["b"][1])

    def walk_test(self, outdir):
        import json
        import random
        D = self.__dict__.setdefault("_walk", {"trial": None, "done": [], "rng": random.Random(self.me * 17 + 3), "t_next": 50.0})
        t = self.now()
        r, W, H = self.r, self.r.W, self.r.H
        if D["trial"] is None:
            if t < D["t_next"] or len(D["done"]) >= 8:
                return
            vs = sorted(self.s.villagers, key=lambda v: v.id)
            if not vs:
                return
            v = vs[-1]
            e0 = r.elev_at(v.x, v.y)
            for _ in range(400):
                tx = v.x + D["rng"].uniform(-18, 18)
                ty = v.y + D["rng"].uniform(-18, 18)
                if not (2 <= tx < W - 2 and 2 <= ty < H - 2) or not self.s.explored(tx, ty) or not self.pm.passable(int(tx), int(ty)):
                    continue
                if abs(r.elev_at(tx, ty) - e0) >= 2 and r.terrain_at(tx, ty) not in gs.FOREST_TERRAINS:
                    dist = math.hypot(tx - v.x, ty - v.y)
                    if 8 <= dist <= 20:
                        D["trial"] = {"vid": v.id, "t0": t, "x0": v.x, "y0": v.y, "e0": e0, "tx": tx, "ty": ty, "e1": r.elev_at(tx, ty),
                                      "dist": dist}
                        break
            return
        tr = D["trial"]
        v = self._by_id.get(tr["vid"])
        if v is None:
            D["trial"] = None
            return
        if t - tr["t0"] < 24.0:
            self.g.move([v], tr["tx"], tr["ty"])
            tr["best"] = min(tr.get("best", 99.0), math.hypot(v.x - tr["tx"], v.y - tr["ty"]))
            return
        tr["final"] = math.hypot(v.x - tr["tx"], v.y - tr["ty"])
        tr["ok"] = tr["best"] < 2.5
        # steps of elevation / slope tiles along the straight line
        n = 40
        elevs = [r.elev_at(tr["x0"] + (tr["tx"] - tr["x0"]) * k / n, tr["y0"] + (tr["ty"] - tr["y0"]) * k / n) for k in range(n + 1)]
        shapes = [r.shape_at(tr["x0"] + (tr["tx"] - tr["x0"]) * k / n, tr["y0"] + (tr["ty"] - tr["y0"]) * k / n) for k in range(n + 1)]
        tr["steps"] = sum(1 for a, b in zip(elevs, elevs[1:]) if a != b)
        tr["slope_tiles"] = sum(1 for sh in shapes if sh)
        D["done"].append(tr)
        D["trial"] = None
        D["t_next"] = t + 4.0
        self.say("WALKTEST dist %.0f elev %d->%d (%d steps, %d slope tiles on the line): best %.1f final %.1f -> %s" % (
            tr["dist"], tr["e0"], tr["e1"], tr["steps"], tr["slope_tiles"], tr["best"], tr["final"], "ARRIVED" if tr["ok"] else "did not arrive"))
        os.makedirs(outdir, exist_ok=True)
        json.dump(D["done"], open(os.path.join(outdir, "P%d_walk.json" % self.me), "w"))

    def terrain_diag(self, outdir):
        import json
        import random
        D = self.__dict__.setdefault("_terr", {"rows": [], "done": False, "rng": random.Random(self.me * 31 + 7)})
        if D["done"]:
            return
        r, tc, W, H = self.r, self.tc(), self.r.W, self.r.H
        for _ in range(60):
            if len(D["rows"]) >= 1500:
                break
            size = 2 if len(D["rows"]) % 2 == 0 else 3
            btype = gs.HOUSE if size == 2 else gs.GRANARY
            x0 = int(tc.x + D["rng"].uniform(-30, 30))
            y0 = int(tc.y + D["rng"].uniform(-30, 30))
            if not (1 <= x0 and x0 + size < W - 1 and 1 <= y0 and y0 + size < H - 1):
                continue
            tiles = [(x0 + i, y0 + j) for j in range(size) for i in range(size)]
            if not all(self.s.explored(x, y) for x, y in tiles):
                continue
            occ = any(self.grid.occ[y * W + x] for x, y in tiles)
            ok = bool(self.g.can_place(self.me, btype, x0 + size / 2.0, y0 + size / 2.0))
            D["rows"].append({"s": size, "x": x0, "y": y0, "ok": ok, "occ": occ,
                              "shape": [r.shape_at(x, y) for x, y in tiles], "elev": [r.elev_at(x, y) for x, y in tiles],
                              "terr": [r.terrain_at(x, y) for x, y in tiles]})
        if len(D["rows"]) >= 1500:
            D["done"] = True
            os.makedirs(outdir, exist_ok=True)
            path = os.path.join(outdir, "P%d_terrain.json" % self.me)
            json.dump(D["rows"], open(path, "w"))
            self.say("TERRDIAG %d footprints -> %s" % (len(D["rows"]), path))

    def vis_diag(self):
        t = self.now()
        if t - getattr(self, "_visdiag_t", -999) < 60 and not (self.ticks <= 3):
            return
        self._visdiag_t = t
        s = self.s
        W, H = self.r.W, self.r.H
        allobjs_tcs = [o for o in getattr(s, "_ally_tc_objs", [])]
        rows = []
        for (ax, ay) in getattr(s, "ally_tcs", []) or []:
            n255 = n0 = nv = 0
            for dy in range(-6, 7):
                for dx in range(-6, 7):
                    x, y = int(ax) + dx, int(ay) + dy
                    if 0 <= x < W and 0 <= y < H and dx * dx + dy * dy <= 36:
                        v = s.vis[y * W + x]
                        if v == 255:
                            n255 += 1
                        elif v == 0:
                            n0 += 1
                        else:
                            nv += 1
            near = min((o.dist(ax, ay) for o in s.mine), default=999.0)
            rows.append("ally TC (%.0f,%.0f): unexplored %d, fog %d, visible %d | our nearest object %.0f tiles" % (
                ax, ay, n255, n0, nv, near))
        tot = W * H
        n_exp = sum(1 for b in s.vis if b != 255)
        n_vis = sum(1 for b in s.vis if b != 255 and b > 0)
        wr = {}
        for pid in [self.me] + sorted(getattr(s, "ally_ids", []) or []):
            try:
                st = self.g.research_states(pid) or []
                wr["P%d" % pid] = st[114] if len(st) > 114 else None
            except Exception:  # noqa: BLE001
                wr["P%d" % pid] = None
        self.say("VISDIAG map explored %.1f %%, visible now %.1f %% | Writing(114) state %s | %s" % (
            100.0 * n_exp / tot, 100.0 * n_vis / tot, wr, " || ".join(rows) or "no ally"))
        try:
            import struct
            m = self.g.m
            masks = {}
            for pid in [self.me] + sorted(getattr(s, "ally_ids", []) or []):
                pp = self.g.player_ptr(pid)
                masks[pid] = (m.u32(pp + 0xD4), m.u32(pp + 0xD8)) if pp else (0, 0)
            em, vm = masks[self.me]
            rp = m.read(0x7D70C8, 4 * H)
            rowp = struct.unpack("<%dI" % H, rp) if rp else ()
            out = []
            for (ax, ay) in getattr(s, "ally_tcs", []) or []:
                ne = nv = n = 0
                for y in range(max(0, int(ay) - 6), min(H, int(ay) + 7)):
                    if y >= len(rowp) or not rowp[y]:
                        continue
                    raw = m.read(rowp[y], 4 * W)
                    if not raw:
                        continue
                    row = struct.unpack("<%dI" % W, raw)
                    for x in range(max(0, int(ax) - 6), min(W, int(ax) + 7)):
                        if (x - int(ax)) ** 2 + (y - int(ay)) ** 2 > 36:
                            continue
                        n += 1
                        v = row[x]
                        ne += 1 if v & em else 0
                        nv += 1 if v & vm else 0
                out.append("ally TC (%.0f,%.0f): %d tiles, explored by our mask %d, visible by our mask %d" % (ax, ay, n, ne, nv))
            self.say("VISMASK masks %s | %s" % (
                " ".join("P%d explored %08x visible %08x" % (pid, a, b) for pid, (a, b) in masks.items()),
                " || ".join(out) or "no ally"))
        except Exception as e:  # noqa: BLE001
            self.say("VISMASK error: %r" % (e,))

    def lag_probe_step(self, game):
        import struct
        P = self.__dict__.setdefault("_lagp", {"g": [], "r": [], "dt": [], "pend": None, "next": 0.0,
                                                "hist": {}, "last": None, "say": -99})
        now = game.m.u32(game.world() + 4) / 1000.0
        wall = time.time()
        if P["last"] is not None:
            P["dt"].append(wall - P["last"])
            del P["dt"][:-200]
        P["last"] = wall
        vs = list(self.s.villagers) if self.s else []
        pos = {}
        for v in vs[:12]:
            raw = game.m.read(v.ptr, O_X + 8)
            if raw and len(raw) >= O_X + 8:
                pos[v.id] = struct.unpack_from("<ff", raw, O_X)
        for vid, p in pos.items():
            h = P["hist"].setdefault(vid, [])
            h.append((now, p[0], p[1]))
            del h[:-30]
        pend = P["pend"]
        if pend is not None:
            vid, t_cmd, w_cmd, x0, y0 = pend
            p = pos.get(vid)
            if p is None or now - t_cmd > 8.0:
                P["pend"] = None
            elif math.hypot(p[0] - x0, p[1] - y0) > 0.1:
                P["g"].append(now - t_cmd)
                P["r"].append(wall - w_cmd)
                P["pend"] = None
                P["next"] = now + 5.0
        elif now >= P["next"] and self.tc() is not None:
            for v in vs[:12]:
                h = P["hist"].get(v.id, [])
                if len(h) < 6 or self.role_name(v.id) not in ("wood", "berry", "farm", "gold"):
                    continue
                if any(math.hypot(x - h[-1][1], y - h[-1][2]) > 0.02 for (_t, x, y) in h[-6:]):
                    continue                              # (must stand still: chopping / picking)
                x0, y0 = h[-1][1], h[-1][2]
                for a in range(8):
                    ang = a * math.pi / 4
                    gx, gy = x0 + 2.5 * math.cos(ang), y0 + 2.5 * math.sin(ang)
                    if self.pm.passable(int(gx), int(gy)):
                        break
                else:
                    continue
                game.move([v], gx, gy)
                P["pend"] = (v.id, now, wall, x0, y0)
                break
        if now - P["say"] > 60 and len(P["g"]) >= 3:
            P["say"] = now
            g, r, dt = sorted(P["g"]), sorted(P["r"]), sorted(P["dt"])
            q = lambda a, f: a[min(len(a) - 1, int(f * len(a)))]   # noqa: E731
            self.say("LAGPROBE n=%d | game s: median %.2f p10 %.2f p90 %.2f | real s: median %.2f p10 %.2f p90 %.2f | "
                     "fast loop dt median %.3f s | game/real %.2f" % (
                         len(g), q(g, 0.5), q(g, 0.1), q(g, 0.9), q(r, 0.5), q(r, 0.1), q(r, 0.9), q(dt, 0.5),
                         (sum(P["g"]) / max(1e-6, sum(P["r"])))))

    def pulse_step(self, game):
        """Fast loop: the shot-synced side steps of the archers archer_fight put in self._pulse."""
        pulse = self.__dict__.get("_pulse")
        if not pulse:
            return
        import struct
        try:
            now = game.m.u32(game.world() + 4) / 1000.0
        except Exception:  # noqa: BLE001
            return
        P = self.__dict__.setdefault("_pulse_stats", {"lags": [], "shots": 0, "dodges": 0, "skips": 0})
        lags = P["lags"]
        L = sorted(lags)[len(lags) // 2] if len(lags) >= 5 else 0.6
        for uid, st in list(pulse.items()):
            u = self._by_id.get(uid)
            tgt = next((e for e in self.s.enemy if e.id == st.get("tgt")), None)   # (_by_id holds ours only)
            if u is None or tgt is None or now - st.get("seen", now) > 4.0:
                del pulse[uid]
                continue
            raw = game.m.read(u.ptr, 0x1B8)
            traw = game.m.read(tgt.ptr, 0x40)
            if not raw or len(raw) < 0x1B8 or not traw:
                continue
            timer, = struct.unpack_from("<f", raw, 0x1B4)
            x, y = struct.unpack_from("<ff", raw, O_X)
            tx, ty = struct.unpack_from("<ff", traw, O_X)
            prev = st.get("timer")
            st["timer"] = timer
            st["peak"] = max(st.get("peak", 0.0), timer)
            shot = prev is not None and timer > prev + 0.3
            # a fixed rhythm (pulse1: the order lag at x2 is ~1.46 game s, about one reload - an order sent
            # after a shot lands at the next one): shoot for one reload + 0.3 s, step aside PULSE_MOVE s, shoot
            # again... every order is late by the same lag, so the rhythm itself stays
            if shot:
                P["shots"] += 1
            R = st.get("peak") or 1.4
            t_ph = st.setdefault("t_ph", now)
            if st["ph"] == "attack":
                if now - t_ph < R + 0.3:
                    continue
                dx, dy = unit(x - tx, y - ty)
                side = st.get("side", 1) * -1
                st["side"] = side
                W, H = self.r.W, self.r.H
                gx = min(W - 2.0, max(1.0, x - dy * PULSE_STEP * side))
                gy = min(H - 2.0, max(1.0, y + dx * PULSE_STEP * side))
                game.move([u], gx, gy)
                st.update(ph="dodge", t_ph=now, t_mv=now, x0=x, y0=y, measured=False)
                P["dodges"] += 1
            else:
                if not st.get("measured") and math.hypot(x - st["x0"], y - st["y0"]) > 0.2:
                    st["measured"] = True
                    lags.append(now - st["t_mv"])
                    del lags[:-40]
                if now - t_ph >= PULSE_MOVE:
                    game.order([u], tgt)
                    st.update(ph="attack", t_ph=now)
        t = now
        if t - P.get("say", -99) > 60 and P["shots"]:
            P["say"] = t
            self.say("PULSE shots %d, side steps %d | order lag median %.2f s (%d measured)" % (
                P["shots"], P["dodges"], L, len(lags)))

    def hand_over_lure(self, eid, L, v, why):
        """The lurer is down to <= 12 hp (one more blow kills it): a fresh villager takes the lure over
        (at most twice per elephant), the hurt one waits at the TC with the killers."""
        L.handovers = getattr(L, "handovers", 0) + 1
        if L.handovers > 2:
            self.lure_failed.add(eid)
            del self.lures[eid]
            self.say("elephant #%d: %s and the lurer is hurt (%.0f hp) again: lure dropped" % (eid, why, v.hp))
            return
        L.__dict__.setdefault("hurt", set()).add(v.id)
        L.lurer, L.state, L.t = None, "provoke", self.now()
        self.leads.pop(v.id, None)
        self.say("elephant #%d: %s and the lurer #%d is hurt (%.0f hp): a fresh villager takes over" % (
            eid, why, v.id, v.hp))
        tc = self.tc()
        if tc is not None:
            ux, uy = unit(tc.x - v.x, tc.y - v.y)
            self.move([v], tc.x - ux * 3.5, tc.y - uy * 3.5)

    def open_dir(self, x, y, dx, dy, ax, ay):
        """(dx, dy, length): the direction turned as little as needed so the way is walkable for at
        least 4 tiles, never towards the elephant (ax, ay = away from it), and how far to send the
        lurer along it (up to 6 tiles, stopping short of trees / buildings: a move order into the TC
        or a forest leaves the villager standing, and the elephant catches it)."""
        pm = getattr(self, "pm", None)
        if pm is None:
            return dx, dy, 4.0
        best = (dx, dy, 0.0)
        for deg in (0, 20, -20, 40, -40, 60, -60, 80, -80, 100, -100, 120, -120):
            a = math.radians(deg)
            ux, uy = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
            if ux * ax + uy * ay < -0.1:
                continue
            free = 0.0
            for i in range(1, 13):
                k = 0.5 * i
                if not pm.passable(int(x + ux * k), int(y + uy * k)):
                    break
                free = k
            if free >= 4.0:
                return ux, uy, free
            if free > best[2]:
                best = (ux, uy, free)
        return best[0], best[1], max(1.5, best[2])

    def lure_elephant_pos(self, L):
        """(x, y) of the lured elephant read through its pointer (it may be just outside the lurer's
        sight), or None once it is gone / dead."""
        import struct
        ptr = getattr(L, "eptr", None)
        if not ptr:
            return None
        r = self.g.m.read(ptr + O_X, 8)
        h = self.g.m.read(ptr + O_HP, 4)
        if not r or len(r) < 8 or not h or len(h) < 4:
            return None
        x, y = struct.unpack("<ff", r)
        hp = struct.unpack("<f", h)[0]
        if hp <= 0 or not (0 <= x < self.r.W and 0 <= y < self.r.H):
            return None
        return x, y

    def lure_hop(self, v, tc):
        """The lurer jumps 3 tiles towards the TC (the elephant follows)."""
        if not self.recent(v.id, ("hop",), within=0.8):
            ux, uy = unit(tc.x - v.x, tc.y - v.y)
            ux, uy, run = self.open_dir(v.x, v.y, ux, uy, ux, uy)
            run = min(run, 3.0)
            self.move([v], v.x + ux * run, v.y + uy * run)
            self.mark([v], ("hop",))

    # ---------------------------------------------------------------- scouting
    def lion_near(self, x, y, r=LION_SAFE):
        for lx, ly, _ in self.lions.values():
            if math.hypot(lx - x, ly - y) < r:
                return (lx, ly)
        return None

    def path_meets_lion(self, x0, y0, x1, y1):
        """True if walking straight from (x0,y0) to (x1,y1) passes inside a lion's trigger range."""
        for lx, ly, _ in self.lions.values():
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((lx - x0) * dx + (ly - y0) * dy) / L2))
            if math.hypot(x0 + k * dx - lx, y0 + k * dy - ly) < LION_SAFE:
                return True
        return False

    # ---------------------------------------------------------------- staged chase (tests only)
    def cheat(self, code):
        """A cheat word through the game's own chat-line parser (aoemem.Game.cheat): the parser submits the cheat
        as a game command, so every game in the match applies it (no desync)."""
        try:
            r, was = self.g.cheat(code)
            self.say("CHEAT %s: call %s, Allow Cheats byte %s" % (code, r, was))
            return True
        except Exception as e:  # noqa: BLE001
            self.say("CHEAT %s failed: %r" % (code, e))
            return False

    def stage_cheats(self):
        """AOESOLO_CHEATS=1: the staged setup in a minute instead of twelve - STEROIDS once (instant build and
        train), WOODSTOCK / PEPPERONI PIZZA whenever wood / food are under 500 (every 6 s at most), and a check
        that the first WOODSTOCK took (the lobby's Allow Cheats byte)."""
        if not os.environ.get("AOESOLO_CHEATS"):
            return
        t = self.now()
        C = self.__dict__.setdefault("_cheat", {"t": -99, "n": 0, "wood0": None, "ok": None})
        if t < 2 or t - C["t"] < 6:
            return
        wood, food = self.res(gs.WOOD), self.res(gs.FOOD)
        if C["wood0"] is not None and C["ok"] is None:
            C["ok"] = wood >= C["wood0"] + 900
            self.say("CHEAT check: wood %d -> %d: %s" % (C["wood0"], wood, "cheats work" if C["ok"] else "NO EFFECT (Allow Cheats off?)"))
        if C["n"] == 0:
            C["wood0"] = wood
            self.cheat("WOODSTOCK")
            if not os.environ.get("AOESOLO_NOSTEROIDS"):
                self.cheat("STEROIDS")
            C["n"], C["t"] = 1, t
            return
        if wood < 500:
            self.cheat("WOODSTOCK")
            C["t"] = t
        elif food < 500:
            self.cheat("PEPPERONI PIZZA")
            C["t"] = t

    def stage_chase(self):
        """AOESOLO_STAGE=chase: P1 builds a market and 3 ranges, researches the Wheel, trains 10 chariot archers and
        sends them at the enemy's town, every one of them attacking the nearest enemy soldier; P2 trains 6 and keeps
        them home, and runs them away (toward the far side of the map) as soon as an enemy soldier is within 10
        tiles. The e_trap of P1 is what is watched."""
        t = self.now()
        S = self.__dict__.setdefault("_stage", {"say": -99})
        tc = self.tc()
        if tc is None:
            return
        me_hunter = self.me == 1
        raid = os.environ.get("AOESOLO_STAGE") == "raid"     # raid: the hunter's archers raid villagers, P2 has no army
        want = 10 if me_hunter else (0 if raid else 6)
        # buildings: a market, then 3 ranges (2 for P2)
        if not self.any_of(gs.MARKET) and not self.pending_of(gs.MARKET) and self.can_afford(wood=150):
            spot, why = self.building_spot(gs.MARKET)
            if spot:
                self.start_build(gs.MARKET, spot, self.builders_near(3, *spot), "(stage) " + why)
        n_rng = len(self.any_of(gs.ARCHERY_RANGE)) + len(self.pending_of(gs.ARCHERY_RANGE))
        cond = (n_rng < (3 if me_hunter else 2), self.can_afford(wood=150), bool(self.complete(gs.MARKET)))
        if t - S.get("cond_say", -99) > 30:
            S["cond_say"] = t
            self.say("STAGE range conditions: few ranges %s, wood ok %s, market %s" % cond)
        if all(cond):
            # the barracks first (the building tree: a range needs it - stage5 never built one), then the ranges
            btype = gs.BARRACKS if not self.any_of(gs.BARRACKS) and not self.pending_of(gs.BARRACKS) else gs.ARCHERY_RANGE
            if btype == gs.ARCHERY_RANGE and not self.complete(gs.BARRACKS):
                btype = None
            spot = None
            if btype is not None:
                for dx in range(-14, 15):
                    for dy in range(-14, 15):
                        x0, y0 = int(tc.x + dx - 1.5), int(tc.y + dy - 1.5)
                        d = math.hypot(dx, dy)
                        if 7 <= d <= 14 and self.footprint_ok(btype, x0, y0, self.keep_clear()) and                                 self.g.can_place(self.me, btype, x0 + 1.5, y0 + 1.5):
                            spot = (x0 + 1.5, y0 + 1.5)
                            break
                    if spot:
                        break
            bl = self.builders_near(3, *spot) if spot else []
            if spot and bl:
                self.start_build(btype, spot, bl, "(stage)")
            elif btype is not None and t - S.get("rng_say", -99) > 20:
                S["rng_say"] = t
                self.say("STAGE %d: spot %s, builders %d" % (btype, spot, len(bl)))
        # the Wheel
        done = getattr(self, "techs_done", set())
        try:
            states = self.g.research_states(self.me) or []
            wheel = states[TECH_WHEEL] if len(states) > TECH_WHEEL else 0
        except Exception:  # noqa: BLE001
            wheel = 0
        if wheel == 1 and t - S.get("wheel_t", -99) > 8:
            mk = [m for m in self.complete(gs.MARKET) if not self.r.producing(m)]
            if mk and self.can_afford(food=175, wood=75):
                self.g.research(mk[0], TECH_WHEEL)
                S["wheel_t"] = t
        archers = [u for u in self.military() if u.type == gs.CHARIOT_ARCHER]
        reserve = 160 if me_hunter else 0        # (wood kept for the trap: stage7 chased with 1-95 wood, no trap)
        ranges = self.complete(gs.ARCHERY_RANGE)
        n_now = len(archers) + sum(1 for b in ranges if self.r.producing(b))   # (stage12: 15 of 10 - those in training were not counted)
        if wheel == 3 and n_now < want:
            for b in ranges:
                if n_now < want and not self.r.producing(b) and self.can_afford(food=40, wood=70 + reserve):
                    self.g.train(b, gs.CHARIOT_ARCHER)
                    n_now += 1
        enemy = [e for e in self.s.enemy if e.kind == gs.KIND_COMBAT and e.hp > 0 and "Artifact" not in e.name
                 and (raid or e.cls != gs.CLS_VILLAGER)]
        if t - S["say"] > 30:
            S["say"] = t
            self.say("STAGE %s: market %d, ranges %d (any %d, pending %d), wood %d, wheel %s, chariot archers %d/%d, enemy soldiers seen %d" % (
                "hunter" if me_hunter else "runner", len(self.complete(gs.MARKET)), len(self.complete(gs.ARCHERY_RANGE)),
                len(self.any_of(gs.ARCHERY_RANGE)), len(self.pending_of(gs.ARCHERY_RANGE)), self.res(gs.WOOD), wheel, len(archers), want, len(enemy)))
        if not archers:
            return
        if me_hunter:
            if len(archers) < want and not S.get("go"):
                return
            S["go"] = True
            if enemy:
                cx = sum(u.x for u in archers) / len(archers)
                cy = sum(u.y for u in archers) / len(archers)
                tgt = min(enemy, key=lambda e: math.hypot(e.x - cx, e.y - cy))
                if t - S.get("atk_t", -99) > 1.5:
                    S["atk_t"] = t
                    self.g.order(archers, tgt)           # (straight to the game: every archer on the same unit)
            else:
                etc = None
                for o in getattr(self.s, "enemy_all", []):
                    if o.type == gs.TOWN_CENTER:
                        etc = (o.x, o.y)
                        break
                if etc and t - S.get("mv_t", -99) > 6:
                    S["mv_t"] = t
                    self.g.move(archers, etc[0], etc[1])
        else:
            cx = sum(u.x for u in archers) / len(archers)
            cy = sum(u.y for u in archers) / len(archers)
            near = [e for e in enemy if math.hypot(e.x - cx, e.y - cy) <= 10]
            if near and t - S.get("run_t", -99) > 2:
                S["run_t"] = t
                ex = sum(e.x for e in near) / len(near)
                ey = sum(e.y for e in near) / len(near)
                ux, uy = unit(cx - ex, cy - ey)
                W, H = self.r.W, self.r.H
                gx = min(W - 2.0, max(1.0, cx + ux * 20))
                gy = min(H - 2.0, max(1.0, cy + uy * 20))
                self.g.move(archers, gx, gy)
                if t - S.get("run_say", -99) > 10:
                    S["run_say"] = t
                    self.say("STAGE runner: %d archers run from %d enemies to (%.0f,%.0f)" % (len(archers), len(near), gx, gy))
            elif not near and t - S.get("home_t", -99) > 10:
                S["home_t"] = t
                self.g.move(archers, tc.x + 3, tc.y + 3)

    # ---------------------------------------------------------------- the foundation trap ("vay E")
    ETRAP_AHEAD = 4.0        # tiles ahead of the running enemy the line of foundations goes (order lag ~0.6 s real)
    ETRAP_MAX = 6            # foundations per trap
    ETRAP_GAP = 8            # a gap this wide (tiles, free width across the heading) or narrower is closed fully
    ETRAP_DELETE_AFTER = 20  # s after the chase ends the foundations are deleted (the user: take the wood back)

    def e_trap(self):
        """While 2+ of ours chase an enemy unit that runs away, foundations are placed across its predicted way
        when that way is a gap between obstacles or runs along one (the user, 15/10). Foundations shot down are
        placed again while the chase lasts; 20 s after it ends they are deleted."""
        t = self.now()
        T = self.__dict__.setdefault("_etrap", {"hist": {}, "active": None, "cool": -99.0})
        s = self.s
        enemy = [e for e in s.enemy if e.kind == gs.KIND_COMBAT and e.hp > 0 and "Artifact" not in e.name]
        # (villagers too: 4 of the player's 7 traps on 15/10 were on wood-line villagers, 8 of 9 died)
        # positions of the enemy units over the last 1.5 s: their heading and speed
        hist = T["hist"]
        for e in enemy:
            h = hist.setdefault(e.id, [])
            h.append((t, e.x, e.y))
            del h[:-8]
        for eid in [k for k, h in hist.items() if h and t - h[-1][0] > 3.0]:
            del hist[eid]                                # (kept 3 s through the fog: etrap4, a runner in and out of
                                                         #  sight never had 3 samples)
        A = T["active"]
        mine = {o.ptr: o for o in s.mine}
        if A is not None:
            e = next((x for x in enemy if x.id == A["eid"]), None)
            # (the chase goes on while any of ours is within 10 tiles of it: archers re-target every shot, so
            #  "has an attack order on it" ended the first trap 4 s in - etrap1)
            chasing = [u for u in self.military() if e is not None and u.dist(e.x, e.y) <= 14]
            # (a target out of sight for a moment is not dead: chase_v2 ended a trap "dead" and then kept adding
            #  foundations for the same unit 18 s later - 2 s of absence end it, and an ended trap never adds)
            if e is None:
                A.setdefault("unseen", t)
            else:
                A.pop("unseen", None)
            over = (e is None and t - A["unseen"] > 2.0) or (not chasing and t - A["t0"] > 8) or (
                e is not None and min(math.hypot(e.x - fx, e.y - fy) for (fx, fy) in A["spots"]) > 16)
            if e is None and not over and A.get("ended") is None:
                return
            founds = [o for o in s.mine if o.type == gs.HOUSE and o.hp <= 1.5 and
                      any(abs(o.x - fx) < 1.1 and abs(o.y - fy) < 1.1 for (fx, fy) in A["spots"])]
            if not over and A.get("ended") is None:
                # a foundation shot down: again, at once
                for (fx, fy) in A["spots"]:
                    if not any(abs(o.x - fx) < 1.1 and abs(o.y - fy) < 1.1 for o in founds) and t - A["placed"].get((fx, fy), -99) > 2.5 \
                            and self.can_afford(wood=30):
                        v = self._etrap_builder(fx, fy)
                        if v is not None and self.g.can_place(self.me, gs.HOUSE, fx, fy):
                            self.g.build([v], gs.HOUSE, fx, fy)
                            self._etrap_release(v)
                            A["placed"][(fx, fy)] = t
                            A["n_orders"] += 1
                            self.say("ETRAP foundation at (%.0f,%.0f) placed again (shot down)" % (fx, fy))
                # the player's cadence (15/10): two foundations first, then one more about every second ahead of
                # the runner while it keeps running and the way 4 tiles ahead is not covered yet
                if e is not None and A["n_orders"] < self.ETRAP_MAX and t - A.get("add_t", -99) >= 1.0 and self.can_afford(wood=30):
                    h = hist.get(e.id, [])
                    if len(h) >= 2 and h[-1][0] - h[0][0] >= 0.5:
                        (t0, x0, y0), (t1, x1, y1) = h[0], h[-1]
                        vx, vy = (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
                        sp = math.hypot(vx, vy)
                        if sp >= 0.8:
                            hx, hy = vx / sp, vy / sp
                            px, py = e.x + hx * self.ETRAP_AHEAD, e.y + hy * self.ETRAP_AHEAD
                            if not any(math.hypot(px - fx, py - fy) < 1.6 for (fx, fy) in A["spots"]):
                                spot = self._etrap_spot(px, py, hx, hy)
                                v = self._etrap_builder(*spot) if spot else None
                                if v is not None:
                                    self.g.build([v], gs.HOUSE, spot[0], spot[1])
                                    self._etrap_release(v)
                                    A["spots"].append(spot)
                                    A["placed"][spot] = t
                                    A["n_orders"] += 1
                                    A["add_t"] = t
                                    self.say("ETRAP +1 foundation at (%.0f,%.0f) ahead of #%d running %.1f t/s (%d spots)" % (
                                        spot[0], spot[1], e.id, sp, len(A["spots"])))
                return
            if A.get("ended") is None:
                A["ended"] = t
                self.say("ETRAP chase of #%d over (%s): %d foundations, %d orders, deleted in %d s" % (
                    A["eid"], "dead or unseen 2 s" if e is None else ("nobody chasing" if not chasing else "ran off"), len(founds), A["n_orders"], self.ETRAP_DELETE_AFTER))
            if t - A["ended"] >= self.ETRAP_DELETE_AFTER or not founds:
                for o in founds:
                    try:
                        self.g.delete(o)
                    except Exception:  # noqa: BLE001
                        pass
                T["active"] = None
                T["cool"] = t
            return
        mil = self.military()
        if os.environ.get("AOESOLO_ETRAPHIST") and t - T.get("hist_t", -99) > 10 and enemy and mil:
            T["hist_t"] = t
            cnt = {}
            for u in mil:
                a = self.r.action(u)
                if a and a[1]:
                    for e in enemy:
                        if a[1] == e.ptr:
                            cnt[e.id] = cnt.get(e.id, 0) + 1
            if cnt:
                eid, n = max(cnt.items(), key=lambda kv: kv[1])
                e = next(x for x in enemy if x.id == eid)
                h = hist.get(eid, [])
                sp = 0.0
                if len(h) >= 2 and h[-1][0] > h[0][0]:
                    sp = math.hypot(h[-1][1] - h[0][1], h[-1][2] - h[0][2]) / (h[-1][0] - h[0][0])
                near = min(mil, key=lambda u: u.dist(e.x, e.y))
                self.say("ETRAPHIST %d of ours attack enemies (%d targets); most-attacked #%d %s by %d, speed %.2f, nearest of ours %.1f, retreating-ours %d" % (
                    sum(cnt.values()), len(cnt), eid, e.name, n, sp, near.dist(e.x, e.y), sum(1 for u in mil if t < self.retreat_until.get(u.id, 0))))
        R = T.setdefault("why", {})
        if t - T.get("why_t", -99) > 10 and R:
            T["why_t"] = t
            self.say("ETRAPWHY " + ", ".join("%s %d" % kv for kv in sorted(R.items(), key=lambda kv: -kv[1])))
            R.clear()
        if t - T["cool"] < 15:
            R["cooldown"] = R.get("cooldown", 0) + 1
            return
        if not self.can_afford(wood=30 * 3 + 50):
            R["no wood"] = R.get("no wood", 0) + 1
            return
        for e in enemy:
            act_of = {}
            chasers = []
            for u in mil:
                a = self.r.action(u)
                if a and a[1] == e.ptr and u.dist(e.x, e.y) <= 12 and t >= self.retreat_until.get(u.id, 0)                         and not self.recent(u.id, ("fall",), within=8):
                    chasers.append(u)             # (not while falling back: etrap1 trapped a camel our archers
                                                  #  were retreating from - "it ran away" because we did)
            if len(chasers) < 2:
                R["chasers<2"] = R.get("chasers<2", 0) + 1
                continue
            why = None
            h = hist.get(e.id, [])
            if len(h) < 2 or h[-1][0] - h[0][0] < 0.5:
                why = "history %d" % len(h)
            (t0, x0, y0), (t1, x1, y1) = (h[0], h[-1]) if len(h) >= 2 else ((t, e.x, e.y), (t, e.x, e.y))
            vx, vy = (x1 - x0) / max(0.1, t1 - t0), (y1 - y0) / max(0.1, t1 - t0)
            speed = math.hypot(vx, vy)
            if why is None and speed < 0.8:
                why = "speed %.2f" % speed
            hx, hy = (vx / speed, vy / speed) if speed > 0 else (0.0, 0.0)
            near = min(chasers, key=lambda u: u.dist(e.x, e.y))
            ccx = sum(u.x for u in chasers) / len(chasers)
            ccy = sum(u.y for u in chasers) / len(chasers)
            if why is None and (e.x - ccx) * hx + (e.y - ccy) * hy < 0:
                why = "not away"                         # (away from the chasers' centre: the nearest chaser may be
                                                         #  on its far side when it is surrounded - stage6)
            px, py = e.x + hx * self.ETRAP_AHEAD, e.y + hy * self.ETRAP_AHEAD
            if why is None and not self.s.explored(px, py):
                why = "ahead unexplored"
            if why is not None:
                R[why.split()[0] if why.startswith(("history", "speed")) else why] = R.get(why.split()[0] if why.startswith(("history", "speed")) else why, 0) + 1
                if t - T.get("dbg_t", -99) > 10:
                    T["dbg_t"] = t
                    self.say("ETRAPDBG #%d %s: %d chasers, %s (speed %.2f, dist %.1f)" % (e.id, e.name, len(chasers), why, speed, near.dist(e.x, e.y)))
                continue
            # free width across the heading at P: the first obstacle to the left and to the right
            lx, ly = -hy, hx
            left = right = 0
            for k in range(1, 7):
                if left == 0 and not self.pm.passable(int(px + lx * k), int(py + ly * k)):
                    left = k
                if right == 0 and not self.pm.passable(int(px - lx * k), int(py - ly * k)):
                    right = k
            if (not left and not right) or (left and right and left + right - 1 > self.ETRAP_GAP):
                R["open ground"] = R.get("open ground", 0) + 1
                if t - T.get("dbg_t", -99) > 10:
                    T["dbg_t"] = t
                    self.say("ETRAPDBG #%d %s: %d chasers, open ground ahead (left %d right %d), speed %.2f" % (e.id, e.name, len(chasers), left, right, speed))
                continue
            # the line of 2x2 footprints across: from the left obstacle to the right one (or 6 tiles into the open)
            spots = []
            kl = (left - 1) if left else 6
            kr = (right - 1) if right else 6
            k = -kr + 1
            while k <= kl - 1 and len(spots) < self.ETRAP_MAX:
                cx, cy = px + lx * k, py + ly * k
                fx, fy = math.floor(cx) + 1.0, math.floor(cy) + 1.0   # the 2x2 centre
                if self.pm.passable(int(fx - 1), int(fy - 1)) and self.pm.passable(int(fx), int(fy)) and \
                        self.g.can_place(self.me, gs.HOUSE, fx, fy):
                    spots.append((fx, fy))
                k += 2
            if len(spots) < 2 or not self.can_afford(wood=30 * len(spots)):
                R["spots<2"] = R.get("spots<2", 0) + 1
                continue
            spots = sorted(spots, key=lambda sp: math.hypot(sp[0] - px, sp[1] - py))[:2]   # (two first, the rest as it runs)
            v = self._etrap_builder(px, py)
            if v is None:
                R["no villager"] = R.get("no villager", 0) + 1
                continue
            placed = {}
            for (fx, fy) in spots:
                self.g.build([v], gs.HOUSE, fx, fy)
                placed[(fx, fy)] = t
            self._etrap_release(v)
            T["active"] = {"eid": e.id, "eptr": e.ptr, "spots": spots, "placed": placed, "n_orders": len(spots), "t0": t}
            self.say("ETRAP #%d (%s) runs %.1f tiles/s from %d chasers into a %s: %d foundations across its way at (%.0f,%.0f)" % (
                e.id, e.name, speed, len(chasers), "gap %d wide" % (left + right - 1) if left and right else "forest edge", len(spots), px, py))
            return

    def _etrap_spot(self, px, py, hx, hy):
        """A placeable 2x2 footprint on the predicted point, or shifted up to 2 tiles across the heading."""
        lx, ly = -hy, hx
        for k in (0, 1, -1, 2, -2):
            cx, cy = px + lx * k, py + ly * k
            fx, fy = math.floor(cx) + 1.0, math.floor(cy) + 1.0
            if 1 <= fx < self.r.W - 1 and 1 <= fy < self.r.H - 1 and self.pm.passable(int(fx - 1), int(fy - 1)) and \
                    self.pm.passable(int(fx), int(fy)) and self.g.can_place(self.me, gs.HOUSE, fx, fy):
                return (fx, fy)
        return None

    def anti_trap(self):
        """The counter to the player's trap (15/10): one of ours that is running (fleeing or ordered to move) but
        has not moved for a second while an enemy foundation (1-2 hp) stands within 2 tiles hits that foundation
        once and runs on. The player's traps held a camel still for 18 s and villagers died pressed against the
        foundation without ever striking it."""
        t = self.now()
        P = self.__dict__.setdefault("_antitrap", {"pos": {}, "hit": {}})
        s = self.s
        founds = [o for o in getattr(s, "enemy_all", []) if o.kind == gs.KIND_BUILDING and 0 < o.hp <= 2.0]
        if not founds:
            P["pos"].clear()
            return
        for u in list(s.villagers) + list(self.military()):
            lo = self.last_order.get(u.id)
            running = (t < self.retreat_until.get(u.id, 0)) or (lo and t - lo[0] < 8 and lo[1] and lo[1][0] in ("m", "flee"))
            if not running:
                P["pos"].pop(u.id, None)
                continue
            prev = P["pos"].get(u.id)
            P["pos"][u.id] = (t, u.x, u.y) if prev is None or math.hypot(u.x - prev[1], u.y - prev[2]) > 0.3 else prev
            if prev is None or t - P["pos"][u.id][0] < 1.0 or t - P["hit"].get(u.id, -99) < 3.0:
                continue
            near = [o for o in founds if o.dist(u.x, u.y) <= 2.2]
            if not near:
                continue
            o = min(near, key=lambda b: b.dist(u.x, u.y))
            self.g.order([u], o)
            self.mark([u], ("unstick", o.id))
            P["hit"][u.id] = t
            self.retreat_until[u.id] = 0                    # (the flee rule sends it on again next tick)
            self.say("ANTITRAP %s #%d stood %.1f s against enemy foundation #%d at (%.0f,%.0f): hits it" % (
                u.name, u.id, t - P["pos"][u.id][0], o.id, o.x, o.y))

    def flee_goal(self, v, ex, ey, dist=8.0):
        """Where a villager runs from raiders at (ex, ey) (the user, 15/10 evening): toward the TC unless the TC is
        behind the raiders; otherwise the most open direction away from them - never along a forest or into a map
        corner (the player's traps killed 8 of 9 villagers that ran into wood lines and corners)."""
        tc = self.tc()
        W, H = self.r.W, self.r.H
        ax, ay = unit(v.x - ex, v.y - ey)
        if tc is not None:
            ux, uy = unit(tc.x - v.x, tc.y - v.y)
            if ux * ax + uy * ay > -0.2 and v.dist(tc.x, tc.y) > 3:
                return tc.x, tc.y
        best, bs = None, -1e9
        for k in range(12):
            a = 2 * math.pi * k / 12
            dx, dy = math.cos(a), math.sin(a)
            away = dx * ax + dy * ay
            if away < 0.2:
                continue
            run = 0
            for r in range(1, int(dist) + 1):
                x, y = int(v.x + dx * r), int(v.y + dy * r)
                if not (1 <= x < W - 1 and 1 <= y < H - 1) or not self.pm.passable(x, y):
                    break
                run = r
            gx, gy = v.x + dx * run, v.y + dy * run
            free = sum(1 for i in range(-2, 3) for j in range(-2, 3)
                       if 0 <= int(gx + i) < W and 0 <= int(gy + j) < H and self.pm.passable(int(gx + i), int(gy + j)))
            edge = min(gx, gy, W - gx, H - gy)
            score = run * 2 + free * 0.5 + away * 3 - (max(0.0, 8 - edge) * 2)
            if score > bs:
                bs, best = score, (gx, gy)
        return best if best else (v.x + ax * dist, v.y + ay * dist)

    def _etrap_release(self, v):
        """The villager that placed the foundations goes straight back to its job (the foundation stays; measured
        15/10) - otherwise it walks over and builds the trap house."""
        r = self.role.get(v.id)
        try:
            if isinstance(r, str):
                self.work(v, r, force=True)
            else:
                self.g.move([v], v.x, v.y)
        except Exception:  # noqa: BLE001
            pass

    def _etrap_builder(self, x, y):
        """Any villager will do (the foundation appears wherever it stands); the nearest one not owned by a task."""
        owned = self.task_owned()
        vs = [v for v in self.s.villagers if v.id not in owned and v.id not in self.defenders]
        return min(vs, key=lambda v: v.dist(x, y)) if vs else None

    def lion_defence(self):
        """A lion attacking one of our workers: the victim and up to 3 villagers within 7 tiles hit it together
        (v10d: one lion at a wood line / farm killed 5 Greek villagers one by one in 2.5 minutes - the lion
        rule only covered scouts). The helpers are released once the lion is dead or gone."""
        t = self.now()
        s = self.s
        helpers = self.__dict__.setdefault("lion_helpers", {})          # villager id -> lion id
        live = {a.id: a for a in s.gaia if a.id in self.lions and a.hp > 0}
        for vid, lid in list(helpers.items()):
            if lid not in live:
                helpers.pop(vid, None)
        if not live:
            return
        mine = {o.ptr: o for o in s.villagers}
        for a in live.values():
            act = self.r.action(a)
            if not act or act[1] not in mine:
                continue
            victim = mine[act[1]]
            group = [v for v in s.villagers if v.id == victim.id or (v.dist(a.x, a.y) <= 7 and v.hp >= 12
                                                                      and helpers.get(v.id, a.id) == a.id)]
            group.sort(key=lambda v: (v.id != victim.id, v.dist(a.x, a.y)))
            group = group[:4]
            for v in group:
                helpers[v.id] = a.id
                if not self.recent(v.id, ("o", a.id), within=2.5):
                    self.g.order([v], a)                     # (straight to the game: no raider / gate check)
                    self.mark([v], ("o", a.id))
            if t - getattr(self, "_lion_say", -99) > 20:
                self._lion_say = t
                self.say("lion #%d attacks villager #%d: %d villagers fight it" % (a.id, victim.id, len(group)))

    def flee_lion(self, v):
        """A scouting villager inside a lion's range steps straight out of it; one the lion already
        attacks fights back (it cannot outrun a lion) and goes on scouting if it wins."""
        for a in self.s.gaia:
            if a.id in self.lions and a.hp > 0:
                act = self.r.action(a)
                if act and act[1] == v.ptr:
                    if not self.recent(v.id, ("o", a.id), within=2.5):
                        self.order([v], a)
                        self.say("lion #%d attacks scouting villager #%d: fighting back" % (a.id, v.id))
                    return True
        lion = self.lion_near(v.x, v.y)
        if not lion:
            return False
        if not self.recent(v.id, ("flee",), within=1.5):
            ux, uy = unit(v.x - lion[0], v.y - lion[1])
            step = LION_SAFE + 2 - math.hypot(v.x - lion[0], v.y - lion[1])
            self.move([v], v.x + ux * step, v.y + uy * step)
            self.mark([v], ("flee",))
            self.scout_goal.pop(v.id, None)
        return True

    def gathering_gaia(self, v):
        """True if the villager works a gaia object we did not send it to (e.g. eating a lion it killed)."""
        a = self.r.action(v)
        if not a or not a[1]:
            return False
        for o in self.s.gaia:
            if o.ptr == a[1]:
                return not (o.id in self.lions and o.hp > 0)
        return False

    def scout(self, v, local=False, max_r=None, near_home=False):
        if self.flee_lion(v):
            return
        tc = self.tc()
        if not tc:
            return
        goal = self.scout_goal.get(v.id)
        stray = self.gathering_gaia(v)                       # never stays to eat what it killed
        if goal and not stray:
            reached = v.dist(*goal) <= 3 or self.s.explored(*goal)
            if not reached:
                if self.r.busy(v) or self.recent(v.id, within=2.0):
                    return
                self.bad_goals.add((int(goal[0]) // 3, int(goal[1]) // 3))
        elif not goal and not stray and self.recent(v.id, within=1.0):
            return
        goal = self.frontier_goal(v, tc, max_r=max_r or (20 if local else None), near_home=near_home)
        if goal:
            self.scout_goal[v.id] = goal
            self.move([v], *goal)
        elif v.dist(tc.x, tc.y) > 6 and not self.recent(v.id, within=10):
            self.move([v], tc.x + 3, tc.y + 3)

    def gazelle_spots(self):
        """Live gazelles we know of (seen now or a moment ago): scouts walk around them."""
        t = self.now()
        return [(x, y) for (x, y, ty, ts) in self.animal_pos.values() if ty == gs.GAZELLE and t - ts < 120]

    def path_meets(self, x0, y0, x1, y1, points, r):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        for px, py in points:
            k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
            if math.hypot(x0 + k * dx - px, y0 + k * dy - py) < r:
                return True
        return False

    def frontier_goal(self, v, tc, max_r=None, toward=None, near_home=False, far=False):
        """Nearest unexplored ground. near_home: the closest to the TC first (finding the first
        berries); otherwise spread out by sector. Villagers keep away from lions and gazelles.
        Scores every frontier cell first (cheap), then checks lions / gazelles only for the best ones."""
        s = self.s
        scouting = v.cls == gs.CLS_VILLAGER and self.role_name(v.id) in ("scout", "search")
        ring = scouting and bool(self.any_of(gs.GRANARY)) and not self.bronze_clicked
        gaz = self.gazelle_spots() if scouting else []
        W, H = self.r.W, self.r.H
        vis = s.vis
        sector = (v.id * 2.399) % (2 * math.pi)
        if toward:
            sector = math.atan2(toward[1] - tc.y, toward[0] - tc.x)
        step = 3
        cands = []
        for y in range(1, H - 1, step):
            row = y * W
            for x in range(1, W - 1, step):
                if vis[row + x] != 255:
                    continue
                if not ((x + step < W and vis[row + x + step] != 255) or (x - step >= 0 and vis[row + x - step] != 255)
                        or (y + step < H and vis[row + step * W + x] != 255)
                        or (y - step >= 0 and vis[row - step * W + x] != 255)):
                    continue
                d_tc = math.hypot(x - tc.x, y - tc.y)
                if max_r is not None and d_tc > max_r:
                    continue
                if (x // 3, y // 3) in self.bad_goals:
                    continue
                ang = math.atan2(y - tc.y, x - tc.x)
                da = abs((ang - sector + math.pi) % (2 * math.pi) - math.pi)
                dv = math.hypot(x - v.x, y - v.y)
                if far and toward:
                    # the user: the scout (and the army without an address) heads for the enemy's likely
                    # home - the far side of the map - not the nearest fog
                    score = math.hypot(x - toward[0], y - toward[1]) + 0.2 * dv
                elif near_home:
                    score = d_tc * 1.0 + dv * 0.3 + da * 4
                elif scouting and ring:
                    # the hunts are 15-45 tiles out (the user's hunters: 15-18 tiles at min 2-3, 27-46 at
                    # min 8-10); once the berries are found the scouts sweep that ring, not the home area
                    score = dv * 0.6 + abs(d_tc - 28) * 0.6 + da * 12
                else:
                    score = dv * 0.6 + d_tc * 0.4 + da * 12
                if self.enemy_base and not self.bronze_clicked and \
                        math.hypot(x - self.enemy_base[0], y - self.enemy_base[1]) < 15:
                    score += 60
                cands.append((score, x, y))
        cands.sort()
        check_lions = bool(self.lions) and v.cls == gs.CLS_VILLAGER
        for score, x, y in cands[:300]:
            if check_lions and (self.lion_near(x, y, LION_SAFE + 1) or self.path_meets_lion(v.x, v.y, x, y)):
                continue
            if gaz and (any(math.hypot(x - gx, y - gy) < GAZELLE_SAFE + 1 for gx, gy in gaz)
                        or self.path_meets(v.x, v.y, x, y, gaz, GAZELLE_SAFE)):
                continue
            return (x + 0.5, y + 0.5)
        return None

    # ================================================================ resource buildings
    def meat_extras(self, cx, cy):
        """Gold mines (and a few trees) near a kill: the pit goes between the meat and them so it
        serves the gold / wood afterwards (the user)."""
        out = []
        gold = sorted([o for o in self.s.gaia if o.type == gs.GOLD_MINE and o.dist(cx, cy) <= 10],
                      key=lambda o: o.dist(cx, cy))[:3]
        out += [(o.x, o.y, 0.5) for o in gold]
        trees = sorted([o for o in self.s.gaia if o.kind == gs.KIND_TREE and o.dist(cx, cy) <= 8],
                       key=lambda o: o.dist(cx, cy))[:6]
        out += [(o.x, o.y, 0.12) for o in trees]
        return out

    def best_dropsite(self, btype, points, rmax=5, extra=()):
        """Granary/pit spot with the least total walking for `points` (bushes, carcasses) and
        without closing any bush in. `extra`: (x, y, weight) points that pull the spot (gold, wood)
        without being required within reach."""
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        cands = []
        for x0 in range(int(min(xs)) - rmax - 2, int(max(xs)) + rmax):
            for y0 in range(int(min(ys)) - rmax - 2, int(max(ys)) + rmax):
                if not self.footprint_ok(btype, x0, y0):
                    continue
                rect = (x0, y0, x0 + 3, y0 + 3)
                total = 0.0
                worst = 0.0
                for px, py in points:
                    d = pathing.rect_distance(px, py, rect)
                    total += d
                    worst = max(worst, d)
                if worst > 6:
                    continue
                for px, py, wgt in extra:
                    total += wgt * pathing.rect_distance(px, py, rect)
                # every bush/carcass must keep at least two free sides after we build
                blocked = 0
                for px, py in points:
                    free = 0
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                        tx, ty = int(px) + dx, int(py) + dy
                        if x0 <= tx < x0 + 3 and y0 <= ty < y0 + 3:
                            continue
                        if self.pm.passable(tx, ty):
                            free += 1
                    if free < 2:
                        blocked += 1
                cands.append((total + blocked * 8, x0, y0))
        return self.place_checked(btype, cands)

    def best_dropsite_paths(self, btype, points, rmax=5, max_walk=8):
        """Brute force: try every free footprint around `points` (bushes / carcasses) and score it by
        the REAL walking distance (path around trees, bushes, cliffs) from every point to the
        building, plus a crowding penalty when several gatherers would drop at the same tile, plus
        a penalty for bushes it walls in. Falls back to the straight-line scorer."""
        if not points:
            return None
        key = (btype, round(sum(p[0] for p in points) / len(points)), round(sum(p[1] for p in points) / len(points)))
        memo = self.__dict__.setdefault("_dropsite_memo", {})
        if key in memo and self.now() - memo[key] < 10:
            return None                                  # nothing found a moment ago: do not redo it every tick
        pm = self.pm
        W = pm.W
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        blk = bytearray(pm.blk)
        pre = []
        for x0 in range(int(min(xs)) - rmax - 2, int(max(xs)) + rmax):
            for y0 in range(int(min(ys)) - rmax - 2, int(max(ys)) + rmax):
                if not self.footprint_ok(btype, x0, y0):
                    continue
                rect = (x0, y0, x0 + 3, y0 + 3)
                ds = [pathing.rect_distance(px, py, rect) for px, py in points]
                if max(ds) > max_walk:
                    continue
                pre.append((sum(ds), x0, y0))
        pre.sort()
        cands = []
        tc = self.tc()
        town = None
        if tc is not None:
            # (the site must be reachable from the TC: a granary in a pocket of trees feeds nobody)
            tx0, ty0 = int(tc.x - 1.5), int(tc.y - 1.5)
            town = pm.bfs([(xx, yy) for (xx, yy) in pm.ring_tiles(tx0, ty0, tx0 + 3, ty0 + 3) if pm.passable(xx, yy)],
                          max_cost=10 * 70)
        for _, x0, y0 in pre[:40]:                       # real paths only for the 40 best straight-line spots
            if town is not None and not any(town[yy * W + xx] >= 0 for (xx, yy) in pm.ring_tiles(x0, y0, x0 + 3, y0 + 3)
                                            if 0 <= xx < W and 0 <= yy < pm.H):
                continue
            if True:
                for yy in range(y0, y0 + 3):
                    for xx in range(x0, x0 + 3):
                        blk[yy * W + xx] = 1
                ring = [(xx, yy) for (xx, yy) in pm.ring_tiles(x0, y0, x0 + 3, y0 + 3) if not blk[yy * W + xx]]
                if len(ring) >= 4:
                    dist = pm.bfs(ring, max_cost=10 * (max_walk + 4), blk=blk)
                    total = 0.0
                    walled = 0
                    drop_tile = {}
                    for px, py in points:
                        best = None
                        free_sides = 0
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                            tx, ty = int(px) + dx, int(py) + dy
                            if 0 <= tx < W and 0 <= ty < pm.H and not blk[ty * W + tx]:
                                free_sides += 1
                                d = dist[ty * W + tx]
                                if d >= 0 and (best is None or d < best):
                                    best = d
                        if free_sides < 2:
                            walled += 1
                        total += (best if best is not None else 200) / 10.0
                        near = min(ring, key=lambda r: (r[0] - px) ** 2 + (r[1] - py) ** 2)
                        drop_tile[near] = drop_tile.get(near, 0) + 1
                    crowd = sum(max(0, c - 2) for c in drop_tile.values())
                    cands.append((total + 2.0 * crowd + 8.0 * walled, x0, y0))
                for yy in range(y0, y0 + 3):
                    for xx in range(x0, x0 + 3):
                        blk[yy * W + xx] = pm.blk[yy * W + xx]
        if not cands:
            memo[key] = self.now()
            return self.best_dropsite(btype, points, rmax)
        spot = self.place_checked(btype, cands)
        if spot and btype == gs.GRANARY and demo_dump.enabled() and not self.any_of(gs.GRANARY):
            cxp = sum(p[0] for p in points) / len(points)
            cyp = sum(p[1] for p in points) / len(points)
            demo_dump.write(self, "granary", {"points": [[round(x, 2), round(y, 2)] for x, y in points],
                                              "n_pre": len(pre), "cands": [[round(c[0], 2), c[1], c[2]] for c in sorted(cands)],
                                              "spot": list(spot), "win": demo_dump.window(self, cxp, cyp, 14)})
        if not spot:
            memo[key] = self.now()
        if spot:
            best = min(cands)
            self.say("dropsite %d by path brute force: %d spots tried, walk score %.1f" % (btype, len(cands), best[0]))
        return spot or self.best_dropsite(btype, points, rmax)

    def granaries(self):
        if self.pending_of(gs.GRANARY):
            return
        grans = self.any_of(gs.GRANARY)
        tc = self.tc()
        # the first patch is almost picked clean (players' 2nd granary: ~8:00): the next patch now
        running_dry = any(sum(1 for b in self.s.gaia if b.type == gs.FORAGE and b.amount > 0 and b.dist(g0.x, g0.y) < 7) <= 2
                          for g0 in grans)
        if grans and not self.any_of(gs.STORAGE_PIT) and not (running_dry and self.res(gs.WOOD) >= 240):
            # after the first granary the wood-line pit comes first (the user: never the second granary
            # before the first pit) - only with 240 wood (granary AND pit paid) when the first patch runs dry
            return
        for cx, cy, items in sorted(self.berry_clusters(), key=lambda c: math.hypot(c[0] - tc.x, c[1] - tc.y)):
            if any(math.hypot(g0.x - cx, g0.y - cy) < 7 for g0 in grans):
                continue
            if grans and math.hypot(cx - tc.x, cy - tc.y) > self.berry_range():
                continue                            # far patches are not worth a granary
            if grans and math.hypot(cx - tc.x, cy - tc.y) < 8:
                continue                            # the TC takes those berries
            # wait until the patch is really known: >= 5 bushes, or the area around it explored
            # (off-map counts as known), or villagers have waited there for a while
            if len(items) < 5:
                W, H = self.r.W, self.r.H
                around_known = all(self.s.explored(cx + dx, cy + dy) for dx in (-6, 0, 6) for dy in (-6, 0, 6)
                                   if 0 <= cx + dx < W and 0 <= cy + dy < H)
                waited = self.now() - self.wait_since.get(("berry", (int(cx) // 6, int(cy) // 6)), self.now())
                if grans and len(items) < 3:
                    continue
                if not around_known and waited < 15:
                    return
            if grans and len(self.s.villagers) < 12 and not running_dry:
                return
            far_patch = len(items) >= 4 and math.hypot(cx - tc.x, cy - tc.y) > 15
            if not self.can_afford(wood=120) or (not self.tool_wood_free(120) and not far_patch):
                # (a far patch of 4+ bushes gets its granary before the market / stable wood: age13 sent six
                #  pickers 36 tiles to the TC with every load for the whole Tool age)
                return
            spot = self.best_dropsite_paths(gs.GRANARY, [(o[1], o[2]) for o in items])
            if not spot:
                return
            if not grans:
                early = [v for v in sorted(self.s.villagers, key=lambda v: v.id)[:6]
                         if self.role_name(v.id) != "build"]
                early.sort(key=lambda v: v.dist(*spot))
                builders = early[:3] or self.builders_near(2, cx, cy)
            else:
                builders = self.builders_near(2, cx, cy)
            self.start_build(gs.GRANARY, spot, builders, "(berries, %d bushes)" % len(items))
            return

    def storage_pits(self):
        if self.pending_of(gs.STORAGE_PIT) or self.pending_of(gs.GRANARY):
            return
        pits = self.any_of(gs.STORAGE_PIT)
        tc = self.tc()
        if not self.woodline_placed and pits and self.ticks <= 2:
            self.woodline_placed = True              # restarted mid-game: a pit already exists
        if not self.can_afford(wood=120):
            return
        if not self.woodline_placed:
            # mandatory right after the first granary (or once the economy is up with no berries)
            if not self.any_of(gs.GRANARY) and len(self.s.villagers) < 9:
                return
            spot = self.woodline_spot()
            if not spot:
                if self.now() - getattr(self, "_wl_warn", -99) > 30:
                    self._wl_warn = self.now()
                    self.say("no wood-line pit spot found yet")
                return
            # every villager chopping (up to 6) builds it, then they all chop there
            choppers = [v for v in self.s.villagers if self.role_name(v.id) == "wood"]
            choppers.sort(key=lambda v: v.dist(*spot))
            builders = choppers[:6] or self.builders_near(2, *spot, roles=("wood", None))
            if self.start_build(gs.STORAGE_PIT, spot, builders, "(wood line)"):
                self.woodline_placed = True
            return
        if self.bronze_clicked:
            gold = self.known_gold()
            if gold and len(pits) < 5:
                g0 = min(gold, key=lambda o: o.dist(tc.x, tc.y))
                # the user: the pit stands one foundation from the mine so a miner drops without walking;
                # only a TC right next to the mine makes it unnecessary
                if not any(p.dist(g0.x, g0.y) < 4.5 for p in pits) and self.tc_edge_dist(g0.x, g0.y) >= 3.0 \
                        and self.can_afford(wood=120):
                    mines = [(o.x, o.y) for o in gold if o.dist(g0.x, g0.y) < 6]
                    spot = self.best_dropsite(gs.STORAGE_PIT, mines, rmax=3)
                    if spot:
                        self.start_build(gs.STORAGE_PIT, spot, self.builders_near(2, g0.x, g0.y), "(gold)")
                    elif self.now() - getattr(self, "_gold_pit_warn", -99) > 60:
                        self._gold_pit_warn = self.now()
                        self.say("no pit spot next to the gold at (%.0f,%.0f)" % (g0.x, g0.y))

    def woodline_spot(self):
        """First pit: touching the forest, with the most wood within 4 tiles around it (trees on two
        or more sides of it if possible: the wood for now) plus the wood within 8 tiles (for later),
        not far from the TC, with open sides to walk in."""
        tc = self.tc()
        if not tc:
            return None
        trees = [o for o in self.s.gaia if o.kind == gs.KIND_TREE and o.amount > 0 and o.dist(tc.x, tc.y) <= 46]
        if not trees:
            return None
        wood = {}
        for t in trees:
            k = (int(t.x), int(t.y))
            wood[k] = wood.get(k, 0) + t.amount / 75.0          # a 75-wood tree = 1, a 40-wood tree ~ 0.5
        seen = set()
        cands = []
        for t in trees:
            if not 4 <= t.dist(tc.x, tc.y) <= 42:      # (a TC at the map edge: the forest can be 35+ tiles out)
                continue
            for dx in range(-4, 2):
                for dy in range(-4, 2):
                    x0, y0 = int(t.x) + dx, int(t.y) + dy
                    if (x0, y0) in seen:
                        continue
                    seen.add((x0, y0))
                    # touching the forest: a tree right next to the footprint
                    if not any((xx, yy) in wood for xx in range(x0 - 1, x0 + 4) for yy in (y0 - 1, y0 + 3)) and \
                            not any((xx, yy) in wood for xx in (x0 - 1, x0 + 3) for yy in range(y0, y0 + 3)):
                        continue
                    if not self.footprint_ok(gs.STORAGE_PIT, x0, y0):
                        continue
                    near = far = 0.0
                    sides = [0, 0, 0, 0]                          # left, right, top, bottom
                    for yy in range(y0 - 8, y0 + 11):
                        for xx in range(x0 - 8, x0 + 11):
                            w = wood.get((xx, yy))
                            if not w:
                                continue
                            gap = max(x0 - xx, xx - (x0 + 2), y0 - yy, yy - (y0 + 2), 0)
                            if gap <= 4:
                                near += w
                                if xx < x0:
                                    sides[0] += 1
                                if xx > x0 + 2:
                                    sides[1] += 1
                                if yy < y0:
                                    sides[2] += 1
                                if yy > y0 + 2:
                                    sides[3] += 1
                            else:
                                far += w
                    if near < 3:
                        continue
                    if len(self.pm.ring_tiles(x0, y0, x0 + 3, y0 + 3)) < 4:
                        continue
                    n_sides = sum(1 for c in sides if c >= 3)
                    cx, cy = x0 + 1.5, y0 + 1.5
                    score = near + 0.3 * far + 3.0 * min(n_sides, 3) - 0.3 * math.hypot(cx - tc.x, cy - tc.y)
                    cands.append((-score, x0, y0))
        spot = self.place_checked(gs.STORAGE_PIT, cands)
        if spot and demo_dump.enabled() and not self.any_of(gs.STORAGE_PIT):
            demo_dump.write(self, "pit", {"cands": [[round(-c[0], 2), c[1], c[2]] for c in sorted(cands)[:80]],
                                          "n_cands": len(cands), "spot": list(spot),
                                          "win": demo_dump.window(self, (tc.x + spot[0]) / 2.0, (tc.y + spot[1]) / 2.0,
                                                                 max(16, 0.5 * math.hypot(spot[0] - tc.x, spot[1] - tc.y) + 10))})
        if spot and not getattr(self, "_wl_logged", False):
            self._wl_logged = True
            best = min(cands)
            self.say("wood-line pit spot score %.1f (%d candidates)" % (-best[0], len(cands)))
        return spot

    # ================================================================ tool/bronze buildings
    def building_spot(self, btype):
        # the user: the market and the (first) stable must be built for the age anyway - they close a
        # gap of the wall; later military buildings stand outside the wall
        first_age_building = btype == gs.MARKET or (btype == self.second_building() and not self.any_of(btype))             or (btype == gs.BARRACKS and not self.any_of(gs.BARRACKS))     # (the user: BB, BM, BL close wall gaps)
        of = self.__dict__.get("_outside_fail", {}).get(btype)
        outside_ok = not (of and of[0] >= 2 and self.now() - of[1] < 240)   # (units4: 8 failures in a row out there)
        if btype in MILITARY_BUILDINGS and btype != gs.BARRACKS and self.military_hub() is not None:
            # (the barracks is no military building to the user - no bot fields its units: it stands on the wall line)
            # the user (14/10): every military building in ONE cluster, chosen at the Tool click, outside
            # the wall (units come out free) and toward the map centre / the enemy - the first barracks and
            # the age's stable / range too (they used to close wall gaps)
            spot = self.hub_spot(btype, wide=not outside_ok)
            if spot:
                return spot, "(military cluster, outside the wall)"
        elif btype in MILITARY_BUILDINGS and btype not in (gs.ACADEMY, gs.BARRACKS):
            # no cluster yet: wait a minute for one before a lone building in the town (it would never be part
            # of the cluster - hub1 P3)
            t0 = self.__dict__.setdefault("_hub_wait_t0", self.now())
            if self.now() - t0 < 60:
                return None, "(waits for the military cluster)"
        if btype in MILITARY_BUILDINGS and btype != gs.BARRACKS and not first_age_building and outside_ok:
            spot = self.outside_spot(btype)
            if spot:
                return spot, "(outside the wall)"
        spot = self.next_wall_slot(btype)
        if spot:
            return spot, "(wall)"
        if btype in MILITARY_BUILDINGS and outside_ok and not first_age_building:
            # (the age's own building stays in the town when no wall slot is free - age3: the stable
            #  went outside, failed, and the age waited for it)
            spot = self.outside_spot(btype)
            if spot:
                return spot, "(outside the wall)"
        tc = self.tc()
        kc = self.keep_clear()
        cands = []
        for dx in range(-16, 17):
            for dy in range(-16, 17):
                x0, y0 = int(tc.x + dx - 1.5), int(tc.y + dy - 1.5)
                cx, cy = x0 + 1.5, y0 + 1.5
                d = math.hypot(cx - tc.x, cy - tc.y)
                if d < FARM_RING + 2 or d > 16:
                    continue
                if not self.footprint_ok(btype, x0, y0, kc):
                    continue
                cands.append((abs(d - 10) + self._near_resources_penalty(cx, cy), x0, y0))
        return self.place_checked(btype, cands), "(town)"

    def wall_inside_tiles(self):
        for p in self.wall or []:
            if getattr(p, "inside", None):
                return p.inside
        return None

    def military_hub(self):
        """The centre of the military cluster, decided ONCE at the Tool click (the user, 14/10: the barracks
        built then fixes where every later military building goes): outside the wall ring, toward the enemy's
        probable side (the first enemy building seen, else the map centre), where the most flat, free,
        explored 3x3 footprints fit. None before the Tool click."""
        hub = getattr(self, "mil_hub", None)
        if hub is not None:
            return hub
        if not (self.tool_clicked or self.age >= 2):
            return None
        tc = self.tc()
        if not tc or self.now() - getattr(self, "_hub_try_t", -99) < 20:
            return None
        self._hub_try_t = self.now()                     # (a search is ~0.3 s of Python: not every tick)
        W, H = self.r.W, self.r.H
        ex, ey = self.enemy_dir()
        if math.hypot(tc.x - W / 2.0, tc.y - H / 2.0) < 15 and self.enemy_base is None:
            # (a town at the map centre: toward the widest unexplored side)
            best_d, best_n = (ex, ey), -1
            for k in range(8):
                a = k * math.pi / 4
                dx, dy = math.cos(a), math.sin(a)
                n = sum(1 for r in range(10, 50, 4) for j in (-4, 0, 4)
                        if not self.s.explored(int(tc.x + dx * r - dy * j), int(tc.y + dy * r + dx * j)))
                if n > best_n:
                    best_d, best_n = (dx, dy), n
            ex, ey = best_d
        inside = self.wall_inside_tiles()
        R = self.wall_reach()
        kc = self.keep_clear()
        best = None
        # first ahead (+-60 deg, up to 17 tiles beyond the ring), then - in the same search - any side and
        # farther out (hub1 P3: a 40-tile ring at a map edge, no room ahead; its barracks and stable went in
        # the town and the cluster came 13 minutes later somewhere else)
        for wide in (False, True):
            if best is not None:
                break
            out = []
            self._hub_search(wide, ex, ey, tc, R, inside, kc, W, H, out)
            best = max(out, key=lambda b: b[0]) if out else None
        if best is None:
            # a military building already standing (built while no cluster could be found) becomes the cluster:
            # the later ones go next to it, never one here and one there
            first = [b for b in self.s.mine if b.type in MILITARY_BUILDINGS and b.type != gs.BARRACKS and b.kind == gs.KIND_BUILDING
                     and not (inside is not None and (int(b.x), int(b.y)) in inside)]
            if first:
                self.mil_hub = (first[0].x, first[0].y)
                self.say("military cluster at the first military building (%.0f,%.0f)" % self.mil_hub)
                return self.mil_hub
            if self.now() - getattr(self, "_hub_say", -99) > 60:
                self._hub_say = self.now()
                self.say("military cluster: no room outside the wall yet (wall r=%s)" % R)
            return None
        self.mil_hub = (best[1], best[2])
        self.say("military cluster at (%.0f,%.0f): %d tiles from the TC, %+d deg off the enemy side, room for %d buildings (wall r=%s)" % (
            best[1], best[2], best[4], best[3], best[5], R))
        return self.mil_hub

    def _hub_search(self, wide, ex, ey, tc, R, inside, kc, W, H, out):
        for ang in range(-150 if wide else -60, 151 if wide else 61, 15):
            a = math.radians(ang)
            dx, dy = ex * math.cos(a) - ey * math.sin(a), ex * math.sin(a) + ey * math.cos(a)
            for dist in range(int(R) + 6, int(R) + (29 if wide else 19), 2):   # (R+3 was on the real cut line:
                                                                                #  v10d P2, no barracks ever, no Bronze)
                hx, hy = tc.x + dx * dist, tc.y + dy * dist
                if not (5 <= hx < W - 5 and 5 <= hy < H - 5):
                    continue
                if inside is not None and (int(hx), int(hy)) in inside:
                    continue
                room = len(self._hub_footprints(btype=gs.STABLE, hx=hx, hy=hy, radius=7, inside=inside, kc=kc, R=R))
                if room < 3:
                    continue
                out.append((min(room, 8) - abs(ang) / 20.0 - 0.25 * (dist - R - 3), hx, hy, ang, dist, room))

    def _hub_footprints(self, btype, hx, hy, radius, inside, kc, R):
        """Free 3x3 footprints (a lane of 1 tile kept round each) with the centre within `radius` of the hub,
        none of them on the enclosed tiles nor inside the wall radius when the ring is not known yet."""
        tc = self.tc()
        size = SIZES.get(btype, 3)
        out = []
        cut = set(getattr(self, "_wall_cut_tiles", ()) or ())
        for p in self.wall or []:
            cut |= {tuple(c) for c in (getattr(p, "cut", None) or ())}
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                x0, y0 = int(hx + ox - size / 2.0), int(hy + oy - size / 2.0)
                cx, cy = x0 + size / 2.0, y0 + size / 2.0
                d = math.hypot(cx - hx, cy - hy)
                if d > radius:
                    continue
                if inside is not None:
                    if any((xx, yy) in inside for yy in range(y0 - 1, y0 + size + 1) for xx in range(x0 - 1, x0 + size + 1)):
                        continue
                elif math.hypot(cx - tc.x, cy - tc.y) < R + 4:
                    continue
                if cut and any((xx, yy) in cut for yy in range(y0 - 1, y0 + size + 1) for xx in range(x0 - 1, x0 + size + 1)):
                    continue                             # (not on the wall's own line)
                if not self.grid.free(x0, y0, size, 1) or not self.footprint_ok(btype, x0, y0, kc):
                    continue
                out.append((d, x0, y0))
        return out

    def hub_spot(self, btype, wide=False):
        """The free footprint nearest the military cluster's centre (a 1-tile lane round each building)."""
        hub = self.military_hub()
        if hub is None:
            return None
        inside = self.wall_inside_tiles()
        R = self.wall_reach()
        cands = self._hub_footprints(btype, hub[0], hub[1], 14 if wide else 9, inside, self.keep_clear(), R)
        spot = self.place_checked(btype, cands)
        miss = self.__dict__.get("_hub_miss", 0) + 1 if spot is None else 0
        self._hub_miss = miss
        if miss >= 3:
            # the cluster has no room any more (the wall line moved onto it, buildings filled it): choose again
            self.say("military cluster at (%.0f,%.0f) has no free footprint (%d tries): chosen again" % (hub[0], hub[1], miss))
            self.mil_hub = None
            self._hub_miss = 0
            self._hub_try_t = -99
        return spot

    def outside_spot(self, btype):
        """The user: military buildings stand outside the house wall (troops spawn outside, no gate
        needed for them), on the enemy's side, just beyond the wall ring."""
        tc = self.tc()
        if not tc:
            return None
        R = max([p.radius for p in (self.wall or [])] + [FARM_RING + 3])
        ex, ey = self.enemy_dir()
        kc = self.keep_clear()
        inside = None
        for p in self.wall or []:
            if getattr(p, "inside", None):
                inside = p.inside
                break
        cands = []
        for dx in range(-int(R) - 9, int(R) + 10):
            for dy in range(-int(R) - 9, int(R) + 10):
                x0, y0 = int(tc.x + dx - 1.5), int(tc.y + dy - 1.5)
                cx, cy = x0 + 1.5, y0 + 1.5
                d = math.hypot(cx - tc.x, cy - tc.y)
                if inside is not None:
                    # just beyond the enclosed tiles: none of the footprint inside, the nearest enclosed
                    # tile 2-7 tiles away
                    if any((xx, yy) in inside for yy in range(y0 - 1, y0 + 4) for xx in range(x0 - 1, x0 + 4)):
                        continue
                    near = min((math.hypot(xx + 0.5 - cx, yy + 0.5 - cy) for (xx, yy) in inside
                                if abs(xx + 0.5 - cx) <= 8 and abs(yy + 0.5 - cy) <= 8), default=99.0)
                    if near > 7.0:
                        continue
                    if not self.footprint_ok(btype, x0, y0, kc):
                        continue
                    toward = ((cx - tc.x) * ex + (cy - tc.y) * ey) / max(d, 0.1)
                    cands.append((abs(near - 3.5) - 3.0 * toward + self._near_resources_penalty(cx, cy), x0, y0))
                    continue
                if d < R + 2.5 or d > R + 8:
                    continue
                if self.wall and any(math.hypot(cx - p.center[0], cy - p.center[1]) < p.radius + 2.5 for p in self.wall):
                    continue
                if not self.footprint_ok(btype, x0, y0, kc):
                    continue
                toward = ((cx - tc.x) * ex + (cy - tc.y) * ey) / max(d, 0.1)
                cands.append((abs(d - (R + 4)) - 3.0 * toward + self._near_resources_penalty(cx, cy), x0, y0))
        return self.place_checked(btype, cands)

    def unit_tech_needed(self):
        """The tech that makes our army's unit, while it is neither done nor started: the Wheel (28) for
        chariot archers; Improved Bow (56), then Composite Bow (57) for improved bowmen (the user, 14/10: both
        bow upgrades get the food first - a Minoan bot sat on 200 food / 150 wood with Composite Bow available
        and never researched it: with fewer than 4 soldiers only the unit tech passed the gate). None otherwise."""
        if not getattr(self, "archer_plan", False):
            return None
        line = (56, 57) if getattr(self, "archer_kind", "chariot") == "improved" else (28,)
        for tid in line:
            if tid in getattr(self, "techs_done", set()) or tid in self.__dict__.get("techs_started", set()):
                continue
            return tid
        return None

    def horse_army(self):
        """The army is horse units (chariot archers, cavalry, camels): Nobility pays."""
        if getattr(self, "archer_plan", False):
            return getattr(self, "archer_kind", "chariot") == "chariot"
        A = self.tactics or {}
        return not A.get("want_academy")

    def second_building(self):
        """The Tool-age building next to the market that opens the Bronze age: the archery range in the
        'cung R' plan (the user's chariot-archer games: no stable at all), else the stable."""
        return gs.ARCHERY_RANGE if getattr(self, "archer_plan", False) else gs.STABLE

    def decide_army_plan(self):
        """Once, at the Tool age: the archer plan for archer civs, and for a share of the others (the
        user plays it in about 2 games of 5); camel civs keep their camels, Greek / Macedonian their
        hoplites."""
        if getattr(self, "archer_plan", None) is not None or self.age < 2 and not self.tool_clicked:
            return
        civ = tactics.civ_name(self.my_civ)
        self.archer_kind = "chariot"
        off = getattr(self, "civ_off", set())
        if civ == "Minoan":
            plan = True                          # (the user: Minoan plays "cung A" - improved bowmen)
            self.archer_kind = "improved"
        elif civ in ("Egyptian", "Assyrian", "Hittite"):
            plan = True
        elif civ in tactics.CAMEL_CIVS or civ in ("Greek", "Macedonian") or civ == "Yamato":
            plan = False                         # (Yamato: mounted units 25 % cheaper - the stable; the user, 14/10:
                                                 #  "sao Yamato lại đánh cung?" - the 35 % roll gave it improved bowmen)
        elif 59 in off:
            plan = False                         # (the random archer share only for civs with chariot archers: without
                                                 #  them the roll fell to plain improved bowmen)
        else:
            import random
            plan = random.Random(self.me * 7919 + int(self.start_time or 0)).random() < 0.35
        if plan and self.archer_kind == "chariot" and 59 in off:
            self.archer_kind = "improved"        # (no chariot archers in our tree: "cung A" instead)
        if plan and self.archer_kind == "improved" and 56 in off:
            plan = False                         # (no archer line either: the stable plan)
        self.archer_plan = plan
        if plan and self.archer_kind == "improved":
            self.say("army plan: improved bowmen (range instead of stable, Improved Bow + Leather Armor Archers at Bronze) - %s" % civ)
        elif plan:
            self.say("army plan: chariot archers (range instead of stable, Leather Armor Archers + Wheel at Bronze) - %s" % civ)

    def buildings_program(self):
        tc = self.tc()
        if not tc:
            return
        self.decide_army_plan()
        sb = self.second_building()
        # BB (barracks) opens BL / BA: right after the Tool click, while the age researches (the user's games:
        # Tool clicked 8:24-9:30, barracks 9:50-10:40, then market + stable / range) - a Stone age building
        if (self.tool_clicked or self.age >= 2) and gs.BARRACKS in PREREQ.get(sb, ()) and                 not self.any_of(gs.BARRACKS) and not self.pending_of(gs.BARRACKS) and self.can_afford(wood=125):
            spot, why = self.building_spot(gs.BARRACKS)
            if spot:
                self.start_build(gs.BARRACKS, spot, self.builders_near(2, *spot), "(BB opens BL / BA) " + why)
        if self.age >= 2:
            for btype in (gs.MARKET, sb):
                if btype == sb and not self.complete(gs.BARRACKS) and gs.BARRACKS in PREREQ.get(sb, ()):
                    continue                             # (its barracks first)
                if not self.any_of(btype) and not self.pending_of(btype) and self.can_afford(wood=150):
                    spot, why = self.building_spot(btype)
                    if spot:
                        self.start_build(btype, spot, self.builders_near(3, *spot), "(tool age) " + why)
                    if not self.can_afford(wood=150):
                        return                           # (both at once when the wood is there)
        A = self.tactics
        wants = []
        if A and self.age >= 3:
            if A.get("want_temple"):
                wants.append((gs.TEMPLE, 200, "(temple: enemy priests) "))
            if A.get("want_archery"):
                wants.append((gs.ARCHERY_RANGE, 150, "(archery: enemy infantry) "))
            if A.get("want_siege") or A.get("want_iron"):
                if not self.any_of(gs.ARCHERY_RANGE):
                    wants.append((gs.ARCHERY_RANGE, 150, "(BA opens BK) "))
                wants.append((gs.SIEGE_WORKSHOP, 200, "(siege workshop) "))
            if A.get("want_iron") and not self.any_of(gs.TEMPLE):
                wants.append((gs.TEMPLE, 200, "(temple: second Bronze building for Iron) "))
        if self.age >= 3 and str(self.me) in os.environ.get("AOESOLO_TEST_WRITING", "").split(","):
            wants.insert(0, (gs.GOVERNMENT_CENTER, 175, "(test: Writing) "))      # (tests only: shared sight)
        if self.age >= 3 and self.horse_army():
            # the user: the first upgrade of the Government Center, Nobility (+15 % hp), for chariot
            # archers, cavalry and camels - the building comes once there are 3 soldiers
            if len(self.military()) >= 3:
                wants.insert(0, (gs.GOVERNMENT_CENTER, 175, "(government centre: Nobility) "))
        for btype, cost, why0 in wants:
            if not self.any_of(btype) and not self.pending_of(btype) and self.can_afford(wood=cost + 75):
                spot, why = self.building_spot(btype)
                if spot:
                    self.start_build(btype, spot, self.builders_near(2, *spot), why0 + why)
                    return
        if False and self.rules_broken and not self.any_of(gs.BARRACKS) and not self.pending_of(gs.BARRACKS) \
                and self.can_afford(wood=125):
            spot, why = self.building_spot(gs.BARRACKS)
            if spot:
                self.start_build(gs.BARRACKS, spot, self.builders_near(2, *spot), "(counter attack) " + why)

    # ================================================================ military
    def stables(self):
        st = self.complete(gs.STABLE)
        mil = self.military()
        t = self.now()
        # the scout right after the Bronze click (the user: the first thing in Bronze). It counts once it
        # really exists; the order is repeated every 8 s until then, and a new one comes if it dies before
        # the enemy's town is found
        have_scout = any(u.type == gs.SCOUT for u in mil)
        if have_scout:
            self.scout_trained = True
        elif self.scout_trained and self.enemy_base is None and t - getattr(self, "_scout_order_t", -99) > 30:
            self.scout_trained = False                   # (ordered, never came / died: again)
        if self.bronze_clicked and not self.scout_trained and st and t - getattr(self, "_scout_order_t", -99) > 8:
            free = [b for b in st if not self.r.producing(b)]
            if free and self.can_afford(food=100):
                self.g.train(free[0], gs.SCOUT)
                self._scout_order_t = t
                self.say("scout cavalry ordered to find enemy houses and villagers")
        pass
        may_fight = self.age >= 3                 # (the user: no Stone / Tool age army, even when attacked)
        if not may_fight or self.res(gs.HEADROOM) < 1:
            return
        for i, b in enumerate(st):
            if self.r.producing(b):
                continue
            A = self.tactics or tactics.assess(self)
            unit_t, cost = {"camel": (gs.CAMEL, dict(food=70, gold=60)),
                            "chariot": (gs.CHARIOT, dict(food=40, wood=60)),
                            "scout": (gs.SCOUT, dict(food=100))}.get(A["pick"], (gs.CAVALRY, dict(food=70, gold=80)))
            if self.age < 3:
                unit_t, cost = gs.SCOUT, dict(food=100)
            if self.can_afford_unit(**cost):
                self.g.train(b, unit_t)
                if A["pick"] in ("chariot", "scout") and A.get("gold_out") and self.now() - getattr(self, "_gold_out_say", 0) > 120:
                    self._gold_out_say = self.now()
                    self.say("no gold left on the map: the stables make %s, archers come in" % A["pick"])
        for b in self.complete(gs.BARRACKS):
            if False:
                self.g.train(b, gs.CLUBMAN)
        A = self.tactics
        if A and A.get("want_academy"):
            for b in self.complete(gs.ACADEMY):
                if not self.r.producing(b) and self.can_afford_unit(food=60, gold=40):
                    self.g.train(b, gs.HOPLITE)
                    if self.now() - getattr(self, "_acad_say", 0) > 60:
                        self._acad_say = self.now()
                        self.say("academy trains hoplites (%s)" % tactics.civ_name(self.my_civ))
        if getattr(self, "archer_plan", False) and self.bronze_clicked and not st:
            archers = [u for u in mil if tactics.unit_class(u.name) in ("archer", "chariot")]
            if archers:
                self.scout_trained = True
            elif t - getattr(self, "_scout_order_t", -99) > 8:
                rg = [b for b in self.complete(gs.ARCHERY_RANGE) if not self.r.producing(b)]
                if rg and self.can_afford(food=40, wood=20):
                    self.g.train(rg[0], gs.BOWMAN)
                    self._scout_order_t = t
                    self.say("bowman ordered to find the enemy (archer plan: no stable)")
        if A and A.get("want_archery"):
            # "cung R" once the Wheel is in (70 food 40 wood), else "cung A" after Improved Bow (40 / 20),
            # else the basic bowman; the villagers' 50 food stays untouched
            ranged = A.get("ranged", "bowman")
            utype, cost = {"chariot_archer": (gs.CHARIOT_ARCHER, dict(food=40, wood=70)),
                           "improved_bowman": (gs.IMPROVED_BOWMAN, dict(food=40, gold=20)),
                           "composite_bowman": (gs.COMPOSITE_BOWMAN, dict(food=40, gold=20))}.get(
                               ranged, (gs.BOWMAN, dict(food=40, wood=20)))
            archers_now = [u for u in mil if tactics.unit_class(u.name) in ("archer", "chariot")]
            ut = self.unit_tech_needed() if self.age >= 3 else None
            ut_wait = None
            if ut is not None and K.TECHS[ut][1] == gs.ARCHERY_RANGE:
                c = K.TECHS[ut][3]
                ut_wait = dict(food=c.get("food", 0), wood=c.get("wood", 0), gold=c.get("gold", 0))
            for b in self.complete(gs.ARCHERY_RANGE):
                if ut_wait is not None and not self.r.producing(b) and self.can_afford(**ut_wait):
                    ut_wait = None                       # (one range stays free for the bow upgrade: it is paid)
                    continue
                if ut_wait is not None and not self.can_afford(
                        food=ut_wait["food"] + cost.get("food", 0),
                        wood=cost.get("wood", 0) + (ut_wait["wood"] if cost.get("wood") else 0)):
                    break                                # (the bow upgrade's food first, then the units; its wood
                                                         #  only holds units that cost wood - improved bowmen cost gold)
                if getattr(self, "archer_plan", False) and ranged == "bowman" and \
                        (len(archers_now) >= 1 or any(self.r.producing(b2) for b2 in self.complete(gs.ARCHERY_RANGE))):
                    break                                # (the user: one bowman to defend until the Wheel)
                if not self.r.producing(b) and self.can_afford_unit(**cost):
                    self.g.train(b, utype)
                    if self.now() - getattr(self, "_rng_say", 0) > 60:
                        self._rng_say = self.now()
                        self.say("archery range trains %s" % ranged)
        if A and (A.get("want_siege") or A.get("want_iron")):
            siege = sum(1 for u in mil if tactics.unit_class(u.name) == "siege")
            for b in self.complete(gs.SIEGE_WORKSHOP):
                if siege < 3 and A.get("want_siege") and not self.r.producing(b) and self.can_afford(wood=180 + 60, gold=80 + 60):
                    self.g.train(b, gs.STONE_THROWER)
                    siege += 1
                    self.say("stone thrower ordered (enemy walled in / out-developing us)")
        if A and A.get("want_temple"):
            priests = sum(1 for u in mil if tactics.unit_class(u.name) == "priest")
            for b in self.complete(gs.TEMPLE):
                if priests < 2 and not self.r.producing(b) and self.can_afford(gold=125 + 80):
                    self.g.train(b, gs.PRIEST)
                    priests += 1
                    self.say("priest ordered (enemy priests / priest civ)")
        want_st = min(MAX_STABLES, max(2, len(self.s.villagers) // 10))
        busy_st = all(self.r.producing(b) for b in st) if st else True
        academy_civ = bool(A and A.get("want_academy"))
        # the user: Greek / Macedonian - one stable, then every military building is an Academy
        more_t = gs.ACADEMY if academy_civ and self.any_of(gs.STABLE) else gs.STABLE
        n_mil = len(self.any_of(gs.STABLE)) + (len(self.any_of(gs.ACADEMY)) if academy_civ else 0)
        if getattr(self, "archer_plan", False):
            more_t = gs.ARCHERY_RANGE                 # (the user: 4-8 ranges, no stable)
            n_mil = len(self.any_of(gs.ARCHERY_RANGE))
            want_st = min(8, max(1, len(self.complete(gs.FARM)) // 2))   # (the user: 4 ranges need >= 8 farms)
        if academy_civ and self.forward_academy():
            return
        first_academy = academy_civ and not self.any_of(gs.ACADEMY)
        if (self.age >= 3 and (n_mil < want_st or first_academy) and not self.pending_of(more_t)
                and (busy_st or first_academy or self.can_afford(food=200, gold=200))
                and self.can_afford(wood=150 + (0 if first_academy else 75))):    # 150 wood (+ a farm kept in hand)
            spot, why = self.building_spot(more_t)
            if spot:
                self.start_build(more_t, spot, self.builders_near(2, *spot),
                                 ("(academy) " if more_t == gs.ACADEMY else "(extra stable) ") + why)

    def second_stone_building(self):
        """The Tool age needs two Stone age buildings of different kinds (two granaries do not count):
        the granary and one of pit / barracks / dock, complete."""
        for bt in (gs.STORAGE_PIT, gs.BARRACKS, gs.DOCK):
            if self.complete(bt):
                return True
        return False

    def tool_second_building(self, nvil):
        """The Tool age is otherwise ready but no second building stands: a storage pit next to the town
        (inside the wall, 7-11 tiles from the TC, toward the choppers). The user's 1v2: the Shang bot's
        only pit was 40 tiles out, its 5 builders idle for 1 700 s - 1 000 food banked, never aged."""
        t = self.now()
        tc = self.tc()
        if (not tc or self.age != 1 or self.tool_clicked or nvil < self.stone_target() - 3
                or not self.complete(gs.GRANARY) or self.second_stone_building() or self.res(gs.FOOD) < 350):
            return
        pend = [p for p in self.pending if p.btype in (gs.STORAGE_PIT, gs.BARRACKS)]
        if any(t - p.t < 60 for p in pend):
            return                                       # one is on its way
        if t - getattr(self, "_tool2_t", -999) < 30 or not self.can_afford(wood=120):
            return
        self._tool2_t = t
        choppers = [v for v in self.s.villagers if self.role_name(v.id) == "wood"]
        if choppers:
            ax = sum(v.x for v in choppers) / len(choppers)
            ay = sum(v.y for v in choppers) / len(choppers)
        else:
            ax, ay = tc.x, tc.y
        sz = SIZES.get(gs.STORAGE_PIT, 2)
        kc = self.keep_clear()
        cands = []
        for i in range(16):
            a = i * math.pi / 8
            for r in (7.5, 8.5, 9.5, 11.0):
                cx, cy = tc.x + math.cos(a) * r, tc.y + math.sin(a) * r
                x0, y0 = int(round(cx - sz / 2.0)), int(round(cy - sz / 2.0))
                if not self.footprint_ok(gs.STORAGE_PIT, x0, y0, keep_clear=kc):
                    continue
                if getattr(self, "wall", None) is not None and self.wall_sealed and not self.wall_inside(cx, cy):
                    continue
                cands.append((math.hypot(cx - ax, cy - ay) + 0.5 * r, x0, y0))
        spot = self.place_checked(gs.STORAGE_PIT, cands) if cands else None
        if not spot:
            self.say("tool age: no spot for a second building near the TC")
            return
        builders = self.builders_near(2, *spot)
        if builders and self.start_build(gs.STORAGE_PIT, spot, builders, "(tool age: second building)"):
            self.say("tool age: second building - a pit %.0f tiles from the TC (the far one never came)"
                     % math.hypot(spot[0] - tc.x, spot[1] - tc.y))

    def forward_academy(self):
        """One academy near home already: the next one goes near the enemy (hoplites are slow). Returns
        True when it was started now."""
        tc = self.tc()
        if not tc or self.age < 3 or self.pending_of(gs.ACADEMY) or not self.can_afford(wood=150):
            return False
        acads = self.any_of(gs.ACADEMY)
        if not any(a.dist(tc.x, tc.y) <= 30 for a in acads):
            return False
        A = self.tactics or {}
        etc = None
        for o in getattr(self.s, "enemy_all", []):
            if o.type == gs.TOWN_CENTER and o.owner in self.enemies:
                if etc is None or o.dist(tc.x, tc.y) < math.hypot(etc[0] - tc.x, etc[1] - tc.y):
                    etc = (o.x, o.y)
        etc = etc or self.enemy_base
        if etc is None:
            return False
        if any(math.hypot(a.x - etc[0], a.y - etc[1]) <= 36 for a in acads):
            return False                              # a forward academy is there already
        if t_last := getattr(self, "_fwd_acad_t", None):
            if self.now() - t_last < 90:
                return False
        ux, uy = unit(tc.x - etc[0], tc.y - etc[1])  # from their TC towards ours
        nx, ny = -uy, ux
        cands = []
        for along in (20, 22, 24, 26):
            for lat in (0, -4, 4, -8, 8):
                cx, cy = etc[0] + ux * along + nx * lat, etc[1] + uy * along + ny * lat
                x0, y0 = int(cx - 1.5), int(cy - 1.5)
                if not self.footprint_ok(gs.ACADEMY, x0, y0):
                    continue
                # never next to an enemy building (their army spawns there)
                if any(b.dist(cx, cy) < 8 for b in self.s.enemy_buildings_seen):
                    continue
                cands.append((abs(along - 22) + 0.3 * abs(lat), x0, y0))
        spot = self.place_checked(gs.ACADEMY, cands) if cands else None
        self._fwd_acad_t = self.now()
        if not spot:
            return False
        builders = self.builders_near(2, tc.x, tc.y, roles=("wood",)) or self.builders_near(2, tc.x, tc.y)
        if len(builders) < 1:
            return False
        if self.start_build(gs.ACADEMY, spot, builders, "(forward academy, %.0f tiles from the enemy TC)"
                            % math.hypot(spot[0] - etc[0], spot[1] - etc[1])):
            return True
        return False

    def research_plan(self):
        """The user: in the long run every useful technology gets researched (never stone mining,
        never walls / towers). The game's research table says what is available (state 1) and done
        (state 3); the plan orders the available ones by priority (the Wheel first: villagers run from
        raids), tries the known research building, else every building type in turn, and checks next
        tick that the research really started."""
        t = self.now()
        if not self.bronze_clicked or t - getattr(self, "_rp_t", -99) < 4:
            return
        self._rp_t = t
        try:
            states = self.g.research_states(self.me)
        except Exception as e:  # noqa: BLE001
            self.say("research states unreadable: %r" % (e,))
            return
        if not states:
            return
        done = {i for i, st in enumerate(states) if st == 3}
        active = {i for i, st in enumerate(states) if st == 2 and i not in K.TECH_AGES}   # (the age-up runs at the TC)
        avail = [i for i, st in enumerate(states) if st == 1 and i not in K.TECH_NEVER and i not in K.TECH_AGES]
        new_done = done - self.techs_done
        names = [K.tech_name(i) for i in sorted(new_done) if i in K.TECHS]
        if names and self.techs_done:
            self.say("researched: %s" % ", ".join(names))
        self.techs_done = done
        # one research per BUILDING TYPE at a time, several types in parallel (the user, 13/10: after
        # 45 minutes the bots had 1-11 techs each - one research at a time for the whole town, each
        # attempt blocked 6 s, and a villager + a cavalry reserved on top of every cost)
        pend = getattr(self, "_rp_pending", None) or {}
        if not isinstance(pend, dict):
            pend = {}
        for btype, (tid, t0) in list(pend.items()):
            if tid in active or tid in done:
                self.say("research %s started" % K.tech_name(tid))
                self.__dict__.setdefault("techs_started", set()).add(tid)
                del pend[btype]
                self._rp_fail.pop(tid, None)
            elif t - t0 > 6:                             # (order lag ~1-2 s, ticks ~1 s)
                del pend[btype]
                self._rp_fail[tid] = self._rp_fail.get(tid, 0) + 1     # that building did not take it
        self._rp_pending = pend
        busy_types = {K.TECHS[tid][1] for tid in active if tid in K.TECHS} | set(pend)
        avail = [tid for tid in avail if tid in K.TECHS]    # (states 1 of pseudo-techs: buildings, civ bonuses)
        prio = K.TECH_PRIORITY
        if getattr(self, "archer_plan", False):
            first = [56, 57, 41, 44] if getattr(self, "archer_kind", "chariot") == "improved" else [28, 41, 34, 56, 44]
            prio = first + [x for x in K.TECH_PRIORITY if x not in first]
        elif self.horse_army():
            prio = K.TECH_PRIORITY[:2] + [34] + [x for x in K.TECH_PRIORITY[2:] if x != 34]   # Nobility early
        # the army's own upgrades only (the user: wood 2, attack 4 for the melee army, armour 4 for the
        # horses): an archer army never buys melee attack / horse or infantry armour, a horse army never
        # the archers' armour or bows, the hoplites neither of them
        MELEE_ATT, HORSE_ARM, INF_ARM, ARCH = {46, 51}, {42, 45}, {40, 43, 47}, {41, 44, 56, 57}
        SWORD = {63, 64, 65, 66, 77}                      # (the barracks line: no bot fields swordsmen - civ1 / civ3:
                                                          #  Minoan researched Axe before Improved Bow)
        if getattr(self, "archer_plan", False):
            useless = MELEE_ATT | HORSE_ARM | INF_ARM | SWORD
        elif (self.tactics or {}).get("want_academy"):
            useless = HORSE_ARM | ARCH | SWORD
        else:
            useless = INF_ARM | ARCH | SWORD
        if (self.tactics or {}).get("want_archery") and not getattr(self, "archer_plan", False):
            useless -= ARCH                               # (archers against their infantry: their armour too)
        prio = [x for x in prio if x not in useless]
        avail = [x for x in avail if x not in useless]
        test_writing = str(self.me) in os.environ.get("AOESOLO_TEST_WRITING", "").split(",")
        if test_writing:
            prio = [114] + [x for x in prio if x != 114]       # (tests only: Writing first)
        order = [tid for tid in prio if tid in avail] + [tid for tid in avail if tid not in prio]
        army_full = len(self.military()) >= 12
        # the first 4 soldiers before any tech, unless the bank has 300 food to spare - except the tech that
        # makes our unit (the Wheel for chariot archers, Improved Bow for improved bowmen)
        unit_tech = {28} if getattr(self, "archer_kind", "chariot") == "chariot" and getattr(self, "archer_plan", False) \
            else ({56, 57} if getattr(self, "archer_plan", False) else set())
        if test_writing:
            unit_tech = set(unit_tech) | {114}
        if len(self.military()) < 4:                      # (also while Bronze researches)
            order = [tid for tid in order if tid in unit_tech or
                     self.can_afford(food=300 + K.TECHS[tid][3].get("food", 0))]
        ut = self.unit_tech_needed()
        if ut is not None:
            # the building of our unit's tech stays free for it (the user: the Wheel the moment Bronze is
            # in). One exception (the user): Wood Working may go first while the Bronze research is not
            # half done yet - it ends about when Bronze comes; past 50 % the Wheel first, then Wood Working
            ut_b = K.TECHS[ut][1]
            t_bc = getattr(self, "bronze_click_t", None)
            early = self.age == 2 and t_bc is not None and t - t_bc < 0.5 * K.TECHS[gs.TECH_BRONZE_AGE][2]
            order = [tid for tid in order if tid == ut or K.TECHS[tid][1] != ut_b or (tid == 107 and early)]
        if t - getattr(self, "_resdbg_t", -99) > 60:
            self._resdbg_t = t
            self.say("RESDBG avail %s | order %s | busy buildings %s | pending %s | fails %s | unit tech %s | army %d" % (
                sorted(avail)[:12], order[:6], sorted(busy_types), dict(pend), {k: v for k, v in self._rp_fail.items() if v},
                self.unit_tech_needed(), len(self.military())))
        # the food / gold set aside for the first tech in the order whose building is free: the stables and
        # the TC spend every 50-70 food at once, so in Bronze the food never reached a tech's 100-300
        # (tech1: 1 tech in 13 minutes of Bronze with 1 900 gold in the bank) - units wait for it now
        self.research_reserve = {}
        if self.age >= 3 and (len(self.military()) >= 3 or self.res(gs.GOLD) > 500) and not getattr(self, "attackers", None):
            for tid in order:
                name, btype, _secs, cost, _req = K.TECHS[tid]
                if btype in busy_types or self._rp_fail.get(tid, 0) >= 4:
                    continue
                if not [b for b in self.complete(btype) if not self.r.producing(b)]:
                    continue
                self.research_reserve = dict(cost)
                break
        first = True
        res_r = getattr(self, "research_reserve", None) or {}
        if ut is not None:
            # our unit's tech keeps its money whatever building the others are researched at (civ3: Minoan
            # in Bronze at 15:50, Leather Armor Archers at the pit + Axe at the barracks took the food and
            # Improved Bow came at 20:46 - three improved bowmen by minute 23)
            res_r = dict(K.TECHS[ut][3])
        for tid in order:
            tries = self._rp_fail.get(tid, 0)
            if tries >= 4 and t - self._rp_fail_t.get(tid, 0) < 120:
                continue
            name, btype, _secs, cost, _req = K.TECHS[tid]
            if btype in busy_types:
                continue
            if (first and res_r and dict(cost) == res_r) or tid == self.unit_tech_needed() or (test_writing and tid == 114):
                # (our unit's tech at its plain cost: with the 100-food margin the Wheel waited 4.6 minutes
                #  while the TC took every food above 225 for villagers - cr2v2c)
                # the tech the food is being kept for: its plain cost is enough (with the old 60-100
                # margin on top the Wheel's 175 food never came - cheaper techs further down took it:
                # units4, an archer plan without chariot archers)
                first = False
                if not self.can_afford(food=cost.get("food", 0), wood=cost.get("wood", 0), gold=cost.get("gold", 0)):
                    continue
            else:
                first = False
                # the villager queue and some army money come first, less so with a full army; and the
                # food kept for the first tech is not touched
                if not self.can_afford(food=cost.get("food", 0) + (60 if army_full else 100) + res_r.get("food", 0),
                                       wood=cost.get("wood", 0) + res_r.get("wood", 0),
                                       gold=cost.get("gold", 0) + ((40 if army_full else 100) if cost.get("gold") else 0)
                                       + res_r.get("gold", 0)):
                    continue
            bld = [b for b in self.complete(btype) if not self.r.producing(b)]
            if not bld:
                # (a building busy with a unit is not a failure: the range was making a bowman when Bronze came,
                #  each 4 s try counted, four of them = a 120 s pause - Improved Bow 200 s after Bronze, 14/10)
                continue
            self.g.research(bld[0], tid)
            pend[btype] = (tid, t)
            busy_types.add(btype)
            self._rp_fail_t[tid] = t
            self.say("research %s (%s) at building type %d" % (name, ", ".join("%s %d" % kv for kv in cost.items()), btype))

    def upgrades(self):
        """(kept for reference; research_plan() does this now)"""
        pits = [p for p in self.complete(gs.STORAGE_PIT) if not self.r.producing(p)]
        if not pits:
            return
        for tech, cost in ((TECH_TOOL_WORKING, 100), (TECH_LEATHER_CAV, 125)):
            if tech in self.techs_done:
                continue
            if self.can_afford(food=cost + 50):
                self.g.research(pits[0], tech)
                self.techs_done.add(tech)
                self.s.res[gs.FOOD] -= cost
                self.say("research %d" % tech)
            return

    def econ_upgrades(self):
        """Market techs the recorded players buy: Wood Working once Bronze is clicked (16/36 players,
        right when Bronze arrives), The Wheel in Bronze (23/36, ~16 min)."""
        if not self.bronze_clicked:
            return
        mk = [m for m in self.complete(gs.MARKET) if not self.r.producing(m)]
        if not mk:
            return
        for tech, food, wood, need_age in ((TECH_WOODWORKING, 120, 75, 2), (TECH_WHEEL, 175, 75, 3)):
            if tech in self.techs_done or self.age < need_age:
                continue
            if TECH_TOOL_WORKING not in self.techs_done:
                return                                   # the attack upgrade comes first
            if self.can_afford(food=food + 100, wood=wood + 50):
                self.g.research(mk[0], tech)
                self.techs_done.add(tech)
                self.s.res[gs.FOOD] -= food
                self.s.res[gs.WOOD] -= wood
                self.say("research %d at the market" % tech)
            return

    def army(self):
        s = self.s
        mil = self.military()
        if not mil:
            return
        tc = self.tc()
        t = self.now()
        may_attack = self.bronze_clicked or self.rules_broken
        if os.environ.get("AOESOLO_PEACE") == "1":
            may_attack = False                       # (tests only: nobody attacks, everybody defends)
        if not may_attack:
            for u in mil:                      # nobody attacks before Bronze is clicked ...
                hitters = [e for e in self.attackers if e.dist(u.x, u.y) < 12 or (tc and e.dist(tc.x, tc.y) < 12)]
                if hitters:                    # ... but enemy soldiers attacking us are fought back
                    tgt = min(hitters, key=lambda e: e.dist(u.x, u.y))
                    if not self.recent(u.id, ("o", tgt.id), within=3):
                        self.order([u], tgt)
                    continue
                if not self.recent(u.id, within=8) and tc and u.dist(tc.x, tc.y) > 6:
                    self.move([u], tc.x + 3, tc.y + 3)
            return
        enemy_vils = [e for e in s.enemy if e.cls == gs.CLS_VILLAGER and e.hp > 0]
        enemy_army = [e for e in s.enemy if e.kind == gs.KIND_COMBAT and e.cls != gs.CLS_VILLAGER and e.hp > 0
                      and "Artifact" not in e.name]
        threats = [e for e in enemy_army if tc and e.dist(tc.x, tc.y) < 20]
        A_mode_pre = (self.tactics or {}).get("mode")
        # the user's "điều cung": in every mode an archer under arrow fire steps sideways (a missile aimed
        # at a unit moving across its path misses), shoots again, steps the other way...
        self.micro_probe(mil)
        # never a losing fight piece by piece (ms10: chariot archers coming 1-2 at a time died to 8 camels):
        # a unit whose enemy within 9 tiles outweighs ours there by 1.5x falls back to the TC to group
        # (not when they are at our town: the defence there stays)
        if tc and A_mode_pre != "defend":
            fall = set()
            for u in mil:
                if u.type == gs.SCOUT or u.dist(tc.x, tc.y) < 15:
                    continue
                foes9 = [e for e in enemy_army if e.dist(u.x, u.y) <= 9]
                if not foes9:
                    continue
                ev = sum(tactics.VALUE.get(tactics.unit_class(e.name), 1.0) * max(0.2, e.hp / max(1.0, e.maxhp or 1.0)) for e in foes9)
                ov = sum(tactics.VALUE.get(tactics.unit_class(o.name), 1.0) * max(0.2, o.hp / max(1.0, o.maxhp or 1.0))
                         for o in mil if o.dist(u.x, u.y) <= 9)
                if ev > 1.5 * ov:
                    fall.add(u.id)
                    if not self.recent(u.id, ("fall",), within=4):
                        self.move([u], tc.x + 4, tc.y + 4)
                        self.mark([u], ("fall",))
                        self.retreat_until[u.id] = t + 4.0
            if fall:
                if t - getattr(self, "_fall_say", -99) > 30:
                    self._fall_say = t
                    self.say("FALLBACK %d soldiers outnumbered (their strength > 1.5x ours within 9 tiles): back to the TC to group" % len(fall))
                for u in mil:
                    if u.id in fall:
                        self.hp_prev[u.id] = u.hp
                mil = [u for u in mil if u.id not in fall]
                if not mil:
                    return
        # (A/B tests: AOESOLO_MICRO_OFF="3,4" - those players keep the old way: a dodge only inside a raid)
        micro_off = str(self.me) in os.environ.get("AOESOLO_MICRO_OFF", "").split(",")
        dodging = set() if micro_off else {u.id for u in mil if self.archer_dodge(u, enemy_army)}
        # archers with enemy soldiers close by fight as one: focus fire, the weak step back (archer_fight)
        fought = set() if micro_off else self.archer_fight([u for u in mil if u.id not in dodging], enemy_army, tc)
        handled = dodging | fought
        if handled:
            for u in mil:
                if u.id in handled:
                    self.hp_prev[u.id] = u.hp
            mil = [u for u in mil if u.id not in handled]
            if not mil:
                return
        lone = self.lone_scouts(mil, enemy_army, tc)
        if lone:
            for u in mil:
                if u.id in lone:
                    self.hp_prev[u.id] = u.hp
            mil = [u for u in mil if u.id not in lone]
            if not mil:
                return
        A = tactics.assess(self)
        if demo_dump.enabled() and self.age >= 3 and A["mode"] in ("raid", "assault") and len(self.military()) >= 3:
            ea = [[o.x, o.y, tactics.unit_class(o.name), o.owner] for o in getattr(s, "enemy_all", [])
                  if o.kind == 70 and o.cls != 4 and "Artifact" not in o.name]
            ev = [[o.x, o.y, o.owner] for o in getattr(s, "enemy_all", []) if o.cls == 4]
            eb = [[o.x, o.y, o.type, o.owner] for o in getattr(s, "enemy_all", []) if o.kind == 80]
            demo_dump.write(self, "army", {
                "mode": A["mode"], "pick": A["pick"], "our_v": A["our_v"], "enemy_v": A["enemy_v"],
                "threat_v": A["threat_v"], "ours": [[u.x, u.y, tactics.unit_class(u.name), u.hp] for u in mil],
                "seen": [[e.x, e.y, tactics.unit_class(e.name)] for e in enemy_army],
                "enemy_all_army": ea, "enemy_all_vils": ev, "enemy_all_bld": eb,
                "enemy_bld_seen": [[o.x, o.y, o.type] for o in s.enemy_buildings_seen],
                "enemy_base": list(self.enemy_base) if self.enemy_base else None,
                "enemy_tc": list(A["enemy_tc"]) if A.get("enemy_tc") else None})
        if A["mode"] == "defend":
            # everybody home: meet the threat near the TC, never chase it out of the base
            for u in mil:
                near = [e for e in enemy_army if tc and e.dist(tc.x, tc.y) < tactics.DEFEND_RADIUS]
                if near:
                    tgt = min(near, key=lambda e: e.dist(u.x, u.y))
                    if not self.recent(u.id, ("o", tgt.id), within=3):
                        self.order([u], tgt)
                elif tc and u.dist(tc.x, tc.y) > 8 and not self.recent(u.id, within=6):
                    self.move([u], tc.x + 3, tc.y + 3)
            for u in mil:
                self.hp_prev[u.id] = u.hp
            return
        if A["mode"] == "assault" and A.get("enemy_tc"):
            ex, ey = A["enemy_tc"]
            for u in mil:
                near_e = [e for e in enemy_army + enemy_vils if e.dist(u.x, u.y) < 8]
                if near_e:
                    tgt = min(near_e, key=lambda e: (0 if e.cls == gs.CLS_VILLAGER else 1, e.dist(u.x, u.y)))
                    if not self.recent(u.id, ("o", tgt.id), within=3):
                        self.order([u], tgt)
                elif u.dist(ex, ey) > 6:
                    if not self.recent(u.id, within=5):
                        self.move([u], ex, ey)
                else:
                    bld = [b_ for b_ in s.enemy_buildings_seen if b_.dist(u.x, u.y) < 10]
                    if bld and not self.recent(u.id, within=4):
                        self.order([u], min(bld, key=lambda b_: b_.dist(u.x, u.y)))
            for u in mil:
                self.hp_prev[u.id] = u.hp
            return
        if A["mode"] == "build":
            # the army waits at home (and still answers anyone attacking our villagers)
            for u in mil:
                near = [e for e in self.attackers if e.hp > 0]
                if near:
                    tgt = min(near, key=lambda e: e.dist(u.x, u.y))
                    if not self.recent(u.id, ("o", tgt.id), within=3):
                        self.order([u], tgt)
                elif tc and u.dist(tc.x, tc.y) > 10 and not self.recent(u.id, within=8):
                    self.move([u], tc.x + 4, tc.y + 4)
            for u in mil:
                self.hp_prev[u.id] = u.hp
            return
        threats += [e for e in self.attackers if e not in threats and e.hp > 0]   # whoever hits our people
        scouts = [u for u in mil if u.type == gs.SCOUT]
        fighters = [u for u in mil if u.type != gs.SCOUT]
        if getattr(self, "archer_plan", False):
            # the user: the first chariot archers find the enemy's town (fast, wide sight) and attack what
            # they meet - no group to wait for; the one bowman before the Wheel defends the town
            riders = [u for u in fighters if u.type == gs.CHARIOT_ARCHER]
            if riders and not threats:
                for u in fighters:
                    if u not in riders and tc and u.dist(tc.x, tc.y) > 10 and not self.recent(u.id, within=8):
                        self.move([u], tc.x + 4, tc.y + 4)
                for u in riders:
                    self.hit_and_run(u, enemy_army, enemy_vils, threats)
                for u in mil:
                    self.hp_prev[u.id] = u.hp
                return
        if len(fighters) >= ATTACK_GROUP or (A["mode"] == "assault" and len(fighters) >= 2):
            self.attacking = True              # (assault = we are the stronger side: go at once, the user)
        if len(fighters) < 1:
            self.attacking = False
        group = scouts + (fighters if self.attacking or threats else [])
        for u in fighters:
            if u in group:
                continue
            if tc and u.dist(tc.x, tc.y) > 10 and not self.recent(u.id, within=8):
                self.move([u], tc.x + 4, tc.y + 4)
        for u in group:
            self.hit_and_run(u, enemy_army, enemy_vils, threats)
        for u in mil:
            self.hp_prev[u.id] = u.hp

    def micro_probe(self, mil):
        """Measures for the user's archer micro (shoot - side step during the reload - shoot):
          reload: the raw floats of up to 3 of our archers that are attacking, every tick; a field that falls
                  and jumps back up regularly (a saw-tooth) is the attack timer - its period is the reload;
          lag:    every side step / retreat move: the time until the unit really starts moving.
        PROBE lines; on in every game (cheap: 3 units x 128 floats a tick)."""
        import struct
        t = self.now()
        P = self.__dict__.setdefault("_probe", {"hist": {}, "said": set(), "lags": [], "moves": {}})
        # lag: the moves given by the micro (archer_dodge / archer_fight store them)
        for uid, (t0, x0, y0) in list(P["moves"].items()):
            u = self.obj_by_id(uid)
            if u is None or t - t0 > 8:
                del P["moves"][uid]
                continue
            if math.hypot(u.x - x0, u.y - y0) > 0.3:
                P["lags"].append(t - t0)
                del P["moves"][uid]
        if len(P["lags"]) >= 20 and t - P.get("lag_say", -99) > 120:
            P["lag_say"] = t
            ls = sorted(P["lags"])
            self.say("PROBE lag: order -> moving, %d moves: median %.2f s, p10 %.2f, p90 %.2f (game seconds)" % (
                len(ls), ls[len(ls) // 2], ls[len(ls) // 10], ls[9 * len(ls) // 10]))
            P["lags"] = P["lags"][-60:]
        shooters = []
        for u in mil:
            if tactics.unit_class(u.name) != "archer":
                continue
            act = self.r.action(u)
            if act and act[1] and any(e.ptr == act[1] for e in self.s.enemy):
                shooters.append(u)
        busy = P.get("thread") is not None and P["thread"].is_alive()
        todo = [u for u in shooters if u.name not in P["said"]]
        if todo and not busy:
            u = todo[0]
            import threading
            P["thread"] = threading.Thread(target=self._probe_sample, args=(u.ptr, u.name), daemon=True)
            P["thread"].start()

    def _probe_sample(self, ptr, name):
        """20 Hz for 10 s (real time) on one attacking archer: the saw-tooth field and its period, game seconds."""
        import struct
        import time as _t
        P = self._probe
        samples = []
        t_end = _t.time() + 10.0
        while _t.time() < t_end:
            raw = self.g.m.read(ptr, 0x200)
            gt = self.g.m.u32(self.g.world() + 4) / 1000.0 if self.g.world() else None
            if raw and gt is not None:
                samples.append((gt, struct.unpack_from("<128f", raw, 0)))
            _t.sleep(0.05)
        best = None
        for k in range(128):
            vals = [(tt, f[k]) for tt, f in samples]
            if len(vals) < 40 or not all(-0.01 <= v <= 6.0 for _tt, v in vals):
                continue
            ups = [tt for (ta, va), (tt, vb) in zip(vals, vals[1:]) if vb - va > 0.4]
            downs = sum(1 for (ta, va), (tt, vb) in zip(vals, vals[1:]) if -0.6 < vb - va < -0.005)
            if len(ups) >= 3 and downs >= 10:
                per = sorted(b2 - a2 for a2, b2 in zip(ups, ups[1:]))
                mid = per[len(per) // 2]
                spread = (per[-1] - per[0]) / max(0.01, mid)
                cand = (spread, k, mid, len(ups), max(v for _tt, v in vals))
                if best is None or cand < best:
                    best = cand
        P["said"].add(name)
        if best is None:
            self.say("PROBE reload %s: no saw-tooth field in %d samples" % (name, len(samples)))
        else:
            self.say("PROBE reload %s: field +0x%x saw-tooth, period %.2f game s (%d resets, peak %.2f, spread %.2f, %d samples)" % (
                name, 4 * best[1], best[2], best[3], best[4], best[0], len(samples)))

    def archer_dodge(self, u, foes):
        """An archer (bowman, chariot archer) that enemy archers / chariot archers / siege aim at: a step of
        2.5 tiles across their line, left / right in turn, held 1.2 s, then it shoots again. Done when it
        was just hit, or every 2.5 s while it is aimed at (the arrows are in the air before they hurt).
        Below 35 % hp it is left to the retreat. True while it steps (the caller gives it no other order)."""
        if tactics.unit_class(u.name) != "archer":
            return False
        t = self.now()
        if t < self.retreat_until.get(u.id, 0):
            return True
        hurt = u.hp < self.hp_prev.get(u.id, u.hp) - 0.01   # (hp_prev is updated by army() at the end)
        if u.hp < 0.35 * (u.maxhp or 1):
            return False
        shooters = []
        for e in foes:
            if e.dist(u.x, u.y) > 10 or tactics.unit_class(e.name) not in ("archer", "chariot", "siege"):
                continue
            act = self.r.action(e)
            if act and act[1] == u.ptr:
                shooters.append(e)
        if not shooters:
            return False
        last = self.__dict__.setdefault("_dodge_t", {}).get(u.id, -99)
        # only when just hit, at most every 3 s (A/B ab1-ab6: dodging every 1.5 s while aimed at kept the
        # archers walking instead of shooting - 120 losses against 112 for the old way)
        if not hurt or t - last < 3.0:
            return False
        self.__dict__["_dodge_n_total"] = self.__dict__.get("_dodge_n_total", 0) + 1
        e0 = min(shooters, key=lambda e: e.dist(u.x, u.y))
        dx, dy = unit(u.x - e0.x, u.y - e0.y)
        n = self.dodge_n.get(u.id, u.id) + 1
        self.dodge_n[u.id] = n
        side = 1 if (n % 2) else -1                      # left, right, left ... (no drift)
        W, H = self.r.W, self.r.H
        gx = min(W - 2.0, max(1.0, u.x - dy * 1.8 * side))
        gy = min(H - 2.0, max(1.0, u.y + dx * 1.8 * side))
        self.move([u], gx, gy)
        self.__dict__.setdefault("_probe", {"hist": {}, "said": set(), "lags": [], "moves": {}})["moves"][u.id] = (t, u.x, u.y)
        self.retreat_until[u.id] = t + 0.9
        self._dodge_t[u.id] = t
        if t - getattr(self, "_dodge_say", 0) > 20:
            self._dodge_say = t
            self.say("DODGE archer #%d steps sideways out of %s #%d's arrows (%s)" % (
                u.id, e0.name, e0.id, "hit" if hurt else "aimed at"))
        return True

    def archer_fight(self, archers, enemy_army, tc):
        """Archers (bowmen, chariot archers) with enemy soldiers within 9 tiles: the soldiers first, never
        their villagers then (cr2v2c: bowmen chased villagers while chariot archers shot them). One target
        for all - the enemy archer / chariot archer in range of most of ours, the weakest of those (a dead
        archer stops shooting: focus fire wins duels); a hurt one (< 35 %) steps 6 tiles back towards home
        for 3 s. Returns the ids given an order here."""
        arch = [u for u in archers if tactics.unit_class(u.name) == "archer"]
        if not arch or not enemy_army:
            return set()
        t = self.now()
        foes = [e for e in enemy_army if e.hp > 0 and min(e.dist(u.x, u.y) for u in arch) <= 9]
        if not foes:
            return set()
        done = set()
        engaged = [u for u in arch if any(e.dist(u.x, u.y) <= 9 for e in foes)]
        for u in engaged:
            if u.hp < 0.35 * (u.maxhp or 1) and t >= self.retreat_until.get(u.id, 0):
                e0 = min(foes, key=lambda e: e.dist(u.x, u.y))
                if e0.dist(u.x, u.y) < 8:
                    hx, hy = (tc.x, tc.y) if tc else (u.x, u.y)
                    ax, ay = unit(u.x - e0.x, u.y - e0.y)
                    bx, by = unit(hx - u.x, hy - u.y)
                    dx, dy = unit(ax + bx, ay + by)
                    self.move([u], u.x + dx * 6, u.y + dy * 6)
                    self.retreat_until[u.id] = t + 3.0
                    done.add(u.id)
        fighters = [u for u in engaged if u.id not in done and t >= self.retreat_until.get(u.id, 0)]
        if not fighters:
            return done
        # kiting melee (the user): their cavalry / camels / infantry / chariots / elephants close to ANY of the
        # group -> the WHOLE group steps back (the ones behind would block the front ones), then shoots again
        # only from melee SLOWER than the archer (ms1-ms6: chariot archers kiting camels - as fast as they are,
        # with a bonus on them - were caught at 1-3 tiles while stepping back: 99 losses against 72): chariot /
        # horse archers (speed ~2.0) kite infantry, hoplites, elephants; bowmen (~1.2) hoplites and elephants
        SLOW = {"infantry": 1.2, "hoplite": 0.9, "elephant": 0.8}
        melee = [e for e in foes if tactics.unit_class(e.name) in SLOW]
        if melee and not str(self.me) in os.environ.get("AOESOLO_KITE_OFF", "").split(","):
            def fast(u):
                return 2.0 if ("Chariot" in u.name or "horse" in u.name.lower()) else 1.2
            close = [(e, u) for e in melee for u in fighters
                     if e.dist(u.x, u.y) < KITE_R and fast(u) > SLOW[tactics.unit_class(e.name)] + 0.2]
            if close:
                mx = sum(e.x for e, _u in close) / len(close)
                my = sum(e.y for e, _u in close) / len(close)
                gx = sum(u.x for u in fighters) / len(fighters)
                gy = sum(u.y for u in fighters) / len(fighters)
                ax, ay = unit(gx - mx, gy - my)
                hx, hy = (tc.x, tc.y) if tc else (gx, gy)
                bx, by = unit(hx - gx, hy - gy)
                dx, dy = unit(ax * 2 + bx, ay * 2 + by)     # away from them, a little towards home
                W, H = self.r.W, self.r.H
                for u in fighters:
                    self.move([u], min(W - 2.0, max(1.0, u.x + dx * KITE_STEP)),
                              min(H - 2.0, max(1.0, u.y + dy * KITE_STEP)))
                    self.retreat_until[u.id] = t + 1.0
                    done.add(u.id)
                    self.__dict__.get("_pulse", {}).pop(u.id, None)
                self.__dict__["_kites"] = self.__dict__.get("_kites", 0) + 1
                if t - getattr(self, "_kite_say", -99) > 30:
                    self._kite_say = t
                    self.say("KITE %d archers step back from %d melee (%s), %d kites so far" % (
                        len(fighters), len(set(e.id for e, _u in close)), close[0][0].name, self._kites))
                return done
        RANGE = 7.0

        def score(e):
            in_range = sum(1 for u in fighters if e.dist(u.x, u.y) <= RANGE + 1)
            shooter = 0 if tactics.unit_class(e.name) in ("archer", "siege", "priest") else 1
            return (shooter, -in_range, e.hp, min(e.dist(u.x, u.y) for u in fighters))
        prev = self.__dict__.get("_focus")
        tgt = None
        if prev is not None:
            tgt = next((e for e in foes if e.id == prev[0]), None)
            if tgt is not None and t - prev[1] > 8 and score(tgt) > score(min(foes, key=score)):
                tgt = None                               # (re-chosen at most every 8 s, unless it died)
        if tgt is None:
            tgt = min(foes, key=score)
            self._focus = (tgt.id, t)
        shooter_tgt = tactics.unit_class(tgt.name) in ("archer", "siege")
        pulse = self.__dict__.setdefault("_pulse", {})
        for u in fighters:
            if shooter_tgt and not str(self.me) in os.environ.get("AOESOLO_PULSE_OFF", "").split(","):
                st = pulse.setdefault(u.id, {"ph": "attack"})
                st["tgt"], st["seen"] = tgt.id, t
                if st.get("ph") == "dodge":
                    done.add(u.id)
                    continue                             # (the fast loop has it)
            else:
                pulse.pop(u.id, None)
            act = self.r.action(u)
            if act and act[1] == tgt.ptr:
                done.add(u.id)
                continue
            if not self.recent(u.id, ("o", tgt.id), within=1.5):
                self.order([u], tgt)
            done.add(u.id)
        if t - getattr(self, "_focus_say", -99) > 30:
            self._focus_say = t
            self.say("ARCHERS %d focus %s #%d (%.0f hp) - %d foes near, %d stepping back, dodges so far %d" % (
                len(fighters), tgt.name, tgt.id, tgt.hp, len(foes), len(done) - len(fighters),
                self.__dict__.get("_dodge_n_total", 0)))
        return done

    def hit_and_run(self, u, enemy_army, enemy_vils, threats):
        t = self.now()
        if t < self.retreat_until.get(u.id, 0):
            return
        hurt = u.hp < self.hp_prev.get(u.id, u.hp) - 0.01
        attackers = [e for e in enemy_army + enemy_vils if e.dist(u.x, u.y) < 9]   # archers shoot from 5-7
        if hurt and attackers:
            hitters = []
            for e in attackers:
                act = self.r.action(e)
                if act and act[1] == u.ptr:
                    hitters.append(e)
            ranged = [e for e in hitters if tactics.unit_class(e.name) in ("archer", "chariot", "siege", "priest")]
            if ranged and tactics.unit_class(u.name) == "archer" and u.hp >= 0.35 * u.maxhp:
                # the user's "điều quân": an archer under arrow fire steps sideways so the volley misses,
                # then shoots again (the tick after the step re-issues the attack)
                e0 = min(ranged, key=lambda e: e.dist(u.x, u.y))
                dx, dy = unit(u.x - e0.x, u.y - e0.y)
                n = self.dodge_n.get(u.id, u.id) + 1
                self.dodge_n[u.id] = n
                side = 1 if (n % 2) else -1                 # left, right, left ... (no drift)
                self.move([u], u.x - dy * 2.5 * side, u.y + dx * 2.5 * side)
                self.retreat_until[u.id] = t + 1.2
                if t - getattr(self, "_dodge_say", 0) > 20:
                    self._dodge_say = t
                    self.say("archer #%d dodges arrows sideways (%s)" % (u.id, e0.name))
                return
            if ranged and u.hp >= 0.35 * u.maxhp:
                tgt = min(ranged, key=lambda e: e.dist(u.x, u.y))   # the user: charge the archers, never run
                if not self.recent(u.id, ("o", tgt.id), within=2):
                    self.order([u], tgt)
                return
            if hitters and u.hp < 0.35 * u.maxhp:
                ax = sum(e.x for e in hitters) / len(hitters)
                ay = sum(e.y for e in hitters) / len(hitters)
                dx, dy = unit(u.x - ax, u.y - ay)
                self.move([u], u.x + dx * 5, u.y + dy * 5)
                self.retreat_until[u.id] = t + 3.0
                return
        # 1st priority: villagers (seen now, or remembered), 2nd: their army, buildings only if blocking
        if threats and u.type != gs.SCOUT:
            tgt = min(threats, key=lambda e: e.dist(u.x, u.y))
            if not self.recent(u.id, ("o", tgt.id), within=3):
                self.order([u], tgt)
            return
        wall = self.enemy_wall_info(u)
        if wall and wall["sealed"]:
            # their town is walled in: the villagers we can reach (repairing the wall, building a house
            # next to it) first, then the wall house nearest to us (the user)
            reach = [e for e in enemy_vils if wall["reach"](e.x, e.y)]
            if reach:
                tgt = min(reach, key=lambda e: e.dist(u.x, u.y))
                if not self.recent(u.id, ("o", tgt.id), within=3):
                    self.order([u], tgt)
                return
            if wall["houses"] and not threats:
                b = min(wall["houses"], key=lambda o: o.dist(u.x, u.y))
                if not self.recent(u.id, ("o", b.id), within=4):
                    self.order([u], b)
                    if self.now() - getattr(self, "_wall_hit_say", 0) > 30:
                        self._wall_hit_say = self.now()
                        self.say("enemy town walled in, no way in: shooting wall house #%d at (%.0f,%.0f)" % (b.id, b.x, b.y))
                return
        if enemy_vils:
            tgt = min(enemy_vils, key=lambda e: e.dist(u.x, u.y))
            if self.blocked_chase(u, tgt):
                return
            if not self.recent(u.id, ("o", tgt.id), within=3):
                self.order([u], tgt)
            return
        if enemy_army and u.type != gs.SCOUT:
            tgt = min(enemy_army, key=lambda e: e.dist(u.x, u.y))
            if not self.recent(u.id, ("o", tgt.id), within=3):
                self.order([u], tgt)
            return
        if self.enemy_vils_seen:
            x, y, _ = min(self.enemy_vils_seen.values(), key=lambda p: math.hypot(p[0] - u.x, p[1] - u.y))
            if math.hypot(x - u.x, y - u.y) > 3:
                if not self.recent(u.id, within=5):
                    self.move([u], x, y)
                return
            for eid in [k for k, p in self.enemy_vils_seen.items() if math.hypot(p[0] - u.x, p[1] - u.y) < 4]:
                del self.enemy_vils_seen[eid]
        # nobody in sight: buildings in reach are hit (villagers come out to repair / defend them),
        # otherwise the shared search / raid goal
        near_b = [b for b in self.s.enemy_buildings_seen if b.dist(u.x, u.y) < 6 and b.type != gs.TOWN_CENTER
                  and u.type != gs.SCOUT]
        if near_b:
            b = min(near_b, key=lambda o: o.dist(u.x, u.y))
            if not self.recent(u.id, ("o", b.id), within=4):
                self.order([u], b)
            return
        goal = self.army_goal(u)
        if goal and math.hypot(goal[0] - u.x, goal[1] - u.y) > 3 and not self.recent(u.id, within=4):
            self.move([u], *goal)

    def note_enemy_sites(self, t):
        """Every enemy building and working villager seen is remembered by 8x8 area: buildings mean
        their home / working area is around (the user: search around what was found first), villagers
        at work mark a working area to raid again now and then."""
        sites = self.__dict__.setdefault("enemy_sites", {})
        for b in self.s.enemy_buildings_seen:
            k = (int(b.x) // 8, int(b.y) // 8)
            st = sites.setdefault(k, {"x": b.x, "y": b.y, "seen": t, "eco": 0.0, "visit": 0.0, "bld": 0})
            st["seen"] = max(st["seen"], t)
            st["bld"] = max(st["bld"], 1)
        for e in self.s.enemy:
            if e.cls == gs.CLS_VILLAGER and e.hp > 0:
                k = (int(e.x) // 8, int(e.y) // 8)
                st = sites.setdefault(k, {"x": e.x, "y": e.y, "seen": t, "eco": 0.0, "visit": 0.0, "bld": 0})
                st["seen"], st["eco"] = t, t
        # our soldiers mark where they have been (to search what is left, and to time the raids)
        vis = self.__dict__.setdefault("army_visit", {})
        for u in self.military():
            vis[(int(u.x) // 6, int(u.y) // 6)] = t
            for k, st in sites.items():
                if math.hypot(st["x"] - u.x, st["y"] - u.y) < 5:
                    st["visit"] = t

    def search_goal(self, u):
        """Where to look for the enemy when nobody is in sight (the user's order):
        1. a known working area / building area not raided for REVISIT s (working areas first);
        2. around the known buildings (their home and fields are there): ground not seen lately;
        3. anywhere unexplored on the map; 4. the area raided longest ago."""
        t = self.now()
        sites = list(self.__dict__.get("enemy_sites", {}).values())
        vis = self.__dict__.get("army_visit", {})
        W, H = self.r.W, self.r.H
        due = [st for st in sites if t - st["visit"] > REVISIT and (st["eco"] or st["bld"])]
        if due:
            st = min(due, key=lambda st: (0 if st["eco"] else 1, math.hypot(st["x"] - u.x, st["y"] - u.y)))
            return st["x"], st["y"]
        bld = sorted((st for st in sites if st["bld"]), key=lambda st: -st["seen"])[:6]
        cands = []
        for st in bld:
            for r in (7, 12, 17):
                for i in range(12):
                    a = i * math.pi / 6
                    x, y = st["x"] + math.cos(a) * r, st["y"] + math.sin(a) * r
                    if not (1 <= x < W - 1 and 1 <= y < H - 1):
                        continue
                    if t - vis.get((int(x) // 6, int(y) // 6), -1e9) < 120:
                        continue
                    cands.append((r * 0.5 + math.hypot(x - u.x, y - u.y), x, y))
        if cands:
            _, x, y = min(cands)
            return x, y
        if self.enemy_base is None:
            g = self.unexplored_goal(u)
            if g:
                return g
        tc = self.tc()
        if tc:
            guess = self.enemy_base or (max(2.0, min(W - 3.0, W - tc.x)), max(2.0, min(H - 3.0, H - tc.y)))
            goal = self.frontier_goal(u, tc, toward=guess, far=self.enemy_base is None)
            if goal:
                return goal
        if sites:
            st = min(sites, key=lambda st: st["visit"])
            return st["x"], st["y"]
        return None

    def lone_scouts(self, mil, enemy_army, tc):
        """The user: once the bows are done (2 áo) and the enemy's town is still not found, 2-3 bowmen go
        searching ALONE, each to its own unexplored spot, the far side of the map first. Ids handled."""
        L = self.__dict__.setdefault("_lone", {})          # unit id -> (gx, gy, since)
        done = getattr(self, "techs_done", set())
        off = getattr(self, "civ_off", set())
        bows = 57 in done or (56 in done and 57 in off)
        if self.enemy_base is not None or not tc or not getattr(self, "archer_plan", False)                 or getattr(self, "archer_kind", "") != "improved" or not bows or self.tactics and self.tactics.get("mode") == "defend":
            if L:
                L.clear()
            return set()
        t = self.now()
        archers = [u for u in mil if tactics.unit_class(u.name) == "archer" and u.type != gs.BOWMAN]
        for uid in [k for k in L if self.obj_by_id(k) is None]:
            del L[uid]
        want = 3 if len(archers) >= 6 else (2 if len(archers) >= 3 else 0)
        if len(L) < want:
            free = sorted((u for u in archers if u.id not in L), key=lambda u: -u.hp)
            for u in free[:want - len(L)]:
                L[u.id] = None
        vis = self.s.vis
        W, H = self.r.W, self.r.H
        out = set()
        for uid in list(L):
            u = self.obj_by_id(uid)
            if u is None:
                continue
            if any(e.dist(u.x, u.y) < 8 for e in enemy_army):
                continue                                   # (enemy soldiers: the fight code has it)
            g = L[uid]
            if g is None or math.hypot(g[0] - u.x, g[1] - u.y) < 4 or t - g[2] > 60 or vis[int(g[1]) * W + int(g[0])] != 255:
                others = [v for k, v in L.items() if k != uid and v is not None]
                best = None
                step = max(6, W // 12)
                for gy in range(6, H - 5, step):
                    for gx in range(6, W - 5, step):
                        if vis[gy * W + gx] != 255:
                            continue
                        if any(math.hypot(gx - o[0], gy - o[1]) < 20 for o in others):
                            continue
                        sc = 1.0 * math.hypot(gx - tc.x, gy - tc.y) - 0.4 * math.hypot(gx - u.x, gy - u.y)
                        if best is None or sc > best[0]:
                            best = (sc, gx, gy)
                if best is None:
                    continue
                L[uid] = g = (best[1] + 0.5, best[2] + 0.5, t)
                if t - getattr(self, "_lone_say", -99) > 30:
                    self._lone_say = t
                    self.say("LONE scouts: %d bowmen search alone for the enemy town (bow #%d -> (%.0f,%.0f))" % (
                        len(L), u.id, g[0], g[1]))
            if not self.recent(u.id, ("lone", int(g[0]), int(g[1])), within=6):
                self.move([u], g[0], g[1])
                self.mark([u], ("lone", int(g[0]), int(g[1])))
            out.add(uid)
        return out

    def unexplored_goal(self, u):
        """The nearest big unexplored part of the map (the user's 1v2: the army searched the corner
        opposite its TC for five minutes while the user sat in another one)."""
        vis = self.s.vis
        W, H = self.r.W, self.r.H
        best = None
        step = max(6, W // 12)
        for gy in range(6, H - 5, step):
            for gx in range(6, W - 5, step):
                n = un = 0
                for dy in (-4, 0, 4):
                    for dx in (-4, 0, 4):
                        x, y = gx + dx, gy + dy
                        if 0 <= x < W and 0 <= y < H:
                            n += 1
                            if vis[y * W + x] == 255:
                                un += 1
                if not n or un < 0.5 * n:
                    continue
                sc = 40.0 * un / n - 0.5 * math.hypot(gx - u.x, gy - u.y)
                if best is None or sc > best[0]:
                    best = (sc, gx, gy)
        return (best[1], best[2]) if best else None

    def army_goal(self, u):
        """Fighters move as one group to a shared goal (re-picked every 20 s or when reached);
        scouts search on their own."""
        if u.type == gs.SCOUT:
            g = self.scout_goals.get(u.id) if hasattr(self, "scout_goals") else None
            if not g or math.hypot(g[0] - u.x, g[1] - u.y) < 4 or self.now() - g[2] > 30:
                p = self.search_goal(u)
                if not p:
                    return None
                self.__dict__.setdefault("scout_goals", {})[u.id] = g = (p[0], p[1], self.now())
            return g[0], g[1]
        g = getattr(self, "group_goal", None)
        if not g or self.now() - g[2] > 20 or math.hypot(g[0] - u.x, g[1] - u.y) < 4:
            p = self.search_goal(u)
            if not p:
                return None
            self.group_goal = g = (p[0], p[1], self.now())
            self.say("army goes to (%.0f,%.0f)" % (p[0], p[1]))
        return g[0], g[1]

    def enemy_wall_info(self, u):
        """Is the nearest known enemy TC walled in from where unit u stands? One path search out of their
        TC (every 20 s): u's tile not reached = walled in. Then the wall pieces are their buildings with
        one side reached from u's side and the other from their TC; reach(x, y) = a tile u can walk to."""
        tc = self.tc()
        etc = None
        for o in getattr(self.s, "enemy_all", []):
            if o.type == gs.TOWN_CENTER and o.owner in self.enemies and tc:
                if etc is None or o.dist(tc.x, tc.y) < math.hypot(etc[0] - tc.x, etc[1] - tc.y):
                    etc = (o.x, o.y)
        if etc is None:
            return None
        cache = getattr(self, "_ewall", None)
        if cache is None or self.now() - cache["t"] > 20 or cache["etc"] != etc:
            pm = self.pm
            W = pm.W
            x0, y0 = int(etc[0] - 1.5), int(etc[1] - 1.5)
            inside = pm.bfs([(xx, yy) for (xx, yy) in pm.ring_tiles(x0, y0, x0 + 3, y0 + 3) if pm.passable(xx, yy)],
                            max_cost=10 * 60)
            cache = {"t": self.now(), "etc": etc, "inside": inside, "ours": None, "from": None}
            self._ewall = cache
        pm = self.pm
        W = pm.W
        inside = cache["inside"]
        ux, uy = int(u.x), int(u.y)
        if not (0 <= ux < W and 0 <= uy < pm.H):
            return None
        if math.hypot(u.x - etc[0], u.y - etc[1]) > 45:
            return None                                   # far from their town: not our question yet
        sealed = inside[uy * W + ux] < 0
        if not sealed:
            return {"sealed": False}
        if cache["ours"] is None or cache["from"] is None or math.hypot(cache["from"][0] - u.x, cache["from"][1] - u.y) > 12:
            cache["ours"] = pm.bfs([(ux, uy)], max_cost=10 * 70)
            cache["from"] = (u.x, u.y)
        ours = cache["ours"]

        def reach(x, y):
            xi, yi = int(x), int(y)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    xx, yy = xi + dx, yi + dy
                    if 0 <= xx < W and 0 <= yy < pm.H and ours[yy * W + xx] >= 0:
                        return True
            return False
        through, outer = [], []
        for b in self.s.enemy_buildings_seen:
            if math.hypot(b.x - etc[0], b.y - etc[1]) > 40:
                continue
            sz = SIZES.get(b.type, 2)
            bx0, by0 = int(math.floor(b.x - sz / 2.0 + 1e-3)), int(math.floor(b.y - sz / 2.0 + 1e-3))
            ring = pm.ring_tiles(bx0, by0, bx0 + sz, by0 + sz)
            side_us = any(0 <= xx < W and 0 <= yy < pm.H and ours[yy * W + xx] >= 0 for (xx, yy) in ring)
            if not side_us:
                continue
            side_them = any(0 <= xx < W and 0 <= yy < pm.H and inside[yy * W + xx] >= 0 for (xx, yy) in ring)
            (through if side_them else outer).append(b)  # through: one house between us and their TC
        if through:
            houses = through
        else:                                             # a double wall: its outer layer, nearest their TC
            houses = sorted(outer, key=lambda o: math.hypot(o.x - etc[0], o.y - etc[1]))[:4]
        return {"sealed": True, "houses": houses, "reach": reach}

    def blocked_chase(self, u, tgt):
        """If we cannot get closer to a villager because a building is in the way, hit that building."""
        t = self.now()
        c = self.chase.get(u.id)
        d = u.dist(tgt.x, tgt.y)
        if not c or c[0] != tgt.id:
            self.chase[u.id] = (tgt.id, t, d)
            return False
        if t - c[1] < 8:
            return False
        if d < c[2] - 1.0:
            self.chase[u.id] = (tgt.id, t, d)
            return False
        dx, dy = unit(tgt.x - u.x, tgt.y - u.y)
        blockers = [b for b in self.s.enemy_buildings_seen
                    if b.dist(u.x, u.y) < 6 and ((b.x - u.x) * dx + (b.y - u.y) * dy) > 0]
        if blockers:
            b = min(blockers, key=lambda o: o.dist(u.x, u.y))
            self.order([u], b)
            self.chase[u.id] = (tgt.id, t, d)
            self.say("building #%d blocks the way to villager #%d: attacking it" % (b.id, tgt.id))
            return True
        return False

    def self_defence(self):
        """D3KT addendum: enemy military that attacks us may be fought back (our army does it, see
        army()). A lone enemy scout (no other enemy soldier near it): every villager within 5 tiles
        of where it struck hits it; once it is more than 4 tiles from that spot the chase is dropped.
        Villagers never hit enemy villagers unless the enemy broke the rules."""
        s = self.s
        t = self.now()
        mine = {o.ptr: o for o in s.mine}
        enemy_mil = [e for e in s.enemy if e.kind == gs.KIND_COMBAT and e.cls != gs.CLS_VILLAGER
                     and e.hp > 0 and "Artifact" not in e.name]
        by_id = {e.id: e for e in enemy_mil}
        self.attackers = []
        tc0 = self.tc()
        raiders = [e for e in enemy_mil if not (e.type == gs.SCOUT and not any(o.id != e.id and o.dist(e.x, e.y) < 10
                                                                                 for o in enemy_mil))]
        if not self.bronze_clicked:
            # before the Bronze click only Bronze units clear the work areas (the early ones are fought
            # by the villagers next to whoever they hit)
            raiders = [e for e in raiders if bronze_unit(e)]
        self._raiders = raiders
        if raiders and tc0:
            for v in s.villagers:
                if t < self.retreat_until.get(v.id, 0) or v.id in self.defenders:
                    continue
                near = [e for e in raiders if e.dist(v.x, v.y) < FLEE_R]
                if not near:
                    continue
                ex = sum(e.x for e in near) / len(near)
                ey = sum(e.y for e in near) / len(near)
                gx, gy = self.flee_goal(v, ex, ey)            # (the TC, or the most open way away from them)
                self.move([v], gx, gy)
                self.retreat_until[v.id] = t + 8
                self.mark([v], ("flee",))
            if t - getattr(self, "_flee_zone_say", 0) > 15:
                n_fled = sum(1 for v in s.villagers if t < self.retreat_until.get(v.id, 0))
                if n_fled:
                    self._flee_zone_say = t
                    self.say("enemy soldiers near our workers: %d villagers run (zone flee, %d raiders)" % (n_fled, len(raiders)))
        for e in enemy_mil:
            act = self.r.action(e)
            if not act or act[1] not in mine:
                continue
            victim = mine[act[1]]
            self.attackers.append(e)
            lone_scout = e.type == gs.SCOUT and not any(o.id != e.id and o.dist(e.x, e.y) < 10 for o in enemy_mil)
            # before the Bronze click an early unit (scout, clubman, axeman, slinger, bowman) is fought by
            # the villagers next to the one it hits; a Bronze unit always makes them run (the user)
            early_fight = victim.cls == gs.CLS_VILLAGER and not bronze_unit(e) and \
                not any(o.id != e.id and o.dist(e.x, e.y) < 10 for o in enemy_mil)   # (a lone early unit, any age)
            if victim.cls == gs.CLS_VILLAGER and not lone_scout and not early_fight and self.tc():
                # the user: keep the villagers. One hit by a soldier runs for the TC (our army is sent to
                # whoever attacks our villagers, see army()); a lone scout is beaten by villagers instead
                tc = self.tc()
                if t >= self.retreat_until.get(victim.id, 0):
                    # the user: the villager hit runs AWAY from the TC, leading the soldier off the town;
                    # if that way goes through the soldier, it turns aside (away from the soldier)
                    # (15/10 evening: no longer led AWAY from the TC - that run went along forests and into corners,
                    #  where the player's foundations killed 8 of 9 villagers; now the TC or the most open way)
                    gx, gy = self.flee_goal(victim, e.x, e.y)
                    self.move([victim], gx, gy)
                    self.retreat_until[victim.id] = t + 6
                    self.mark([victim], ("flee",))
                    if t - getattr(self, "_flee_say", 0) > 10:
                        self._flee_say = t
                        self.say("villager #%d attacked by %s #%d: runs for the TC / open ground (%.0f,%.0f)"
                                 % (victim.id, e.name, e.id, gx, gy))
            lone = e.type == gs.SCOUT and not any(o.id != e.id and o.dist(e.x, e.y) < 10 for o in enemy_mil)
            if (lone or early_fight) and e.id not in self.scout_hunts:
                self.scout_hunts[e.id] = (e.x, e.y, t)
                self.say("enemy %s #%d attacks our %s: villagers within %d tiles fight back, the others keep working"
                         % (e.name, e.id, victim.name, SCOUT_CALL_R))
        # the user (15/10): a lone Stone / Tool-age unit (scout, clubman, bowman...) that comes within 3 tiles of a
        # villager is attacked at once, whatever our age; a Bronze unit always makes them run
        for e in enemy_mil:
            if e.id in self.scout_hunts or bronze_unit(e):
                continue
            if any(o.id != e.id and o.dist(e.x, e.y) < 10 for o in enemy_mil):
                continue                                 # not alone
            if any(v.dist(e.x, e.y) <= SCOUT_TRIGGER_R for v in s.villagers):
                self.scout_hunts[e.id] = (e.x, e.y, t)
                self.say("lone enemy %s #%d within %d tiles of a villager: villagers within %d tiles attack it"
                         % (e.name, e.id, SCOUT_TRIGGER_R, SCOUT_CALL_R))
        for sid, (ax, ay, t0) in list(self.scout_hunts.items()):
            e = by_id.get(sid)
            if e is None:
                self.drop_scout_hunt(sid, "gone")
                continue
            workers = [v for v in s.villagers if v.id not in self.defenders]
            d_work = min((v.dist(e.x, e.y) for v in workers), default=99.0)
            if d_work > SCOUT_CHASE_R + 1.0 and t - t0 > 3:
                self.drop_scout_hunt(sid, "is %.1f tiles from every worker" % d_work)
                continue
            ax, ay = e.x, e.y                            # (the unit moves: the call radius follows it)
            self.scout_hunts[sid] = (ax, ay, t0)
            if bronze_unit(e):
                self.drop_scout_hunt(sid, "is a Bronze unit: villagers run")
                continue
            owned = self.task_owned()
            near = sorted((v for v in s.villagers if v.id not in owned and
                           (v.id in self.defenders or v.dist(ax, ay) <= SCOUT_CALL_R)), key=lambda v: v.dist(ax, ay))
            for v in near[:EARLY_DEFENDERS]:              # (a cluster, never the whole town)
                self.defenders[v.id] = sid
                if not self.recent(v.id, ("o", e.id), within=2.5):
                    self.order([v], e)
        if not self.rules_broken:
            return
        # enemy VILLAGERS that came to fight (rules broken): the villagers next to them answer, a few only
        for e in [e for e in s.enemy if e.cls == gs.CLS_VILLAGER and e.hp > 0]:
            act = self.r.action(e)
            if not act or act[1] not in mine:
                continue
            near = [v for v in s.villagers if v.dist(e.x, e.y) < 5 and not self.recent(v.id, ("o", e.id), within=4)]
            if near:
                self.order(near[:3], e)

    def drop_scout_hunt(self, sid, why):
        del self.scout_hunts[sid]
        back = [vid for vid, s_ in self.defenders.items() if s_ == sid]
        for vid in back:
            del self.defenders[vid]
            v = self.obj_by_id(vid)
            role = self.role.get(vid)
            if v is not None:
                if isinstance(role, tuple):
                    self.order([v], None, x=v.x, y=v.y)      # builders: the pending build re-orders them
                else:
                    self.work(v, role, force=True)
        self.say("enemy scout #%d %s: %d villagers back to work" % (sid, why, len(back)))

    # ================================================================ artifact cart
    def artifacts(self):
        tc = self.tc()
        if not tc:
            return
        carts = [o for o in self.s.mine if "Artifact" in o.name and "Ruins" not in o.name]
        for c in carts:
            if self.r.busy(c) or self.recent(c.id, within=3):
                continue
            k = self.artifact_wp.get(c.id, 0)
            self.artifact_wp[c.id] = k + 1
            if self.now() < ARTIFACT_EDGE_AFTER:
                radius = 9 + (k // 8) * 3
                ang = k * (2 * math.pi / 8)
                self.move([c], tc.x + math.cos(ang) * radius, tc.y + math.sin(ang) * radius)
            else:
                W, H, m = self.r.W, self.r.H, 4
                edge = [(m, m), (W / 2, m), (W - m, m), (W - m, H / 2), (W - m, H - m), (W / 2, H - m),
                        (m, H - m), (m, H / 2)]
                start = min(range(len(edge)), key=lambda i: math.hypot(edge[i][0] - tc.x, edge[i][1] - tc.y))
                x, y = edge[(start + k) % len(edge)]
                self.move([c], x, y)


if os.environ.get("AOESOLO_STAGE"):
    # staged tests (tools/stage.py): a small town - the wood goes to the stage's buildings and soldiers (stage12:
    # 45 villagers, 15 houses, the first archer at minute 9 and the chase began a minute before the end)
    MAX_VILLAGERS = 14
    WOOD_HARD_CAP = 10


def run(game, me, enemies, log=print, stop=lambda: False, period=0.6, pop_limit=200):
    """Bot loop for one player until the match ends or `stop()` is true."""
    used = load_params()
    if used:
        log("params loaded: %s" % used)
    cls = Brain
    if os.environ.get("AOESOLO_BRAIN", "new").lower() == "new":
        from brain.brain import NewBrain as cls              # the restructured brain (KIEN_TRUC_AI.md); AOESOLO_BRAIN=old for the old one
    brain = cls(game, me, enemies, log, pop_limit)
    log("bot started for player %d, enemies %s (%s)" % (me, sorted(enemies), cls.__name__))
    errors = 0
    started = time.time()
    # the fast control (pushers, lurer) runs on its own thread with its own hook connection, so a slow
    # brain tick never freezes a villager next to an elephant
    import threading
    mg = None
    try:
        import inject
        mg = aoemem.Game(game.m, inject.Hook(game.h.pid))
    except Exception as e:  # noqa: BLE001
        log("fast control on the main loop (%r)" % (e,))

    def fast_loop():
        n_calls, n_err, last_say, last_err = 0, 0, time.time(), ""
        while not stop() and not getattr(brain, "done", False):
            try:
                brain.micro(mg)
                n_calls += 1
            except Exception as e:  # noqa: BLE001
                n_err += 1
                last_err = repr(e)[:120]
            if time.time() - last_say > 60:
                last_say = time.time()
                try:
                    w = brain.wfast
                    brain.say("MICRO heartbeat: %d calls, %d errors (%s), fast now=%.1f, tasks=%d %s (id %x)" % (
                        n_calls, n_err, last_err, w.now if w is not None else -1, len(brain.ntasks),
                        " ".join("%s/%s:%s" % (k[0], k[1], getattr(t, "state", "?")) for k, t in list(brain.ntasks.items())[:4]),
                        id(brain.ntasks)))
                except Exception:  # noqa: BLE001
                    pass
                n_calls = n_err = 0
            time.sleep(0.05)
    if mg is not None:
        threading.Thread(target=fast_loop, daemon=True).start()
    while not stop():
        t0 = time.time()
        try:
            if not game.in_game():
                log("match over for player %d" % me)
                return brain
            t1 = time.time()
            if not brain.tick():
                if t1 - started < 15:            # the world may still be loading its units
                    time.sleep(0.1)
                    continue
                log("player %d has no units left" % me)
                return brain
            brain.tick_times = getattr(brain, "tick_times", []) + [time.time() - t1]
            errors = 0
        except Exception as e:
            errors += 1
            import traceback
            log("tick error: %r %s" % (e, traceback.format_exc().splitlines()[-3:]))
            if errors > 30:
                raise
        while time.time() - t0 < period:
            if mg is None:
                try:
                    brain.micro()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.05)
    brain.done = True
    return brain
