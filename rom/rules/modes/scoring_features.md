# Small scoring features — Stern Transformers Pro 1.80 (`tf_180`)

Pop bumpers (pops grow, super pop bumpers), right orbit spinner (super spinner), Bumblebee target letters
and **double scoring**, the right 2-bank targets and **fast scoring**. Sources: `[0xADDR]` = function in
`code/tf_decompiled.c`; "observed" = `rules/traces/scoring.jsonl` (scenario `scoring.txt`, watch list
`watch_scoring.tsv`, factory settings, one player who started as Decepticon); "inferred" = reasoning.
1 tick ≈ 16.26 ms. All points below go through `score_add`, so they are multiplied by the playfield multiplier
(×2 during double scoring) unless noted. Every playfield switch handler also adds its own small base points
and +1 bonus count (see `combos_and_multipliers.md` §bonus); those are listed in `rules/switches_and_shots.md`.

## 1. Summary

- **Pops**: each pop hit scores the current pop value (3,000 at ball start), which then rises by 1,000 per
  hit up to 20,000 while the pops keep being hit; 1.5 s after the last pop hit it falls back to the base.
  A left-eject award ("POPS SCORE", deff 47 POPS GROW) raises the base by 1,000 for the rest of the ball.
  Another award lights **super pop bumpers**: a fixed number of hits worth 50,000+ each.
- **Spinner**: 2,500 per spin; a left-eject award lights **super spinner** (50+ spins worth 50,000+ each).
- **Bumblebee target**: spells B-U-M-B-L-E-B-E-E (9 letters, 2 pre-lit on easy); each hit scores
  10,000 + 5,000 × letters already lit; the last letter starts **double scoring**: all scores ×2 for 40 s.
- **2-bank** (right 2-bank, sw50 top / sw37 bottom): each hit 75,000 and one step toward **fast scoring**
  (7 hits the first time); the hit after "FAST SCORING READY" starts 25 s of fast scoring: every switch also
  scores the all-targets value (10,000 the first time).

## 2. Settings
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 70 | BUMBLEBEE LETTER DIFFICULTY | 0 EASY | 0-2 | Letters pre-lit for the first word: EASY 2, MEDIUM 1, HARD 0 [0x01001880] [0x010017fc] |
| 80 | DOUBLE SCORING TIMER | 40 | 10-60 | Double scoring length in "seconds" of 66 ticks [0x010039a0] |
| 81 | FAST SCORING TIMER | 25 | 10-60 | Fast scoring length, same unit [0x01004394] |

## 3. State (p = player 1-4; arrays indexed p-1)

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| pop_value | 0x2112044 + 4(p-1) (u32) | per ball | = pop_base at ball start and 93 ticks after the last pop | Value of the next pop hit [0x0102c8c8] (observed 3000→20000) |
| pop_base | 0x2112054 + 4(p-1) (u32) | per ball | 3,000 at ball start (event 0x11) unless flag 0x40 [0x0102d1ec] | Base pop value; +1,000 per POPS GROW, cap 20,000 [0x0102c56c] |
| pop_queue / pop task | 0x353c0 (u8), task 0x51 | while hits arrive | | Pending pop hits, paid one per tick [0x0102ca98] [0x0102ca30] |
| pop_total | 0x353d4 (u32) | burst | | Sum shown by deff 46 [0x0102c8c8] |
| super_pops (flag 0x4d) | game flag 77 | until completed | | Super pop bumpers lit [0x0102d31c] |
| super_pop_value | 0x2112064 + 4(p-1) | per lighting | 50,000 + 10,000 × n, cap 100,000 | n = times lit before [0x0102d270] |
| super_pop_hits_left | 0x2112078 + (p-1) (u8) | per lighting | 50 + 5 × n, cap 75 [0x0102d2bc] | |
| super_pop_count n | 0x211207c + (p-1) | per player | 0 at the player's first ball [0x0102d244] | Times super pops lit |
| spin_value | 0x21120dc + 4(p-1) | per ball | 2,500 at ball start (event 0x11) unless flag 0x1c [0x01032484] | Normal spinner value |
| super_spin (flag 0x4c) | game flag 76 | until completed | cleared at player's first ball [0x010324dc] | Super spinner lit |
| super_spin_value / hits | 0x21120ec + 4(p-1) / 0x2112100 + (p-1) | per lighting | 50,000 + 10,000 n (cap 100,000) / 50 + 5 n (cap 75) [0x01032510] [0x0103255c] | |
| super_spin_count n | 0x2112104 + (p-1) | per player | 0 at first ball | |
| bb_letters | 0x2111cf4 + (p-1) (u8) | per player | 2 / 1 / 0 by difficulty (adj 70) at first ball | Letters lit, 0-9 [0x01001a70] |
| bb_completions | 0x2111cf8 + 4(p-1) (u32) | per player | adj 70 at first ball [0x01001880] | Also selects the restart letters [0x010017fc] |
| dbl_seconds | 0x34be0 (u8) | while running | adj 80 | Double scoring countdown [0x010038dc] |
| twobank_left | 0x2112094 + (p-1) (u8) | per player | 5 + 2 × fs_starts, cap 12 [0x0102e88c] | Hits still needed for FAST SCORING READY (observed 7 at game start, 9 after the first start) |
| fs_starts | 0x2112090 + (p-1) (u8) | per player | see open questions | Fast scoring starts this game |
| fast_value | 0x34c38 (u32) | while running | 10,000 + 5,000 × fast scoring starts before, cap 50,000 [0x01004394] | All-targets award |
| fast_seconds | 0x34c3c (u8) | while running | adj 81 | Countdown |
| fast_groups | 0x34c34 (u8) | while running | 4 (+ bits of disabled switches) [0x01004080] | 2-bank targets hit this cycle: bit 1 sw50, bit 2 sw37 [table 0x040c5da0] |
| fast_total | 0x34c6c (u32) | while running | 100,000 at start | Shown by deff 137 [0x01004950] |

