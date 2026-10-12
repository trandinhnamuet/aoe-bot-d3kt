import py_compile

p = r"D:\Game\AoESolo\launcher\orchestrator.py"
s = open(p, encoding="utf-8").read()

s = s.replace('''PLAYER_EXE = "EMPIRESX.EXE"
BOT_EXE = "AOEBOT.EXE"
''', '''PLAYER_EXE = "EMPIRESX.EXE"
BOT_EXE = "AOEBOT.EXE"
RESOLUTIONS = {1366: (1366, 768), 1600: (1600, 900), 1920: (1920, 1080)}
_reg_lock = threading.Lock()


class BotPool:
    """Hidden bots started in advance (when the launcher opens), parked on the multiplayer game
    list so that pressing "Choi" only has to open the player's room and let them join."""

    def __init__(self, game_dir, dll, log=print):
        self.game_dir = game_dir
        self.dll = dll
        self.log = log
        self.lock = threading.Lock()
        self.parked = []          # GameProc waiting on "Join Screen"
        self.starting = 0
        self.names_in_use = set()
        self.closed = False

    def _name(self):
        k = 1
        while "AI %d" % k in self.names_in_use:
            k += 1
        self.names_in_use.add("AI %d" % k)
        return "AI %d" % k

    def ensure(self, n):
        with self.lock:
            self.parked = [b for b in self.parked if b.alive()]
            missing = n - len(self.parked) - self.starting
            for _ in range(max(0, missing)):
                self.starting += 1
                threading.Thread(target=self._start_one, daemon=True).start()

    def _start_one(self):
        name = None
        try:
            with _reg_lock:                       # bots always run at 1366x768 (lobby coordinates)
                saved = lobby.reg_get_dword(lobby.REG_SCREEN)
                lobby.reg_set_dword(lobby.REG_SCREEN, 1366)
                try:
                    gp = procs.start(self.game_dir, BOT_EXE, self.dll, True, log=self.log)
                    lobby.wait_screen(gp, "Main Menu", 60)
                finally:
                    if saved is not None:
                        lobby.reg_set_dword(lobby.REG_SCREEN, saved)
            with self.lock:
                name = self._name()
            gp.bot_name = name
            lobby.open_connection(gp, name, self.log)        # parked on the game list
            with self.lock:
                if self.closed:
                    gp.kill()
                else:
                    self.parked.append(gp)
            self.log("bot %s parked (pid %d)" % (name, gp.pid))
        except Exception as e:
            self.log("bot start failed: %r" % (e,))
            if name:
                with self.lock:
                    self.names_in_use.discard(name)
        finally:
            with self.lock:
                self.starting -= 1

    def take(self, n, timeout=90):
        self.ensure(n)
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                self.parked = [b for b in self.parked if b.alive()]
                if len(self.parked) >= n:
                    got, self.parked = self.parked[:n], self.parked[n:]
                    return got
                short = n - len(self.parked) - self.starting
            if short > 0:
                self.ensure(n)
            time.sleep(0.2)
        raise RuntimeError("bots were not ready in time")

    def release_names(self, bots):
        with self.lock:
            for b in bots:
                self.names_in_use.discard(getattr(b, "bot_name", None))

    def shutdown(self):
        with self.lock:
            self.closed = True
            for b in self.parked:
                b.kill()
            self.parked = []
''')

s = s.replace('''        self.ai_team_mode = "together"  # "together": player vs all AIs, "ffa": everyone alone''',
              '''        self.ai_team_mode = "together"  # "together": player vs all AIs, "ffa": everyone alone
        self.resolution = 1366          # the player's game resolution (Screen Size)''')

s = s.replace('''    def __init__(self, base_dir, cfg, log=print, status=lambda s: None, dll=None, dplaunch=None):''',
              '''    def __init__(self, base_dir, cfg, log=print, status=lambda s: None, dll=None, dplaunch=None, pool=None):
        self.pool = pool''')

