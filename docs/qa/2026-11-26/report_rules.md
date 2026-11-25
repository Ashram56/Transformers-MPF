# QA 2026-11-26, scope R: rules conversion and address integrity against the tf_180 decompile

Independent read-only review. Matrix: [matrix_rules.csv](matrix_rules.csv) (771 rows). Labels: **confirmed**
(decompile reading + a probe run), **code-proven** (decompile reading).

## Scope

| Part | Rows | Source of truth |
|---|---|---|
| R-SW: every row of `rom/rules/switch_handlers.csv` (29 switches x first / repeat hit) | 58 | handlers run as ROM code by `rom/tools/switch_lift.py`, read against `tf_decompiled.c` |
| R-CR: every mark of 9 replayed scenarios vs `rom/rules/traces/code_runs.csv` | 138 | agent A's code runs of the same scenarios |
| R-DG: every node address of `docs/functional_diagram.md` | 109 | decompile; replays as the behaviour check |
| R-AD: every distinct ROM address cited in `game/` (.py, .gd; `0x0XXXXXXX`, short `0x10XXXXX`, `FUN_/DAT_/LAB_`) | 433 | function heads of `tf_decompiled.c`; Tron 1.74 heads of `tron_game_decompiled_v2.c` |
| R-K: tick constants of `os_layer.py` and the features | 33 | decompile |

## Method

- **Switches and scenarios** ([probe_rules_marks.py](probe_rules_marks.py)): runs the game's own replay
  (`python -m tests.scenario <name>`, the MPF harness `tests/tf_test.py`) with the trace written outside the repository,
  cuts it at the scenario's marks and compares each mark with the code side on points, sounds, deffs and leffs
  (random speech task 0xc6 0x14c / 0x14d, score display deff 19 and the deff rules' background restarts, caller
  0x0001794c, logged `rule=1` by the game, are left out). For the switches scenario it also compares coil pulses per
  coil, audits (less the OS counters 59-64) and game flags against `switch_handlers.csv`. **Game state for the switch
  rows**: `rom/rules/traces/switches.txt`, as in the code run: one player, Decepticon side (`#! random 01033f94 1`),
  ball plunged, the validating left sling, then every playfield switch hit twice, 2.19 s apart, on the same ball.
  Scenarios replayed one after another (about 3 s each): switches, game_flow, scoring, combos, allspark_energon,
  megatron_autobot, optimus_autobot, battle_blackout, wizard_multiball.
- **Addresses** ([probe_rules_addresses.py](probe_rules_addresses.py)): classifies each cited address as a tf_180
  function head, a call site or offset inside a function, data / ROM table / RAM named in the decompile, or nowhere;
  flags those that are Tron 1.74 function heads and not tf_180 ones. The 335 function-head citations were read once
  against the routine's name.
- **Diagram and constants**: each node's game location by its citation or feature; behaviour from the replays that
  cover it; number labels and tick constants read in the decompile. [probe_rules_matrix.py](probe_rules_matrix.py)
  rebuilds the CSV.

## Counts

| Part | match | differs | missing | extra | unverifiable |
|---|---|---|---|---|---|
| R-SW (58) | 41 | 10 | 4 | 0 | 3 |
| R-CR (138) | 94 | 37 | 0 | 0 | 7 |
| R-DG (109) | 82 | 12 | 0 | 0 | 15 |
| R-AD (433) | 406 | 17 | 0 | 8 | 2 |
| R-K (33) | 20 | 5 | 0 | 1 | 7 |
| **Total (771)** | **643** | **81** | **4** | **9** | **34** |

**Scores are equal on all 58 switch rows and on 137 of 138 scenario marks.** The one exception is
`allspark_collect_3`, the random mystery award: the code run's `random_below` answers 0 (SPECIAL) while the game
replays the emulator's BONUS X. The remaining differences are sounds, flasher pulses, timers and citations.

## Findings