## 4. How it starts

### 4.1 Pops [0x01032f8c → 0x0102ca98 → 0x0102c8c8]
- Pop switches 30 (top), 31 (right), 32 (bottom). The handler [0x01032f8c] adds 170 (+1 bonus count) and
  queues one pop award; task 0x51 pays one queued award per tick and ends after **93 ticks (1.51 s) with no
  pending award**, then sets every player's pop_value back to pop_base [0x0102ca30].
- Each award (normal case): score pop_value, then pop_value = min(pop_value + 1,000, 20,000).
  Sound 0x15b (Autobot) / 0x15c (Decepticon), 0x15d while double or fast scoring runs [0x0102c804].
  deff 46 (pop total) only if not already showing; leff 26 + leff 27/28/29 (top/right/bottom) [0x0102ca98].
- Observed: 20 hits 0.16-0.18 s apart → 3,000, 4,000 ... 20,000, 20,000, 20,000; value back to 3,000 1.53 s
  after the last hit (t 25.90 → 27.43); hits 1.4-1.9 s apart → 3,000 each (t 28.06-31.53).
- During a **multiball** or the side-complete mode (0x0102c878: `any_multiball_running` 0x01006704 or flag 0x3c
  via 0x0100ff6c) the pop still scores pop_value but the value does not step and deff 46 is not shown
  [0x0102c8c8] (code). Timed battles do not affect pops; double and fast scoring only change the sound to 0x15d
  [0x0102c804, 0x0102c8c8: tests 0x010038b0 / 0x01004618].
- **Pops grow**: left-eject award "POPS SCORE %,02lu" (award bag 0x040dde30, weight 150) → [0x0102c624]:
  pop_base += 1,000 (cap 20,000), pop_value = pop_base, score pop_value, audit 0x4a, deff 47 "POPS GROW /
  value" (sound 0x15e, leff 30). The base resets to 3,000 at the next ball (code; not traced).
- **Super pop bumpers**: left-eject award "SUPER POP BUMPERS LIT" (weight 100) → [0x0102d31c]: set the
  value and hits as in §3, flag 0x4d, deff 149 "SUPER / POP BUMPERS / LIT" queued (task 100), audit 0x9d.
  While lit each pop scores super_pop_value instead (sound 0x163, leff 33) and hits_left − 1: deff 150
  "SUPER POP BUMPERS / n / HITS REMAINING / total"; at 0 deff 151 "SUPER POP BUMPERS / COMPLETED"
  (sound 0x164) and flag 0x4d cleared [0x0102c8c8]. Lit state survives balls (flag not cleared at ball start;
  inferred).

### 4.2 Spinner [0x01033a08 → 0x01032294 → 0x010320a4]
- Right orbit spinner (sw34): handler 90 points; queued like the pops (task 0x49, 93-tick idle end).
  Normal spin: spin_value (2,500), leff 152, sound 0x26d stepping through its samples [0x010320a4].
  Observed 5 spins → 5 × (2,500 + 90) (t 33.71-34.31).
- Spinning while the right orbit switch is disabled triggers the right orbit shot (0x01033488) [0x01032294].
- **Super spinner** (left-eject award "SUPER SPINNER LIT", weight 100) [0x010325bc]: value/hits as §3,
  flag 0x4c, deff 146 "SUPER / SPINNER / LIT" queued; each spin super value, sound 0x270, leff 155, deff 147
  "SUPER SPINNER / n / HITS REMAINING"; at 0 deff 148 "SUPER SPINNER / COMPLETED" (sound 0x271), flag clear.
  Not traced. deff 145 "RIGHT SPINNER = value / total" exists [0x01032344]; its starter was not found and it
  did not show in the trace.

