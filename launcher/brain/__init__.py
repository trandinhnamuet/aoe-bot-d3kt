"""The restructured D3KT brain (see KIEN_TRUC_AI.md): world -> plan -> jobs -> tasks -> micro.

Tasks are written against the small World / Orders interface in `iface.py`, so the same code runs in
the game (adapter over gamestate + the hook) and in `sim/` (a 2D simulator with the measured
gazelle / elephant / lag numbers) where lure and push logic is tuned in seconds."""
