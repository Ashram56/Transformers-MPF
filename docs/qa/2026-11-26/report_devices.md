# QA 2026-11-26, scope D: MPF device and settings conversion against the tf_180 code

Independent read-only review. The question for every row: does the game's MPF conversion (generated config,
overlays, Python) equal what the ROM's code and tables do? Matrix: [matrix_devices.csv](matrix_devices.csv)
(830 rows). Labels: **code-proven** (decompile or ROM table reading), **confirmed** (code + a probe).

## Scope

| Area | Elements | ROM source | Game side |
|---|---|---|---|
| Switches | 64 matrix + 32 dedicated records: number, name; per handled switch the dispatch (edges, game-state gate, debounce passes) and the valid-playfield class | records 0x040e2c20 / 0x040e3740, `switch_dispatch_debounce` [0x0000dc44] | `game/config/rom/switches.yaml`, `hardware.yaml`, `hw_vpx.yaml`, `game/tf/switches.py`, `os_layer.py` FORCE / COUNTING |
| Coils | 35 records: number, name, default pulse / hold, pop and sling OS tables (on, dead) | records 0x040ce3d4, pops 0x040ddfb0, slings 0x040ddfe0, `coil_pulses.csv` call sites | `game/config/rom/coils.yaml`, `hw_vpx.yaml` autofire / flippers |
| Lamps | 80 records | 0x040d0dfc | `game/config/rom/lights.yaml` |
| Adjustments | 98: definition (table default, factory default, range, step, wrap) and use (who reads it) | records 0x040cb20c, `adjustments.csv` readers, `presets.csv` | `game/config/rom/settings.yaml`, `service_menu.json`, `game/tf/settings.py`, every `adj[n]` / `adj_value(n)` in `game/tf` |
| Installs | 13 presets + INSTALL FACTORY | 0x01049c2c → 0x01049910 → 0x598 | `Adjustments.install`, `factory_reset` |
| Pricing / credits | 68 pricing presets, coin task, limits, free play, custom | coin task [0x00003f00], records {coin door, unit index, ladder, len} | `game/tf/credits.py`, `pricing.json`, `free_play.yaml` |
| Audits | 150 counters, 16 computed audits, display formats | audit table 0x040cd5a4, `audits.csv`, decompile `audit_add` sites | `game/tf/settings.py` Audits, every `audit(...)` in `game/tf` |
| Service menu | 17 menus | runtime lists of 0x0000eb3c (`menus_runtime.json`) | `rom/mpf_package/service_menu.json`, game mode `tf_service` |

Out of scope (other reviewers): the time of each `coil_pulse` call, what each rule does with an adjustment it
reads, the OS switch handlers' behaviour (start, tilt, slam, coins in play).

## Method

- [probe_devices.py](probe_devices.py) (`TF_ROM=... .venv/bin/python docs/qa/2026-11-26/probe_devices.py`) reads
  the ROM's own records from the image (switch, coil, lamp, adjustment, pop / sling, pricing records), agent A's
  code tables (`coil_pulses.csv`, `adjustments.csv` readers, `audits.csv`, `presets.csv`, `menus_runtime.json`) and
  the game's files, and writes the matrix. The switch dispatch rules were read in the decompile:
  `switch_dispatch_debounce` [0x0000dc44] runs the handler task only on the edge its +0xe word allows (0x400 closing,
  0x800 opening), only when gf_state is 0 or `+0xe & gf_state` (the low 10 bits are the extra states it runs in),
  after +0x1b (closing) or +0x1c (opening) main-loop passes, and posts event 0x6c (+0xe & 0x2000, force) or 0x6b
  (& 0x1000, counts toward the valid playfield).
- [probe_devices_game.py](probe_devices_game.py) runs the game in the MPF test harness for the confirmed rows
  (`.venv/bin/python -m pytest -q -s -p no:cacheprovider docs/qa/2026-11-26/probe_devices_game.py`, 5 probes).
- The adjustment use check is static (a ROM reader, an `adj_get` call site with the id, against any game reference
  to `adj[n]`, `adj_value(n)` or a named tuple of ids), and so is the audit check (the id each `audit()` call
  uses): they say whether the conversion carries the item, not whether its rule is right.