start = s.index('    def run(self):')
end = s.index('    def _start_player_room(self):')
new = '''    def run(self):
        """Player hosts (visible, straight into the room), pre-started hidden bots join as players 2..N.
        Returns once the room is ready; the player presses Start Game."""
        cfg = self.cfg
        t0 = time.time()
        self.ensure_bot_exe()
        if self.pool is None:
            self.pool = BotPool(self.game_dir, self.dll, self.log)
        self.pool.ensure(cfg.num_ai)                  # normally already parked since the launcher opened
        lobby.write_settings(self.game_dir, map_size=cfg.map_size, map_type=cfg.map_type, age=cfg.age,
                             resources=cfg.resources, pop_limit=cfg.pop_limit, reveal_map=cfg.reveal_map)
        lobby.reg_set(lobby.REG_SERVICE, "Internet TCP/IP Connection For DirectPlay")
        self.saved_name = lobby.reg_get(lobby.REG_NAME)
        self.saved_screen = None
        try:
            # 1. the player's game opens straight in the hosted room
            self.status("\\u0110ang m\\u1edf ph\\u00f2ng ch\\u1edd...")
            with _reg_lock:
                lobby.reg_set_dword(lobby.REG_SCREEN, cfg.resolution)
                if self.test_hidden_player:
                    pl = procs.start(self.game_dir, BOT_EXE, self.dll, True, log=self.log)
                    lobby.host_create(pl, log=self.log)
                else:
                    pl = self._start_player_room()
            self.player = pl
            w, h = RESOLUTIONS.get(cfg.resolution, (1366, 768))
            pl.sx, pl.sy = w / 1366.0, h / 768.0
            # 2. parked bots join together (no new window is created while the player's game is up)
            self.status("C\\u00e1c m\\u00e1y \\u0111ang v\\u00e0o ph\\u00f2ng...")
            self.bots = self.pool.take(cfg.num_ai)
            errors = []

            def join(b):
                try:
                    lobby.join_from_list(b, log=self.log)
                except Exception as e:
                    errors.append(e)
            ths = [threading.Thread(target=join, args=(b,)) for b in self.bots]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
            if errors:
                raise errors[0]
            # 3. civilisations, teams, ready
            self.slots = {gp.pid: lobby.my_player_number(gp) - 1 for gp in self.bots + [pl]}
            together = cfg.ai_team_mode == "together"

            def setup(i, b):
                try:
                    lobby.choose_civ(b, self.slots[b.pid], self._civ(cfg.ai_civs[i]), log=self.log)
                    lobby.set_team(b, self.slots[b.pid], 2 if together else 0, log=self.log)
                    lobby.ready(b, False)
                except Exception as e:
                    errors.append(e)
            ths = [threading.Thread(target=setup, args=(i, b)) for i, b in enumerate(self.bots)]
            for th in ths:
                th.start()
            lobby.host_set_civ(pl, self.slots[pl.pid], self._civ(cfg.player_civ), log=self.log)
            lobby.host_set_team(pl, self.slots[pl.pid], 1 if together else 0, log=self.log)
            for th in ths:
                th.join()
            if errors:
                raise errors[0]
            lobby.ready(pl, True)
        except Exception:
            self.restore_settings()
            self.shutdown()
            if self.player:
                self.player.kill()
            raise
        self.restore_settings()
        # 4. hand the game over to the player (one focus, no window juggling)
        if not self.test_hidden_player:
            pl.hook.cmd("vin 0")
            pl.hook.cmd("autodlg -")
            gw.focus(pl.hwnd)
        self.log("room ready in %.1f s" % (time.time() - t0))
        self.status("Ph\\u00f2ng \\u0111\\u00e3 s\\u1eb5n s\\u00e0ng - b\\u1ea5m Start Game trong game \\u0111\\u1ec3 b\\u1eaft \\u0111\\u1ea7u")

'''
s = s[:start] + new + s[end:]

s = s.replace('''                pl = procs.attach(ps, self.dll, log=self.log)
                lobby.detect_scale(pl, log=self.log)
                if lobby.wait_screen(pl, "MP Setup Screen", 40):''', '''                pl = procs.attach(ps, self.dll, log=self.log)
                if lobby.wait_screen(pl, "MP Setup Screen", 40):''')
s = s.replace('''        pl = procs.start(self.game_dir, PLAYER_EXE, self.dll, False, log=self.log)
        lobby.detect_scale(pl, log=self.log)
        lobby.host_create(pl, log=self.log)
        return pl''', '''        pl = procs.start(self.game_dir, PLAYER_EXE, self.dll, False, log=self.log)
        w, h = RESOLUTIONS.get(self.cfg.resolution, (1366, 768))
        pl.sx, pl.sy = w / 1366.0, h / 768.0
        lobby.host_create(pl, log=self.log)
        return pl''')
s = s.replace('''    def shutdown(self):
        self.stop_flag = True
        self.restore_settings()
        for b in self.bots:
            b.kill()
        self.bots = []''', '''    def shutdown(self):
        self.stop_flag = True
        self.restore_settings()
        for b in self.bots:
            b.kill()
        if self.pool:
            self.pool.release_names(self.bots)
        self.bots = []''')
open(p, "w", encoding="utf-8").write(s)
py_compile.compile(p, doraise=True)
print("ok", "BotPool" in s, "host_set_civ" in s, "detect_scale" in s)
