# QA against the strict rule

The owner's strict rule of 2026-11-24 ([CLAUDE.md](../../CLAUDE.md)) and the audit method of MPF-Godot-Packaging
`agents/recreation.md` ("have the rules reviewed against the decompile": independent read-only reviewers, one
scope each, every finding proved; the review fixes nothing, the fixes follow from the reports). One folder per
pass.

## Pass of 2026-11-26: the MPF conversion against the ROM code

Owner, 2026-11-26: the QA matrix also covers the conversion to MPF (configs, generated config, shows, Python and
GDScript) and checks it against the decompiled code, not against the specs. Five independent read-only reviews,
each one matrix row per element of its scope (verdicts: match, differs, missing, extra, unverifiable):

| Scope | Matrix | Report | Rows | match | differs | missing | extra | unverifiable |
|---|---|---|---|---|---|---|---|---|
| MPF devices, settings, audits, pricing, service menu | [matrix_devices.csv](2026-11-26/matrix_devices.csv) | [report_devices.md](2026-11-26/report_devices.md) | 830 | 705 | 29 | 59 | 3 | 34 |
| Display: 155 deffs, deff engine, score screen, fonts, text formats | [matrix_display.csv](2026-11-26/matrix_display.csv) | [report_display.md](2026-11-26/report_display.md) | 182 | 89 | 40 | 18 | 1 | 34 |
| Lamps: 178 leffs, 148 lamp groups, inserts, lamp rules, engine | [matrix_lamps.csv](2026-11-26/matrix_lamps.csv) | [report_lamps.md](2026-11-26/report_lamps.md) | 412 | 118 | 112 | 60 | 0 | 122 |
| Sounds (every call site) and rule-driven coils | [matrix_sounds_coils.csv](2026-11-26/matrix_sounds_coils.csv) | [report_sounds_coils.md](2026-11-26/report_sounds_coils.md) | 900 | 306 | 68 | 492 | 0 | 34 |
| Rules: switch handlers, code runs, functional diagram, cited addresses, constants | [matrix_rules.csv](2026-11-26/matrix_rules.csv) | [report_rules.md](2026-11-26/report_rules.md) | 771 | 643 | 81 | 4 | 9 | 34 |
| **total** | | | **3,095** | **1,861** | **330** | **633** | **13** | **258** |

Each matrix is rebuilt by the `probe_*` script next to it (command in its report). Scores equal the ROM code on all
58 switch rows and 137 of 138 scenario marks; devices, numbers, coil pulses, pricing, deff priorities and the
package's deff and leff data match the code mechanically. The departures are in how the game plays that data.

### High

| id | What | Where |
|---|---|---|
| L-G01 | no leff lights a lamp: `parse_show` misses the shows' double-quoted colours (0 of 113 shows read) | lamps.py:78 |
| SC1 | every battle hit sound plays twice (op list + Battle.hit_media) | battles.py:284 |
| V-TXT1 | `%P1//S/%` plurals wrong ("SHOOT 11 SHOT", "3 COMBO") | media_bridge.py:35 |
| V-SC1 | main score font and row from 1,000,000 up (table 0x040c75d0) | score_screen.py:18 |
| D-SM-MODE / V003 | no service menu: SELECT starts mode `tf_service`, which does not exist | os_layer.py:1430 |
| SC4 | the hint speech slot 0x02111f54 is never played (its reader is to be decoded by agent A) | - |

Medium and low: the findings tables of each report. Fixes follow, high first, each with a regression test.

### Fixed (regression tests in [tests/test_qa_2026_11_26.py](../../tests/test_qa_2026_11_26.py))

| id | Fix | ROM |
|---|---|---|
| L-G01 | `parse_show` reads the shows' double-quoted colours: the leffs light their lamps (52 shows with lamps) | leff op lists |
| L-G02 | flash phase 10 ticks (FLASH_TICKS) | `0x000073cc` |
| SC1 | the battle hit call plays once, with its argument (Display.own_sounds keeps the op list from playing it again) | `0x010189a8` |
| V-TXT1 | `%P1//S/%` picks choice n-1 clamped to the last: "0 COMBOS", "SHOOT 11 SHOTS" | `0x0002fef0`, deff_044 op list |
| V-SC1 | main score font and row by value, table 0x040c75d0 (font 17 row 18 from 1,000,000) | `0x0102f11c`, `0x0102fa40` |
| R-F8, V-ENG2, L-G12 (citations) | the Tron 1.74 addresses still cited are replaced by tf_180 routines or marked inferred | see the commit |

