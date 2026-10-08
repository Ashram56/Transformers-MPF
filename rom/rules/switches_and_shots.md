# Switches, shots, side choice and bonus

Transformers Pro 1.80 (`tf_180`). Tags: **observed** = the real ROM in the emulator (`tools/trace/tf_ref`),
**code** = read from `code/tf_decompiled.c`, **inferred** = reasoning only.

## Per-switch handlers (observed)

Scenario `rules/traces/switches.txt`: one player, ball plunged, one left sling hit to validate the
playfield, then every playfield switch hit twice ("first" and "repeat"), 2 s apart, with nothing else
going on. The trace is `rules/traces/switches.jsonl`; the same data as a table is `rules/switch_handlers.csv`
(with handler address, switch flags, audit counters and game flags). Values depend on game state: a
repeat hit can differ from the first because the first lit or advanced something (Energon, top lanes,
2-bank, Optimus). Treat this as the behaviour from a fresh ball, not the whole rule.

How to read it:
- **Points** is the change of the player's score. **Awards** lists each `score_add` with the function that
  awarded it. `handler` means the switch's own handler (switch table `handler` column; the OS switch
  dispatcher 0x14f1c calls it and the handler tail-calls `score_add`). Other addresses are rule
  functions in the decompile.
- **Sounds** are sound calls (`rom_data/sound/sound_call_uses.csv`). The right orbit spinner sound
  0x14d repeats while a ball spins it and is left out of the table.
- **Display effects** are deffs (`mpf_package/event_map.csv`); deff 19 (the in-play score display,
  restarted by the music table) is left out. **Lamp effects** are leffs (`mpf_package/config/shows/lampfx_NNN.yaml`).
- **Coils** are pulses measured from the solenoid registers, `coil:ms`. Coils 18/21/23/32 etc. are flashers.
- The playfield multiplier was 1 throughout.

