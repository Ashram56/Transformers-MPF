# Wizard: requirements, All Hail Megatron / Autobots Roll Out, Wizard Multiball (Battle for Cybertron)

Audience: a developer rebuilding Transformers Pro 1.80 (`tf_180`) in MPF who has not read the ROM. Addresses refer
to `code/tf_decompiled.c` (headers `// ==== ADDR NAME`; `zuse_qualify_enabled` and `portal_mb_all_shots_done` are
names carried over from Tron by code shape only). 1 tick = 16.25 ms (see `megatron_multiball.md`).

Audit numbers: the trace prints the **counter id**; `rom_data/settings/audits.csv` # = counter + 8 (e.g. counter
0x7e = 126 = #134 "WIZARD STARTED").

Reference traces (`traces/`, watch file `traces/watch_wizard.tsv`, factory settings). **Both use pokes** to skip
the many modes needed to qualify:
| Trace | What | Pokes |
|---|---|---|
| wizard_all_hail_megatron | Decepticon side: All Hail Megatron started at the Allspark, 12 shots (2 per shot), super jackpot, completed, total, drain | requirements 0-4 marked started + completed (0x0211210c + 16 x req = 0x0101) |
| wizard_multiball | Autobot side: Autobots Roll Out, one real shot, super jackpot, then the Wizard Multiball: 18 shots (3 per shot), super wizard jackpot, drains, total | requirements 5-9, later 0-4, = 0x0101; Autobots Roll Out shot counters (0x34eb4 + 4i) = 2 |

## 1. Summary
The game keeps 11 **wizard requirements** per player: Megatron multiball, the 4 Decepticon battles, Optimus
multiball, the 4 Autobot battles, and the side mode below. Each is "collected" when started and "completed" when
won (battle completed, multiball super jackpot). Starting 5 of them lights an extra ball.
- Completing your own side's five (Decepticon: Megatron multiball + Starscream, Shockwave, Blackout, Devastator;
  Autobot: Optimus multiball + Bumblebee, Ironhide, Mudflap & Skids, Ratchet) makes the **Allspark** (left eject)
  start **All Hail Megatron** (Decepticon) / **Autobots Roll Out** (Autobot): a single-ball mode, 1,000,000 to
  start, every main shot twice for 500,000 + 50,000 per shot made; then the Allspark collects a super jackpot equal
  to everything scored by the shots, and the mode is completed.
- Completing all 11 makes the Allspark start the **Wizard Multiball** "BATTLE FOR CYBERTRON": 4 balls, 1,000,000,
  every main shot three times (same growing value), then the Allspark scores the **SUPER WIZARD JACKPOT** (sum of
  the 18 shots) and the round repeats. Starting it resets all wizard progress so the cycle starts over.

## 2. Settings
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 83 | BONUS EXTRA BALL AT | 5 | 0-10 | the extra ball is lit when the number of requirements started reaches this value [0x01035af0] |
| 86 | RESET WIZARD AT BALL START | NO | NO/YES | not read through `adj_get` anywhere (open question) |
No other adjustment; values, counts and ball save are fixed.

## 3. State
| Name (watch) | RAM | Scope / init | Meaning |
|---|---|---|---|
| req[r] (req0, req4, req5, req10) | 0x0211210c + 16 x r + 4 x (p-1), u32 | per player; 0 at game start (0x010359f4(2) via event 0x26) | byte 0 = times started ("collected"), byte 1 = times completed |
| ahm_super | 0x00034eac | 0 at start | sum of this mode's shot awards (= super value) |
| ahm_total | 0x00034ecc | start award | total for the end screen |
| ahm_c0..c5 | 0x00034eb4 + 4i (u8) | 0 at start | hits per shot (max 2) |
| wmb_super | 0x00035aa4 | 0 at start and after each super | sum of shot awards (= super value) |
| wmb_total | 0x00035aa8 | start award | total |
| wmb_c0..c5 | 0x00035aac + 4i (u8) | 0 at start and after each super | hits per shot (max 3) |
| wizard MB count | 0x021121cc + (p-1) | per player | wizard multiballs started |
| AHM count | 0x02111e14 + (p-1) | per player | side modes started |
Game flags: 0x3c (60) side mode running; 0x3d (61) side mode played (blocks a restart until the wizard multiball
clears it); 0x3e (62) wizard multiball running; 0x15 (21) extra ball lit by the wizard count.

