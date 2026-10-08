# Character battles (Starscream, Shockwave, Blackout, Devastator / Bumblebee, Ironhide, Mudflap & Skids, Ratchet)

Audience: a developer rebuilding Transformers Pro 1.80 (`tf_180`) in MPF who has not read the ROM. Addresses refer
to `code/tf_decompiled.c` (headers `// ==== ADDR NAME`; most functions here are unnamed `FUN_...`). Tables are in
the ROM data area (0x040xxxxx = file offset 0x0xxxxx). 1 tick = 16.2 ms (measured: the battle "second" of 66
ticks lasts 1.07 s, traces/battle_starscream.jsonl 43.82 -> 81.13 s for 35 steps).

Reference traces (scenario `.txt` + trace `.jsonl` in `traces/`, factory settings):
| Trace | What | Pokes |
|---|---|---|
| battle_starscream | Decepticon default: 4 mode-start shots, Starscream, 5 hits, timer runs out, total screen | none |
| battle_bumblebee | Autobot (left flipper): 4 mode-start shots, Bumblebee phase 1 (all 6 shots incl. the Allspark), phase 2 (Bumblebee target), completed, total | none |
| battle_shockwave | Shockwave phases, completion | battle_lit = 2, shots left = 1 |
| battle_blackout | Blackout alternating groups, completion, mode-start counting again right after | battle_lit = 4, shots left = 1 |
| battle_devastator | Devastator right orbit / rover moved by bumpers, timer reset, completion | battle_lit = 8, shots left = 1 |
| battle_ironhide | Ironhide levels 1-3, completion | battle_lit = 0x20, shots left = 1 |
| battle_mudflap | Mudflap & Skids multiball, completion, end at one ball | battle_lit = 0x40, shots left = 1 |
| battle_ratchet | Ratchet, double shot, ended by a drain | battle_lit = 0x80 |
Watch file: `traces/watch_battle.tsv` (names used below).

## 1. Summary
Each side has four character battles. The player's side (chosen with the flippers before the plunge, see
`switches_and_shots.md`) decides which four are offered: **Decepticon** (default): Starscream, Shockwave,
Blackout, Devastator; **Autobot**: Bumblebee, Ironhide, Mudflap & Skids, Ratchet. One battle is "lit" at a time
(its character insert flashes); pop bumpers and the Bumblebee target move the lit battle to the next one.

**Starting a battle ("MODE START")**: the main shots carry purple (Decepticon) / red (Autobot) arrows. At ball
start 4 of them flash (default HARD). Hitting a flashing one scores 10,000 + 5,000 per hit already made (+10,000
per battle started this game, max 75,000) and shows "N MORE FOR MODE START"; the **4th** such hit starts the lit
battle. The left eject (the **Allspark**) is one of the five mode-start shots; it flashes only on the two easiest
settings or when the game relights it at random.

**A battle** scores 100,000 at its start, plays an intro (deff "NAME BATTLE / SHOOT FLASHING SHOTS"), then
flashing orange arrows show the shots worth points. Lit shots score a growing value; unlit main shots 25,000. Each
battle has a shot count to finish ("SHOOT 11 SHOTS"), kept per player across balls and attempts. Most battles
run on a timer (adjustable, 15-45 s); Mudflap & Skids is a 2-ball multiball instead. Making the last shot
**completes** the battle (counts for the Cybertron wizard); otherwise it ends when time runs out, the ball drains
or the game tilts. A "NAME / TOTAL: value" screen follows. The next battle is lit at once.

## 2. Settings (operator adjustments)
| Adj # | ROM name (id) | Default | Range | Effect |
|---|---|---|---|---|
| 65 | TRANSFORMERS SELECT (0x41) | RANDOM | RANDOM/AUTOBOT/DECEPTICON | side choice, see `switches_and_shots.md` [0x01033f94] |
| 66 | MODE START DIFFICULTY (0x42) | HARD (3) | 0 EXTRA EASY .. 4 EXTRA HARD | mode-start shots lit at reset / minimum kept lit: EE 5/5, E 5/4, M 4/4, H 4/3, EH 4/2; at EXTRA EASY a hit shot stays lit [table 0x040c6d3c, 0x0101fe98, 0x0101ffa0] |
| 72 | STARSCREAM TIMER (0x48) | 45 | 30-60 s | [0x0101795c] |
| 73 | SHOCKWAVE TIMER (0x49) | 45 | 30-60 s | [0x0101e400] |
| 74 | BLACKOUT TIMER (0x4a) | 45 | 30-60 s | [0x0101caa4] |
| 75 | DEVASTATOR TIMER (0x4b) | 20 | 10-30 s | restarts after every second Devastator shot [0x01015dc0, 0x01015f8c] |
| 76 | BUMBLEBEE TIMER (0x4c) | 15 | 5-30 s | phase 2 (Bumblebee target) only [0x010142dc] |
| 77 | IRONHIDE TIMER (0x4d) | 25 | 15-35 s | restarts at each new level [0x0101adc8, 0x0101afbc] |
| 78 | MUDFLAP/SKIDS TIMER (0x4e) | 15 | 5-30 s | ball-save time of the multiball, x 62 ticks [0x01019150] |
| 79 | RATCHET TIMER (0x4f) | 45 | 20-60 s | [0x01012318] |
| 42 | COMPETITION MODE | NO | | YES: the first lit battle is Bumblebee whatever the side [0x01022aa0] |
None of the shot counts or values are adjustable.