| Switch | Hit | Points | Awards (who awarded) | Sounds | Display effects | Lamp effects | Coils |
|---|---|---|---|---|---|---|---|
| 1 Bumblebee Target | first | 20030 | 20000 (0x1001a70) + 30 (handler) | 0x26b | 128 deff_128 | 150 | 18:64ms 23:64ms 18:65ms x2 23:65ms |
| 1 Bumblebee Target | repeat | 25030 | 25000 (0x1001a70) + 30 (handler) | 0x26b | 128 deff_128 | 150 | 18:65ms x2 23:65ms 23:64ms 18:64ms |
| 2 Energon (Left) | first | 76110 | 75000 (0x10309a4) + 1110 (handler) | 0x25e 0x01f [music: main play, Decepticon] 0x25f | 124 deff_124 | 140 | 18:32ms x3 23:32ms x3 |
| 2 Energon (Left) | repeat | 11110 | 10000 (0x10309a4) + 1110 (handler) | 0x25d | - | 141 | - |
| 4 L. Ramp Entrance | first | 560 | 560 (handler) | 0x273 | - | - | - |
| 4 L. Ramp Entrance | repeat | 560 | 560 (handler) | 0x273 | - | - | - |
| 5 Left Orbit (Bottom) | first | 11220 | 10000 (0x1020074) + 1220 (handler) | 0x172 | 91 deff_091_0_more | 103 103 | 18:3ms x6 21:3ms x6 23:3ms x6 8:202ms 5:1493ms |
| 5 Left Orbit (Bottom) | repeat | 1220 | 1220 (handler) | - | - | - | - |
| 6 Left Orbit (Top) | first | 150000 | 150000 (0x1002f0c) | - | - | 35 | 5:1503ms |
| 6 Left Orbit (Top) | repeat | 0 | - | - | - | - | - |
| 7 Right Top Lane | first | 5060 | 2500 (0x102e208) + 2560 (handler) | 0x16d [drain (ball lost)] | - | 100 | - |
| 7 Right Top Lane | repeat | 5060 | 2500 (0x102e208) + 2560 (handler) | 0x16d [drain (ball lost)] | - | 100 | - |
| 8 Left Top Lane | first | 5060 | 2500 (0x102db28) + 2560 (handler) | 0x169 [ball saved sound] | - | 97 | - |
| 8 Left Top Lane | repeat | 5060 | 2500 (0x102db28) + 2560 (handler) | 0x169 [ball saved sound] | - | 97 | - |
| 10 L. Ramp Exit | first | 16170 | 15000 (0x1020074) + 1170 (handler) | 0x172 | 91 deff_091_0_more | 103 103 | 18:3ms x6 21:3ms x6 23:3ms x6 8:202ms |
| 10 L. Ramp Exit | repeat | 1170 | 1170 (handler) | - | - | - | - |
| 11 Center Lane | first | 152530 | 2500 (0x1025de4) + 150000 (0x1002f0c) + 30 (handler) | 0x2a3 0x2a4 | 141 deff_141_0_more | 170 35 | 8:202ms 31:29ms |
| 11 Center Lane | repeat | 177530 | 2500 (0x1025de4) + 175000 (0x1002f0c) + 30 (handler) | 0x2a3 0x2a4 | 141 deff_141_0_more | 170 35 | 8:202ms 31:30ms |
| 12 Right Orbit | first | 1220 | 1220 (handler) | - | - | - | - |
| 12 Right Orbit | repeat | 221220 | 20000 (0x1020074) + 200000 (0x1002f0c) + 1220 (handler) | 0x172 | 91 deff_091_0_more | 103 35 103 | 18:3ms x5 21:3ms x5 23:3ms x5 8:203ms |
| 13 Megatron Back Door | first | 30 | 30 (handler) | - | - | - | - |
| 13 Megatron Back Door | repeat | 30 | 30 (handler) | - | - | - | - |
| 14 R. Ramp Exit | first | 351170 | 25000 (0x1020074) + 100000 (0x101caa4) + 225000 (0x1002f0c) + 1170 (handler) | 0x1a9 0x02a 0x1c2 | 100 deff_100_blackout 101 deff_101_blackout | 35 113 114 | 8:386ms |
| 14 R. Ramp Exit | repeat | 276170 | 25000 (0x101cc6c) + 250000 (0x1002f0c) + 1170 (handler) | 0x1aa | 101 deff_101_blackout | 35 | - |
| 24 Left Outlane | first | 102500 | 2500 (0x102db28) + 100000 (handler) | 0x169 [ball saved sound] | 101 deff_101_blackout | 97 | - |
| 24 Left Outlane | repeat | 101000 | 1000 (0x102db28) + 100000 (handler) | 0x168 | - | 98 | - |
| 25 Left Return Lane | first | 11090 | 10000 (0x102db28) + 1090 (handler) | 0x16a 0x059 0x05a | 44 deff_044 101 deff_101_blackout | 99 37 | - |
| 25 Left Return Lane | repeat | 3590 | 2500 (0x102db28) + 1090 (handler) | 0x169 [ball saved sound] | - | 97 | - |
| 26 Left Slingshot | first | 440 | 440 (0x1033104) | 0x15a | - | - | 13:66ms |
| 26 Left Slingshot | repeat | 440 | 440 (0x1033104) | 0x15a | - | - | 13:66ms |
| 27 Right Slingshot | first | 440 | 440 (0x10331a4) | 0x15a | - | - | 14:66ms |
| 27 Right Slingshot | repeat | 440 | 440 (0x10331a4) | 0x15a | - | - | 14:66ms |
| 28 Right Return Lane | first | 3590 | 2500 (0x102e208) + 1090 (handler) | 0x16d [drain (ball lost)] | - | 100 | - |
| 28 Right Return Lane | repeat | 2090 | 1000 (0x102e208) + 1090 (handler) | 0x16c | - | 101 | - |
| 29 Right Outlane | first | 110000 | 10000 (0x102e208) + 100000 (handler) | 0x16e | 45 deff_045 | 102 | - |
| 29 Right Outlane | repeat | 102500 | 2500 (0x102e208) + 100000 (handler) | 0x16d [drain (ball lost)] | - | 100 | - |
| 30 Top Bumper | first | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c | 46 deff_046 | 26 27 | 9:34ms 21:33ms 21:32ms x2 |
| 30 Top Bumper | repeat | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c | 46 deff_046 | 26 27 | 9:34ms 21:32ms x3 |
| 31 Right Bumper | first | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c | 46 deff_046 | 26 28 | 10:34ms 21:33ms 21:32ms x2 |
| 31 Right Bumper | repeat | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c | 46 deff_046 | 26 28 | 10:34ms 21:32ms x2 21:33ms |
| 32 Bottom Bumper | first | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c | 46 deff_046 | 26 29 | 11:34ms 21:32ms x3 |
| 32 Bottom Bumper | repeat | 3170 | 3000 (0x102c8c8) + 170 (0x1032f8c) | 0x15c | 46 deff_046 | 26 29 | 11:34ms 21:32ms x2 21:33ms |
| 34 Right Orbit Spinner | first | 2590 | 2500 (0x10320a4) + 90 (handler) | 0x26d | - | 152 | 19:33ms |
| 34 Right Orbit Spinner | repeat | 2590 | 2500 (0x10320a4) + 90 (handler) | 0x26d | - | 152 | 19:32ms |
| 35 R. Ramp Entrance | first | 560 | 560 (handler) | 0x272 | - | - | - |
| 35 R. Ramp Entrance | repeat | 560 | 560 (handler) | 0x272 | - | - | - |
| 37 R. 2 Bank Target-Bot | first | 5030 | 5000 (0x102e9c0) + 30 (handler) | 0x261 | - | 143 | - |
| 37 R. 2 Bank Target-Bot | repeat | 5030 | 5000 (0x102e9c0) + 30 (handler) | 0x261 | - | 143 | - |
| 45 Captive Ball | first | 60 | 30 (handler) + 30 (handler) | - | - | - | - |
| 45 Captive Ball | repeat | 60 | 30 (handler) + 30 (handler) | - | - | - | - |
| 46 Energon (Right) | first | 76110 | 75000 (0x10309a4) + 1110 (handler) | 0x25e | 124 deff_124 101 deff_101_blackout | 140 | 18:32ms x3 23:32ms x3 |
| 46 Energon (Right) | repeat | 11110 | 10000 (0x10309a4) + 1110 (handler) | 0x25d | 101 deff_101_blackout | 141 | - |
| 49 Energon (Center) | first | 251110 | 250000 (0x10309a4) + 1110 (handler) | 0x260 0x13e 0x13f | 125 deff_125 101 deff_101_blackout | 142 40 | - |
| 49 Energon (Center) | repeat | 76110 | 75000 (0x10309a4) + 1110 (handler) | 0x25e | 124 deff_124 101 deff_101_blackout | 140 | 18:32ms 23:32ms 18:33ms x2 23:33ms x2 |
| 50 R. 2 Bank Target-Top | first | 5030 | 5000 (0x102e9c0) + 30 (handler) | 0x261 0x01f [music: main play, Decepticon] | - | 143 104 | - |
| 50 R. 2 Bank Target-Top | repeat | 75030 | 75000 (0x102e9c0) + 30 (handler) | 0x263 0x266 0x265 | 126 deff_126_0_more | 144 | 19:32ms x3 |
| 51 Optimus Prime | first | 30 | 30 (handler) | 0x05b 0x05c | 50 deff_050 | 38 | 12:65ms |
| 51 Optimus Prime | repeat | 30 | 30 (handler) | 0x1cb 0x1cc | 103 deff_103_blackout | 116 | 12:66ms |

