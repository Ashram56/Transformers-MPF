# AGENTS.md: working on Transformers MPF with Claude (or any coding agent)

This file is for a contributor who arrives with no history of the project: you, and the AI agent you run in
this repository (Claude Code reads it through [CLAUDE.md](CLAUDE.md); other agents read `AGENTS.md` directly).
It says what the repository is, how to build, run and test it, the rules every change follows, and where
changes that are not about this game go. The owner is Vincent (GitHub `Ashram56`).

## 1. What this is

Stern's **Transformers Pro**, code v1.80 (PinMAME set and ROM image `tf_180`), rebuilt in the Mission Pinball
Framework: **MPF 0.80.1** runs the rules, **GMC 1.0.0 on Godot 4.6.3** draws the 128x32 DMD and plays the
sounds. Everything (rules, scores, display effects, sounds, lamp shows, coil times, the 98 operator
adjustments, the service menu, audits) was reverse engineered from the ROM and lives in [rom/](rom/README.md).
The goal is **the ROM's game exactly**. Every place the game still differs is a row in
[docs/rom_differences.md](docs/rom_differences.md).

It runs on Windows, macOS and Linux: on a desktop (virtual hardware, optionally MPF Monitor), in Visual
Pinball X with MPF replacing PinMAME (Windows), and optionally with TerryRed's PuP Pack on three extra screens.