## 3. State

### 3.1 Battle manager (per player, kept in the 0x0211xxxx player area)
| Name (watch) | RAM | Size | Init / reset | Meaning |
|---|---|---|---|---|
| battle_lit | 0x02111ecc + 4*(p-1) | 4 | game start (event 0x26): Bumblebee 0x10 if competition mode else Starscream 0x01 (side is still the default 2) [0x01022c20 -> 0x01022aa0]; each side toggle: 0x10 Autobot / 0x01 Decepticon [0x01022d7c from deff 40 0x01034198] | bit of the battle that the next mode start will start |
| battle_started | 0x02111eac + 4*(p-1) | 4 | 0 at game start [0x01022c20] and at a wizard reset [0x01022b88] | bit set when the battle starts [0x01022e08] |
| battle_completed | 0x02111ebc + 4*(p-1) | 4 | as above | bit set when completed [0x01023058] |
| battles_started_n | 0x02111f24 + (p-1) | 1 | 0 at game start | battles started this game (stops at 255); raises the mode-start shot value [0x0101fd34] |
| mode_start_lit | 0x02111eec + 4*(p-1) | 4 | reset at game start and at each battle start [0x0101fe98] | flashing mode-start shots, bits of table 0x040c6d00 (see 4.2) |
| mode_start_hits | 0x02111f1c + (p-1) | 1 | 0 at reset | lit mode-start shots made |
| mode_start_needed | 0x02111f20 + (p-1) | 1 | 4 at reset; nothing else writes it | hits needed |
| (unused masks) | 0x02111efc, 0x02111f0c | 4 | 0 at reset, never set | the lamp code shows 0x02111f0c shots solid (dead code) [0x01022854] |
Event 0x26 is the player's first ball of the game (`event_post(0x26)` in the ball-start code 0x00019e44 area).

### 3.2 Battle record table [ROM 0x040c6e08, 8 records x 0x28 bytes]
| # | Battle | Bit | Side | Next | Task ids (timer, run) | Start fn | Hit fn | End fn | Wizard item | Audits started/completed (counter) | Insert lamp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Starscream | 0x01 | Decepticon | Shockwave | 0x9c, 0x9d | 0x0101795c | 0x01017b24 | 0x01017d98 | 1 | 0x59 / 0x5a | 7 STARSCREAM |
| 1 | Shockwave | 0x02 | Decepticon | Blackout | 0x9e, 0x9f | 0x0101e400 | 0x0101e5d4 | 0x0101e8ac | 2 | 0x5b / 0x5c | 6 SHOCKWAVE |
| 2 | Blackout | 0x04 | Decepticon | Devastator | 0xa0, 0xa1 | 0x0101caa4 | 0x0101cc6c | 0x0101ceb8 | 3 | 0x5d / 0x5e | 5 BLACKOUT |
| 3 | Devastator | 0x08 | Decepticon | Starscream | 0xa2, 0xa3 | 0x01015dc0 | 0x01015f8c | 0x0101633c | 4 | 0x5f / 0x60 | 4 DEVASTATOR |
| 4 | Bumblebee | 0x10 | Autobot | Ironhide | 0xa4, 0xa5 | 0x010142dc | 0x01014638 | 0x01014970 | 6 | 0x61 / 0x62 | 23 BUMBLEBEE |
| 5 | Ironhide | 0x20 | Autobot | Mudflap | 0xa6, 0xa7 | 0x0101adc8 | 0x0101afbc | 0x0101b328 | 7 | 0x63 / 0x64 | 24 IRONHIDE |
| 6 | Mudflap & Skids | 0x40 | Autobot | Ratchet | flag 0x1e, task 0xa9 | 0x01019150 | 0x01019294 | 0x01019518 | 8 | 0x65 / 0x66 | 25 MUDFLAP / SKIDS |
| 7 | Ratchet | 0x80 | Autobot | Bumblebee | 0xaa, 0xab | 0x01012318 | 0x01012508 | 0x010127c8 | 9 | 0x67 / 0x68 | 26 RATCHET |
Record layout: {u32 bit, abort fn, running fn, start fn, u16 started audit, end fn, completed fn, u16 completed
audit, u8 insert lamp at +0x1e, u32 wizard item at +0x20, u32 next index at +0x24}. Audit counters 0x59-0x68 are
the audits "STARSCREAM STARTED" .. "RATCHET COMPLETED"; each start also bumps 0x58 MODES STARTED.

