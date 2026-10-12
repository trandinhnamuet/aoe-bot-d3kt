#!/bin/bash
# arena_batch.sh N TAG [MINUTES] : N 4-AI arena matches, then a summary of Tool / Bronze clicks
# REC=1 ./arena_batch.sh ... records each match with AoE-MapCap (D:/Game/AoE-MapCap/Video/Raw)
# BRAIN=new ./arena_batch.sh ... plays with brain.brain.NewBrain instead of the old d3kt.Brain
N=${1:-3}; TAG=${2:-batch}; M=${3:-16}; SPEED=${SPEED:-2.0}   # the user plays multiplayer at x2 (the UI maximum): test at x2 (order lag scales with the speed)
cd /d/Game/AoESolo/tools
# the user is playing (LoL, AoE, or AoESolo whose parked bots could join an arena room): wait.
# Never kill AOEBOT.EXE by name here - that also killed the bots of the user's own AoESolo game;
# arena.py's bots live in its kill-on-close job and die with it.
busy() { tasklist | grep -i -E "league of|empiresx|aoesolo" >/dev/null; }   # (this grep aborts with -q / multiple -e; -E works)
for i in $(seq 1 $N); do
  while busy; do sleep 120; done
  for try in 1 2 3; do
    timeout 1500 python arena.py --minutes $M --speed $SPEED --tag ${TAG}_$i --brain ${BRAIN:-new} $([ -n "$REC" ] || echo --no-rec) > /tmp/a_$i.txt 2>&1
    rc=$?
    [ $rc -eq 4 ] && { echo "match $i: slow game, retrying"; sleep 20; continue; }
    [ $rc -eq 3 ] && { while busy; do sleep 120; done; continue; }
    break
  done
done
python - "$TAG" <<'PY'
import json, sys, statistics as st
tag = sys.argv[1]
rows = [json.loads(l) for l in open("arena/results.jsonl") if json.loads(l)["tag"].startswith(tag + "_")
        and not json.loads(l).get("invalid")]
f = lambda v: "%d:%02d" % (v // 60, v % 60) if v else "-"
for t in sorted(set(r["tag"] for r in rows)):
    rs = [r for r in rows if r["tag"] == t]
    print(t, "tool", [f(r["tool"]) for r in rs], "bronze", [f(r["bronze"]) for r in rs])
to = [r["tool"] for r in rows if r["tool"]]; br = [r["bronze"] for r in rows if r["bronze"]]
print("n=%d tool %d (median %s) bronze %d %s" % (len(rows), len(to), f(int(st.median(to))) if to else "-", len(br), [f(b) for b in sorted(br)]))
PY
