# Switches, shots, side choice and bonus

Transformers Pro 1.80 (`tf_180`). Tags: **observed** = the real ROM in the emulator (`tools/trace/tf_ref`), used here only to confirm,
**code** = read from `code/tf_decompiled.c`, **inferred** = reasoning only.

## Per-switch handlers (code)

Read by running the ROM's own code: `tools/switch_lift.py` runs tf_180 in Unicorn (owner, 2026-11-24: running ROM
code counts as decoding) with the OS tick of 16 ms: the global constructors [0x0002c0f4] that hook every module
on its events, `game_init` [0x00019c64] as `sw_start_button` [0x0001a6e4] calls it, then each tick the OS loop
[0x0002bd48] (event 0x20, deff manager, lamp compositor, sound resolver, switch debounce), the due tasks and
[0x0000b648]. A switch hit is decided as `switch_dispatch_debounce` [0x0000dc44] does: the record at
0x040e2c20 + n*0x20 gives the handler (+0), its argument (+4), the task flags (+0xc), the edges and game-state
mask (+0xe: 0x400 closing edge, 0x800 opening edge; the captive ball runs on both, hence its 60 points) and
the task id (+0x14); dedicated switches (flippers, tilt, coins) have their records at 0x040e3740 + (n - 0x81) * 0x20
(`switch_rec_d2d4` [0x0000d2d4]). Every rule routine, deff, leff, sound and coil pulse below is the ROM's code,
the current player, side and flipper state included; tasks end through the OS exit path with their exit calls
(`task_run_exit_handlers_a84c` [0x0000a84c]). Python only records `score_add_player` [0x0001cb0c], `event_post`, `audit_add`, the game
flags and the deff, leff and sound starts, keeps the OS task list, and moves the balls as the tracer does
(`tools/trace/tf_ref.cpp`: coil 1 trough to shooter, coil 2 launch, coil 22 eject, coil 3 lock release). The random
draws (`random_below` [0x0000ba94]) are inputs, like the switch hits: the scenario's `#! random` lines give the side
drawn at game start (on_event_26_33f94 [0x01033f94]), every other draw answers 0.

Scenario `rules/traces/switches.txt`: one player, ball plunged, one left sling hit to validate the playfield,
then every playfield switch hit twice ("first" and "repeat"), with nothing else going on. A hit is 60 ms
closed, then the next one 2.18 s later (the spacing the scenario gives). Op lists:
`rom_data/rules/switch_lift.json`; the table with handler address, switch flags, audit counters and game flags:
`rules/switch_handlers.csv` (`TF_ROM=tf_180.bin python3 tools/switch_lift.py OUT_JSON OUT_CSV TRACE_JSONL`).
Values depend on game state: a repeat hit can differ from the first because the first lit or advanced
something (Energon, top lanes, 2-bank, Optimus). Treat this as the behaviour from a fresh ball, not the whole
rule.

