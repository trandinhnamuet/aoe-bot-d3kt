"""Building placement: occupancy grid from known objects + terrain, ring search near an anchor."""
import math

import gamestate as gs

SIZES = {gs.HOUSE: 2, gs.GRANARY: 3, gs.STORAGE_PIT: 3, gs.MARKET: 3, gs.STABLE: 3, gs.FARM: 3,
         gs.BARRACKS: 3, gs.TOWN_CENTER: 3, gs.DOCK: 3}


class Grid:
    def __init__(self, snap, bad_spots, checker=None):
        self.checker = checker
        r = snap.r
        self.W, self.H = r.W, r.H
        self.r = r
        self.snap = snap
        occ = bytearray(self.W * self.H)
        objs = snap.mine + snap.gaia + snap.enemy + snap.enemy_buildings_seen
        for o in objs:
            if o.kind not in (gs.KIND_BUILDING, gs.KIND_TREE, gs.KIND_STATIC, gs.KIND_DOPPEL):
                continue
            if o.kind == gs.KIND_STATIC and o.cls == 14:      # passable ground decoration
                continue
            if o.cls == 16 and o.rx <= 0 and o.ry <= 0:     # a tree stump: a house may close the gap it leaves
                continue
            rx = max(o.rx, 0.5)
            ry = max(o.ry, 0.5)
            x0, x1 = int(math.floor(o.x - rx)), int(math.ceil(o.x + rx))
            y0, y1 = int(math.floor(o.y - ry)), int(math.ceil(o.y + ry))
            for yy in range(max(0, y0), min(self.H, y1)):
                for xx in range(max(0, x0), min(self.W, x1)):
                    occ[yy * self.W + xx] = 1
        self.occ = occ
        self.bad = bad_spots

    def free(self, x0, y0, size, margin=0):
        for yy in range(y0 - margin, y0 + size + margin):
            for xx in range(x0 - margin, x0 + size + margin):
                # (the outermost row / column is buildable: the user's wall houses stand on x = 0, and the
                #  wall cut often ends on the map edge - load2: every last slot there, never built)
                if not (0 <= xx < self.W and 0 <= yy < self.H):
                    return False
                if self.occ[yy * self.W + xx]:
                    return False
                t = self.r.terrain_at(xx, yy)
                if t in gs.WATER_TERRAINS or t in gs.FOREST_TERRAINS:
                    return False
                if not self.snap.explored(xx, yy):
                    return False
                # 6000 footprints asked of the game's own can_place (14/10): a 3x3 building (granary, pit, market,
                # barracks...) is refused when ANY of its 9 tiles is a slope (0 of 376), a 2x2 house is not
                # (341 of 353 accepted on slopes / uneven ground)
                if size >= 3 and x0 <= xx < x0 + size and y0 <= yy < y0 + size and self.r.shape_at(xx, yy):
                    return False
        return True

    def find(self, btype, ax, ay, rmin=2, rmax=10, prefer=None, margin=1):
        """Centre coordinates for building `btype` near (ax, ay). `prefer(cx, cy)` -> score, lower is better."""
        size = SIZES.get(btype, 3)
        best = None
        for radius in range(rmin, rmax + 1):
            cands = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    x0 = int(ax + dx - size / 2.0)
                    y0 = int(ay + dy - size / 2.0)
                    cx, cy = x0 + size / 2.0, y0 + size / 2.0
                    if (round(cx, 1), round(cy, 1), btype) in self.bad:
                        continue
                    if not self.free(x0, y0, size, margin):
                        continue
                    score = math.hypot(cx - ax, cy - ay) + (prefer(cx, cy) if prefer else 0)
                    cands.append((score, cx, cy))
            if cands:
                cands.sort()
                for c in cands[:12]:
                    if self.checker is None or self.checker(btype, c[1], c[2]):
                        best = c
                        break
                    self.bad.add((round(c[1], 1), round(c[2], 1), btype))
                if best:
                    break
        return (best[1], best[2]) if best else None

    def mark(self, cx, cy, btype):
        size = SIZES.get(btype, 3)
        x0, y0 = int(cx - size / 2.0), int(cy - size / 2.0)
        for yy in range(y0, y0 + size):
            for xx in range(x0, x0 + size):
                if 0 <= xx < self.W and 0 <= yy < self.H:
                    self.occ[yy * self.W + xx] = 1
