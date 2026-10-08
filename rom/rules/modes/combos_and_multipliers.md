# Combos, multipliers, lanes and the bonus — Stern Transformers Pro 1.80 (`tf_180`)

Sources: `[0xADDR]` = function in `code/tf_decompiled.c`; "observed" = `rules/traces/combos.jsonl`
(scenario `combos.txt`, watch `watch_combos.tsv`), `scoring.jsonl` (lanes, bonus X) and `game_flow.jsonl`
(bonus); "inferred" = reasoning. Factory settings. 1 tick ≈ 16.26 ms. Points go through `score_add`
(× playfield multiplier, 2 during double scoring).

## 1. Summary

- **Combos**: six major shots (left eject, left orbit, left ramp, center lane, right ramp, right orbit).
  Making a major shot within about 5 s (+2 s grace) of the previous one is an n-way combo worth
  100,000 + 25,000 × n (× that shot's multiplier). The left eject and the left ramp cannot combo into
  themselves.
- **Lanes**: each side has four lane lamps (two top-lane lamps, return lane, outlane). Lighting all four
  of a side **completes** it: completing your **own** side's lanes (Decepticon = purple Megatron lanes on the
  left, Autobot = red Optimus lanes on the right) lights **shot multipliers**; completing the **other** side's
  lanes raises the **bonus multiplier** by 1 (cap 25X).
- **Shot multipliers**: each major shot has a 1X/2X multiplier; when lit, the next major shot made goes to 2X
  ("LEFT LOOP MULTIPLIER AT 2X"); with all six at 2X a roving 3X runs.
- **Bonus** at end of ball = (670 × switches hit this ball + 125,000) × bonus multiplier.

## 2. Settings
| Adj # | ROM name | Default | Effect |
|---|---|---|---|
| 90-95 | COMBO CHAMPION 20, BEST COMBO CHAMPION 5-WAY (327681 = 5<<16 \| 1), awards | | Combo high-score tables fed by the counters below (OS/attract; not traced) |
No adjustment changes the combo window or values.

## 3. State (p = player, arrays [p-1])
| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| combo_way | 0x34b84 (u8) | running chain | 1 at a chain start | Current n-way [0x01002f0c] (observed 1..6) |
| combo_mask | 0x34b88 (u8) | running chain | 0x3f | Shots allowed as the next combo: all 6, minus the shot just made if it was the eject (bit 1) or left ramp (bit 4) (observed 63, 59, 62) |
| combo_ticks | 0x34b8c (u16) | running chain | 312 at each combo shot | Window countdown, −7 every 7 ticks [0x01002b5c] |
| combo_total | 0x2111d08 + 2(p-1) (u16) | per game | 0 (0x010026ec) | Combos made (way ≥ 2) |
| combo_best | 0x2111d10 + 4(p-1) (u32) | per game | 0x10001 | Best combo, way << 16 \| multiplier (observed 0x60001 = 6-way) [0x01002918] |
| combo display | 0x21120ac / 0x21120ae | | | Last way / total for the status panel [0x0102f1c0] [0x0102f1f0] |
| lanes lit | lamp state, groups 76 (left: 50, 51, 8, 9) and 77 (right: 52, 49, 10, 11) | per ball (lamps) | | [lamp_groups.json] |
| lanes_left_done / right_done | 0x2112080 / 0x2112088 + 2(p-1) (u16) | per game | 0x0102dad8 | Completions (observed 1) |
| shot_mult[s] | 0x2111f28 + 4(s-1) + (p-1), s = 1..6 (u8) | per ball | 1 at ball start unless the hold flag 0x16+s-1 is set [0x01023418] | Shot multiplier, max 2 [table 0x040c6f58] |
| mult_lit | 0x2111f40 + (p-1) (u8) | per ball | 0 | "Multipliers lit": next major shot gets +1X [0x010236e8] |
| roving 3X | task 0xb6, index 0x351c0 / 0x351c4 | while all 2X | | [0x01023650] |
| bonus_count | 0x34b3c + 2(p-1) (u16) | per ball | 0 at ball start (event 0x13 hook 0x01000d58) | +1 per playfield switch handler [0x01000dfc] |
| bonus_mult | 0x2111cf0 + (p-1) (u8) | per ball | 1 at ball start unless flag 0x4a (BONUS X HOLD) [0x01000d58] | +1 per call of 0x01000e44, cap 25 |
| held_bonus | 0x2111ce0 + 4(p-1) (u32) | per ball | 125,000 at ball start unless flag 0x4b (BONUS HOLD) [0x01000d58] | Added to the bonus base |

