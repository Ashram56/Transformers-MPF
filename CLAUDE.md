# Transformers MPF: instructions for Claude

This repository is the MPF recreation of Stern Transformers Pro 1.80 (ROM `tf_180`), built by the agents of the
master plan in [Ashram56/Stern-SAM-Decryption `agents/README.md`](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/README.md).
Read that plan first; it says which agent file covers the task. Game-agnostic learnings go back to
Stern-SAM-Decryption (its CONTRIBUTING.md: a PR, else an issue); facts about this game stay here.
Everything lives here:

| Path | Agent | What |
|---|---|---|
| `rom/` | A, ROM extraction | the ROM's tables, sounds, images, MPF package, tools ([rom/README.md](rom/README.md)) |
| `game/monitor/`, `docs/vpx/` | B, VPX extraction | MPF Monitor layout and the table's device positions |
| `game/`, `scripts/`, `tests/`, `docs/` | C, strict recreation | the game ([README.md](README.md)) |
| `scripts/vpx_*.py`, `game/config/hw_vpx.yaml`, `game/tf/vpx_hardware.py`, `docs/vpx.md` | D, VPX bridge | Visual Pinball X plays with MPF instead of PinMAME |
| `scripts/install/`, `scripts/setup.bat`, `scripts/setup.ps1` | F, packaging | the one-line installers (`setup.py` and `run.py` are shared with C) |

Never commit the ROM. Run `pytest -q tests` before pushing; `scripts/render_check.py` for display work.
