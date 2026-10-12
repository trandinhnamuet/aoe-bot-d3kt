import py_compile

p = r"D:\Game\AoESolo\launcher\lobby.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''def join_from_list(gp, log=print, retries=8):''', '''SCR_MY_CIV_PENDING = 0x72C      # client: civ change waiting to be sent to the host
SCR_MY_TEAM_PENDING = 0x738     # client: team change waiting to be sent to the host


def client_set_civ_team(gp, slot, civ, team, host=None, log=print, timeout=3.0):
    """Client: what the civ dropdown / team button do, without the UI: set the local value and the
    pending request the lobby sends to the host. Verified on the host's side when `host` is given."""
    g = gp.mem.u32(ADDR_GAME)
    scr = gp.mem.u32(ADDR_SCREEN)
    if not g or not scr or current_screen(gp) != "MP Setup Screen":
        return False
    gp.hook.call("thiscall", FN_GAME_SET_CIV, g, slot, civ)
    gp.mem.write(scr + SCR_MY_CIV_PENDING, int(civ).to_bytes(4, "little"))
    gp.hook.call("thiscall", FN_GAME_SET_TEAM, g, slot, team + 1)
    gp.mem.write(scr + SCR_MY_TEAM_PENDING, int(team + 1).to_bytes(4, "little"))
    if host is None:
        return True
    t0 = time.time()
    while time.time() - t0 < timeout:
        if slot_civ(host, slot) == civ and slot_team(host, slot) == team + 1:
            log("slot %d civ=%s team=%s (direct, confirmed by host)" % (
                slot, CIVS[civ - 1] if civ <= len(CIVS) else "Random", team or "-"))
            return True
        time.sleep(0.15)
    log("slot %d direct civ/team not confirmed (host sees civ %s team %s)" % (
        slot, slot_civ(host, slot), slot_team(host, slot)))
    return False


def join_from_list(gp, log=print, retries=8):''')
open(p, "w", encoding="utf-8").write(s)
py_compile.compile(p, doraise=True)

p = r"D:\Game\AoESolo\launcher\orchestrator.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''            locked = False
            if not self.test_hidden_player and self.pool.starting:
                locked = pl.hook.cmd("fglock 1").startswith("ok")   # bots still starting: keep our focus
            try:
                self.bots = self.pool.take(cfg.num_ai)
            finally:
                if locked:
                    pl.hook.cmd("fglock 2")''', '''            # the player's game keeps the foreground for the whole setup (no other window may take it)
            locked = False
            if not self.test_hidden_player:
                gw.focus(pl.hwnd)
                locked = pl.hook.cmd("fglock 1").startswith("ok")
            self.bots = self.pool.take(cfg.num_ai)''')
s = s.replace('''            for i, b in enumerate(self.bots):
                lobby.choose_civ(b, self.slots[b.pid], self._civ(cfg.ai_civs[i]), log=self.log)
                lobby.set_team(b, self.slots[b.pid], 2 if together else 0, log=self.log)
                lobby.ready(b, False)
''', '''            for i, b in enumerate(self.bots):
                civ, team = self._civ(cfg.ai_civs[i]), (2 if together else 0)
                if not lobby.client_set_civ_team(b, self.slots[b.pid], civ, team, host=pl, log=self.log):
                    lobby.choose_civ(b, self.slots[b.pid], civ, log=self.log)      # fallback: hidden UI
                    lobby.set_team(b, self.slots[b.pid], team, log=self.log)
                lobby.ready(b, False)
            if locked:
                pl.hook.cmd("fglock 2")
''')
open(p, "w", encoding="utf-8").write(s)
py_compile.compile(p, doraise=True)
print("ok", "client_set_civ_team" in s, 'fglock 1").startswith' in s)