### 3.3 Per-battle state
"C" below = how many times this battle was completed this game by this player (RAM byte, reset at event 0x26,
only above 0 after a wizard reset makes the battle playable again).
| Battle | Kept per player across balls (0x0211...) | Per run (RAM) |
|---|---|---|
| Starscream | ss_left 0x02111e5c+2(p-1) = 10 at reset | hits 0x3500c, lit 0x35010, base 0x35014, timer s 0x35018, total 0x3501c, pattern index 0x313c0; C 0x34fd8+(p-1) |
| Shockwave | sw_left 0x02111e9c = 11 | hits 0x35144, phase 0x313c4, lit 0x35148, base 0x3514c, timer 0x35150, total 0x35154; C 0x35110 |
| Blackout | bo_left 0x02111e94 = 11 | hits 0x350f0, lit 0x350f4, used-A 0x350f8, used-B 0x350fc, base 0x35100, timer 0x35104, total 0x35108; C 0x350bc |
| Devastator | dv_left 0x02111e54 = 10 | hits 0x34fbc, lit 0x34fc0, step 0x34fc4 (=25, unused), base 0x34fc8, timer 0x34fcc, total 0x34fd0, state 0x313b4, rover index 0x313b8; C 0x34f88 |
| Bumblebee | phase 0x02111e34 = 1, lit mask 0x02111e44 = 0x3f | phase copy 0x34f68, lit 0x34f6c, value 0x34f70, phase-2 award 0x34f74, decay step 0x34f78, timer 0x34f7c, total 0x34f80; C 0x34f20 |
| Ironhide | ih_left 0x02111e8c = 10, level 0x02111e6c = 1, lit 0x02111e7c = pattern(1) | level 0x350a0, hits 0x350a4, lit 0x350a8, base 0x350ac, timer 0x350b0, total 0x350b4; C 0x3506c |
| Mudflap & Skids | mf_left 0x02111e64 = 11 | hits 0x35058, lit 0x3505c, total 0x35064; C 0x35024 |
| Ratchet | ra_left 0x02111e2c = 11, lit mask 0x02111e1c = 0x3f | hits 0x34f04, lit 0x34f08, double bit 0x34f0c, base 0x34f10, timer 0x34f14, total 0x34f18; C 0x34ed0 |
"Reset" = the player's game start (event 0x26 -> 0x010359ac -> 0x010359f4(2): clears wizard progress, all
battle bits [0x01022b88(0xff)] and the counters above) and also when the Cybertron wizard progress is reset after
the wizard (0x01035ad0 from 0x010363ec). (verified in emulator: all traces, 10.52 s, vars ss_left 10, sw_left 11,
bo_left 11, dv_left 10, bb_phase 1, ih_left 10, ih_level 1, ih_lit 8, mf_left 11, ra_left 11)

## 4. How it starts

### 4.1 Which battles are offered (side)
The side byte (0x02112107 + p, 1 Autobot, 2 Decepticon) selects the four battles only through battle_lit: it is
set to the first battle of the side (Starscream 0x01 or Bumblebee 0x10) [0x01022d7c], and "next" never leaves the
side's ring of four (records 0-3 / 4-7). Choosing the next battle [0x010229ec]: from the record after the one
just started, walk the ring and take the first battle **not yet started**; if all four were started, take the
first **started but not completed**; if all four are completed, nothing (0).
The other side's battles become reachable only through the side-complete feature [0x0100fff0, started at the
Allspark when all own-side wizard items are done]: it sets battle_lit to the opposite side's first battle
[0x01022dbc] and game flag 0x3d (see 4.3).

### 4.2 Mode-start shots [0x01020074]
Table 0x040c6d00, 5 shots, record {mask, shot-multiplier group, Autobot lamp, Decepticon lamp}:
| Shot id | Shot | Switch / function | Mask | Lamp Autobot (red) | Lamp Decepticon (purple) |
|---|---|---|---|---|---|
| 0 | Allspark (left eject) | sw 3 [0x0100a788] | 0x01 | 14 ALLSPARK (RED) | 13 ALLSPARK (PURPLE) |
| 1 | Left orbit | sw 5 or sw 6 [0x01033244] | 0x02 | 18 LEFT ORBIT (RED) | 17 LEFT ORBIT (PURPLE) |
| 2 | Left ramp | sw 10 [0x01033824] | 0x04 | 45 LEFT RAMP (RED) | 46 LEFT RAMP (PURPLE) |
| 3 | Right ramp | sw 14 [0x01033918] | 0x08 | 33 RIGHT RAMP (RED) | 32 RIGHT RAMP (PURPLE) |
| 4 | Right orbit | sw 12 [0x01033488] | 0x10 | 38 RIGHT ORBIT (RED) | 37 RIGHT ORBIT (PURPLE) |
The center lane and Optimus are not mode-start shots. Orbits: the left orbit counts at sw 5 (bottom) or sw 6
(top), once per pass (switch-timeout tokens 7/8/9 [0x01033354, 0x010332e4, 0x01033530]); the right orbit sw 12 is
ignored while task 0x47 runs (a ball that just came round from the left orbit / center).

