#!/bin/bash
# bench.sh N MINUTES : N recorded AI-vs-AI matches, one summary line per AI (Tool / Bronze click, game s)
N=${1:-3}; M=${2:-7.5}
cd /d/Game/AoESolo/tools
for i in $(seq 1 $N); do
  if tasklist | grep -qi -e "league of" -e "empiresx" -e "aoesolo"; then echo "BUSY: user is playing - stop"; break; fi
  timeout 1200 python t_match_rec.py $M > /tmp/m.txt 2>&1
  cp match.log bench_$i.log
  for p in P1 P2; do
    tool=$(grep -oE "\[$p +[0-9]+s\] Tool Age clicked with [0-9]+" match.log | grep -oE "[0-9]+s|with [0-9]+" | tr '\n' ' ')
    bronze=$(grep -oE "\[$p +[0-9]+s\] Bronze Age clicked" match.log | grep -oE "[0-9]+s")
    errs=$(grep -c "\[$p.*tick error" match.log)
    echo "run $i $p tool=[$tool] bronze=[${bronze:--}] errors=$errs"
  done
done
