"""Game-state reader and command issuer for AoE RoR (AoE-HD EMPIRESX.EXE).

Addresses were reverse engineered from this exact executable.
"""
import struct
import time

# ---- static addresses
ADDR_WORLD_PTR = 0x6A6858          # RGE_Game_World*
ADDR_SCREEN_PTR = 0x7C4B18         # in-game screen (TRIBE_Screen_Game*)
FN_CALLOC = 0x528450               # cdecl void* calloc(n, size)
FN_SUBMIT = 0x42BA60               # thiscall RGE_Command::submit(buf, size)
FN_CMD_ORDER = 0x42BAB0            # thiscall (units**, short n, target*, float x, float y)   type 0
FN_CMD_STOP = 0x42BB50             # thiscall (units**, short n)                               type 1
FN_CMD_WORK = 0x42BBD0             # thiscall (units**, short n, target*, float x, float y)   type 2
FN_CMD_MOVE = 0x42BCF0             # thiscall (units**, short n, target*, float x, float y)   type 3
FN_CMD_TRAIN = 0x4EB730            # thiscall (building*, short unit_type)                    type 0x64
FN_CMD_RESEARCH = 0x4EB7D0         # thiscall (building*, short tech_id)                      type 0x65
FN_CMD_BUILD = 0x4EB870
FN_PLAYER_RESIGN = 0x45F760        # thiscall RGE_Player::resign(comm player no, 0) -> command 0x0B
FN_CMD_DELETE = 0x4EBBF0           # thiscall (object*)  type 0x6A: 8-byte command holding the object id (the Delete key)
FN_CMD_SPEED = 0x4EBB80            # thiscall (float speed)  type 0x67 sub 1 (host sets the match speed)            # thiscall (units**, short n, short type, float x, float y) type 0x66

# ---- world offsets
W_PLAYER_COUNT = 0x3C
W_PLAYERS = 0x40
W_COMMAND = 0x58
W_OBJ_TABLE = 0x88
W_OBJ_TABLE_SIZE = 0x8C

# ---- player offsets
P_NAME = 0x44
P_ID = 0x4A          # short
P_RESOURCES = 0x50   # float*
P_CIV = 0x109        # byte: 0 Gaia, 1 Egyptian ... 16 Macedonian (AoE-MapCap offsets.PLAYER_CIV)
P_RESEARCH = 0x224   # -> research object: +0 -> entries (8 bytes each, int16 state at +4), +4 int16 count

# ---- object offsets
O_ID = 0x04
O_MASTER = 0x08
O_OWNER = 0x0C
O_HP = 0x30
O_X = 0x38
O_Y = 0x3C

# ---- master (unit definition) offsets
M_TYPE = 0x04        # byte: 10 static, 20 animated, 30 doppel, 40 moving, 50 action, 60 projectile, 70 combat, 80 building
M_NAME = 0x08
M_ID = 0x10          # short
M_CLASS = 0x14       # short

RES_FOOD, RES_WOOD, RES_STONE, RES_GOLD, RES_POP_HEADROOM = 0, 1, 2, 3, 4


def f2u(f):
    return struct.unpack("<I", struct.pack("<f", f))[0]


class Unit:
    __slots__ = ("ptr", "id", "type", "cls", "kind", "name", "owner", "hp", "x", "y", "master")

    def __repr__(self):
        return "<%s #%d p%d (%.1f,%.1f) hp=%.0f>" % (self.name, self.id, self.owner, self.x, self.y, self.hp)