| id | ROM does | game does | game file:line | proof | label | sev |
|---|---|---|---|---|---|---|
| R-F1 | the ramp entrance handlers play `snd_play(0x273)` (left [0x010337e8]) and `snd_play(0x272)` (right [0x010338dc]) on every hit, before the timer 0xc / 0xd | no sound, timer only | switches.py:87 | R-SW-05/06/45/46, R-CR-05/06/45/46 (emulator trace agrees with the code) | confirmed | medium |
| R-F2 | deff 91 [0x01022608] plays 0x170..0x177 by the lit battle bit (task+0x38 = DAT_02111ecc[p], set by [0x01020074]: 1→0x170, 2→0x171, 4→0x172, 8→0x173, 0x10→0x174, 0x20→0x175, 0x40→0x176, 0x80→0x177), with a random animation per bit | `MS_SOUND` by side (0x170 / 0x174) | battles.py:71, 908 | R-SW-07/15/20, R-CR-07/15/20/125 (code 0x172, game 0x170) | confirmed | medium |
| R-F3 | the orbit tokens are switch-timeout timers of 0xbb = 187 ticks, decremented each tick ([0x0000ff60] in the tick loop [0x0002bd48]). Right orbit [0x01033530]: token 7 up → clear it, no shot; else task 0x47 running (187 ticks, `leaf_abe8(0x47,0xbb)`) → kill it, no shot (one hit only); else token 9 up → clear it, no shot; else set token 9 and score | left token 2.26 s (inferred); right orbit ignored 3.0 s after any left orbit / back door / lane / launch (inferred) and 187 ticks after the last counted hit, on every hit, nothing cleared | battles.py:50, 60-61, 964-1003 | decompile; the replays never hit inside the windows | code-proven | medium |
| R-F4 | event 0x6a hook `LAB_010060a4` sets flag 0x10; `on_event_6a_3bcf4` [0x0103bcf4] clears flags 0xc / 0xd | sets flag 0x1c citing [0x0100f25c] (Tron; inside `ram_00001d80_user`); flag 0x1c is read in lamps.py:247 and display.py:406 | os_layer.py:1008 | R-SW-03 (code +16 −12 −13, game +28) | confirmed | low |
| R-F5 | no time gate in the center lane [0x01025de4] or Optimus target [0x010262f0]; the only lockout is task 0x54 (62 ticks), already in switches.py:81-84 | extra 1.0 s `HIT_IGNORE_S` | optimus.py:53, 398, 441 | decompile | code-proven | low |
| R-F6 | deff 44 (lanes complete) plays 0x059, then speech 0x05a 75 ticks later | 0x059 only | deff 44 media / lanes.py | R-SW-27, R-CR-27/81 | confirmed | low |
| R-F7 | leff 103 pulses flashers 18 / 21 / 23 18 times each; leff 170 pulses coil 31 17 times; leff 40 [0x01024328] pulses coil 32 every 4 ticks | 6 pulses each, 1, and none | lamp shows (lamps scope) | R-SW-07/15/17/18/20/53/54/57 | confirmed | low |
| R-F8 | 16 Tron function heads are still cited as tf_180 routines: 0x010022c4, 0x0100f164, 0x0100f25c, 0x0100f564, 0x0100f594, 0x0100f5c8, 0x0100f918, 0x0100fbb0, 0x0100fd88, 0x01012228, 0x01015094, 0x0101ac74, 0x01023704, 0x01024460, 0x0102a188, 0x010346e8, 0x01036f1c; each lands inside an unrelated tf_180 routine (deff 4 is tf 0x0103ee10, deff 32 tf 0x0103c840). F13 is marked fixed in docs/qa/README.md | wrong citations | display.py:13,17,23,167,232,245,293,339,394,409,460; os_layer.py:53,564,572,976,1008,1475,1604; lamps.py:361; media_bridge.py:289; high_scores.py:20,48,75 | R-AD `differs` rows | code-proven | medium |
| R-F9 | lamp rules have no address order keys in the ROM | 8 `order=` sort keys written as addresses that are not routines (0x01010959, 0x01012000+i, 0x01012010, 0x01026000+i, 0x01026010, 0x01028000+flag, 0x01028100+flag, 0x01037019) | wizard.py:98,101; battles.py:748,750; optimus.py:338-347 | R-AD `extra` rows | code-proven | low |
| R-F10 | ball feed: device settles of 31 / 46 / 62 ticks (table 0x040d17fc), shooter task 125 ticks (ball_feed.md) | SERVE_EJECT 32, SAVE_EJECT 39, MB_EJECT 101, MB_FIRST_EJECT 51, DEVICE_BUSY 149, SAVE_SERVE 48 (Tron traces) | os_layer.py:56-68 | R-K-08 | code-proven | medium |
| R-F11 | the code run pulses the orbit gate (coil 5) for 1488 ms (93 ticks) from 0x0102c0a8 | 91 ticks (1456 ms) | battles.py:54 | R-K-14 | confirmed | low |
| R-F12 | diagram node MSH reads "10,000 + 5,000 x hits"; the code [0x0101fd34] is min(10,000 + 10,000 x started + 5,000 x hits, 75,000) | the game has the code's formula | battles.py:893 | diagram label error, not a game error | code-proven | low |

