# Energon targets, Allspark (left eject) and the Allspark mystery award

Audience: a developer rebuilding Transformers Pro 1.80 (`tf_180`) in MPF who has not read the ROM. Addresses refer
to `code/tf_decompiled.c` (headers `// ==== ADDR NAME`); OS helper names as in that file. 1 tick = 16.2 ms
(measured: a battle "second" of 66 ticks lasts 1.07 s). Reference traces (factory settings, no pokes):
`traces/allspark_energon.jsonl` (scenario `traces/allspark_energon.txt`), and the Allspark-as-battle-shot hits in
`traces/battle_bumblebee.jsonl` / `traces/battle_shockwave.jsonl`.

## 1. Summary
- Three **Energon** standups (left sw 2, center sw 49, right sw 46). Hitting an unlit one lights it (75,000);
  hitting a lit one scores 10,000. Lighting the third completes the set: **250,000 (+25,000 per earlier set,
  max 750,000)**, the screen "ALLSPARK LIT", and one **Allspark** is banked. Then all three go unlit again.
- The **Allspark** is the left eject (sw 3, kicked out by coil 22). Every ball that enters it counts as the
  "Allspark shot" (shot 0) for the mode-start shots and every character battle, and scores 5,070. If at least one
  Allspark is banked, one is spent and a **mystery award** is picked (deff 52): Light Special, Light Extra Ball,
  200,000, +1 bonus multiplier, Add-a-Ball, Add More Time, Pops score, Bonus Hold, Bonus X Hold, Shot
  Multiplier, Super Spinner, Super Pop Bumpers.
- While a **multiball** runs (Mudflap & Skids, Optimus A/D, Megatron A/D or the wizard multiball:
  `any_multiball_running` 0x01006704), Energon hits are worth only 5,000 and do not light anything. Timed modes
  (the other seven battles, double / fast scoring) do **not** affect the Energon targets.

## 2. Settings (operator adjustments)
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 42 | COMPETITION MODE | NO | NO/YES | YES (or game flag 0xf) makes the mystery award follow a fixed 10-step sequence [0x00017ea0, weight fns 0x01024854..0x01024ea0] |
None for the Energon targets themselves [0x010309a4].

## 3. State
| Name | RAM | Size | Scope | Init / reset | Meaning |
|---|---|---|---|---|---|
| energon_lit | 0x021120bc + 4*(p-1) | 4 | per player | at game start (event 0x26) and after each completed set: bits of targets whose switch is marked disabled/broken (`sw_is_disabled`), normally 0 [0x01030908, 0x010308a8] | bit 0 left (sw 2), bit 1 center (sw 49), bit 2 right (sw 46) |
| energon_sets | 0x021120cc + (p-1) | 1 | per player | 0 at game start [0x01030908]; +1 per completed set, stops at 255 [0x010309a4] | sets completed this game; drives the set value |
| allspark_lit | 0x02111f50 + (p-1) (written as 0x02111f4f + p) | 1 | per player | 0 at game start [0x01023fc8]; +1 per Energon set [0x0102402c]; -1 per collection [0x010243b4] | banked Allspark awards (they stack) |
| allspark_last_award | 0x02111f48 + 2*(p-1) | 2 | per player | 0 at game start [0x01023fc8] | item number (1-12) of the last mystery award; that item gets weight 0 next time (no repeat) [0x01024808] |
| allspark_comp_step | 0x02111f44 + (p-1) | 1 | per player | 9 at game start [0x01023fc8] | competition sequence step: before an award, 0 becomes 10; after it, -1 [0x010243b4] |
| (task 0xb0) | – | – | 10 ticks | started after a completed set [0x010309a4 `FUN_0000abe8(0xb0,10,0)`] | for 10 ticks (162 ms) Energon hits do nothing (inferred: debounce of a ball rattling between targets) |

(verified in emulator: traces/allspark_energon.jsonl, vars energon_mask, energon_sets, allspark_lit, allspark_last)

## 4. How it starts
Always active during a ball. Each Energon switch handler (sw 2 0x01033a28, sw 49 0x01033a64, sw 46 0x01033aa0)
calls `energon_hit(index, lamp)` [0x010309a4] with index 0 left, 1 center, 2 right, then scores its own switch
value (1,110, from the switch table).

