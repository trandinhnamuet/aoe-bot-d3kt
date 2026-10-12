"""Self-improvement loop: keep changing the brain's numbers, play 4-AI arena matches with each set,
keep what plays better. Runs unattended for hours; pauses while the user plays (LoL / AoE).

python tune.py [--hours 8] [--matches 2] [--speed 3]

Score of one player (lower is better): Bronze click time (game s); without Bronze: Tool click + 400,
without Tool: 1500; plus 5 s per unit of distance to the recorded players' profile and 20 s per dead
villager. A candidate's score is the mean over all its players; it replaces the best set when it beats
it over --matches matches. The best set goes to launcher/params.json (the bot loads it every match)
and every trial to tools/arena/tune.jsonl.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(os.path.dirname(D), "launcher")
sys.path.insert(0, LAUNCHER)
import d3kt  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--hours", type=float, default=8)
ap.add_argument("--matches", type=int, default=2)
ap.add_argument("--speed", type=float, default=3.0)
ap.add_argument("--minutes", type=float, default=16.0)
args = ap.parse_args()

# search space: name -> (low, high, step)
SPACE = {
    "STONE_VILLAGERS": (22, 27, 1), "POOR_VILLAGERS": (18, 24, 1), "PUSH_RANGE": (10, 24, 2),
    "MAX_PUSHES": (1, 3, 1), "KILL_NEAR_TC": (4.0, 10.0, 1.0), "LURE_RANGE": (15, 32, 3),
    "HERD_NEAR": (18, 32, 2), "HERD_RANGE": (30, 50, 5), "BERRY_NEAR": (16, 30, 2),
    "HUNT_SITE_MIN": (3, 5, 1), "HUNT_SITE_MAX": (5, 9, 1), "MAX_HUNT_SITES": (2, 4, 1),
    "ELEPHANT_EATERS": (3, 6, 1), "WAIT_LIMIT": (10.0, 45.0, 5.0), "KEEP_MIN": (2.5, 4.5, 0.5),
    "KEEP_MAX": (5.0, 8.0, 0.5), "LURE_TIMEOUT": (90.0, 210.0, 30.0), "FOOD_ITEM_RANGE": (30, 50, 5),
    "FOOD_ITEMS_WANTED": (4, 7, 1), "WOOD_HARD_CAP": (6, 10, 1),
}
OUT = os.path.join(D, "arena")
BEST = os.path.join(LAUNCHER, "params.json")
LOG = os.path.join(OUT, "tune.jsonl")
os.makedirs(OUT, exist_ok=True)


def player_score(r):
    if r.get("bronze"):
        base = r["bronze"]
    elif r.get("tool"):
        base = r["tool"] + 400
    else:
        base = 1500
    return base + 5 * (r.get("profile_dist") or 0) + 20 * (r.get("deaths") or 0)


def run_match(params, tag):
    cand = os.path.join(OUT, "cand_%s.json" % tag)
    json.dump(params, open(cand, "w"), indent=1)
    while True:
        p = subprocess.run([sys.executable, os.path.join(D, "arena.py"), "--minutes", str(args.minutes),
                            "--speed", str(args.speed), "--params", cand, "--tag", tag],
                           capture_output=True, text=True, timeout=3600)
        if p.returncode == 3:                                  # the user is playing: wait, then retry
            time.sleep(300)
            continue
        rows = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
        if rows:
            return rows
        time.sleep(30)                                          # setup failed: try again


def mutate(base):
    c = dict(base)
    for k in random.sample(list(SPACE), random.randint(1, 3)):
        lo, hi, st = SPACE[k]
        v = c.get(k, (lo + hi) / 2)
        v = v + random.choice((-1, 1)) * st * random.randint(1, 2)
        v = min(hi, max(lo, v))
        c[k] = int(round(v)) if isinstance(st, int) else round(v, 2)
    if c.get("KEEP_MAX", 6.5) <= c.get("KEEP_MIN", 3.5) + 1.5:
        c["KEEP_MAX"] = c["KEEP_MIN"] + 2.0
    if c.get("HUNT_SITE_MAX", 7) < c.get("HUNT_SITE_MIN", 4):
        c["HUNT_SITE_MAX"] = c["HUNT_SITE_MIN"]
    return c


def evaluate(params, tag):
    rows = []
    for i in range(args.matches):
        rows += run_match(params, "%s_%d" % (tag, i))
    sc = sum(player_score(r) for r in rows) / len(rows)
    return sc, rows


def snapshot():
    """The tuner plays a frozen copy of the bot code, so the code can keep changing meanwhile."""
    import shutil
    dst = os.path.join(OUT, "code_" + time.strftime("%Y%m%d_%H%M%S"))
    shutil.copytree(LAUNCHER, dst, ignore=shutil.ignore_patterns("__pycache__", "params.json"))
    os.environ["AOESOLO_LAUNCHER"] = dst
    return dst


def main():
    code = snapshot()
    with open(LOG, "a") as f:
        f.write(json.dumps({"t": time.time(), "kind": "start", "code": code, "hours": args.hours}) + "\n")
    t_end = time.time() + args.hours * 3600
    defaults = {k: v for k, v in d3kt.current_params().items() if k in SPACE}
    best = json.load(open(BEST)) if os.path.exists(BEST) else defaults
    best = {**defaults, **best}
    best_score, rows = evaluate(best, "best0")
    with open(LOG, "a") as f:
        f.write(json.dumps({"t": time.time(), "kind": "baseline", "score": best_score, "params": best, "rows": rows}) + "\n")
    n = 0
    while time.time() < t_end:
        n += 1
        cand = mutate(best)
        sc, rows = evaluate(cand, "c%d" % n)
        better = sc < best_score
        with open(LOG, "a") as f:
            f.write(json.dumps({"t": time.time(), "kind": "trial", "n": n, "score": sc, "best": best_score,
                                "accepted": better, "params": cand, "rows": rows}) + "\n")
        if better:
            best, best_score = cand, sc
            json.dump(best, open(BEST, "w"), indent=1)
        # re-measure the best set now and then (maps differ a lot between matches)
        if n % 5 == 0:
            sc2, rows2 = evaluate(best, "best%d" % n)
            best_score = (best_score + sc2) / 2
            with open(LOG, "a") as f:
                f.write(json.dumps({"t": time.time(), "kind": "recheck", "score": sc2, "best": best_score}) + "\n")


if __name__ == "__main__":
    main()