## Side choice (observed + code)

- At game start the player's side byte (0x02112107 + player) is set to **2 = Decepticon**. Display effect 40
  ("USE FLIPPERS TO / CHOOSE YOUR SIDE / PLUNGE BALL TO / CONFIRM SELECTION") runs while task 200 is alive,
  with music 0x1b (Decepticon) or 0x1a (Autobot) from the music table.
- **Either flipper toggles the side** (left: side-1, wrapping 1 -> 2; right: side+1, wrapping 2 -> 1; with two
  values both act as a toggle). Each press plays sound 0x257 and re-evaluates the music (0x1a/0x1b). Code:
  deff 40 function 0x1034198; trace `side_left.jsonl`, `side_right.jsonl` (side 2 -> 1 on one press).
- **1 = Autobot, 2 = Decepticon** (code: deff 41 draws message 0x682 AUTOBOT when the byte is 1, 0x683 DECEPTICON otherwise).
- **What ends it:** the shooter lane switch (23) opening while task 200 runs starts task 0xc9 (0x1033f18), which
  sleeps 31 ticks (about 0.53 s observed: plunge 16.67 s, deff 41 at 17.20 s) and then calls 0x1033f54: deff 41
  "AUTOBOT/DECEPTICON TRANSFORMER SELECTED" (sound 0x57 Autobot / 0x58 Decepticon) and kills task 200.
  The choice also ends earlier if a playfield switch other than 12 (right orbit) is released first
  (event hooks 0x6b/0x6c, 0x1033dec/0x1033e08, object 0x3141c) (code).
- After the choice the music table gives deff 19 with 0x1c (Autobot) / 0x1d (Decepticon) at ball start and
  0x1e / 0x1f in main play; 0x31 / 0x34 when the battle can progress.

## End-of-ball bonus (code + observed)

Display effect 25 (0x1000ffc), started at drain (caller 0x19fb8):
- **Bonus base** = 670 x bonus count (u16 per player at RAM 0x34b3c, +1 from 11 shot functions through
  0x1000dfc) + held bonus (u32 per player at NVRAM 0x02111ce0, saved by 0x1000f68 when game flag 0x4b is set).
- **Multiplier** = u8 per player at 0x02111cef, raised by 0x1000e44 (+1 per call, capped at 25).
- **Total** = base x multiplier (0x1000f38).
- Screen: "BONUS" with the animated background images 0x225b-0x2262, then "%dX" and the value, counting the
  multiplier up from 2 (8 frames per step below 6x, 4 above), then "TOTAL BONUS".
- Sounds: 0x21 (Autobot) / 0x20 (Decepticon) at start, 0x77 + 0x78 at the first value, 0x76 after the
  multiplier count, 0x79, then 0x7a at TOTAL BONUS (observed: `sounds.jsonl` at 114.47-116.92 s).
