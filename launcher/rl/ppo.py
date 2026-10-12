"""PPO for the herd push (torch, CPU). One policy shared by both pushers (egocentric observations,
team reward), N environments stepped in-process (the sim is fast), evaluation on fixed seeds.

    python -m rl.ppo [--minutes 60] [--envs 16] [--out rl/policies/herd_push] [--resume path.pt]

Prints one line per update (reward, episode outcome rates) and every --eval-every updates the strict
pass rate on the fixed evaluation seeds at lag 2 and lag 1; keeps the best policy (by the lag-2 strict
rate) as <out>.npz (numpy, for the game) and <out>.pt (torch, to resume)."""
import argparse
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rl import features as F                         # noqa: E402
from rl.herd_env import HerdEnv                      # noqa: E402


class Net(nn.Module):
    def __init__(self, obs_dim, n_act, hidden=128):
        super().__init__()
        self.l1 = nn.Linear(obs_dim, hidden)
        self.l2 = nn.Linear(hidden, hidden)
        self.pi = nn.Linear(hidden, n_act)
        self.v = nn.Linear(hidden, 1)
        nn.init.orthogonal_(self.pi.weight, gain=0.01)
        nn.init.zeros_(self.pi.bias)

    def forward(self, x):
        h = torch.tanh(self.l1(x))
        h = torch.tanh(self.l2(h))
        return self.pi(h), self.v(h).squeeze(-1)


class RunningNorm:
    def __init__(self, dim):
        self.n, self.mean, self.m2 = 1e-4, np.zeros(dim, np.float64), np.ones(dim, np.float64)

    def update(self, x):
        x = np.asarray(x, np.float64).reshape(-1, self.mean.shape[0])
        bn = x.shape[0]
        bm, bv = x.mean(0), x.var(0)
        delta = bm - self.mean
        tot = self.n + bn
        self.mean += delta * bn / tot
        self.m2 = (self.m2 * self.n + bv * bn + delta ** 2 * self.n * bn / tot) / tot
        self.n = tot

    @property
    def std(self):
        return np.sqrt(self.m2) + 1e-6

    def __call__(self, x):
        return np.clip((np.asarray(x, np.float32) - self.mean) / self.std, -5.0, 5.0).astype(np.float32)


def export_npz(net, norm, path):
    sd = {k: v.detach().cpu().numpy() for k, v in net.state_dict().items()}
    np.savez(path, w1=sd["l1.weight"].T, b1=sd["l1.bias"], w2=sd["l2.weight"].T, b2=sd["l2.bias"],
             wpi=sd["pi.weight"].T, bpi=sd["pi.bias"], obs_mean=norm.mean.astype(np.float32), obs_std=norm.std.astype(np.float32))