## 4. Combos [0x01002f0c] [0x01002be4] [0x01002b5c] [table 0x040c5c7c]

### 4.1 Shots
| Shot | Index / mask | Switch, handler | Combo arrow lamp | Shot multiplier slot |
|---|---|---|---|---|
| Left eject (Allspark) | 0 / 0x01 | sw3 0x0100a788 (when the eject kicks) | 15 ALLSPARK (ORANGE) | 1 ALLSPARK |
| Left orbit | 1 / 0x02 | sw6 0x010332e4 | 19 LEFT ORBIT (ORANGE) | 2 LEFT LOOP |
| Left ramp | 2 / 0x04 | sw10 L. ramp exit 0x01033824 | 44 LEFT RAMP (ORANGE) | 3 LEFT RAMP |
| Center lane | 3 / 0x08 | sw11 0x01033b3c | 40 CENTER LANE (ORANGE) | 4 CENTER LANE |
| Right ramp | 4 / 0x10 | sw14 R. ramp exit 0x01033918 | 34 RIGHT RAMP (ORANGE) | 5 RIGHT RAMP |
| Right orbit | 5 / 0x20 | sw12 0x01033530 → 0x01033488 | 39 RIGHT ORBIT (ORANGE) | 6 RIGHT LOOP |
- Right orbit (sw12) counts only when the ball did not just come round the left orbit (switch timer 7 from
  the left orbit) and not within 187 ticks (3.0 s) of the previous right orbit shot (timer 9)
  [0x01033530]. Observed: sw12 1.2 s after sw6 never counted (t 23.76, 69.09 ...); sw12 alone counted
  (t 38.99). The left orbit (sw6) counted every time.
- Ramp entrances (4, 35), orbit bottom (5) and the spinner are not combo shots.

### 4.2 Rule
On a major shot:
1. If no combo window is running (task 0x92/0x93): combo_way = 1, no award.
2. Else if the shot's bit is in combo_mask: combo_way + 1, combo_total + 1, best updated,
   **award = M × (100,000 + 25,000 × combo_way)** where M = that shot's multiplier (1, 2, or 3 when the
   roving 3X is on it) [0x01002c7c] [0x01023538]; leff 35, audit 154 (0x9a).
3. Else (shot not allowed, e.g. left ramp twice): the chain keeps its way count and the window restarts.
4. In all cases the window tasks 0x92/0x93 are killed; then, if no **multiball** runs (0x01002afc ->
   `any_multiball_running` 0x01006704): mask = 0x3f minus the shot if it is the eject or left ramp;
   combo_ticks = 312; task 0x92 restarted. During a multiball no new window starts (a window already open still
   pays the next shot, then ends). Timed battles, double and fast scoring do not affect combos. Observed: task
   0x92 restarted at 34.07-64.35 during the Blackout battle (traces/battle_blackout.jsonl, battle from 26.15),
   but never during Mudflap & Skids (traces/battle_mudflap.jsonl, flag 30 27.34-48.99; next window 54.60) or
   Optimus A (traces/optimus_autobot.jsonl, flag 31 34.93-81.53).
- Window: task 0x92 counts combo_ticks down by 7 every 7 ticks (312 ticks = 5.07 s), not counting while
  0x0103a4f0(3) reports the ball held; then task 0x93 keeps the window open **124 more ticks (2.0 s)**.
  Observed: countdown 312 → 0 in 5.1 s (t 30.83 → 35.94); shots 5.7 s and 6.9 s after the previous one still
  combined (t 49.37, 56.30); 8.2 s later the chain restarted at 1 (t 67.91).
- leff 34 lights the arrows of the allowed shots and blinks faster as the window runs out (sleep =
  ticks/31, min 2) [0x01003104].
- Observed values: 2-way 150,000, 3-way 175,000, 4-way 200,000, 5-way 225,000, 6-way 250,000 (t 24.95-30.83
  and t 70.28-79.74, every multiplier 1). There is no cap on the way count in the code.