How to read it:
- **Points** is the change of the player's score. **Awards** lists each award with the function that
  awarded it (`handler`: the switch's own handler, `handler` column of the CSV).
- **Sounds** are sound calls (`rom_data/sound/sound_call_uses.csv`). Speech 0x14c / 0x14d of task 0xc6
  [0x010250f4] (one of the two at random, retried every tick) is not a switch sound.
- **Display effects** are deffs (`mpf_package/event_map.csv`); deff 19 (the in-play score display,
  restarted by the music table) is left out. **Lamp effects** are leffs (`mpf_package/config/shows/lampfx_NNN.yaml`).
- **Coils** are the pulses the code asks for, `coil:ms`. Coils 18/21/23/32 etc. are flashers.
- The playfield multiplier was 1 throughout.
- **Trace** compares the row with the emulator trace `rules/traces/switches.jsonl` (confirmation only).
  Points, awards and audits agree on all 58 rows; 52 rows agree on every column. The others (their Trace column says which column and what the trace has): the
  Blackout battle's total screen (deff 103, leff 116, sounds 0x1cb 0x1cc) starts on the 50 hits in the code run
  and on 51 repeat in the trace (the battle timers run on the scenario's tick count, inferred as the cause); the
  extra Energon sound 0x25f, the 2-bank's 0x265 / 0x266 and some game flags differ in the same way. Random picks
  (`random_below`) answer 0 in the code run.

| Switch | Hit | Points | Awards (who awarded) | Sounds | Display effects | Lamp effects | Coils | Trace |
|---|---|---|---|---|---|---|---|---|
| 1 BUMBLEBEE TARGET | first | 20030 | 20000 (0x1001a70) + 30 (handler) | 0x26b | 128 deff_128 | 150 | 18:64ms x3 23:64ms x2 | same |
| 1 BUMBLEBEE TARGET | repeat | 25030 | 25000 (0x1001a70) + 30 (handler) | 0x26b | 128 deff_128 | 150 | 18:64ms x3 23:64ms x2 | same |
| 2 ENERGON (LEFT) | first | 76110 | 75000 (0x10309a4) + 1110 (handler) | 0x25e 0x01f [music: main play, Decepticon] 0x25f | 124 deff_124 | 140 | 18/23:32ms x3 | differs: flags (trace +16 +16 +16 +16 +16 +71 -12 -12 -12 -12 -12 -13 -13 -13 -13 -13) |
| 2 ENERGON (LEFT) | repeat | 11110 | 10000 (0x10309a4) + 1110 (handler) | 0x25d | - | 141 | - | same |
| 4 L. RAMP ENTRANCE | first | 560 | 560 (handler) | 0x273 | - | - | - | same |
| 4 L. RAMP ENTRANCE | repeat | 560 | 560 (handler) | 0x273 | - | - | - | same |
| 5 LEFT ORBIT (BOTTOM) | first | 11220 | 10000 (0x1020074) + 1220 (handler) | 0x172 | 91 deff_091_0_more | 103 103 | 5:1488ms 8:200ms 21/18/23:32ms x5 21/18/23:250ms x13 | same |
| 5 LEFT ORBIT (BOTTOM) | repeat | 1220 | 1220 (handler) | - | - | - | - | same |
| 6 LEFT ORBIT (TOP) | first | 150000 | 150000 (0x1002f0c) | - | - | 35 | 5:1488ms | same |
| 6 LEFT ORBIT (TOP) | repeat | 0 | - | - | - | - | - | same |
| 7 RIGHT TOP LANE | first | 5060 | 2500 (0x102e208) + 2560 (handler) | 0x16d [drain (ball lost)] | - | 100 | - | same |
| 7 RIGHT TOP LANE | repeat | 5060 | 2500 (0x102e208) + 2560 (handler) | 0x16d [drain (ball lost)] | - | 100 | - | same |
| 8 LEFT TOP LANE | first | 5060 | 2500 (0x102db28) + 2560 (handler) | 0x169 [ball saved sound] | - | 97 | - | same |
| 8 LEFT TOP LANE | repeat | 5060 | 2500 (0x102db28) + 2560 (handler) | 0x169 [ball saved sound] | - | 97 | - | same |
| 10 L. RAMP EXIT | first | 16170 | 15000 (0x1020074) + 1170 (handler) | 0x172 | 91 deff_091_0_more | 103 103 | 8:200ms 21/18/23:32ms x5 21/18/23:250ms x13 | same |
| 10 L. RAMP EXIT | repeat | 1170 | 1170 (handler) | - | - | - | - | same |
| 11 CENTER LANE | first | 152530 | 2500 (0x1025de4) + 150000 (0x1002f0c) + 30 (handler) | 0x2a3 0x2a4 | 141 deff_141_0_more | 170 35 | 8:200ms 31:100ms x17 | same |
| 11 CENTER LANE | repeat | 177530 | 2500 (0x1025de4) + 175000 (0x1002f0c) + 30 (handler) | 0x2a3 0x2a4 0x14c x12 | 141 deff_141_0_more | 170 35 | 8:200ms 31:100ms x17 | same |
| 12 RIGHT ORBIT | first | 1220 | 1220 (handler) | 0x14c x31 | - | - | - | same |
| 12 RIGHT ORBIT | repeat | 221220 | 20000 (0x1020074) + 200000 (0x1002f0c) + 1220 (handler) | 0x172 | 91 deff_091_0_more | 103 35 103 | 8:200ms 21/18/23:32ms x5 21/18/23:250ms x13 | same |
| 13 MEGATRON BACK DOOR | first | 30 | 30 (handler) | 0x14c x31 | - | - | - | same |
| 13 MEGATRON BACK DOOR | repeat | 30 | 30 (handler) | - | - | - | - | same |
| 14 R. RAMP EXIT | first | 351170 | 25000 (0x1020074) + 100000 (0x101caa4) + 225000 (0x1002f0c) + 1170 (handler) | 0x02a 0x1a9 0x1c2 | 100 deff_100_blackout 101 deff_101_blackout | 35 114 113 | 8:384ms | same |
| 14 R. RAMP EXIT | repeat | 276170 | 25000 (0x101cc6c) + 250000 (0x1002f0c) + 1170 (handler) | 0x1aa | 101 deff_101_blackout | 35 | - | same |
| 24 LEFT OUTLANE | first | 102500 | 2500 (0x102db28) + 100000 (handler) | 0x169 [ball saved sound] | 101 deff_101_blackout | 97 | - | same |
| 24 LEFT OUTLANE | repeat | 101000 | 1000 (0x102db28) + 100000 (handler) | 0x168 | - | 98 | - | same |
| 25 LEFT RETURN LANE | first | 11090 | 10000 (0x102db28) + 1090 (handler) | 0x16a 0x059 0x05a | 44 deff_044_multipliers 101 deff_101_blackout | 99 37 | - | same |
| 25 LEFT RETURN LANE | repeat | 3590 | 2500 (0x102db28) + 1090 (handler) | 0x169 [ball saved sound] | - | 97 | - | same |
| 26 LEFT SLINGSHOT | first | 440 | 440 (0x1033104) | 0x15a [slingshot] | - | - | - | same |
| 26 LEFT SLINGSHOT | repeat | 440 | 440 (0x1033104) | 0x15a [slingshot] | - | - | - | same |
| 27 RIGHT SLINGSHOT | first | 440 | 440 (0x10331a4) | 0x15a [slingshot] | - | - | - | same |
| 27 RIGHT SLINGSHOT | repeat | 440 | 440 (0x10331a4) | 0x15a [slingshot] | - | - | - | same |
| 28 RIGHT RETURN LANE | first | 3590 | 2500 (0x102e208) + 1090 (handler) | 0x16d [drain (ball lost)] | - | 100 | - | same |
| 28 RIGHT RETURN LANE | repeat | 2090 | 1000 (0x102e208) + 1090 (handler) | 0x16c | - | 101 | - | same |
| 29 RIGHT OUTLANE | first | 110000 | 10000 (0x102e208) + 100000 (handler) | 0x16e | 45 deff_045 | 102 | - | same |
| 29 RIGHT OUTLANE | repeat | 102500 | 2500 (0x102e208) + 100000 (handler) | 0x16d [drain (ball lost)] | - | 100 | - | same |
| 30 TOP BUMPER | first | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c [pop bumper] | 46 deff_046 | 26 27 | 21:32ms x3 | same |
| 30 TOP BUMPER | repeat | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c [pop bumper] | 46 deff_046 | 26 27 | 21:32ms x3 | same |
| 31 RIGHT BUMPER | first | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c [pop bumper] | 46 deff_046 | 26 28 | 21:32ms x3 | same |
| 31 RIGHT BUMPER | repeat | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c [pop bumper] | 46 deff_046 | 26 28 | 21:32ms x3 | same |
| 32 BOTTOM BUMPER | first | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c [pop bumper] | 46 deff_046 | 26 29 | 21:32ms x3 | same |
| 32 BOTTOM BUMPER | repeat | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c [pop bumper] | 46 deff_046 | 26 29 | 21:32ms x3 | same |
| 34 RIGHT ORBIT SPINNER | first | 2590 | 2500 (0x10320a4) + 90 (handler) | 0x26d | - | 152 | 19:32ms | same |
| 34 RIGHT ORBIT SPINNER | repeat | 2590 | 2500 (0x10320a4) + 90 (handler) | 0x26d | - | 152 | 19:32ms | same |
| 35 R. RAMP ENTRANCE | first | 560 | 560 (handler) | 0x272 | - | - | - | same |
| 35 R. RAMP ENTRANCE | repeat | 560 | 560 (handler) | 0x272 | - | - | - | same |
| 37 R. 2 BANK TARGET-BOT | first | 5030 | 5000 (0x102e9c0) + 30 (handler) | 0x261 | - | 143 | - | same |
| 37 R. 2 BANK TARGET-BOT | repeat | 5030 | 5000 (0x102e9c0) + 30 (handler) | 0x261 | - | 143 | - | same |
| 45 CAPTIVE BALL | first | 60 | 30 (handler) + 30 (handler) | - | - | - | - | same |
| 45 CAPTIVE BALL | repeat | 60 | 30 (handler) + 30 (handler) | - | - | - | - | same |
| 46 ENERGON (RIGHT) | first | 76110 | 75000 (0x10309a4) + 1110 (handler) | 0x25e 0x25f | 124 deff_124 101 deff_101_blackout | 140 | 18/23:32ms x3 | differs: sounds (trace 0x25e) |
| 46 ENERGON (RIGHT) | repeat | 11110 | 10000 (0x10309a4) + 1110 (handler) | 0x25d | 101 deff_101_blackout | 141 | - | same |
| 49 ENERGON (CENTER) | first | 251110 | 250000 (0x10309a4) + 1110 (handler) | 0x260 0x13e 0x13f | 125 deff_125 101 deff_101_blackout | 142 40 | 32:100ms x34 | same |
| 49 ENERGON (CENTER) | repeat | 76110 | 75000 (0x10309a4) + 1110 (handler) | 0x25e 0x25f | 124 deff_124 101 deff_101_blackout | 140 | 32:100ms x35 18/23:32ms x3 | differs: sounds (trace 0x25e) |
| 50 R. 2 BANK TARGET-TOP | first | 5030 | 5000 (0x102e9c0) + 30 (handler) | 0x261 0x01f [music: main play, Decepticon] 0x1cb | 103 deff_103_blackout | 143 104 116 | 32:100ms x34 | differs: sounds (trace 0x01f 0x261) deffs (trace -) leffs (trace 104 143) |
| 50 R. 2 BANK TARGET-TOP | repeat | 75030 | 75000 (0x102e9c0) + 30 (handler) | 0x263 0x1cc | 126 deff_126_0_more | 144 | 32:100ms x34 | differs: sounds (trace 0x263 0x265 0x266) flags (trace +48) |
| 51 OPTIMUS PRIME | first | 30 | 30 (handler) | 0x05b 0x05c | 50 deff_050 | 38 | 32:100ms x34 12:64ms | same |
| 51 OPTIMUS PRIME | repeat | 30 | 30 (handler) | - | - | - | 32:100ms x35 12:64ms | differs: sounds (trace 0x1cb 0x1cc) deffs (trace 103) leffs (trace 116) |

## Side choice (code; code run = trace)

- At the player's first ball (event 0x26) on_event_26_33f94 [0x01033f94] sets the side byte (0x02112107 + player):
  adj 65 TRANSFORMERS SELECT 0 RANDOM gives random_below(2) + 1, 1 / 2 give that side, competition mode gives 1
  (the emulator drew 2 = Decepticon in the one-player traces). Display effect 40
  ("USE FLIPPERS TO / CHOOSE YOUR SIDE / PLUNGE BALL TO / CONFIRM SELECTION") runs while task 200 is alive,
  with music 0x1b (Decepticon) or 0x1a (Autobot) from the music table.
- **Either flipper toggles the side** (left: side-1, wrapping 1 -> 2; right: side+1, wrapping 2 -> 1; with two
  values both act as a toggle). Each press plays sound 0x257 and re-evaluates the music (0x1a/0x1b). Code:
  deff 40 function 0x1034198; trace `side_left.jsonl`, `side_right.jsonl` (side 2 -> 1 on one press).
- **1 = Autobot, 2 = Decepticon** (code: deff 41 draws message 0x682 AUTOBOT when the byte is 1, 0x683 DECEPTICON otherwise).
- **What ends it:** the shooter lane switch (23) opening while task 200 runs starts task 0xc9 (0x1033f18), which
  sleeps 31 ticks (0.50 s; the trace confirms: plunge 16.67 s, deff 41 at 17.20 s; code runs side_left / side_right in `traces/code_runs.csv`) and then calls 0x1033f54: deff 41
  "AUTOBOT/DECEPTICON TRANSFORMER SELECTED" (sound 0x57 Autobot / 0x58 Decepticon) and kills task 200.
  The choice also ends earlier if a playfield switch other than 12 (right orbit) is released first
  (event hooks 0x6b/0x6c, 0x1033dec/0x1033e08, object 0x3141c) (code).
- After the choice the music table gives deff 19 with 0x1c (Autobot) / 0x1d (Decepticon) at ball start and
  0x1e / 0x1f in main play; 0x31 / 0x34 when the battle can progress.

## End-of-ball bonus (code; code run = trace)

Display effect 25 (0x1000ffc), started at drain (caller 0x19fb8):
- **Bonus base** = 670 x bonus count (u16 per player at RAM 0x34b3c, +1 from 11 shot functions through
  0x1000dfc) + held bonus (u32 per player at NVRAM 0x02111ce0, saved by 0x1000f68 when game flag 0x4b is set).
- **Multiplier** = u8 per player at 0x02111cef, raised by 0x1000e44 (+1 per call, capped at 25).
- **Total** = base x multiplier (0x1000f38).
- Screen: "BONUS" with the animated background images 0x225b-0x2262, then "%dX" and the value, counting the
  multiplier up from 2 (8 frames per step below 6x, 4 above), then "TOTAL BONUS".
- Sounds: 0x21 (Autobot) / 0x20 (Decepticon) at start, 0x77 + 0x78 at the first value, 0x76 after the
  multiplier count, 0x79, then 0x7a at TOTAL BONUS (code run = trace: `sounds` in `traces/code_runs.csv`, `sounds.jsonl` at 114.47-116.92 s).