## 5. Behaviour

### 5.1 Energon hit [0x010309a4]
| Trigger | Condition | Effect | Display | Sound | Lamp effect |
|---|---|---|---|---|---|
| sw 2 / 49 / 46 | a multiball runs (`any_multiball_running` 0x01006704: game flag 0x1e Mudflap & Skids, 0x1f / 0x22 Optimus A / D, 0x25 / 0x29 Megatron A / D, 0x3e wizard multiball) [0x0103096c] | 5,000; nothing lit | – | 0x25c | leff 139 |
| same | task 0xb0 running (162 ms after a set) | nothing (not even 5,000) | – | – | – |
| same | target already lit, set not complete | 10,000 | – | 0x25d | leff 141 |
| same | target unlit and not the last one | light it; 75,000 | deff 124 (Energon picture; gets the lit-target mask and the new bit as parameters; its code also holds an "ALLSPARK / LIT" page) | 0x25e, then 0x25f about 1 s later (task 0x97, 0x01030984) | leff 140 |
| same | this hit lights the third target (or all three were already lit) | **set complete**: energon_sets += 1; energon_lit reset; **250,000 + 25,000 x (sets before this one)**, capped at 750,000 [0x01030934]; Allspark banked (+1); 0x0100af0c (Megatron lock feature, see that spec) | deff 125 "ALLSPARK / LIT" | 0x260, then 0x13e, 0x13f from deff 125 | leff 142 (param 0x87); then leff 40 (Allspark flasher) while an Allspark is banked |

Scores here are plain `score_add` (the playfield multiplier applies; no shot multiplier).

Observed (traces/allspark_energon.jsonl): 18.58 left 75,000 (+1,110 switch), deff 124; 20.77 left again 10,000;
22.97 right 75,000; 25.16 center 250,000 with deff 125, energon_sets 1, allspark_lit 1; second set 43.10
275,000; third set 55.87 300,000.

### 5.2 Allspark: the left eject (sw 3, coil 22) [0x0100a754, 0x0100a788]
The left eject is an OS ball device; its rule callback 0x0100a788 gets these events:
- **2 = ball entered** (only when not tilted / not in game over, `DAT_00031468 & 0x310 == 0`). In order:
  audit 0x45; `FUN_010237ac(1)`; Megatron/Optimus/wizard hooks (0x010365c4, 0x01010174, **0x0100fff0** the
  side-complete feature, 0x010363ec, 0x01027b74, 0x01029bf4, 0x0100c430, 0x0100e29c); **every character battle
  with shot 0** (8 hit functions, see `battles.md`); 0x010047b8(2), 0x01003a64; **Allspark award**
  [0x010243b4]; **mode-start shot 0** [0x01020074(0)]; combo shot 0 [0x01002f0c(0,1)]; 0x01024fe8; **5,070
  points** [0x01032d2c(0x13ce)]. Then it waits while any display-show task 0x5d-0x7e runs (the award or battle
  screens) before letting the ball go [0x0100a8a8 loop].
- **4 / 9 = eject**: sound 0x158, leff 22; **3**: pulse coil 22 (`FUN_00002078(0x16,...)`).
- **7 = eject retry / warning**: waits for the device, then sound 0x157 and leff 21.

Observed: the switch closes, the rule runs about 0.75 s later (device settle), 0x157 + leff 21 at the end of the
wait, 0x158 + leff 22, coil 22 64 ms about 0.1 s after that. With no award showing the ball is held about 1.9 s
(traces/allspark_energon.jsonl 35.51 -> 37.26); with the mystery award showing about 4.4 s (29.34 -> 33.70).

### 5.3 The Allspark mystery award [0x010243b4]
Only if allspark_lit > 0:
1. Kill a previous award display task 0x5e.
2. Pick an award from the award list at ROM 0x040dde30 (12 items, `bag_weighted_pick` [0x0000bae8]): each item's
   weight function returns a weight; if any weight is >= 1000 the highest wins outright, otherwise a weighted
   random pick.
