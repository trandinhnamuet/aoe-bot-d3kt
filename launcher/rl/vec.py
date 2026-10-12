"""Environments in worker processes (the sim is pure Python: one core each).

    vec = VecHerdEnv(n_workers=12, envs_per_worker=2); obs = vec.reset()      # (N, 2, OBS_DIM)
    obs, rew, done, infos = vec.step(actions)                                  # actions (N, 2); auto-reset
    vec.close()
"""
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _worker(conn, n_envs, seed, env_kwargs):
    from rl.herd_env import HerdEnv
    envs = [HerdEnv(seed=seed + i, **env_kwargs) for i in range(n_envs)]
    while True:
        cmd, arg = conn.recv()
        if cmd == "reset":
            conn.send([e.reset() for e in envs])
        elif cmd == "step":
            out = []
            for e, a in zip(envs, arg):
                o, r, d, info = e.step(a)
                if d:
                    o = e.reset()
                out.append((o, r, d, info))
            conn.send(out)
        elif cmd == "close":
            conn.close()
            return


class VecHerdEnv:
    def __init__(self, n_workers=8, envs_per_worker=2, seed=0, **env_kwargs):
        ctx = mp.get_context("spawn")
        self.n_workers, self.k = n_workers, envs_per_worker
        self.n = n_workers * envs_per_worker
        self.conns, self.procs = [], []
        for w in range(n_workers):
            a, b = ctx.Pipe()
            p = ctx.Process(target=_worker, args=(b, envs_per_worker, seed + 100 * w, env_kwargs), daemon=True)
            p.start()
            self.conns.append(a)
            self.procs.append(p)

    def reset(self):
        for c in self.conns:
            c.send(("reset", None))
        rows = []
        for c in self.conns:
            rows.extend(c.recv())
        return np.asarray(rows, np.float32)

    def step(self, actions):
        actions = np.asarray(actions).reshape(self.n, -1).tolist()
        for w, c in enumerate(self.conns):
            c.send(("step", actions[w * self.k:(w + 1) * self.k]))
        obs, rew, done, infos = [], [], [], []
        for c in self.conns:
            for o, r, d, info in c.recv():
                obs.append(o)
                rew.append(r)
                done.append(d)
                infos.append(info)
        return np.asarray(obs, np.float32), np.asarray(rew, np.float32), np.asarray(done, np.float32), infos

    def close(self):
        for c in self.conns:
            try:
                c.send(("close", None))
            except Exception:  # noqa: BLE001
                pass
        for p in self.procs:
            p.join(timeout=2)
