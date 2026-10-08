# Optimus Prime battle and Optimus multiball (Autobot "A" and Decepticon "D" versions)

Audience: a developer rebuilding Transformers Pro 1.80 (`tf_180`) in MPF who has not read the ROM. Addresses refer
to `code/tf_decompiled.c` (headers `// ==== ADDR NAME`; some functions here carry names borrowed from Tron
(`dbattle_*`) that only match by code shape). 1 tick = 16.25 ms (see `megatron_multiball.md`).

Audit numbers: the trace prints the **counter id** passed to `audit_add`; `rom_data/settings/audits.csv` # =
counter + 8 (e.g. counter 0x6b = 107 = #115 "OPTIMUS BATTLE STARTED").

Reference traces (`traces/`, watch file `traces/watch_optimus.tsv`, factory settings, **no pokes**):
| Trace | What |
|---|---|
| optimus_decepticon | Decepticon (default side): 3 center-lane shots, 4th opens the Optimus battle, 3 Optimus hits, 4th starts the multiball; jackpot / Optimus double jackpot on all 6 shots, the center-lane quirk, super jackpot at Optimus, drains, total |
| optimus_autobot | Autobot (left flipper on the choose-side screen): battle, multiball, unlit shot, jackpot + double jackpot on each of the 6 shots, super jackpot at the Megatron lock, drains, total |

## 1. Summary
Shooting the **center lane** four times (when nothing else is running) opens the **Optimus Prime battle**:
Optimus (the figure / target, switch 51) rises and must be hit a number of times ("N MORE TO START OPTIMUS
MULTIBALL", 4 hits on the default setting). The last hit awards 2,000,000 and starts a **3-ball Optimus
multiball**, whose rules depend on the side:
- **Autobot (A)**: the 6 main shots are lit. A lit shot scores a jackpot and becomes the only lit shot; hitting it
  again scores a double jackpot and removes it; the other remaining shots relight. When all 6 are done the super
  jackpot is lit at the Megatron lock.
- **Decepticon (D)**: a lit shot scores a jackpot, is removed and lights Optimus; Optimus scores the double
  jackpot and relights the remaining shots. When all 6 are done the super jackpot is lit at Optimus.
Jackpot 150,000 (+100,000 per super already collected, max 500,000), double = 2x. Super = all jackpots since the
last super (min 1,000,000). The multiball ends at one ball with an "OPTIMUS PRIME MULTIBALL TOTAL" screen.

## 2. Settings
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 67 | OPTIMUS DIFFICULTY | 1 (MEDIUM) | 0-2 | starting battle level L per player at game start [0x01025d14]; Optimus hits = 2L + 2 (see 4.2) |
| 85 | DISABLE OPTIMUS PRIME MOTOR | NO | NO/YES | not read through `adj_get` anywhere (open question) |
| 87 | SAVE OPTIMUS PRIME PROGRESS | YES | NO/YES | YES: multiball phase / remaining shots / lit shots are restored per player at the next Optimus multiball [0x01027994, 0x01029a08] |

## 3. State
| Name (watch) | RAM | Scope / init | Meaning |
|---|---|---|---|
| opt_access | 0x02111f7c + (p-1) | per player; 0 at game start, 0 after the battle starts [0x01026418] | center-lane shots made toward the battle (0-4) |
| opt_level | 0x02111f94 + (p-1) | per player; adj 67 at game start; +1 at each battle won [0x010262f0] | battle level L |
| opt_battle_left | 0x02111f9c + (p-1) | per player; 2L + 1 (max 8) at battle start [0x010261cc] | Optimus hits still needed before the starting hit |
| opt_award_level | 0x02111f90 + (p-1) | per player; never incremented in the code | start award = 2,000,000 + 1,000,000 x this (max 4,000,000) [0x01026240] -> always 2,000,000 |
| opa_phase / opa_remaining / opa_lit / opa_total | 0x000352f8 / 0x000352fc / 0x00035300 / 0x00035304 | while A runs; per-player copies at 0x02111fc0 / 0x02111fd0 / 0x02111fe0 | phase (1 jackpot, 2 double, 3 super), shots not yet completed (bits 0-5), lit shots, total |
| opa_supers | 0x02111fa4 + (p-1) | per player, game | supers collected in A (jackpot base) |
| op_a_mb_since_super / op_a_sum | 0x02111fac + (p-1) / 0x02111fb0 + 4(p-1) | per player; +1 per A start / += each jackpot and double; both 0 at a super (and at start when adj 87 = NO) | super base |
| opd_phase / opd_remaining / opd_lit / opd_total | 0x00035370 / 0x00035374 / 0x00035378 / 0x0003537c | while D runs; copies at 0x02112010 / 0x02112020 / 0x02112030 | same for D |
| opd_supers | 0x02111ff4 + (p-1) | per player, game | supers collected in D |
| op_d_mb_since_super / op_d_sum | 0x02111ffc + (p-1) / 0x02112000 + 4(p-1) | as for A | super base |
Game flags: 0x46 (70) Optimus battle running; 0x1f (31) Optimus A running; 0x22 (34) Optimus D running; 0x49 (73)
set at the multiball start; 0x14 (20, add-a-ball used) cleared at the start when no timed mode runs, so ADD-A-BALL
can be offered again [0x01027994, 0x01029a08] (verified in emulator: both traces).

## 4. How it starts
### 4.1 Access (center lane sw 11) [0x01025de4]
- Blocked (any Megatron / Optimus / AHM / wizard multiball running, or the battle already running; character
  battles do not block it [0x01025d7c]): 1,000 points, leff 169, sound 0x2a1, nothing else (verified in emulator:
  megatron_decepticon.jsonl 41.42 s).
- Hits 1-3: opt_access += 1; 2,500 points; deff 141 "n MORE TO ACCESS OPTIMUS" (n = 4 - hits); leff 170; sound
  0x2a3 (then 0x2a4 from the deff) (verified in emulator: optimus_decepticon.jsonl 16.40, 18.57, 20.74 s).
- Hit 4: **battle start** [0x0102628c]: flag 0x46, opt_battle_left = 2L + 1, counter 0x6b, **200,000**, deff 142
  (split screen "HUNT FOR DECEPTICONS" / "DESTROY OPTIMUS PRIME"), opt_access = 0
  (verified in emulator: optimus_decepticon.jsonl 22.92 s, opt_battle_left 3). Music becomes 0x34 (Decepticon) /
  0x31 (Autobot) through the music-table fallback rows 0 / 17 while the battle can progress [0x010260d8]
  (verified in emulator: 22.92 s music 0x034). The background stays deff 19 (main play).
- The center lane's other scoring (switch score, combos 0x01002fec: 150,000 / 175,000 / 200,000 in the trace)
  is separate, see `combos_and_multipliers.md`.

### 4.2 Battle (Optimus target sw 51) [0x010262f0]
Only while the battle can progress (flag 0x46 and no Megatron / Optimus / AHM / wizard multiball) [0x010260d8]:
- opt_battle_left > 0: opt_battle_left -= 1; deff 144 "n MORE TO START OPTIMUS MULTIBALL" with n = opt_battle_left + 1;
  leff 178; sound 0x2aa; Optimus coil 12 pulses about 0.37 s later (task 0x54, which also ignores sw 51 and the
  center lane for about 1 s) (verified in emulator: 27.15, 29.32, 31.50 s, coil 12 at 27.53 / 29.68 / 31.88 s).
- opt_battle_left = 0: **2,000,000** (start award, not multiplied), battle cleared, opt_level += 1, then the
  multiball for the player's side, passing the center lane's shot multiplier (slot 4) [0x010262f0]
  (verified in emulator: 33.66 s, 2,000,000, opt_level 1 -> 2).
- So the default (L = 1) needs 3 + 1 = 4 Optimus hits; each battle won adds 2 hits (max 8 + 1).
- Optimus is raised for the battle and lowered after; in the simulator motor coil 30 runs about 7.65 s per move
  (observed: 22.95 -> 30.62 s and 31.53 -> 39.19 s). Deff 143 "OPTIMUS BATTLE! / SHOOT OPTIMUS" (a background
  deff) is never started (open question).

### 4.3 Multiball start [A 0x01027994 / D 0x01029a08]
`multiball_start(balls = 3 if none in play else in_play + 2, 1, ball save 625 ticks = 10.2 s, grace 187 ticks =
3.0 s)` (verified in emulator: both traces). Then: adj 87 YES restores phase / remaining / lit from the player's
copies, NO resets them (all 6 shots, phase 1) and clears mb_since_super and sum; **250,000 x the center-lane
multiplier**; flag 0x14 cleared (no timed mode); flag 0x1f (A) / 0x22 (D) set; intro task 0x71 (A) - deff 57
(A, 5.7 s) / deff 63 (D, 8.7 s), shown 1.3 s (A) / 3.5 s (D) after the start (observed); mb_since_super += 1;
counter 0x6c (A, #116 OPTIMUS M.B.A. STARTED) / 0x70 (D, #120); wizard requirement 5 (Optimus multiball)
collected: 0x01035af0(5,1), counter 0x86 (#142 WIZARD: REQ. 6 COLLECTED).
(verified in emulator: optimus_decepticon.jsonl 33.67 s, optimus_autobot.jsonl 34.93 s)

## 5. Behaviour while running
Shots: 0 Allspark / left eject, 1 left orbit, 2 left ramp, 3 center lane, 4 right ramp, 5 right orbit, 6 = Megatron
lock (A) / Optimus target sw 51 (D) [tables 0x040c729c A, 0x040c7400 D: {mask, lamp group, multiplier slot}].
Awards are x the shot's multiplier (slot = index + 1; the Megatron lock has none; Optimus uses the center lane's).
J = min(150,000 + 100,000 x supers (opa_supers / opd_supers) + 25,000 x a per-player counter that is never
incremented, 500,000) [A 0x0102779c, D 0x01029810]; DJ = min(2J, 1,000,000) [0x0102781c, 0x01029890].
Super = max(1,000,000, pct x sum), pct = [100, 100, 75, 50]% indexed by min(mb_since_super, 3)
[tables 0x040c72f0, 0x040c7454; 0x01027874, 0x010298e8].

### 5.1 Autobot (A) [0x01027b74]
| Trigger | Condition | Effect | Deff | Sound | Next |
|---|---|---|---|---|---|
| lit shot | phase 1 | J; lit = only this shot; counter 0x6d | 59 JACKPOT | 0x7f (sample index cycles) | phase 2 |
| the lit shot again | phase 2 | DJ; shot removed from remaining; lit = remaining; counter 0x6e | 60 DOUBLE JACKPOT | 0x84 | phase 1, or phase 3 (lit = Megatron lock) when none remain |
| Megatron lock | phase 3 | super; opa_supers += 1; wizard req 5 completed (counter 0x91, #153); sum and mb_since_super = 0; all 6 relit; counter 0x6f | 61 SUPER JACKPOT | 0x8f, 0x90, 0xa1 | phase 1 |
| unlit shot | any | nothing | | | |
Observed (optimus_autobot.jsonl): 41.05 left orbit J 150,000 (lit 2); 43.20 left ramp: nothing; 45.39 left orbit
DJ 300,000; then J / DJ pairs at left ramp, center, right ramp, right orbit, Allspark (47.57-70.45); 70.45 phase 3;
74.64 super **2,700,000** at the lock (= 6 x 450,000); background deff 58 changes its text to "SHOOT MEGATRON".

### 5.2 Decepticon (D) [0x01029bf4]
| Trigger | Condition | Effect | Deff | Sound | Next |
|---|---|---|---|---|---|
| lit shot 0-5 | phase 1 | J; shot removed from remaining; lit = Optimus only (0x40); counter 0x71 | 65 JACKPOT | 0xa5 (cycles) | phase 2 |
| Optimus sw 51 | phase 2 | DJ; lit = remaining; counter 0x72 | 66 DOUBLE JACKPOT | 0xaa | phase 1, or phase 3 (super at Optimus) when none remain |
| center lane (sw 11), unlit | phase 2 | **quirk**: J again, deff 65, counter 0x71, no state change | 65 | | phase 2 |
| Optimus sw 51 | phase 3 | super; opd_supers += 1; wizard req 5 completed (counter 0x91); sum and mb_since_super = 0; all relit; counter 0x73 | 67 SUPER JACKPOT | 0xab, 0xc5 | phase 1 |
Observed (optimus_decepticon.jsonl): 39.78 J 150,000; 42.02 Optimus DJ 300,000; 46.30 center lane in phase 2:
J 150,000 (quirk, caller 0x01029e14); J/DJ pairs to 66.89; 69.06 super **2,850,000** (= 6 x 450,000 + the quirk
jackpot). The quirk is probably there because the center lane and Optimus share one shot position (inferred);
reproduce it or not by choice.

## 6. How it ends
- Down to one ball: flag 0x1f / 0x22 cleared (grace 187 ticks for add-a-ball), then the total screen deff 62 (A) /
  68 (D) "OPTIMUS PRIME MULTIBALL TOTAL: n" via task 0x89 / 0x8a, skipped in tilt / game-over states
  [0x01027ec0, 0x01029fa4] (verified in emulator: A flag 31 cleared 81.53 s, deff 62 at 85.09 s; D flag 34 cleared
  73.82 s, deff 68 at 77.40 s).
- Carries over: opt_level, supers, sum / mb_since_super, A/D progress when adj 87 = YES, wizard requirement 5.

## 7. Media
| When | Display effect | Sound | Lamp effect |
|---|---|---|---|
| access hit 1-3 | 141 "n MORE / TO ACCESS / OPTIMUS" | 0x2a3, 0x2a4 | 170 |
| access blocked | - | 0x2a1 | 169 |
| battle start | 142 "HUNT FOR DECEPTICONS" / "DESTROY OPTIMUS PRIME" | 0x2ab, 0x2ad; music 0x34 (D) / 0x31 (A) | 174 |
| battle hit | 144 "n / MORE TO START / OPTIMUS MULTIBALL" | 0x2aa, then 0x2b5 / 0x2b6 | 178 |
| A start / background | 57 intro, 58 "OPTIMUS PRIME MULTIBALL / SHOOT FLASHING SHOTS" ("SHOOT MEGATRON" when super lit) | 0x7d, 0x93; music 0x32 | 45 |
| A jackpot / double / super / total | 59 / 60 / 61 / 62 | 0x7f / 0x84 / 0x8f.. / 0x91 | 48 / 49 / 50 / 51 |
| D start / background | 63 intro, 64 "... SHOOT FLASHING SHOTS" / "SHOOT OPTIMUS TARGET" | 0xa4, 0xb0; music 0x35 | 53 |
| D jackpot / double / super / total | 65 / 66 / 67 / 68 | 0xa5, 0xb1 / 0xaa, 0xc4 / 0xab, 0xc5 / 0xae | 56 / 57 / 58 / 59 |
Music table rows: 4 = Optimus A (flag test 0x010285a0) -> deff 58 + music 0x32; 5 = Optimus D (0x0102a6e4) ->
deff 64 + music 0x35; rows 0 and 17 give music 0x31 / 0x34 while the battle can progress.

## 8. Lamps
Lamp groups (`rom_data/io/lamp_groups.json`): A 0x17-0x1d, D 0x1e-0x24 = the orange arrows (15 Allspark, 19 left
orbit, 44 left ramp, 40 center, 34 right ramp, 39 right orbit) plus 29 CHALLENGE MEGATRON (A super) or 59 OPTIMUS
PRIME CHALLENGE (D Optimus). Lit shots flash (inferred). Lamp 22 OPTIMUS PRIME shows the battle (inferred).

## 9. Interactions
- The battle cannot progress during Megatron, Optimus, AHM or wizard multiballs; the access count also stops
  (4.1).
- During the Optimus multiball the Megatron lock does not lock or light (`megatron_multiball.md`).
- Optimus multiball = wizard requirement 5 (Autobot group): started = collected, super = completed.
- In Megatron D the Optimus target is the super-jackpot shot.

## 10. Reference scenarios
`traces/optimus_decepticon.txt`, `traces/optimus_autobot.txt` with `traces/watch_optimus.tsv`. The right orbit
(sw 12) needs at least 3.5 s after the center lane or the previous right orbit, or the simulator's debounce
(task 0x47 / timer 9) ignores it.

## 11. Open questions
- Deff 143 "OPTIMUS BATTLE! / SHOOT OPTIMUS" is never started; the battle shows deff 19.
- Adj 85 DISABLE OPTIMUS PRIME MOTOR is not read with `adj_get` (maybe read directly from NVRAM).
- The Optimus position logic (0x0100e798, target 0x2b) and when exactly it rises / lowers were only seen as motor
  runs; the watch address for the target did not change.
- Second argument of `multiball_start` (1 here, 0 for Megatron / wizard).
- 0x02111f90 and the 25,000 jackpot term are never incremented: dead features or set elsewhere by direct writes.