## Counts

| Verdict | Rows |
|---|---|
| match | 705 |
| missing | 59 |
| differs | 29 |
| extra | 3 |
| unverifiable | 34 |
| **total** | **830** |

What matches: every switch, coil and lamp number and name (96 + 35 + 80 records); every playfield switch's edge,
state gate and closing delay but sw 45 and 51; the valid-playfield class of every playfield switch but the eject
and locks (F16); every coil's default pulse against the code's call sites, the pop (32 ms) and sling (64 ms) OS
tables and the knocker (64 ms, [0x00019420]); 96 of 98 adjustment definitions (default = U.S.A. factory value,
range, step); 79 of 98 adjustment uses; all 68 pricing presets byte for byte (units per slot, ladder); 146 of 150
audit counters incremented; 7 of 16 computed audits.

## Findings

| id | what the ROM does | what the game does | game file:line | proof | label | sev |
|---|---|---|---|---|---|---|
| D-SM-MODE (+ D-SM-1..17, D-INS-*, D-SM-ADJSTEP) | SELECT opens the service menu: 17 menus (0x0000eb3c), the 98 adjustment editors, 166 audits, installs, resets, tests | SELECT starts mode `tf_service`, which no config defines (config.yaml modes: attract, game; no `game/tf/service.py`), so nothing opens. `Adjustments.menu/step/install/factory_reset` and `Audits.menu/reset_*` have no caller. The 13 install presets and INSTALL FACTORY are carried in `service_menu.json` (same data as presets.csv) but cannot be reached. AGENTS.md and README say the service menu is there | os_layer.py:1430, 1845; settings.py:97-122 | probe `test_SM_service_menu`: `'tf_service' in modes: False` | confirmed | high |
| D-AUD-2, 16, 22, 24, 27 | the percentage audits divide by c17 (paid plays): 2 = audit 28 (TOTAL FREE PLAYS) x 100 / c17; 16 = c9 x 100 / c17 | 2 = c18 x 100 / (c17 + c18); 16 = c9 x 100 / c8 (balls); 22, 24, 27 divide by c17 + c18 | settings.py:180-191 | probe `test_AUD_percentages` (c17 = c18 = 10: game 50 / 10 / 10 / 5 / 5, ROM 40 / 60 / 20 / 10 / 10); formulas in audits.csv (fns 0x00026c94, 0x00026c48, 0x00026d34, 0x00026d80, 0x00026ce0) | confirmed | medium |
| D-AUD-13, 72 | SOFTWARE METER and RECENT REPLAY PERCENT are always 0 (`mov r0,#0`, 0x0002af18, 0x00026d2c) | c7, and replays x 100 / plays (marked "inferred" in the code) | settings.py:185, 195 | probe `test_AUD_percentages` (game 40 / 10, ROM 0 / 0) | confirmed | low |
| D-AUD-11 | TOTAL EARNINGS = c7 (units) x unit value of the current pricing, in the pricing record's money format | coins (c2..c6) x 25 cents | settings.py:184 | audits.csv formula, fn 0x00026e7c | code-proven | medium |
| D-AUD-47 | AVERAGE SCORES = u64 sum / count, then /10 x 10; the count is per player (0x0001ce58 adds 1 per player) | score_total // games (c17 + c18), no rounding | settings.py:193 | decompile 0x00026c3c, 0x0001ce58 | code-proven | low |
| D-AUD-FMT6 | 85 feature audits show "v" and "p% OF GAMES" (display type 6, msgs 0x500 / 0x501, formatter 0x0002700c) | plain number | settings.py:199 | audits.csv display_format | code-proven | low |
| D-AUD-51, 95, 163, 166 | counters 39 LOST BALL GAME STARTS (0x0001a1dc, flag 0xb), 87 MODE START LIT, 155 SUPER COMBOS STARTED (0x01002d14), 158 SPECIAL LIT (0x01008528, NVRAM 0x02102cf8) are counted | never counted | os_layer.py:1618 (light_special says "not modelled") | decompile `audit_add(0x27,1)` in sw_start_button; error_log_user_8528 | code-proven | low |
| D-HS-COMBO, D-ADJ-90..95-use | the high-score table (0x040cf948, 18 x 32) also holds COMBO CHAMPION and BEST COMBO CHAMPION, with adj 90-95 (score, award kind, award count; 0x00018730, 0x00018c04) | 5 entries (grand champion, #1-#4); adj 90-95 never read | high_scores.py:32 | adjustments.csv readers 0x18788, 0x18c54, 0x18c64 | code-proven | medium |
| D-SW-51-EDGE, D-SW-51-disp | sw 51 OPTIMUS PRIME: +0xe = 0x1800, so the handler runs on the **opening** edge only, debounce 0 / 0 | runs on the closing edge + 5 ticks; the code's "observed 0.08 s" is in fact the release of the scenario's 60 ms hit | switches.py:51 | ROM bytes +0xe 0x1800; 0x0000dc44; probe `test_SW51_edge` (1 s hold: game scores 30 while held, ROM scores nothing until the release) | confirmed | medium |
| D-ADJ-89-SEM | AUTOFIRE AFTER LOCK: the new ball is auto-launched after a lock only when adj 89 = 1 (0x0100a074 `adj_get(0x59) == 1`) | serves a ball after every held lock, never reads adj 89 (the default 1 hides it) | megatron.py:654 | probe `test_ADJ89_autofire` | confirmed | low |
| D-ADJ-84/85-use, D-ADJ-85-SEM | device records carry an adj id; adj = 1 disables the device: 84 the orbit gate (0x0102c0cc), 85 the Optimus motor (0x00017134) | neither is read; optimus_mech.py says adj 85 "is not read by the code" | optimus_mech.py:18 | decompile FUN_0102c0cc `adj_get(*(short *)(param_1 + 2)) == 1`; adjustments.csv readers | code-proven | low |
| D-ADJ-69-use | MEGATRON M.B. VIRTUAL LOCK is read at 0x0100a278 (adj_megatron_m_b_virtual) and in deff 140 | not modelled (megatron.py docstring) | megatron.py:36 | adjustments.csv reader | code-proven | low |
| D-ADJ-82, 86, 46-use | MUDFLAP/SKIDS TARGET DIFFICULTY (0x0102e900), RESET WIZARD AT BALL START (0x010359dc), PLAYER COMPETITION (0x00017ef4) are read | never read (the game behaves as the default) | - | adjustments.csv readers | code-proven | low |
| D-ADJ-2, 3, 4, 7, 10-use | CUSTOM MESSAGE, TIME FORMAT, FAST BOOT, LANGUAGE, PLAYER LANGUAGE SELECT are read by OS / attract code | never read | - | adjustments.csv readers | code-proven | low |
| D-ADJ-25-use, D-CR-FGL | FREE GAME LIMIT: no `adj_get` call site with id 25 | `award()` caps free games per game at adj 25 (default 5) | credits.py:143 | probe `test_ADJ25_free_game_limit` (adj 25 = 0: 0 credits) | confirmed | low |
| D-ADJ-97, 98, D-SM-ADJSTEP | MUSIC / SPEECH VOLUME (-60..60) do not wrap; every other adjustment wraps | `step()` always wraps (unreachable anyway) | settings.py:97 | adjustments.csv wraps | code-proven | low |
| D-SW-45-disp, D-SW-45-STATE | captive ball +0xe 0x1fff: runs in every game state; `sw_captive_ball` [0x01033b14] adds audit 72 before any state test and returns 30 in attract | handled only when gf_state == 0 (nothing in tilt, bonus, attract) | switches.py:73 | decompile; ROM bytes | code-proven | low |
| D-SW-DEB | a closing counts after +0x1b passes and the switch must then stay open +0x1c passes (1-9 x 16 ms) before the next closing counts; a bounce drops the event | every MPF active edge runs the handler one tick later; no open-time filter | switches.py:68 | decompile 0x0000dc44 (DAT_00036968 / DAT_00036a08 counters) | code-proven | low |
| D-SW-3, 38-41-vpf (QA F16, open) | the eject and the four lock switches carry +0xe 0x1000: they post 0x6b and count toward the valid playfield | not in COUNTING_SWITCHES | os_layer.py:49 | 0x0000dc44 tail | code-proven | low |
| D-SW-15 | TOURNAMENT START: `sw_tournament_start` [0x0001a6fc] starts a tournament game (audit 0x12, flag 0xb → audit 0x27) | no handler | - | decompile | code-proven | low |
| D-SW-D19 | TICKET NOTCH: `leaf_fdb0` [0x0000fdb0] clears the dispenser's pending flag | no handler, no ticket model | - | decompile | code-proven | low |
| D-SW-DOOR | D20 is NOT USED; the door is read from the IO board's interlock bits | `s_coin_door_open` on D20 (MPF needs a switch) | hardware.yaml:22 | ROM record | code-proven | low |
| D-SW-ERR | each edge clears the switch's bit in 0x021100f4 (+0x10 & 2 / & 4), the switch-error list | not modelled | - | decompile 0x0000dc44 | code-proven | low |
| D-AF-13, 14 | slings: 64 ms on, then 192 ms dead and until the switch opens (0x040ddfe0, IO interrupt 0x000114b0) | autofire coils only in hw_vpx.yaml, with no recycle; no autofire or flipper rules for a P-ROC overlay | hw_vpx.yaml:94 | ROM bytes | code-proven | low |
| D-CR-DELAY | COIN INPUT DELAY: sleeps 1 tick adj-62 times, re-checking the refusal (0x00003ea8) each tick | one wait, then one `in_service` check at its end | credits.py:92 | decompile task_0x13_of_FUN_00019c40 | code-proven | low |
| D-CR-CUSTOM | CUSTOM pricing: a coin door and a ladder of up to 100 steps in NVRAM 0x02110808 | two machine vars (already a row in rom_differences.md, interim) | credits.py:73 | pricing.json `custom` | code-proven | low |

Not re-listed separately: F16 is covered by the D-SW-*-vpf rows above (still open). The other open items of
2026-11-25 are outside this scope.

## Unverifiable, and what agent A would need

| Rows | Why | For agent A |
|---|---|---|
| D-CO-15/16-pulse (flipper drive) | no flipper drive in the CPU code; the times are the waived emulator measurement (40.5 / 40.6 ms, hold 0.083 / 0.084). hw_vpx.yaml uses 40 / 0.083 for both, rom/coils.yaml 41 / 0.084 for the right one | the FPGA flipper logic (boards inventory: `partiel`) |
| D-AF-9/10/11 (pop recycle) | the pop table's dead time (16 ms) and debounce byte (16) are read, but MPF's autofire only exists in the VPX overlay, where the table moves the ball | none (a P-ROC overlay would need autofire rules from table 0x040ddfb0) |
| 28 D-SW-*-disp rows of OS / device switches (eject, trough, shooter, locks, Optimus up/down, coins, flippers, tilt, slam, coin door buttons) | MPF ball devices and switch handlers replace the ROM's per-pass debounce and handler tasks; whether they are equivalent is a question of timing, not data | the device task timings (serve / trough / lock, already in `ball_feed.md`) for the OS reviewer |
| D-CR-SNDS | credit / coin sounds 0x043 / 0x042 are observed; the code posts events 0x19 / 0x1a, whose hook was not traced | the event hook table entries of 0x19 / 0x1a |
| D-AUD-95 (counter 87 MODE START LIT) | no `audit_add` with a constant 0x57; probably the table at 0x040c7a1e (`audit_add(*(ushort *)(&DAT_040c7a1e + i))`) | the reader of DAT_040c7a1e and when it counts |
| D-AUD-166 / 0x02102cf8 | `error_log_user_8528` increments 0x02102cfc in a game and 0x02102cf8 / 0x02102d00 in attract; which one the audit shows is unclear | the special-lit record layout |
| Counters 59-64 | per-second time counters; the game keeps the seconds in `extra` (ball, game time) | none |

Severity: high, the service menu is not in the game (no adjustment, audit, install or reset can be reached; the
device and settings data behind it are right); medium, the audit formulas, the combo champion entries, the
Optimus target's opening edge; low, the rest.
