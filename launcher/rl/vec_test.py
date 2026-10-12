"""Throughput of the worker-process environments: python -m rl.vec_test [workers=10] [per=2]"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rl import features as F        # noqa: E402
from rl.vec import VecHerdEnv       # noqa: E402

if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    vec = VecHerdEnv(n_workers=nw, envs_per_worker=per, seed=5)
    obs = vec.reset()
    print("reset ok", obs.shape, flush=True)
    t0 = time.time()
    steps = 0
    rng = np.random.default_rng(0)
    for _ in range(100):
        acts = rng.integers(0, F.N_ACTIONS, size=(vec.n, 2))
        obs, r, d, infos = vec.step(acts)
        steps += vec.n
    dt = time.time() - t0
    print("vec: %d envs in %d workers, %.0f env-steps/s" % (vec.n, nw, steps / dt))
    vec.close()
