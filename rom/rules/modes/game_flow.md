# Game flow (base game) — Stern Transformers Pro 1.80 (`tf_180`)

Audience: a developer rebuilding the game in MPF who has not read the ROM. Most of the flow lives in the
Stern SAM OS (addresses below 0x36000), which is the same OS as Tron Legacy 1.74 at different addresses;
Transformers game code hooks into it through OS events (`event_post(id)`). Sources: `[0xADDR]` = function in
`code/tf_decompiled.c` (scratch copy `out/tf_decompiled.c`), "observed" = `rules/traces/game_flow.jsonl`
(scenario `game_flow.txt`, watch list `watch_game_flow.tsv`, factory settings, 2 players), "inferred" = reasoning.
Times in the trace are emulated seconds since power-on (script starts at 8.0 s).

Related specs: side choice and the per-switch table in `rules/switches_and_shots.md`; combos, bonus X and the
lanes in `combos_and_multipliers.md`; pops, spinner, Bumblebee, double/fast scoring in `scoring_features.md`.

Naming warnings: game state word is RAM **0x31468** (u16), not Tron's 0x37274. The playfield multiplier byte
is **0x3243c** and, unlike Tron, Transformers **does** set it (double scoring = 2, see `scoring_features.md`).

## 0. Tick

1 `task_sleep` tick ≈ 16.26 ms (Tron measurement, same OS and same scheduler; not re-measured here). The
ROM treats 62 ticks (0x3e) as one second for ball save and tilt bob timing [0x00017a28] [0x0001dc14].
Observed here: ball search 10.06 s after the last switch (traces t 30.59 → 40.65), i.e. 620 ticks at 16.2 ms.

## 1. Summary

1-4 players, 3 balls each (adj 31). START with a credit starts a game; more players can be added while
player 1 is on ball 1. Each new ball: the player's **side** (Autobot / Decepticon) is chosen on the first
ball with the flippers (random by default), the ball is plunged manually, a **skill shot** is lit at the
player's own top lane (350,000 hands free, 250,000 after moving it with the flippers) and a **super skill
shot** at the Megatron back door (500,000). A 5 s ball save (+3.5 s grace) starts when the playfield becomes
valid. When the last ball drains: modes stop, the end-of-ball bonus is counted (unless tilted), then shoot
again / next player / game over with high scores and match.

