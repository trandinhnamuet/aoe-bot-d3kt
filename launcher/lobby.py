"""Multiplayer lobby automation (TCP/IP on 127.0.0.1) for AoE-HD at 1366x768.

All clicks go through the hook's virtual mouse, so they work on hidden windows and never move
the real cursor. Every important step is verified by reading game memory.
"""
import os
import struct
import time
import winreg

# ---------------------------------------------------------------- static addresses (EMPIRESX.EXE AoE-HD)
ADDR_GAME = 0x585E88       # TRIBE_Game*
ADDR_COMM = 0x585DF8       # TCommunications_Handler*
ADDR_WORLD = 0x6A6858      # RGE_Game_World* (non-zero once a match is loaded)
G_CIV = 0xA94              # byte[8]  civ per lobby slot (1..16, 0x11 = random?)
G_TEAM = 0x994             # byte[8]  1 = no team, 2.. = team 1..
COMM_MY_PLAYER = 0x10E0    # dword    my player number (1-based)
COMM_NUM_PLAYERS = 0x12D8  # word     players in session

CIVS = ["Egyptian", "Greek", "Babylonian", "Assyrian", "Minoan", "Hittite", "Phoenician", "Sumerian",
        "Persian", "Shang", "Yamato", "Choson", "Roman", "Carthaginian", "Palmyran", "Macedonian"]

CIV_RANDOM = len(CIVS) + 1      # last entry of the lobby civ list

MAP_SIZES = ["Tiny", "Small", "Medium", "Large", "Huge", "Gigantic"]
MAP_TYPES = ["Small Islands", "Large Islands", "Coastal", "Inland", "Highland", "Continental",
             "Mediterranean", "Hill Country", "Narrows"]
AGES = ["Default", "Nomad", "Stone Age", "Tool Age", "Bronze Age", "Iron Age"]
RESOURCES = {"Default": 0, "Medium": 2, "High": 3}
POP_LIMITS = [25, 50, 75, 100, 125, 150, 175, 200]
VICTORIES = ["Standard", "Conquest", "Time Limit", "Score"]   # lobby order (index = ex_tcf.cfg byte 0x1C)

# ---------------------------------------------------------------- screen coordinates (1366x768 client)
MAIN_MULTIPLAYER = (683, 397)
CONN_TCPIP = (400, 337)
CONN_OK = (405, 728)
GAMES_SHOW = (682, 617)
GAMES_FIRST_ROW = (300, 157)
GAMES_JOIN = (234, 728)
GAMES_CREATE = (682, 728)
CREATE_OK = (583, 464)
LOBBY_ROW_Y = [152, 190, 229, 267, 306, 344, 383, 421]
LOBBY_CIV_ARROW_X = 380
LOBBY_CIV_ITEM_X = 420
LOBBY_TEAM_X = 842
LOBBY_READY_HOST = (52, 728)
LOBBY_READY_CLIENT = (245, 728)
LOBBY_START = (628, 728)
DROPDOWN_ITEM_H = 21

REG_KEY = r"Software\Microsoft\Games\Age of Empires\1.00"
REG_NAME = "Default Age Of Empires Player Name"
REG_GAMENAME = "Default Age Of Empires MP Gamename"
REG_SERVICE = "Default Age of Empires Multiplayer Service"
REG_SCREEN = "Screen Size"
G_SCREEN_W = 0x1CAC        # int game resolution (width, height)


# ---------------------------------------------------------------- settings file / registry
def write_settings(game_dir, map_size="Medium", map_type="Highland", age="Default", resources="Default",
                   pop_limit=50, reveal_map=False, fixed_positions=False, victory="Conquest", cheats=False):
    """Pre-seed the lobby settings ExWE.dll loads at startup (data/ex_tcf.cfg, 47 bytes)."""
    path = os.path.join(game_dir, "data", "ex_tcf.cfg")
    try:
        b = bytearray(open(path, "rb").read())
    except OSError:
        b = bytearray()
    if len(b) != 47:
        b = bytearray(bytes.fromhex("000000007817 5f42 00000000 00000100 00000001 03000000 07000000 00000000"
                                    "03000000 00000000 00000100 0000c8".replace(" ", "")))
    b[0x13] = 0                                   # scenario: Random Map
    b[0x14] = MAP_SIZES.index(map_size)
    b[0x18] = MAP_TYPES.index(map_type)
    b[0x1C] = VICTORIES.index(victory)            # victory (the user: Conquest by default)
    b[0x20] = AGES.index(age)
    b[0x24] = RESOURCES[resources]
    b[0x29] = 0 if fixed_positions else 1         # 1 = random positions
    b[0x2A] = 1 if reveal_map else 0
    b[0x2B] = 0                                   # full tech tree off
    b[0x2C] = 1 if cheats else 0                  # Allow Cheats (the staged tests: STEROIDS / WOODSTOCK through chat)
    b[0x2E] = int(pop_limit)
    open(path, "wb").write(bytes(b))