The method (how a Stern SAM ROM becomes an MPF game) is not in this repository: it is game agnostic and lives
in [Ashram56/Stern-SAM-Decryption](https://github.com/Ashram56/Stern-SAM-Decryption) (public). See section 8.

## 2. Repository map

| Path | What | Notes |
|---|---|---|
| `game/` | The MPF machine folder and the Godot project (`project.godot`, `gmc.cfg`) | |
| `game/config/config.yaml`, `hardware.yaml`, `free_play.yaml` | MPF config | `hw_virtual.yaml` (default), `hw_vpx.yaml` (VPX) are hardware overlays |
| `game/config/rom/` | **Generated** device config (switches, coils, lights, settings, P-ROC numbers) | git-ignored; `scripts/gen_config.py` writes it from `rom/mpf_package/config/`. Never edit it, fix the generator or the package |
| `game/config/interim/` | Tables read from the ROM until the package carries them | `scripts/interim_tables.py`, `interim_fonts.py` (need the ROM, section 6) |
| `game/tf/` | The game's Python: OS layer (`os_layer.py`: ball search, task timing), display (`display.py`, `score_screen.py`, `rom_draw.py`), lamps, switches, settings, credits, traces, virtual and VPX hardware | Godot side: `rom_screen.gd`, `rom_fonts.gd`, `deff_values.gd` |
| `game/tf/features/` | One file per rule feature: `battles.py`, `megatron.py`, `optimus.py`, `wizard.py`, `combos.py`, `energon.py`, `allspark.py`, `bonus.py`, `side.py`, `skill_shot.py`, `pops.py`, `spinner.py`, ... | Each follows its spec in `rom/rules/modes/` |
| `game/modes/attract/`, `game/slides/` | MPF modes and GMC slides | |
| `game/monitor/` | MPF Monitor layout (`monitor.yaml`) and playfield picture from the VPX table | |
| `game/pup.cfg`, `game/tf_pup/trigger_map.yaml`, `game/modes/pup/` | This game's PuP Pack integration | section 5 |
| `game/pup_runtime/`, `game/pup/`, `scripts/pup_*.py`, `scripts/gen_pup.py` | **Copies** of the shared PuP runtime | never edit here (section 5) |
| `pup_addons/` | Video add-ons for Godot (GDE GoZen, `native_video`), copied into `game/addons/` by setup | the macOS `native_video` build carries a heap fix: never replace it with the upstream zip |
| `pup_pack/` | Git submodule: the private PuP Pack repository [Ashram56/Transformers-PuP](https://github.com/Ashram56/Transformers-PuP) | section 5 |
| `rom/` | The ROM extraction: tables (`rom_data/`), the MPF package (`mpf_package/`: config, sounds, DMD frames, 111 lamp shows), the rules specs (`rules/modes/*.md`, `rules/switch_handlers.csv`), the reference traces (`rules/traces/`), the Ghidra decompile (`code/tf_decompiled.c`), the readers and emulator probes (`tools/`) | [rom/README.md](rom/README.md). The ROM image itself is never here |
| `scripts/setup.py`, `scripts/toolchain.py` | Setup: venv, MPF, Godot, GMC, generated media, PuP; the pinned versions live in `toolchain.py` | idempotent, safe to repeat |
| `scripts/run.py` | Starts the game (MPF + Godot, optionally MPF Monitor, VPX) | `--help` lists the options |
| `scripts/gen_config.py`, `gen_media.py`, `gen_fonts.py` | Generators from `rom/` into `game/` | |
| `scripts/trace_check.py`, `lamp_state.py`, `coil_state.py` | Compare the game against the ROM's reference traces | section 4 |
| `scripts/render_check.py` | Runs Godot + MPF headless and writes `captures/dmd_latest_x8.png` | for display work |
| `scripts/vpx_table.py`, `vpx_bridge.py`, `game/tf/vpx_hardware.py`, `docs/vpx.md` | The VPX bridge (COM server `TransformersMPF.Controller`, BCP) | Windows only |
| `scripts/install/`, `setup.bat`, `setup.ps1`, `setup_workspace.sh` | The one-line installers per OS | README "Install" |
| `scripts/package/` | Game side of the prebuilt bundle (settings schema, import template); the package contract `game_package.json` and its completeness check are this game's; MPF-Godot-Packaging only turns the package into a bundle | none |
| `tests/` | pytest: boot, switches, display, sounds, PuP, VPX, install; `tf_test.py` is the MPF test base, `scenario.py` replays traces | |
| `.github/workflows/test.yml` | CI: setup + tests on Windows, macOS, Linux, render check on Linux | runs only on pushes to `main` |
| `docs/` | `rom_differences.md`, `pup.md`, `pup_captures.md`, `vpx.md`, `vpx/`, `hardware.md`, `requirements.md` | |

Generated and git-ignored (rebuilt by setup, never committed): `.venv/`, `tools/` (Godot), `game/addons/`,
`game/config/rom/`, `game/sounds/`, `game/media/`, `game/fonts/`, `game/slides/deffs/`, `captures/`,
`pup_media/`, `game/pup.local.cfg`.

[CLAUDE.md](CLAUDE.md) has which of the project's agents owns which files; useful when you need the matching
method file in Stern-SAM-Decryption.

## 3. Set up and run

Prerequisites: Git, Python 3.11 (what CI and the installers pin; MPF Monitor is installed only below 3.13), and a
GPU that runs Godot 4.6 (the project uses the mobile renderer). [docs/requirements.md](docs/requirements.md) has the details per OS.

```sh
git clone https://github.com/Ashram56/Transformers-MPF.git
cd Transformers-MPF
git submodule update --init pup_pack       # the PuP Pack: needs read access to Ashram56/Transformers-PuP
python3.11 scripts/setup.py                # Windows: py -3.11 scripts\setup.py
```

`setup.py` creates `.venv/`, installs MPF and GMC, downloads Godot 4.6.3 into `tools/`, generates the config
and media from `rom/`, sets up the PuP and runs Godot's import. The first run is long. Useful flags:
`--skip-godot` (MPF and tests only), `--skip-media`, `--no-monitor`, `--vpx` (Windows), `--dry-run`. The
one-line installers in the README do the same from nothing.

Run (from the repository folder; Windows uses `.venv\Scripts\python`):

| Command | What |
|---|---|
| `.venv/bin/python scripts/run.py` | the game, free play, desktop DMD window |
| `... run.py --monitor` | also MPF Monitor: click switches on the playfield picture |
| `... run.py --hw vpx` | Visual Pinball X with MPF instead of PinMAME (Windows, after `setup.py --vpx`; [docs/vpx.md](docs/vpx.md)) |
| `... run.py --no-free-play` | factory pricing (key `5` inserts a coin) |
| `... run.py --scenario basic --seconds 60` | replays the trace scenario `rom/rules/traces/basic.txt` in real time |
| `TF_PUP=0 ... run.py` | **strict ROM mode**: PuP off, the ROM's own music |
| `TF_VIDEO_PLAYER=native ... run.py` | the PuP videos through `native_video` instead of GoZen |

Keys in the DMD window: `5` coin, `1` start, `Space` plunge, `Z` and `/` flippers, `T` tilt, `D` coin door,
`7` `8` `9` `0` service BACK, MINUS, PLUS, SELECT (`game/gmc.cfg`). Godot's log is `game/logs/godot.log`.

## 4. Test before every push

CI runs only on pushes to `main`, never on branches or pull requests: **you test locally**.

```sh
.venv/bin/python -m pytest -q tests                      # always
.venv/bin/python scripts/render_check.py                 # display work: look at captures/dmd_latest_x8.png
.venv/bin/python scripts/trace_check.py basic            # rules work: any scenario in rom/rules/traces/
.venv/bin/python scripts/trace_check.py basic --events score,deff_start,lamp,coil
```

The PuP tests skip without the `pup_pack` submodule (CI does not check it out). After a rules change run the
trace checks of every scenario that covers the feature (the table in `rom/rules/traces/README.md` and the
scenario names: `battle_*`, `megatron_*`, `optimus_*`, `wizard_*`, `combos`, `allspark_energon`, ...).
Scores, display effects and audits match the ROM in all 24 traces today: a change that breaks one is a
regression unless the ROM says otherwise.

## 5. The PuP Pack

The game can play **TerryRed's Transformers (Stern) PuP-Pack** (v1.0, PinUP Player set `tf_180`) the way
PinUP Player does in Visual Pinball. All of it is in [docs/pup.md](docs/pup.md); the essentials:

- **Where it is.** The pack is TerryRed's work. Players get it from the author's download page and install it
  with `TF_PUP_ZIP=<zip or https URL>`. The owner's private, byte-for-byte copy is
  [Ashram56/Transformers-PuP](https://github.com/Ashram56/Transformers-PuP) (`tf_180/`), checked out here as the
  `pup_pack` submodule. **Never copy any of the pack's files (videos, images, music, its muted ROM) into this
  public repository**, and never commit the pack's ROM to either repository. The pack repository is changed
  only to update the pack from a new release of the author's zip.
- **Three screens.** `backglass` (16:9, background and mode videos with the pack's crests, faces and text
  panel; PuP screens 2, 11-15), `dmd` (the game's DMD in the pack's panel art) and an optional `topper`
  (screen 0). The pack's music (screen 4) **replaces the ROM's music** when the PuP is on; speech and effects
  stay the ROM's. `TF_PUP=0` (or `[pup] enabled=false`) gives the strict ROM game.
- **Video playback.** The pack's MP4s play as they are, decoded on the GPU: **GDE GoZen** (FFmpeg) on Windows and
  Linux, `native_video` (AVFoundation) on macOS; `native_video` (Media Foundation) is the Windows fallback.
  Theora conversion (`scripts/gen_pup.py`) is only the last fallback. `scripts/video_check.py` reports the
  decoder and speed.
- **Per-cabinet settings** go in `game/pup.local.cfg` (git-ignored, same sections as `game/pup.cfg`). Do not
  put cabinet settings in `game/pup.cfg`.
- **How triggers work.** In VPX, PinUP Player fires `D<n>` when a capture's pixels appear on PinMAME's DMD.
  Here the game posts `tf_deff_<id>` when display effect `<id>` takes the DMD (`game/tf/display.py`), and
  `game/tf_pup/trigger_map.yaml` maps each `D<n>` to its effects (with conditions on the event's arguments for
  the variants: battle shots left, lock number, side, animation index). `scripts/pup_captures.py` rebuilds the
  match in `docs/pup_captures.md`. A hand-set or ROM-checked line says so and gives the ROM address.
- **The runtime is shared.** `game/pup_runtime/`, `game/pup/`, `scripts/pup_setup.py`, `scripts/gen_pup.py`,
  `scripts/pup_captures.py`, `scripts/pup_decode.py` are copies of Stern-SAM-Decryption
  `tools/pup/runtime/`. **Do not edit the copies**: a runtime fix goes to Stern-SAM-Decryption (section 8) and
  comes back by running its `install.py`. This game's own PuP files are `game/pup.cfg`,
  `game/tf_pup/trigger_map.yaml`, `game/modes/pup/` and the hooks in `docs/pup.md`.

## 6. The ROM

The ROM image `tf_180.bin` (30,560,052 bytes, SHA1 `62e1328e8462680694157aca266055d57347e904`) is
copyrighted. **It is never committed, to any repository, in any form** (`.gitignore` blocks `*.bin` and
`tf_*.zip`; do not force it). You do not need it to build, run or test the game: everything the game uses is
already extracted in `rom/`. You need your own copy only to re-read tables or run the extraction tools:
`TF_ROM=/path/to/tf_180.bin python rom/tools/<tool>.py` (`rom/tools/rom.py` is the reader;
`scripts/interim_tables.py` and `interim_fonts.py` take the same variable). The emulator probes and the
reference tracer (`rom/tools/emu/`, `rom/tools/trace/`) need libpinmame; see `rom/tools/trace/README.md` and
`rom/README.md`.

Fact tags used throughout `rom/` and the docs: **code** (read from the ROM or its decompile, with the address),
**observed** (seen in the emulator or a trace), **inferred** (a guess, say so).

## 7. Rules for every change

1. **Strict to the ROM.** The game reproduces tf_180, quirks included (`docs/rom_differences.md` lists ROM
   quirks that are not bugs: do not "fix" them). A behaviour change must be backed by the ROM: the spec in
   `rom/rules/modes/`, the decompile `rom/code/tf_decompiled.c`, or a reference trace in `rom/rules/traces/`.
2. **Cite the ROM.** Rules code and docs give the ROM address of what they reproduce, in the house form
   `[0x0101db34]` (a function or table in the game code, which starts at 0x01000000), plus the trace and time
   when the evidence is a trace (`scoring.jsonl 153.46 s`). Say when a value is inferred.
3. **Every departure gets a row** in `docs/rom_differences.md` (area, what the ROM does, what the game does,
   kind: interim, inferred, timing, MPF limit, option). Remove the row when the departure is fixed.
4. **Improvements are switchable.** Anything that is not the ROM (HD display, new looks, the PuP's music) is an
   option, with the ROM's behaviour one setting away, and a row in `docs/rom_differences.md`.
5. **Generated files are not edited.** Change `rom/` or the generator, then rerun `scripts/setup.py` (or the
   generator); the tests rerun `gen_config.py` themselves.
6. **Match the code around you.** Short docstrings that say what and why, the ROM address next to the
   behaviour, no new dependencies without adding them to `scripts/toolchain.py` and the installers.
7. **Docs travel with the code.** Update the README's tables, `docs/*.md` or `rom/README.md` when what they say
   changes.
8. **Test** (section 4) before every push.
9. **Never commit**: the ROM, the PuP Pack's media, anything third-party or private, tokens or credentials.

Typical tasks:

| Task | Where to look | Check with |
|---|---|---|
| A rule scores or behaves differently from the real game | the feature in `game/tf/features/`, its spec in `rom/rules/modes/`, the handler in `rom/rules/switch_handlers.csv`, the decompile | the trace scenarios covering it; add a test in `tests/` |
| A display effect looks wrong | `game/tf/display.py`, `score_screen.py`, `rom_draw.py`, `deff_values.gd`, the capture in `rom/mpf_package/media/dmd/deffs/deff_NNN/` | `render_check.py` |
| A sound is wrong or missing | `rom/rom_data/sound/sound_call_uses.csv`, `rom/mpf_package/config/sounds.yaml`, the feature that calls it | `tests/test_sounds.py`, the `sounds` trace |
| A PuP video plays at the wrong moment | `game/tf_pup/trigger_map.yaml`, `docs/pup_captures.md` | `tests/test_pup.py`, a play test with the submodule |
| VPX does not drive a device | `game/tf/vpx_hardware.py`, `game/config/hw_vpx.yaml`, `docs/vpx.md` "Device map" | `tests/test_vpx.py` |
| Install or run breaks on an OS | `scripts/setup.py`, `scripts/toolchain.py`, `scripts/install/` | `tests/test_install.py`, `setup.py --dry-run --os <os>` |

## 8. Game facts here, methods in Stern-SAM-Decryption

[Ashram56/Stern-SAM-Decryption](https://github.com/Ashram56/Stern-SAM-Decryption) holds what every Stern SAM
game shares: the master plan and agent files (`agents/README.md`, `rom_extraction.md`, `recreation.md`,
`vpx_bridge.md`, `packaging.md`, `pup_pack.md`, ...), the knowledge base (`knowledge/`, notably
`sam_to_mpf_playbook.md`) and the shared tools (`tools/`, including the PuP runtime). Read the agent file for
your kind of task before a large change: it explains how the parts were built and the mistakes already made.

- **Game facts stay here**: this game's addresses, values, status, owner decisions.
- **Game-agnostic learnings go there**: a fact true of every SAM ROM, MPF, GMC, Godot, VPX or PinMAME
  behaviour, a method that worked or failed, a fix to a shared tool or the PuP runtime. Its
  [CONTRIBUTING.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/CONTRIBUTING.md) is the rule:
  - **With write access**, a pull request editing the file that owns the topic, titled
    `Knowledge: <topic> (from Transformers)`.
  - **Without write access (the usual case for a contributor)**, open a **GitHub issue** on
    Ashram56/Stern-SAM-Decryption with its "knowledge update" template, titled
    `Knowledge: <topic> (from Transformers)`: the finding, its fact tag, the evidence (this game's value as the
    example, e.g. an address or a trace), the file and section it belongs in, and the exact text to add. For a
    code fix to a shared tool, put the diff in the issue, or open a pull request from your fork. Do it in the
    same session as the finding; you do not need to ask anyone first.
  - Nothing private or ROM-derived goes there (no ROM data, no PuP media, no tokens).

## 9. Contributing workflow

1. Branch from `main` (or work on a fork if you cannot push here). One topic per branch.
2. Make the change following section 7; run the tests (section 4).
3. Commit with a message that says what changed and why (the ROM address or trace when it is a rules fix).
4. Open a pull request against `main`: what changed, the ROM evidence, what you ran. The owner reviews and
   merges; a push to `main` runs CI on all three OSes.
5. A change to the PuP Pack itself (a new pack release) is a separate pull request on
   Ashram56/Transformers-PuP, then a submodule bump here.
6. Report game-agnostic learnings to Stern-SAM-Decryption (section 8) and say in your pull request which issue
   or PR you opened.

When a change needs the owner's judgement (a look and feel choice, a departure from the ROM), pick a sensible
default, say which in the pull request, and list the open questions as a short numbered list.
