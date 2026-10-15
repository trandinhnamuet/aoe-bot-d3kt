"""Wall-in ("bo nhà") planning with houses and buildings, using the terrain as the main barrier.

A plan encloses a region (tiles within `radius` of some anchor tiles that are reachable from them).
Every passable region tile that touches a passable tile outside the region is an opening; covering
all openings with building footprints seals the region. One 1-tile gate is kept on the side away
from the enemy so our own army can get out.

Two flavours are produced by the brain:
  * wide ("bo rộng"): the whole town (TC, wood line, berries, farms) in one region;
  * small ("bo nhỏ"): one region per work site (wood line, farm/granary block).
"""
import math

GATE_HALF_WIDTH = 0          # 0 -> a single gate tile


class Plan:
    def __init__(self, mode, center, radius, openings, slots, gate, leaks, region_size):
        self.mode = mode
        self.center = center
        self.radius = radius
        self.openings = openings          # list of (x, y) still uncovered when planned
        self.slots = slots                # [(x0, y0, size)] in priority order
        self.gate = gate                  # (x, y) or None
        self.leaks = leaks                # openings no footprint could cover
        self.region_size = region_size

    @property
    def cost_houses(self):
        return len(self.slots)

    def __repr__(self):
        return "<Plan %s r=%d openings=%d slots=%d leaks=%d gate=%s>" % (
            self.mode, self.radius, len(self.openings), len(self.slots), len(self.leaks), self.gate)


def _region(pm, anchors, radius):
    """Flood fill from the anchor tiles, never leaving the radius disc(s)."""
    W, H = pm.W, pm.H
    r2 = radius * radius

    def inside(x, y):
        for ax, ay in anchors:
            if (x - ax) ** 2 + (y - ay) ** 2 <= r2:
                return True
        return False

    seen = set()
    stack = []
    for ax, ay in anchors:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                x, y = int(ax) + dx, int(ay) + dy
                if pm.passable(x, y) and (x, y) not in seen:
                    seen.add((x, y))
                    stack.append((x, y))
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or not (0 <= nx < W and 0 <= ny < H):
                continue
            if not pm.passable(nx, ny) or not inside(nx, ny):
                continue
            if dx and dy and (not pm.passable(nx, y) or not pm.passable(x, ny)):
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen, inside


def _openings(pm, region, inside):
    out = []
    for (x, y) in region:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in region:
                continue
            if pm.passable(nx, ny) and not inside(nx, ny):
                if dx and dy and (not pm.passable(nx, y) or not pm.passable(x, ny)):
                    continue
                out.append((x, y))
                break
    return out