### 4.3 Bumblebee target and double scoring [0x01033adc → 0x01001a70] [0x010039a0]
- Each sw1 hit with bb_letters = L < 9: score table[L] = 10,000 + 5,000 × L [table 0x040c5c18]
  (10,000 ... 50,000), L + 1, deff 128 "SPELL [BUMBLEBEE] FOR DOUBLE SCORING" (letters animation, sound
  0x26b, leff 150). Handler adds 30.
- When L reaches 9: double scoring starts, bb_completions + 1, letters restart at 1 after the first word
  (completions 1), 0 after that (code [0x010017fc]; observed restart 1).
- **Double scoring** [0x010039a0]: playfield multiplier = 2 (OS 0x0001cce0), deff 129 "DOUBLE / SCORING" then
  "ALL SCORES / DOUBLED / FOR n SECONDS" (sound 0x27a, ticks 0x27b), leff 156. The 0x27b ticks are four
  plays: one from deff 129 at +0.33 s, then three at +1.43, +2.41 and +3.43 s after deff 129 starts played by the
  OS delayed-sound queue (caller 0x255b8 in 0x254b4: 8 slots at 0x38368, each with a call and a countdown; the
  call is played when its countdown reaches 0) (observed scoring.jsonl t 60.31-63.41), audit 105; background deff 130
  "DOUBLE SCORING / n / ALL SCORES X 2" with music 0x026 and leff 157. Every scoring switch plays 0x27c +
  0x27d [0x01003a64]. Countdown: adj 80 steps of 11 × 6 = 66 ticks (observed 1.07 s each); sound 0x285 at 10,
  0x284..0x280 at 5..1, 0x286 at the end [0x010038dc]; the countdown pauses while 0x0100683c says the ball is
  not in free play. ADD MORE TIME award adds adj 80 (cap 90) [0x01003a8c]. Restarting kills the old timer.
- Observed: 7 hits from L=2: 20,000 ... 50,000 (t 49.87-59.97); at the 7th the 50,000 itself was ×1 but the
  same switch's 30 was ×2; pf_mult 2 for 40 counts (t 59.99 → 102.81), end sound 0x286 at 103.89, pf_mult
  back to 1 at 105.91 (2.0 s later). During it: sling 440 → 880, pop 3,170 → 6,340, Bumblebee 15,030 → 30,060.

### 4.4 2-bank and fast scoring [0x01033c00 (sw50) / 0x01033c40 (sw37) → 0x0102e9c0] [0x01004394]
- Handler 30 points. If a multiball (`any_multiball_running` 0x01006704) or a timed mode
  (`any_timed_mode_running` 0x010067bc: the seven timed battles, double or fast scoring) runs [0x0102e994]:
  5,000, sound 0x261, leff 143 only (seen in traces/switches.jsonl 119.94, sw 37 during the Blackout battle). Otherwise (one hit per 10 ticks, task 0xb1):
  - twobank_left > 0: −1, score 75,000, sound 0x263, leff 144, deff 126 "n MORE FOR FAST SCORING"
    (sounds 0x266, 0x264 near the end); when it reaches 0 deff 131 "FAST / SCORING / READY" (0x287, 0x288)
    and leff 147/148 flash the targets (observed t 112.89-123.52: 7 → 0, 75,000 each).
  - twobank_left = 0: **start fast scoring** [0x01004394]: score 100,000, fs_starts + 1, twobank_left =
    5 + 2 × fs_starts (observed 9), audit 106 (observed t 124.71).
- **Fast scoring**: fast_value = 10,000 + 5,000 × previous starts (cap 50,000), timer adj 81 counts of 66
  ticks (observed 25 counts t 130.71 → 156.22), deff 132 "FAST SCORING / ALL TARGETS SCORE n POINTS" queued
  (0.9 s), background deff 133 "ALL TARGETS=n" with music 0x027, leff 158/159/160. Sound 0x291 plays once
  about 10 s after the start (observed t 134.83 = start + 10.1 s; caller 0x10041b0 in 0x0100415c, which calls
  0x010049a8; the trigger was not decoded).
  - Every switch handler calls 0x010047b8: one all-targets award of fast_value per hit (queued, task 0x5b,
    one per tick), deff 134 when deff 132 and deff 134 are not up and no multiball runs (0x01006704), sound 0x28d,
    leff 164 [0x01004644]
    (observed sw2, sw46, sw49: +10,000 each).
  - sw50 / sw37 during fast scoring: the first hit of each this cycle raises fast_value by 1,000 (cap 50,000,
    deff 135 "ALL / TARGETS / value") [0x01004520]; when both are hit (groups = 7): time +10 counts (cap 90),
    deff 136 "TIME / EXTENDED", groups reset [0x010047b8] [0x0100457c].
  - End: the countdown reaches 0 and switches keep scoring for that last count, then task 0xae waits 250
    ticks (4.1 s) during which switches still score fast_value (MPF port observed 0 at t 148.22, deff 137 at
    153.46 in its run)
    (observed sw26 at t 160.41 +10,000), then deff 137 "FAST SCORING / TOTAL: n" (sound 0x290, leff 165)
    [0x01004220] [0x01004950].
  - ADD MORE TIME award adds adj 81 (cap 90) [0x0100457c]. Tilt and end of ball stop it (event 0x65 / 0x1d
    hooks 0x0100414c / 0x0100415c).

