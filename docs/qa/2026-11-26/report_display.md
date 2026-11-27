# QA 2026-11-26, display conversion (scope V)

Matrix: [matrix_display.csv](matrix_display.csv), 182 rows, written by [probe_display.py](probe_display.py)
(`.venv/bin/python docs/qa/2026-11-26/probe_display.py`, read-only, about 12 s; it also prints the text-format and
score-font probes quoted below).

## Scope

- One row per display effect, deffs 1-155 (the deff table 0x040ce7c4 has 155 entries; "153" in the waiver text
  leaves out the two empty functions 8 and 22): priority and flags, run length, hold tail, frames (the slide the
  game builds), sounds and leffs started inside the deff, state variants, printf slots, and who starts it (ROM vs
  game).
- The deff engine as the game models it (V-ENG1-V-ENG8), the score display and status panel (V-SC1-V-SC11), the
  fonts (V-FNT1-V-FNT4), the printf formats (V-TXT1-V-TXT4).

## Method

ROM side, code only: `rom/rom_data/dmd/deffs.csv` (table 0x040ce7c4), agent A's op lists
`rom/rom_data/dmd/deff_ops/deff_NNN*.json` (the deff functions run as ROM code), and `rom/code/tf_decompiled.c`:
constant ids passed to `deff_start` 0x000209b4, to the show tasks 0x01006350 / 0x01006480, to the idle wait
0x0100664c and to the deff rules FUN_00017834, plus the functions read by hand (cited per row). The main-score
table 0x040c75d0 was read from the ROM with `rom/tools/rom.py` (values only).

Game side, what the game actually loads: `display.deff_table()` (event_map.csv), `HOLD_TICKS_BY_DEFF`,
`media_table.load()` (lengths, sounds, leffs), the slide data `scripts/gen_media.py build_deffs(only_data=True)`
builds from the package (run in memory, nothing written), `media_bridge.format_rom_text / format_values`,
`score_screen.score_draw`, and an AST scan of `game/tf` for the deff ids the game starts.

Mechanical results first: the priority, flags and background bit of all 155 deffs equal the code table; the
package's `timing.json` (run length, sounds, leffs) equals the op lists for all 155; the 27 game fonts equal
`rom_data/fonts.json` glyph by glyph. Everything below is where the game departs from that data or from the code.

Note on the review checkout: `game/tf/media_data.json` and `game/slides/deffs/` (generated, git-ignored) dated from
before the package was re-decoded: 27 deffs had no slide until `scripts/setup.py` runs again. The matrix uses the
regenerated data, what setup builds.

## Counts

| Kind | match | differs | missing | extra | unverifiable |
|---|---|---|---|---|---|
| deff (155) | 78 | 31 | 13 | 0 | 33 |
| engine (8) | 4 | 2 | 1 | 1 | 0 |
| score screen (11) | 3 | 4 | 4 | 0 | 0 |
| fonts (4) | 3 | 0 | 0 | 0 | 1 |
| text formats (4) | 1 | 3 | 0 | 0 | 0 |
| **total (182)** | **89** | **40** | **18** | **1** | **34** |

## Findings

All code-proven (decompile or op list read); "confirmed" where the probe also printed the game's wrong value.

