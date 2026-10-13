"""The plan: the user's rules (LUAT_D3KT.md) as demand tables, one per stage of the game
(KIEN_TRUC_AI.md 3.1). `demands(b)` reads the brain's state and returns the Demand list the
allocator fills every tick. Nothing here orders a villager; it only says who may do what, how
many, and in what order of importance.

Stage 1 (đời 1):  2 build the first house, the 3rd searches; 6 on berries (never pulled off);
                  villagers 7 and 9 scout; 8 and on chop until the first pit (120 wood), then exactly
                  6 on wood and everybody else on food; lures / pushes only from the 9th villager on.
Stage 2 (đời 2):  no new villagers; berries 6, wood 5-7 (market + stable + farms), hunts, farms.
Stage 3 (đời 3):  gold 2 + 2 per stable, wood 4-8 by stock, hunts, farms take the rest.
"""
import math

import gamestate as gs
from brain.jobs import Demand

HUNT_FROM = 8            # birth index (0-based): the 9th villager and later may lure / push
BERRY_SIX = range(0, 6)
SCOUTS = (6, 8)
FIRST_WOOD = 7


def demands(b):
    """b: the brain (NewBrain). Returns [Demand] in priority order."""
    s = b.s
    vils = sorted(s.villagers, key=lambda v: v.id)
    n = len(vils)
    t = b.now()
    tc = b.tc()
    out = []
    # 0. villagers building something keep at it (start_build gives them a ("build", ...) role)
    builders = [v.id for v in vils if isinstance(b.role.get(v.id), tuple) and b.role[v.id][0] == "build"]
    out.append(Demand("build", 0, 99, 0, ok=lambda i, v: False, pin=builders))
    # defenders / helpers / villagers running from a soldier are driven elsewhere this tick
    busy = [v.id for v in vils if v.id in b.defenders or v.id in b.helpers or t < b.retreat_until.get(v.id, 0)]
    out.append(Demand("busy", 0, 99, 0, ok=lambda i, v: False, pin=busy))

    stage = 3 if (b.age >= 3 or b.bronze_clicked) else (2 if (b.age >= 2 or b.tool_clicked) else 1)
    cap = b.berry_capacity()
    if (stage == 2 or (cap == 0 and b.any_of(gs.GRANARY) and b.pit_finished())) and not getattr(b, "far_food", False):
        b.far_food = True                        # the near food is gone / the Tool age: far patches, far herds
        b.say("plan: far patches and far herds allowed (players hunt 30+ tiles out in the Tool age)")
    if getattr(b, "far_food", False):
        b.food_emergency = True                  # (the old brain's flag: berry range 60, far herds, more scouts)
        cap = b.berry_capacity()
    berries = bool(b.berry_clusters()) and (cap > 0 or not b.any_of(gs.GRANARY))

    # 1. the first six: berries, or the search for the first bush
    if berries:
        out.append(Demand("berry", min(6, n), 6, 1, indices=BERRY_SIX))
    elif not b.any_of(gs.GRANARY):
        out.append(Demand("search", 0, 6, 1, indices=BERRY_SIX))

    # 2. hunting sites run by the tasks (lure / herd push) - leads only from the 9th villager on
    for (key, x, y, state) in b.sites:
        cap = b.site_cap.get(key, 0)
        task = b.ntasks.get(key if key[0] == "lure" else ("herd", key[1]))
        pinned = [i for i in (task.owned() if task else []) if any(v.id == i for v in vils)]
        if state in ("provoke", "run") and key[0] == "lure":
            # the user: the 9th villager may lure at once - the lurer and one waiter outrank the scouts
            # (2) and the first choppers (2.5); lure7: a lure waited 132 s for anybody at prio 3
            # the allocator counts by demand NAME, so the demands of one site are cumulative: the lurer
            # (the 9th+ villager) first, then the total brought to 2 with a waiter that may be a chopper
            # (the 7th+; with both from the 9th+ the early lures had no waiter: lure15). Two separate
            # min-1 demands shared the count and the waiter was never taken (lure19: 4 x nobody fresh,
            # 2 lurers dead). Hurt villagers (< 20 hp, an elephant hit is 10) are never picked.
            out.append(Demand(("hunt", key), min(cap, 1), min(cap, 1), 1.9,
                              ok=lambda i, v: i >= HUNT_FROM and v.hp >= 20, score=lambda v, x=x, y=y: v.dist(x, y), pin=pinned))
            out.append(Demand(("hunt", key), min(cap, 2), min(cap, 2), 1.9,
                              ok=lambda i, v: i >= 6 and v.hp >= 20, score=lambda v, x=x, y=y: v.dist(x, y), pin=pinned))
            out.append(Demand(("hunt", key), 0, cap, 4,                 # more waiters when there is room
                              ok=lambda i, v: i >= 6, score=lambda v, x=x, y=y: v.dist(x, y), pin=pinned))
        elif state in ("provoke", "run", "push"):
            need = 2 if key[0] == "herd" else 1
            out.append(Demand(("hunt", key), max(need, min(cap, 2)) if stage == 1 else need, max(cap, need), 3,
                              ok=lambda i, v: i >= HUNT_FROM, score=lambda v, x=x, y=y: v.dist(x, y), pin=pinned))
        elif cap > 0:
            home = tc and (math.hypot(x - tc.x, y - tc.y) <= 12 or b.meat_drop_near(x, y))   # a pit counts as home
            carc = 0
            if state == "eat":
                if key[0] == "herd" and key[1] in b.herds:
                    carc = len(b.herd_carcasses(b.herds[key[1]]))
                elif key[0] == "meat":
                    carc = len(b.meat_groups.get(key, []))
                elif key[0] == "lure":
                    carc = 1
            # the user: gazelle meat decays fast - at least one villager per carcass, right after the
            # berry pickers, before wood; more when there is room
            # a gazelle carcass vanishes 300 s after the kill (measured): one eater at 0.43/s cannot finish
            # its 150 food in time - two per carcass at least, at the TC right away
            need = min(cap, max(2, 2 * carc)) if (state == "eat" and home) else 0
            prio = 1.5 if (state == "eat" and home) else (6 if home else 8)
            if key[0] == "lure" and state == "kill" and not home:
                need, prio = min(cap, 4), 5              # a far elephant: four go and kill it
            out.append(Demand(("hunt", key), need, cap, prio,
                              ok=lambda i, v: i >= 6, score=lambda v, x=x, y=y: v.dist(x, y), pin=pinned))

    if getattr(b, "food_desperate", False):
        out.append(Demand("scout", 2, 4, 1.8, ok=lambda i, v: i >= 6))     # nothing to eat anywhere near: find it
    # 3. scouts: villagers 7 and 9 until enough food is known (the user: they scout on until the food
    #    is found; players still hunt 30+ tiles out in the Tool age)
    # (the user: scouting does not stop before the food known covers what the Bronze age still needs)
    if stage <= 2 and not b.bronze_clicked and (b.known_food() < b.food_needed() or getattr(b, "far_food", False)):
        out.append(Demand("scout", 2, 2, 2, indices=SCOUTS))     # (min 2: the wood demand below must not take them)

    # 4. wood - ahead of the hunts (priority 2.5): 4 choppers first (houses, the pit's 120 wood), then
    #    exactly 6 at the first pit; before the pit everybody spare chops (after the hunts took theirs)
    if stage == 1:
        if not b.woodline_placed:
            # players: 5-7 choppers at minute 4-6, the pit at ~5:40; with 4 the houses eat the pit's
            # 120 wood and the pit never comes (night4: pit at 12:00, 1356 food, no Tool click)
            out.append(Demand("wood", min(4 if n < 14 else 6, max(0, n - 8)), 6, 2.5, ok=lambda i, v: i >= FIRST_WOOD))
            out.append(Demand("wood", 0, 99, 4, ok=lambda i, v: i >= FIRST_WOOD))      # everybody spare chops
        else:
            out.append(Demand("wood", min(6, max(0, n - 8)), 6, 2.5, ok=lambda i, v: i >= FIRST_WOOD))
    elif stage == 2:
        out.append(Demand("wood", min(b.wood_target(), 7), 7, 4, ok=lambda i, v: i >= 6))
    else:
        stables = max(1, len(b.complete(gs.STABLE)))
        gold_want = min(2 + 5 * stables, max(2, (n - 10) // 2))     # ~5 miners per stable (knowledge.py)
        if b.res(gs.GOLD) > 600:
            # gold piling up while food is the bottleneck (tech2: 17 miners, 1 965 gold banked, 13 farmers,
            # food at 30 - no tech, 4 cavalry): the miners go farming until the bank is spent
            gold_want = min(gold_want, 4)
        wood_want = b.wood_target()
        if b.res(gs.WOOD) > 600:
            wood_want = min(wood_want, 4)
        if b.known_gold():
            out.append(Demand("gold", gold_want, gold_want, 3, ok=lambda i, v: i >= 6))
        out.append(Demand("wood", wood_want, wood_want, 4, ok=lambda i, v: i >= 6))

    # 5. extra berry capacity (a second patch) and farms
    if berries and cap > 6:
        out.append(Demand("berry2", 0, cap - 6, 7, ok=lambda i, v: i >= 6))
    if stage >= 2 and b.complete(gs.MARKET):
        # one farmer per farm plus a few to finish / start the next ones - never a crowd on the same farms
        # (the user, 13/10: far too many villagers on the same farms; 28 "farmers" for 10 farms)
        n_farm = len(b.complete(gs.FARM))
        pend = len(b.pending_of(gs.FARM))
        if stage == 2:
            # the user: farms right after the market in the Tool age - 4 at once, 8 before the Bronze
            # click (his 1v2: the Persian bot had none until the Bronze age, 14 food at 1 300 s, no scout)
            want = 8 if b.res(gs.FOOD) < 400 else 4
            out.append(Demand("farm", min(want, n_farm + pend + 2), max(want, n_farm + pend + 2), 3.5))
        else:
            extra = 4 if b.res(gs.FOOD) < 150 else 2                 # (food is the Bronze bottleneck)
            out.append(Demand("farm", n_farm, n_farm + pend + extra, 9))

    # 6. whoever is left: food first (hunt sites with room were listed above); in stage 1 with no food
    #    work left, scouts go and find some (players never put more than ~7 on wood); else wood
    if stage == 1 and b.woodline_placed and t - (b.start_time or 0) < 480 and \
            (b.food_items() < b.FOOD_ITEMS_WANTED or b.food_emergency):
        out.append(Demand("scout", 0, 2, 10, ok=lambda i, v: i >= 6))        # two more look for food, before min 8
    if stage == 1 and b.woodline_placed:
        wood_cap = 5 if b.res(gs.WOOD) >= 300 else 8                         # (players hold < 300 wood in Stone)
        out.append(Demand("wood", 0, wood_cap, 18, ok=lambda i, v: i >= 6))  # wood is capped at 8 (players: 6-7)
        out.append(Demand("scout", 0, 4 if b.food_short else 2, 19, ok=lambda i, v: i >= 6))        # no food work: look for food (2 at most)
    out.append(Demand("wood", 0, 99, 20))
    return out