**Reset** [0x0101fe98] (game start and each battle start): light N shots walking from shot 1 (1, 2, 3, 4, then
0), N from the difficulty table (default 4: left orbit, left ramp, right ramp, right orbit = 0x1e); hits = 0;
needed = 4. (verified: traces/battle_starscream.jsonl 10.52 mode_start_lit 30)

**Qualifying allowed** [0x0101fdac] when all of these hold:
- `clu_start_allowed` [0x01022ca8]: no timed mode running (`any_timed_mode_running`: battles, double/fast scoring),
  no battle running [0x01022f64: any record's running fn], side-complete feature not running (flag 0x3c),
  `zuse_qualify_enabled` false [0x0100ff80], 0x010363b4 false (wizard);
- the player's own side is not complete (all 4 own bits in battle_completed) unless flag 0x3d (side-complete
  feature already played) is set; and if the other side is complete too and flag 0x3d set: not allowed;
- battle_completed low byte != 0xff (all eight done: never).

**Hit on a lit mode-start shot** (qualifying allowed):
1. value = min(10,000 + 10,000 x battles_started_n + 5,000 x mode_start_hits, 75,000) x shot multiplier of the
   shot's group [0x0101fd34, 0x01023538]; `score_add` (playfield multiplier applies).
2. mode_start_hits += 1.
3. If hits < needed: unlight the shot (not at EXTRA EASY); if fewer than the minimum stay lit, light one other
   random unlit shot (not the one just hit) [0x0101ffa0]; deff 91 "N MORE / FOR / MODE START" (N = needed - hits,
   also gets battle_lit); leff 103. Deff 91 plays 0x170 (Decepticon) / 0x174 (Autobot) (observed).
4. Else start the lit battle [0x01022f34 = 0x01022e08].
An unlit mode-start shot gives nothing from this rule.

Observed (traces/battle_starscream.jsonl): 18.58 left orbit 10,000 "3 MORE"; 20.75 left ramp 15,000; 22.94 right
ramp 20,000; 25.12 right orbit 25,000 -> Starscream starts. Relighting: 0x1e -> 0x1c -> 0x1a -> 0x16.

### 4.3 Battle start [0x01022e08]
For the record whose bit is battle_lit:
1. Call its start fn; if it fails, nothing more.
2. battle_started |= bit; mode-start reset (4.2); battles_started_n += 1; audits (record + 0x58); wizard item
   "played" +1 [0x01035af0(item, 1)].
3. battle_lit = next battle (4.1). (observed: battle_lit 1 -> 2 at 25.13 s when Starscream starts)

Every start fn: kills a running copy; sets its per-run state; adds **100,000** (kept as the run total); reads its
timer adjustment; creates the timer task and the intro task; clears game flag 0x13 (so ADD MORE TIME can be
awarded again); starts its rule lamp effect. The intro task [FUN_01006480(deff, 0xea6, 0x9f, 0, callback)] waits up
to 3750 ticks for display priority, shows the intro deff, and when it ends the callback pauses battle timers for
156 ticks [0x010062f0(0x9c)].

### 4.4 Moving the lit battle [0x01022cf8]
Each pop bumper hit (not repeated within its own debounce task 0x3f/0x40/0x41) [0x01032f8c] and each Bumblebee
target hit [0x01033adc]: if `clu_start_allowed`, battle_lit = next battle after the current one (same choice as
4.1), music re-evaluated. Example: two Bumblebee target hits from Starscream give Blackout (switches.jsonl: ramp
started Blackout).

## 5. Behaviour while running

### 5.0 Common rules
**Battle shot ids** (passed by the shot functions to all eight hit fns):
| Id | Shot | Switches | Orange arrow lamp |
|---|---|---|---|
| 0 | Allspark / left eject | sw 3 | 15 ALLSPARK (ORANGE) |
| 1 | Left orbit | sw 5 / 6 | 19 LEFT ORBIT (ORANGE) |
| 2 | Left ramp | sw 10 | 44 LEFT RAMP (ORANGE) |
| 3 | Center | sw 11 center lane, or sw 51 Optimus (one of them per 0x54 lockout) | 40 CENTER LANE (ORANGE) |
| 4 | Right ramp | sw 14 | 34 RIGHT RAMP (ORANGE) |
| 5 | Right orbit | sw 12 | 39 RIGHT ORBIT (ORANGE) |
| 6 | Bumblebee target | sw 1 | 30 BUMBLEBEE (CAPTIVE BALL) |
(each battle's shot table, e.g. 0x040c69f8, gives {mask 1<<id, shot-multiplier group id+1, lamp group}; lamp
groups 79-134 in lamp_groups.json resolve to the lamps above.)