## 2. Settings (operator adjustments) — `rom_data/settings/adjustments.csv`

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 31 | BALLS PER GAME | 3 | 1-10 | Balls per player |
| 32 | TILT WARNINGS | 2 | 0-3 | DANGER warnings before a tilt [0x0001da8c] (observed: 2 warnings, 3rd bob tilts) |
| 64 | COIN DOOR DISABLE TILT | 0 | 0-1 | 1 = tilt bob ignored with the coin door open [0x0001da38] |
| 38 | BALL SAVE TIME | 5 | 0-16 | Seconds × 62 ticks; 0 = no ball save [0x00017acc] |
| 65 | TRANSFORMERS SELECT | 0 RANDOM | 0-2 | Starting side per player: random / Autobot / Decepticon (observed: random gave P1 Autobot, P2 Autobot in this run) |
| 26 | EXTRA BALL LIMIT | 5 | 0-10 | Max extra balls per player per game (OS, same rule as Tron) |
| 83 | BONUS EXTRA BALL AT | 5 | 0-10 | Extra ball lit once per game when a progress count reaches this value [0x01035af0] (owned by the mode specs) |
| 22 / 23 | SPECIAL LIMIT / SPECIAL AWARD | 1 / CREDIT | | Special award [0x0001d7a0] |
| 11-21 | REPLAY TYPE AUTO, AUTO REPLAY START 20,000,000, ... | | | Replay (OS) |
| 29 / 30 | MATCH AWARD / MATCH PERCENTAGE | CREDIT / 9 | | Match [0x00019668] |
| 36 | GAME RESTART | 1 | | Hold START on ball 2+ restarts (OS) |
| 39 | TIMED PLUNGER | 0 | 0-60 | >0 auto-launches a ball left in the shooter lane (OS) |
| 40 | FLIPPER BALL LAUNCH | 0 | 0-4 | (OS) not traced |
| 48-61 | ALLOW HIGH SCORES, GRAND CHAMPION 75,000,000, HIGH SCORE #1-#4 55/40/30/25 M, awards, HSTD INITIALS | | | High score entry [0x00018d54] |
| 63 | LOST BALL RECOVERY | 1 | | Ball search → lost ball re-serve (OS) |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| gf_state | 0x31468 (u16) | machine | 16 in attract | Bits: 0x01 bonus running, 0x04 end of ball, 0x08 game over sequence, 0x10 no game, 0x20 starting, 0x80 match, 0x200 **tilted**. Observed values: attract 16, play 0, bonus 5, tilt 512, match 152 (observed) |
| gf_cur_player | 0x32438 (u8) | game | 1 | Player up [0x0001aa40] |
| gf_ball | 0x32439 (u8) | game | 1 | Ball number, advances after the last player [0x0001abb4] |
| gf_num_players | 0x2110900 (u8) | game | 1 | Players [0x0001a94c] |
| gf_scores | 0x21109e4 (u32[4]) | game | 0 | Scores |
| gf_pf_mult | 0x3243c (u8) | per ball | 1 at ball start and before bonus | Playfield multiplier applied by every score_add [0x0001cce0] [0x00019e44] |
| gf_tilt_warnings | 0x37628 (u8) | per ball | 0 at ball start | DANGER warnings this ball [0x0001da8c] (observed 0→1→2, back to 0 at next ball) |
| player side | 0x2112107 + player (u8) | per player | adj 65 at game start | 1 Autobot, 2 Decepticon (switches_and_shots.md) |
| skill_lane_mask | 0x3570c (u8) | per serve | 2 if side = Autobot, else 1 [0x01031518] | Lit skill lane: bit 1 = left top lane sw8, bit 2 = right top lane sw7 [table 0x040c7654] |
| skill flag 0x11 | game flag 17 | per serve | cleared at serve [0x01031518] | Set when a flipper moved the skill lane after the side choice → regular (not hands-free) skill shot [0x0103196c] [0x010319b0] |
| skill_count_handsfree | 0x21120d4 + p-1 (u8) | per player | 0 at the player's first ball (event 0x26) [0x010318cc] | Hands-free skill shots made |
| skill_count_regular | 0x21120d0 + p-1 (u8) | per player | idem | Regular skill shots made |
| super_skill_count | 0x21120d8 + p-1 (u8) | per player | idem | Super skill shots made |
| EB lit (OS) | 0x3759b + player / shared 0x37598 | per game | 0 | Extra balls lit [0x000180c8] [0x00018090] |

## 4. How it starts

### 4.1 Game start [0x00019c64]
Same OS sequence as Tron: event 0x2f veto, state = 0x20, players/ball = 1, extra-ball counters, scores and
replay levels cleared, event 0x2e (game hook 0x0103621c clears a per-player array 0x21121bc), then ball
start. Audit 17 GAMES STARTED. Pressing START again on ball 1 adds a player (observed t 13.89: audit 17,
sound 0x048, num_players 2).

### 4.2 Ball start [0x00019d30]
1. event 0x12, kill tasks flag 0x80; `first_ball_of_player` = ball 1 and not shoot-again (flag 9).
2. Ball search, shoot-again lamp, valid playfield reset; pf multiplier 1; tilt warnings 0.
3. If first ball of this player: event 0x26 = per-player init (about 25 game hooks: skill counters
   0x010318cc, Bumblebee 0x01001880, pops 0x0102d244, spinner 0x010324dc, 2-bank 0x0102e8f8 ...).
