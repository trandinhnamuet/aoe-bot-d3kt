"""World / Orders (brain.iface) over the running game, for the old Brain in d3kt.py: the tasks tuned
in sim/ run here unchanged. Positions and hp are read fresh by pointer on every call (the fast
thread runs 20 times a second between brain ticks); a pointer is trusted only while the id stored
in the object still matches (the game reuses freed memory)."""
import struct

import aoemem as am
import gamestate as gs
from brain.iface import U

KIND = {gs.GAZELLE: "gazelle", gs.ELEPHANT: "elephant"}


def kind_of(o):
    if o.cls == gs.CLS_VILLAGER:
        return "villager"
    k = KIND.get(o.type)
    if k:
        return k
    return "lion" if "lion" in o.name.lower() else "other"


class GameWorld:
    def __init__(self, brain, game):
        self.b = brain
        self.g = game
        self.m = game.m

    # ---------------------------------------------------------------- reads
    def _fresh(self, o):
        raw = self.m.read(o.ptr, 0x40)
        if not raw or len(raw) < 0x40:
            return None
        if struct.unpack_from("<i", raw, am.O_ID)[0] != o.id:
            return None                                   # the memory now holds another unit
        hp, = struct.unpack_from("<f", raw, am.O_HP)
        x, y = struct.unpack_from("<ff", raw, am.O_X)
        return U(o.id, x, y, hp, o.maxhp, o.type, kind_of(o))

    @property
    def lag(self):
        """Order lag in game seconds: ~1 s at x1, scaling with the game speed (measured as game clock
        over wall clock, sampled every 5 s; 1.0 until measured)."""
        import time as _t
        try:
            g, wall = self.now, _t.time()
            s0 = getattr(self, "_lag_s0", None)
            if s0 is None:
                self._lag_s0, self._lag_v = (g, wall), 1.0
            elif wall - s0[1] >= 5.0:
                sp = (g - s0[0]) / max(1e-6, wall - s0[1])
                if 0.3 <= sp <= 4.0:
                    self._lag_v = max(0.8, min(3.0, sp))
                self._lag_s0 = (g, wall)
            return getattr(self, "_lag_v", 1.0)
        except Exception:  # noqa: BLE001
            return 1.0

    @property
    def now(self):
        """The live game clock (ms at world+4), read through this world's own memory connection: the
        fast loop ran its 0.4-2.5 s order gates against the 1-Hz snapshot time before, so the lurer /
        killers / pushers were re-ordered only once a second in the game (the sim ran them at 20 Hz)."""
        try:
            w = self.g.world()
            t = self.m.u32(w + 4) if w else None
            if t:
                return t / 1000.0
        except Exception:  # noqa: BLE001
            pass
        from d3kt import game_s
        return game_s(self.b.s)

    @property
    def W(self):
        return self.b.r.W

    @property
    def H(self):
        return self.b.r.H

    @property
    def tc(self):
        return self.b.tc_anchor

    def units(self):
        return [u for u in (self._fresh(v) for v in self.b.s.villagers) if u]

    def unit(self, i):
        o = self.b._by_id.get(i)
        if o is None or o.cls != gs.CLS_VILLAGER:
            return None
        return self._fresh(o)

    def animals(self):
        out = []
        for o in self.b.s.gaia:
            if o.kind == gs.KIND_COMBAT and o.cls != gs.CLS_DEAD and kind_of(o) in ("gazelle", "elephant", "lion"):
                u = self._fresh(o)
                if u and u.hp > 0:
                    out.append(u)
        return out

    def animal(self, i):
        o = self.b._gaia_by_id.get(i)
        if o is None or o.cls == gs.CLS_DEAD:
            return None
        u = self._fresh(o)
        return u if u and u.hp > 0 else None

    def track(self, i):
        o = self.b._gaia_by_id.get(i) or self.b.anim_cache.get(i)
        if o is None or o.cls == gs.CLS_DEAD:
            return None
        u = self._fresh(o)
        return u if u and u.hp > 0 else None

    def last_seen(self, i):
        p = self.b.animal_pos.get(i)
        return (p[0], p[1], p[3]) if p else None

    def _ptr_map(self):
        return {o.ptr: o.id for o in self.b.s.mine}

    def target_of(self, i):
        o = self.b._gaia_by_id.get(i) or self.b.anim_cache.get(i)
        if o is None:
            return None
        act = self.b.r.action(o)
        if not act or not act[1]:
            return None
        return self._ptr_map().get(act[1])

    def action_of(self, i):
        o = self.b._by_id.get(i)
        if o is None:
            return None
        act = self.b.r.action(o)
        if not act:
            return ("idle",)
        if act[1]:
            tid = {g.ptr: g.id for g in self.b.s.gaia}.get(act[1])
            if tid is None:
                tid = {e.ptr: e.id for e in self.b.s.enemy}.get(act[1])
            if tid is not None:
                return ("attack", tid)
        return ("move",) if act[2] in (4, 0x0B) else ("idle",)

    def passable(self, x, y):
        pm = getattr(self.b, "pm", None)
        return bool(pm and pm.passable(int(x), int(y)))

    def visible(self, x, y):
        return self.b.s.visible(x, y)

    # ---------------------------------------------------------------- orders
    def _objs(self, ids):
        """The units an order goes to - never one that is running from an enemy soldier (the brain's
        retreat_until): the fast tasks re-ordered a fleeing lurer / pusher back into the fight at
        4-20 Hz, so the brain's flee order lasted a fraction of a second (the user's question on the
        flee priority: the flee now outranks every task)."""
        try:
            now, ru = self.now, self.b.retreat_until
        except Exception:  # noqa: BLE001
            now, ru = 0.0, {}
        return [o for o in (self.b._by_id.get(i) for i in ids) if o is not None and ru.get(o.id, 0) <= now]

    def move(self, ids, x, y):
        objs = self._objs(ids)
        if objs:
            self.b.gate_request(objs, x, y)
            self.g.move(objs, x, y)

    def attack(self, ids, tid):
        objs = self._objs(ids)
        tgt = self.b._gaia_by_id.get(tid) or self.b.anim_cache.get(tid) or self.b._by_id.get(tid)
        if objs and tgt is not None:
            self.b.gate_request(objs, tgt.x, tgt.y)
            self.g.order(objs, tgt)

    def stop(self, ids):
        objs = self._objs(ids)
        if objs:
            self.g.stop(objs)