**Every hit fn** (only while its run test is true):
- shot multiplier m = 1, or the shot's multiplier from the shot-multiplier feature [0x01023538] (3 when the roving
  3x of task 0xb6 is on that shot).
- shot **not lit** (or Mudflap: not lit): 25,000 flat (no m, except Bumblebee phase 1: 25,000 x m), added to the
  run total.
- shot **lit**: score = m x value (formula per battle below); remove/advance lit shots; hits += 1; shots-left -= 1;
  hit deff with the value, sound index cycling through the samples of the battle's hit sound call; add to total.
- the last shot (shots-left was 1): **completed**: C += 1; wizard item completed [0x01035af0(item, 2)];
  battle_completed |= bit, completed audit, total screen [0x010230d0 -> completed fn]; then the end fn kills the
  run (5.0 end) - Mudflap only sets flag 0x1d.
- all hit fns end with `FUN_00017650` (re-evaluate lamps/music).

**Timer task** (Starscream, Shockwave, Blackout, Devastator, Ironhide, Ratchet; Bumblebee phase 2 similar)
[e.g. 0x01017824, 0x0101224c]: wait for the intro (`wait_display_idle(0x138)`, then 93 ticks); then repeat: count
11 steps of 6 ticks (66 ticks = 1.07 s), restarting the count whenever timers are paused [0x0100683c: playfield
not active (0x314d8), a display show task 0x5d-0x7e runs (e.g. the Allspark award), or the pause task 0x59 runs];
then if seconds = 0 stop, else seconds -= 1. When it stops: kill the run task (second id), music returns, wait
125 ticks (2.0 s; **lit shots still score during this grace** because the timer task itself is the "running"
test), then the total screen. Pause task 0x59 [0x010062f0(ticks)] is started for 156 ticks by: the intro end,
pop bumpers, top lanes (sw 7, 8) and Bumblebee phase-1 hits; 372 ticks by 0x0100b058 (Megatron).
Observed: Starscream 45 s adj: started 25.12, first decrement 34.20, 0 at 81.13, run killed 82.20 (music 0x1f),
total deff 95 at 84.23.

**Add time** (ADD MORE TIME mystery, `0x01024b14`, once per mode via flag 0x13): +15 s, capped at 90 s, restart the
timer task: Starscream 0x01017a78, Shockwave 0x0101e528, Blackout 0x0101cbc0, Devastator 0x01015ee0, Ironhide
0x0101af10, Ratchet 0x0101245c; Bumblebee phase 1 restores the full value [0x0101449c], phase 2 +5 s cap 15
[0x0101456c].

**End fn / total**: kills both tasks and starts a total task (0x81-0x87) that shows the total deff with the run
total (unless tilted / game over, `0x31468 & 0x310`). The battle manager calls every record's end fn on event
0x1d (ball drained, end of ball) and on event 0x65 (tilt) [0x01023048 via hooks in 0x010232d4]. Completion also
kills the run at once.

### 5.1 Starscream (Decepticon 1) [0x0101795c, 0x01017b24]
- Shots left 10. Value = min(100,000 + 12,500 C, 500,000) + 12,500 x hits.
- Lit shots: a moving pair from table 0x040c6a40, index 0..7: 0x03 (Allspark + left orbit), 0x06, 0x0c, 0x18,
  0x30 (right ramp + right orbit), 0x18, 0x0c, 0x06. The index moves one step after every lit hit, and once
  shots left < 6 also every timer second unless switch-timeout tokens 0xc or 0xd are active [0x01017824].
- Observed: 32.29 left orbit 100,000; 34.47 left ramp 112,500; 36.69 center 125,000; 38.96 left ramp unlit
  25,000; 41.17 right ramp 137,500; ss_lit 3 -> 6 -> 12 -> 24 -> 48.

### 5.2 Shockwave (Decepticon 2) [0x0101e400, 0x0101e5d4]
- Shots left 11. Value = min(200,000 + 25,000 C, 500,000) + 25,000 x hits [0x0101e3c8: base 0x30d40 + C x 0x186a
  words = 25,000 per completion; Ghidra shows it as pointer arithmetic, scale 4].
- Phases: 1 Allspark only (0x01) -> 2 right ramp only (0x10) -> 3 all six (0x3f) -> from then on all six except
  the shot just hit.
- Observed (traces/battle_shockwave.jsonl): Allspark 200,000; right ramp 225,000; left orbit 250,000; left ramp
  275,000; left ramp again (unlit) 25,000; completing center 300,000; total deff 99 at 55.15.