4. event 0x11 = per-ball init (hooks 0x0100fea0, 0x01023418 shot multipliers, 0x0102d1ec pops value 3,000,
   0x01032484 spinner value 2,500, 0x010359d4); bonus count, bonus X, held bonus reset by the 0x13 hook
   0x01000d58 (see combos_and_multipliers.md).
5. If shoot-again: deff 26 (shoot again animation, sounds 0x060 then 0x061) + leff 16.
6. deff 19 (score display); serve_ball(3) [0x0103b39c] → event 0x0f → skill shots armed (§5.1) and ball save
   armed (task 0x31, leff 14).
- On the player's **first ball** the side choice runs: deff 40 "USE FLIPPERS TO CHOOSE YOUR SIDE", music
  0x1a (Autobot) / 0x1b (Decepticon); flippers toggle (sound 0x257); the plunge confirms 0.53 s later with
  deff 41 + speech 0x057 Autobot / 0x058 Decepticon and music 0x1c / 0x1d. On later balls deff 19 with
  music 0x1c / 0x1d at once (observed t 13.00, 18.37, 52.96, 54.71, 74.57). Details: switches_and_shots.md.
- Trace: ball start → trough eject 0.54-0.64 s later; first playfield switch switches music to 0x1e
  (Autobot) / 0x1f (Decepticon) (observed t 18.81, 56.31).

### 4.3 Valid playfield (OS, same rule as Tron) [0x0000e264 hooks 0x6b/0x6c]
The switch descriptor's top byte (`flags_0x0c` in `rom_data/io/switches.csv`): **0x20 = force** (one hit
validates): 7, 8, 10, 11, 12, 14, 24, 25, 28, 29, 34; **0x10 = valid** (3 different needed): 1, 2, 4, 5, 6,
13, 35, 37, 46, 49, 50; slingshots, pops (0x04) and the eject/lock/trough switches do not count (inferred from
the flag pattern, matching Tron's 0x2000/0x1000 bits). Observed: one sling then drain → re-served for a manual
plunge, same player and ball, no bonus, no ball save (t 25.25 → 26.44 drain → 27.61 eject); sw7 or sw12
alone validates (t 18.78, 30.57).

## 5. Behaviour while running

### 5.1 Skill shots [0x01031928] [0x01031518] [0x0103177c] [0x01031630] [0x01031848]
Armed on every serve of type 3 or 4 (new ball; not on ball-save replacements or re-serves) by the event 0x0f
hook 0x01031928: task 0xb2 = top-lane skill shot, task 0xb4 = super skill shot. Type 1 (ball-save
auto-launch) cancels both.

**Top-lane skill shot** (task 0xb2):
- Lit lane: the player's own colour: **Autobot → right top lane (sw7, red lamps 52/49)**, **Decepticon →
  left top lane (sw8, purple lamps 51/50)** [0x01031518] [table 0x040c7654]. leff 92 shows the lit lane
  (two lamps on solid, other lane off) [0x01031a04].
- Left flipper shifts the lit lane one way, right flipper the other (with two lanes both toggle)
  [0x0103196c] [0x010319b0]. During the side choice the flippers toggle side and lane together and nothing
  else happens; after it, a flipper press sets game flag 0x11 (= not hands free) (observed t 79.69:
  flag 17 set, mask 2 → 1).
- Hitting the lit lane while task 0xb2 runs:
  - flag 0x11 clear (**hands free**): 350,000 + 25,000 × hands-free skill shots already made this game,
    cap 500,000 [0x010315e0] (observed t 18.79: 350,000).
  - flag 0x11 set: 250,000 + 25,000 × regular skill shots made, cap 500,000 [0x01031590]
    (observed t 80.86: 250,000).
  - The count used is then +1. deff 42 (prio 193): image sweep, then "HANDS FREE / SKILL SHOT / value" or
    "SKILL SHOT / value"; leff 93, sound 0x165 [0x01031aa4]. Both skill tasks are killed.
  - The lane's own handler also runs: the lane switch lights **both** lamps of that lane (two lane awards of
    2,500, see combos_and_multipliers.md) (observed t 18.79, 80.86).