## 5. Behaviour table (from a fresh ball, side Decepticon, observed)
| Trigger | Condition | Score | Display | Sound | Lamp effect |
|---|---|---|---|---|---|
| Pop 30/31/32 | burst | pop_value (3,000 → 20,000) + 170 | deff 46 once | 0x15b/0x15c | leff 26 + 27/28/29 |
| Spinner 34 | normal | 2,500 + 90 | — | 0x26d | 152 |
| Bumblebee 1 | L < 9 | 10,000 + 5,000 L + 30 | 128 | 0x26b | 150 |
| Bumblebee 1 | 9th letter | 50,000 + 30, double scoring | 129, then 130 | 0x27a | 156, 157 |
| 2-bank 50/37 | left > 0 | 75,000 + 30 | 126 / 131 | 0x263 | 144 |
| 2-bank 50/37 | ready | 100,000 + 30, fast scoring | 132, then 133 | 0x289 | 158-160 |
| any switch | fast scoring | + fast_value | 134 | 0x28d | 164 |

## 6. How it ends
- Pops value: 93 idle ticks; base per ball. Super pops / spinner: when hits run out.
- Double scoring: after adj 80 counts (or ball end: pf multiplier is reset to 1 before the bonus and at ball
  start by the OS); the bonus is never doubled.
- Fast scoring: timer + 250 ticks; total deff 137 also shown at end of ball if it was running (observed twice,
  t 161.46 and 164.11 after the drain).

## 7. Media
deffs 46, 47, 126-137, 145-151 as above; leffs 26-33, 143-165 as above; music 0x026 (double scoring),
0x027 (fast scoring) from the background table (`rom_data/sound/music_table.csv`).

## 8. Lamps
leff 147/148 flash the 2-bank while FAST SCORING READY; leff 159/160 during fast scoring; leff 156/157 during
double scoring (lamp lists in `rom_data/io/lamp_effects.csv`).

## 9. Interactions
- Double scoring multiplies every score_add, including mode jackpots and fast scoring awards; not the bonus.
- Pops lose their step and deff during multiballs / the side-complete mode (0x0102c878); the 2-bank pays only
  5,000 during multiballs and timed modes (0x0102e994).
- Super pops, super spinner, pops grow, extra time, bonus hold and shot multipliers come from the left eject
  random award bag at 0x040dde30 (owned by the eject/Allspark spec): names "SPECIAL LIT" (weight 1),
  "EXTRA BALL LIT" 5, "200,000" 200, "%iX BONUS MULTIPLIER" 150, "ADD-A-BALL" 300, "ADD MORE TIME" 250,
  "POPS SCORE" 150, "BONUS HOLD" 100, "BONUS X HOLD" 100, "SHOT MULTIPLIERS LIT" 100, "SUPER SPINNER LIT"
  100, "SUPER POP BUMPERS LIT" 100 (each also has an availability test).

## 10. Reference scenario
`traces/scoring.txt` → `traces/scoring.jsonl`: pops burst t 22.57-25.90, pops slow 28.06-31.53, spinner
33.71, lanes 36.45-46.72 (see combos_and_multipliers.md), Bumblebee 49.87-59.97, double scoring 59.99-105.91,
2-bank 112.89-123.52, fast scoring 124.71-161.46, bonus 333,080 at t 172.44 (×2).

## 11. Open questions
- fs_starts is 0x2112090 but the first value of twobank_left was 7 (= 5 + 2 × 1); the per-player init that
  sets it (hook 0x0102e8f8) was not decoded.
- What sets flags 0x40 (keep pop base) and 0x1c (keep spinner value) was not found.
- deff 127 BUMBLEBEE GROWS and deff 145 RIGHT SPINNER: starters not found, not seen in traces.
- Super pops / super spinner / pops grow were read from code only (they need the left-eject award).
