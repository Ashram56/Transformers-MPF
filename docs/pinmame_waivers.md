# Emulator-capture waivers (STRICT RULE item 4)

The strict rule ([CLAUDE.md](../CLAUDE.md)) forbids building a rule, value, image or DMD render from a PinMAME
capture or trace. A capture is allowed only as a last resort, **with Vincent's approval asked beforehand**, and
recorded here as a line `` `path` ... approved by Vincent YYYY-MM-DD `` (the form `tools/check_strict_rule.py`
reads). A path not approved here fails the check.

## Captured data the game uses today (found by the QA pass of 2026-11-25)

None of these is approved: they were built before the rule. **Owner decision 2026-11-25: no waiver.** Each one
is decoded from the ROM by agent A, then the game switches to the decoded data; until then the check fails on
them and they stay in the game.

| Path | What was captured | What the ROM holds instead (to decode) | Status |
|---|---|---|---|
| `rom/mpf_package/media/dmd/deffs` | 153 display effects: frames, run lengths (`ended_ms`), sounds and leffs started inside each effect, recorded by `rom/tools/emu/tracer.cpp` | each deff's draw function (table of 155 deffs, `rom_data/dmd/deffs.csv` gives the function); its images (already exported from the ROM: `rom_data/dmd/`), its text draws (`deff_text_formats.csv`, from the decompile) and its `task_sleep` calls give the frames and the length | refused 2026-11-25: decode |
| `rom/mpf_package/config/shows` | 111 lamp effects (leffs) as MPF shows, recorded on every lamp compositor tick by `rom/tools/emu/lfx.cpp` | each leff's function (leff table 0x040cfe00, `rom_data/io/lamp_effects.csv`) and the 148 lamp groups (table 0x040d1510) | refused 2026-11-25: decode |
| `rom/rom_data/io/coils.csv` (column `mpf_source`, from `coil_timing.csv`) | coil pulse and hold times measured from the solenoid register writes in the emulator | the coil descriptors (test and ball-search ms already read: `test_pulse_ms`), the game's `coil_pulse` call arguments and the OS pulse routine | refused 2026-11-25: decode |
| `rom/rom_data/settings/adjustments.csv` | the display text of 143 adjustment values, from the OS formatter run in the emulator | the formatter 0x0002aebc and its message tables (the values and ranges themselves are read from the ROM) | refused 2026-11-25: decode |

## Approved captures

| Path | Why | Approval |
|---|---|---|
| `rom/rules/traces/tilt_ball_save.jsonl` | QA F15: does the ball save survive a tilt? The code read leaves it open (the hooks of events 0x65 / 0x66 not read); one reference trace, tilt during the ball save then a drain, used only to confirm the code | approved by Vincent 2026-11-25 |

Not waivers (allowed by the rule): the reference traces `rom/rules/traces/` and their scenarios confirm the game,
they are not a source; `game/tools/dmd_capture.gd` saves the game's own DMD for `scripts/render_check.py`, it
builds nothing.

Last updated 2026-11-25.
