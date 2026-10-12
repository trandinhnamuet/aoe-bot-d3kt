"""Passability grid and breadth-first path distances on the tile map.

Blocked: water terrain and the footprint of every known obstacle (trees, buildings and foundations
of every player, mines, berry bushes, cliffs, farms). Unexplored tiles count as open: for walling
we must assume the enemy can walk there.
"""
import array
import collections
import math

import gamestate as gs

WATER = {1, 22, 23}
UNREACHABLE = -1
NEIGHBOURS = ((1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10), (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14))


def footprint(o):
    """Tiles covered by object `o` (x0, y0, x1, y1), half-open."""
    rx = max(o.rx, 0.5)
    ry = max(o.ry, 0.5)
    return (int(math.floor(o.x - rx + 1e-3)), int(math.floor(o.y - ry + 1e-3)),
            int(math.ceil(o.x + rx - 1e-3)), int(math.ceil(o.y + ry - 1e-3)))


def is_obstacle(o):
    if o.kind == gs.KIND_BUILDING or o.kind == gs.KIND_TREE:
        return True
    if o.kind in (gs.KIND_STATIC, gs.KIND_DOPPEL):
        return o.cls != 14                       # 14 = ground decoration (grass clumps, small rocks)
    return False


class PassMap:
    def __init__(self, snap, extra_blocked=()):
        r = snap.r
        self.W, self.H = W, H = r.W, r.H
        blk = bytearray(W * H)
        terr = r.terrain
        if terr:
            for i, t in enumerate(terr):
                if t in WATER:
                    blk[i] = 1
        for o in snap.mine + snap.gaia + snap.enemy + snap.enemy_buildings_seen:
            if not is_obstacle(o):
                continue
            x0, y0, x1, y1 = footprint(o)
            for yy in range(max(0, y0), min(H, y1)):
                row = yy * W
                for xx in range(max(0, x0), min(W, x1)):
                    blk[row + xx] = 1
        for (x0, y0, x1, y1) in extra_blocked:
            self.block_rect(x0, y0, x1, y1, blk)
        self.blk = blk

    def block_rect(self, x0, y0, x1, y1, blk=None):
        blk = self.blk if blk is None else blk
        for yy in range(max(0, y0), min(self.H, y1)):
            for xx in range(max(0, x0), min(self.W, x1)):
                blk[yy * self.W + xx] = 1

    def copy(self):
        c = PassMap.__new__(PassMap)
        c.W, c.H, c.blk = self.W, self.H, bytearray(self.blk)
        return c

    def passable(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H and not self.blk[y * self.W + x]

    def bfs(self, sources, max_cost=None, blk=None):
        """Path cost (10 per straight step, 14 per diagonal, no corner cutting) from any source tile.
        Returns array('i') of size W*H, -1 = unreachable. Sources may be blocked tiles (e.g. a building)."""
        W, H = self.W, self.H
        blk = self.blk if blk is None else blk
        dist = array.array("i", [UNREACHABLE]) * (W * H)
        # Dijkstra with two step costs: a deque per bucket keeps it fast enough in Python
        buckets = collections.defaultdict(list)
        for (x, y) in sources:
            if 0 <= x < W and 0 <= y < H:
                dist[y * W + x] = 0
                buckets[0].append(y * W + x)
        cost = 0
        maxc = max_cost if max_cost is not None else 10 ** 9
        while buckets:
            if cost not in buckets:
                cost = min(buckets)
            cur = buckets.pop(cost)
            if cost > maxc:
                break
            for i in cur:
                if dist[i] != cost:
                    continue
                x, y = i % W, i // W
                for dx, dy, c in NEIGHBOURS:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < W and 0 <= ny < H):
                        continue
                    j = ny * W + nx
                    if blk[j]:
                        continue
                    if dx and dy and (blk[y * W + nx] or blk[ny * W + x]):
                        continue                 # no squeezing between two diagonal obstacles
                    nc = cost + c
                    if dist[j] == UNREACHABLE or nc < dist[j]:
                        dist[j] = nc
                        buckets[nc].append(j)
        return dist

    def ring_tiles(self, x0, y0, x1, y1, gap=0):
        """Passable tiles touching the rectangle [x0,x1)x[y0,y1) (grown by `gap`)."""
        out = []
        for yy in range(y0 - 1 - gap, y1 + 1 + gap):
            for xx in range(x0 - 1 - gap, x1 + 1 + gap):
                if x0 - gap <= xx < x1 + gap and y0 - gap <= yy < y1 + gap:
                    continue
                if self.passable(xx, yy):
                    out.append((xx, yy))
        return out


def rect_of(cx, cy, size):
    x0 = int(round(cx - size / 2.0))
    y0 = int(round(cy - size / 2.0))
    return x0, y0, x0 + size, y0 + size


def rect_distance(px, py, rect):
    """Euclidean distance from point to a tile rectangle (0 inside)."""
    x0, y0, x1, y1 = rect
    dx = max(x0 - px, 0, px - x1)
    dy = max(y0 - py, 0, py - y1)
    return math.hypot(dx, dy)
