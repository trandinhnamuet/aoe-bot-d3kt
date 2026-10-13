"""Combat doctrine (KIEN_TRUC_AI.md 3.4): what to build and whether to attack, from the balance of
forces and the civilisations of both sides. Pure functions over the brain's state; the brain's
army() / stables() / buildings_program() act on the assessment.

Measured and remembered facts live in brain.knowledge; nothing here hard-codes a game number.

    A = assess(b)         # every tick (cheap)
    A["mode"]             # "defend" | "attack" | "build"
    A["pick"]             # unit class to train next: "cavalry" | "camel" | "scout"
    A["want_temple"]      # True: the enemy fields priests (or is a priest civ): 1 temple, 2 priests
"""
import math

import gamestate as gs
from brain import knowledge as K

# unit classes by name (robust to type ids we have not verified)
CLASSES = (
    ("priest", ("priest",)),
    ("siege", ("stone thrower", "catapult", "ballista", "helepolis")),
    ("elephant", ("war elephant", "elephant archer", "armored elephant")),
    ("camel", ("camel",)),
    ("archer", ("archer", "bowman", "slinger")),
    ("chariot", ("chariot",)),
    ("cavalry", ("cavalry", "cataphract", "heavy cavalry")),
    ("hoplite", ("hoplite", "phalanx", "centurion")),
    ("infantry", ("clubman", "axeman", "swordsman", "legion")),
    ("scout", ("scout",)),
)
VALUE = {"priest": 3.0, "siege": 3.0, "elephant": 4.0, "camel": 1.6, "archer": 1.2, "chariot": 1.8,
         "cavalry": 2.0, "hoplite": 2.0, "infantry": 0.8, "scout": 0.8, "other": 1.0}
# what we train against what we see (we have stables; archery / academy come later)
COUNTER = {"archer": "cavalry", "chariot": "cavalry", "priest": "cavalry", "siege": "cavalry",
           "infantry": "cavalry", "scout": "cavalry", "hoplite": "camel", "cavalry": "camel",
           "camel": "camel", "elephant": "camel", "other": "cavalry"}   # (camels beat cavalry: camels meet camels)
DEFEND_RADIUS = 22.0     # enemy soldiers this close to our TC are a threat we meet at home
CAMEL_CIVS = ("Palmyran", "Persian")   # the user: these field camels (their camel advantage)
GOLD_OUT_AFTER_S = 900.0 # no gold mine known after this long in the game = the map's gold is gone
ENEMY_MEMORY_S = 120.0   # an enemy soldier seen is counted for this long


def unit_class(name):
    n = (name or "").lower()
    for cls, keys in CLASSES:
        if any(k in n for k in keys):
            return cls
    return "other"


def civ_name(cid):
    return K.CIV_IDS.get(int(cid or 0), "?")


