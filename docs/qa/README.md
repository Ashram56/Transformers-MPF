# QA against the strict rule

The owner's strict rule of 2026-11-24 ([CLAUDE.md](../../CLAUDE.md)) and the audit method of MPF-Godot-Packaging
`agents/recreation.md` ("have the rules reviewed against the decompile": independent read-only reviewers, one
scope each, every finding proved; the review fixes nothing, the fixes follow from the reports). One folder per
pass.

## Pass of 2026-11-25

Three independent read-only reviews, each with the decompile, the ROM and the game in its test harness:

| Scope | Report | Probes | Findings |
|---|---|---|---|
| OS layer and game flow | [report_os.md](2026-11-25/report_os.md) | [probe_os.py](2026-11-25/probe_os.py) | 18 (F1-F18) |
| Modes and multiballs | [report_modes.md](2026-11-25/report_modes.md) | [probe_modes.py](2026-11-25/probe_modes.py) | 15 (M1-M15) |
| Playfield scoring | [report_playfield.md](2026-11-25/report_playfield.md) | `probe_playfield_*.py` on [qa_base.py](2026-11-25/qa_base.py) | 20 (P1-P20) |

Run a probe file from the repository folder: `.venv/bin/python -m pytest -q -s -p no:cacheprovider
docs/qa/2026-11-25/probe_os.py` (the playfield ones need `--rootdir docs/qa/2026-11-25`). A probe prints what
the game does next to what the ROM does; after a fix it prints the ROM's value. The probes were written against
the game before the fixes; the regression tests are in [tests/test_qa_2026_11_25.py](../../tests/test_qa_2026_11_25.py).

### The strict rule, mechanically (`python tools/check_strict_rule.py .`)

| Check | State |
|---|---|
| Rule text in CLAUDE.md | passes |
| `docs/boards_inventory.md` | written; **fails**: the ARM game program is `partiel` (deff and leff scripts not decoded, coil pulses measured, 2,526 functions unnamed), the two Xilinx XC95144XL CPLDs `absent` (flash fuse map, only readable through the J8 JTAG header of a real board; owner to say whether it counts) |
| Captured data | **fails** for 266 files: 153 deff captures, 111 leff shows, `coils.csv` (pulses), `adjustments.csv` (value texts); listed in [pinmame_waivers.md](../pinmame_waivers.md); no waiver (owner, 2026-11-25): agent A decodes them |
| Functional diagram | passes: [functional_diagram.md](../functional_diagram.md), assembled after the fact from A's specs, each address checked by `tests/test_functional_diagram.py` |

### Fixed in this pass (each with a regression test)

| id | What | ROM |
|---|---|---|
| F1 | the right orbit collects a lit extra ball (deff 54) | `0x01033488` → `0x01007b74` |
| F2, F3 | special lit with lamp 53 and deff 55, collected at the right orbit with deff 56; extra ball lit shows deff 53 | `0x01008528`, `0x01008684`, `0x01007b40` |
| M1 | every multiball keeps scoring in its 218-tick end window (wizard: 312) | gates `0x0100be84`, `0x0100dec0`, `0x010276e0`, `0x01029754`, `0x01036590` |
| M2 | Megatron Decepticon progress saved per player with adj 88 YES | `0x0100e0bc` |
| M3 | Megatron Autobot doubles do not time out before M = 3 | `0x0100c10c` |
| M4 | Optimus Decepticon super x the center lane multiplier | `0x01029bf4` |
| M13 | the never-set grace flags 0x26 / 0x2a are no longer set | grep: only `game_flag_clear` |
| P1 | BONUS HOLD and BONUS X HOLD last one ball; no held bonus stored when tilted | `0x01000d58`, `0x01000f68` |

All 24 trace scenarios give the same comparison before and after these fixes (no trace reaches them).

### Open (proved, not fixed yet)

High first. Each line's detail, proof and game line are in its report.

| id | What | Sev |
|---|---|---|
| F13 | `os_layer.py`, `display.py`, `lamps.py`, `credits.py`, `settings.py`, `high_scores.py`, `slam_tilt.py` cite Tron 1.74 OS addresses, wrong in tf_180 (rule 3: re-cite every one to the tf_180 routine) | high |
| M5, P11 | center lane / Optimus lockout: only task 0x54 (started by sw 51) blocks sw 11; sw 51 blocked by 0x4e / 0x54 | medium |
| F4, F5 | held plumb bob tilts after 124 ticks; the bob is taken in the end of ball and bonus | medium |
| F6, F7 | deff equal priority needs flags & 3; hold tail per deff (1, 2, 10, 15, 41 ticks) | medium |
| F9b | match sounds 0x072 / 0x074 when matched; award inside deff 38 | medium |
| F10 | end-of-ball wait: every flag-0x2000 task, up to 937 ticks | medium |
| F11 | Megatron lock entry adds the bonus count and resets the search | medium |
| M6 | super-lit flasher leffs 47 / 55 / 63 / 71 (coil groups every 8 ticks) | medium |
| M7 | add-a-ball offered in the first 156 ticks of the end window, with ball save 312 / grace 187 | medium |
| M9 | Starscream's lit pair moves each second | medium |
| P2 | the shot multiplier is raised before the combo award | medium |
| P3 | skill shot end: any 3 distinct switches posting 0x6b (slings, pops, 45, 51 count); `tests/test_switches.py` asserts the wrong value | medium |
| P4, P5 | mystery item 10 weight; flag 0x13 cleared by double and fast scoring starts | medium |
| P7, P8, P9 | fast scoring pause on pops / top lanes; 2-bank cycle values and leffs 144 / 145; timed-mode tails are not timed modes | medium |
| F15 | ball save may survive a tilt (doubtful: hooks of events 0x65 / 0x66 not read) | medium if true |
| F8, F9a, F9c, F12, F14, F16-F18, M8, M10-M12, M14, M15, P6, P10, P12-P20 | smaller differences (lengths, ids, args, sample picks, rare adjustments) | low |

### For agent A (one batched request)

The spec errors the reviews found are at the end of each report (game_flow.md 7, megatron_multiball.md 4,
optimus_multiball.md 2, wizard_modes.md 1, scoring_features.md 3, allspark_and_energon.md 1,
combos_and_multipliers.md 1). Decoding still needed for the strict rule: each deff's draw function (frames,
length, hold tail, sounds), each leff's function and the lamp groups (table 0x040d1510), the coil pulses of the
game's `coil_pulse` calls, the adjustment value formatter 0x0002aebc, the ball search task `0x0103b778`, the serve
and multiball tasks (`0x0103b39c`, `0x01039db4`, `0x0103aba4`).

### Owner decisions

1. Decided 2026-11-25: no waiver for the captured data; agent A decodes it ([pinmame_waivers.md](../pinmame_waivers.md)).
2. Whether the two Xilinx XC95144XL CPLDs (fuse map, no program, not loaded by the ROM) count as a board to decompile.
3. F15: confirming the tilt / ball save case needs a new reference trace, which is an emulator capture.