| id | ROM does | game does | file:line | proof | sev |
|---|---|---|---|---|---|
| V-TXT1 (deffs 44 52 97 101 105 113 121 147 150, and 16 30 48 49 138 when started) | `%P1//S/%` consumes its own argument and picks choice arg-1 clamped to the last: plural "S" for 0 and every n >= 2 (op lists: "0 COMBOS", "SHOOT 11 SHOTS") | treats `//S/` as an ordinal list: "S" only for 2; "SHOOT 11 SHOT", "3 COMBO", "0 HITS" -> "0 HIT" | game/tf/media_bridge.py:35 | vsprintf 0x0002fef0 'P' branch; confirmed: probe prints `3 COMBO`, `11 COMBO` | high |
| V-SC1 | main score font and row by value, table 0x040c75d0 via FUN_0102f11c: >= 100,000,000 font 22 y 18; >= 1,000,000 font 17 y 18; >= 100,000 font 24 y 21; else 26 y 21 | fonts 26/24/22/20 by width, always y 21: from 1,000,000 up font 22 on row 21 instead of 17 on row 18 | game/tf/score_screen.py:18 | 0x0102fa40 + table; confirmed: probe 1,500,000 -> font 22 y 21 | high |
| V003 | service menu deff 3 started by start_deff_3 0x0000ed90 | no service menu at all: `os_layer.py:1429` starts mode `tf_service`, which does not exist (game/modes has attract and pup only; no tf/service.py ever committed), though README and AGENTS.md list it | game/tf/os_layer.py:1429 | grep, config.yaml modes | high |
| V001 | attract deff 1 cycles 5 child pages every 750 ticks (0x01000c30, 0x01000120, 0x010001e4, 0x01000cd0, 0x010003e4) printing live state (last scores, credits / FREE PLAY, high scores) | one slide of the lift's zero-state run, no printf slot: "CREDITS 0" and score "00" baked | game/tf/features/attract.py:45 | deff_001.json task ops; regenerated slide data has no slots | medium |
| V010, V015, V017 | 0x01000000 draws the credit text `msg_get_user_44a4(+0x30)` every frame | credit line baked empty; the `credits=` argument the game passes is dropped by media_bridge (no "args") | game/tf/credits.py:119, os_layer.py:1024, credits.py:158 | 0x01000000 read; timing.json page 0 text '' at 0x010000a0 | medium |
| V-SC6 | other players' scores drawn with palette entry 15 -> 3 | level 6 (marked inferred) | game/tf/score_screen.py:21 | 0x0102f200: `local_21 = 3` | medium |
| V-SC2, V-SC9 | after a score change (DAT_021120b0 >= 63, 7 of 14 frames) a box over the main score (x 41-127) and over the current player's panel row (x 0-39) | not drawn | game/tf/score_screen.py:48 | 0x0102fa40, 0x0102f200 | medium |
| V-SC7 | 1-2 players: last award value at x 38 row 13 / 8p+13, fading in | not drawn | game/tf/score_screen.py:29 | 0x0102f200 | medium |
| V-SC8 | combo text "%d-WAY" / "COMBO" / "%d COMBOS" font 1 x 39 sliding in while DAT_021120a8 < 94 | not drawn (combos.py:21 says the panel shows combos) | game/tf/score_screen.py:29 | 0x0102f200; deff_019.json ops 0x0102f5a8 / 0x0102f620 / 0x0102f6cc | medium |
| V-SC11 | every deff that calls FUN_0102f200 has the full panel | gen_media clears columns 0-40 and draws panel_draw (gaps V-SC6-9) | scripts/gen_media.py:123 | as above | medium |
| V-ENG5 | deff rule priority byte: multiball bg rules 7, battles 5, fast scoring (133) 5, double scoring 5 | fast / double scoring 0x80 above wizard 0x70 and Megatron / Optimus 0x60: during a multiball with fast or double scoring the game shows deff 133 / 130, the ROM the multiball's | game/tf/features/twobank.py:74, bumblebee.py:50, battles.py:85 | FUN_00017834 / leaf_17580 sort; the 19 rule calls | medium |
| V-ENG4 | show task 0x01006480 (all battle and multiball intros, 140, 149, 146, 43) ends its deff with deff_stop when one flipper is held and the other pressed | no skip | game/tf/display.py:499 | 0x01006480 loop | medium |
| V050 | shot name (text_draw_msg 0x01023d5c) and level from +0x30 / +0x34 [0x010237ac]: 12 variants | slide of the shot1_x2 run; combos.py:172 passes no values: always "ALLSPARK ... 2X" | game/tf/features/combos.py:172 | deff_050__*.json | medium |
| V066, V071, V072 | random_below(3 / 5 / 4) picks a video, each with its own frames and length (e.g. 72: 261-297 ticks) | always video 0 and its length; `anim` only reaches the PuP | game/tf/features/optimus.py:288, megatron.py:225, :235 | deff_066 / 071 / 072 variant op lists | medium |
| V097, V101, V105, V113, V121 | 0 shots left: "SHOOT LIT SHOT" (text_draw_msg, e.g. 0x0101f580); Devastator rover: "SHOOT R. ORBIT" (0x01016eb0) | the "SHOOT %u SHOT%P1" slot stays ("SHOOT 0 SHOT") | game/tf/features/battles.py:745 | deff_NNN__lit.json, deff_105__rover.json | medium |
| V052 / V-TXT3 | "%iX BONUS" (i = d) | SPEC has no `i`: "%iX BONUS" shown literally, the next slots shift (the 20,000 slot prints "03") | game/tf/media_bridge.py:19 | confirmed: probe `['%iX BONUS', '03', 'SHOT MULTIPLER']` | medium |
| V124, V125 | 124: 31 frames x 5 ticks + hold(1) = 156 ticks (2.50 s); 125: 27 x 5 + hold(2) = 137 ticks (2.19 s), 0x13e at 0, 0x13f at frame 14 (1.12 s) | set_media 1.0 s and 2.0 s from traces; no slide at all (the op lists ran with arg 0 and are empty), so the screen keeps the previous frame | game/tf/features/energon.py:37 | deff_124 0x01030b94, deff_125 0x01031038 read | medium |
| V002 | volume display (0x0000ee1c / 0x0000f2a8) | none | - (no caller) | grep | medium |
| V012 | OPERATOR ALERT / DEVICE MALFUNCTION (0x010383a8 and 3 more) | never started | - | grep | low |
| V005, V007, V011, V014 | boot screen 0x00006ecc; region lock 0x00005630; LOCATING PINBALLS (task_ball_search 0x0103b5e4); deff 14 from the flipper buttons 0x000068ec / 0x00026608 | never started (14 is only stopped, flippers.py:39) | game/tf/features/flippers.py:39 | decompile callers | low |
| V016, V018, V034-V037 | tournament / BUMP 'N' WIN deffs (0x0001a6fc, 0x0001e810, 0x0001e328) | tournament not modelled | - | decompile callers | low |
| V-TXT2 | "%P1/1ST/...//%" takes its own argument (deff 37 +0x38, deff 36 +0x18) | uses the previous slot's number (player): "YOU ARE IN 1ST PLACE!" for player 1 whatever the place | game/tf/media_bridge.py:59 | confirmed: probe; only tournament deffs, not started today | low |
| V013, V023, V024, V026, V027, V041 (and 10 15 17) | no hold call: priority kept to the last tick (e.g. deff_024 0x0103dc88 ends on deff_frame_sleep(0x138)) | priority 0x20 for the last 10 ticks (HOLD_TICKS default) | game/tf/display.py:191 | op lists without a prio op; 0x0103dc88, 0x01000000 read | low |
| V084, V089 | priority 0x20 from tick 162 (84) / 140 (89): 85 / 137 replaceable ticks | 2 ticks (deff_holds keeps only the last 0x20 op) | game/tf/display.py:83 | deff_084.json, deff_089.json prio ops | low |
| V047 | priority drops to 128 at tick 44, then 0x20 for the last 2 | table priority until the 2-tick hold | game/tf/display.py:83 | deff_047.json prio ops | low |
| V052 (sounds) | 0x144 at tick 12 (0.192 s), 0x141 at tick 100 (1.600 s) | 0.2 s and 1.63 s (trace) | game/tf/features/allspark.py:39 | deff_052.json | low |
| V129 | 0x27a at 0, 0x27b at tick 20, then queued after the sample (sound_after 0x000253d4) | five calls at trace times | game/tf/features/bumblebee.py:28 | deff_129.json | low |
| V033 | award variant "AWARD 1 TICKET" (FUN_00018c04) | not in the slide | game/tf/features/high_scores.py:306 | deff_033__award.json | low |
| V-SC4 | replay row first tries the tournament line FUN_0001e0d8, then the first replay award 1-4 (0x0102f8a0) | REPLAY AT only | game/tf/media_bridge.py:288 | 0x0102f770 / 0x0102f8a0 | low |
| V-ENG2 | show tasks are 0x5d-0x7e (0x01006634); queue routines 0x01006350 / 0x01006480 | docstrings cite Tron's 0x81-0xa7 and 0x0100fbb0 | game/tf/display.py:13, os_layer.py:564 | citation only | low |
| V-ENG8 (extra) | lengths and sounds from the code | trace-measured UNCAPTURED / set_media tables in battles, megatron, optimus, wizard, combos, twobank: dead now (the package length wins), live only for 124 / 125 | game/tf/features/battles.py:89 | display.py:281 | low |