def assess(b):
    """b: the brain. Returns the assessment dict (also stored as b.tactics)."""
    t = b.now()
    tc = b.tc()
    ours = {}
    for u in b.military():
        c = unit_class(u.name)
        ours[c] = ours.get(c, 0) + 1
    our_v = sum(VALUE.get(c, 1.0) * n for c, n in ours.items())
    seen = getattr(b, "enemy_army_seen", {})
    enemy, threat_v = {}, 0.0
    for eid, (name, x, y, t0) in seen.items():
        if t - t0 > ENEMY_MEMORY_S:
            continue
        c = unit_class(name)
        enemy[c] = enemy.get(c, 0) + 1
        if tc and math.hypot(x - tc.x, y - tc.y) <= DEFEND_RADIUS and t - t0 < 30:
            threat_v += VALUE.get(c, 1.0)
    enemy_v_seen = sum(VALUE.get(c, 1.0) * n for c, n in enemy.items())
    # the enemy's whole roster (the achievements screen): army by class, villagers, their TC
    total, enemy_vils, enemy_tc = {}, 0, None
    for o in getattr(b.s, "enemy_all", []):
        if o.cls == 4:
            enemy_vils += 1
        elif o.kind == 70 and "Artifact" not in o.name:
            c = unit_class(o.name)
            total[c] = total.get(c, 0) + 1
        elif o.type == 109 and enemy_tc is None:
            enemy_tc = (o.x, o.y)
    if total:
        enemy = total
    enemy_v = max(enemy_v_seen, sum(VALUE.get(c, 1.0) * n for c, n in total.items()))
    civs = [civ_name(c) for c in getattr(b, "enemy_civs", {}).values()]
    priest_civ = any(c in K.PRIEST_CIVS for c in civs)
    # ---- mode
    fighters = sum(n for c, n in ours.items() if c != "scout")
    if threat_v > 0 and threat_v >= 0.5 * max(our_v, 1.0):
        mode = "defend"                  # they are at our base with a force we cannot ignore
    elif fighters >= 2 and our_v >= 1.2 * enemy_v + 2.0:
        mode = "assault"                 # stronger than everything they have: the whole army goes for their base
    elif fighters >= 2:
        mode = "raid"                    # the user: two fighters = attack; they only defend when attacked
    else:
        mode = "build"                   # (a single unit waits for the second)
    # ---- what to train: counter the enemy's main class; two classes alternate when it is mixed
    if enemy:
        main = max(enemy.items(), key=lambda kv: VALUE.get(kv[0], 1.0) * kv[1])[0]
        pick = COUNTER.get(main, "cavalry")
        second = sorted(enemy.items(), key=lambda kv: -VALUE.get(kv[0], 1.0) * kv[1])
        if len(second) > 1 and COUNTER.get(second[1][0]) != pick and (ours.get(pick, 0) > 2 * ours.get(COUNTER[second[1][0]], 0)):
            pick = COUNTER[second[1][0]]
    else:
        pick = "cavalry" if ours.get("cavalry", 0) <= ours.get("camel", 0) + 2 else "camel"
    our_civ = civ_name(getattr(b, "my_civ", 0))
    if our_civ in CAMEL_CIVS and pick == "cavalry":
        pick = "camel"                   # the user: Palmyran / Persian field camels
    # the map's gold is gone (no mine left that we know of, little in the bank): no more gold units -
    # the stables make chariots (food + wood, after the Wheel) or scouts (food), archers come in
    gold_out = b.age >= 3 and not b.known_gold() and b.res(gs.GOLD) < 200 \
        and t - (b.start_time or 0) > GOLD_OUT_AFTER_S
    if gold_out:
        pick = "chariot" if 28 in getattr(b, "techs_done", set()) else "scout"
    want_temple = (priest_civ and b.age >= 3) or enemy.get("priest", 0) >= 1
    # archers against infantry / hoplites (the user: "when to use archers"); siege against a walled-in
    # enemy that out-develops us (the user: "BK + stone throwers"); the Iron Age when Bronze does not end it
    # ranged doctrine ("cung A" / "cung R"): the no-gold army. Wanted when the gold cannot feed the
    # stables, when the enemy fields infantry / hoplites, or when our civ is an archer civ.
    idle_stables = sum(1 for st in b.complete(gs.STABLE) if not b.r.producing(st))
    gold_short = b.age >= 3 and b.res(gs.GOLD) < 80 and (idle_stables >= 1 or not b.complete(gs.STABLE)) \
        and not any(b.role_name(v.id) == "gold" for v in b.s.villagers)
    archer_civ = our_civ in ("Assyrian", "Egyptian", "Hittite")
    # the user: Greek / Macedonian build Academies after the first stable, hoplites all game
    want_academy = b.age >= 3 and our_civ in ("Greek", "Macedonian") and not gold_out
    want_archery = b.age >= 3 and (enemy.get("hoplite", 0) + enemy.get("infantry", 0) >= 4 or gold_short or archer_civ
                                   or gold_out or getattr(b, "archer_plan", False))
    done = getattr(b, "techs_done", set())
    ranged = "chariot_archer" if 28 in done else ("improved_bowman" if 56 in done else "bowman")
    n_enemy_bld = sum(1 for o in getattr(b.s, "enemy_all", []) if o.kind == 80)
    want_siege = b.age >= 3 and mode == "assault" and enemy_tc is not None and (n_enemy_bld >= 25 or enemy_vils >= 1.3 * len(b.s.villagers))
    want_iron = b.age >= 3 and t - (b.start_time or 0) > 1200 and enemy_vils > 0 and b.res(0) >= 1000 + 200 and b.res(3) >= 800 + 150
    A = dict(mode=mode, pick=pick, our_v=round(our_v, 1), enemy_v=round(enemy_v, 1), threat_v=round(threat_v, 1),
             ours=ours, enemy=enemy, enemy_vils=enemy_vils, enemy_tc=enemy_tc, enemy_civs=civs, want_temple=want_temple,
             want_archery=want_archery, want_siege=want_siege, want_iron=want_iron, ranged=ranged,
             gold_short=gold_short, want_academy=want_academy, gold_out=gold_out)
    prev = getattr(b, "tactics", None)
    if prev is None or prev["mode"] != mode or prev["pick"] != pick or prev.get("want_temple") != want_temple \
            or prev.get("want_archery") != want_archery or prev.get("want_siege") != want_siege or prev.get("want_iron") != want_iron:
        b.say("TACTICS %s: ours %.1f %s vs enemy %.1f %s + %d villagers (threat %.1f), civs %s, enemy TC %s -> train %s%s%s%s%s" % (
            mode, our_v, ours, enemy_v, enemy, enemy_vils, threat_v, civs,
            ("(%.0f,%.0f)" % enemy_tc) if enemy_tc else "unknown", pick, ", temple" if want_temple else "",
            (", archery (%s%s)" % (ranged, ", gold short" if gold_short else "")) if want_archery else "",
            (", siege" if want_siege else "") + (", academy (hoplites)" if want_academy else ""), ", IRON" if want_iron else ""))
    b.tactics = A
    return A
