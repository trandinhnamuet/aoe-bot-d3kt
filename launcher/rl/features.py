"""Observation and action geometry of the herd-push policy, shared by the sim environment
(rl.herd_env) and the in-game task (brain.tasks.herd_rl): everything is expressed in the PUSH FRAME
(origin = the herd centre, x = the push direction towards the TC, y = its normal), mirrored per
pusher so that the pusher's own lateral offset is never negative (left/right symmetry)."""
import math

from brain import geom

# ---- actions: a move target relative to the REAR gazelle (the one furthest from the TC) in the
# pusher's mirrored frame, plus one nudge spear at it, plus stop
ALONG = (-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0)
LATERAL = (-4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0)     # +-4: room to walk round the herd (keep-out 3.2)
MOVES = [(a, l) for a in ALONG for l in LATERAL]
A_SPEAR = len(MOVES)          # 49
A_STOP = len(MOVES) + 1       # 50
N_ACTIONS = len(MOVES) + 2    # 51

MAX_GAZ = 5
GRID = 5                      # passability grid round the pusher (GRID x GRID tiles, frame-aligned)
OBS_DIM = MAX_GAZ * 4 + 1 + 2 + 1 + 2 + 1 + 3 + GRID * GRID + 3 + 1 + 1   # 60


def frame(cx, cy, dx, dy, mirror):
    """Returns (to_frame, from_frame) for the push frame at (cx, cy) with x along (dx, dy)."""
    nx, ny = -dy, dx
    if mirror:
        nx, ny = -nx, -ny

    def to_frame(x, y):
        return (x - cx) * dx + (y - cy) * dy, (x - cx) * nx + (y - cy) * ny

    def from_frame(a, l):
        return cx + dx * a + nx * l, cy + dy * a + ny * l
    return to_frame, from_frame


def pusher_obs(px, py, other, members, cx, cy, dx, dy, tc, passable, t_frac, lag):
    """The observation vector of one pusher.
    other: (x, y) of the other pusher or None; members: [(x, y, age, hopping)] of the herd;
    (cx, cy): herd centre; (dx, dy): push direction; passable(x, y) on tile ints.
    Returns (obs list of OBS_DIM floats, mirror flag)."""
    nx0, ny0 = -dy, dx
    mirror = ((px - cx) * nx0 + (py - cy) * ny0) < 0.0
    to_f, from_f = frame(cx, cy, dx, dy, mirror)
    o = []
    # the gazelles, rear (most negative along) first, up to MAX_GAZ
    gz = sorted((to_f(m[0], m[1]) + (m[2], m[3]) for m in members), key=lambda q: q[0])
    for k in range(MAX_GAZ):
        if k < len(gz):
            a, l, age, hop = gz[k]
            o += [a / 10.0, l / 10.0, 1.0 if hop else 0.0, max(0.0, 1.0 - age / 8.0)]
        else:
            o += [0.0, 0.0, 0.0, 0.0]
    o.append(len(gz) / MAX_GAZ)
    if gz:
        sa = max(q[0] for q in gz) - min(q[0] for q in gz)
        sl = max(q[1] for q in gz) - min(q[1] for q in gz)
    else:
        sa = sl = 0.0
    o += [sa / 10.0, sl / 10.0]
    o.append(geom.tc_edge_dist(cx, cy, tc[0], tc[1]) / 30.0)
    pa, pl = to_f(px, py)
    o += [pa / 10.0, pl / 10.0]
    near = min((math.hypot(px - m[0], py - m[1]) for m in members), default=10.0)
    o.append(min(near, 10.0) / 10.0)
    if other is not None:
        oa, ol = to_f(other[0], other[1])
        o += [oa / 10.0, ol / 10.0, 1.0]
    else:
        o += [0.0, 0.0, 0.0]
    # passability round the pusher, frame-aligned, 1 tile apart
    h = GRID // 2
    for i in range(-h, h + 1):
        for j in range(-h, h + 1):
            x, y = from_f(pa + i, pl + j)
            o.append(1.0 if passable(int(x), int(y)) else 0.0)
    # the way ahead of the herd
    for k in (2.0, 4.0, 6.0):
        x, y = from_f(k, 0.0)
        o.append(1.0 if passable(int(x), int(y)) else 0.0)
    o.append(t_frac)
    o.append(lag / 2.0)
    assert len(o) == OBS_DIM, len(o)
    return o, mirror


def move_target(action, rear_xy, cx, cy, dx, dy, mirror):
    """World (x, y) of a move action relative to the rear gazelle in the pusher's mirrored frame."""
    a, l = MOVES[action]
    to_f, from_f = frame(cx, cy, dx, dy, mirror)
    ra, rl = to_f(rear_xy[0], rear_xy[1])
    return from_f(ra + a, rl + l)
