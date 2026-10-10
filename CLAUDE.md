# Transformers MPF: instructions for Claude

This repository is the MPF recreation of Stern Transformers Pro 1.80 (ROM `tf_180`), built by the agents of the
master plan in [Ashram56/Stern-SAM-Decryption `agents/README.md`](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/README.md)
(agents in `agents/`, knowledge base in `knowledge/`). Read that plan first; it says which agent file covers the task.
Game facts stay here; every game-agnostic learning goes back to Stern-SAM-Decryption in the same session, per its
[CONTRIBUTING.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/CONTRIBUTING.md) (a PR with write access, else an issue). Everything for this game lives here:

| Path | Agent | What |
|---|---|---|
| `rom/` | A, ROM extraction | the ROM's tables, sounds, images, MPF package, tools ([rom/README.md](rom/README.md)) |
| `game/monitor/`, `docs/vpx/` | B, VPX extraction | MPF Monitor layout and the table's device positions |
| `game/`, `scripts/`, `tests/`, `docs/` | C, strict recreation | the game ([README.md](README.md)) |

Never commit the ROM. Run `pytest -q tests` before pushing; `scripts/render_check.py` for display work.