## Unverifiable, and what agent A would need to decode

- **Starters (28 deffs)**: 6 8 9 22 28 29 30 39 62 68 74 80 90 95 99 103 107 111 115 119 123 130 137 138 152 153
  154 155, and 4: the id never appears as a constant in a deff_start / show / rule call (totals, replay awards,
  tables, callbacks). Needed: a deff -> starter table that follows ids through tables, task arguments and rule
  callbacks (extend `rom/tools/deff_args.py`). The game starts 4, 28, 62-123 totals, 130, 137 with its own
  citations.
- **Starter not found by A**: 49, 127, 145 (the game does not start them either).
- **140**: its sounds depend on the side and the lock count (table 0x040c62aa, counters 0x02111d78 / 0x02111d88);
  one op list per (side, count) is needed.
- **124, 125**: op lists for +0x34 / +0x30 = 1, 2, 4 (the lifter ran 0 and the functions return at once), so the
  frames can be packaged.
- **V-FNT3**: tf_180's glyph renderer 0x00021878 (placement taken from Tron).
- Variants not lifted: deff 1 with real state over its full 750-tick cycle; deffs 10 / 15 / 17 with a credit text;
  the Autobot side of 41, 81, 84, 91 (the game picks the side's sound itself; only the Decepticon run exists).
- Not checked mechanically: the argument order each game caller passes to every printf slot (only the cases above
  were read); the values the slides print for the 78 matching deffs rely on that order.
