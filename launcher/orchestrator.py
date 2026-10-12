"""Sets up a multiplayer match: hidden bot host + hidden bot clients + the visible player game."""
import os
import random
import threading
import time

import aoemem
import d3kt
import gamewin as gw
import lobby
import procs

PLAYER_EXE = "EMPIRESX.EXE"
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
            lobby.fast_session_list(gp)
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


class Config:
    def __init__(self):
        self.num_ai = 1
        self.map_type = "Hill Country"
        self.map_size = "Large"
        self.age = "Default"
        self.resources = "Default"
        self.pop_limit = 200
        self.reveal_map = False
        self.player_civ = 0            # 0 = random, 1..16
        self.ai_civs = [0] * 7
        self.ai_team_mode = "together"  # "together": player vs all AIs, "ffa": everyone alone
        self.resolution = 1366          # the player's game resolution (Screen Size)
        self.player_name = ""           # the player's in-game name (empty = whatever the game remembers)


class Session:
    def __init__(self, base_dir, cfg, log=print, status=lambda s: None, dll=None, dplaunch=None, pool=None):
        self.pool = pool
        self.dplaunch = dplaunch or os.path.join(base_dir, "bin", "dplaunch.exe")
        self.base = base_dir
        self.game_dir = os.path.join(base_dir, "AoE-HD")
        self.dll = dll or os.path.join(base_dir, "bin", "aoehook.dll")
        self.cfg = cfg
        self.log = log
        self.status = status
        self.bots = []          # GameProc
        self.player = None      # GameProc
        self.threads = []
        self.stop_flag = False
        self.test_hidden_player = False   # testing only: run the "player" as another hidden instance

    # ------------------------------------------------------------------
    def _try_join(self, b, retries=1):
        try:
            lobby.join_from_list(b, log=self.log, retries=retries)
        except Exception as e:
            self.log("%s join: %r" % (getattr(b, "bot_name", "bot"), e))

    @staticmethod
    def _host_sees(pl, b):
        if lobby.current_screen(b) != "MP Setup Screen":
            return False
        n = lobby.my_player_number(b)
        st = lobby.session_states(pl)
        return bool(n) and 1 <= n <= len(st) and st[n - 1] in (2, 5)

    def _civ(self, c):
        return c if c else lobby.CIV_RANDOM          # "Random" in the lobby: the game rolls the civ itself

    def ensure_bot_exe(self):
        src = os.path.join(self.game_dir, PLAYER_EXE)
        dst = os.path.join(self.game_dir, BOT_EXE)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            import shutil
            shutil.copyfile(src, dst)

    def run(self):
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
        if getattr(cfg, "player_name", ""):
            lobby.reg_set(lobby.REG_NAME, cfg.player_name)   # the game reads its player name from here
            self.saved_name = cfg.player_name
        self.saved_screen = None
        try:
            # 1. the player's game opens straight in the hosted room
            self.status("\u0110ang m\u1edf ph\u00f2ng ch\u1edd...")
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
            self.status("C\u00e1c m\u00e1y \u0111ang v\u00e0o ph\u00f2ng...")
            # the player's game keeps the foreground for the whole setup (no other window may take it)
            locked = False
            if not self.test_hidden_player:
                gw.focus(pl.hwnd)
                locked = pl.hook.cmd("fglock 1").startswith("ok")
            self.bots = self.pool.take(cfg.num_ai)
            # all bots join at once (short EnumSessions timeout): the host takes simultaneous joins in
            # ~2 s, one by one it needs ~2 s each. Any bot the HOST does not list afterwards is retried.
            ths = [threading.Thread(target=self._try_join, args=(b,), daemon=True) for b in self.bots]
            for th in ths:
                th.start()
            for th in ths:
                th.join(15)
            t1 = time.time()
            while time.time() - t1 < 3 and lobby.present_players(pl) < 1 + sum(
                    lobby.current_screen(b) == "MP Setup Screen" for b in self.bots):
                time.sleep(0.05)
            for i in range(len(self.bots)):
                for attempt in range(4):
                    b = self.bots[i]
                    if self._host_sees(pl, b):
                        break
                    self.log("host does not see %s (states %s), attempt %d" % (
                        getattr(b, "bot_name", "bot"), lobby.session_states(pl), attempt + 1))
                    try:
                        self.log("  bot screen %s, popups %s, bot states %s, my number %s" % (
                            lobby.current_screen(b), lobby.open_popups(b), lobby.session_states(b),
                            lobby.my_player_number(b)))
                        if attempt == 0:
                            for vk in (13,):                           # Enter closes a game popup (Esc = Cancel)
                                b.hook.tap(vk)
                                time.sleep(0.2)
                            self.log("  after Enter: screen %s, popups %s" % (
                                lobby.current_screen(b), lobby.open_popups(b)))
                    except Exception as e:
                        self.log("  diag: %r" % (e,))
                    if attempt in (1, 3):
                        # a bot that ignores the game list (seen rarely, even Cancel does nothing): swap it
                        self.log("replacing %s" % getattr(b, "bot_name", "bot"))
                        b.kill()
                        self.pool.release_names([b])
                        b = self.bots[i] = self.pool.take(1)[0]
                    elif attempt == 2:
                        try:
                            lobby.reopen_list(b, log=self.log)     # fresh DirectPlay session, then join again
                        except Exception as e:
                            self.log("%s reopen: %r" % (getattr(b, "bot_name", "bot"), e))
                    self._try_join(b, retries=1 if attempt == 0 else 2)
                    t1 = time.time()
                    while (not self._host_sees(pl, b) and time.time() - t1 < 3
                           and lobby.current_screen(b) == "MP Setup Screen"):
                        time.sleep(0.05)
                if not self._host_sees(pl, self.bots[i]):
                    raise RuntimeError("the room never saw %s" % getattr(self.bots[i], "bot_name", "a bot"))
            # 3. civilisations, teams, ready ("AI k" in the room gets the launcher's AI k civ, whatever seat)
            self.slots = {gp.pid: lobby.my_player_number(gp) - 1 for gp in self.bots + [pl]}
            self.bots.sort(key=lambda b: (len(getattr(b, "bot_name", "")), getattr(b, "bot_name", "")))
            together = cfg.ai_team_mode == "together"
            lobby.host_set_civ(pl, self.slots[pl.pid], self._civ(cfg.player_civ), log=self.log)
            lobby.host_set_team(pl, self.slots[pl.pid], 1 if together else 0, log=self.log)

            def civ_team(b, civ, team):
                if not lobby.client_set_civ_team(b, self.slots[b.pid], civ, team, host=pl, log=self.log):
                    lobby.ready(b, False)                                          # un-ready, then the UI way
                    lobby.choose_civ(b, self.slots[b.pid], civ, log=self.log)
                    lobby.set_team(b, self.slots[b.pid], team, log=self.log)
                    lobby.ready(b, False)
            ths = [threading.Thread(target=civ_team, daemon=True,
                                    args=(b, self._civ(cfg.ai_civs[i]), 2 if together else 0))
                   for i, b in enumerate(self.bots)]
            for th in ths:
                th.start()
            for th in ths:
                th.join(30)
            if locked:
                pl.hook.cmd("fglock 2")
            lobby._click(pl, lobby.LOBBY_READY_HOST, 0.2)     # the click returns once the game handled it
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
        self.status("Ph\u00f2ng \u0111\u00e3 s\u1eb5n s\u00e0ng - b\u1ea5m Start Game trong game \u0111\u1ec3 b\u1eaft \u0111\u1ea7u")

    def _start_player_room(self):
        """Open the player's game straight in the hosted room (DirectPlay Lobby, like XArena).
        Falls back to driving the menus if the lobby launch is not available."""
        import dplobby
        name = self.saved_name or "Player"
        try:
            if not dplobby.is_registered(self.game_dir):
                self.status("Cần quyền Administrator một lần để vào thẳng phòng chờ...")
                dplobby.register(self.game_dir, log=self.log)
            if dplobby.is_registered(self.game_dir) and os.path.exists(self.dplaunch):
                ps, _helper = dplobby.launch_host(self.dplaunch, self.game_dir, name, "AoESolo", log=self.log)
                pl = procs.attach(ps, self.dll, log=self.log)
                if lobby.wait_screen(pl, "MP Setup Screen", 40):
                    self.log("player room opened through DirectPlay Lobby")
                    return pl
                self.log("lobby launch did not reach the room (screen=%s), using the menus" % lobby.current_screen(pl))
                pl.kill()
        except Exception as e:
            self.log("lobby launch failed: %r -> using the menus" % (e,))
        pl = procs.start(self.game_dir, PLAYER_EXE, self.dll, False, log=self.log)
        w, h = RESOLUTIONS.get(self.cfg.resolution, (1366, 768))
        pl.sx, pl.sy = w / 1366.0, h / 768.0
        lobby.host_create(pl, log=self.log)
        return pl

    def restore_settings(self):
        if getattr(self, "saved_name", None):
            lobby.reg_set(lobby.REG_NAME, self.saved_name)
        if getattr(self, "saved_screen", None) is not None:
            lobby.reg_set_dword(lobby.REG_SCREEN, self.saved_screen)

    def reready_bots(self):
        """Bots that lost their ready mark (e.g. the host changed settings) click 'I'm Ready' again."""
        n = 0
        for b in self.bots:
            if lobby.current_screen(b) != "MP Setup Screen":
                continue
            comm = b.mem.u32(lobby.ADDR_COMM)
            if comm and not b.mem.u32(comm + 0x84):
                lobby.ready(b, False)
                n += 1
        self.log("re-ready: %d bot(s) clicked ready" % n)
        return n

    def wait_and_play(self, poll=0.2):
        """Block until the match starts (then run the bots) or the player's game closes."""
        while self.player_alive() and not self.stop_flag:
            if lobby.in_match(self.player):
                self.log("match started by the player")
                t0 = time.time()                 # bots start the moment their own world is up
                while time.time() - t0 < 5 and not all(lobby.in_match(b) for b in self.bots):
                    time.sleep(0.1)
                self.start_bots(self.slots)
                self.status("Đang chơi")
                return True
            time.sleep(poll)
        return False

    debug_dir = None

    def debug_shot(self, tag):
        if self.debug_dir and self.player and not self.test_hidden_player:
            try:
                gw.screenshot(self.player.hwnd, os.path.join(self.debug_dir, "orch_%s.png" % tag))
            except Exception:
                pass

    def start_bots(self, slots):
        cfg = self.cfg
        numbers = {}
        for gp in self.bots + [self.player]:
            numbers[gp.pid] = lobby.my_player_number(gp)
        player_no = numbers[self.player.pid]
        bot_nos = [numbers[b.pid] for b in self.bots]
        for b in self.bots:
            me = numbers[b.pid]
            if cfg.ai_team_mode == "together":
                enemies = [player_no]
            else:
                enemies = [x for x in bot_nos + [player_no] if x != me]
            g = aoemem.Game(b.mem, b.hook)
            th = threading.Thread(target=self._bot_thread, args=(g, me, enemies), daemon=True)
            th.start()
            self.threads.append(th)
        mon = threading.Thread(target=self._resign_monitor, args=(numbers, player_no), daemon=True)
        mon.start()

    RESIGN_RATIO = 3.0 / 7.0      # AIs together below 3:7 of the player's villagers + army -> resign (the user
    RESIGN_AFTER = 300.0          # keeps this rule: an AI that far behind has lost; never in the first 5 min)

    def _resign_monitor(self, numbers, player_no):
        bot_nos = {numbers[b.pid]: b for b in self.bots}
        g = aoemem.Game(self.bots[0].mem, self.bots[0].hook)
        while not self.stop_flag and self.player_alive():
            time.sleep(10)
            try:
                if not g.in_game():
                    return
                t = (g.m.u32(g.world() + 4) or 0) / 1000.0
                counts = {}
                for u in g.units():
                    if u.kind != 70 or u.owner <= 0 or u.hp <= 0 or "Artifact" in u.name:
                        continue
                    counts[u.owner] = counts.get(u.owner, 0) + 1
                ai = sum(counts.get(n, 0) for n in bot_nos)
                pl = counts.get(player_no, 0)
                if t < self.RESIGN_AFTER or pl == 0:
                    continue
                if ai < pl * self.RESIGN_RATIO:
                    self.log("AIs resign: %d villagers+army vs player's %d (below 3:7) at %.0fs" % (ai, pl, t))
                    for n, b in bot_nos.items():
                        try:
                            bg = aoemem.Game(b.mem, b.hook)
                            bg.resign(n, lobby.my_player_number(b) or n)
                        except Exception as e:
                            self.log("resign failed for AI %d: %r" % (n, e))
                    self.status("Các AI đã đầu hàng")
                    self.stop_bots = True
                    return
            except Exception as e:
                self.log("resign monitor: %r" % (e,))

    def _bot_thread(self, g, me, enemies):
        try:
            d3kt.run(g, me, enemies, log=self.log, stop=lambda: self.stop_flag or getattr(self, "stop_bots", False),
                     pop_limit=self.cfg.pop_limit)
        except Exception as e:
            self.log("bot %d stopped: %r" % (me, e))

    def player_alive(self):
        return self.player is not None and self.player.alive()

    def shutdown(self):
        self.stop_flag = True
        self.restore_settings()
        for b in self.bots:
            b.kill()
        if self.pool:
            self.pool.release_names(self.bots)
        self.bots = []