### 5.3 Blackout (Decepticon 3) [0x0101caa4, 0x0101cc6c, 0x0101c910]
- Shots left 11. Value = min(200,000 + 50,000 C, 500,000) + 50,000 x hits [base 0x0101ca6c: 0x30d40 + C x 0x30d4
  words x 4].
- Two groups: A = Allspark, left orbit, left ramp (0x01, 0x02, 0x04); B = center, right ramp, right orbit (0x08,
  0x10, 0x20). After an even number of lit hits a random shot of A not used yet in this run is added to the
  used-A set and **the whole used-A set is lit**; after an odd number, the same with B. When a group is used up,
  its full group stays lit.
- Observed (traces/battle_blackout.jsonl): lit 0x01 -> (hit) 0x10 -> 0x03 -> 0x30 -> 0x07; values 200,000,
  250,000, 300,000, 350,000.

### 5.4 Devastator (Decepticon 4) [0x01015dc0, 0x01015f8c, 0x010161e4]
- Shots left 10. Value = min(100,000 + 100,000 C, 500,000) + 100,000 x hits.
- State 1: only the right orbit (0x20). A hit there -> state 2: a **rover** at position 0 (Allspark), table
  0x040c6964 = 0,1,2,3,4,5,5,4,3,2,1,0 (shot ids). Each pop bumper hit while in state 2 moves the rover one step
  (wraps after 12), starts leff 120 and scores 10,000 (x the playfield multiplier, via the score event). A hit on
  the rover shot -> state 1 and the timer restarts at max(current, adj 75).
- Observed (traces/battle_devastator.jsonl): right orbit 100,000 (rover 0x01); Allspark 200,000 (timer 17 -> 20);
  right orbit 300,000; two bumpers move 0x01 -> 0x02 -> 0x04 (+10,000 each); left ramp 400,000; right orbit
  500,000 completes; total deff 107 at 57.14.

### 5.5 Bumblebee (Autobot 1) [0x010142dc, 0x01014638, 0x010141a4]
Two phases, the phase is kept per player:
- **Phase 1** (bb_phase 1): the six main shots (mask kept per player, 0x3f at reset). Value starts at
  min(750,000 + 50,000 C, 1,000,000) and drops every 3 ticks by step = ((start - 100,000) / 3,000) x 10 - 10
  (2,160 at C = 0) down to 100,000 (about 15 s of unpaused time); timer pauses also freeze it. A lit hit scores
  m x current value, unlights the shot (saved per player), adds the score to the phase-2 jackpot and pauses the
  timer 156 ticks. Unlit hits 25,000 x m. Phase 1 has no timer: it ends 46 ticks after the value reaches 100,000
  (then the 125-tick grace and the total). When all six are made: phase = 2 (saved), mask = 0x40, timer task 2.
- **Phase 2**: only the Bumblebee target (sw 1, "SHOOT CAMARO FOR value"), timer = adj 76 (15 s). Hitting it awards
  the jackpot = sum of this attempt's phase-1 lit awards, or **200,000** if the battle started directly in phase 2
  (an earlier attempt ended between the phases), and completes the battle.
- Shot count: none (completion is the phase-2 hit). Deff 110 gets "7 - lit shots left".
- Observed (traces/battle_bumblebee.jsonl, Autobot): Allspark, left orbit, left ramp, right ramp, right orbit
  750,000 each (no decay yet: paused after each hit); right ramp again 25,000; center 668,300; phase 2; Bumblebee
  target 4,418,300 (= 5 x 750,000 + 668,300), completed; total deff 111 at 59.73.

### 5.6 Ironhide (Autobot 2) [0x0101adc8, 0x0101afbc, 0x0101ab5c]
- Shots left 10. Value = min(200,000 + 50,000 C, 500,000) + 50,000 x hits [base 0x0101ad90, scale 4 as Blackout].
- Levels (kept per player) with patterns 0x040c6b3c: 1 = 0x08 (center), 2 = 0x14 (left + right ramp), 3 = 0x2a
  (left orbit, center, right orbit), 4 = 0x36 (orbits + ramps). A lit hit unlights the shot (saved per player);
  when the pattern is cleared the level goes up one (4 stays 4), the new pattern is lit and the timer restarts at
  max(current, adj 77).
- Observed (traces/battle_ironhide.jsonl): center 200,000 (level 2, lit 0x14); left ramp 250,000; right ramp
  300,000 (level 3, lit 0x2a); left orbit 350,000; center 400,000 completes; total deff 115 at 51.34.