### 4.3 Display
- deff 48 "%d-WAY COMBO / value" (with DOUBLE/TRIPLE variants, msg 0x6d4-0x6d6, sounds 0x2b7-0x2b9,
  0x2ba / 0x2bb / 0x2bc every 5th way) exists [0x01003354] but **was never started** in any trace and no
  starter was found. Combos show in the status panel drawn by 0x0102f200 ("%d-WAY / COMBO", "%d COMBOS").
- deff 48's second page refers to milestones "SUPER COMBOS AT 10", "SUPER LOOPS AT 25", "COMBO
  MULTIBALL AT 50" and "SUPER COMBO +%,02lu" (250,000 + 50,000 × (n−1), cap 500,000) [table 0x040c5cc4]
  [0x01002ca4]; the function that would evaluate them (0x01002d54) has no caller: treat as unused in 1.80.

## 5. Lanes (Megatron / Optimus) [0x0102db28] [0x0102e208]
| Switch | Lamp it lights | Group |
|---|---|---|
| 8 left top lane | 51 TOP LANE (PURPLE/TOP), or 50 (PURPLE/BOT) if 51 is lit | Megatron (left, purple, group 76) |
| 24 left outlane | 8 LEFT OUTLANE | Megatron |
| 25 left return lane | 9 LEFT RETURN LANE | Megatron |
| 7 right top lane | 52 TOP LANE (RED/TOP), or 49 (RED/BOT) if 52 is lit | Optimus (right, red, group 77) |
| 28 right return lane | 10 RIGHT RETURN LANE | Optimus |
| 29 right outlane | 11 RIGHT OUTLANE | Optimus |
- Lamp unlit and the group not complete after lighting it: light it, **2,500**, leff 97 (left) / 100 (right),
  sound 0x169 / 0x16d.
- Lamp already lit: **1,000**, leff 98 / 101, sound 0x168 / 0x16c.
- Lighting the 4th lamp: the group is cleared, completions + 1, **10,000**, leff 99 / 102, sound 0x16a /
  0x16e, and:
  - own side (Decepticon on the left lanes, Autobot on the right lanes): shot multipliers lit
    [0x010236e8], deff 44 "%uX / n MULTIPLIER(S) LIT" (sounds 0x059, 0x05a).
  - other side: bonus multiplier + 1 [0x01000e44], deff 45 "OPTIMUS LANES / COMPLETED / %dX BONUS"
    (Decepticon player) or "MEGATRON LANES / COMPLETED / %dX BONUS" (Autobot player).
- A made top-lane skill shot lights both lamps of that lane (0x010335d0 / 0x0103361c call the lane function
  twice) (observed game_flow t 18.79, two 2,500 awards).
- Lane change: each flipper press (not during side choice, bonus, tilt or attract) rotates the lit lamps of
  one group by one position: left flipper the Megatron group in order 50 → 51 → 8 → 9, right flipper the
  Optimus group 52 → 49 → 10 → 11 [0x01032d5c] [0x01032dac] [0x0102dd58] (code; direction not traced).
- Base switch points on top of this (handlers): top lanes 2,560, return lanes 1,090, **outlanes 100,000**
  (rules/switches_and_shots.md).
- Observed (scoring.jsonl, Decepticon): 8, 8, 24 → 2,500 each; 25 → 10,000 + deff 44 + leff 37 (t 40.01);
  7, 7, 28 → 2,500 each; 29 → 10,000, deff 45, bonus_mult 1 → 2 (t 46.72).

## 6. Shot multipliers [0x010236e8] [0x010237ac] [0x01023538] [0x01023650]
- Lighting (own lanes complete, or left-eject award "SHOT MULTIPLIERS LIT"): if any of the six shots is below
  2X, mult_lit = 1 and leff 37 flashes the X lamps of those shots (12 ALLSPARK (X), 16 LEFT ORBIT (X), 47
  LEFT RAMP (X), 43 CENTER LANE (X), 31 RIGHT RAMP (X), 36 RIGHT ORBIT (X)); deff 44 shows "2X" and the count.
  If all six are at 2X: task 0xb6 starts a roving 3X (deff 44 shows "3X").
- Collecting: the next major shot made whose multiplier is below 2X goes to 2X, mult_lit = 0, deff 50
  "<SHOT> / MULTIPLIER AT / 2X" (sound 0x05b, 0x05c at 2X / 0x05d at 3X, leff 38) [0x01023c5c].