Requirement numbers [0x01035af0 callers; audits table 0x040c7a1e + 16 x r]:
| r | Requirement | Collected (counter / audits.csv) | Completed (counter / audits.csv) |
|---|---|---|---|
| 0 | Megatron multiball (start / super jackpot) | 0x81 / #137 REQ. 1 COLLECTED | 0x8c / #148 WIZARD MB: REQ. 1 COMPLETED |
| 1-4 | Starscream, Shockwave, Blackout, Devastator (start / completed, see `battles.md`) | 0x82-0x85 | 0x8d-0x90 |
| 5 | Optimus multiball (start / super jackpot) | 0x86 / #142 | 0x91 / #153 |
| 6-9 | Bumblebee, Ironhide, Mudflap & Skids, Ratchet | 0x87-0x8a | 0x92-0x95 |
| 10 | All Hail Megatron / Autobots Roll Out (both at its start) | 0x8b / #147 | 0x96 / #158 |
A requirement belongs to a group by number, not by the player's side: the Megatron multiball is in the Decepticon
group even when an Autobot player plays it.

## 4. How it starts
### 4.1 Requirements and extra ball [0x01035af0]
- (r, 1) collected: byte 0 += 1 (max 255), audit; then if the number of requirements with byte 0 != 0 equals
  adj 83 (5) and flag 0x15 is clear: set flag 0x15 and light the extra ball (0x01007b40).
- (r, 2) completed: byte 1 += 1 (max 255), audit.
- Wizard reset 0x01035ad0 (at the wizard multiball start): both bytes of all 11 cleared, battle progress and
  Megatron / Optimus multiball progress reset (0x010359f4(2): 0x01022b88(0xff), each battle's reset, 0x01027510,
  0x01029558, 0x0100bd1c, 0x0100dcc0) (verified in emulator: wizard_multiball.jsonl 40.94 s, req0 / req4 / req5 -> 0).