class Game:
    def __init__(self, mem, hook):
        self.m = mem
        self.h = hook
        self._names = {}
        self._player_ids = {}

    # ---------------------------------------------------------------- reading
    def world(self):
        return self.m.u32(ADDR_WORLD_PTR) or 0

    def in_game(self):
        w = self.world()
        return bool(w) and bool(self.m.u32(w + W_PLAYERS))

    def players(self):
        w = self.world()
        n = self.m.u32(w + W_PLAYER_COUNT) or 0
        arr = self.m.u32(w + W_PLAYERS)
        return [self.m.u32(arr + 4 * i) for i in range(min(n, 9))]

    def player_ptr(self, idx):
        ps = self.players()
        return ps[idx] if idx < len(ps) else 0

    def resources(self, idx, n=8):
        p = self.player_ptr(idx)
        r = self.m.u32(p + P_RESOURCES)
        raw = self.m.read(r, 4 * n)
        return list(struct.unpack("<%df" % n, raw)) if raw else [0.0] * n

    def research_states(self, idx):
        """[state per tech id] for a player: 0 locked, 1 available, 2 being researched, 3 done."""
        p = self.player_ptr(idx)
        obj = self.m.u32(p + P_RESEARCH) if p else 0
        if not obj:
            return []
        arr, n = self.m.u32(obj), self.m.u16(obj + 4)
        if not arr or not n or n > 1024:
            return []
        raw = self.m.read(arr, n * 8)
        if not raw:
            return []
        return [struct.unpack_from("<h", raw, i * 8 + 4)[0] for i in range(n)]

    def civ(self, idx):
        p = self.player_ptr(idx)
        return self.m.u8(p + P_CIV) if p else 0

    def player_name(self, idx):
        p = self.player_ptr(idx)
        return self.m.cstr(self.m.u32(p + P_NAME) or 0)

    def _owner_index(self, pptr):
        v = self._player_ids.get(pptr)
        if v is None:
            v = self.m.u16(pptr + P_ID)
            v = -1 if v is None else v
            self._player_ids[pptr] = v
        return v

    def _master_info(self, mptr):
        info = self._names.get(mptr)
        if info is None:
            raw = self.m.read(mptr, 0x18)
            if not raw:
                return None
            kind = raw[4]
            name = self.m.cstr(struct.unpack_from("<I", raw, 8)[0], 32) or "?"
            uid = struct.unpack_from("<h", raw, 0x10)[0]
            cls = struct.unpack_from("<h", raw, 0x14)[0]
            info = (kind, name, uid, cls)
            self._names[mptr] = info
        return info

    def units(self, owner=None):
        """All live objects (optionally of one player index)."""
        w = self.world()
        tbl = self.m.u32(w + W_OBJ_TABLE)
        n = self.m.u32(w + W_OBJ_TABLE_SIZE) or 0
        raw = self.m.read(tbl, 4 * n)
        if not raw:
            return []
        ptrs = struct.unpack("<%dI" % n, raw)
        out = []
        for ptr in ptrs:
            if not ptr:
                continue
            o = self.m.read(ptr, 0x40)
            if not o:
                continue
            mptr, optr = struct.unpack_from("<II", o, O_MASTER)
            idx = self._owner_index(optr) if optr else -1
            if owner is not None and idx != owner:
                continue
            mi = self._master_info(mptr)
            if not mi:
                continue
            u = Unit()
            u.ptr = ptr
            u.id = struct.unpack_from("<i", o, O_ID)[0]
            u.kind, u.name, u.type, u.cls = mi
            u.master = mptr
            u.owner = idx
            u.hp, = struct.unpack_from("<f", o, O_HP)
            u.x, u.y = struct.unpack_from("<ff", o, O_X)
            out.append(u)
        return out

    # ---------------------------------------------------------------- commands
    def command_obj(self):
        return self.m.u32(self.world() + W_COMMAND)

    def alloc(self, size):
        return self.h.call("cdecl", FN_CALLOC, 1, size)

    def _alive(self, o, need_hp=True):
        """The object still lives at its pointer: the id at ptr+4 matches (a dead unit's memory is
        freed and reused - a build command with such a pointer crashed AOEBOT.EXE, 13/10 00:09, and the
        host hung waiting for the dropped player) and, for units, its hp is positive."""
        if o is None or not getattr(o, "ptr", 0):
            return False
        try:
            if self.m.i32(o.ptr + O_ID) != o.id:
                return False
            if need_hp and self.m.f32(o.ptr + O_HP) <= 0.0:
                return False
        except Exception:  # noqa: BLE001
            return False
        return True

    def _live(self, units):
        return [u for u in units if self._alive(u)]

    def _unit_array(self, units):
        buf = self.alloc(4 * len(units))
        self.m.write(buf, struct.pack("<%dI" % len(units), *[u.ptr for u in units]))
        return buf

    def train(self, building, unit_type):
        if not self._alive(building, need_hp=False):
            return None
        return self.h.call("thiscall", FN_CMD_TRAIN, self.command_obj(), building.ptr, unit_type)

    def research(self, building, tech_id):
        if not self._alive(building, need_hp=False):
            return None
        return self.h.call("thiscall", FN_CMD_RESEARCH, self.command_obj(), building.ptr, tech_id)

    def delete(self, obj):
        """Delete one of our own objects (the Delete key): used to open a gap in the house wall."""
        if not self._alive(obj, need_hp=False):
            return None
        return self.h.call("thiscall", FN_CMD_DELETE, self.command_obj(), obj.ptr)

    def order(self, units, target=None, x=None, y=None):
        """Right-click equivalent: gather / attack / move depending on target."""
        units = self._live(units)
        if not units:
            return
        if x is None:
            x, y = (target.x, target.y) if target else (0.0, 0.0)
        if target is not None and not self._alive(target, need_hp=False):
            target = None                                # gone: a plain move to where it was
        arr = self._unit_array(units)
        return self.h.call("thiscall", FN_CMD_ORDER, self.command_obj(), arr, len(units),
                           target.ptr if target else 0, f2u(x), f2u(y))

    def move(self, units, x, y):
        """Right-click on the ground (the type-3 move command is ignored by this build)."""
        units = self._live(units)
        if not units:
            return
        arr = self._unit_array(units)
        return self.h.call("thiscall", FN_CMD_ORDER, self.command_obj(), arr, len(units), 0, f2u(x), f2u(y))

    def stop(self, units):
        units = self._live(units)
        if not units:
            return
        arr = self._unit_array(units)
        return self.h.call("thiscall", FN_CMD_STOP, self.command_obj(), arr, len(units))

    def resign(self, player_idx, comm_player_no):
        """Same call as the in-game Resign dialog: player->vtbl[0xD4](comm player number, 0) = 0x45F760."""
        return self.h.call("thiscall", FN_PLAYER_RESIGN, self.player_ptr(player_idx), comm_player_no, 0)

    def set_speed(self, speed):
        return self.h.call("thiscall", FN_CMD_SPEED, self.command_obj(), f2u(float(speed)))

    def can_place(self, player_idx, building_type, x, y):
        """Ask the game itself whether `building_type` may be placed at (x, y) for this player
        (same check the build command runs: master->vtbl[0x20](player, x, y, &reason, 1,1,1,1,1,1))."""
        p = self.player_ptr(player_idx)
        masters = self.m.u32(p + 0x24)
        master = self.m.u32(masters + 4 * building_type) if masters else 0
        if not master:
            return False
        fn = self.m.u32(self.m.u32(master) + 0x20)
        if not getattr(self, "_reason_buf", None):
            self._reason_buf = self.alloc(16)
        self.m.write(self._reason_buf, bytes(4))
        r = self.h.call("thiscall", fn, master, p, f2u(x), f2u(y), self._reason_buf, 1, 1, 1, 1, 1, 1)
        out = self.m.i32(self._reason_buf) or 0
        self.last_place_reason = (r & 0xFF, out)
        return (r & 0xFF) == 0      # 0 = free; otherwise blocked (out = id of the blocking object, if any)

    def build(self, units, building_type, x, y):
        units = self._live(units)
        if not units:
            return
        arr = self._unit_array(units)
        return self.h.call("thiscall", FN_CMD_BUILD, self.command_obj(), arr, len(units), building_type, f2u(x), f2u(y))
