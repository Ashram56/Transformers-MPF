# Emulator-capture waivers (STRICT RULE item 4)

The strict rule ([CLAUDE.md](../CLAUDE.md)) forbids building a rule, value, image or DMD render from a PinMAME
capture or trace. A capture is allowed only as a last resort, **with Vincent's approval asked beforehand**, and
recorded here as a line `` `path` ... approved by Vincent YYYY-MM-DD `` (the form `tools/check_strict_rule.py`
reads). A path not approved here fails the check.

## Captured data the game uses today (found by the QA pass of 2026-11-25)

None of these is approved: they were built before the rule. **Owner decision 2026-11-25: no waiver.** Each one
is decoded from the ROM by agent A, then the game switches to the decoded data; until then the check fails on
them and they stay in the game.

| Path | What was captured | Decoded from the code (agent A, 2026-11-25) | Still open |
|---|---|---|---|
| `rom/mpf_package/media/dmd/deffs` | 153 display effects: frames, run lengths (`ended_ms`), sounds and leffs started inside each effect, recorded by `rom/tools/emu/tracer.cpp` | **all 153** now come from the deff's own code: `rom/tools/deff_lift.py` runs the deff function as ROM code with the OS calls answered in Python (sleep, tasks, sound, show), `rom/tools/deff_render.py` draws the op list with the ROM's primitives, images and fonts, `rom/tools/deff_package.py` writes the frames and `timing.json` (`"tag": "code"`) plus the op list `rom/rom_data/dmd/deff_ops/deff_NNN.json`. Of these, 84 reproduce every captured frame, 26 had no capture at all, 7 differ only in the value texts the game draws live The 38 drawn from game state (ids 1 3 14 16 18 19 25 32 33 34 36 48 50 51 58 64 66 70 71 72 76 81 87 97 101 105 113 121 123 126 127 135 139 140 147 149 150 152) run with the state their caller sets (`rom/tools/deff_variants.py`: task arguments stored after `deff_start`, RAM such as the shots left of a battle or the tournament record, the random pick of a video), one run per state, each cited to the routine that sets it; the first is packaged, the others are op lists `deff_NNN__<name>.json`. The edit cursor routine 0x0002b808 that writes the page directly is modelled (op `invert`) | none |
| `rom/mpf_package/config/shows` | 111 lamp effects (leffs) as MPF shows, recorded on every lamp compositor tick by `rom/tools/emu/lfx.cpp` | **all**: `rom/tools/leff_lift.py` runs each leff function as ROM code (the lamp library and layers too) and re-does the compositor 0x000073cc each tick; `rom/tools/leff_package.py` writes 113 shows (2 more than captured: 99, 102) and `rom_data/io/lamp_effects.csv`, `tag` code. Leffs 46, 54, 62, 70, 104 blink the entries lit in a game word: run with every bit set | none |
| `rom/rom_data/io/coils.csv` (column `mpf_source`) | coil pulse and hold times measured from the solenoid register writes in the emulator | **33 of 35**: `rom/tools/coil_pulses.py` (every constant `coil_pulse` call, the leffs' pulses, the OS pop table 0x040ddfb0 and slingshot table 0x040ddfe0 of the 1 ms IO pass 0x000114b0, the shaker table 0x040c7620); one row per call site in `rom_data/io/coil_pulses.csv` | flippers 15, 16 (no flipper drive found in the CPU code yet): their emulator times stay, approved by the owner below |
| `rom/rom_data/settings/adjustments.csv` | the display text of 143 adjustment values, from the OS formatter run in the emulator | **all**: the 15 formatter functions are run as ROM code (`rom/tools/adj_format.py`; each one's logic, read from the decompile, is listed there: 0x0002aebc is `sprintf("%d")`); factory defaults read from the U.S.A. country record | none |

## Approved waivers

- `rom/rom_data/io/coils.csv`: the flipper times of coils 15 and 16 (pulse 40.5 / 40.6 ms, hold 0.083 / 0.084) stay as measured in the emulator until the flipper drive is found in the code, approved by Vincent 2026-11-25.
  This is the only measured data left in the file: every other row comes from the code (`rom/tools/coil_pulses.py`),
  coil 24 (Q24, the knocker) included: 64 ms at FUN_00019420.

## Owner decisions on the method (2026-11-25)

- Running the ROM's own code in Unicorn (the ROM image only, the OS services answered in Python: `rom/tools/coderun.py`)
  counts as decoding from the code (Vincent, 2026-11-25).
- The tick is the code's: 64 IO interrupts of 250 us = **16.0 ms** [0x000114b0], not the 16.26 ms measured in the
  emulator (Vincent, 2026-11-25). The decoded deffs and lamp shows use it (`TICK_MS` of `deff_package.py`,
  `leff_package.py`).

## Approved captures

| Path | Why | Approval |
|---|---|---|
| `rom/rules/traces/tilt_ball_save.jsonl` | QA F15: does the ball save survive a tilt? Answered from the code since 2026-11-26: the tilt's `task_kill(0, 0x1000)` [0x0001dbb4] ends the save task 0x31 (flags 0x300, [0x00017acc]), so no save after a tilt (`rom/rules/modes/game_flow.md` 5.4, run in ROM code by `rom/tools/scenario_lift.py`). The reference trace, tilt during the ball save then a drain, only confirms it | approved by Vincent 2026-11-25 |

Not waivers (allowed by the rule): the reference traces `rom/rules/traces/` and their scenarios confirm the game,
they are not a source; `game/tools/dmd_capture.gd` saves the game's own DMD for `scripts/render_check.py`, it
builds nothing.

Last updated 2026-11-25.
