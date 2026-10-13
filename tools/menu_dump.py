"""Control rectangles of the game's menu screens, read from memory (panel +0x24..+0x30 = x, y, x2, y2;
the screen panel at 0x7C4B18). Used to map the lobby click coordinates of the HD build to the normal
AoE (AOE1R), whose menus are drawn at a fixed 800x600.

python menu_dump.py [GAME_DIR=D:\\Game\\AOE1R]      (hidden bot instance; prints every screen on the way)
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "launcher"))
import lobby  # noqa: E402
import procs  # noqa: E402

GD = sys.argv[1] if len(sys.argv) > 1 else r"D:\Game\AOE1R"
DLL = r"D:\Game\AoESolo\hook\aoehook.dll"


def controls(gp):
    m = gp.mem

    def rect(p):
        try:
            x, y, x2, y2 = (m.i32(p + o) for o in (0x24, 0x28, 0x2C, 0x30))
            if 0 <= x <= x2 < 2000 and 0 <= y <= y2 < 2000:
                return (x, y, x2, y2)
        except Exception:  # noqa: BLE001
            pass
        return None

    def name_of(p):
        try:
            q = m.u32(p + 0x1C)
            s = m.cstr(q) if q else None
            return s if s and len(s) < 40 else None
        except Exception:  # noqa: BLE001
            return None
    seen, out = set(), []

    def walk(p, depth):
        if depth > 8 or p in seen:
            return
        seen.add(p)
        raw = m.read(p, 0x300) or b""
        for off in range(0, len(raw) - 3, 4):
            q = struct.unpack_from("<I", raw, off)[0]
            if not (0x100000 < q < 0x7fff0000) or q in seen:
                continue
            try:
                vt = m.u32(q)
            except Exception:  # noqa: BLE001
                continue
            r = rect(q)
            if r and 0x400000 < vt < 0x800000:
                out.append((hex(vt), r, name_of(q)))
                walk(q, depth + 1)
    walk(m.u32(lobby.ADDR_SCREEN), 0)
    return sorted(set(out), key=lambda c: (c[1][1], c[1][0]))


def show(gp, label):
    print("== %s (screen %s)" % (label, lobby.current_screen(gp)))
    for vt, r, n in controls(gp):
        print("   %s %-22s centre (%d,%d) %s" % (vt, r, (r[0] + r[2]) // 2, (r[1] + r[3]) // 2, n or ""))


def main():
    saved = lobby.reg_get_dword(lobby.REG_SCREEN)
    lobby.reg_set_dword(lobby.REG_SCREEN, 1366)
    try:
        gp = procs.start(GD, "AOEBOT.EXE", DLL, True, log=print)
        lobby.wait_screen(gp, "Main Menu", 60)
    finally:
        lobby.reg_set_dword(lobby.REG_SCREEN, saved)
    try:
        show(gp, "main menu")
        lobby.open_connection(gp, "dump", print)
        show(gp, "game list")
        gp.hook.click(399, 568)
        time.sleep(2)
        show(gp, "create dialog")
        gp.hook.click(299, 379)
        lobby.wait_screen(gp, "MP Setup Screen", 10)
        time.sleep(1.5)
        show(gp, "room (host)")
    finally:
        gp.p.kill()


if __name__ == "__main__":
    main()