Non-match rows that are not separate findings:
- **R-CR sound / leff rows (about 30)**: speech and deff-internal sounds falling a few ticks across a mark, random
  speech picks (deff 126 0x264 / 0x265, Bumblebee 0x27a / 0x27b, Optimus hit speech 0x2b3-0x2b6 one mark later),
  music channel calls 0x01d / 0x01e / 0x01f / 0x020 / 0x076, leff 23 + 0x13b at Megatron jackpots. Points are equal
  on all of them; they belong to the sounds and lamps scopes.
- **Leff 21 (eject warning)**: in the game and the emulator, not in the code runs; at [0x0100a788] case 7 it starts
  only when `snd_play(0x157)` is accepted, and the code run refuses that call. The game follows the code path.
- **Wizard pokes (R-CR-128, 131)**: the game starts leffs 76 / 77, deff 82 and leff 80 after RAM pokes: the still
  open M8.
- Still open from 2026-11-25 in this scope: F14, F16, F17, M8, P19.

## Unverifiable, and what agent A would need

| rows | why | for agent A |
|---|---|---|
| R-SW-55/56/58, R-CR-55/56/58 | the code run ends the Blackout battle about 400 ticks earlier than the game and the emulator, which agree with each other | rerun with the emulator's switch timing, or name the pause (task 0x59, device holds) the code run misses |
| R-CR-59/97/100/102, R-DG-093 | mystery draw: `random_below` [0x0000bae8] answers 0 in the code run | feed the emulator's draw as a `#! random` input to `scenario_lift.py` |
| R-DG battles B1, B2, B4-B8; Megatron / Optimus Decepticon side; kill paths | not replayed in this pass | none: run `probe_rules_marks.py OUT battle_* megatron_decepticon optimus_decepticon` |
| R-K-09 auto-launch, R-K-10 ball search run / event ticks | fitted to traces | the auto-launch wait in 0x0103bba0; the search task's total length |
| R-K-19 battle total at drain, R-K-24 deff 132 length, R-K-32 Optimus motor, R-K-33 bonus deff length | capture or emulator values | the lengths are in `rom/rom_data/dmd/deff_ops` (agent C to read); the motor limit from the mech task |
| R-AD 0x0003817e, 0x040dde30 | not named in the decompile | name them in `function_names.csv` / `rom_map.json` |

Notes: the game side is the MPF replay; the code side is agent A's Unicorn run of the ROM code (counts as decoding,
owner, 2026-11-25). No PinMAME capture decided any verdict. The functional diagram was written after the game; it
has no nodes for ball search, the side choice, the Optimus mech, slam tilt, or the service / audit side.