def plan(pm, anchors, radius, gate_dir, mode="wide", keep_clear=(), min_dist_from=None,
         size=2, max_slots=60, blocked_rects=()):
    """Plan footprints of `size` covering the openings of the region around `anchors`.

    gate_dir: unit vector pointing to where the gate should be (away from the enemy).
    keep_clear: [(x, y, r)] discs where no footprint may be placed (e.g. the farm ring around the TC).
    """
    cx = sum(a[0] for a in anchors) / len(anchors)
    cy = sum(a[1] for a in anchors) / len(anchors)
    work = pm.copy()
    for (x0, y0, x1, y1) in blocked_rects:
        work.block_rect(x0, y0, x1, y1)
    region, inside = _region(work, anchors, radius)
    openings = _openings(work, region, inside)
    if not openings:
        return Plan(mode, (cx, cy), radius, [], [], None, [], len(region))

    def ang(t):
        return math.atan2(t[1] + 0.5 - cy, t[0] + 0.5 - cx)

    gate_ang = math.atan2(gate_dir[1], gate_dir[0]) if gate_dir else None
    gate = None
    if gate_ang is not None:
        gate = min(openings, key=lambda t: abs((ang(t) - gate_ang + math.pi) % (2 * math.pi) - math.pi))
    gate_set = set()
    if gate:
        for dy in range(-GATE_HALF_WIDTH, GATE_HALF_WIDTH + 1):
            for dx in range(-GATE_HALF_WIDTH, GATE_HALF_WIDTH + 1):
                gate_set.add((gate[0] + dx, gate[1] + dy))
    # cover the front first: openings facing away from the gate get the first houses
    front = (gate_ang + math.pi) if gate_ang is not None else 0.0
    openings.sort(key=lambda t: abs((ang(t) - front + math.pi) % (2 * math.pi) - math.pi))
    open_set = set(openings)
    covered = set()
    slots = []
    leaks = []

    def allowed(x0, y0):
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                if not work.passable(xx, yy) or (xx, yy) in gate_set:
                    return False
                for kx, ky, kr in keep_clear:
                    if (xx + 0.5 - kx) ** 2 + (yy + 0.5 - ky) ** 2 < kr * kr:
                        return False
        # keep the gate walkable: never touch the gate tile's 4-neighbours
        if gate:
            gx, gy = gate
            for yy in range(y0, y0 + size):
                for xx in range(x0, x0 + size):
                    if abs(xx - gx) + abs(yy - gy) == 1 and (xx, yy) in region:
                        return False
        return True

    for t in openings:
        if t in covered or t in gate_set:
            continue
        best = None
        for ox in range(-(size - 1), 1):
            for oy in range(-(size - 1), 1):
                x0, y0 = t[0] + ox, t[1] + oy
                if not allowed(x0, y0):
                    continue
                gain = 0
                outward = 0.0
                for yy in range(y0, y0 + size):
                    for xx in range(x0, x0 + size):
                        if (xx, yy) in open_set and (xx, yy) not in covered:
                            gain += 1
                        if (xx, yy) not in region:
                            outward += 1
                score = gain * 10 + outward
                if best is None or score > best[0]:
                    best = (score, x0, y0)
        if best is None:
            leaks.append(t)
            continue
        _, x0, y0 = best
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                covered.add((xx, yy))
        work.block_rect(x0, y0, x0 + size, y0 + size)
        slots.append((x0, y0, size))
        if len(slots) >= max_slots:
            break
    # second pass - the leaks (the user: a house set a bit further in or out still blocks the way)
    still = []

    def allowed_relaxed(x0, y0):                     # (a plug may stand in the farm ring)
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                if not work.passable(xx, yy) or (xx, yy) in gate_set:
                    return False
        return True

    for t in leaks:
        fix = _plug_leak(work, t, region, inside, (cx, cy), radius, size, allowed) or             _plug_leak(work, t, region, inside, (cx, cy), radius, size, allowed_relaxed)
        if fix is None:
            still.append(t)
            continue
        x0, y0 = fix
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                covered.add((xx, yy))
        covered.add(t)
        work.block_rect(x0, y0, x0 + size, y0 + size)
        slots.append((x0, y0, size))
    leaks = still
    remaining = [t for t in openings if t not in covered and t not in gate_set]
    return Plan(mode, (cx, cy), radius, remaining, slots, gate, leaks, len(region))


def _local_leak(work, t, inside, center, radius, extra=None):
    """Can one walk from the leak tile t both deep inside (< radius - 2.5 from the centre) and
    outside the disc, within 8 tiles of t? (`extra` = a footprint rect treated as blocked)"""
    W, H = work.W, work.H

    def blocked(x, y):
        if not (0 <= x < W and 0 <= y < H) or not work.passable(x, y):
            return True
        if extra and extra[0] <= x < extra[2] and extra[1] <= y < extra[3]:
            return True
        return False

    if blocked(*t):
        return False
    seen = {t}
    stack = [t]
    deep = out = False
    r_in2 = (radius - 2.5) ** 2
    while stack:
        x, y = stack.pop()
        if (x + 0.5 - center[0]) ** 2 + (y + 0.5 - center[1]) ** 2 <= r_in2:
            deep = True
        if not inside(x, y):
            out = True
        if deep and out:
            return True
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or abs(nx - t[0]) > 8 or abs(ny - t[1]) > 8 or blocked(nx, ny):
                continue
            if dx and dy and (blocked(nx, y) or blocked(x, ny)):
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return False


