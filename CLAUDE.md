# AoE Bot D3KT (AoESolo) — context for Claude Code

The owner is Vietnamese and writes in Vietnamese; answer in Vietnamese. He plays AoE1 Rise of Rome (AoE-HD build)
and this project lets him play against bots that follow his own rules ("luật D3KT", see LUAT_D3KT.md).

## What it is
- `launcher/` — the app (tkinter, packaged as one `AoESolo.exe` by PyInstaller). The player's game opens a
  multiplayer room (DirectPlay lobby); hidden copies of the game (`AOEBOT.EXE` = copy of EMPIRESX.EXE) join as AI
  players; a hook DLL (`hook/aoehook.dll`, injected) gives memory access and virtual input; each AI's brain runs in
  its own Python process (`launcher/brainproc.py`) and plays through game commands.
- Key modules: `main.py` (UI), `orchestrator.py` (bot pool, room setup, joins, start), `lobby.py` (game screens,
  registry, civ/team writes), `d3kt.py` (the brain: economy, buildings, army), `brain/plan.py` (the villager
  allocation table actually used by NewBrain — `d3kt.allocate` is the OLD allocator, mostly unused),
  `brain/tactics.py` (army assessment, Iron-age plans per civ), `botnames.py`, `updater.py`, `telemetry.py`.
- `KIEN_TRUC_AI.md` = brain architecture; `LUAT_D3KT.md` = the owner's rules + every test result (section 3.9b).
- Logs: the launcher writes `aoesolo.log` next to `AoESolo.exe` (the whole session: room setup and every bot's
  lines `[P<n> <game s>s] ...`, `STAT` every ~10 s). Start every investigation there.

## Setup on a new machine
1. Python 3.10+ (64-bit), Git for Windows. `powershell -ExecutionPolicy Bypass -File tools\setup_dev.ps1`
   (creates `.venv`, installs `requirements.txt`).
2. A game folder with EMPIRESX.EXE (AoE-HD, e.g. `C:\Program Files\XArena\Game\AoE-HD`). Game files are NEVER put in
   the repo or a release. The launcher copies a Program Files game to `%LOCALAPPDATA%\AoESolo\AoE-HD`.
3. Run from source: `.venv\Scripts\python launcher\main.py`. Packaging check: `AoESolo.exe --check`.
4. Some tools hard-code `D:\Game\AoESolo` and `D:\Game\AoE-HD` (tools/arena.py: `--game`, env `AOESOLO_LAUNCHER`).
   Clone to `D:\Game\AoESolo` or pass the paths.

## Tests (hidden, never on the owner's screen)
- `tools/arena.py --players N --minutes M --no-rec [--civs A,B] [--teams 1,1,2,2] [--size Large] --tag X`:
  hidden host + N-1 hidden bots, x2 speed, log in `tools/arena/<time>_<tag>.log`.
- `tools/campaign.py tools/plans/<plan>.json <tag>` runs several arena games; `tools/campaign_report.py <tag>`
  summarises age clicks, villagers, farms, army per bot.
- `AoESolo.exe --selftest` = hidden 1-AI room, Start, 30 s of play, `selftest.log` (`--visible` uses a window).
- Local micro behaviours: staged set pieces `tools/stage.py chase|raid` (not random games).

## Build and release
1. Bump `launcher/version.py` (VERSION); `python -m py_compile` the changed files first.
2. `.venv\Scripts\python build.py --no-dll --no-game` -> `dist\AoESolo\AoESolo.exe`; run `--selftest`.
3. Zip = `AoESolo.exe` + `HUONG_DAN.txt` (user guide, ASCII Vietnamese) as `AoESolo.zip`.
4. Commit, `git push`, then `python tools/release.py vX.Y.Z "AoE Bot D3KT vX.Y.Z" notes.txt AoESolo.zip`
   (token from `git credential fill`, never printed). Release name exactly "AoE Bot D3KT vX.Y.Z", tag vX.Y.Z.
   Notes in Vietnamese: "Mới trong bản này" + the content of the two previous patches ("Có từ 1.2.x").
   The launcher's updater offers the latest release to every user (one click).

## Standing rules from the owner (do not break)
- NEVER add Claude / Co-Authored-By attribution to commits or PRs (it put Claude in the public repo's Contributors).
- Tests must never disturb his game: never kill AOEBOT.EXE / EMPIRESX.EXE by name (kill only your own PIDs); pause
  tests while `AoESolo.exe`, `EMPIRESX.EXE` or League of Legends run; bots on the hidden desktop; do not start
  `dist\AoESolo\AoESolo.exe` while an arena game runs (its user_busy() stops the test).
- Never try cheats or resource tampering in games (cheat command / memory writes freeze the match clock).
- Ask when a Vietnamese game term is unclear; never guess. Terms: đời 1/2/3/4 = Stone/Tool/Bronze/Iron;
  BE House, BS Storage Pit, BG Granary, BF Farm (ruộng), BM Market, BL Stable, BY Academy, BC Government Center,
  BB Barracks, BP Temple, BN Town Center, BK Siege Workshop, BA Archery Range, BD Dock; cung T Bowman, cung A
  Improved/Composite Bowman, cung R Chariot Archer, horse = Horse Archer, horse thần = Heavy Horse Archer, ngựa chém
  Cavalry, Y Hoplite / Y đẹp Phalanx / Y thần Centurion, Z swordsmen, voi War Elephant / voi thần Armored Elephant /
  voi tên Elephant Archer, K Catapult / K thần Heavy Catapult, bẹt Ballista / bẹt thần Helepolis, đạp đôi Scythe
  Chariot, phù Priest; "xóc quân" = mass-produce units; vảy E = house foundations to block a running enemy.
- Iron army per civ: horse -> horse thần (Choson, Carthaginian, Yamato, Hittite, Assyrian, Shang, Palmyran,
  Babylonian, Sumerian); đạp đôi (Roman, Egyptian); Y đẹp -> Y thần (Greek, Macedonian); Minoan cung A lửa
  (Composite + Alchemy + Ballistics) + K thần + bẹt thần; Persian/Phoenician voi thần + voi tên.
- Bot names: the first Roman is always "Hoang Tu Roman"; Vietnamese words go before the civ name, English after.
- Telemetry: Cloudflare worker in `telemetry/` on its own account (see telemetry/README.md).

## State (1.2.23, 02/11/2026)
Known weak points: room setup with 7 bots still 18+ s (1-2 bots do not see the room and reopen the list);
bots reach the Iron Age around minute 33+ (the owner wants < 32); Iron army production after the click was fixed
in 1.2.23 (tactics froze with 0 soldiers) but not yet verified in a long game. On a slower machine (internet café)
the owner reported 1v7 unplayable: bots not ready, civs not set, slow joins, freeze in game — investigate there
from aoesolo.log first (CPU count, tick times `tick=a/b ms` in STAT lines, SLOW tick lines, join lines).
