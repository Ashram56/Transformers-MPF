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
| F13 | the OS-layer files cite tf_180's routines, not Tron 1.74's: about 110 citations (bracketed addresses, `FUN_` names, RAM and the power table) re-cited by matching each Tron routine of Tron-Legacy-LE-ROM-Decryption `code/tron_game_decompiled_v2.c` against the tf_180 decompile (normalised bodies), ties settled by reading both; still marked Tron: the score-display music rules (Tron 0x0100f594 / 0x0100f5c8), no tf_180 match yet (`any_multiball` cites tf_180's `0x01006704`) | e.g. serve_ball `0x0103b39c`, score_add `0x0001caf0`, multiball_start `0x0103aec0`, end of ball `0x00019e44`, slam `0x0001d534` |

| P2 | the lit shot multiplier is raised before the shot's combo award (FUN_010237ac first in every shot handler) | `0x010237ac`, `0x01033824` |
| P3 | the skill shots end on any 3 distinct switches posting event 0x6b (slings and pops count) | hook `0x010313cc` |
| P4, P5 | mystery item 10 weight 0 only with a lit multiplier or the roving 3X; double and fast scoring starts clear flag 0x13 | `0x01023494`, `0x010039a0`, `0x01004394` |
| P6, P12, P16 | double scoring: the countdown never pauses, 0x285 once per run at the first count in 5..10, 125-tick tail, ADD MORE TIME in the tail revives it | `0x010038dc`, `0x0100393c`, `0x0100396c`, `0x01003a8c` |
| P7, P8, P9 | fast scoring: pops and top lanes hold it 156 ticks; 11 x 6-tick steps; +1,000 on a cycle's first target only, leffs 144 / 145, +10 counts on the completing hit; the tails are not timed modes | `0x01032f8c`, `0x01004220`, `0x010047b8`, `0x010067bc` |
| M5, P10, P11 | the center lane / Optimus lockout is task 0x54 (62 ticks, started by sw 51); sw 51 ignored while 0x54 or 0x4e run; the fast award and double sounds in every handler but sw 6's | `0x01033d3c`, `0x01033b3c`, `0x010332e4` |
| F4, F5 | a held plumb bob warns every 62 ticks then tilts (task 0x2e); the bob counts in the end of ball and a tilt there removes the bonus | `0x0001dc58`, `0x0001dc14`, `0x00019e44` |
| F6 | an equal-priority deff replaces the running one only when its flags & 3 | `0x00020498` |
| F10 | the end of ball waits for the longest flag-0x2000 task, at most 937 ticks | `0x00019e44`, DAT_00033324 |
| F11 | the Megatron lock entry adds a bonus count and resets the ball search | `0x0100a31c` |
| M6 | the super-lit leffs 47 / 55 / 63 / 71 pulse their coil group every 8 ticks (a higher leff owning the flashers wins); Megatron's run by their lamp rules | `0x010286f8`, `0x0102a83c`, `0x0100d038`, `0x0100ef64`, `0x0100d004`, `0x0100ef30` |
| M7 | ADD-A-BALL offered while a multiball flag is set or in the first 156 ticks of its end task; award with ball save 312 / grace 187 | `0x01006760`, `0x01024a20`, `0x01024a60`, `0x0100c7e8` |
| M9 | Starscream's lit pair moves each counted second with fewer than 6 shots left, unless a ramp entrance in the last 93 ticks | `0x01017824`, `0x010337e8`, `0x010338dc` |
| F7 | each decoded deff holds for its own tail (1, 2 or 10 ticks), read from agent A's op lists | `0x0103058c`, `0x0002108c` |
| F8 | ball save: ends when fewer than 7 ticks are left (adj 38 = 5: 312 ticks) | `0x00017a28` |
| P13, P17, P18, P20 | skill shot second lane lamp 50 / 49; spinner sample index reset each ball; deff 124 arg 0 before the new bit; item 4 text capped at 25 | `0x010335d0`, `0x0103361c`, `0x01032484`, `0x010309a4`, `0x01000f18` |
| M10, M15 | the lock re-arm copies every player's count (ROM quirk kept); deff 139 gets the locked count | `0x0100af0c` |
All 24 trace scenarios give the same comparison before and after these fixes, except two coil burst counts that M6 moves (megatron_decepticon, optimus_autobot); the trace replay runs at the code's 16.0 ms tick, scaled to the traces' 16.15 ms (counted on code-timed spans; the 16.26 ms used before drifted 0.3 s over a battle and gave battle_blackout an extra bonus).

### Open (proved, not fixed yet)

High first. Each line's detail, proof and game line are in its report.

| id | What | Sev |
|---|---|---|
| F9b | match sounds 0x072 / 0x074 when matched; award inside deff 38 | medium |
| F15 | ball save may survive a tilt (doubtful: hooks of events 0x65 / 0x66 not read) | medium if true |
| F9a, F9c, F12, F14, F16-F18, M8, M11, M12, M14, P14, P15, P19 | smaller differences (lengths, ids, args, sample picks, rare adjustments) | low |

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