### 5.7 Mudflap & Skids (Autobot 3) [0x01019150, 0x01019294, 0x01019550]
- A **multiball**, no timer: start = `multiball_start(balls in play + 1, or 2 if none, ..., ball save adj 78 x 62
  ticks)`; sets flag 0x1e (running), clears 0x1d; clears flag 0x14 when no timed mode runs (so ADD-A-BALL can be
  awarded). Intro deff 116 from task 0x6e.
- All six main shots lit; a lit hit unlights it; when all six are made they all relight.
- Value = min(200,000 + 50,000 x (hits this run + C), 500,000) [0x010190e0, hits 0x35058 counted before the
  value is read, so the first hit of a run is 250,000 with C = 0 - observed]. Shots left 11; when it reaches 0 it is
  reset to 11.
- The first time shots left reaches 0 in the run (flag 0x1d clear) the battle is **completed** (flag 0x1d set,
  wizard item, audit, total) but the multiball and the battle continue.
- Ends when the multiball is down to one ball [0x01019550 clears flag 0x1e and starts task 0xa9 (a short grace,
  LAB_01019504) whose end shows the total]; an ADD-A-BALL during the grace revives it [0x01019594].
- Observed (traces/battle_mudflap.jsonl, poked battle_lit 0x40, shots left poked to 1 at 44.07): 4 mode-start hits
  start it at 27.34 (100,000 start award, audit 0x65 started); intro deff 117 from 32.72; hits at 37.52 left orbit
  250,000, 39.71 left ramp 300,000, 41.90 right ramp 350,000, 44.09 right orbit 400,000 = completion (audit 102,
  battle_completed 0x40, mf_left back to 11, deff 118 "COMPLETED") - the multiball keeps running; 46.27 left ramp
  (already made) 25,000 [0x0101946c]; drain to one ball at 48.46 -> sound 0x230 at 49.20, total deff 119 at 52.17
  (sound 0x232). After the end the next mode-start hit is 20,000 (54.60: started count 1).

### 5.8 Ratchet (Autobot 4) [0x01012318, 0x01012508]
- Shots left 11. Value = min(100,000 + 50,000 C, 500,000) + 50,000 x hits, **doubled** for the "double" shot =
  the lowest-numbered lit shot (Allspark first).
- Lit mask kept per player (0x3f at reset); a lit hit unlights it; all six made -> all relit; the double shot is
  recomputed after every hit [0x01012178].
- Observed (traces/battle_ratchet.jsonl, poked battle_lit 0x80): started at 27.33; intro deff 121 at 31.09; 34.51
  left orbit 100,000 (not the double: Allspark was); 37.52 Allspark 300,000 (= 2 x 150,000, double); 40.96 left ramp
  400,000 (= 2 x 200,000, the new double); 43.15 right ramp 250,000; 45.41 left ramp again (unlit) 25,000
  [0x0101272c]; drain at 47.63 ends it: total deff 123 at 48.17 (sound 0x255), then bonus.
  ra_lit 63 -> 61 -> 60 -> 56 -> 40. Ramps also scored combos (150,000-225,000, caller 0x01002fec) on top.

## 6. How it ends
| End | What happens |
|---|---|
| last shot (completion) | value scored, hit deff with "COMPLETED", run killed at once, music back to main play, battle_completed bit, wizard item, total deff about 8-9 s later (after the hit deff) |
| timer reaches 0 | run task killed, music back, 125 ticks grace (shots still score), total deff |
| ball drain (event 0x1d) / tilt (event 0x65) | all running battles killed, total deff (not when tilted) |
| Mudflap: one ball left | grace task 0xa9, then total |
Carried over: shots left, Bumblebee phase and lit mask, Ironhide level and lit mask, Ratchet lit mask (all per
player for the game). A not-completed battle stays "started": the next-battle choice skips it until every battle
of the side was started, then offers it again (with its remaining shot count).
Right after a battle ends, the mode-start shots work again; the same switch hit that completes a battle can
already count as the first mode-start hit (battle_blackout.jsonl 57.04: 350,000 then 20,000 + deff 91).

