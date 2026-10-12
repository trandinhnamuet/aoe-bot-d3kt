import py_compile

p = r"D:\Game\AoESolo\launcher\orchestrator.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''            self.bots = self.pool.take(cfg.num_ai)''', '''            locked = False
            if not self.test_hidden_player and self.pool.starting:
                locked = pl.hook.cmd("fglock 1").startswith("ok")   # bots still starting: keep our focus
            try:
                self.bots = self.pool.take(cfg.num_ai)
            finally:
                if locked:
                    pl.hook.cmd("fglock 2")''')
open(p, "w", encoding="utf-8").write(s)
py_compile.compile(p, doraise=True)

p = r"D:\Game\AoESolo\launcher\main.py"
s = open(p, encoding="utf-8").read()
# resolution choice
s = s.replace('''        ttk.Separator(frm).grid(row=r, column=0, columnspan=4, sticky="ew", pady=12)
        r += 1
        ttk.Label(frm, text="Quân của bạn").grid(row=r, column=0, sticky="w")''', '''        ttk.Label(frm, text="Độ phân giải").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.resolution = tk.StringVar(value="1366x768")
        ttk.Combobox(frm, textvariable=self.resolution, state="readonly", width=16,
                     values=["1366x768", "1600x900", "1920x1080"]).grid(row=r, column=1, sticky="w", pady=(8, 0))
        r += 1

        ttk.Separator(frm).grid(row=r, column=0, columnspan=4, sticky="ew", pady=12)
        r += 1
        ttk.Label(frm, text="Quân của bạn").grid(row=r, column=0, sticky="w")''')
# bot pool started when the launcher opens
s = s.replace('''        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(200, self.pump)''', '''        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(200, self.pump)
        self.pool = orchestrator.BotPool(os.path.join(base_dir(), "AoE-HD"),
                                         resource_path(os.path.join("bin", "aoehook.dll")), log=self.log)
        root.after(1500, self.warm_bots)       # hidden bots get ready while you choose the settings

    def warm_bots(self):
        if os.path.exists(os.path.join(base_dir(), "AoE-HD", "EMPIRESX.EXE")):
            threading.Thread(target=self.pool.ensure, args=(int(self.num_ai.get()),), daemon=True).start()''')
s = s.replace('''    def refresh_ai_rows(self):
        n = self.num_ai.get()''', '''    def refresh_ai_rows(self):
        n = self.num_ai.get()
        if getattr(self, "pool", None):
            threading.Thread(target=self.pool.ensure, args=(int(n),), daemon=True).start()''')
s = s.replace('''        cfg.ai_team_mode = "together" if self.team_mode.get().startswith("Các AI") else "ffa"''', '''        cfg.ai_team_mode = "together" if self.team_mode.get().startswith("Các AI") else "ffa"
        cfg.resolution = int(self.resolution.get().split("x")[0])''')
s = s.replace('''                                    dplaunch=resource_path(os.path.join("bin", "dplaunch.exe")))
        self.session = sess''', '''                                    dplaunch=resource_path(os.path.join("bin", "dplaunch.exe")),
                                    pool=self.pool)
        self.session = sess''')
s = s.replace('''        while sess.player_alive():
            time.sleep(1.0)
        sess.shutdown()
        self.root.after(0, self.root.deiconify)
        self.q.put(("done", "Trận đã kết thúc"))''', '''        while sess.player_alive():
            time.sleep(1.0)
        sess.shutdown()
        self.root.after(0, self.root.deiconify)
        self.q.put(("done", "Trận đã kết thúc"))
        self.root.after(1000, self.warm_bots)  # get the next match's bots ready''')
s = s.replace('''    def on_close(self):
        if self.session:
            self.session.shutdown()''', '''    def on_close(self):
        if self.session:
            self.session.shutdown()
        self.pool.shutdown()''')
open(p, "w", encoding="utf-8").write(s)
py_compile.compile(p, doraise=True)
print("ok", "warm_bots" in s, "pool=self.pool" in s, "cfg.resolution" in s)