- Hitting the unlit lane: nothing extra, and the skill shot is cancelled (task killed) [0x01031630].
- Ends (task killed) on a **force** switch other than 7, 8, 12, or after **3 different valid** switches other
  than 7, 8, 12 [0x010313cc] [0x01031420] [0x01031470] [obj 0x31400 count 3]. Slings and pops do not end it.

**Super skill shot** (task 0xb4):
- Megatron back door (sw13) while task 0xb4 runs: 500,000 + 100,000 × super skill shots made this game,
  cap 1,000,000 [0x010317cc]; count +1; deff 43 "SUPER SKILL SHOT / value" (prio 193, leff 94, sound 0x167)
  is queued through task 0x65 and appears when the display is free (observed t 55.12 score 500,000,
  deff 43 at t 57.21, 2.1 s later). Both skill tasks killed.
- Ends on a force switch other than 12, 13 or 3 different valid switches other than 12, 13 (obj 0x3140c).
  The right orbit (sw12) does not end either skill shot (observed t 56.29).

### 5.2 Ball save (adj 38) [0x00017acc] [0x00017a28] [0x00017b3c]
Same OS code as Tron: armed at each new-ball serve (task 0x31, adj38 × 62 = 310 ticks, leff 14); paused until
the playfield is valid; then 6-tick steps; at expiry leff 14 stops and a 218-tick (3.54 s) grace follows
(task 0x32). A drain while either runs and the playfield is valid: deff 20 "BALL SAVED / KEEP SHOOTING"
(prio 223, sounds 0x05e, 0x05f), leff 15, audit 43, replacement **auto-launched** (coil 2) with no ball save
and no skill shot of its own.
Observed: drain t 21.12 (2.3 s after valid) → deff 20 at 21.66 (trough settle 0.54 s) → launch 22.97.
Outlanes call ball_save_try(1/2) for an early save (code, not traced). Multiball starts kill it (OS).

### 5.3 Ball search (OS)
10 s (620 ticks) without a valid/force switch or score → search (audit 37), coils pulsed; 15 s after a tilt;
5th search with adj 63 = 1 → deff 13 "PINBALL MISSING / PLEASE WAIT", ball re-served. Observed: audit 37 at
t 40.65 (10.06 s after sw12 at 30.59).

### 5.4 Tilt [0x0001da8c] [0x0001db40] [0x0001dc14] [0x0001d534]
| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| Plumb bob | not tilted, coin-door rule, warnings < adj 32 | warnings +1 | deff 23 "DANGER" (prio 241) | 0x016, then speech **0x052** 0.51 s later (game hook) | leff 11 |
| Plumb bob | warnings ≥ adj 32 | **TILT**: event 0x66, state \|= 0x200, audit 42, flippers/slings off, tasks with flag 0x1000 killed, sounds stopped, event 0x65 (game hooks stop modes: 0x0100414c fast scoring, 0x01023130 shot multipliers, 0x0102b898, 0x0103bd5c, 0x01005e98), ball search 15 s | deff 21 "TILT" | 0x017, speech **0x053** 1.0 s later | leff 9 |
| Bob held closed | — | a warning every 62 ticks, tilt after 2 | | | |
| Slam tilt (dedicated) | — | state \|= 0x200, task 0x39 resets the game (OS) | deff 24 "SLAM TILT" (prio 251) | 0x018 | leff 12 |
- While tilted: no score, no ball save, no bonus; ball(s) drain; next ball starts with warnings 0.
- Observed: bobs at t 83.19 / 85.31 → deff 23, warnings 1, 2; t 87.45 → deff 21, state 512; drain t 91.70
  → audit 8 at 92.23 (0.53 s), no deff 25, next player at once (state 0, warnings 0).

