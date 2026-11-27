# Transformers MPF: instructions for Claude

> **STRICT RULE: DECOMPILE EVERYTHING (owner, 2026-11-24), and working rules 6-7 (owner, 2026-11-24). Binding on every agent, every game.**
> 1. Agent A decompiles **all**: the main ROM **and the firmware of every independent board** (any board with its own CPU, MCU, ROM or firmware: DMD, sound, others).
> 2. **Step zero, before anything else**: `docs/boards_inventory.md` lists every such board (board, CPU, ROM, decompile state `complet` / `partiel` / `absent`). A board that is not `complet` blocks the rules that depend on it.
> 3. The decompiled code is the source of every rule, value and behaviour, with the **ROM address cited**. It must cover scores, displays, inserts, coils and sounds. Every datum sent that is not understood is traced in the code (destination, function).
> 4. **Never code from an emulator capture** (PinMAME frames, renders, traces), images and DMD renders included. Last resort only, after a dead end, and **ask Vincent first**; record it in `docs/pinmame_waivers.md`.
> 5. Agent C codes nothing until A has delivered the **visual diagram taken from the code, one ROM address per node** (`docs/functional_diagram.md` or `docs/flow/`).
> 6. **Never end a turn by announcing "I continue" or "next step".** A finished turn stops the work. Chain on while doable work remains; stop only when everything is done, or on a blocker, which you name (what, and what you need).
> 7. **Post a factual progress report at least every 15 minutes** (done, running, blocked). The coordinator checks every active session every 15 minutes; a session that shows no progress is chased.
> 8. Enforced by `python tools/check_strict_rule.py .` (canonical copy: `tools/strict_rule/` in Stern-SAM-Decryption). Run it before every push; it must pass.
>
> Where this game stands against the rule: [docs/qa/README.md](docs/qa/README.md) (the QA reports) and
> [docs/boards_inventory.md](docs/boards_inventory.md).

This repository is the MPF recreation of Stern Transformers Pro 1.80 (ROM `tf_180`), built by the agents of the
master plan in [Ashram56/Stern-SAM-Decryption `agents/README.md`](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/README.md).
Since 2026-11-23 the plan has two halves: agents A (ROM extraction) and B (VPX extraction) with the decryption knowledge in
Stern-SAM-Decryption, agents C to G (recreation, VPX bridge, improvements, packaging, PuP Pack) with the MPF, Godot and GMC
knowledge and the PuP runtime in [Ashram56/MPF-Godot-Packaging](https://github.com/Ashram56/MPF-Godot-Packaging/blob/main/agents/README.md).
Read the plan first; it says which agent file covers the task.
Game facts stay here; every game-agnostic learning goes back in the same session to the repository that owns the topic
(taking a ROM or table apart: Stern-SAM-Decryption; rebuilding in MPF: MPF-Godot-Packaging, which holds no game content), per its
CONTRIBUTING.md (a PR with write access, else an issue). Everything for this game lives here:

| Path | Agent | What |
|---|---|---|
| `rom/` | A, ROM extraction | the ROM's tables, sounds, images, MPF package, tools ([rom/README.md](rom/README.md)) |
| `game/monitor/`, `docs/vpx/` | B, VPX extraction | MPF Monitor layout and the table's device positions |
| `game/`, `scripts/`, `tests/`, `docs/` | C, strict recreation | the game ([README.md](README.md)) |
| `scripts/vpx_*.py`, `game/config/hw_vpx.yaml`, `game/tf/vpx_hardware.py`, `docs/vpx.md` | D, VPX bridge | Visual Pinball X plays with MPF instead of PinMAME |
| `scripts/package/` (the package contract `game_package.json`, its completeness check, options and import template; MPF-Godot-Packaging only builds the bundle from the package), `scripts/install/`, `scripts/setup.bat`, `scripts/setup.ps1`, `scripts/setup_workspace.sh`, `tests/test_install.py`, `.github/workflows/test.yml`, `docs/requirements.md`, README "Install", "Play", "Settings" | F, packaging | the one-line installers on Windows, macOS and Linux, CI, the install docs (`setup.py` and `run.py` are shared with C) |
| `game/pup.cfg`, `game/tf_pup/`, `game/modes/pup/`, `docs/pup.md`; copies: `game/pup_runtime/`, `game/pup/`, `scripts/pup_*.py`, `scripts/gen_pup.py` | G, PuP Pack | TerryRed's PuP Pack on three screens ([docs/pup.md](docs/pup.md)); the pack is the private `pup_pack` submodule (Ashram56/Transformers-PuP); the copies come from MPF-Godot-Packaging `tools/pup/runtime/` (never edit them here) |

A contributor new to the project starts with [AGENTS.md](AGENTS.md): layout, set-up, tests, rules for changes, the
PuP Pack, and how to report to Stern-SAM-Decryption or MPF-Godot-Packaging without write access.

@AGENTS.md

Never commit the ROM. Run `pytest -q tests` and `python tools/check_strict_rule.py .` before pushing;
`scripts/render_check.py` for display work.
