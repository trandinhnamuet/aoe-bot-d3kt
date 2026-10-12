"""What a task may see and do. Implemented by the game adapter and by sim.Sim.

World (read):
    now            game seconds
    W, H           map size in tiles
    tc             (x, y) of our town centre
    units()        our villagers now: [U]
    unit(id)       one of ours, or None
    animals()      gaia animals in sight now: [U]
    animal(id)     an animal in sight now, or None
    track(id)      an animal wherever it is (the game reads it by pointer), or None once dead / gone
    last_seen(id)  (x, y, t) where an animal was last in sight, or None
    target_of(id)  the unit an animal is attacking / chasing now (id), or None
    action_of(id)  what one of ours does now: ("attack", target_id) | ("move",) | ("idle",) | None
    passable(x, y) tile walkable (not water / forest / building / off the map)
    visible(x, y)  tile in sight now

Orders (write) - every order reaches the game ~1 game second later (lockstep):
    move(ids, x, y)      attack(ids, target_id)      stop(ids)
"""


class U:
    """Snapshot of one unit. kind: villager, gazelle, elephant, lion, other."""
    __slots__ = ("id", "x", "y", "hp", "maxhp", "type", "kind")

    def __init__(self, id, x, y, hp, maxhp, type=0, kind="other"):
        self.id, self.x, self.y, self.hp, self.maxhp, self.type, self.kind = id, x, y, hp, maxhp, type, kind

    def dist(self, x, y):
        return ((self.x - x) ** 2 + (self.y - y) ** 2) ** 0.5

    def __repr__(self):
        return "<%s#%d (%.1f,%.1f) %.0f/%.0f>" % (self.kind, self.id, self.x, self.y, self.hp, self.maxhp)


class Task:
    """One piece of work with a named state machine. It owns the villagers it was given, declares
    what it still wants (`want`), and ends in done or failed (with a reason). tick() runs every
    ~0.5 game s on the brain thread, micro() ~20 times a second on the fast thread."""
    name = "task"

    def __init__(self):
        self.state = "init"
        self.done = False
        self.failed = False
        self.reason = ""
        self.log = []
        self._last = {}

    def owned(self):
        """Villager ids this task controls now."""
        return []

    def say(self, w, msg):
        self.log.append((round(w.now, 1), msg))

    def finish(self, w, msg="done"):
        self.done, self.state = True, "done"
        self.say(w, msg)

    def fail(self, w, reason):
        self.failed, self.state, self.reason = True, "failed", reason
        self.say(w, "failed: " + reason)

    def recent(self, w, key, within):
        return w.now - self._last.get(key, -1e9) < within

    def mark(self, w, key):
        self._last[key] = w.now

    def tick(self, w, o):
        pass

    def micro(self, w, o):
        pass