### 5.5 Extra ball (deff 53 / 54) and special (deff 55 / 56)
- **Lighting the extra ball** [0x01007b40]: OS lit count +1 (0x000180c8), task 0x5f queues deff 53
  "EXTRA / BALL / IS LIT" (prio 180, leff 42 is started by it as leff 0x2a, sound call 0x062 cycled through its
  samples). Sources: left-eject random award "EXTRA BALL LIT" (weight 5 of the award bag at 0x040dde30,
  [0x01024924]); a progress count reaching adj 83 (once per game, flag 0x15) [0x01035af0]. Not traced.
- **Collecting** [0x01007b74]: the **right orbit** (sw12 path 0x01033488) while lit: OS award 0x00018204 →
  0x00018170 (same as Tron: limit adj 26, audit, shoot-again pending, lamp SHOOT AGAIN); deff 54 (sound 0x064).
  Not traced.
- **Shoot again**: at the next end of ball the same player plays again with the same ball number; ball start
  shows deff 26 + leff 16 [0x00019d30] [0x0001abb4].
- **Special** [0x01008528]: lit by the left-eject award "SPECIAL LIT" (weight 1) [0x010248b0]: lamp 53
  SPECIAL on, task 0x61 queues deff 55 "SPECIAL / IS LIT" (prio 180, sound 0x066). Collected at the **right
  orbit** while lamp 53 is lit [0x01008684]: lamp off, OS special award 0x0001d7a0 (adj 22/23), deff 56
  (sound 0x068). Not traced.

### 5.6 Replay, high score, match
- Replay (OS): checked on every score; deff 28 (sound 0x068 in deff), knocker. Factory: auto replay at
  20,000,000.
- High scores [0x00018d54]: after the last ball, before match: Grand Champion 75 M, #1-#4 55/40/30/25 M →
  deff 33 "PLAYER %d", deff 31 "PLAYER %d / ENTER INITIALS", deff 32 initials entry; deffs 34-37 are the
  competition/tournament results ("SORRY, YOU DID NOT QUALIFY", "YOU QUALIFIED!", "%P PLACE") [0x0001e810]
  [0x0001e328]. Not traced (needs ≥ 25 M).
- Match [0x00019668]: deff 38 (prio 245), music 0x023, then 0x073 (observed t 166.65 → 171.48); award adj 29,
  percentage adj 30.

## 6. How it ends

### 6.1 End of ball [0x00019e44]
Same as Tron: event 0x1e, state |= 4, event 0x1d (game hooks end multiballs/modes: 0x0100415c,
0x0100c8dc, 0x0100e768, 0x01010428, 0x01023140, 0x01027fc4, 0x0102a0a8, 0x0103686c), audit 8 (and 40 / 41
LEFT/RIGHT DRAINS after an outlane), wait up to 169 ticks for "total" deffs, **pf multiplier = 1**, then (not
tilted) deff 25 bonus (see combos_and_multipliers.md for the formula), event 0x16 adds it, event 0x15; wait
for replay tasks; clear tilt; event 0x1f; next up [0x0001abb4].
- Observed: drain t 42.82 → audit 8 + deff 25 at 43.36 (0.54 s) → bonus added at 48.85 (5.5 s at bonus X 1)
  → next player's ball start in the same ms.
- Bonus sounds: 0x021 (Autobot) / 0x020 (Decepticon) at start, 0x077 + 0x078 at +0.76 s, 0x079 +1.08 s,
  0x07a +2.1 s ("TOTAL BONUS"), 0x022 +2.44 s, 0x001 +5.45 s (observed).

### 6.2 Multi-player rotation [0x0001abb4]
Shoot-again pending → same player, flag 9. Else player + 1; after the last player, ball + 1 and player 1.
Per-player state lives in NVRAM arrays indexed by player and survives other players' turns. Observed order:
P1 b1 → P2 b1 → P1 b2 → P2 b2 → P1 b3 → P2 b3 (t 48.86, 74.57, 92.23, 118.02, 142.34).

