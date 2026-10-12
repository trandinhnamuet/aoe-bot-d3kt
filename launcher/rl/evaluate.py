"""A saved policy (npz) on fixed seeds: the strict pass rate at lag 2 and lag 1, next to the hand-coded
push on the same episodes.

    python -m rl.evaluate rl/policies/herd_push.npz [N=40] [--seed0 100000] [--show]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rl.herd_env import HerdEnv                      # noqa: E402
from rl.policy import Policy                         # noqa: E402


def run_policy(pol, n, lag, seed0, show=False):
    env = HerdEnv()
    rows = []
    for k in range(n):
        obs = env.reset(seed0 + k, lag=lag)
        done = False
        while not done:
            obs, r, done, info = env.step(pol.act_batch(obs))
        rows.append(info)
        if show:
            print("  seed %d: %s" % (seed0 + k, {k2: info[k2] for k2 in ("n", "home4", "near", "field", "alive", "t", "strict")}))
    return rows


def summary(label, rows):
    n = len(rows)
    tot = sum(r["n"] for r in rows)
    return "%s: strict %d/%d (%.0f%%) | all home %d | gazelles %d: <=4 tiles %d, 4-6.5 %d, field %d, alive %d | t p50 %.0f" % (
        label, sum(1 for r in rows if r["strict"]), n, 100.0 * sum(1 for r in rows if r["strict"]) / n,
        sum(1 for r in rows if r["all_home"]), tot, sum(r["home4"] for r in rows), sum(r["near"] for r in rows),
        sum(r["field"] for r in rows), sum(r["alive"] for r in rows), float(np.median([r["t"] for r in rows])))


def main():
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 40
    seed0 = 100000
    show = "--show" in sys.argv
    for i, a in enumerate(sys.argv):
        if a == "--seed0":
            seed0 = int(sys.argv[i + 1])
    pol = Policy.load(path)
    env = HerdEnv()
    for lag in (2.0, 1.0):
        rows = run_policy(pol, n, lag, seed0, show)
        print(summary("policy    lag %.1f" % lag, rows))
        base = [env.rollout_handcoded(seed0 + k, lag=lag) for k in range(n)]
        print(summary("hand-coded lag %.1f" % lag, base))


if __name__ == "__main__":
    main()
