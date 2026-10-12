"""One table decides who does what (KIEN_TRUC_AI.md 3.1).

Every tick the plan hands the allocator a list of Demands in priority order; the allocator assigns
each villager to exactly one of them. A villager keeps its job while the demand still wants it
(stickiness), the user's "who may do this" rules are the demands' eligibility (by birth index: the
first six are the berry pickers, hunting from the 9th villager on...), and whatever is left over
goes to the lowest-priority demand that takes everybody.

    d = [Demand("berry", 6, 6, prio=1, indices=range(0, 6)),
         Demand("scout", 2, 2, prio=2, indices=(6, 8)),
         Demand("wood", 1, 99, prio=9)]
    jobs = Allocator().assign(villagers_sorted_by_id, d, previous_jobs)   # {villager id: demand name}
"""


class Demand:
    __slots__ = ("name", "min", "max", "prio", "indices", "ok", "score", "pin")

    def __init__(self, name, min, max, prio, indices=None, ok=None, score=None, pin=()):
        self.name = name
        self.min, self.max, self.prio = min, max, prio
        self.indices = set(indices) if indices is not None else None   # birth indices allowed (None = any)
        self.ok = ok                      # extra eligibility: ok(index, villager) -> bool
        self.score = score                # preference among eligible villagers: lower first (e.g. distance)
        self.pin = set(pin)               # villager ids that must take this demand (a task owns them)

    def eligible(self, idx, v):
        if self.indices is not None and idx not in self.indices:
            return False
        return self.ok is None or self.ok(idx, v)


class Allocator:
    STICKY = 1.0                          # score bonus for staying on the current job

    def assign(self, villagers, demands, current=None):
        """villagers: list sorted by id (birth order); demands: in priority order (lower prio first);
        current: {id: demand name} from the last tick. Returns the new {id: demand name}."""
        current = current or {}
        demands = sorted(demands, key=lambda d: d.prio)
        idx_of = {v.id: i for i, v in enumerate(villagers)}
        free = {v.id: v for v in villagers}
        out = {}
        count = {d.name: 0 for d in demands}

        def take(d, vid):
            out[vid] = d.name
            count[d.name] += 1
            free.pop(vid, None)

        # 1. pinned villagers (tasks that own them)
        for d in demands:
            for vid in list(d.pin):
                if vid in free and count[d.name] < d.max:
                    take(d, vid)

        # 2. minimums, then maximums, in priority order; sticky villagers first, then by score
        def candidates(d):
            cands = [v for vid, v in free.items() if d.eligible(idx_of[vid], v)]
            cands.sort(key=lambda v: ((0 if current.get(v.id) == d.name else self.STICKY),
                                      d.score(v) if d.score else 0, idx_of[v.id]))
            return cands

        for level in ("min", "max"):
            for d in demands:
                want = (d.min if level == "min" else d.max) - count[d.name]
                if want <= 0:
                    continue
                for v in candidates(d)[:want]:
                    take(d, v.id)

        # 3. leftovers: the last demand that takes anybody, else the lowest priority one
        if free:
            sink = next((d for d in reversed(demands) if d.indices is None and d.ok is None), demands[-1] if demands else None)
            if sink is not None:
                for vid in list(free):
                    take(sink, vid)
        return out


def changes(old, new):
    """Villagers whose job changed: {id: (old, new)}."""
    return {vid: (old.get(vid), j) for vid, j in new.items() if old.get(vid) != j}
