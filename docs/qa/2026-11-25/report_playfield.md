# QA 2026-11-25: playfield scoring against the tf_180 decompile

Independent read-only review (scope: `side.py`, `lanes.py`, `pops.py`, `spinner.py`, `skill_shot.py`,
`twobank.py`, `bumblebee.py`, `combos.py`, `energon.py`, `allspark.py`, `bonus.py`). Probes:
[probe_playfield_bonus_hold.py](probe_playfield_bonus_hold.py), [probe_playfield_findings.py](probe_playfield_findings.py),
[probe_playfield_findings2.py](probe_playfield_findings2.py) on [qa_base.py](qa_base.py); each prints the game's
value, then the ROM's. Labels: confirmed (code + probe), code-proven, doubtful.

## Findings

| id | feature | ROM address | ROM does | game does | game file:line | proof | label | sev |
|---|---|---|---|---|---|---|---|---|
| P1 | Bonus hold flags | ball-start hook 0x01000d58 (`game_flag_clear(0x4a)` at 0x01000d8c, `(0x4b)` at 0x01000dc4); 0x01000f68 | BONUS X HOLD and BONUS HOLD last one ball; the held bonus is not stored when tilted | flags never cleared: multiplier and held bonus carry and grow for the rest of the game; mystery items 8/9 never offered again; stored when tilted | bonus.py:33-41 | probe_playfield_bonus_hold | confirmed | high |
| P2 | Shot multiplier vs combo | every major shot handler calls `FUN_010237ac(shot)` first, then the mode shots, then the combo (`0x0100a788`, `0x01033244`, `0x01033824`, `0x01033918`, `0x01033b3c`, `0x01033488`) | the shot that takes a lit multiplier scores its combo and mode awards at 2X | combo at 1X, then the multiplier is upgraded (docstring: "inferred") | combos.py:142-145 | probe F2: combo 150,000 (ROM 300,000) | confirmed | medium |
| P3 | Skill shot end | event 0x6b hook 0x010313cc (registered at 0x01031ed8); counters 0x31400 / 0x3140c count 3 distinct switches; slings 0x01033104, 0x010331a4 and pops 0x01032f8c post 0x6b | any 3 distinct switches posting 0x6b end both skill shots (slings, pops, captive ball 45, Optimus 51 count), except 7/8/12 (top lanes) and 12/13 (super) | SKILL_COUNTING leaves out 26, 27, 30-32, 45, 51 | skill_shot.py:25 | probe F3: sling, sling, pop, then the back door scores 500,030 (ROM 30); `tests/test_switches.py` asserts the wrong value | code-proven, game side confirmed | medium |
| P4 | Allspark item 10 weight | 0x01024d80 → 0x01023494 | 0 when a multiplier is lit or the roving 3X runs; with all six at 2X it returns 3 (start the roving 3X) | 0 when all shots are at least 2X; offered while one is lit | allspark.py:175 | probe F4 | confirmed | medium |
| P5 | ADD MORE TIME re-offer | `game_flag_clear(0x13)` in 0x010039a0 and 0x01004394 | double and fast scoring starts clear flag 0x13 | only a battle start clears it | bumblebee.py:73; twobank.py:119 | probe F5 | confirmed | medium |
| P6 | Double scoring countdown | 0x010038dc (the `bl 0x100683c` result is thrown away) | never pauses | pauses while the playfield is not valid | bumblebee.py:96 | probe F6 | confirmed | low-med |
| P7 | Fast scoring pause | `FUN_010062f0(0x9c)` from pops 0x01032f8c and top lanes 0x010335d0 / 0x0103361c → task 0x59 → 0x0100683c holds the count in 0x01004220 | each pop or top-lane hit holds the count 156 ticks | task 0x59 only while a battle runs | battles.py:1005, 1018; twobank.py:146 | probe F7: 24 → 18 in 6 s of pops (ROM none lost) | confirmed | medium |
| P8 | Fast scoring 2-bank cycle | 0x010047b8 (the completing hit jumps past 0x01004520, gated on task 0xac); leffs 0x90 / 0x91 | +1,000 (deff 135) only on the first target of a cycle and only during the countdown; the completing hit gives +10 counts (deff 136); leff 144 new target, 145 repeat | +1,000 and deff 135 on both targets, also in the tail; no leff 144 / 145 | twobank.py:183-193 | probe F8 | confirmed | medium |
| P9 | Timed-mode tails | `any_timed_mode_running` 0x010067bc tests tasks 0xac and 0xc3 only; pop sound 0x0102c804; 0x0100457c and 0x01003a8c kill the tail task (0xae / 0xc4) and restart the count | during the 250-tick fast and 124-tick double tails no timed mode runs (2-bank 75,000 and counts down; pop sound 0x15b / 0x15c); +10 in the fast tail restarts the countdown | both tails count as a timed mode (2-bank 5,000, pop sound 0x15d); no restart | twobank.py:94, 246-249; bumblebee.py:121-124 | probes F9 / F9b | confirmed | medium |
| P10 | Callers of the fast award (0x010047b8) and the double sounds (0x01003a64) | absent from sw 6 0x010332e4; present in the eject 0x0100a788 and the lock 0x0100a31c | sw 6 gets neither; eject and lock entries get both | the opposite | switches.py:87; allspark.py:88-100 | probe F10 (sw 6) | confirmed / code-proven | low-med |
| P11 | Optimus / center lockout (task 0x54) | 0x01033b3c (whole block only when 0x54 is not running); 0x01033d3c returns before its 30 and bonus count while 0x4e or 0x54 runs | center lane within 62 ticks of an Optimus hit scores only its 30; a repeat Optimus hit scores nothing | no 0x54 gate in combos; sw 51 always scores 30, bonus count, fast award, double sounds | combos.py:126; switches.py:84-97 | probe F11 | confirmed | low-med |
| P12 | Double scoring 0x285 warning | 0x0100393c-0x01003964 | 0x285 at the first count in 5..10 after the task (re)starts | only at exactly 10 (never with adj 80 = 10) | bumblebee.py:32 | probe F12 | confirmed | low |
| P13 | Lane award after a skill shot | 0x010335d0 / 0x0103361c call `FUN_0102db28(0x32)` / `FUN_0102e208(0x31)` | the second award lights lamp 50 (49) | lights 51 (52) | lanes.py:72 | probe F13 | confirmed | low |
| P14 | Lane rotation gate | flipper handlers 0x01032d5c / 0x01032dac | skip only on state & 0x311; leffs 97 / 99 (100 / 102) killed first | also blocks during the side choice and needs in_play; leffs not killed | lanes.py:95 | code | code-proven | low |
| P15 | Deff 44 | 0x0102db28 (same in 0x0102e208) | deff 44 always on an own-side completion, arg = result of 0x010236e8 | no deff 44 while the roving 3X runs; no arg | combos.py:199-203 | probe F17 | confirmed | low |
| P16 | Add more time in the double scoring tail | 0x01003a8c (kills 0xc4, restarts 0xc3); 0x0100457c starts deff 136 | revives double scoring; fast scoring add-time shows deff 136 | count added, stop still fires; no deff 136 | bumblebee.py:90; twobank.py:181 | code | code-proven | low |
| P17 | Spinner sound index | 0x01032484 (`strh 0` to 0x3573c) | sample index of 0x26d reset every ball | never reset | spinner.py:66 | code | code-proven | low |
| P18 | Energon deff 124 args | 0x010309a4 | arg0 = lit set without the new bit | with the new bit | energon.py:71 | code | code-proven | low |
| P19 | Broken-switch compensation | 0x01032294, 0x010308a8, 0x01004080, 0x010332e4 (`sw_is_disabled`) | disabled targets count as lit; spinner stands in for the right orbit | not modelled | spinner.py, energon.py, twobank.py | code | code-proven | low |
| P20 | Mystery item 4 text | 0x010243b4 reads 0x01000f18 after the award | shows the capped multiplier (25) | shows bonus_x + 1 (26 at the cap) | allspark.py:200 | code | code-proven | low |

