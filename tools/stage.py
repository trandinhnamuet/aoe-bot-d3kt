"""Set-piece (staged) tests for a local algorithm - the user, 15/10: no more random arena games for things like
the foundation trap. One command dresses the stage and runs it through the arena:

    .venv/Scripts/python tools/stage.py chase            # 10 chariot archers (P1) chase 6 (P2) that run away
    .venv/Scripts/python tools/stage.py chase --minutes 20 --rec      # with an .aoerec recording to watch

What it sets (env + arena flags):
  AOESOLO_STAGE=<stage>       the brain runs the stage's tick steps (d3kt.stage_<stage>) instead of the full game
  (no resource tampering: the game's cheat commands AND resource writes into every process both freeze the
   match clock on the AoE-HD build - stage8..stage11, 15/10; the hunter gathers its wood and keeps 160 for the trap)
  AOESOLO_ETRAPHIST=1         the chase history diagnostics
  --players 2 --age "Bronze Age" --resources High --reveal --no-rec   (two towns, Bronze start, whole map explored)

A real AoE1 Scenario (.scn) is not used: the game's lobby settings file has no scenario field and the .scn format
is not implemented; the stage dresses the situation from a random map instead (Bronze start, High resources
+ the staged build order), which takes about 8-10 game minutes (4-5 minutes real at x2) before the chase begins."""
import os
import subprocess
import sys

STAGES = {
    "chase": dict(env={"AOESOLO_STAGE": "chase", "AOESOLO_ETRAPHIST": "1"},
                  args=["--players", "2", "--civs", "Egyptian,Egyptian", "--age", "Bronze Age", "--resources", "High",
                        "--reveal", "--no-rec"]),
    # raid: P1's 10 chariot archers raid P2's villagers (P2 trains no army): the trap on villagers, the villagers'
    # flight toward the TC / open ground, and the anti-trap are what is watched
    "raid": dict(env={"AOESOLO_STAGE": "raid", "AOESOLO_ETRAPHIST": "1"},
                 args=["--players", "2", "--civs", "Egyptian,Egyptian", "--age", "Bronze Age", "--resources", "High",
                       "--reveal", "--no-rec"]),
}

if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
    print("usage: tools/stage.py <%s> [--minutes N] [--tag T] [arena args]" % "|".join(STAGES))
    sys.exit(2)
stage = STAGES[sys.argv[1]]
extra = sys.argv[2:]
args = list(stage["args"])
if "--rec" in extra:                      # --rec: an AoE-MapCap recording (.aoerec) of the match to look at
    extra.remove("--rec")
    args.remove("--no-rec")
if "--tag" not in extra:
    extra += ["--tag", "stage_" + sys.argv[1]]
if "--minutes" not in extra:
    extra += ["--minutes", "14"]
env = dict(os.environ)
env.update(stage["env"])
here = os.path.dirname(os.path.abspath(__file__))
cmd = [sys.executable, os.path.join(here, "arena.py")] + args + extra
print(" ".join(cmd))
sys.exit(subprocess.call(cmd, env=env, cwd=os.path.dirname(here)))
