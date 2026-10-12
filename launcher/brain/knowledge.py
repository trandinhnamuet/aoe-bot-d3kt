"""What the AI knows about the game: measured in the user's recorded games / the arena (verified), or
from the game's data as remembered (unverified: check against empires.dat before a tactic relies
on it). The tactics modules (brain/tactics) read this, nothing else hard-codes a number.

Each entry says where it comes from. Add to it with the tools in tools/*_study.py."""

# ---------------------------------------------------------------- measured (tools/speed_study.py, 2026-10-11, 4-6 recordings)
SPEED = {               # tiles / game second at x1
    "villager": 1.10, "elephant": 1.00, "gazelle_hop": 1.85, "scout": 1.87, "cavalry": 2.00,
}
ORDER_LAG = 1.0         # game seconds between an order and the unit obeying it (lockstep, x1 speed)

# ---------------------------------------------------------------- measured (tools/gazelle_study.py, 894 flees)
GAZELLE = dict(hp=8.0, flee_radius=(2.1, 0.5, 1.3, 2.9),     # mean, sd, p10, p90 - distance to a villager
               hop=(2.75, 0.5), hop_time=1.7, dir_error_deg=8,  # straight away from the villager
               players_push_from=(10, 23, 15))                # tiles from the TC: min, max, median

# ---------------------------------------------------------------- measured (tools/elephant_study.py, 29 kills; arena LUREDBG)
ELEPHANT = dict(hp=45.0, speed=1.00, hit_range=2.0, hit_damage=10.0, hit_interval=1.0, gives_up_beyond=4.4,
                spear_damage=4.0, spears_to_kill=11, first_hit_to_death_s=30,
                villager_hp_lost_per_kill=(9, 10),           # p50, p90: the whole group loses ONE hit
                killed_at_tc_distance=5.4)                   # tiles from the TC centre (p50)
VILLAGER = dict(hp=25.0, spear_range=3.0, spear_damage=4.0, los=4.0, needs_to_restart_s=(2, 3))
LION = dict(aggro_radius=7.0)                                # scouts keep this far (LUAT_D3KT.md)

# ---------------------------------------------------------------- measured (tools/learn_profile.py, 80 players in 20 games)
PLAYER_PROFILE = dict(tool_click_median_s=535, bronze_click_median_s=716, villagers_at_tool=25,
                      berries_all_game=6, wood_all_game=(6, 7), hunters_from_min7=(8, 10),
                      house2_s=72, pit1_s=334, pit1_tc_dist=22.6, granary2_s=480, market_s=682, stable_s=675)
USER_BEST = dict(tool_median_s=518, bronze_median_s=684, tool_to_bronze_s=173)   # ChimSeDiNet, 11 games

# ---------------------------------------------------------------- game data as remembered (UNVERIFIED - check empires.dat)
AGE_RESEARCH_S = {"tool": 120, "bronze": 140, "iron": 160}
# planning rates (UNVERIFIED, to measure from recordings): a farmer ~0.35 food/s, a gold miner ~0.4 gold/s,
# a stable trains cavalry (70 food, 80 gold) in ~40 s -> ~5 farmers + ~5 miners keep one stable busy
# MEASURED 2026-10-12 from 3 of the user's recordings (unit 'ramount' every 80 ms, scratchpad
# measure_rates.py): effective units per game second per villager over a whole trip (gather + walk to
# the drop as players place them), median of 1588-4306 trips. The instantaneous gathering rate is
# ~1.05/s for every job; the drop walk is what makes the difference.
RATES = {"berry": 0.45, "hunt": 0.43, "farm": 0.41, "gold": 0.45, "wood": 0.58, "stone": 0.38,
         "gather_instant": 1.05, "stable_cavalry_s": 40}
# a carcass object's 'amount' counts DOWN by 1.0/s from death whether or not it is eaten (every
# Dead_* object does the same ~1.0-1.15/s): Dead_Gazelle starts at 300, Dead_Elephant at 400 - so a
# gazelle carcass is gone 300 s after the kill, an elephant 400 s after. Eat at once, with many.
CARCASS_TIMER = {"gazelle": 300.0, "elephant": 400.0, "rate": 1.0}
PER_STABLE = {"farmers": 5, "miners": 5}
COST = {"villager": {"food": 50}, "scout": {"food": 100}, "cavalry": {"food": 70, "gold": 80},
        "camel": {"food": 70, "gold": 60}, "house": {"wood": 30}, "farm": {"wood": 75},
        "granary": {"wood": 120}, "storage_pit": {"wood": 120}, "market": {"wood": 150}, "stable": {"wood": 150},
        "barracks": {"wood": 125}, "temple": {"wood": 200}, "siege_workshop": {"wood": 200}, "archery": {"wood": 150},
        "stone_thrower": {"wood": 180, "gold": 80}, "priest": {"gold": 125}}