Checked and matching: pops (0x0102c8c8, 0x0102ca98, 0x0102ca30, 0x0102d31c, 0x0102c624); spinner and super
spinner; Bumblebee letters, restart and double scoring start (0x01001a70, 0x010017fc, 0x010039a0); lane values,
sounds, leffs and side split; combo value, mask and window (0x01002f0c, 0x01002b5c); roving 3X (0x01023650,
0x01023538); Energon (0x010309a4, 0x01030934); 2-bank qualify (0x0102e9c0, 0x0102e88c); skill shot values and lane
mask (0x01031518, 0x01031630, 0x01031848); the bonus formula.

ROM routines with no caller (the game rightly leaves them out): 0x0102dd58 and 0x0102e408 (copies of the lane
rotation), 0x010019c8, 0x01004334, deff 48, leff 34.

## Observed / inferred values, with their code

| value | code |
|---|---|
| side choice ends on a playfield switch | hooks 0x6b / 0x6c |
| lane rotation (no address; direction "not traced") | 0x01032d5c / 0x01032dac; 50 → 51 → 8 → 9 |
| pop reset 1.53 s | 0x0102ca30 (93 idle ticks) |
| deff 46 extend | deff_046 0x0102d004 re-arms 62 ticks per award |
| spinner keep flag | 0x01032484 consumes flag 0x1c |
| 2-bank countdown hold | 0x01004220 (wait_display_idle + 0x0100683c) |
| double scoring tail split | 0x0100396c-0x0100398c: 0x286, sleep 0x7d (125 ticks, game uses 124), exit 0x01003998 sets pf_mult 1 |
| held bonus store at end of ball | 0x01000f68, registered by 0x0100172c |
| combo order "after its combo award" | wrong (P2) |
| allspark settle 47 ticks, competition sequence | observed / inferred; most weight functions (0x01024854 ...) missing from the decompile |
| bonus delay 338 ticks | observed (deff 25 0x010014b8) |

## Spec errors

1. scoring_features.md 4.3: the double scoring countdown does not pause (P6); 0x285 at the first count in 5..10
   (P12); sw 6 does not play 0x27c / 0x27d, the eject and lock entries do (P10).
2. scoring_features.md line 130: +1,000 only on the first target of a cycle and only in the countdown (P8); line
   126 "every switch handler calls 0x010047b8" is wrong for sw 6 and the locked center lane / Optimus (P10, P11).
3. game_flow.md 4.3 and 5.1: slings and pops do end the skill shot (P3).
4. allspark_and_energon.md item 10: 0x01023494 gives 0 only when a multiplier is lit or the roving 3X runs (P4).
5. combos_and_multipliers.md: the 2X goes to the shot before its combo award (P2).
6. scoring_features.md: spin_value "unless flag 0x1c" omits that the flag is cleared and the sample index resets (P17).