| R-F1, SC5 | the ramp entrances play 0x273 / 0x272 on every hit | `0x010337e8`, `0x010338dc` |
| R-F2, SC3 | deff 91's call by the lit battle bit (0x170-0x177), not by side | `0x01022608` |
| L-G13, L-R06 | completed battle inserts and lit Energon targets solid (flash bit cleared); Energon inserts off in a multiball | `0x00007858`, `0x01030f80` |
| V-ENG5, SC14 | rule and music order: Megatron, wizard side, Optimus, WMB above double scoring, fast scoring, battles | `0x000178b0`, FUN_00017834 |
| R-F4 | validation sets game flag 0x10 (event 0x6a hook); the playfield-valid tests read pf_valid instead of the made-up flag 0x1c | LAB_010060a4, `0x0000d8c4` |
| R-F5 | no 1 s Optimus time gate (the lockout is task 0x54) | `0x01025de4`, `0x010262f0` |
| D-AUD-2, 13, 16, 22, 24, 27, 47, 72 | percentages over paid plays (c17); audits 13 and 72 are 0; average score per player, /10 x 10 | `0x00026c94` ... `0x00026c3c` |
| D-SW-51-EDGE | the Optimus target's handler runs on the opening edge (+0xe 0x1800) | `0x0000dc44` |

| R-F3, R-F11 | right orbit: token 7, task 0x47 (plunge, center lane), token 9 cancel the shot in that order; the 187-unit timers last 2.99 s (16 ms OS loop); gate held 93 ticks | `0x01033530`, `0x0002bd48`, `0x0102c0a8` |
| SC8 | initials entry sounds 0x04c / 0x04d / 0x04e | `0x0103c840`, words `0x00030eac`-`0x00030eb0` |
| D-ADJ-25, D-ADJ-89 | no free game cap (no reader of adj 25); the ball after a lock is auto-launched only when adj 89 = 1 | `0x0100a074` |
| V-TXT3, V-SC6 | `%i` printed as a number ("3X BONUS"); players not up drawn at level 3 | `0x0002fef0`, `0x0102f200` |

All 24 trace scenarios compare the same or better after these fixes (161 checks OK; the sounds and switches
scenarios match further: 29 of 29 and 55 of 87 sound events in order, before 28 and 51).

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
| `docs/boards_inventory.md` | written; **fails**: the ARM game program is `partiel` (the flipper drive and 2,526 unnamed functions open), the two Xilinx XC95144XL CPLDs `absent` (flash fuse map, only readable through the J8 JTAG header of a real board; owner to say whether it counts) |
| Captured data | **passes** (was 266 failures): the flipper times in `coils.csv` are waived by the owner, 2026-11-25. Decoded from the code by agent A on 2026-11-25: all 153 deffs (the 38 game-state ones per state, `rom/tools/deff_variants.py`), all leff shows, 33 coil times, every adjustment value text ([pinmame_waivers.md](../pinmame_waivers.md)) |
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
| F9 | match: the number steps by 10 past the players when the rate is reached; 0x072 / 0x073 at frame 60 of deff 38, the award after frame 68 with 0x074 and 24 more frames; MATCH OFF shows no deff 38 (tournament not modelled) | `0x00019668`, `0x0100820c`, `0x00019874` |
| P14, P15 | lanes rotate on every flipper press but in gf_state & 0x311, killing the group's leffs first; a lane completion always shows deff 44 with FUN_010236e8's result | `0x01032d5c`, `0x0102db28`, `0x010236e8` |
| F12 | tilt() and the multiball task validate the playfield | `0x0001db40`, `0x0103aba4`, `0x0000d8c4` |
| M10, M15 | the lock re-arm copies every player's count (ROM quirk kept); deff 139 gets the locked count | `0x0100af0c` |
| F15 | no change needed: the ball save does not survive a tilt in the ROM, as in the game. Approved capture [tilt_ball_save.jsonl](../../rom/rules/traces/tilt_ball_save.jsonl) (waiver row in [pinmame_waivers.md](../pinmame_waivers.md)): tilt 2.87 s, drain 3.64 s inside the save, end of ball, next ball's save 6.57 s, no re-serve | `0x0001db40` |
All 24 trace scenarios give the same comparison before and after these fixes, except two coil burst counts that M6 moves (megatron_decepticon, optimus_autobot); the trace replay runs at the code's 16.0 ms tick, scaled to the traces' 16.15 ms (counted on code-timed spans; the 16.26 ms used before drifted 0.3 s over a battle and gave battle_blackout an extra bonus).