### 4.2 All Hail Megatron / Autobots Roll Out [0x0100fff0, gate 0x0100ff80]
Qualifies when no multiball runs (`any_multiball_running` 0x01006704: Mudflap & Skids, Optimus A/D, Megatron
A/D, wizard multiball), all 5 own-side requirements are completed (Decepticon r 0-4, Autobot r 5-9: byte 1 != 0)
[0x01035db4], flag 0x3d is clear [0x0100ff58] and no timed mode runs (`any_timed_mode_running` 0x010067bc: the
seven timed battles, double or fast scoring) [0x0100ff80]. Started by the **left eject (Allspark, sw 3)**; the eject handler tries, in this order: wizard
multiball hit, side-mode hit, side-mode start, wizard multiball start, Optimus / Megatron hits, battles
[0x0100a788]. Start:
- shot counters and super = 0; **1,000,000 x the Allspark shot multiplier**; flags 0x3c, 0x3d set; counter 0x7e
  (#134 WIZARD STARTED); requirement 10 collected and completed (counters 0x8b, 0x96); intro deff 81 "COMPLETE ALL
  SHOTS FOR SUPER JACKPOT" via task 0x79, leff 78, sound 0x11a [0x0100fff0, 0x01010544].
- The ball is held in the eject during the intro, about 6 s (verified in emulator: wizard_all_hail_megatron.jsonl
  start 18.14 s, eject coil 22 at 24.35 s; wizard_multiball.jsonl start 19.37 s, coil 22 at 25.28 s).

### 4.3 Wizard Multiball [0x010363ec, gate 0x010363b4]
Qualifies when all 11 requirements are completed [items_all_collected 0x01035d50], no multiball runs
(`any_multiball_running` 0x01006704) and the side mode is not running (flag 0x3c) [0x010363b4]. Timed battles,
double and fast scoring do not block it. Started by the left eject. Because the side-mode start is tried first, with all 11 done and
flag 0x3d clear the side mode starts instead; the wizard multiball needs the side mode already played.
- `multiball_start(4 if none in play else in_play + 3, 0, ball save 937 ticks = 15.2 s, grace 312 ticks = 5.1 s)`
  (verified in emulator: wizard_multiball.jsonl 40.94 s).
- shot counters and super = 0; flag 0x14 cleared (add-a-ball available again) when no other multiball runs (tested before flag 0x3e is set;
wizard_multiball.jsonl 40.94 flag 20 cleared by 0x1036484); flag 0x3e set;
  wizard-MB count += 1; **wizard reset** (4.1); flag 0x3d cleared; counter 0x97 (#159 WIZARD MULTIBALL STARTED);
  **1,000,000 x Allspark multiplier**; intro deff 86 "BATTLE FOR CYBERTRON / COMPLETE ALL SHOTS FOR SUPER
  JACKPOT" via task 0x7c (10.5 s); the ball stays in the eject about 11.5 s [0x010363ec] (verified in emulator:
  start 40.94 s, eject coil 22 at 52.47 s).

## 5. Behaviour while running
Shot index (wizard numbering; table rows {mask, lamp group, counter address, max hits, multiplier slot}):
0 Allspark / left eject, 1 left orbit, 2 left ramp (also the Megatron lock entry), 3 center lane, 4 right orbit,
5 right ramp [tables 0x040c66e0 side mode, 0x040c7ac4 wizard MB]. Awards are x that shot's multiplier
(`FUN_01023538`, slot 1-6).

### 5.1 Side mode [0x01010174]
| Trigger | Condition | Effect | Deff | Sound / leff |
|---|---|---|---|---|
| shot i | its counter < 2 | **500,000 + 50,000 x (total hits so far)** x mult [0x01010100]; counter += 1; added to super and total; counter 0x7f (#135 WIZARD AWARDS) | 83: on a shot's first hit the character of that shot: Decepticon SOUNDWAVE, DEMOLISHER, STARSCREAM, SHOCKWAVE, BLACKOUT, DEVASTATOR / Autobot ARCEE, SIDESWIPE, BUMBLEBEE, IRONHIDE, MUD & SKIDS, RATCHET (index 0-5) [msg tables 0x040c66c8 / 0x040c66d4]; second hit: value only | 0x11b, 0x11c / leff 81 |
| shot i | counter = 2 | nothing from this mode | | |
| Allspark | all six counters = 2 [portal_mb_all_shots_done] | **super = ahm_super x Allspark multiplier**; counter 0x80 (#136 WIZARD COMPLETED); mode ends (flag 0x3c cleared) | 84 "ALL HAIL MEGATRON / COMPLETED" or "AUTOBOTS ROLL OUT / COMPLETED", then total 85 | 0x128, 0x12a / 0x12c |
Observed (wizard_all_hail_megatron.jsonl): 26.33-59.62 twelve shots 500,000, 550,000 ... 1,050,000; 63.57 super
**9,300,000** (the sum), deff 84 at 64.22, deff 85 at 66.84. The background deff 82 "ALL HAIL MEGATRON / NEXT
SHOT = n / SUPER = n" ("SUPER LIT / SHOOT THE ALLSPARK" when lit) with music 0x3c appears after the intro
(33.45 s). With the counters poked to 2, the super is only the real awards (wizard_multiball.jsonl 30.75 s:
500,000).

### 5.2 Wizard Multiball [0x010365c4]
| Trigger | Condition | Effect | Deff | Sound |
|---|---|---|---|---|
| shot i | counter < 3 | **500,000 + 50,000 x (total hits this round)** x mult [0x01036534]; counter += 1; added to super and total; counter 0x98 (#160 WIZARD MULTIBALL AWARDS) | 88 (value, shot, "complete" flag) | 0x131 |
| Allspark | counter 0 >= 3 and all others at 3 [0x01036318] | **SUPER WIZARD JACKPOT = wmb_super x Allspark multiplier**; all counters and wmb_super = 0 (new round, values restart at 500,000); counter 0x99 (#161) | 89 "SUPER WIZARD JACKPOT" | 0x135-0x139 |
| shot at 3 | super not lit | nothing | | |
Observed (wizard_multiball.jsonl): 55.09-103.52 eighteen shots 500,000 ... 1,350,000; 107.44 super wizard
jackpot **16,650,000**. Background deff 87 "NEXT SHOT = n" / "SHOOT THE ALLSPARK / SUPER = n" + music 0x3d from
the start (40.95 s).

## 6. How it ends
- Side mode: ends at the super (6 shots x 2 done) [0x010103c0(1)] -> deff 84 then total deff 85 via task 0x7b;
  or at the end of the ball / drain [0x010103f8 -> 0x01010330(0), task 0x8f]; total not shown in tilt / game
  over. It is single-ball; flag 0x3d stays set so it cannot restart before the next wizard multiball.
  (verified in emulator: wizard_all_hail_megatron.jsonl flag 60 cleared at the super 63.57 s)
- Wizard multiball: ends when one ball is left (flag 0x3e cleared, task 0xc5 grace for add-a-ball
  [0x0103686c, 0x010367c4]); total deff 90 "WIZARD MULTIBALL TOTAL: n" via task 0x90 [0x01036814]
  (verified in emulator: flag 62 cleared 115.65 s, deff 90 at 120.68 s). Afterwards all requirements are empty
  (reset at the start), so the player starts collecting again.
- Add-a-ball (Allspark mystery, 0x01024a60: `multiball_start(1, 0, 312, 187)`, sets flag 0x14) works in all
  multiballs and revives one still in its grace window.

## 7. Media
| When | Display effect | Sound | Lamp effect |
|---|---|---|---|
| side mode start | 81 "COMPLETE ALL SHOTS / FOR / SUPER JACKPOT" | 0x11a | 78, 79 |
| side mode background | 82 title (ALL HAIL MEGATRON / AUTOBOTS ROLL OUT, run-time message), "NEXT SHOT = n", "SUPER = n" | music 0x3c | |
| side mode shot | 83 character name + value | 0x11b, 0x11c | 81 |
| side mode completed / total | 84 / 85 | 0x128, 0x12a / 0x12c | 82 / 83 |
| wizard MB start | 86 "BATTLE / FOR / CYBERTRON", "COMPLETE ALL SHOTS / FOR / SUPER JACKPOT" | 0x12d, 0x12e, 0x130 | 86 |
| wizard MB background | 87 "NEXT SHOT = n" / "SHOOT THE ALLSPARK / SUPER = n" | music 0x3d | |
| wizard MB shot / super / total | 88 / 89 "SUPER WIZARD JACKPOT" / 90 "WIZARD MULTIBALL TOTAL:" | 0x131 / 0x135-0x139 / 0x13a | 89 / 90 / 91 |
Music table rows: 3 = side mode (flag test 0x01010958) -> deff 82 + music 0x3c; 6 = wizard multiball
(0x01037018) -> deff 87 + music 0x3d.

## 8. Lamps
Side mode lamp groups 0x37-0x3c: two inserts per shot (purple + red arrow: Allspark 13/14, left orbit 17/18, left
ramp 46/45, center 42/41, right orbit 37/38, right ramp 32/33) - one per hit left (inferred). Wizard multiball
groups 0x41-0x46: three inserts per shot (purple, red, orange) - one per hit left (inferred). The Allspark flashes
when the super is lit (inferred). Character inserts (4-7, 23-26) show battle requirements (`battles.md`).

## 9. Interactions
- The side mode blocks: the Megatron lock (not held, no lighting), the Optimus battle, character battle starts;
  the wizard multiball blocks the same plus the Megatron / Optimus multiballs (all gates test flags 0x3c / 0x3e).
- Combos (0x01002fec) keep scoring during both modes (150,000, 175,000 ... per repeat, seen in the AHM trace).
- The wizard reset at the multiball start also resets Megatron / Optimus multiball saved progress and the battles.

## 10. Reference scenarios
`traces/wizard_all_hail_megatron.txt`, `traces/wizard_multiball.txt` with `traces/watch_wizard.tsv` (pokes marked
in the scenario headers and `mark poke_*` lines).

## 11. Open questions
- Adj 86 RESET WIZARD AT BALL START is not read with `adj_get`.
- The extra-ball test uses "== adj 83" on the count of started requirements; with adj 83 = 0 it would never
  fire, and once flag 0x15 is set it is not re-armed in this code path (where flag 0x15 is cleared was not traced).
- Lamp behaviour per hit was not captured lamp by lamp.
- The real path to the wizard (completing all battles) was not played without pokes.