- Roving 3X: index moves 6 → 2 then back up every 46 ticks, blinking (leff 39); a shot whose index matches
  scores ×3 [0x01023650].
- Use: the multiplier multiplies the combo award and the mode-progress shot award 0x01020074 for that shot.
- Reset: every ball each shot goes back to 1X unless its hold flag (game flags 0x16-0x1b) is set; mult_lit
  cleared [0x01023418]. Tilt / ball end: 0x01023048 (event 0x65 / 0x1d).
- deff 49 "%uX / MULTIPLIER(S) LIT" (leff 36) exists [0x01023b10]; its starter was not found.

## 7. Bonus (end of ball) [0x01000ffc] [0x01000f38] [0x01000d58]
**bonus = (670 × bonus_count + held_bonus) × bonus_mult**, added with playfield multiplier 1.
- bonus_count +1 for every call of the common switch scoring helper 0x01032d2c, i.e. **every playfield
  switch handler** (slings, pops, lanes, targets, ramps, orbits, spinner per spin, eject, lock, Optimus,
  captive ball, outlanes...), except while state & 0x10 (no game) [0x01000dfc]. Not the trough, shooter
  lane or flipper buttons.
- held_bonus = 125,000 each ball. BONUS HOLD (left-eject award, flag 0x4b): at the end of that ball
  0x01000f68 stores 670 × count + held into held_bonus (hook list 0x38ec4, inferred end of ball) and the
  next ball keeps it.
- bonus_mult +1: completing the other side's lanes; left-eject award "%iX BONUS MULTIPLIER"
  [0x01024a0c]. Cap 25. BONUS X HOLD (flag 0x4a) keeps it for the next ball.
- Checked against traces: sounds.jsonl 127,680 = 125,000 + 4 × 670; basic.jsonl 130,360 = 125,000 + 8 × 670;
  game_flow.jsonl 128,350 (5 switches), 127,010 (3), 125,670 (1); scoring.jsonl 333,080 =
  (125,000 + 62 × 670) × 2; combos.jsonl 135,050 = 125,000 + 15 × 670.
- Display deff 25 (switches_and_shots.md): "BONUS", "%dX" value counting the multiplier up from 2 (8 frames
  per step below 6X, 4 above, sound 0x076 after the count), "TOTAL BONUS"; sounds 0x021 Autobot / 0x020
  Decepticon, 0x077 + 0x078, 0x079, 0x07a, 0x022, 0x001.

## 8. Lamps
- Combo arrows (orange) 15, 19, 44, 40, 34, 39 via leff 34 while a window runs.
- Shot multiplier X lamps 12, 16, 47, 43, 31, 36: leff 37 / 39 / rule 0x01023a84 (lit = below 2X flashing).
- Lane lamps 49-52, 8-11 hold the lane state.

## 9. Interactions
- No new combo window starts during a multiball (0x01002afc -> 0x01006704); the multiplier and combo totals feed the combo
  champion tables (adj 90-95).
- Left orbit / right orbit / ramp shots also advance the mode-progress ladder 0x01020074 (deff 91 "n MORE ...",
  owned by the mode specs) and the Starscream etc. modes; those awards appear next to the combo award in
  the traces (e.g. 10,000 / 15,000 / 20,000 / 25,000 from 0x010200e0, 100,000 from 0x010179d4).
- Double scoring doubles combo and lane awards but never the bonus.

## 10. Reference scenarios
- `traces/combos.txt` → `combos.jsonl`: chain 6 → 12 (not a shot) → 10 → 10 (not allowed) → 14 → 11 → 11 → 6:
  ways 1, 2, 3, 4, 5, 6; timeout tests at t 38.99-59.73; 11-shot orbit chain t 67.91-79.74; bonus 135,050.
- `traces/scoring.txt` → `scoring.jsonl` t 36.45-46.72: both lane groups completed (Decepticon), bonus 2X.

## 11. Open questions
- deff 48 / 49 never shown: starter not found (maybe a dead path in 1.80 or a status-panel-only display).
- Lane-change rotation direction and the shot multiplier collection were read from code, not traced.
- The left orbit's own "came from the right" check, if any, was not decoded (sw6 always counted).
