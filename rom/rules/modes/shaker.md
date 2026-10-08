# Shaker motor (optional, coil 8)

Audience: a developer rebuilding Transformers Pro 1.80 (`tf_180`) in MPF who has not read the ROM. Addresses refer
to `code/tf_decompiled.c` (headers `// ==== ADDR NAME`). The full list of triggers, one row per call site, is in
`rom_data/io/shaker.csv`.

## 1. Summary
- Coil 8 "SHAKER MOTOR (OPTIONAL)" (`rom_data/io/coils.csv`, flags motor_or_long, test 1,000 ms) is run for a
  fixed time by one helper. Nothing else drives it in game: no coil group contains coil 8 (coil group table
  0x040cf65c used by `coilgroup_pulse` 0x00005fd4), no lamp effect pulses it, its ball-search time is 0, and no
  `coil_pulse(8, ...)` call exists. The only other user is the coil test in the service menu (OS).
- Three patterns, each a single continuous run: **1 = 200 ms, 2 = 384 ms, 3 = 1,024 ms** (table 0x040c7620,
  u16 at +4 x pattern).
- Almost every call sits at the very start of a display effect (deff) function, so the shake happens when that
  deff actually begins to show (a queued deff shakes when it gets on screen, not when it was requested).

## 2. Settings
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 96 | SHAKER MOTOR (OPTIONAL) | MAXIMAL USE (3) | 0 NONE, 1 MINIMAL USE, 2 MODERATE USE, 3 MAXIMAL USE | each trigger has a minimum level; the shaker runs when adj 96 != 0 and adj 96 >= that level [0x010307a0, also read directly by 0x01004644] |

## 3. How a shake is started
`shaker(pattern, min_level)` [0x010307a0]: if `adj_get(96)` is not 0 and is >= min_level, call
`shaker_run(pattern)` [0x0103070c]:
- pattern outside 1-3: error 0xb4, nothing.
- nothing while game state 0x31468 has any of bits 0x310 (0x200 tilted, 0x10 no game in progress; 0x100 not
  decoded), so no shaking in attract mode or after a tilt.
- if the time left on coil 8 (0x00001ecc(8)) is already >= the pattern time, nothing (a long shake is never cut
  short); otherwise coil 8 is (re)started for the full pattern time (0x00002078(8, ms, 0, 0, 0, 1)).
So overlapping triggers extend the run: traces show 386-401 ms for pattern 2 and 1,029-1,064 ms for pattern 3.

## 4. Triggers by level
| Level needed | Pattern | Triggers (deff) |
|---|---|---|
| 1 MINIMAL and up | 3 (1,024 ms) | Megatron A / D super jackpot (73 / 79), Optimus A / D super jackpot (61 / 67), side mode intro (81) and completion (84), wizard multiball intro (86), super wizard jackpot (89) |
| 2 MODERATE and up | 2 (384 ms) | every battle intro (92, 96, 100, 104, 108, 112, 116, 120) and battle hit deff (94, 98, 102, 106, 110, 114, 118, 122); Megatron A / D intro (69 / 75), jackpot (71 / 77), double jackpot (72 / 78); Optimus battle start (142) and hits (144); Optimus A / D intro (57 / 63), jackpot (59 / 65), double jackpot (60 / 66); side mode shot (83); wizard multiball shot (88); double scoring start (129); FAST SCORING READY (131), fast scoring start (132), fast value raised (135), TIME EXTENDED (136); SUPER POP BUMPERS LIT (149); SUPER SPINNER LIT (146) |
| 2 MODERATE and up | 1 (200 ms) | Allspark mystery award (52) |
| 3 MAXIMAL only | 2 (384 ms) | Megatron BALL n LOCKED (140); N-WAY COMBO (48, a deff no code was found to start) |
| 3 MAXIMAL only | 1 (200 ms) | N MORE FOR MODE START (91), N MORE TO ACCESS OPTIMUS (141), every fast-scoring all-targets award [0x01004644, tail call at 0x01004750] |

## 5. Observed
Every coil 8 run in `traces/*.jsonl` (factory settings, adj 96 = 3; 207 runs) starts within 80 ms of one of
the deffs above, with the listed length: e.g. `battle_blackout.jsonl` 19.61 deff 91 -> 200 ms, 26.18 deff 100 ->
390 ms; `megatron_autobot.jsonl` 76.93 deff 73 -> 1,060 ms; `scoring.jsonl` 160.41 fast-scoring award (deff 134)
-> 210 ms. Not seen in traces: deffs 48, 135, 136, 146, 89 (code only).

## 6. MPF notes
- Model it as a timed hold of coil 8 (not a pulse): enable for 200 / 384 / 1,024 ms, extending only when the new
  time is longer than what is left. Gate it on a machine setting with the four levels above, and disable it
  while tilted and outside a game.
- Tie each shake to the start of the slide / show that replaces the deff, not to the scoring event.
