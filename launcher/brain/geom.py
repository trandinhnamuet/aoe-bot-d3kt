"""Small geometry helpers shared by the tasks and the simulator."""
import math


def unit(dx, dy):
    L = math.hypot(dx, dy)
    return (dx / L, dy / L) if L > 1e-9 else (0.0, 0.0)


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def rot(dx, dy, rad):
    c, s = math.cos(rad), math.sin(rad)
    return dx * c - dy * s, dx * s + dy * c


def ang_diff(a, b):
    """Signed difference a - b wrapped to [-pi, pi]."""
    return (a - b + math.pi) % (2 * math.pi) - math.pi


def tc_edge_dist(x, y, tcx, tcy, half=1.5):
    """Distance from a point to the edge of the TC's 3x3 footprint (0 inside)."""
    return max(0.0, max(abs(x - tcx), abs(y - tcy)) - half)


def open_dir(passable, x, y, dx, dy, ax=None, ay=None, far=4.0, step=0.5, max_len=6.0):
    """(ux, uy, length): (dx, dy) turned as little as needed so the way ahead is walkable for at least
    `far` tiles, never towards (ax, ay) = the direction AWAY from a threat when given, and how far to
    go along it (up to max_len, stopping short of obstacles: a move order into a forest or a building
    leaves the unit standing, and whatever chases it catches it)."""
    best = (dx, dy, 0.0)
    n = int(max_len / step)
    for deg in (0, 20, -20, 40, -40, 60, -60, 80, -80, 100, -100, 120, -120):
        ux, uy = rot(dx, dy, math.radians(deg))
        if ax is not None and ux * ax + uy * ay < -0.1:
            continue
        free = 0.0
        for i in range(1, n + 1):
            k = step * i
            if not passable(int(x + ux * k), int(y + uy * k)):
                break
            free = k
        if free >= far:
            return ux, uy, free
        if free > best[2]:
            best = (ux, uy, free)
    return best[0], best[1], max(1.0, best[2])