### Open (proved, not fixed yet)

High first. Each line's detail, proof and game line are in its report.

| id | What | Sev |
|---|---|---|
| F14, F16-F18, M8, M11, M12, M14, P19 | smaller differences (lengths, ids, args, sample picks, rare adjustments) | low |

M8 stays open on purpose: the code starts leffs 76 / 77 on zuse_qualify_enabled for either side [0x01011ed4], but
the Decepticon reference (wizard_all_hail_megatron.jsonl 16.38 s) shows no 76 / 77 after its requirements are poked
while the Autobot one (wizard_multiball.jsonl 17.96 s) does; FUN_01035db4 / FUN_0100ff58 are to be read before the
Autobot-only gate goes.

### For agent A (one batched request)

The spec errors the reviews found are at the end of each report (game_flow.md 7, megatron_multiball.md 4,
optimus_multiball.md 2, wizard_modes.md 1, scoring_features.md 3, allspark_and_energon.md 1,
combos_and_multipliers.md 1). Decoding still needed for the strict rule: each deff's draw function (frames,
length, hold tail, sounds), each leff's function and the lamp groups (table 0x040d1510), the coil pulses of the
game's `coil_pulse` calls, the adjustment value formatter 0x0002aebc, the ball search task `0x0103b778`, the serve
and multiball tasks (`0x0103b39c`, `0x01039db4`, `0x0103aba4`).

Status 2026-11-25 (agent A): the deffs (all 153), the leffs and lamp groups (all), the coil pulses (33 of 35) and
the adjustment formatters (all 15, 0x0002aebc included) are decoded from the code; what stays open is listed in
[pinmame_waivers.md](../pinmame_waivers.md). The 20 spec errors are corrected in `rom/rules/modes/` (each
line cites its routine and the QA id). The ball search's coil sweep is decoded from its task (`rom/tools/ball_search.py`,
`rom/rom_data/io/ball_search_ops.json`: Optimus coil 0, top pop 5, left eject and Megatron lockup 6, right pop 10,
bottom pop 15, slings 20 and 25 ticks, end 30; the game's `BALL_SEARCH_SWEEP` is the same, one tick later); still
open there: the queued auto-launch's wait, the motor and gate from the event handlers. The serve and multiball
tasks are read from the code in `rom/rules/modes/ball_feed.md` (device settles 31 / 46 / 62 ticks from table
0x040d17fc, the shooter task's 125 ticks, 6-tick polls); the game's Tron-derived `MB_EJECT_TICKS`,
`MB_FIRST_EJECT_TICKS`, `SAVE_SERVE_TICKS` and `DEVICE_BUSY_TICKS` are for agent C to re-derive from it.

### Owner decisions

1. Decided 2026-11-25: no waiver for the captured data; agent A decodes it ([pinmame_waivers.md](../pinmame_waivers.md)).
   Decided later the same day: the flipper times may stay as measured until decoded; running the ROM's own code in
   Unicorn counts as decoding; the tick is the code's 16.0 ms (the game's `os_layer.py` TICK still says 16.26).
2. Decided 2026-11-25: the two Xilinx XC95144XL CPLDs are not decoded (fixed function, no game rule); `docs/boards_inventory.md` lists them with the unchecked boards.
3. Decided 2026-11-25: PinMAME capture approved for F15 only (row in [pinmame_waivers.md](../pinmame_waivers.md)); it confirmed the game.
