# QA 2026-11-25: OS layer and game flow against the tf_180 decompile

Independent read-only review (scope: `os_layer.py`, `switches.py`, `display.py`, `lamps.py`, `credits.py`,
`settings.py`, `features/game_over.py`, game and ball flow). Probes: [probe_os.py](probe_os.py) (9, each prints
what the game does). Labels: confirmed (code + probe), code-proven (decompile reading), doubtful.

**Main point.** `game/tf/os_layer.py` says in its header (lines 17-24) that its addresses and tick counts are
Tron 1.74's; so do `display.py`, `lamps.py`, `credits.py`, `settings.py`, `high_scores.py`, `slam_tilt.py`. Most
of those addresses land inside unrelated tf_180 functions (F13). The tf_180 OS routines are in the decompile:
game_init 0x19c64, ball_start 0x19d30, end of ball 0x19e44, game over 0x1a144, next_up 0x1abb4, tilt 0x1db40,
ball save 0x17a28 / 0x17acc / 0x17b3c, score_add 0x1caf0, deff_start_core 0x20498, multiball_start 0x0103aec0,
serve_ball 0x0103b39c, ball_search_start 0x0103b8e0.

## Findings

| id | area | ROM address | ROM does | game does | game file:line | proof | label | sev |
|---|---|---|---|---|---|---|---|---|
| F1 | Extra ball collect | right orbit `0x01033488` → `FUN_01007b74` → `FUN_00018204`/`00018170`, `deff_start(0x36)` | right orbit while EB lit awards it (audit 9, shoot again), deff 54 | never collected (`collect_extra_ball` reached only from a replay with adj 13 = 3) | os_layer.py:1530, 906 | probe `test_F_eb_collect_right_orbit` | confirmed | high |
| F2 | Special lit / collect | lit `0x01008528` (lamp 53 on + flash, task 0x61 → deff 55, audit 0x2102cf8); collect `0x01008684` (from 0x01033488: lamp 53 off, `FUN_0001d7a0(0)`, task 0x62 → deff 56) | special lit with deff 55, right orbit awards it per adj 23 (over limit 5,000,000 at 0x30ea8) | allspark item 1 only counts `specials_lit`; `light_special()` (deff 81, a Tron number) and `special_collect()` never called | allspark.py:214; os_layer.py:1545-1584 | probes `test_F_special_collect_right_orbit`, `test_F_eb_special_lit_shows` | confirmed | high |
| F3 | EB lit display | `FUN_01007b40`: `FUN_000180c8(0)`, task 0x5f (`FUN_01007b14`) queues deff 53 | "EXTRA BALL IS LIT" | count and lamp only, no deff 53 | os_layer.py:1525 | probe `test_F_eb_special_lit_shows` | confirmed | medium |
| F4 | Plumb bob held | `FUN_0001dc58`, task_2e `0x0001dc14` | held bob: warning every 62 ticks, `tilt()` after 124 ticks | one warning on the closing edge only | os_layer.py:1494-1523 | probe `test_F_bob_held` | confirmed | medium |
| F5 | Bob during end of ball | `FUN_0001dc58` ignores the bob only in task 0x29 or state & 0x310; `0x19e44` adds the bonus only if not tilted after deff 25 | tilt in end of ball / bonus taken, bonus lost | bob ignored in `ST_END_BALL` | os_layer.py:1495 | probe `test_F_bob_during_bonus` | confirmed | medium |
| F6 | Deff equal priority | `deff_start_core 0x00020498` | equal priority replaces only if the running deff has flags & 3 | equal priority always restarts; deff flags not loaded | display.py:121 | probe `test_F_deff_equal_prio` | confirmed | medium |
| F7 | Deff hold tail | `FUN_0103058c` / `FUN_0002108c(n, 0x20)` in each deff | n = 1 (44 deffs), 2 (29), 10 (28), 15/41 (deff 89) | 10 ticks for all, `HOLD_TICKS_BY_DEFF = {}` | display.py:38-41 | decompile: (1,0x20) x56, (2,0x20) x30, (10,0x20) x19 | code-proven | medium |
| F8 | Ball save length | `0x00017a28` (sleep 6, stop when < 7) | adj 38 = 5: 312 ticks | 306 ticks | os_layer.py:1175-1183 | probe `test_F_ball_save_length` | confirmed | low |
| F9a | Match number | `0x00019668` | steps by 10 until no player matches when the rate is not drawn | keeps the random number (player digits shown, no award); `random`, not `os.pick` | game_over.py:22-31 | probe `test_F_match_number_no_award` | confirmed | low |
| F9b | Match sounds | deff 38 `0x0100820c` | frame 60: 0x072 matched / 0x073 not; award inside the deff after 67 frames, then 0x074 | captured 0x023 + 0x073 always; award at fixed 258 ticks | game_over.py:22-34 | probe `test_F_match_sounds` | confirmed | medium |
| F9c | Match off | `0x00019668` | no deff 38 when adj 30 = 11 or tournament | deff 38 always | game_over.py:23 | code | code-proven | low |
| F10 | End-of-ball wait | `0x19e44`, `DAT_33324` = 937 | waits for every flag-0x2000 task (every foreground deff with flags & 5 == 0), up to 937 ticks | waits for `hook("ball_end_wait")` (the last feature's value, not the longest), no cap | os_layer.py:1633, 1646, 312 | code | code-proven | medium |
| F11 | Common switch award | `0x01032d2c`; inline copy in lock entry `0x0100a31c` (5,120 + `FUN_01000dfc(1)` + `FUN_00017d60`) | lock entry adds 1 to the bonus count, resets the search count | `base_score(5120)` only | megatron.py:489-490; switches.py:84 | code | code-proven | medium |
| F12 | Playfield validated | `FUN_0000d8c4` from `tilt()` 0x1db40 and multiball task `0x0103aba4` | both validate the playfield | neither | os_layer.py:744, 1509 | code | code-proven | low |
| F13 | ROM citations | e.g. serve [0x0001f258], score_add [0x0002340c], multiball_start [0x0001ed7c], end_of_ball [0x00020764], high_score_entry [0x0001ad4c], slam [0x00023e40] ... | | Tron 1.74 addresses, wrong in tf_180 | os_layer.py:23-88 and passim; slam_tilt.py:1; high_scores.py:3-26 | bisect against the decompile's function heads | code-proven | high |
| F14 | Slam tilt | `FUN_0001d534` | runs without a game too; event 0x54; task 0x39 → reset after 0xda + 0x5d ticks | gated on a game; posts the tilt hooks (0x65) | slam_tilt.py:31-39 | code | doubtful | low |
| F15 | Tilt during ball save | save task flags 0 (`0x17acc`), tilt kills only 0x1000 tasks; `0x01039ed4` calls `ball_save_try(0)` without a tilt check | the save seems to survive a tilt | `kill_ball_save()` at tilt | os_layer.py:1513 | code only | doubtful | medium if true |
| F16 | Valid playfield set | dispatcher flags +0x0e (0x1000 counts, 0x2000 forces); slings `0x01033104` / `0x010331a4` post 0x6b | switches 3, 38-42 carry 0x1000 | left out | os_layer.py:42-46 | code | doubtful | low |
| F17 | Ball search | `FUN_00017c60` (no multiball check); reset `FUN_00017d60` only with switch-timeout obj 0x31608 | | no search in multiball save/grace; reset on every switch | os_layer.py:961-963, 1303 | code | doubtful | low |
| F18 | Game-over music | `0x01006138` | 0x24 only if not playing, then volume fade | always 0x24, no fade | game_over.py:52-53 | code | code-proven | low |

Shared routines: the multiball-start gate is once (os_layer.py:756) but without `DAT_31624`/`31628` and the
restart flag; the common switch award is not one routine (F11); the multiball end is one (`_mb_end`); task_kill
keep masks are not modelled (F15 follows). Coded routines that nothing calls: `light_special`, `special_collect`,
`sound2`, `display_busy`, `current_score`.

## Provenance (values not taken from the decompile)

| item | current source | in the ROM at |
|---|---|---|
| Deff run lengths (timing.json `ended_ms`) | emulator capture | each deff function (e.g. deff 38 `0x0100820c`: 0x43 frames x `deff_frame_sleep(5)` + hold) |
| Deff hold tail 10 ticks | Tron | `FUN_0103058c` / `FUN_0002108c` arguments (F7) |
| Lamp shows (111) | emulator | leff functions, table 0x040cfe00 |
| Coil game pulses | emulator | driver calls `FUN_00002078(coil, 0x40, ...)` (not tabulated); test pulses in the descriptors |
| Ball search sweep and tick constants | traces | search task `FUN_0103b778`; countdown `DAT_33320` = 10 s |
| End-of-ball wait | traces | `DAT_33324` = 937, flag 0x2000 (0x19e44) |
| Serve / eject / multiball tick constants | Tron traces | `serve_ball 0x0103b39c`, trough task `FUN_01039db4`, multiball task `0x0103aba4` (device table 0x040d17fc) |
| Auto-launch 12 ticks | inferred | serve / trough code 0x0103b3xx |
| Launch sound 0x056 | observed | `0x01032dfc` (also tasks 0x3e 0x7d, 0x47 187 ticks) |
| Shoot-again lamp 3, EB lamp 55 | inferred / table | ROM bytes 0x00030e9a = 3, 0x00030e99 = 55 |
| EB / special over-limit 3,000,000 / 5,000,000 | Tron | 0x00030ea4 / 0x00030ea8 (values match) |
| Tilt speech 0x052 / 0x053 | observed | not found (task dispatcher 0x14f1c; event hooks not mapped) |
| Music 0x1d / 0x1f, add-player 0x048, coin 0x042 / 0x043 | observed | not located |
| Match reveal 258, attract delay 370 | traces | deff 38 `0x0100820c`; `0x1a144` |
| Bonus length 338 and sound offsets | capture | deff 25 `0x010014b8` |
| Switch delays, both-edge switches, base scores | traces | dispatcher and each handler (e.g. sling `FUN_01032d2c(0x1b8)`) |
| Power-off dim, coin door ticks, boot time | Tron | not found in tf_180 |
| High score default names, sounds | not read | table 0x040cf948, `0x18d54` |

## Spec errors (`rom/rules/modes/game_flow.md`)

1. §6.1 "wait up to 169 ticks": the ROM waits up to 937 ticks (`DAT_00033324`) for every flag-0x2000 task.
2. §4.3 slings / pops count "observed": code (`0x01033104`, `0x010331a4` post 0x6b); "eject, lock, trough do not
   count (inferred)" conflicts with dispatcher flag 0x1000 on switches 3 and 38-42.
3. §5.6 / §7 match: 0x023 then 0x073 is only the no-match path (0x072 and 0x074 when matched); no deff 38 when adj
   30 = 11 or in a tournament.
4. §5.4 tilt: the bob is ignored only in task 0x29 or state & 0x310; a held bob tilts after 124 ticks.
5. §5.5 special: lit state is lamp 53 (`0x01008528`), audit at 0x2102cf8, over-limit 5,000,000 at 0x30ea8.
6. "While tilted: no ball save" is not supported by the code (F15, unconfirmed).
7. §0: ball search is `DAT_33320` = 10 s, a ROM constant, not a Tron measurement.
