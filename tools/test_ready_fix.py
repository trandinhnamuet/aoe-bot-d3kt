"""The net cafe's 1v7 of 06/11 (all bots in team 2): a bot whose Ready went out with the wrong civ, and a bot that
is NOT ready, must both end READY on Random + team 2 as the HOST sees it. Hidden games only
(bot desktop), killed by their own PIDs.

    .venv\Scripts\python tools/test_ready_fix.py"""
import sys
import time

sys.path.insert(0, r"D:\Game\AoESolo\launcher")
import lobby  # noqa: E402
import procs  # noqa: E402

GAME = r"D:\Game\AoE-HD"
DLL = r"D:\Game\AoESolo\hook\aoehook.dll"
RANDOM, TEAM = lobby.CIV_RANDOM, 2

lobby.reg_set(lobby.REG_SERVICE, "Internet TCP/IP Connection For DirectPlay")
games = []
ok = True
try:
    h = procs.start(GAME, "AOEBOT.EXE", DLL, True, log=print)
    games.append(h)
    lobby.host_create(h, log=print, name="HostT")
    cl = []
    for nm in ("CliA", "CliB"):
        c = procs.start(GAME, "AOEBOT.EXE", DLL, True, log=print)
        games.append(c)
        lobby.open_connection(c, nm, print)
        lobby.fast_session_list(c, 1000)
        lobby.join_from_list(c, log=print)
        time.sleep(1.0)
        cl.append((c, lobby.my_player_number(c) - 1))

    def state(slot):
        comm = h.mem.u32(lobby.ADDR_COMM)
        print("   ready marks", [h.mem.u32(comm + lobby.COMM_READY + 4 * k) for k in range(8)])
        return lobby.is_ready(h, slot), lobby.slot_civ(h, slot), lobby.slot_team(h, slot)

    print("slots", [x[1] for x in cl]); state(0)
    # A: ready already, on a concrete civ (what the host saw at the cafe: "civ 15 team 1")
    a, sa = cl[0]
    lobby._click(a, lobby.LOBBY_READY_CLIENT, 1.5)
    print("A before", state(sa))
    lobby.client_set_civ_team(a, sa, RANDOM, TEAM, host=h, log=print)
    print("A after ", state(sa))
    ok &= state(sa) == (True, RANDOM, TEAM + 1)

    # B: not ready, on a concrete civ (the cafe's "all bots not ready"): sent again until the host sees it
    b, sb = cl[1]
    print("B before", state(sb))
    lobby.client_set_civ_team(b, sb, RANDOM, TEAM, host=h, log=print)
    print("B after ", state(sb))
    ok &= state(sb) == (True, RANDOM, TEAM + 1)

    # C: the same bot, already ready and right: nothing is clicked, it stays ready
    lobby.client_set_civ_team(b, sb, RANDOM, TEAM, host=h, log=print)
    print("B again ", state(sb))
    ok &= state(sb) == (True, RANDOM, TEAM + 1)
finally:
    for g in games:
        g.kill()
print("PASS" if ok else "FAIL")
