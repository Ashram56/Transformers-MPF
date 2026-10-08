# Megatron lock and Megatron multiball (Autobot "A" and Decepticon "D" versions)

Audience: a developer rebuilding Transformers Pro 1.80 (`tf_180`) in MPF who has not read the ROM. Addresses refer
to `code/tf_decompiled.c` (headers `// ==== ADDR NAME`; most functions here are unnamed `FUN_...`). Tables are in
the ROM data area (0x040xxxxx = file offset 0x0xxxxx). 1 tick = 16.25 ms (measured: the 312-tick phase-2 timeout
below lasts 5.07 s in traces/megatron_autobot.jsonl, 51.49 -> 56.56 s).

Audit numbers: the trace prints the **counter id** passed to `audit_add`; the line in
`rom_data/settings/audits.csv` is counter + 8 (e.g. counter 0x74 = 116 = audits.csv #124 "MEGATRON BATTLE LOCKS LIT").

Reference traces (scenario `.txt` + trace `.jsonl` in `traces/`, watch file `traces/watch_megatron.tsv`, factory
settings, **no pokes**):
| Trace | What |
|---|---|
| megatron_decepticon | Decepticon (default side): 3 locks + 4th lock starts the multiball, 10 jackpots (one at the Megatron lock), 3 double jackpots at the center lane, super jackpot at Optimus, drains, total screen; then relighting the lock with one Energon set (level 1) and locking again |
| megatron_autobot | Autobot (left flipper on the choose-side screen): 4 locks, jackpot at Megatron, double jackpot, phase-2 timeout, unlit shot, jackpot, 6 double jackpots, super jackpot, jackpot after the super, drains, total screen |

## 1. Summary
The Megatron head (lock, switches 38-41, released by coil 3) holds real balls. With factory settings all four locks
are lit at game start: shoot Megatron four times; balls 1-3 are locked ("BALL n LOCKED", 25,000 each) and a new ball
is auto-launched; the 4th lock starts a **4-ball Megatron multiball** and releases the locked balls. Later
multiballs need Energon target-bank completions to relight the lock ("N MORE TARGET COMPLETIONS TO LIGHT LOCK").
The multiball has two rule sets chosen by the player's side:
- **Autobot (A)**: jackpot at Megatron, then all 6 main shots light for double jackpots (they time out if you stop
  scoring them); after 6 doubles (or 10 jackpots in all) the super jackpot is lit at Megatron. Super = all jackpots
  since the last super (at least 1,000,000).
- **Decepticon (D)**: all 6 shots + Megatron lit for growing jackpots (100,000 .. 250,000); after 10 jackpots the
  center lane is lit for 3 double jackpots (500,000); then Optimus lights for a 1,000,000 super jackpot.
It ends when one ball is left; a "MEGATRON MULTIBALL TOTAL" screen follows.

## 2. Settings (operator adjustments)
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 68 | MEGATRON M.B. LOCK DIFFICULTY | 0 (EASY) | 0-2 (EASY/MEDIUM/HARD) | starting lock level per player at game start [0x0100ada4]; see 4.1 |
| 69 | MEGATRON M.B. VIRTUAL LOCK | NO | NO/YES (FRANCE: YES) | YES: the lock keeps no balls, every locked ball is kicked out again (locks are counted virtually) [0x0100a1f8] |
| 88 | SAVE MEGATRON PROGRESS | YES | NO/YES | YES: Autobot multiball phase, lit shots, jackpot count and the "since last super" sum are kept per player into the next Megatron multiball [0x0100c200] |
| 89 | AUTOFIRE AFTER LOCK | YES | NO/YES | a new ball is served and auto-launched (coil 2) after a lock (verified in emulator: megatron_decepticon.jsonl 17.14 lock -> 19.65 trough coil 1 -> 20.30 coil 2) (inferred: adj read not located) |
Nothing else (values, counts, timers) is adjustable.

## 3. State
### 3.1 Lock (per player, NVRAM player area; arrays indexed [player-1])
| Name (watch) | RAM | Init / reset | Meaning |
|---|---|---|---|
| mtl_level | 0x02111d44 + (p-1) | adj 68 at game start [0x0100ada4]; +1 at each Megatron multiball start (either side) [0x0100ad70] | lock level |
| mtl_need | 0x02111d48 + (p-1) | from level [0x0100acb4] | completions needed per lock (initial value) |
| mtl_count | 0x02111d4c + (p-1) | = mtl_need [0x0100acb4]; re-armed when a lock is lit at level >= 2 [0x0100af0c] | completions still needed |
| mtl_lit | 0x02111d50 + (p-1) | 4 if mtl_need = 0 else 0 [0x0100acb4] | locks lit |
| mtl_locked | 0x02111d54 + (p-1) | 0 [0x0100acb4] | balls locked |
| keep_lock | 0x0211108c | recomputed [0x0100a1f8] | how many balls the Megatron device keeps |

### 3.2 Autobot multiball (A)
| Name (watch) | RAM | Init / reset | Meaning |
|---|---|---|---|
| mta_phase | 0x00034da4 | 1 at start (or restored) | 1 = jackpot at Megatron, 2 = double jackpots, 3 = super lit |
| mta_mask | 0x00034da8 | 0x40 in phase 1 / 3; 0x3f entering phase 2 | lit shots (bit = shot index, 3.5) |
| mta_mult | 0x00034dac | 1 | jackpot step M: +1 per jackpot or double jackpot, max 6; back to 1 on the phase-2 timeout and at the super |
| mta_supers | 0x00034db0 | 0 at start [0x0100c200] | supers this multiball |
| mta_total | 0x00034db4 | start award | total for the end screen |
| mta_jp | 0x00034dba | 0 / restored | jackpots + doubles since the last super |
| (saved) | 0x02111db4 / 0x02111dc4 / 0x02111dd4 + (p-1) | written as play goes | per-player copies of phase / mask / jp for adj 88 |
| mt_mb_since_super | 0x02111da0 + (p-1) | +1 at each A start; 0 at a super (and at start when adj 88 = NO) | indexes the super percentage |
| mt_sum | 0x02111da4 + 4(p-1) | += every jackpot and double; 0 at a super (and at start when adj 88 = NO) | base of the super jackpot |

### 3.3 Decepticon multiball (D)
| Name (watch) | RAM | Init / reset | Meaning |
|---|---|---|---|
| mtd_phase | 0x00034e18 | 1 | 1 = jackpots, 2 = double jackpots, 3 = super lit |
| mtd_mask | 0x00034e1c | 0x7f in phase 1 | lit shots |
| mtd_supers | 0x00034e24 | 0 | supers this multiball |
| mtd_total | 0x00034e28 | start award | total for the end screen |
| mtd_jp | 0x00034e2e | 0 | jackpots this cycle |
| mtd_dj | 0x00034e30 | 0 on entering phase 2 | double jackpots this cycle (reads 65535 before the first phase 2: uninitialised, harmless) |

Game flags: 0x25 (37) Megatron A running, 0x26 (38) A grace; 0x29 (41) Megatron D running, 0x2a (42) D grace
[0x0100c200, 0x0100e0bc] (verified in emulator).

## 4. How it starts
### 4.1 Lighting the lock
1. At game start: level = adj 68 [0x0100ada4]. Completions needed per lock [0x0100acb4]:
   level 0 -> 0 (all 4 locks lit at once), level 1 -> 1, level n >= 2 -> min(n - 1, 5).
   (verified in emulator: megatron_decepticon.jsonl 10.52 s, mtl_lit = 4 at game start)
2. A **target completion** = completing the 3-bank Energon targets (switches 2, 49, 46; see
   `allspark_and_energon.md`), whose award calls 0x0100af0c [0x01030b34]. It counts only if no Megatron, Optimus,
   All Hail Megatron or wizard multiball is running, no lock is lit (mtl_lit = 0) and lit + locked < 4 [0x0100ae6c].
   - Not the last one: mtl_count -= 1, 5,000 points [0x0100af0c]. (No display found for this; deff 138
     "N MORE TARGET COMPLETIONS TO LIGHT LOCK" exists but nothing starts it, see 11.)
   - The last one: **lock lit**. level < 2: mtl_lit = 4 (all four); level >= 2: mtl_lit += 1 and the counter is
     re-armed to mtl_need. Counter 0x74, deff 139 (LOCK IS LIT), leff 167, sound 0x293, 10,000 points
     [0x0100af0c]. (verified in emulator: megatron_decepticon.jsonl 88.03 s: Energon set deff 125 + 250,000, then
     deff 139 + 10,000, mtl_lit 0 -> 4)
   - ROM bug: the re-arm copies the whole 4-byte "needed" array over the 4-byte counter array (`DAT_02111d4c =
     DAT_02111d48`), so it resets every player's counter, not only the current one [disasm 0x0100af84]. Rebuild it
     per player.
3. Consequence of the gate: at level >= 2 each lock must be used before the next one can be lit.

### 4.2 Locking balls (Megatron lock entry, shot 6)
Lock entry handler 0x0100a31c (switches 38-41; the trace's `hit 38..41`) calls 0x0100b130 when mtl_lit > 0 and
no Megatron/Optimus/AHM/wizard multiball is running [0x0100b0b8]:
1. mtl_lit -= 1.
2. If mtl_locked + 1 < 4: mtl_locked += 1, counter 0x75, deff 140 "BALL n LOCKED" (via task 0x73), 25,000 points
   [0x0100b130]. The lock entry itself also scores 5,120 (switch score) [0x0100a420].
   (verified in emulator: megatron_decepticon.jsonl 17.14 / 21.31 / 25.49 s)
3. Else (4th ball): start the multiball: Autobot side -> 0x0100c200, Decepticon -> 0x0100e0bc [0x0100b130].
   (verified in emulator: megatron_decepticon.jsonl 29.65 s; megatron_autobot.jsonl 36.88 s)

Ball handling [0x0100a1f8]: the device keeps lit + locked balls, capped by its size (observed 3 =
the 3 locked balls), and 0 when adj 69 = YES, the back-door task 0x4f runs, a multiball runs (`any_multiball_running`
0x01006704: Mudflap & Skids, Optimus A/D, Megatron A/D, wizard multiball) or All Hail Megatron runs (flag 0x3c,
0x0100ff6c). Timed battles, double and fast scoring do not release the held balls. Back door (switch 13) starts task 0x4f for 187 ticks (3.0 s); a lock entry during it is not held and skips
all shot handlers. The lock-entry handler waits while tasks 0x73/0x74/0x75 (lock deff, A intro, D intro) run, and
the eject waits for deff 61 (Optimus super) [list 0x040c61f8 / 0x040c6200]. A ball re-entering about 1-2 s after an
eject is ignored (observed; locks spaced 4 s worked on the default side, 6 s were used on the Autobot run).

### 4.3 Multiball start (both sides)
`multiball_start(balls = 4 if none in play else in_play + 3, 0, ball save 625 ticks = 10.2 s, grace 187 ticks =
3.0 s)` [0x0100c200 A / 0x0100e0bc D] (verified in emulator: both traces). Then:
- mtl_level += 1 and the lock state is re-derived (4.1 step 1) [0x0100ad70]: after the first multiball at level 0,
  one Energon completion relights all 4 locks (verified in emulator: mtl_level 0 -> 1, mtl_need 1).
- Wizard requirement 0 (Megatron multiball) "collected": 0x01035af0(0,1), counter 0x81 (#137 WIZARD: REQ. 1
  COLLECTED) - also counts toward the extra ball lit at adj 83 requirements, see `wizard_modes.md`.
- The locked balls are released about 6.5 s after the start, 0.4 s apart: sounds 0x13b, 0x13c, 0x13d, leffs 23,
  24, 25, coil 3 (verified in emulator: megatron_autobot.jsonl 43.35-44.3 s).
- **A** [0x0100c200]: adj 88 YES restores phase/mask/jp from the player's copies (a saved phase 2 restarts at
  phase 1); NO resets them and mt_mb_since_super / mt_sum. supers = 0, M = 1. **250,000** (not multiplied).
  Flag 37 set, 38 cleared. Intro deff 69 via task 0x74; leff 61; counter 0x76 (#126 M.B.A. STARTED);
  mt_mb_since_super += 1. A 434-tick task 0x57 is started (purpose not traced).
- **D** [0x0100e0bc]: **100,000**. Flag 41 set, 42 cleared. Intro deff 75 via task 0x75; leff 69; counter 0x7a
  (#130 M.B.D. STARTED).

## 5. Behaviour while running
Shot indices (from the switch handlers): 0 Allspark / left eject (sw 3), 1 left orbit (sw 5/6), 2 left ramp
(sw 10), 3 center lane (sw 11), 4 right ramp (sw 14), 5 right orbit (sw 12), 6 Megatron lock, 7 Optimus target
(sw 51, D only). Each shot table row is {mask bit, lamp group, shot-multiplier slot}; a slot != 0 multiplies the
award by that shot's 1x/2x/3x multiplier (`FUN_01023538`, see `combos_and_multipliers.md`)
[table 0x040c63e4 A, 0x040c65dc D]. Megatron (slot 0) is never multiplied; Optimus uses the center lane's slot.

### 5.1 Autobot (A) [0x0100c430]
Let J = min(100,000 x (mta_supers + 1) + 25,000 x M, 500,000) [0x0100bf14]; DJ = min(2 x J, 1,000,000) [0x0100bf70].
| Trigger | Condition | Effect | Deff | Sound | Next |
|---|---|---|---|---|---|
| Megatron lock | phase 1 | J x mult; jp += 1; M += 1 (max 6); counter 0x77 | 71 JACKPOT | 0xca (sample index cycles) | phase 2, mask 0x3f; if jp >= 10: phase 3 |
| a lit main shot | phase 2 | DJ x mult; the shot unlights; jp += 1; M += 1; counter 0x78 | 72 DOUBLE JACKPOT | 0xd2 | if jp >= 10 or no shot left: phase 3 (mask 0x40, M = 1) |
| no double jackpot for 250 + 62 ticks (5.07 s) after the last one | phase 2 | mask 0x40, M = 1 (tasks 0xbd / 0xbe) | - | - | phase 1 |
| Megatron lock | phase 3 | **super** = max(1,000,000, pct x mt_sum), pct = [100, 100, 75, 50]% indexed by min(mt_mb_since_super, 3) [table 0x040c6438, 0x0100c024]; supers += 1; jp = 0; mt_sum = 0; mt_mb_since_super = 0; wizard req 0 completed (0x01035af0(0,2), counter 0x8c #148); counter 0x79 | 73 SUPER JACKPOT | from deff 73 | phase 1 |
| unlit shot | any | nothing from this mode | - | - | - |
Observed (megatron_autobot.jsonl): 49.05 jackpot 125,000; 51.49 DJ 300,000; 56.56 timeout (phase 1, M = 1);
59.70 unlit left ramp: nothing; 62.13 jackpot 125,000; 64.58-73.97 six DJ 300k, 350k, 400k, 450k, 500k, 500k ->
phase 3; 76.89 super **3,050,000** (= the sum of the 9 awards); 81.07 jackpot 225,000 (supers = 1).

### 5.2 Decepticon (D) [0x0100e29c]
| Trigger | Condition | Effect | Deff | Sound | Next |
|---|---|---|---|---|---|
| lit main shot 0-5 | phase 1 | min(100,000 + 25,000 x jp, 250,000) x mult; shot unlit; jp += 1; counter 0x7b | 77 JACKPOT | 0xe4 | jp = 10: phase 2 (mask 8) |
| Megatron lock | phase 1, lit | 100,000 flat; all 7 relit (mask 0x7f); jp += 1; counter 0x7b | 77 | 0xe4 | same |
| center lane | phase 2 | 500,000 x mult; dj += 1; counter 0x7c | 78 DOUBLE JACKPOT | 0xf7 | dj = 3: phase 3 (mask 0x80); Optimus is raised (0x0100e798 returns position 0x2b) |
| Optimus target sw 51 | phase 3 | 1,000,000 x mult; supers += 1; wizard req 0 completed (counter 0x8c); counter 0x7d | 79 (super jackpot) | 0xf9 | phase 1, mask 0x7f, jp = 0 |
Observed (megatron_decepticon.jsonl): 38.08-47.21 jackpots 100k, 125k, 150k, 175k, 200k, 225k (left orbit, left
ramp, center, right ramp, right orbit, Allspark); 50.37 Megatron 100,000 and all relit; 52.78-56.14 250k x 3 ->
phase 2; 58.32 / 60.49 / 62.66 DJ 500,000 -> phase 3; 66.90 super 1,000,000 -> phase 1.

## 6. How it ends
- Draining to one ball: the running flag is cleared (A [0x0100c814], D likewise); a grace task (0xbb for A: sleeps
  156 then 62 ticks) then the total screen: deff 74 "MEGATRON MULTIBALL TOTAL: n" (A) / deff 80 (D) via a queued
  task (0x8b) [0x0100c790]; not shown in tilt / game-over states (0x31468 & 0x310).
  (verified in emulator: A flag 37 cleared 86.25 s, deff 74 at 89.78 s; D flag 41 cleared 73.84 s, deff 80 at 77.40 s)
- Add-a-ball (Allspark mystery award, 0x01024a60) during the grace window revives the multiball [0x0100c858].
- Carries over: mtl_level (+1 per multiball), A progress if adj 88 = YES, mt_sum / mt_mb_since_super (A),
  wizard requirement 0. D progress always starts fresh.

## 7. Media
| When | Display effect | Sound | Lamp effect |
|---|---|---|---|
| lock lit | 139 (LOCK IS LIT; no text captured) | 0x293 | 167 |
| ball locked | 140 "BALL n LOCKED" | from table 0x040c62aa: 0x29a / 0x29c / 0x29f (lock 1/2/3), then speech 0x297 | 168 |
| A start | 69 intro (6.4 s) then background 70 "MEGATRON MULTIBALL / SHOOT FLASHING SHOTS" | 0xc7, 0xc8, 0xc9; music 0x38 | 61, 62 |
| A jackpot / double / super / total | 71 / 72 / 73 / 74 "MEGATRON MULTIBALL TOTAL:" | 0xca / 0xd2 / 0xd9.. / 0xde | |
| D start | 75 intro (6.1 s) then background 76 | 0xe2, 0xe3; music 0x3b | 69, 70 |
| D jackpot / double / super / total | 77 / 78 / 79 / 80 | 0xe4 / 0xf7 / 0xf9 / 0xfc | |
| lock release | | 0x13b, 0x13c, 0x13d | 23, 24, 25 |
Music table (`rom_data/sound/music_table.csv`): row 1 = flag 37 -> deff 70 + music 0x38; row 2 = flag 41 ->
deff 76 + music 0x3b [0x0100cee0, 0x0100ee0c]. Deff 81 "COMPLETE ALL SHOTS FOR SUPER JACKPOT" belongs to All Hail
Megatron (`wizard_modes.md`), not to this multiball.

## 8. Lamps
Shot inserts by lamp group (`rom_data/io/lamp_groups.json`): A uses groups 0x25-0x2b, D 0x2c-0x33: the orange arrow
of each shot (15 Allspark, 19 left orbit, 44 left ramp, 40 center, 34 right ramp, 39 right orbit), 29 CHALLENGE
MEGATRON for the lock and 59 OPTIMUS PRIME CHALLENGE for Optimus (D) [tables 0x040c63e4, 0x040c65dc]. Lit shot =
flashing (inferred from the leff shapes; not captured lamp by lamp). Megatron inserts 27 / 57 / 58 show the lock
(inferred).

## 9. Interactions
- Blocks: lock lighting and locking while any Megatron/Optimus/AHM/wizard multiball runs [0x0100ae6c, 0x0100b0b8];
  the Optimus battle cannot progress (center lane scores 1,000 only, see `optimus_multiball.md`); character battles
  do not start (`battles.md`).
- Wizard: starting = requirement 0 collected; super jackpot = requirement 0 completed (needed for All Hail
  Megatron on the Decepticon side and for the wizard multiball).
- Energon sets keep scoring their own award (250,000+) when they light a lock.
- Combos (0x01002fec) and switch scores keep running during the multiball.

## 10. Reference scenarios
`traces/megatron_decepticon.txt`, `traces/megatron_autobot.txt` (run `tf_ref <scenario> <trace> traces/watch_megatron.tsv`).
Key expected events: see the observed lines in 4.1, 4.2, 5.1, 5.2 and 6.

## 11. Open questions
- Deff 138 "N MORE TARGET COMPLETIONS TO LIGHT LOCK" (function 0x0100b2f0) has no starter in the code; a
  non-final completion only scores 5,000 silently. Searched for deff_start(0x8a) and task starters.
- Purpose of task 0x57 (434 ticks) at the A start and of `multiball_start`'s second argument.
- The re-arm bug (4.1) was read in the disassembly, not triggered with two players.
- Exact insert-lamp states per phase were not captured.