# research. TECHS: id -> (name, research building type, seconds, cost, required tech ids) read from
# empires.dat (AoE-MapCap mapcap/dat.py parse_research, 2026-10-12). Buildings: 84 market, 103 storage
# pit, 68 granary, 12 barracks, 101 stable, 87 archery range, 49 siege workshop, 104 temple, 82 government
# center, 0 academy, 45 dock, 109 town center.
TECHS = {
    2: ("Catapult Tower", 68, 150, {"food": 1800, "stone": 750}, [15, 103]),
    4: ("Fishing Ship", 45, 30, {"food": 50, "wood": 100}, [0, 102]),
    5: ("Medium War Ship", 45, 75, {"food": 150, "wood": 75}, [0, 102]),
    6: ("Merchant Ship", 45, 60, {"food": 200, "wood": 75}, [0, 102]),
    7: ("Trireme", 45, 100, {"food": 250, "wood": 100}, [5, 103]),
    8: ("Heavy Transport", 45, 75, {"food": 150, "wood": 125}, [0, 103]),
    9: ("Trireme with Catapult", 45, 100, {"food": 300, "wood": 100}, [7, 103]),
    11: ("Stone Wall", 68, 10, {"food": 50}, [10, 101]),
    12: ("Sentry Tower", 68, 30, {"food": 120, "stone": 50}, [102, 16]),
    13: ("Medium Wall", 68, 60, {"food": 180, "stone": 100}, [11, 102]),
    14: ("Fortifications", 68, 75, {"food": 300, "stone": 175}, [13, 103]),
    15: ("Guard Tower", 68, 75, {"food": 300, "stone": 100}, [12, 103]),
    16: ("Watch Tower", 68, 10, {"food": 50}, [10, 101]),
    18: ("Afterlife", 104, 75, {"gold": 275}, [17, 103]),
    19: ("Monotheism", 104, 75, {"gold": 350}, [17, 103]),
    20: ("Fanaticism", 104, 60, {"gold": 150}, [17, 103]),
    21: ("Mysticism", 104, 50, {"gold": 120}, [17, 102]),
    22: ("Astrology", 104, 50, {"gold": 150}, [17, 102]),
    23: ("Jihad", 104, 60, {"gold": 120}, [17, 103]),
    24: ("Polytheism", 104, 50, {"gold": 120}, [17, 102]),
    25: ("Juggernaught", 45, 180, {"food": 2000, "wood": 900}, [9, 35, 103]),
    27: ("Helepolis", 49, 150, {"food": 1500, "wood": 1000}, [58, 103]),
    28: ("Wheel", 84, 75, {"food": 175, "wood": 75}, [26, 102]),
    30: ("Coinage", 84, 60, {"food": 200, "gold": 100}, [103]),
    31: ("Plow", 84, 75, {"food": 250, "wood": 75}, [81, 102]),
    32: ("Artisanship", 84, 80, {"food": 170, "wood": 150}, [102]),
    34: ("Nobility", 82, 70, {"food": 175, "gold": 120}, [33, 102]),
    35: ("Engineering", 82, 70, {"food": 200, "wood": 100}, [33, 103]),
    36: ("Massive Catapult", 49, 150, {"food": 1800, "wood": 900}, [54, 103]),
    37: ("Alchemy", 82, 100, {"food": 250, "gold": 200}, [33, 103]),
    38: ("Advanced Horse Archer", 87, 150, {"food": 1750, "gold": 800}, [60, 49, 103]),
    40: ("Leather Armor - Soldiers", 103, 30, {"food": 75}, [39, 101]),
    41: ("Leather Armor - Archers", 103, 30, {"food": 100}, [39, 101]),
    42: ("Leather Armor Mounted", 103, 30, {"food": 125}, [39, 101]),
    43: ("Scale Armor - Soldiers", 103, 60, {"food": 100, "gold": 50}, [40, 102]),
    44: ("Scale Armor - Archers", 103, 60, {"food": 125, "gold": 50}, [41, 102]),
    45: ("Scale Armor - Cavalry", 103, 60, {"food": 150, "gold": 50}, [42, 102]),
    46: ("Tool Working", 103, 40, {"food": 100}, [101, 39]),
    47: ("Bronze Shield", 103, 50, {"food": 150, "gold": 180}, [102, 39]),
    48: ("Chain Mail - Soldiers", 103, 75, {"food": 125, "gold": 100}, [43, 103]),
    49: ("Chain Mail - Archers", 103, 75, {"food": 150, "gold": 100}, [44, 103]),
    50: ("Chain Mail - Cavalry", 103, 75, {"food": 175, "gold": 100}, [45, 103]),
    51: ("Metal Working", 103, 75, {"food": 200, "gold": 120}, [46, 102]),
    52: ("Metalurgy", 103, 100, {"food": 300, "gold": 180}, [51, 103]),
    54: ("Heavy Catapult", 49, 100, {"food": 300, "wood": 250}, [53, 103]),
    56: ("Improved bow", 87, 60, {"food": 140, "wood": 80}, [55, 102]),
    57: ("Composit bow", 87, 100, {"food": 180, "wood": 100}, [56, 102]),
    63: ("Axe", 12, 40, {"food": 100}, [62, 101]),
    64: ("Short Sword", 12, 50, {"food": 120, "gold": 50}, [63, 102]),
    65: ("Broad Sword", 12, 80, {"food": 140, "gold": 50}, [64, 102]),
    66: ("Long Sword", 12, 90, {"food": 160, "gold": 50}, [65, 103]),
    71: ("Heavy Cavalry", 101, 90, {"food": 350, "gold": 125}, [67, 103]),
    73: ("Phalanx", 0, 90, {"food": 300, "gold": 100}, [72, 103]),
    77: ("Legion", 12, 150, {"food": 1400, "gold": 600}, [66, 20, 103]),
    78: ("Cataphracts", 101, 150, {"food": 2000, "gold": 850}, [71, 52, 103]),
    79: ("Centurion", 0, 150, {"food": 1800, "gold": 700}, [73, 103]),
    80: ("Irrigation", 84, 100, {"food": 300, "wood": 100}, [31, 103]),
    81: ("Domestication", 84, 40, {"food": 200, "wood": 50}, [26, 101]),
    101: ("Tool Age", 109, 120, {"food": 500}, [74]),
    102: ("Bronze Age", 109, 140, {"food": 800}, [75, 101]),
    103: ("Iron Age", 109, 160, {"food": 1000, "gold": 800}, [76, 102]),
    106: ("Balistics", 82, 60, {"food": 200, "gold": 50}, [33, 103]),
    107: ("Wood Working", 84, 60, {"food": 120, "wood": 75}, [26, 101]),
    108: ("Gold Mining", 84, 50, {"food": 120, "wood": 100}, [26, 101]),
    109: ("Stone Mining", 84, 30, {"food": 100, "stone": 50}, [26, 101]),
    110: ("Craftmanship", 84, 100, {"food": 240, "wood": 200}, [32, 103]),
    111: ("Siege Craft", 84, 60, {"food": 190, "stone": 100}, [103]),
    112: ("Architecture", 82, 50, {"food": 150, "wood": 175}, [33, 102]),
    113: ("Aristocracy", 82, 60, {"food": 175, "gold": 150}, [33, 103]),
    114: ("Writing", 82, 60, {"food": 200, "gold": 75}, [33, 102]),
    117: ("Iron Shield", 103, 75, {"food": 200, "gold": 320}, [103, 47]),
    119: ("Medicine", 104, 50, {"gold": 150}, [17, 103]),
    120: ("Martyrdom", 104, 100, {"gold": 600}, [17, 103]),
    121: ("Logistics", 82, 60, {"food": 180, "gold": 100}, [33, 102]),
    122: ("Tower Shield", 103, 100, {"food": 250, "gold": 400}, [103, 47]),
    125: ("Armored Elephants", 101, 150, {"food": 1000, "gold": 1200}, [67, 70, 103]),
    126: ("Heavy Chariots", 101, 150, {"gold": 800, "wood": 1200}, [67, 68, 103, 34]),
}
TECH_AGES = {101, 102, 103}
TECH_WHEEL = 28
# the user's order: the Wheel first (villagers run from raids), then attack / armour for the units we
# use (cavalry, then archers), economy (wood, gold, farms), then everything else that becomes available
TECH_PRIORITY = [28, 56, 46, 42, 107, 108, 81, 45, 51, 41, 32, 31, 47, 57, 44, 40, 43, 71, 21, 22, 24, 52, 50, 49, 48,
                 112, 114, 121, 113, 34, 35, 37, 106, 80, 110, 117, 122, 18, 19, 20, 23, 119]