def _plug_leak(work, t, region, inside, center, radius, size, allowed):
    """The nearest allowed footprint around the leak tile t that cuts the way through it."""
    if not _local_leak(work, t, inside, center, radius):
        return None                                  # already cut by the houses placed so far
    best = None
    for oy in range(-size - 2, 3):
        for ox in range(-size - 2, 3):
            x0, y0 = t[0] + ox, t[1] + oy
            if not allowed(x0, y0):
                continue
            if _local_leak(work, t, inside, center, radius, extra=(x0, y0, x0 + size, y0 + size)):
                continue
            d = abs(x0 + size / 2.0 - t[0] - 0.5) + abs(y0 + size / 2.0 - t[1] - 0.5)
            if best is None or d < best[0]:
                best = (d, x0, y0)
    return (best[1], best[2]) if best else None


def best_building_slot(pm, plan_obj, size, existing_rects=(), keep_clear=()):
    """A size x size footprint (market, stable, barracks...) that covers as many still-open
    openings of `plan_obj` as possible. Returns (x0, y0) or None."""
    if not plan_obj or not plan_obj.openings:
        return None
    work = pm.copy()
    for (x0, y0, x1, y1) in existing_rects:
        work.block_rect(x0, y0, x1, y1)
    open_set = set(plan_obj.openings)
    best = None
    tried = set()
    for t in plan_obj.openings:
        for ox in range(-(size - 1), 1):
            for oy in range(-(size - 1), 1):
                x0, y0 = t[0] + ox, t[1] + oy
                if (x0, y0) in tried:
                    continue
                tried.add((x0, y0))
                ok = True
                gain = 0
                for yy in range(y0, y0 + size):
                    for xx in range(x0, x0 + size):
                        if not work.passable(xx, yy):
                            ok = False
                            break
                        if plan_obj.gate and abs(xx - plan_obj.gate[0]) + abs(yy - plan_obj.gate[1]) <= 1:
                            ok = False
                            break
                        for kx, ky, kr in keep_clear:
                            if (xx + 0.5 - kx) ** 2 + (yy + 0.5 - ky) ** 2 < kr * kr:
                                ok = False
                                break
                        if (xx, yy) in open_set:
                            gain += 1
                    if not ok:
                        break
                if ok and gain >= 2 and (best is None or gain > best[0]):
                    best = (gain, x0, y0)
    return (best[1], best[2]) if best else None


# ====================================================================== terrain-following enclosure
INF = 10 ** 9
STEP4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _dinic(n, adj, src, dst):
    """Max flow on adjacency lists adj[u] = [[v, cap, rev_index], ...]. Returns the flow value."""
    from collections import deque
    flow = 0
    while True:
        level = [-1] * n
        level[src] = 0
        dq = deque([src])
        while dq:
            u = dq.popleft()
            for v, cap, _ in adj[u]:
                if cap > 0 and level[v] < 0:
                    level[v] = level[u] + 1
                    dq.append(v)
        if level[dst] < 0:
            return flow
        it = [0] * n

        def dfs(u, f):
            if u == dst:
                return f
            edges = adj[u]
            while it[u] < len(edges):
                e = edges[it[u]]
                v, cap, rev = e
                if cap > 0 and level[v] == level[u] + 1:
                    d = dfs(v, min(f, cap))
                    if d > 0:
                        e[1] -= d
                        adj[v][rev][1] += d
                        return d
                it[u] += 1
            return 0

        while True:
            f = dfs(src, INF)
            if f <= 0:
                break
            flow += f


def _add_edge(adj, u, v, cap):
    adj[u].append([v, cap, len(adj[v])])
    adj[v].append([u, 0, len(adj[u]) - 1])


SOFT_CAP = 80                                         # a farm tile on the cut (a house tile is 100 + distance)


