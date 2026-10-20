"""AoE Solo vs AI (D3KT) launcher window: a match room (your seat + up to 7 AI seats, civs, teams), the match
settings, one button. Look: launcher/ui_theme.py."""
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import gamedir
import lobby
import orchestrator
import ui_theme as T
import updater
from version import VERSION

APP_TITLE = "AoE Solo vs AI — D3KT"
CIV_CHOICES = ["Ngẫu nhiên"] + lobby.CIVS
TEAM_CHOICES = ["—", "1", "2", "3", "4"]
RESOLUTIONS = ["1366x768", "1600x900", "1920x1080"]
MAX_AI = 7
W, H = 1060, 700


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel):
    root = getattr(sys, "_MEIPASS", None) or base_dir()
    return os.path.join(root, rel)


SETTINGS = os.path.join(base_dir(), "launcher_settings.json")


class Seat:
    """One row of the room: colour, name, civ, team (+ remove for an AI)."""

    def __init__(self, app, parent, index):
        self.app, self.index = app, index
        self.kind = "you" if index == 0 else "empty"          # you | ai | empty
        self.civ = tk.StringVar(value=CIV_CHOICES[0])
        self.team = tk.StringVar(value="—")
        self.card = T.Card(parent, pad=8)
        self.card.pack(fill="x", pady=3)
        self.card.columnconfigure(2, minsize=190, weight=1)   # (name column: civ / team line up across the seats)
        self.swatch = tk.Canvas(self.card, width=16, height=16, bg=T.BG2, highlightthickness=0)
        self.swatch.create_oval(1, 1, 15, 15, fill=T.PLAYER_COLOURS[index], outline="")
        self.swatch.grid(row=0, column=0, padx=(2, 10))
        self.num = T.label(self.card, "%d" % (index + 1), muted=True)
        self.num.grid(row=0, column=1, padx=(0, 10))
        self.name_var = tk.StringVar()
        self.name_lbl = T.label(self.card, "", font=T.FONT_B)
        self.name_entry = tk.Entry(self.card, textvariable=self.name_var, bg=T.BG3, fg=T.TEXT, insertbackground=T.TEXT,
                                   relief="flat", font=T.FONT, width=18, highlightthickness=1,
                                   highlightbackground=T.LINE, highlightcolor=T.GOLD)
        self.civ_box = T.field(self.card, self.civ, CIV_CHOICES, width=15, on_change=app.autosave)
        self.team_lbl = T.label(self.card, "Phe", muted=True)
        self.team_box = T.field(self.card, self.team, TEAM_CHOICES, width=3, on_change=app.autosave)
        self.remove = T.Button(self.card, "✕", kind="tiny", command=lambda: app.remove_ai(self))
        self.add = T.Button(self.card, "+  Thêm AI", kind="ghost", command=app.add_ai)
        self.hint = T.label(self.card, "ghế trống", muted=True)
        # (rendered by App.refresh_seats once every seat exists)

    def render(self):
        for w in (self.name_lbl, self.name_entry, self.civ_box, self.team_lbl, self.team_box, self.remove, self.add, self.hint):
            w.grid_remove()
        if self.kind == "you":
            self.card.set_edge(T.GREEN)
            self.name_entry.grid(row=0, column=2, sticky="w")
            self.civ_box.grid(row=0, column=3, padx=(10, 0))
            self.team_lbl.grid(row=0, column=4, padx=(14, 4))
            self.team_box.grid(row=0, column=5)
            self.num.configure(fg=T.GREEN)
        elif self.kind == "ai":
            self.card.set_edge(T.GOLD)
            self.name_lbl.configure(text="AI %d" % self.index, fg=T.GOLD2)
            self.name_lbl.grid(row=0, column=2, sticky="w")
            self.civ_box.grid(row=0, column=3, padx=(10, 0))
            self.team_lbl.grid(row=0, column=4, padx=(14, 4))
            self.team_box.grid(row=0, column=5)
            self.remove.grid(row=0, column=6, padx=(14, 0))
            self.num.configure(fg=T.GOLD)
        else:
            self.card.set_edge(T.LINE)
            self.num.configure(fg=T.MUTED)
            first_empty = self.app.first_empty() is self
            (self.add if first_empty else self.hint).grid(row=0, column=2, sticky="w")
        self.swatch.itemconfigure("all", fill=T.PLAYER_COLOURS[self.index] if self.kind != "empty" else T.GREY)


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.configure(bg=T.BG)
        root.geometry("%dx%d" % (W, H))
        root.resizable(False, False)
        T.style(root)
        try:
            self._icon = T.app_icon()
            root.iconphoto(True, self._icon)
        except Exception:  # noqa: BLE001
            pass
        self.q = queue.Queue()
        self.session = None
        self.pool = None
        self.playing = False
        self.logfile = open(os.path.join(base_dir(), "aoesolo.log"), "a", encoding="utf-8")
        self.saved = self._load_settings()

        self._bg = T.backdrop(W, H)
        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, bd=0)
        self.canvas.place(x=0, y=0)
        self.canvas.create_image(0, 0, image=self._bg, anchor="nw")
        self.build_header()
        self.build_room()
        self.build_settings()
        self.build_footer()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Return>", lambda e: self.play())
        root.after(200, self.pump)
        if updater.running_exe():
            # (the previous exe may still be closing for a few seconds after an update: a few tries)
            for delay in (0, 3000, 8000, 20000):
                root.after(delay, lambda: updater.cleanup_old(updater.running_exe()))
        threading.Thread(target=self._check_update, daemon=True).start()
        self.game_dir = self.editions.get(self.edition.get()) or gamedir.find(base_dir(), deep=False)
        if os.environ.get("AOESOLO_UI_PREVIEW"):
            # (screenshots of the window off screen, no bots started: the look is checked without a game)
            root.geometry("%dx%d%s" % (W, H, os.environ["AOESOLO_UI_PREVIEW"]))
            self.game_dir_var.set(self.game_dir or "(xem trước)")
            self._apply_status("Sẵn sàng", T.GREEN)
            return
        if self.game_dir:
            root.after(300, lambda: self.use_game_dir(self.game_dir))
        else:
            self.game_dir_var.set("(đang tìm...)")
            threading.Thread(target=self._deep_find, daemon=True).start()

    # ---------------------------------------------------------------- layout
    def build_header(self):
        c = self.canvas
        c.create_text(W // 2, 38, text="AoE Solo vs AI", fill=T.GOLD2, font=T.FONT_TITLE)
        c.create_line(W // 2 - 190, 66, W // 2 - 60, 66, fill=T.GOLD)
        c.create_text(W // 2, 66, text="LUẬT D3KT", fill=T.GOLD, font=("Segoe UI", 9, "bold"))
        c.create_line(W // 2 + 60, 66, W // 2 + 190, 66, fill=T.GOLD)
        c.create_text(W // 2, 86, text="Đời 3 không thành · bot chơi như người theo luật của bạn", fill=T.MUTED, font=T.FONT_S)
        c.create_text(W - 24, 22, text="bản " + VERSION, fill=T.MUTED, font=T.FONT_S, anchor="ne")

    def build_room(self):
        self.room = T.Card(self.root, pad=12)
        self.room.place(x=20, y=108, width=640, height=470)
        head = tk.Frame(self.room, bg=T.BG2)
        head.pack(fill="x")
        tk.Label(head, text="Phòng chờ", bg=T.BG2, fg=T.GOLD, font=T.FONT_H).pack(side="left")
        self.count_lbl = T.label(head, "", muted=True)
        self.count_lbl.pack(side="left", padx=(10, 0))
        T.Button(head, "Mỗi người một phe", kind="ghost", command=lambda: self.preset("ffa")).pack(side="right", padx=(6, 0))
        T.Button(head, "Các AI cùng phe", kind="ghost", command=lambda: self.preset("together")).pack(side="right")
        # the quick bot count (the user, 20/10: 1v7 took seven clicks): 1..7 buttons, the chosen one gold
        row2 = tk.Frame(self.room, bg=T.BG2)
        row2.pack(fill="x", pady=(8, 0))
        T.label(row2, "Số AI", muted=True).pack(side="left", padx=(0, 8))
        self.count_btns = []
        for n in range(1, MAX_AI + 1):
            b = T.Button(row2, " %d " % n, kind="ghost", command=lambda n=n: self.set_ai_count(n))
            b.pack(side="left", padx=2)
            self.count_btns.append(b)
        self.size_note = T.label(row2, "", muted=True)
        self.size_note.pack(side="left", padx=(14, 0))
        tk.Frame(self.room, bg=T.LINE, height=1).pack(fill="x", pady=(8, 6))
        seats = tk.Frame(self.room, bg=T.BG2)
        seats.pack(fill="both", expand=True)
        self.seats = [Seat(self, seats, i) for i in range(MAX_AI + 1)]
        you = self.seats[0]
        try:
            you.name_var.set(self.saved.get("name") or lobby.reg_get(lobby.REG_NAME) or "")
        except Exception:  # noqa: BLE001
            you.name_var.set(self.saved.get("name", ""))
        you.name_entry.bind("<FocusOut>", lambda e: self.autosave())
        you.civ.set(self.saved.get("civ", CIV_CHOICES[0]) if self.saved.get("civ") in CIV_CHOICES else CIV_CHOICES[0])
        you.team.set(self.saved.get("team", "1"))
        ais = self.saved.get("ais") or [{"civ": CIV_CHOICES[0], "team": "2"}]
        for i, a in enumerate(ais[:MAX_AI]):
            s = self.seats[i + 1]
            s.kind = "ai"
            s.civ.set(a.get("civ") if a.get("civ") in CIV_CHOICES else CIV_CHOICES[0])
            s.team.set(a.get("team") if a.get("team") in TEAM_CHOICES else "—")
        self.refresh_seats()

    def build_settings(self):
        sv = self.saved
        card = T.Card(self.root, title="Cài đặt trận", pad=12)
        card.place(x=676, y=108, width=364, height=300)
        grid = tk.Frame(card, bg=T.BG2)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        def row(r, text, var, values, key):
            T.label(grid, text, muted=True).grid(row=r, column=0, sticky="w", pady=4)
            var.set(sv.get(key, var.get()) if sv.get(key) in values else var.get())
            T.field(grid, var, values, width=18, on_change=self.autosave).grid(row=r, column=1, sticky="e", pady=4)
        self.map_type = tk.StringVar(value="Hill Country")
        self.map_size = tk.StringVar(value="Large")
        self.resources = tk.StringVar(value="Default")
        self.pop = tk.StringVar(value="200")
        self.victory = tk.StringVar(value="Conquest")
        self.resolution = tk.StringVar(value="1366x768")
        row(0, "Bản đồ", self.map_type, lobby.MAP_TYPES, "map_type")
        row(1, "Kích thước", self.map_size, lobby.MAP_SIZES, "map_size")
        row(2, "Tài nguyên", self.resources, list(lobby.RESOURCES), "resources")
        row(3, "Dân số tối đa", self.pop, [str(p) for p in lobby.POP_LIMITS], "pop")
        row(4, "Điều kiện thắng", self.victory, lobby.VICTORIES, "victory")
        row(5, "Độ phân giải", self.resolution, RESOLUTIONS, "resolution")
        self._last_n = None
        self.refresh_seats()                              # (the map size for the saved seat count)

        game = T.Card(self.root, title="Bản game", pad=12)
        game.place(x=676, y=420, width=364, height=158)
        g = tk.Frame(game, bg=T.BG2)
        g.pack(fill="x")
        g.columnconfigure(1, weight=1)
        self.editions = gamedir.find_editions(base_dir(), deep=False)
        first = gamedir.remembered_edition()
        if first not in self.editions:
            first = next((e for e in gamedir.EDITIONS if e in self.editions), gamedir.HD)
        self.edition = tk.StringVar(value=first)
        T.label(g, "Bản", muted=True).grid(row=0, column=0, sticky="w", pady=4)
        T.field(g, self.edition, gamedir.EDITIONS, width=18, on_change=self.on_edition).grid(row=0, column=1, sticky="e", pady=4)
        T.label(g, "Thư mục", muted=True).grid(row=1, column=0, sticky="nw", pady=4)
        self.game_dir_var = tk.StringVar(value="")
        T.label(g, "", muted=True, textvariable=self.game_dir_var, wraplength=250, justify="left",
                anchor="w").grid(row=1, column=1, sticky="w", pady=4)
        T.Button(g, "Chọn thư mục...", kind="ghost", command=self.choose_game_dir).grid(row=2, column=1, sticky="e", pady=(4, 0))

    def build_footer(self):
        bar = tk.Frame(self.root, bg=T.BG2, highlightthickness=1, highlightbackground=T.LINE)
        bar.place(x=20, y=592, width=1020, height=88)
        self.dot = tk.Canvas(bar, width=12, height=12, bg=T.BG2, highlightthickness=0)
        self.dot.create_oval(1, 1, 11, 11, fill=T.MUTED, outline="", tags="d")
        self.dot.place(x=16, y=16)
        self.status = tk.StringVar(value="Sẵn sàng")
        tk.Label(bar, textvariable=self.status, bg=T.BG2, fg=T.TEXT, font=T.FONT_B, anchor="w").place(x=36, y=10, width=600)
        self.sub = tk.StringVar(value="Bot ẩn được chuẩn bị sẵn trong lúc bạn chọn cài đặt.")
        self.sub_lbl = tk.Label(bar, textvariable=self.sub, bg=T.BG2, fg=T.MUTED, font=T.FONT_S, anchor="w")
        self.sub_lbl.place(x=36, y=34, width=600)
        self.log_btn = T.Button(bar, "Nhật ký ▸", kind="tiny", command=self.toggle_log)
        self.log_btn.place(x=36, y=58)
        self.ready_btn = T.Button(bar, "Bot sẵn sàng lại", kind="ghost", command=self.reready)
        self.ready_btn.place(x=668, y=24)
        self.update_btn = T.Button(bar, "", kind="gold", command=self.do_update)   # shown when a newer release exists
        self.update = None
        self.play_btn = T.Button(bar, "VÀO TRẬN", kind="primary", command=self.play)
        self.play_btn.place(x=820, y=18, width=180)
        self.log_box = tk.Text(self.root, bg="#101010", fg=T.MUTED, font=("Consolas", 9), relief="flat", wrap="word",
                               state="disabled", highlightthickness=1, highlightbackground=T.LINE)
        self.log_open = False

    # ---------------------------------------------------------------- the room
    def active_ai(self):
        return [s for s in self.seats[1:] if s.kind == "ai"]

    def first_empty(self):
        return next((s for s in self.seats[1:] if s.kind == "empty"), None)

    @staticmethod
    def size_for(players):
        """The user (20/10): up to 4 players Large, 5-7 Huge, 8 Gigantic."""
        return "Large" if players <= 4 else ("Huge" if players <= 7 else "Gigantic")

    def set_ai_count(self, n):
        """n AI seats (1..7), the new ones random civ on the AIs' team; the map size follows the player count."""
        for i, s in enumerate(self.seats[1:]):
            if i < n and s.kind != "ai":
                s.kind = "ai"
                s.civ.set(CIV_CHOICES[0])
                s.team.set("2" if self.seats[0].team.get() in ("1", "—") else "—")
            elif i >= n:
                s.kind = "empty"
        if self.seats[0].team.get() == "—" and all(a.team.get() == "2" for a in self.active_ai()):
            self.seats[0].team.set("1")                   # (default: you against all the AIs together)
        self.refresh_seats()

    def refresh_seats(self):
        for s in self.seats:
            s.render()
        n = len(self.active_ai())
        self.count_lbl.configure(text="bạn + %d AI" % n)
        for i, b in enumerate(self.count_btns):
            on = (i + 1) == n
            b.configure(bg=T.GOLD if on else T.BG3, fg="#1a1a1a" if on else T.TEXT)
            b.look = dict(b.look, bg=T.GOLD if on else T.BG3, fg="#1a1a1a" if on else T.TEXT, hover=T.GOLD2 if on else "#333333")
        if hasattr(self, "map_size"):
            size = self.size_for(1 + n)
            if n != getattr(self, "_last_n", None):
                self.map_size.set(size)                   # (the map size follows the player count; it can still be changed)
                self._last_n = n
            self.size_note.configure(text="%d người chơi → bản đồ %s" % (1 + n, size))
        if self.pool is not None:
            threading.Thread(target=self.pool.ensure, args=(n,), daemon=True).start()
        self.autosave()

    def add_ai(self):
        s = self.first_empty()
        if s is None:
            return
        s.kind = "ai"
        s.civ.set(CIV_CHOICES[0])
        s.team.set("2" if self.seats[0].team.get() == "1" and all(a.team.get() == "2" for a in self.active_ai()) else "—")
        self.refresh_seats()

    def remove_ai(self, seat):
        # keep the AIs packed from seat 2 up: the ones after it move up a seat
        ais = [(a.civ.get(), a.team.get()) for a in self.active_ai() if a is not seat]
        for i, s in enumerate(self.seats[1:]):
            if i < len(ais):
                s.kind = "ai"
                s.civ.set(ais[i][0])
                s.team.set(ais[i][1])
            else:
                s.kind = "empty"
        if not ais:
            self.seats[1].kind = "ai"
            self.seats[1].civ.set(CIV_CHOICES[0])
            self.seats[1].team.set("2")
            self.set_status("Cần ít nhất một AI", T.AMBER)
        self.refresh_seats()

    def preset(self, mode):
        if mode == "together":
            self.seats[0].team.set("1")
            for a in self.active_ai():
                a.team.set("2")
        else:
            for s in [self.seats[0]] + self.active_ai():
                s.team.set("—")
        self.autosave()

    # ---------------------------------------------------------------- settings file
    def _load_settings(self):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def autosave(self):
        try:
            you = self.seats[0]
            data = {"name": you.name_var.get().strip()[:24], "civ": you.civ.get(), "team": you.team.get(),
                    "ais": [{"civ": a.civ.get(), "team": a.team.get()} for a in self.active_ai()],
                    "map_type": self.map_type.get(), "map_size": self.map_size.get(), "resources": self.resources.get(),
                    "pop": self.pop.get(), "victory": self.victory.get(), "resolution": self.resolution.get()}
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except (OSError, AttributeError):
            pass

    # ---------------------------------------------------------------- the game folder
    def on_edition(self):
        e = self.edition.get()
        p = self.editions.get(e)
        if not p:
            self.editions.update(gamedir.find_editions(base_dir(), deep=True))
            p = self.editions.get(e)
        if p:
            self.use_game_dir(p)
        else:
            self.game_dir_var.set("(chưa thấy %s - bấm Chọn thư mục...)" % e)
            self.choose_game_dir()

    def _deep_find(self):
        found = gamedir.find_editions(base_dir(), deep=True)
        self.editions.update(found)
        p = self.editions.get(self.edition.get()) or gamedir.find(base_dir(), deep=True)
        self.root.after(0, lambda: self._found(p))

    def _found(self, p):
        if p:
            self.use_game_dir(p)
        else:
            self.game_dir_var.set("(chưa tìm thấy - bấm Chọn thư mục...)")
            self.set_status("Chưa có thư mục game", T.AMBER)

    def choose_game_dir(self):
        p = filedialog.askdirectory(title="Chọn thư mục game AoE (có EMPIRESX.EXE)", initialdir=self.game_dir or "C:\\")
        if not p:
            return
        p = os.path.normpath(p)
        if not gamedir.has_game(p):
            messagebox.showerror(APP_TITLE, "Thư mục này không có EMPIRESX.EXE.")
            return
        self.use_game_dir(p)

    def use_game_dir(self, p):
        """Take the player's own install; copy it to AoESolo's folder when it cannot be written to."""
        if not gamedir.known_build(p):
            messagebox.showwarning(APP_TITLE, "EMPIRESX.EXE ở thư mục này khác bản AoE HD / AoE thường (AOE1R) "
                                              "mà bot được viết cho. Bot có thể không chạy được.")
        if not gamedir.writable(p):
            if not messagebox.askyesno(APP_TITLE, "Thư mục game không ghi được (cần quyền admin):\n%s\n\n"
                                                  "Chép bản game trên máy này sang thư mục riêng của AoESolo để dùng?\n%s"
                                       % (p, gamedir.local_copy_dir(p))):
                self.game_dir_var.set("(chưa dùng được - bấm Chọn thư mục...)")
                return

            def prog(i, n):
                self.set_status("Đang chép game... %d/%d" % (i, n), T.AMBER)
                self.root.update()
            p = gamedir.copy_local(p, progress=prog)
            self.set_status("Sẵn sàng")
        e = gamedir.edition_of(p) or self.edition.get()
        if e in gamedir.EDITIONS and e != self.edition.get():
            self.edition.set(e)
        self.editions[self.edition.get()] = p
        if self.pool is not None and os.path.normpath(p) != os.path.normpath(self.game_dir or ""):
            old = self.pool
            threading.Thread(target=old.shutdown, daemon=True).start()
        self.game_dir = p
        gamedir.remember(p)
        gamedir.remember_edition(self.edition.get(), p)
        self.game_dir_var.set(p)
        self.log("game folder: %s (%s)" % (p, self.edition.get()))
        self.pool = orchestrator.BotPool(p, resource_path(os.path.join("bin", "aoehook.dll")), log=self.log)
        self.set_status("Sẵn sàng", T.GREEN)
        self.root.after(1500, self.warm_bots)

    def warm_bots(self):
        if self.pool is not None and gamedir.has_game(self.game_dir):
            threading.Thread(target=self.pool.ensure, args=(len(self.active_ai()),), daemon=True).start()

    # ---------------------------------------------------------------- status, log
    def log(self, msg):
        line = time.strftime("%H:%M:%S ") + msg
        try:
            self.logfile.write(line + "\n")
            self.logfile.flush()
        except OSError:
            pass
        self.q.put(("log", line))

    def set_status(self, s, colour=None):
        self.q.put(("status", (s, colour)))

    def _apply_status(self, s, colour):
        self.status.set(s)
        self.dot.itemconfigure("d", fill=colour or T.MUTED)

    def toggle_log(self):
        self.log_open = not self.log_open
        if self.log_open:
            self.root.geometry("%dx%d" % (W, H + 160))
            self.log_box.place(x=20, y=H, width=1020, height=150)
            self.log_btn.configure(text="Nhật ký ▾")
        else:
            self.log_box.place_forget()
            self.root.geometry("%dx%d" % (W, H))
            self.log_btn.configure(text="Nhật ký ▸")

    def _append_log(self, line):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        if int(self.log_box.index("end-1c").split(".")[0]) > 400:
            self.log_box.delete("1.0", "2.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "status":
                    s, colour = val if isinstance(val, tuple) else (val, None)
                    self._apply_status(s, colour or (T.AMBER if self.playing else None))
                elif kind == "log":
                    self._append_log(val)
                elif kind == "update":
                    self._show_update(val)
                elif kind == "quit":
                    # (the frozen onefile exe did not end after destroy(): the parent bootloader kept waiting -
                    #  e2e 20/10; leaving the interpreter outright ends both)
                    def bye():
                        try:
                            self.logfile.close()
                            self.root.destroy()
                        finally:
                            os._exit(0)
                    self.root.after(300, bye)
                    return
                elif kind == "error":
                    self._apply_status("Lỗi: " + val, T.RED)
                    self.playing = False
                    self.play_btn.set_enabled(True)
                    messagebox.showerror(APP_TITLE, val)
                elif kind == "done":
                    self._apply_status(val, T.GREEN)
                    self.playing = False
                    self.play_btn.set_enabled(True)
        except queue.Empty:
            pass
        self.root.after(200, self.pump)

    # ---------------------------------------------------------------- play
    @staticmethod
    def civ_value(name):
        return 0 if name == CIV_CHOICES[0] else lobby.CIVS.index(name) + 1

    @staticmethod
    def team_value(s):
        return 0 if s == "—" else int(s)

    def play(self):
        if self.playing:
            return
        ais = self.active_ai()
        cfg = orchestrator.Config()
        cfg.num_ai = len(ais)
        cfg.map_type = self.map_type.get()
        cfg.map_size = self.map_size.get()
        cfg.pop_limit = int(self.pop.get())
        cfg.resources = self.resources.get()
        cfg.victory = self.victory.get()
        cfg.player_civ = self.civ_value(self.seats[0].civ.get())
        cfg.ai_civs = ([self.civ_value(a.civ.get()) for a in ais] + [0] * MAX_AI)[:MAX_AI]
        teams = [self.team_value(self.seats[0].team.get())] + [self.team_value(a.team.get()) for a in ais]
        cfg.teams = teams if any(teams) else []
        cfg.ai_team_mode = "together" if teams and teams[0] and all(t == teams[1] for t in teams[1:]) else "ffa"
        cfg.resolution = int(self.resolution.get().split("x")[0])
        cfg.player_name = self.seats[0].name_var.get().strip()[:24]
        if not gamedir.has_game(self.game_dir or "") or self.pool is None:
            messagebox.showerror(APP_TITLE, "Chưa có thư mục game AoE (có EMPIRESX.EXE). Bấm \"Chọn thư mục...\" để chọn.")
            return
        self.autosave()
        self.playing = True
        self.play_btn.set_enabled(False)
        self._apply_status("Đang chuẩn bị...", T.AMBER)
        self.sub.set("Game của bạn mở phòng, %d bot ẩn vào theo. Bạn bấm Start Game trong phòng chờ." % len(ais))
        threading.Thread(target=self._run, args=(cfg,), daemon=True).start()

    def _run(self, cfg):
        sess = orchestrator.Session(base_dir(), cfg, log=self.log, status=self.set_status,
                                    dll=resource_path(os.path.join("bin", "aoehook.dll")),
                                    dplaunch=resource_path(os.path.join("bin", "dplaunch.exe")),
                                    pool=self.pool, game_dir=self.game_dir)
        self.session = sess
        try:
            sess.run()
            self.root.after(0, self.root.iconify)
            sess.wait_and_play()
        except Exception as e:  # noqa: BLE001
            self.log("setup failed: %r" % (e,))
            self.q.put(("error", "Không tạo được trận: %s" % e))
            self.root.after(0, self.root.deiconify)
            return
        self.set_status("Đang chơi...", T.GREEN)
        while sess.player_alive():
            time.sleep(1.0)
        sess.shutdown()
        self.root.after(0, self.root.deiconify)
        self.q.put(("done", "Trận đã kết thúc"))
        self.root.after(1000, self.warm_bots)

    # ---------------------------------------------------------------- updates
    def _check_update(self):
        test_url = os.environ.get("AOESOLO_UPDATE_TEST_URL")
        if test_url:
            # (a test of the one-click path with a local zip: file:///...; the update runs by itself after 2 s)
            self.q.put(("update", {"version": "9.9.9", "url": test_url, "notes": "Bản thử", "page": ""}))
            self.root.after(2000, self.do_update)
            return
        try:
            info = updater.check()
        except Exception as e:  # noqa: BLE001
            self.log("update check failed: %r" % (e,))
            return
        if info:
            self.log("update available: %s" % info["version"])
            self.q.put(("update", info))

    def _show_update(self, info):
        self.update = info
        first = next((ln.strip(" -") for ln in info["notes"].splitlines() if ln.strip() and not ln.lower().startswith("bản")), "")
        self.sub.set(("Có bản %s. " % info["version"]) + (first[:70] if first else "Bấm Cập nhật để tải và mở lại."))
        self.update_btn.configure(text="⬆  Cập nhật %s" % info["version"])
        self.update_btn.place(x=500, y=26)
        self.sub_lbl.place_configure(width=455)

    def do_update(self):
        """One click: download the zip, swap the exe, restart. In a dev run (not frozen) only the download is done."""
        if not self.update or self.playing:
            return
        self.update_btn.set_enabled(False)
        info = self.update

        def work():
            try:
                zpath = updater.temp_zip()

                def prog(done, total):
                    pct = (100 * done // total) if total else 0
                    self.set_status("Đang tải bản %s... %d%%" % (info["version"], pct), T.AMBER)
                updater.download(info["url"], zpath, prog)
                exe = updater.running_exe() or os.environ.get("AOESOLO_UPDATE_TARGET")
                if not exe:
                    self.q.put(("done", "Đã tải %s (bản chạy từ mã nguồn: không thay exe)" % zpath))
                    return
                self.set_status("Đang thay file...", T.AMBER)
                if self.pool:
                    self.pool.shutdown()
                updater.swap(zpath, exe)
                self.set_status("Đang mở lại bản %s..." % info["version"], T.GREEN)
                self.log("updated to %s, restarting" % info["version"])
                updater.restart(exe)
                self.q.put(("quit", None))                # (the window is closed on the Tk thread: after() from
                                                          #  this thread never fired - e2e 20/10, the old exe stayed)
            except Exception as e:  # noqa: BLE001
                self.log("update failed: %r" % (e,))
                self.q.put(("error", "Cập nhật không thành công: %s\nBạn có thể tải tay tại %s" % (e, info.get("page", ""))))
                self.root.after(0, lambda: self.update_btn.set_enabled(True))
        threading.Thread(target=work, daemon=True).start()

    def reready(self):
        sess = self.session
        if sess and sess.bots:
            self.set_status("Bot sẵn sàng lại...", T.AMBER)
            threading.Thread(target=sess.reready_bots, daemon=True).start()
        else:
            self.sub.set("Chỉ dùng khi đang ở phòng chờ và bạn vừa đổi cài đặt trong đó.")

    def on_close(self):
        self.autosave()
        if self.session:
            self.session.shutdown()
        if self.pool:
            self.pool.shutdown()
        self.root.destroy()


def selftest():
    """AoESolo.exe --selftest: set up a 1-AI room, press Start in the player's game, play 30 s, close."""
    log = open(os.path.join(base_dir(), "selftest.log"), "w", encoding="utf-8")

    def L(m):
        log.write(time.strftime("%H:%M:%S ") + m + "\n")
        log.flush()

    cfg = orchestrator.Config()
    sess = orchestrator.Session(base_dir(), cfg, log=L, status=lambda m: L("STATUS " + m),
                                dll=resource_path(os.path.join("bin", "aoehook.dll")),
                                dplaunch=resource_path(os.path.join("bin", "dplaunch.exe")))
    ok = False
    try:
        sess.run()
        t = threading.Thread(target=sess.wait_and_play, daemon=True)
        t.start()
        time.sleep(2)
        sess.player.hook.cmd("vin 1")
        sess.player.hook.click(628, 728)
        sess.player.hook.cmd("vin 0")
        t.join(90)
        time.sleep(30)
        ok = bool(sess.threads) and all(th.is_alive() for th in sess.threads)
        L("bots running: %s" % ok)
    except Exception as e:  # noqa: BLE001
        L("selftest error: %r" % (e,))
    finally:
        sess.shutdown()
        if sess.player:
            sess.player.kill()
        L("SELFTEST %s" % ("PASS" if ok else "FAIL"))


def check():
    """AoESolo.exe --check: import every module the launcher needs and report (packaging test)."""
    out = []
    for name in ("psutil", "winreg", "PIL", "PIL.ImageTk", "dplobby", "orchestrator", "lobby", "procs", "inject", "aoemem",
                 "gamedir", "gamestate", "d3kt", "pathing", "walling", "placement", "gamewin", "brainproc", "ui_theme", "updater", "version",
                 "brain.brain", "brain.plan", "brain.jobs", "brain.adapter", "brain.tasks.lure", "brain.tasks.herd"):
        try:
            __import__(name)
            out.append("ok   " + name)
        except Exception as e:  # noqa: BLE001
            out.append("FAIL %s: %r" % (name, e))
    for rel in (os.path.join("bin", "aoehook.dll"), os.path.join("bin", "dplaunch.exe")):
        out.append(("ok   " if os.path.exists(resource_path(rel)) else "FAIL missing ") + rel)
    with open(os.path.join(base_dir(), "check.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main():
    if "--check" in sys.argv:
        return check()
    if "--selftest" in sys.argv:
        return selftest()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # (the frozen exe: a child process of the wall-cut pool / a brain process
    main()                             #  would otherwise run the launcher again)
