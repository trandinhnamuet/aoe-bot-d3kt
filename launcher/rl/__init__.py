"""Reinforcement learning for the hunting micro (the herd push first).

rl.herd_env   - the environment: the 2D sim (sim.sim) with a herd 12-25 tiles out, two pushers under
                the policy, the hand-coded kill at the TC; reward = the user's pass condition
rl.baseline   - the hand-coded HerdPush scored on the same episodes
rl.ppo        - PPO training (torch, CPU)
rl.evaluate   - a saved policy on fixed seeds, strict pass rate at lag 1 / 2
rl.policy     - numpy inference of a saved policy (no torch in the game)
"""
