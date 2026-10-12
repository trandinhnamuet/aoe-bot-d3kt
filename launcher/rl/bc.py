"""Behaviour cloning of the hand-coded push as a warm start for PPO: record what HerdPush orders
on many episodes of the environment, fit the policy network to it (cross-entropy), evaluate, and
save a checkpoint that `python -m rl.ppo --resume` continues from.

    python -m rl.bc [--episodes 600] [--epochs 15] [--out rl/policies/herd_push_bc]
"""
import argparse
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rl import features as F                          # noqa: E402
from rl.herd_env import HerdEnv                       # noqa: E402
from rl.ppo import Net, RunningNorm, evaluate, export_npz   # noqa: E402


def collect(n_episodes, seed0=5000, dmin=12.0, dmax=25.0, lag2=0.7):
    env = HerdEnv(d_range=(dmin, dmax), lags=((2.0, lag2), (1.0, 1.0 - lag2)))
    X, Y = [], []
    t0 = time.time()
    for k in range(n_episodes):
        for obs, acts in env.record_handcoded(seed0 + k):
            for row, a in zip(obs, acts):
                X.append(row)
                Y.append(a)
        if (k + 1) % 100 == 0:
            print("  %d episodes, %d samples, %.0f s" % (k + 1, len(Y), time.time() - t0), flush=True)
    return np.asarray(X, np.float32), np.asarray(Y, np.int64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=600)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--out", default="rl/policies/herd_push_bc")
    ap.add_argument("--dmin", type=float, default=12.0)
    ap.add_argument("--dmax", type=float, default=25.0)
    ap.add_argument("--lag2", type=float, default=0.7)
    ap.add_argument("--eval-n", type=int, default=40)
    args = ap.parse_args()
    torch.set_num_threads(4)
    torch.manual_seed(0)
    print("collecting the hand-coded push ...", flush=True)
    X, Y = collect(args.episodes, dmin=args.dmin, dmax=args.dmax, lag2=args.lag2)
    hist = np.bincount(Y, minlength=F.N_ACTIONS)
    print("samples %d; most used actions: %s" % (len(Y), [(int(i), int(hist[i])) for i in np.argsort(-hist)[:8]]), flush=True)
    norm = RunningNorm(F.OBS_DIM)
    norm.update(X)
    Xn = torch.as_tensor(norm(X))
    Yt = torch.as_tensor(Y)
    net = Net(F.OBS_DIM, F.N_ACTIONS)
    nn.init.orthogonal_(net.pi.weight, gain=1.0)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    n = len(Y)
    for ep in range(args.epochs):
        perm = torch.randperm(n)
        tot, correct = 0.0, 0
        for k in range(0, n, 512):
            idx = perm[k:k + 512]
            logits, _ = net(Xn[idx])
            loss = Fn.cross_entropy(logits, Yt[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(idx)
            correct += int((logits.argmax(-1) == Yt[idx]).sum())
        print("epoch %2d: loss %.3f acc %.2f" % (ep + 1, tot / n, correct / n), flush=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    seeds = list(range(100000, 100000 + args.eval_n))
    e2 = evaluate(net, norm, seeds, 2.0)
    e1 = evaluate(net, norm, seeds, 1.0)
    print("BC policy: lag2 strict %.2f all-home %.2f home4 %.2f alive %d t %.0f | lag1 strict %.2f all-home %.2f home4 %.2f t %.0f" % (
        e2["strict"], e2["all_home"], e2["home4"], e2["alive"], e2["t"], e1["strict"], e1["all_home"], e1["home4"], e1["t"]), flush=True)
    best = e2["strict"] + 0.5 * e1["strict"] + 0.2 * e2["home4"]
    torch.save(dict(net=net.state_dict(), norm_n=norm.n, norm_mean=norm.mean, norm_m2=norm.m2, best=best, update=0), args.out + ".pt")
    export_npz(net, norm, args.out + ".npz")
    print("saved %s.pt / .npz (score %.2f)" % (args.out, best))


if __name__ == "__main__":
    main()
