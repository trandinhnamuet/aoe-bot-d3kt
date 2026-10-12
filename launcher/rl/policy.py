"""Inference of a saved herd-push policy without torch - and without numpy in the game (the exe's venv
has neither): a pure-Python MLP over the JSON export; numpy is used when it is importable.

    pol = Policy.load("rl/policies/herd_push.json"); a = pol.act(obs)   # greedy action
"""
import json
import math
import os

try:
    import numpy as np
except Exception:  # noqa: BLE001
    np = None


class Policy:
    def __init__(self, params):
        self.p = params                       # lists (json) or arrays (npz)
        self.np = np is not None and all(hasattr(v, "shape") for v in params.values())
        if not self.np:
            self.p = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in params.items()}

    @classmethod
    def load(cls, path):
        if path.endswith(".npz"):
            if np is None:
                raise RuntimeError("numpy needed for .npz policies; use the .json export")
            with np.load(path) as z:
                return cls({k: z[k] for k in z.files})
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def find(cls, name="herd_push"):
        """The policy file next to the launcher (or inside the exe bundle), None when absent."""
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        cands = [os.path.join(here, "policies", name + ".json")]
        if getattr(sys, "_MEIPASS", None):
            cands.insert(0, os.path.join(sys._MEIPASS, "rl", "policies", name + ".json"))
        for c in cands:
            if os.path.exists(c):
                return cls.load(c)
        return None

    # ---------------------------------------------------------------- forward
    def logits(self, obs):
        p = self.p
        if self.np:
            x = (np.asarray(obs, dtype=np.float32) - p["obs_mean"]) / p["obs_std"]
            x = np.clip(x, -5.0, 5.0)
            h = np.tanh(x @ p["w1"] + p["b1"])
            h = np.tanh(h @ p["w2"] + p["b2"])
            return (h @ p["wpi"] + p["bpi"]).tolist()
        x = [max(-5.0, min(5.0, (o - m) / s)) for o, m, s in zip(obs, p["obs_mean"], p["obs_std"])]
        h = _layer(x, p["w1"], p["b1"], True)
        h = _layer(h, p["w2"], p["b2"], True)
        return _layer(h, p["wpi"], p["bpi"], False)

    def act(self, obs):
        lg = self.logits(obs)
        return max(range(len(lg)), key=lambda i: lg[i])

    def act_batch(self, obs_rows):
        return [self.act(o) for o in obs_rows]


def _layer(x, w, b, tanh):
    """x: list (n), w: n x m nested lists, b: list (m)."""
    m = len(b)
    out = list(b)
    for i, xi in enumerate(x):
        if xi == 0.0:
            continue
        row = w[i]
        for j in range(m):
            out[j] += xi * row[j]
    return [math.tanh(v) for v in out] if tanh else out


def npz_to_json(src, dst):
    """Export a numpy policy for the game (lists)."""
    with np.load(src) as z:
        d = {k: z[k].tolist() for k in z.files}
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return dst


if __name__ == "__main__":
    import sys
    print(npz_to_json(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1][:-4] + ".json"))
