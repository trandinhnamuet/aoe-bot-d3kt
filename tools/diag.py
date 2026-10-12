"""Per-AI diagnosis over a batch of arena matches: why Tool / Bronze came late.

python diag.py TAG   (arena logs tools/arena/*_TAG_*.log, results from arena/results.jsonl)"""
import glob
import json
import os
import re
import statistics as st
import sys

D = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1]
res = {}
for line in open(os.path.join(D, "arena", "results.jsonl")):
    r = json.loads(line)
    if r["tag"].startswith(tag + "_") and not r.get("invalid"):
        res[(r["stamp"], r["player"])] = r
rows = []
for f in sorted(glob.glob(os.path.join(D, "arena", "*_%s_*.log" % tag))):
    stamp = os.path.basename(f)[:15]
    text = open(f, encoding="utf-8").read()
    for p in range(1, 9):
        tagp = r"\[P%d +(?:\d+)s\] " % p
        if not re.search(tagp, text):
            continue
        r = res.get((stamp, p))
        if r is None:
            continue
        def count(pat):
            return len(re.findall(tagp + pat, text))
        m25 = re.search(tagp + r"DIAG stone villagers \(\d+\) reached at (\d+) s with food (\d+)", text)
        dg = re.findall(tagp + r"DIAG gaz_near=(\d+) ele_near=(\d+)", text)
        gaz, ele = (int(dg[-1][0]), int(dg[-1][1])) if dg else (0, 0)
        rows.append({
            "match": stamp, "p": p, "tool": r["tool"], "bronze": r["bronze"],
            "t25": int(m25.group(1)) if m25 else None, "food25": int(m25.group(2)) if m25 else None,
            "gaz_near": gaz, "push_try": count(r"push (?:gazelle #|herd )"),
            "push_home": count(r"(?:gazelle #\d+|herd \(\d+, \d+\))(?:: herd)? pushed home"),
            "push_lost": count(r"(?:push of (?:gazelle #\d+|herd \(\d+, \d+\)) lost|herd \(\d+, \d+\): failed: lost)"),
            "push_stuck": count(r"(?:gazelle #\d+ is stuck|push of herd \(\d+, \d+\) (?:stuck|no way)|herd \(\d+, \d+\): failed: (?:stuck|no way))"),
            "push_timeout": count(r"(?:push of (?:gazelle #\d+|herd \(\d+, \d+\)) timed out|herd \(\d+, \d+\): failed: timed)"),
            "herd_gaz_home": sum(int(x) for x in re.findall(tagp + r"herd \(\d+, \d+\)(?:: herd)? pushed home in \d+ s \((\d+) gazelles", text)),
            "ele_near": ele, "lure_try": count(r"lure elephant #"), "lure_ok": count(r"elephant #\d+ down after"),
            "lure_fail": count(r"(?:elephant #\d+ (?:not found|does not follow|: lure took)|lure \d+: failed)"),
            "stable_fail": count(r"placement failed for 101"), "tool_restart": count(r"Tool Age click did not start"),
            "nofood": count(r"WATCHDOG nobody on food"), "deaths": r.get("deaths"),
        })
f = lambda v: "%d:%02d" % (v // 60, v % 60) if v else "  -  "
print("%-15s P  tool  bronze  t25   wait  gaz push(h/l/s/t)  ele lure(ok/f) nofood" % "match")
for r in rows:
    wait = (r["tool"] - r["t25"]) if r["tool"] and r["t25"] else None
    print("%-15s %d %s %s %s %5s  %3d  %2d(%d/%d/%d/%d)  %3d  %2d(%d/%d)  %d" % (
        r["match"], r["p"], f(r["tool"]), f(r["bronze"]), f(r["t25"]), wait if wait is not None else "-",
        r["gaz_near"], r["push_try"], r["push_home"], r["push_lost"], r["push_stuck"], r["push_timeout"],
        r["ele_near"], r["lure_try"], r["lure_ok"], r["lure_fail"], r["nofood"]))
n = len(rows)
if n:
    tools = [r["tool"] for r in rows if r["tool"]]
    br = [r["bronze"] for r in rows if r["bronze"]]
    waits = [r["tool"] - r["t25"] for r in rows if r["tool"] and r["t25"]]
    t25 = [r["t25"] for r in rows if r["t25"]]
    print("\nAIs %d | Tool %d (median %s) | Bronze %d (%s) | 25 villagers at median %s, then waited median %s s for food" % (
        n, len(tools), f(int(st.median(tools))) if tools else "-", len(br), " ".join(f(b) for b in sorted(br)),
        f(int(st.median(t25))) if t25 else "-", int(st.median(waits)) if waits else "-"))
    G = sum(r["gaz_near"] for r in rows)
    print("gazelles seen in reach %d | push tries %d, home %d (%d gazelles in whole herds), lost %d, stuck %d, timed out %d" % (
        G, sum(r["push_try"] for r in rows), sum(r["push_home"] for r in rows), sum(r["herd_gaz_home"] for r in rows),
        sum(r["push_lost"] for r in rows), sum(r["push_stuck"] for r in rows), sum(r["push_timeout"] for r in rows)))
    print("elephants seen in reach %d | lure tries %d, killed %d, failed %d" % (
        sum(r["ele_near"] for r in rows), sum(r["lure_try"] for r in rows), sum(r["lure_ok"] for r in rows),
        sum(r["lure_fail"] for r in rows)))
    print("stable placement failures %d, Tool re-clicks %d, 'nobody on food' %d" % (
        sum(r["stable_fail"] for r in rows), sum(r["tool_restart"] for r in rows), sum(r["nofood"] for r in rows)))
