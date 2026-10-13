"""AoE Solo vs AI (D3KT) launcher window."""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import gamedir
import lobby
import orchestrator

APP_TITLE = "AoE Solo vs AI — D3KT"
CIV_CHOICES = ["Ngẫu nhiên"] + lobby.CIVS
MAP_TYPES_VI = lobby.MAP_TYPES
MAP_SIZES = lobby.MAP_SIZES


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel):
    root = getattr(sys, "_MEIPASS", None) or base_dir()
    return os.path.join(root, rel)


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.resizable(False, False)
        self.q = queue.Queue()
        self.session = None
        self.logfile = open(os.path.join(base_dir(), "aoesolo.log"), "a", encoding="utf-8")

        frm = ttk.Frame(root, padding=14)
        frm.grid(sticky="nsew")
        frm.columnconfigure(0, minsize=115)
        r = 0
        ttk.Label(frm, text="Solo với AI chơi D3KT (Đời 3 không thành)", font=("Segoe UI", 12, "bold")).grid(
            row=r, column=0, columnspan=4, sticky="w", pady=(0, 10))
        r += 1

        ttk.Label(frm, text="Số AI").grid(row=r, column=0, sticky="w")
        self.num_ai = tk.IntVar(value=1)
        sp = ttk.Spinbox(frm, from_=1, to=7, textvariable=self.num_ai, width=5, command=self.refresh_ai_rows,
                         state="readonly")
        sp.grid(row=r, column=1, sticky="w")
        ttk.Label(frm, text="Phe AI").grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.team_mode = tk.StringVar(value="Các AI cùng phe")
        ttk.Combobox(frm, textvariable=self.team_mode, state="readonly", width=18,
                     values=["Các AI cùng phe", "Mỗi người một phe"]).grid(row=r, column=3, sticky="w")
        r += 1

        ttk.Label(frm, text="Bản đồ").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.map_type = tk.StringVar(value="Hill Country")
        ttk.Combobox(frm, textvariable=self.map_type, state="readonly", width=16, values=MAP_TYPES_VI).grid(
            row=r, column=1, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Kích thước").grid(row=r, column=2, sticky="e", padx=(16, 4), pady=(8, 0))
        self.map_size = tk.StringVar(value="Large")
        ttk.Combobox(frm, textvariable=self.map_size, state="readonly", width=18, values=MAP_SIZES).grid(
            row=r, column=3, sticky="w", pady=(8, 0))
        r += 1

        ttk.Label(frm, text="Dân số tối đa").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.pop = tk.StringVar(value="200")
        ttk.Combobox(frm, textvariable=self.pop, state="readonly", width=16,
                     values=[str(p) for p in lobby.POP_LIMITS]).grid(row=r, column=1, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Tài nguyên").grid(row=r, column=2, sticky="e", padx=(16, 4), pady=(8, 0))
        self.resources = tk.StringVar(value="Default")
        ttk.Combobox(frm, textvariable=self.resources, state="readonly", width=18,
                     values=list(lobby.RESOURCES)).grid(row=r, column=3, sticky="w", pady=(8, 0))
        r += 1

        ttk.Label(frm, text="Chế độ chơi").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.victory = tk.StringVar(value="Conquest")
        ttk.Combobox(frm, textvariable=self.victory, state="readonly", width=16,
                     values=lobby.VICTORIES).grid(row=r, column=1, sticky="w", pady=(8, 0))
        r += 1

        ttk.Label(frm, text="Độ phân giải").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.resolution = tk.StringVar(value="1366x768")
        ttk.Combobox(frm, textvariable=self.resolution, state="readonly", width=16,
                     values=["1366x768", "1600x900", "1920x1080"]).grid(row=r, column=1, sticky="w", pady=(8, 0))
        r += 1

        ttk.Label(frm, text="Bản game").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.editions = gamedir.find_editions(base_dir(), deep=False)
        first = gamedir.remembered_edition()
        if first not in self.editions:
            first = next((e for e in gamedir.EDITIONS if e in self.editions), gamedir.HD)
        self.edition = tk.StringVar(value=first)
        cb = ttk.Combobox(frm, textvariable=self.edition, state="readonly", width=16, values=gamedir.EDITIONS)
        cb.grid(row=r, column=1, sticky="w", pady=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_edition())
        r += 1
        ttk.Label(frm, text="Thư mục game").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.game_dir = self.editions.get(first) or gamedir.find(base_dir(), deep=False)
        self.game_dir_var = tk.StringVar(value=self._short(self.game_dir) if self.game_dir else "(đang tìm...)")
        ttk.Label(frm, textvariable=self.game_dir_var, foreground="#555", width=34).grid(
            row=r, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(frm, text="Chọn...", command=self.choose_game_dir, width=10).grid(row=r, column=3, sticky="e", pady=(8, 0))
        r += 1

        ttk.Separator(frm).grid(row=r, column=0, columnspan=4, sticky="ew", pady=12)
        r += 1
        ttk.Label(frm, text="Tên của bạn").grid(row=r, column=0, sticky="w")
        try:
            remembered = lobby.reg_get(lobby.REG_NAME) or ""
        except Exception:  # noqa: BLE001
            remembered = ""
        self.player_name = tk.StringVar(value=remembered)
        ttk.Entry(frm, textvariable=self.player_name, width=18).grid(row=r, column=1, sticky="w")
        ttk.Label(frm, text="(tên hiện trong game)", foreground="#777").grid(row=r, column=2, columnspan=2, sticky="w", padx=(16, 0))
        r += 1
        ttk.Label(frm, text="Quân của bạn").grid(row=r, column=0, sticky="w")
        self.player_civ = tk.StringVar(value=CIV_CHOICES[0])
        ttk.Combobox(frm, textvariable=self.player_civ, state="readonly", width=16, values=CIV_CHOICES).grid(
            row=r, column=1, sticky="w")
        r += 1

        self.ai_frame = ttk.Frame(frm)
        self.ai_frame.grid(row=r, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.ai_civs = [tk.StringVar(value=CIV_CHOICES[0]) for _ in range(7)]
        self.ai_rows = []
        for i in range(7):
            lab = ttk.Label(self.ai_frame, text="Quân AI %d" % (i + 1))
            cb = ttk.Combobox(self.ai_frame, textvariable=self.ai_civs[i], state="readonly", width=16,
                              values=CIV_CHOICES)
            self.ai_rows.append((lab, cb))
        self.refresh_ai_rows()
        r += 1

        ttk.Separator(frm).grid(row=r, column=0, columnspan=4, sticky="ew", pady=12)
        r += 1
        self.status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(frm, textvariable=self.status, foreground="#555").grid(row=r, column=0, columnspan=3, sticky="w")
        self.play_btn = ttk.Button(frm, text="Chơi", command=self.play, width=14)
        self.play_btn.grid(row=r, column=3, sticky="e")
        r += 1
        self.ready_btn = ttk.Button(frm, text="Bot sẵn sàng lại", command=self.reready, width=18)
        self.ready_btn.grid(row=r, column=3, sticky="e", pady=(6, 0))
        ttk.Label(frm, text="(dùng nếu bạn đổi cài đặt trong phòng chờ)", foreground="#777").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(6, 0))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(200, self.pump)
        self.pool = None
        if self.game_dir:
            root.after(300, lambda: self.use_game_dir(self.game_dir))
        else:
            threading.Thread(target=self._deep_find, daemon=True).start()

    # ---------------------------------------------------------------- the game folder
    @staticmethod
    def _short(p):
        return p if len(p) <= 44 else "..." + p[-41:]

    def on_edition(self):
        """The player picked AoE HD / AoE thường: its folder (found or remembered), else ask for it."""
        e = self.edition.get()
        p = self.editions.get(e)
        if not p:
            found = gamedir.find_editions(base_dir(), deep=True)
            self.editions.update(found)
            p = self.editions.get(e)
        if p:
            self.use_game_dir(p)
        else:
            self.game_dir_var.set("(chưa thấy %s - bấm Chọn...)" % e)
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
            self.game_dir_var.set("(chưa tìm thấy - bấm Chọn...)")

    def choose_game_dir(self):
        p = filedialog.askdirectory(title="Chọn thư mục game AoE (có EMPIRESX.EXE)",
                                    initialdir=self.game_dir or "C:\\")
        if not p:
            return
        p = os.path.normpath(p)
        if not gamedir.has_game(p):
            messagebox.showerror(APP_TITLE, "Thư mục này không có EMPIRESX.EXE.")
            return
        self.use_game_dir(p)

    def use_game_dir(self, p):
        """Take the player's own install; copy it to AoESolo's folder when it cannot be written to (the
        bot copy of the exe and the game settings live in the game folder)."""
        if not gamedir.known_build(p):
            messagebox.showwarning(APP_TITLE, "EMPIRESX.EXE ở thư mục này khác bản AoE HD / AoE thường (AOE1R) "
                                              "mà bot được viết cho. Bot có thể không chạy được.")
        if not gamedir.writable(p):
            if not messagebox.askyesno(APP_TITLE, "Thư mục game không ghi được (cần quyền admin):\n%s\n\n"
                                                  "Chép bản game trên máy này sang thư mục riêng của AoESolo để dùng?\n%s"
                                       % (p, gamedir.local_copy_dir(p))):
                self.game_dir_var.set("(chưa dùng được - bấm Chọn...)")
                return

            def prog(i, n):
                self.status.set("Đang chép game... %d/%d" % (i, n))
                self.root.update()
            p = gamedir.copy_local(p, progress=prog)
            self.status.set("Sẵn sàng")
        e = gamedir.edition_of(p) or self.edition.get()
        if e in gamedir.EDITIONS and e != self.edition.get():
            self.edition.set(e)
        self.editions[self.edition.get()] = p
        if self.pool is not None and os.path.normpath(p) != os.path.normpath(self.game_dir or ""):
            old = self.pool
            threading.Thread(target=old.shutdown, daemon=True).start()   # the other edition's hidden bots go
        self.game_dir = p
        gamedir.remember(p)
        gamedir.remember_edition(self.edition.get(), p)
        self.game_dir_var.set(self._short(p))
        self.log("game folder: %s (%s)" % (p, self.edition.get()))
        self.pool = orchestrator.BotPool(p, resource_path(os.path.join("bin", "aoehook.dll")), log=self.log)
        self.root.after(1500, self.warm_bots)  # hidden bots get ready while you choose the settings

    def warm_bots(self):
        if self.pool is not None and gamedir.has_game(self.game_dir):
            threading.Thread(target=self.pool.ensure, args=(int(self.num_ai.get()),), daemon=True).start()

    def refresh_ai_rows(self):
        n = self.num_ai.get()
        if getattr(self, "pool", None):
            threading.Thread(target=self.pool.ensure, args=(int(n),), daemon=True).start()
        for i, (lab, cb) in enumerate(self.ai_rows):
            if i < n:
                lab.configure(width=14)
                lab.grid(row=i, column=0, sticky="w", pady=2)
                cb.grid(row=i, column=1, sticky="w", pady=2)
            else:
                lab.grid_remove()
                cb.grid_remove()

    # ------------------------------------------------------------------
    def log(self, msg):
        line = time.strftime("%H:%M:%S ") + msg
        try:
            self.logfile.write(line + "\n")
            self.logfile.flush()
        except OSError:
            pass

    def set_status(self, s):
        self.q.put(("status", s))

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "status":
                    self.status.set(val)
                elif kind == "error":
                    self.status.set("Lỗi: " + val)
                    self.play_btn.state(["!disabled"])
                    messagebox.showerror(APP_TITLE, val)
                elif kind == "done":
                    self.status.set(val)
                    self.play_btn.state(["!disabled"])
        except queue.Empty:
            pass
        self.root.after(200, self.pump)

    def civ_value(self, name):
        return 0 if name == CIV_CHOICES[0] else lobby.CIVS.index(name) + 1

    def play(self):
        cfg = orchestrator.Config()
        cfg.num_ai = int(self.num_ai.get())
        cfg.map_type = self.map_type.get()
        cfg.map_size = self.map_size.get()
        cfg.pop_limit = int(self.pop.get())
        cfg.resources = self.resources.get()
        cfg.victory = self.victory.get()
        cfg.player_civ = self.civ_value(self.player_civ.get())
        cfg.ai_civs = [self.civ_value(v.get()) for v in self.ai_civs]
        cfg.ai_team_mode = "together" if self.team_mode.get().startswith("Các AI") else "ffa"
        cfg.resolution = int(self.resolution.get().split("x")[0])
        cfg.player_name = self.player_name.get().strip()[:24]
        if not gamedir.has_game(self.game_dir) or self.pool is None:
            messagebox.showerror(APP_TITLE, "Chưa có thư mục game AoE (có EMPIRESX.EXE). Bấm \"Chọn...\" để chọn.")
            return
        self.play_btn.state(["disabled"])
        self.status.set("Đang chuẩn bị...")
        threading.Thread(target=self._run, args=(cfg,), daemon=True).start()

    def _run(self, cfg):
        sess = orchestrator.Session(base_dir(), cfg, log=self.log, status=self.set_status,
                                    dll=resource_path(os.path.join("bin", "aoehook.dll")),
                                    dplaunch=resource_path(os.path.join("bin", "dplaunch.exe")),
                                    pool=self.pool, game_dir=self.game_dir)
        self.session = sess
        try:
            sess.run()                 # the player's game hosts; hidden bots join
            self.root.after(0, self.root.iconify)
            sess.wait_and_play()
        except Exception as e:
            self.log("setup failed: %r" % (e,))
            self.q.put(("error", "Không tạo được trận: %s" % e))
            self.root.after(0, self.root.deiconify)
            return
        # wait for the player to close the game, then clean up the hidden bots
        while sess.player_alive():
            time.sleep(1.0)
        sess.shutdown()
        self.root.after(0, self.root.deiconify)
        self.q.put(("done", "Trận đã kết thúc"))
        self.root.after(1000, self.warm_bots)  # get the next match's bots ready

    def reready(self):
        sess = self.session
        if sess and sess.bots:
            threading.Thread(target=sess.reready_bots, daemon=True).start()

    def on_close(self):
        if self.session:
            self.session.shutdown()
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
    except Exception as e:
        L("selftest error: %r" % (e,))
    finally:
        sess.shutdown()
        if sess.player:
            sess.player.kill()
        L("SELFTEST %s" % ("PASS" if ok else "FAIL"))


def check():
    """AoESolo.exe --check: import every module the launcher needs and report (packaging test)."""
    out = []
    for name in ("psutil", "winreg", "PIL", "dplobby", "orchestrator", "lobby", "procs", "inject", "aoemem", "gamedir",
                 "gamestate", "d3kt", "pathing", "walling", "placement", "gamewin",
                 "brain.brain", "brain.plan", "brain.jobs", "brain.adapter", "brain.tasks.lure", "brain.tasks.herd"):
        try:
            __import__(name)
            out.append("ok   " + name)
        except Exception as e:
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
    try:
        root.iconbitmap(resource_path("aoesolo.ico"))
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
