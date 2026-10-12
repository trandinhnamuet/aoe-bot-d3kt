"""The hand-coded HerdPush scored on the RL environment's episodes - the number a policy must beat.

    python -m rl.baseline [N=40] [--lag 2.0|1.0|both] [--seed0 100000]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rl.herd_env import HerdEnv                      # noqa: E402


def run(n, lag, seed0):
    env = HerdEnv()
    rows = [env.rollout_handcoded(seed0 + k, lag=lag) for k in range(n)]
    tot = sum(r["n"] for r in rows)
    print("hand-coded lag %.1f: strict %d/%d (%.0f%%) | all home %d | gazelles %d: <=4 tiles %d, 4-6.5 %d, field %d, alive %d | t p50 %.0f" % (
        lag, sum(1 for r in rows if r["strict"]), n, 100.0 * sum(1 for r in rows if r["strict"]) / n,
        sum(1 for r in rows if r["all_home"]), tot, sum(r["home4"] for r in rows), sum(r["near"] for r in rows),
        sum(r["field"] for r in rows), sum(r["alive"] for r in rows), sorted(r["t"] for r in rows)[n // 2]))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 40
    lag = "both"
    seed0 = 100000
    for i, a in enumerate(sys.argv):
        if a == "--lag":
            lag = sys.argv[i + 1]
        if a == "--seed0":
            seed0 = int(sys.argv[i + 1])
    for L in ([2.0, 1.0] if lag == "both" else [float(lag)]):
        run(n, L, seed0)


if __name__ == "__main__":
    main()