### 6.3 Game over [0x0001a144]
Ball > balls per game: event 0x2a, state |= 0x18, audits (46, 19 observed), high score entry, match deff 38,
event 0x2b (game hook 0x01006200), attract: deff 1 + leff 1, sound 0x024 then 0x04b 2.0 s later
[0x01006164]. Observed: last bonus t 166.65 → deff 38 at once → attract t 172.66 (6.0 s).

## 7. Media

| When | Display effect | Sounds | Lamp effect |
|---|---|---|---|
| Ball start | deff 19 score (background) | music 0x1c / 0x1d (side), 0x1e / 0x1f after first switch | leff 14 (ball save) |
| Side choice | deff 40, deff 41 | 0x1a/0x1b, 0x257, 0x057/0x058 | leff 104, 92, 95 at start; leff 96 at confirm |
| Skill shot | deff 42 "HANDS FREE / SKILL SHOT / n" or "SKILL SHOT / n" | 0x165 | leff 93 |
| Super skill shot | deff 43 "SUPER SKILL SHOT / n" | 0x167 | leff 94 |
| Ball saved | deff 20 | 0x05e, 0x05f | leff 15 |
| Tilt warning / tilt / slam | deff 23 / 21 / 24 | 0x016 + 0x052 / 0x017 + 0x053 / 0x018 | leff 11 / 9 / 12 |
| EB lit / collected | deff 53 / 54 | 0x062 / 0x064 | leff 42 (from deff 53) |
| Special lit / collected | deff 55 / 56 | 0x066 / 0x068 | — |
| Shoot again | deff 26 | 0x060, 0x061 | leff 16 |
| Bonus | deff 25 | see 6.1 | — |
| Match | deff 38 | 0x023, 0x072-0x074 | — |
| Game over | deff 1 (attract) | 0x024, 0x04b | leff 1 |

## 8. Lamps
- Skill lanes: lamps 49-52 (TOP LANE RED/BOT, PURPLE/BOT, PURPLE/TOP, RED/TOP) via leff 92 while task 0xb2
  runs [0x01031a04].
- 53 SPECIAL: lit while a special is lit [0x01008528].
- Shoot again / start button: OS rules as Tron (not re-checked).

## 9. Interactions
- Skill shot and super skill shot exist only on a freshly served ball (not after ball save or re-serve).
- A skill shot hit counts as a top-lane hit for the lanes feature and the combo/bonus counters.
- pf multiplier is forced to 1 before the bonus, so double scoring never doubles the bonus.
- Tilt kills running modes through event 0x65 hooks and stops ball save.

## 10. Reference scenario
`traces/game_flow.txt` → `traces/game_flow.jsonl` (watch `watch_game_flow.tsv`). Key events:
- t 18.79 hands-free skill shot 350,000 (deff 42); t 21.66 BALL SAVED; t 26.44 drain without valid playfield
  → re-serve; t 43.36 bonus 128,350 = 125,000 + 5 × 670.
- t 52.96 P2 flips side Autobot → Decepticon (mask 2 → 1); t 55.12 super skill shot 500,000, deff 43 at 57.21.
- t 80.86 regular skill shot 250,000 after a flipper press; t 83.19 / 85.31 DANGER; t 87.48 TILT; no bonus.
- t 166.65 match deff 38 after the last bonus; t 172.66 attract.

## 11. Open questions
- Exact ball-save timings were not re-measured on this ROM (code identical to Tron; Tron measured 5.14 s + 3.54 s).
- What speech 0x052 / 0x053 say and which hook plays them (caller logged as the switch dispatcher).
- Extra ball, special, replay, high score entry and slam tilt were read from code, not traced.
- Adj 65 RANDOM: the random source was not identified; in this run both players started as Autobot.