## 7. Media
| Battle | Intro deff (task) | Background deff + music (music-table entry) | Hit deff | Total deff (task) | Rule leff (while running) | Hit sound call | Intro sounds | Total sounds |
|---|---|---|---|---|---|---|---|---|
| Starscream | 92 "STARSCREAM BATTLE" (0x68) | 93 + 0x28 (12) | 94 | 95 "STARSCREAM / TOTAL:" (task from 0x01017d40) | 106 | 0x181 | 0x17f, 0x180 | 0x191, 0x192 |
| Shockwave | 96 (0x69) | 97 + 0x29 (16) | 98 | 99 | 110 | 0x195 | 0x193, 0x194 | 0x1a8 |
| Blackout | 100 (0x6a) | 101 + 0x2a (15) | 102 | 103 | 114 | 0x1ab | 0x1a9, 0x1aa | 0x1cb |
| Devastator | 104 (0x6b) | 105 + 0x2b (11) | 106 | 107 | 118 | 0x1d1 | 0x1cd, 0x1ce, 0x1cf | 0x1e7 |
| Bumblebee | 108 (0x6c) | 109 + 0x2c (10) | 110 | 111 | 123 (phase 2: 124) | 0x1ee | 0x1e9-0x1ed | 0x1fe |
| Ironhide | 112 (0x6d) | 113 + 0x2d (14) | 114 | 115 | 128 | 0x201 | 0x17d, 0x203, 0x204, 0x200 | 0x218 |
| Mudflap & Skids | 116 (0x6e) | 117 + 0x2e (13) | 118 | 119 | 132 | 0x21c | 0x17d, 0x21b | 0x232 |
| Ratchet | 120 (0x6f) | 121 + 0x2f (9) | 122 | 123 | 136 | 0x236 | 0x17d, 0x235 | 0x255 |
- Intro: "NAME / BATTLE" then "SHOOT / FLASHING / SHOTS" (msgs 1557-1665). Background (looping, priority 1):
  "NAME / timer seconds / SHOOT n SHOTS" ("SHOOT LIT SHOT" when 1 left; Devastator "SHOOT R. ORBIT" in state 1;
  Bumblebee "SHOOT CAMARO / FOR value" in phase 2, "BEE = value" in phase 1). Hit deff: value, "+n SHOTS", and
  "COMPLETED" on the last shot. Total: "NAME / TOTAL: / value". Deffs 94-123 take their numbers from the task.
- Music table (`rom_data/sound/music_table.csv`, entries 9-16, mask 0x20, priority 5): condition = the battle's
  timer task (first id) runs and, while the intro task runs, only once the intro deff is no longer showing
  [e.g. 0x01018884]; Mudflap: flag 0x1e. Observed music: Starscream 0x28 at 25.14, back to 0x1f at 82.20;
  Shockwave 0x29; Blackout 0x2a; Devastator 0x2b; Bumblebee 0x2c (traces).
- The 0x31 / 0x34 "battle" music of the fallback entry comes from 0x010260d8 (the Optimus feature), not from these
  battles.
- Mode start: deff 91 + leff 103, sounds 0x170 / 0x174 by side. Lit-battle insert: leff 104 (rule while
  qualifying is allowed, registered in 0x010232d4) flashes the insert lamp of battle_lit (byte +0x1e of the
  record) every 4 ticks [leff_104 0x01023150].
- Total task ids: Shockwave 0x81, Blackout 0x82, Devastator 0x83, Bumblebee 0x84, Ironhide 0x85, Mudflap 0x86,
  Ratchet 0x87 [end fns]; Starscream's is created in 0x01017d40 (not decoded).

## 8. Lamps
- Mode-start arrows [0x01022854, lamp rule 0x0003515c]: for each of the 5 shots, if qualifying is allowed and the
  shot is in mode_start_lit: the side's colour flashes (red Autobot / purple Decepticon), the other colour off;
  otherwise both off.
- Battle arrows: the orange insert of each lit battle shot (5.0 table), drawn by the battle's rule leff (lamp
  groups from the shot table). Observed lit masks are in the traces; the flash pattern itself was not decoded.
- Character inserts (4-7 Decepticons, 23-26 Autobots) [0x01035ea8, wizard items]: off = never started, flashing =
  started but not completed, solid = completed; the lit battle additionally blinks via leff 104.

## 9. Interactions
- Only one battle at a time; while one runs no mode start, no lit-battle rotation, Energon targets pay 5,000
  (timed mode), the side-complete feature cannot start.
- Double / fast scoring are timed modes too: while they run no battle can be qualified.
- Mudflap & Skids is a multiball: its intro waits for display priority; ADD-A-BALL works during it.
- ADD MORE TIME (Allspark mystery) is forced whenever a timed battle runs and flag 0x13 is clear.
- Completions feed the Cybertron wizard (items 1-4 Decepticons, 6-9 Autobots, `FUN_01035af0`), audit counters
  0x81-0x8b; all own-side items done enables the side-complete feature at the Allspark [0x0100fff0].
- Tilt / drain end the battle; the total is skipped when tilted.

## 10. Reference scenarios
See the table at the top. Key events per trace are quoted in section 5.

## 11. Open questions
- Starscream's per-second rotation condition reads switch-timeout tokens 0xc and 0xd (`FUN_0000febc`); what sets
  them was not traced.
- Event 0x26 is assumed to be the player's first ball (it resets everything here); not traced across a multi-player
  game.
- Wizard reset (0x01035ad0) re-enables completed battles with C > 0; not exercised.
- The side-complete feature (0x0100fff0, flags 0x3c/0x3d, 1,000,000 x multiplier) belongs to the wizard /
  Megatron-Optimus spec; its exact gate (0x01035db4: all 5 own-side wizard items) was read but not traced.