# never: stone mining / siege craft (stone), walls and towers (banned by D3KT), ships, the catapult tower
TECH_NEVER = {109, 111, 2, 11, 12, 13, 14, 15, 16, 4, 5, 6, 7, 8, 9, 25}
TECH_BUILDINGS = {tid: (loc,) for tid, (_n, loc, _t, _c, _r) in TECHS.items()}
TECH_TRY_ORDER = (84, 103, 68, 101, 12, 104, 87, 109)   # (fallback when a tech is not in TECHS)


def tech_name(tid):
    return TECHS[tid][0] if tid in TECHS else "tech %d" % tid

# counter table: what beats what (unverified numbers, the relations are the common knowledge of the game)
COUNTERS = {
    "priest": ["cavalry", "scout", "camel", "chariot"],          # fast units reach a priest before it converts
    "cavalry": ["camel"],
    "archer": ["cavalry", "scout"],
    "hoplite": ["archer", "chariot_archer", "stone_thrower"],
    "walls_and_towers": ["stone_thrower", "catapult"],
}

# civilisation bonuses as remembered (UNVERIFIED): what matters for picking a counter in a 2-team game
CIV = {
    "Egyptian": dict(priest_range=+3, chariot_hp="+33%", gold_mining="+20%"),
    "Greek": dict(hoplite_speed="+30%", war_ships_speed="+30%"),
    "Babylonian": dict(walls_towers_hp="x2", priest_rejuvenation="+30%", stone_mining="+30%"),
    "Assyrian": dict(archer_fire_rate="+40%", villager_speed="+30%"),
    "Minoan": dict(composite_bowman_range=+2, farms="+25%", ships_cost="-30%"),
    "Hittite": dict(archer_attack=+1, siege_hp="x2", war_ships_range=+4),
    "Phoenician": dict(elephants_cost="-25%", woodcutting="+30%", catapult_trireme_fire="+65%"),
    "Sumerian": dict(villager_hp=+15, farms_food=+250, catapult_fire_rate="+50%"),
    "Persian": dict(hunting="+30%", elephant_speed="+50%", trireme_fire_rate="+50%", farming="-30%"),
    "Shang": dict(villager_cost=35, walls_hp="x2"),
    "Yamato": dict(mounted_cost="-25%", villager_speed="+30%", ships_hp="+30%"),
    "Choson": dict(priest_cost="-30%", swordsman_hp=+80, towers_range=+2),
    "Roman": dict(buildings_cost="-15%", towers_cost="-50%", swordsman_attack_rate="+33%"),
    "Carthaginian": dict(elephant_academy_hp="+25%", fire_galley_attack="+25%", transports_speed="+30%"),
    "Palmyran": dict(villager_cost=75, villager_armor=+1, villager_work="+25%", tribute_free=True, camel_speed="+25%"),
    "Macedonian": dict(academy_pierce_armor=+2, siege_cost="-50%", conversion_resistance="x4", los=+2),
}
CIV_IDS = {1: "Egyptian", 2: "Greek", 3: "Babylonian", 4: "Assyrian", 5: "Minoan", 6: "Hittite", 7: "Phoenician",
           8: "Sumerian", 9: "Persian", 10: "Shang", 11: "Yamato", 12: "Choson", 13: "Roman", 14: "Carthaginian",
           15: "Palmyran", 16: "Macedonian"}       # player struct byte 0x109 (confirmed in recordings)
# civs whose priests the user wants countered with our own temples (the user's note, 11/10/2026)
PRIEST_CIVS = {"Choson", "Yamato", "Minoan", "Greek"}