3. Start task 0x5e (0x01024388), which shows **deff 52** with the award text; run the award (`bag_run_award`,
   bumps the item's audit).
4. allspark_last_award = item; allspark_lit -= 1; competition step: if 0 set 10, then -1.

| Item | Text (deff 52) | Base weight | Weight is 0 when | Forced (>= 1000) when | Award | Audit |
|---|---|---|---|---|---|---|
| 1 | SPECIAL LIT | 1 | last award | competition step 0 | light Special [0x01008528] | MYSTERY: LIGHT SPECIAL |
| 2 | EXTRA BALL LIT | 5 | last award | competition step 1 | light Extra Ball [0x01007b40] | MYSTERY: LIGHT EXTRA BALL |
| 3 | 200,000 | 200 | last award | competition step 2 | 200,000 points [0x01024998] | MYSTERY: 200,000 |
| 4 | %iX BONUS MULTIPLIER | 150 | last award | competition step 8 | bonus multiplier +1 [0x01000e44(1)] | MYSTERY: BONUS X |
| 5 | ADD-A-BALL | 300 -> only offered during a multiball, and once | no multiball (0x01006760) or flag 0x14 set | always when offered (weight + 1000) | add one ball (0x0103aff4), set flag 0x14, notify Mudflap/Optimus/Megatron/wizard multiballs [0x01024a60] | MYSTERY: ADD-A-BALL |
| 6 | ADD MORE TIME | 250 -> only during a timed mode, once per mode | no timed mode (0x010067bc) or flag 0x13 set | always when offered (+1000) | every running battle +15 s (cap 90 s), Bumblebee phase 1 value restored / phase 2 +5 s, double and fast scoring time; sets flag 0x13 [0x01024b14] | MYS. ADD MORE TIME |
| 7 | POPS SCORE %,02lu | 150 | last award, or 0x0102c8a4 true (super pops running, inferred) | competition step 9 | pop bumper value up (0x0102c624) | MYSTERY: POPS GROW |
| 8 | BONUS HOLD | 100 | last award, or flag 0x4b set (already held) | competition step 7 | set flag 0x4b | MYSTERY: BONUS HOLD |
| 9 | BONUS X HOLD | 100 | last award, or flag 0x4a set | competition step 6 | set flag 0x4a | MYSTERY: BONUS X HOLD |
| 10 | SHOT MULTIPLER(S) LIT | 100 | last award, or no shot multiplier can be raised (0x01023494) | competition step 5 | light shot multipliers (0x010236e8) | MYSTERY: SHOT MULTIP. LIT |
| 11 | SUPER SPINNER LIT | 100 | last award, or super spinner already lit (0x01032280) | competition step 4 | light super spinner (0x010325bc) | MYSTERY: SUPER SPINNERS LIT |
| 12 | SUPER POP BUMPERS LIT | 100 | last award, or 0x0102c8a4 true | competition step 3 | light super pops (0x0102d31c) | MYSTERY: SUPER POPS LIT |

Item table: ROM 0x040dde30, 0x18 bytes each {weight fn, award fn, weight store, name, u16 base weight at +0x10,
u16 audit at +0x14} [0x0000bae8, 0x0000bc2c]. Weights are recomputed at every pick. The competition sequence
(starting value 9, so the first award of a game is item 7): 7 POPS, 4 BONUS X, 8 BONUS HOLD, 9 BONUS X HOLD, 10
SHOT MULT, 11 SUPER SPINNER, 12 SUPER POPS, 3 200,000, 2 EXTRA BALL, 1 SPECIAL, then again from 7 (inferred from
the weight functions; Add-a-Ball and Add Time still force themselves in because they add 1000 too).

Observed (factory settings, no multiball, no timed mode): 30.09 item 4 BONUS X; 48.02 item 12 SUPER POPS (then
deff 149 "SUPER POP BUMPERS"); 60.79 item 4 again (traces/allspark_energon.jsonl).

### 5.4 2-bank, Bumblebee and Optimus targets (only how they touch battles)
- **Bumblebee target (sw 1)** [0x01033adc]: advances the lit character battle to the next one (see
  `battles.md` 4.4); is battle shot 6 (only the Bumblebee battle uses it); then the Bumblebee letters
  [0x01001a70] (own spec) and 30 points.
- **Optimus Prime target (sw 51)** [0x01033d3c]: counts as battle shot 3 (the center shot) for all eight battles,
  locked out together with the center lane by task 0x54; it is not a mode-start shot.
- **Pop bumpers (sw 30-32)** [0x01032f8c]: advance the lit battle, move the Devastator rover, and pause running
  battle timers for 156 ticks.
- **2-bank (sw 37, 50)** [0x0102e9c0]: fast scoring qualify (deff 126 "N MORE FOR FAST SCORING"). Fast scoring
  is a timed mode; it does not change the Energon targets (only multiballs do) and does not block battle
  qualifying (`clu_start_allowed` 0x01022ca8 tests multiballs, battles and flag 0x3c only). No direct battle link.

## 6. How it ends
Energon sets and the Allspark bank persist for the whole game (per player, reset only at game start). An
unspent Allspark stays banked across balls.

## 7. Media
| When | Display | Sounds | Lamp effect / lamps |
|---|---|---|---|
| Energon target lit | deff 124 (priority 128) | 0x25e, 0x25f | leff 140 |
| Energon lit target re-hit | – | 0x25d | leff 141 |
| Energon during a multiball | – | 0x25c | leff 139 |
| Set complete | deff 125 "ALLSPARK / LIT" (priority 129) | 0x260; 0x13e, 0x13f (deff) | leff 142 |
| Allspark banked | – | – | leff 40 rule (runs while allspark_lit > 0 [0x01024058, rule 0x01024f24]): pulses the Allspark flasher, coil 32 FLASH: ALLSPARK, continuously (observed) |
| Allspark collected | deff 52 (award text cycling through all items, then the chosen one) | 0x140, then 0x143 (item 5) / 0x142 (item 6) / 0x144 (others), 0x141 | leff 41 |
| Eject | – | 0x157 then 0x158 | leff 21, leff 22, coil 22 |
deff 51 also draws "ALLSPARK / LIT" with sounds 0x13e/0x13f, but no code path that starts it was found (only its
deff table entry references it).

## 8. Lamps
Energon inserts: 48 ENERGON (LEFT), 54 ENERGON (CENTER), 35 ENERGON (RIGHT). Observed: an unlit target flashes
(about 0.33 s period), a lit one is solid on, all flash again after a set (traces/allspark_energon.jsonl lamp
events 18-26 s). The lamp rule is 0x01030f80 (registered by 0x010312e4). The Allspark has no "lit" insert of its
own: the flasher coil 32 shows a banked Allspark. Inserts 12-15 ALLSPARK (X / PURPLE / RED / ORANGE) are the shot
multiplier, mode-start (purple Decepticon / red Autobot) and battle-shot (orange) arrows of shot 0.

## 9. Interactions
- Multiballs (Mudflap & Skids, Optimus, Megatron, wizard multiball) freeze the Energon targets at 5,000
  [0x0103096c -> 0x01006704]; the Energon lamp rule then drives all three inserts the same way (FUN_00007714, regardless of lit state)
  [0x01030f80]. Timed battles, double and fast scoring leave them working normally (observed:
  traces/switches.jsonl 128.67, sw 46 lights the right target for 75,000 with deff 124 while the Blackout battle,
  task 0xa0 started 67.58, end task 0x82 at 140.18, is running).
- A completed set also calls 0x0100af0c (Megatron multiball lock lighting; deff 139) - see the Megatron spec.
- The mystery award can add time to battles (item 6) and balls to Mudflap & Skids (item 5).
- The left eject waits for display-show tasks 0x5d-0x7e, so battle intros started by the Allspark hold the ball
  until they finish.

## 10. Reference scenario
`traces/allspark_energon.txt`: start, plunge, sling; left Energon twice, right, center (set 1, 250,000);
collect at the eject (BONUS X); eject with nothing banked (5,070 only); set 2 (275,000); collect (SUPER POPS);
set 3 (300,000); collect; drain. Key events listed in 5.1-5.3.

## 11. Open questions
- What starts deff 51 (same text and sounds as deff 125)? No `deff_start(0x33)` or show call found.
- Exact meaning of weight-function conditions 0x0102c8a4 (pops), 0x01032280 (spinner) is taken from the callee
  names in the award functions, not traced.
- Task 0x97 (0x01030984) after a target is lit plays 0x25f; whether it does more was not checked.