def evaluate(net, norm, seeds, lag, max_t=150.0):
    env = HerdEnv()
    out = []
    with torch.no_grad():
        for s in seeds:
            obs = env.reset(s, lag=lag)
            done = False
            while not done:
                x = torch.as_tensor(norm(np.asarray(obs, np.float32)))
                logits, _ = net(x)
                acts = logits.argmax(-1).tolist()
                obs, r, done, info = env.step(acts)
            out.append(info)
    n = len(out)
    return dict(strict=sum(1 for i in out if i["strict"]) / n, all_home=sum(1 for i in out if i["all_home"]) / n,
                home4=sum(i["home4"] for i in out) / max(1, sum(i["n"] for i in out)),
                field=sum(i["field"] for i in out), alive=sum(i["alive"] for i in out),
                t=float(np.median([i["t"] for i in out])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--envs", type=int, default=16)
    ap.add_argument("--steps", type=int, default=128, help="rollout length per env per update")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--eval-every", type=int, default=10)
    ap.add_argument("--eval-n", type=int, default=40)
    ap.add_argument("--out", default="rl/policies/herd_push")
    ap.add_argument("--resume", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--workers", type=int, default=0, help="worker processes (0 = the envs in this process)")
    ap.add_argument("--dmin", type=float, default=12.0, help="herd distance range (curriculum: start nearer)")
    ap.add_argument("--dmax", type=float, default=25.0)
    ap.add_argument("--lag2", type=float, default=0.7, help="share of episodes at lag 2 (x2)")
    args = ap.parse_args()
    env_kwargs = dict(d_range=(args.dmin, args.dmax), lags=((2.0, args.lag2), (1.0, 1.0 - args.lag2)))
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    vec = None
    if args.workers > 0:
        from rl.vec import VecHerdEnv
        per = max(1, args.envs // args.workers)
        vec = VecHerdEnv(n_workers=args.workers, envs_per_worker=per, seed=args.seed * 1000, **env_kwargs)
        args.envs = vec.n
        envs = []
    else:
        envs = [HerdEnv(seed=args.seed * 1000 + i, **env_kwargs) for i in range(args.envs)]
    P = 2                                                        # pushers per env
    net = Net(F.OBS_DIM, F.N_ACTIONS)
    norm = RunningNorm(F.OBS_DIM)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, eps=1e-5)
    best = -1.0
    if args.resume and os.path.exists(args.resume):
        ck = torch.load(args.resume)
        net.load_state_dict(ck["net"])
        norm.n, norm.mean, norm.m2 = ck["norm_n"], ck["norm_mean"], ck["norm_m2"]
        best = ck.get("best", -1.0)
        print("resumed from %s (best %.2f)" % (args.resume, best))

    obs = np.zeros((args.envs, P, F.OBS_DIM), np.float32)
    if vec is not None:
        obs[:] = vec.reset()
    else:
        for i, e in enumerate(envs):
            obs[i] = np.asarray(e.reset(), np.float32)
    ep_ret = np.zeros(args.envs)
    ep_hist, t_start, update = [], time.time(), 0
    eval_seeds = list(range(100000, 100000 + args.eval_n))
    while time.time() - t_start < args.minutes * 60:
        T, N = args.steps, args.envs
        b_obs = np.zeros((T, N, P, F.OBS_DIM), np.float32)
        b_act = np.zeros((T, N, P), np.int64)
        b_logp = np.zeros((T, N, P), np.float32)
        b_val = np.zeros((T, N), np.float32)
        b_rew = np.zeros((T, N), np.float32)
        b_done = np.zeros((T, N), np.float32)
        norm.update(obs.reshape(-1, F.OBS_DIM))
        for t in range(T):
            x = torch.as_tensor(norm(obs.reshape(-1, F.OBS_DIM)))
            with torch.no_grad():
                logits, val = net(x)
                dist = torch.distributions.Categorical(logits=logits)
                act = dist.sample()
                logp = dist.log_prob(act)
            b_obs[t] = obs
            b_act[t] = act.view(N, P).numpy()
            b_logp[t] = logp.view(N, P).numpy()
            b_val[t] = val.view(N, P).mean(-1).numpy()
            if vec is not None:
                o_all, r_all, d_all, infos = vec.step(b_act[t])
                b_rew[t], b_done[t] = r_all, d_all
                ep_ret += r_all
                for i in range(N):
                    if d_all[i]:
                        ep_hist.append((ep_ret[i], infos[i]))
                        ep_ret[i] = 0.0
                obs[:] = o_all
            else:
                for i, e in enumerate(envs):
                    o, r, d, info = e.step(b_act[t, i].tolist())
                    b_rew[t, i], b_done[t, i] = r, float(d)
                    ep_ret[i] += r
                    if d:
                        ep_hist.append((ep_ret[i], info))
                        ep_ret[i] = 0.0
                        o = e.reset()
                    obs[i] = np.asarray(o, np.float32)
        with torch.no_grad():
            _, last_val = net(torch.as_tensor(norm(obs.reshape(-1, F.OBS_DIM))))
            last_val = last_val.view(N, P).mean(-1).numpy()
        # GAE
        adv = np.zeros((T, N), np.float32)
        gae = np.zeros(N, np.float32)
        for t in reversed(range(T)):
            nxt = last_val if t == T - 1 else b_val[t + 1]
            nonterm = 1.0 - b_done[t]
            delta = b_rew[t] + args.gamma * nxt * nonterm - b_val[t]
            gae = delta + args.gamma * args.lam * nonterm * gae
            adv[t] = gae
        ret = adv + b_val
        # flatten per pusher (shared reward / value per env step)
        f_obs = torch.as_tensor(norm(b_obs.reshape(-1, F.OBS_DIM)))
        f_act = torch.as_tensor(b_act.reshape(-1))
        f_logp = torch.as_tensor(b_logp.reshape(-1))
        f_adv = torch.as_tensor(np.repeat(adv.reshape(-1), P))
        f_ret = torch.as_tensor(np.repeat(ret.reshape(-1), P))
        f_adv = (f_adv - f_adv.mean()) / (f_adv.std() + 1e-8)
        n_samples = f_obs.shape[0]
        for _ in range(args.epochs):
            perm = torch.randperm(n_samples)
            for k in range(0, n_samples, args.minibatch):
                idx = perm[k:k + args.minibatch]
                logits, val = net(f_obs[idx])
                dist = torch.distributions.Categorical(logits=logits)
                logp = dist.log_prob(f_act[idx])
                ratio = torch.exp(logp - f_logp[idx])
                pg = -torch.min(ratio * f_adv[idx], torch.clamp(ratio, 1 - args.clip, 1 + args.clip) * f_adv[idx]).mean()
                vl = Fn.mse_loss(val, f_ret[idx])
                ent = dist.entropy().mean()
                loss = pg + 0.5 * vl - args.ent * ent
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()
        update += 1
        recent = ep_hist[-200:]
        if recent:
            strict = sum(1 for _, i in recent if i["strict"]) / len(recent)
            allhome = sum(1 for _, i in recent if i["all_home"]) / len(recent)
            home4 = sum(i["home4"] for _, i in recent) / max(1, sum(i["n"] for _, i in recent))
            field = sum(i["field"] for _, i in recent) / len(recent)
            tmed = float(np.median([i["t"] for _, i in recent]))
            print("upd %4d %6.0fs samples %7d | ret %6.2f | strict %.2f all-home %.2f home4 %.2f field/ep %.2f t %.0f | ent %.2f" % (
                update, time.time() - t_start, update * T * N * P, float(np.mean([r for r, _ in recent])), strict, allhome, home4,
                field, tmed, float(ent)), flush=True)
        if update % args.eval_every == 0:
            e2 = evaluate(net, norm, eval_seeds, 2.0)
            e1 = evaluate(net, norm, eval_seeds, 1.0)
            print("EVAL upd %d: lag2 strict %.2f all-home %.2f home4 %.2f field %d alive %d t %.0f | lag1 strict %.2f all-home %.2f home4 %.2f t %.0f" % (
                update, e2["strict"], e2["all_home"], e2["home4"], e2["field"], e2["alive"], e2["t"],
                e1["strict"], e1["all_home"], e1["home4"], e1["t"]), flush=True)
            score = e2["strict"] + 0.5 * e1["strict"] + 0.2 * e2["home4"]
            torch.save(dict(net=net.state_dict(), norm_n=norm.n, norm_mean=norm.mean, norm_m2=norm.m2, best=best, update=update),
                       args.out + "_last.pt")
            if score > best:
                best = score
                torch.save(dict(net=net.state_dict(), norm_n=norm.n, norm_mean=norm.mean, norm_m2=norm.m2, best=best, update=update),
                           args.out + ".pt")
                export_npz(net, norm, args.out + ".npz")
                print("  saved best (score %.2f) -> %s.npz" % (best, args.out), flush=True)
    print("done: %d updates, best score %.2f" % (update, best))
    if vec is not None:
        vec.close()


if __name__ == "__main__":
    main()