def min_cut_tiles(work, tc, anchors, rmax, uncuttable, explored=None, dear=None, soft=None, sink=None):
    """The cheapest set of tiles whose blocking separates the TC (and anchors) from every passable
    tile rmax or more from the TC, given the terrain / buildings in `work`. Tiles in `uncuttable`
    (a function (x, y) -> bool) and unexplored tiles can be walked through but never built on.
    Returns (cut tiles as a list, flow) - flow >= INF means no cut exists (unexplored all round).
    `soft` = blocked tiles that are a weak barrier (our farms: troops cannot cross a farm, but it falls fast -
    the user, 14/10): in the graph at SOFT_CAP + distance, a little under a new house, far over the free
    terrain; a soft tile on the cut needs no house."""
    import sys
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    cx, cy = tc
    R = int(rmax) + 2
    tiles = []
    index = {}
    for yy in range(int(cy) - R, int(cy) + R + 1):
        for xx in range(int(cx) - R, int(cx) + R + 1):
            if not work.passable(xx, yy) and not (soft and (xx, yy) in soft):
                continue
            if (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 > (rmax + 1.5) ** 2:
                continue
            index[(xx, yy)] = len(tiles)
            tiles.append((xx, yy))
    n = 2 * len(tiles) + 2
    S, T = n - 2, n - 1
    adj = [[] for _ in range(n)]
    src_tiles = set()
    for (ax, ay) in [tc] + list(anchors):
        for yy in range(int(ay) - 2, int(ay) + 3):
            for xx in range(int(ax) - 2, int(ax) + 3):
                if (xx, yy) in index:
                    src_tiles.add((xx, yy))
    for k, (xx, yy) in enumerate(tiles):
        d = math.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
        # (unexplored tiles can be cut - a footprint there waits until they are explored; treating
        #  them as uncuttable made the cut infinite whenever one unexplored lane led out: wall1)
        if soft and (xx, yy) in soft:
            _add_edge(adj, 2 * k, 2 * k + 1, SOFT_CAP + int(d))
            for dx, dy in STEP4:
                j = index.get((xx + dx, yy + dy))
                if j is not None:
                    _add_edge(adj, 2 * k + 1, 2 * j, INF)
            if (xx, yy) in src_tiles:
                _add_edge(adj, S, 2 * k, INF)
            if (sink(xx, yy) if sink is not None else d >= rmax):
                _add_edge(adj, 2 * k + 1, T, INF)
            continue
        cuttable = not uncuttable(xx, yy)
        cap = 100 + int(d) + (50 if explored is not None and not explored(xx, yy) else 0)
        if dear is not None and dear(xx, yy):
            cap += 300                                   # the farm ring: cut only when nothing else goes
        _add_edge(adj, 2 * k, 2 * k + 1, cap if cuttable else INF)
        for dx, dy in STEP4:
            j = index.get((xx + dx, yy + dy))
            if j is not None:
                _add_edge(adj, 2 * k + 1, 2 * j, INF)
        if (xx, yy) in src_tiles:
            _add_edge(adj, S, 2 * k, INF)
        if (sink(xx, yy) if sink is not None else d >= rmax):
            _add_edge(adj, 2 * k + 1, T, INF)
    flow = _dinic(n, adj, S, T)
    if flow >= INF:
        return [], flow
    # the cut: tiles whose in-node is reachable from S in the residual graph and out-node is not
    seen = [False] * n
    stack = [S]
    seen[S] = True
    while stack:
        u = stack.pop()
        for v, cap, _ in adj[u]:
            if cap > 0 and not seen[v]:
                seen[v] = True
                stack.append(v)
    cut = [tiles[k] for k in range(len(tiles)) if seen[2 * k] and not seen[2 * k + 1]]
    return cut, flow


def _inside_set(work, tc, rmax):
    """Tiles reachable from the TC without reaching rmax (the town, once the cut is blocked)."""
    cx, cy = tc
    seen = set()
    stack = []
    for yy in range(int(cy) - 2, int(cy) + 3):
        for xx in range(int(cx) - 2, int(cx) + 3):
            if work.passable(xx, yy):
                seen.add((xx, yy))
                stack.append((xx, yy))
    lim2 = (rmax + 1.5) ** 2
    while stack:
        x, y = stack.pop()
        for dx, dy in STEP4:
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or not work.passable(nx, ny):
                continue
            if (nx + 0.5 - cx) ** 2 + (ny + 0.5 - cy) ** 2 > lim2:
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen


def plan_cut(pm, tc, anchors, rmax, keep_clear=(), uncuttable_rects=(), explored=None, size=2, max_slots=60,
             rounds=6, soft=(), sink=None):
    """The terrain-following enclosure: minimum-cut tiles between the town and the field, covered by
    size x size footprints; re-cut with the footprints in place until the town is sealed.
    Returns a Plan (mode 'wide'): openings = cut tiles still uncovered, slots = footprints to build,
    leaks = cut tiles no footprint can cover; plan.inside = the enclosed tiles, plan.cut = the cut."""
    work = pm.copy()
    soft = set(soft or ())

    def uncuttable(x, y):
        for (x0, y0, x1, y1) in uncuttable_rects:
            if x0 <= x < x1 and y0 <= y < y1:
                return True
        return False

    def in_keep_clear(x, y):
        # (a keep-clear disc - the farm ring round the TC / a granary - is dear, not forbidden: with it
        #  forbidden a granary 8 tiles out reached past rmax and no cut existed at all - flow INF, and
        #  the brain then thought the town "sealed" with 0 houses)
        for kx, ky, kr in keep_clear:
            if (x + 0.5 - kx) ** 2 + (y + 0.5 - ky) ** 2 < kr * kr:
                return True
        return False

    def allowed(x0, y0):
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                if not work.passable(xx, yy) or uncuttable(xx, yy):
                    return False
                if explored is not None and not explored(xx, yy):
                    return False
        return True

    def fits(x0, y0):
        """The footprint fits the ground (explored or not: a footprint on unexplored ground waits)."""
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                if not work.passable(xx, yy) or uncuttable(xx, yy):
                    return False
        return True

    def coverable(x, y):
        """Some size x size footprint containing (x, y) fits: a 1-tile gap between two forests is
        the cheapest cut but no house fits there - such tiles are never cut. (Unexplored ground
        counts as coverable: treating it as uncoverable made every cut infinite while a lane of
        fog led out - wall3: a 'chosen' ring with 0 slots that never sealed.)"""
        for ox in range(-(size - 1), 1):
            for oy in range(-(size - 1), 1):
                if fits(x + ox, y + oy):
                    return True
        return False

    def uncuttable_full(x, y):
        return uncuttable(x, y) or not coverable(x, y)

    slots, leaks, all_cut, all_soft = [], [], [], []
    flow = 0
    for _round in range(rounds):
        cut, flow = min_cut_tiles(work, tc, anchors, rmax, uncuttable_full, explored, dear=in_keep_clear, soft=soft, sink=sink)
        if flow >= INF:
            break
        p_soft = [t for t in cut if t in soft]
        cut = [t for t in cut if t not in soft]         # (a farm on the cut is the wall there: no house)
        all_soft.extend(p_soft)
        if not cut:
            leaks = []                                    # sealed: nothing is left to cover
            break
        all_cut.extend(cut)
        open_set = set(cut)
        covered = set()
        leaks = []                                        # a tile left over this round is re-cut around next round
        for t in cut:
            if t in covered:
                continue
            best = None
            for ox in range(-(size - 1), 1):
                for oy in range(-(size - 1), 1):
                    x0, y0 = t[0] + ox, t[1] + oy
                    if not allowed(x0, y0):
                        continue
                    gain = sum(1 for yy in range(y0, y0 + size) for xx in range(x0, x0 + size)
                               if (xx, yy) in open_set and (xx, yy) not in covered)
                    # prefer footprints whose other tiles are already barrier (fewer new gaps)
                    snug = sum(1 for yy in range(y0 - 1, y0 + size + 1) for xx in range(x0 - 1, x0 + size + 1)
                               if not work.passable(xx, yy))
                    dear_n = sum(1 for yy in range(y0, y0 + size) for xx in range(x0, x0 + size) if in_keep_clear(xx, yy))
                    score = gain * 10 + snug - 3 * dear_n
                    if best is None or score > best[0]:
                        best = (score, x0, y0)
            if best is None:
                leaks.append(t)
                continue
            _, x0, y0 = best
            for yy in range(y0, y0 + size):
                for xx in range(x0, x0 + size):
                    covered.add((xx, yy))
            work.block_rect(x0, y0, x0 + size, y0 + size)
            slots.append((x0, y0, size))
            if len(slots) >= max_slots:
                break
        if len(slots) >= max_slots:
            break
    inside = _inside_set(work, tc, rmax)
    # openings = the cut tiles not covered by a footprint (the leaks) - for the status / 3x3 slots
    remaining = [t for t in all_cut if work.passable(*t)]
    p = Plan("wide", tc, rmax, remaining, slots, None, leaks, len(inside))
    p.inside = inside
    p.cut = all_cut
    p.flow = flow
    p.soft_cut = all_soft                               # (the farm tiles the wall leans on)
    return p
