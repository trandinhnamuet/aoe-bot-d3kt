import py_compile

p = r"D:\Game\AoESolo\launcher\orchestrator.py"
s = open(p, encoding="utf-8").read()
old_start = s.index("            errors = []\n\n            def join(b):")
old_end = s.index("            lobby.ready(pl, True)\n        except Exception:")
new = '''            # one bot at a time, each confirmed by the HOST's own player list (simultaneous joins get lost)
            for k, b in enumerate(self.bots):
                for attempt in range(3):
                    lobby.join_from_list(b, log=self.log)
                    t1 = time.time()
                    while lobby.present_players(pl) < k + 2 and time.time() - t1 < 4:
                        time.sleep(0.2)
                    if lobby.present_players(pl) >= k + 2:
                        break
                    self.log("host does not see %s yet (states %s), rejoining" % (
                        getattr(b, "bot_name", "bot"), lobby.session_states(pl)))
                    lobby._click(b, (1055, 728), 1.5)          # Cancel -> back to the game list
                    lobby.wait_screen(b, "Join Screen", 5)
                else:
                    raise RuntimeError("the room never saw %s" % getattr(b, "bot_name", "a bot"))
            # 3. civilisations, teams, ready
            self.slots = {gp.pid: lobby.my_player_number(gp) - 1 for gp in self.bots + [pl]}
            together = cfg.ai_team_mode == "together"
            lobby.host_set_civ(pl, self.slots[pl.pid], self._civ(cfg.player_civ), log=self.log)
            lobby.host_set_team(pl, self.slots[pl.pid], 1 if together else 0, log=self.log)
            time.sleep(0.5)
            for i, b in enumerate(self.bots):
                lobby.choose_civ(b, self.slots[b.pid], self._civ(cfg.ai_civs[i]), log=self.log)
                lobby.set_team(b, self.slots[b.pid], 2 if together else 0, log=self.log)
                lobby.ready(b, False)
'''
s = s[:old_start] + new + s[old_end:]
open(p, "w", encoding="utf-8").write(s)
py_compile.compile(p, doraise=True)
print("ok", "present_players(pl)" in s)