def reg_get(name, default=None):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return default


def reg_get_dword(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            v, t = winreg.QueryValueEx(k, name)
            return int(v)
    except (OSError, ValueError):
        return None


def reg_set_dword(name, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))


def reg_set(name, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


# ---------------------------------------------------------------- memory helpers
def my_player_number(gp):
    comm = gp.mem.u32(ADDR_COMM)
    return gp.mem.u32(comm + COMM_MY_PLAYER) if comm else None


def session_players(gp):
    comm = gp.mem.u32(ADDR_COMM)
    return gp.mem.u16(comm + COMM_NUM_PLAYERS) if comm else 0


COMM_PLAYER_STATE = 0x16D4  # dword[1..8] per player: 2 or 5 = present in the session


def session_states(gp):
    comm = gp.mem.u32(ADDR_COMM)
    if not comm:
        return []
    return [gp.mem.u32(comm + COMM_PLAYER_STATE + 4 * i) for i in range(1, 9)]


def present_players(gp):
    """Players the HOST really sees in its room (state 2 or 5)."""
    return sum(1 for st in session_states(gp) if st in (2, 5))


def slot_civ(gp, slot):
    g = gp.mem.u32(ADDR_GAME)
    return gp.mem.u8(g + G_CIV + slot) if g else None


def slot_team(gp, slot):
    g = gp.mem.u32(ADDR_GAME)
    return gp.mem.u8(g + G_TEAM + slot) if g else None


def in_match(gp):
    w = gp.mem.u32(ADDR_WORLD)
    return bool(w) and bool(gp.mem.u32(w + 0x40))


# ---------------------------------------------------------------- UI steps
def detect_scale(gp, log=print, timeout=8):
    """Coordinates are designed for 1366x768; scale them if this instance runs another resolution."""
    t0 = time.time()
    w = h = 0
    while time.time() - t0 < timeout:
        g = gp.mem.u32(ADDR_GAME)
        if g:
            w = gp.mem.u32(g + G_SCREEN_W) or 0
            h = gp.mem.u32(g + G_SCREEN_W + 4) or 0
            if w and h:
                break
        time.sleep(0.5)
    if not (w and h):
        w, h = 1366, 768        # Screen Size is forced to 1366 for the session
    gp.sx = w / 1366.0
    gp.sy = h / 768.0
    log("game resolution %dx%d (scale %.3f, %.3f)" % (w, h, gp.sx, gp.sy))


def _xy(gp, x, y):
    return int(round(x * getattr(gp, "sx", 1.0))), int(round(y * getattr(gp, "sy", 1.0)))


def _dialog_xy(gp, x, y):
    """Dialogs keep their size and sit in the screen's centre in both builds (the screens around them
    scale): a dialog point is its offset from the 1366x768 centre, put on this window's centre. Measured
    on AOE1R: the Create dialog's OK at (299,379) = (400 - 100, 300 + 80) vs (683 - 100, 384 + 80) in HD."""
    w = 1366.0 * getattr(gp, "sx", 1.0)
    h = 768.0 * getattr(gp, "sy", 1.0)
    return int(round(w / 2.0 + (x - 683))), int(round(h / 2.0 + (y - 384)))


def _click(gp, xy, wait=0.6):
    gp.hook.click(*_xy(gp, xy[0], xy[1]))
    time.sleep(wait)


CONN_NAME = (680, 170)


def set_name_field(gp, name):
    """The name box is a real Win32 EDIT child of the game window: set its text directly."""
    import ctypes
    u = ctypes.windll.user32
    ed = u.FindWindowExW(gp.hwnd, 0, "Edit", None)
    if not ed:
        return False
    u.SendMessageW(ed, 0x000C, 0, ctypes.c_wchar_p(name))      # WM_SETTEXT
    return True


ADDR_SCREEN = 0x7C4B18     # current UI panel; panel+0x1C = name


def current_screen(gp):
    p = gp.mem.u32(ADDR_SCREEN)
    return gp.mem.cstr(gp.mem.u32(p + 0x1C) or 0) if p else None


def wait_screen(gp, names, timeout=15.0, poll=0.25):
    if isinstance(names, str):
        names = (names,)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if current_screen(gp) in names:
            return True
        time.sleep(poll)
    return False


def open_connection(gp, name=None, log=print):
    if not wait_screen(gp, "Main Menu", 90):
        raise RuntimeError("main menu not reached (screen=%s)" % current_screen(gp))
    time.sleep(0.5)
    for _ in range(3):
        _click(gp, MAIN_MULTIPLAYER, 0.3)
        if wait_screen(gp, "MP Startup Screen", 6):
            break
    else:
        raise RuntimeError("multiplayer screen not reached")
    if name:
        set_name_field(gp, name)
        time.sleep(0.2)
    _click(gp, CONN_TCPIP, 0.5)
    for _ in range(3):
        _click(gp, CONN_OK, 0.3)
        if wait_screen(gp, "Join Screen", 8):
            return
    raise RuntimeError("game list screen not reached (screen=%s)" % current_screen(gp))


LIST_CANCEL = (1055, 728)


def rename_on_list(gp, name, log=print):
    """A parked bot (game list) goes back to the connection screen, takes a new name, and comes back in."""
    if current_screen(gp) == "MP Setup Screen":
        _click(gp, LIST_CANCEL, 0.2)
        wait_screen(gp, "Join Screen", 5, poll=0.05)
    _click(gp, LIST_CANCEL, 0.2)
    if not wait_screen(gp, "MP Startup Screen", 5, poll=0.05):
        raise RuntimeError("connection screen not reached (screen=%s)" % current_screen(gp))
    set_name_field(gp, name)
    time.sleep(0.2)
    _click(gp, CONN_TCPIP, 0.2)
    for _ in range(3):
        _click(gp, CONN_OK, 0.2)
        if wait_screen(gp, "Join Screen", 8, poll=0.05):
            return
    raise RuntimeError("game list screen not reached (screen=%s)" % current_screen(gp))


def reopen_list(gp, log=print):
    """Back from the game list to the connection screen and in again (fresh DirectPlay session)."""
    if current_screen(gp) == "MP Setup Screen":
        _click(gp, LIST_CANCEL, 0.2)
        wait_screen(gp, "Join Screen", 5, poll=0.05)
    _click(gp, LIST_CANCEL, 0.2)
    if not wait_screen(gp, "MP Startup Screen", 5, poll=0.05):
        raise RuntimeError("connection screen not reached (screen=%s)" % current_screen(gp))
    _click(gp, CONN_TCPIP, 0.2)
    for _ in range(3):
        _click(gp, CONN_OK, 0.2)
        if wait_screen(gp, "Join Screen", 8, poll=0.05):
            return
    raise RuntimeError("game list screen not reached (screen=%s)" % current_screen(gp))


def host_create(gp, log=print, name=None):
    open_connection(gp, name, log)
    for _ in range(3):
        _click(gp, GAMES_CREATE, 1.5)
        gp.hook.click(*_dialog_xy(gp, *CREATE_OK))
        time.sleep(0.3)
        if wait_screen(gp, "MP Setup Screen", 10):
            n = my_player_number(gp)
            log("host lobby ready, my player number=%s" % n)
            return n
    raise RuntimeError("could not create the lobby (screen=%s)" % current_screen(gp))


def client_join(gp, log=print, retries=6, name=None):
    open_connection(gp, name, log)
    for attempt in range(retries):
        _click(gp, GAMES_SHOW, 3.0)          # the Locate Session dialog is answered by the hook (127.0.0.1)
        _click(gp, GAMES_FIRST_ROW, 0.6)
        _click(gp, GAMES_JOIN, 0.3)
        if wait_screen(gp, "MP Setup Screen", 8):
            time.sleep(1.0)
            n = my_player_number(gp)
            log("joined lobby as player %s (attempt %d)" % (n, attempt + 1))
            return n
        log("join attempt %d failed (screen=%s, rooms listed %s), retrying" % (
            attempt + 1, current_screen(gp), listed_sessions(gp)))
        if attempt % 2 == 1:
            try:
                reopen_list(gp, log)
            except Exception as e:
                log("reopen: %r" % (e,))
    raise RuntimeError("could not join the lobby")


def choose_civ(gp, slot, civ, log=print):
    """civ: 1..16 (index into CIVS + 1). Verified via memory; tries list-below then list-above."""
    row_y = LOBBY_ROW_Y[slot]
    n_items = len(CIVS) + 1
    before = slot_civ(gp, slot)
    if civ == CIV_RANDOM and before == CIV_RANDOM:
        return True
    for direction in ("below", "above"):
        gp.hook.click(*_xy(gp, LOBBY_CIV_ARROW_X, row_y))
        time.sleep(0.8)
        if direction == "below":
            y = row_y + 33 + (civ - 1) * DROPDOWN_ITEM_H
        else:
            y = row_y - 12 - (n_items - (civ - 1)) * DROPDOWN_ITEM_H
        gp.hook.click(*_xy(gp, LOBBY_CIV_ITEM_X, y))
        time.sleep(0.8)
        got = slot_civ(gp, slot)
        if got == civ or (civ == CIV_RANDOM and got is not None and got != before):
            log("slot %d civ=%s (byte %s)" % (slot, CIVS[civ - 1] if civ <= len(CIVS) else "Random", got))
            return True
        gp.hook.tap(0x1B)
        time.sleep(0.4)
    log("WARNING: could not set civ for slot %d (have %s)" % (slot, slot_civ(gp, slot)))
    return False


FN_GAME_SET_CIV = 0x507A40      # thiscall game->set_civ(slot, civ)      (what the civ dropdown does on the host)
FN_GAME_SET_TEAM = 0x41C190     # thiscall game->set_team(slot, team+1)
SCR_CIV_DROPDOWNS = 0x5D0       # MP setup screen: civ dropdown per slot
SCR_TEAM_BUTTONS = 0x590        # MP setup screen: team button per slot (state short at +0x1F6)


def host_set_civ(gp, slot, civ, log=print):
    """Host only: set a slot's civilisation without touching the UI (no dropdown pops up)."""
    g = gp.mem.u32(ADDR_GAME)
    gp.hook.call("thiscall", FN_GAME_SET_CIV, g, slot, civ)
    scr = gp.mem.u32(ADDR_SCREEN)
    dd = gp.mem.u32(scr + SCR_CIV_DROPDOWNS + 4 * slot) if scr else 0
    lst = gp.mem.u32(dd + 0xFC) if dd else 0
    node = gp.mem.u32(lst + 0xF4) if lst else 0
    idx = 0
    while node and idx < 40:
        if gp.mem.u32(node + 8) == civ:
            gp.mem.write(lst + 0x100, idx.to_bytes(2, "little"))     # dropdown shows the new line
            break
        node = gp.mem.u32(node + 0xC)
        idx += 1
    got = slot_civ(gp, slot)
    log("slot %d civ=%s (direct, byte %s)" % (slot, CIVS[civ - 1] if civ <= len(CIVS) else "Random", got))
    return got == civ


def host_set_team(gp, slot, team, log=print):
    """Host only: set a slot's team (0 = none) without touching the UI."""
    g = gp.mem.u32(ADDR_GAME)
    gp.hook.call("thiscall", FN_GAME_SET_TEAM, g, slot, team + 1)
    scr = gp.mem.u32(ADDR_SCREEN)
    btn = gp.mem.u32(scr + SCR_TEAM_BUTTONS + 4 * slot) if scr else 0
    if btn:
        gp.mem.write(btn + 0x1F6, int(team).to_bytes(2, "little"))
    ok = slot_team(gp, slot) == team + 1
    log("slot %d team=%s (direct, ok=%s)" % (slot, team or "-", ok))
    return ok


# The client's Ready message carries its civ / colour / team, read from the screen's own controls
# (civ dropdown 0x5D0, team button 0x590 ...); +0x72C / +0x738 keep the lobby's periodic sync from
# resetting the controls to the host's old values until Ready has gone out.
SCR_MY_CIV_PENDING = 0x72C
SCR_MY_TEAM_PENDING = 0x738


def client_set_civ_team(gp, slot, civ, team, host=None, log=print, timeout=2.0):
    """Client: set civ + team in the screen's controls and send them with Ready (no dropdown opens).
    Confirmed on the host's side when `host` is given. The bot is left READY on success."""
    scr = gp.mem.u32(ADDR_SCREEN)
    if not scr or current_screen(gp) != "MP Setup Screen":
        return False
    quiet = lambda m: None
    host_set_civ(gp, slot, civ, log=quiet)
    host_set_team(gp, slot, team, log=quiet)
    gp.mem.write(scr + SCR_MY_CIV_PENDING, int(civ).to_bytes(4, "little"))
    gp.mem.write(scr + SCR_MY_TEAM_PENDING, int(team + 1).to_bytes(4, "little"))
    _click(gp, LOBBY_READY_CLIENT, 0.1)
    if host is None:
        return True
    t0 = time.time()
    while time.time() - t0 < timeout:
        if slot_civ(host, slot) == civ and slot_team(host, slot) == team + 1:
            log("slot %d civ=%s team=%s (sent with Ready, %.1f s)" % (
                slot, CIVS[civ - 1] if civ <= len(CIVS) else "Random", team or "-", time.time() - t0))
            return True
        time.sleep(0.1)
    log("slot %d civ/team not confirmed (host sees civ %s team %s)" % (
        slot, slot_civ(host, slot), slot_team(host, slot)))
    return False


ENUM_TIMEOUT_IMM = 0x428F63      # imm32 of "push 4000": the game list's EnumSessions timeout (ms)


def fast_session_list(gp, ms=500):
    """Bots only: 'Show games' blocks the game for the whole EnumSessions timeout (4 s); on 127.0.0.1
    the room answers at once, so a short timeout lists it just as well."""
    import struct
    cur = gp.mem.read(ENUM_TIMEOUT_IMM - 1, 5)
    if cur[:1] == b"h" and struct.unpack("<I", cur[1:])[0] in (4000, 500, 1000, 2000, 3000, ms):
        # (any value we set before counts too: the 3 s retry window never applied once 500 ms was in - the user's
        #  1v7 of 1.2.21: two bots "no room listed" four times within 3 s, 8 processes answering on 127.0.0.1)
        return gp.mem.write(ENUM_TIMEOUT_IMM, struct.pack("<I", ms))
    return False


SCR_SESSION_COUNT = 0x4A4       # Join Screen: rooms in the game list


def listed_sessions(gp):
    scr = gp.mem.u32(ADDR_SCREEN)
    return gp.mem.u32(scr + SCR_SESSION_COUNT) if scr and current_screen(gp) == "Join Screen" else None


def join_from_list(gp, log=print, retries=8):
    """A bot already waiting on the game list ('Join Screen') joins the first room."""
    for attempt in range(retries):
        _click(gp, GAMES_SHOW, 0.05)            # returns once the session list is enumerated
        if listed_sessions(gp) == 0:
            log("no room listed yet (attempt %d)" % (attempt + 1))
            fast_session_list(gp, 1000 + 500 * attempt)   # a longer enumeration window each look (8 processes answer)
            time.sleep(0.3)
            continue
        _click(gp, GAMES_FIRST_ROW, 0.05)
        _click(gp, GAMES_JOIN, 0)
        if wait_screen(gp, "MP Setup Screen", 3 if attempt < 3 else 6, poll=0.05):
            n = None
            t0 = time.time()
            while not n and time.time() - t0 < 2:
                n = my_player_number(gp)
                time.sleep(0.05)
            log("joined lobby as player %s (attempt %d)" % (n, attempt + 1))
            return n
        if current_screen(gp) != "Join Screen":
            raise RuntimeError("bot left the game list (screen=%s)" % current_screen(gp))
        log("join failed with %s room(s) listed (attempt %d)" % (listed_sessions(gp), attempt + 1))
    raise RuntimeError("could not join the lobby")


def set_team(gp, slot, team, log=print):
    """team: 0 = no team, 1..4. Team button cycles; verified via memory."""
    want = team + 1
    for _ in range(6):
        if slot_team(gp, slot) == want:
            log("slot %d team=%s" % (slot, team or "-"))
            return True
        gp.hook.click(*_xy(gp, LOBBY_TEAM_X, LOBBY_ROW_Y[slot]))
        time.sleep(0.7)
    return slot_team(gp, slot) == want


def ready(gp, host):
    _click(gp, LOBBY_READY_HOST if host else LOBBY_READY_CLIENT, 1.0)


def start_match(gp, expected_players, log=print, timeout=60, attempts=10, on_retry=None):
    for attempt in range(attempts):
        _click(gp, LOBBY_START, 3.0)
        t1 = time.time()
        while time.time() - t1 < 25:
            if in_match(gp):
                log("match started")
                return True
            time.sleep(0.5)
        log("start attempt %d did not launch the match, retrying" % (attempt + 1))
        if on_retry:
            on_retry(attempt)
    raise RuntimeError("match did not start")


PANEL_MGR = 0x588138            # the game's panel manager (named screens and popups)
FN_PANEL_FIND = 0x452A60        # thiscall mgr->find(name) -> panel or 0
POPUPS = ("OKDialog", "Cancel Dialog", "YesNoDialog", "YesNoCancelDialog")


def find_panel(gp, name):
    buf = getattr(gp, "_namebuf", None)
    if not buf:
        buf = gp._namebuf = gp.hook.call("cdecl", 0x528450, 1, 64)     # calloc
    gp.mem.write(buf, name.encode() + b"\0")
    return gp.hook.call("thiscall", FN_PANEL_FIND, PANEL_MGR, buf)


def open_popups(gp):
    return [n for n in POPUPS if find_panel(gp, n)]
