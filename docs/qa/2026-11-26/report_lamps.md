# QA 2026-11-26: lamp conversion against the decompiled code

Independent read-only review. Scope (id prefix L): every lamp effect (leff 1-178 of table 0x040cfe00, agent A's
lift in `rom/rom_data/io/leff_ops/`, the packaged shows `rom/mpf_package/config/shows/lampfx_NNN.yaml`), every lamp
group (table 0x040d1510, 148 entries), the lamp engine (leff_start 0x00007c10, the compositor 0x000073cc, the rule
evaluator 0x000177b4), and the ROM's insert lamp rules with each insert of `lamps.csv`.
Matrix: [matrix_lamps.csv](matrix_lamps.csv) (412 rows), written by [probe_lamps_matrix.py](probe_lamps_matrix.py).
Probes: [probe_lamps.py](probe_lamps.py)
(`.venv/bin/python -m pytest -q -s -p no:cacheprovider docs/qa/2026-11-26/probe_lamps.py`).

## Method

- ROM, who starts a leff: every `leff_start(N)` and every list-3 lamp rule (`ram_00033dfc_user(obj, 3, cond, N,
  mask)`) in `rom/code/tf_decompiled.c`; every deff op `leff` in `rom/rom_data/dmd/deff_ops/`; and, with the ROM
  image, a scan of every BL to leff_start 0x00007c10 with r0 loaded by an immediate (`rom/tools/rom.py`
  `bl_callers` + capstone), which finds 3 call sites outside the decompiled functions: leff 17 in the replay task
  (0x0001c3bc), 18 in the tournament task (0x0001e084), 19 in the ticket task (0x0001b414). The same scan gives the
  leff kills (on 0x0000b7e4, the real leff kill; 0x0000b6fc "leff_stop" kills deff tasks) and the lamp groups used
  with a constant (the 28 lamp-group routines).
- ROM, what a leff draws: the lift (frames, brightness levels, GI, coil ops); for the leffs that draw from game
  state or from their caller's argument (+0x30), the leff function in the decompile.
- Game: every leff start in `game/tf` read by hand (`leff_start`, `lamp_rule`, `deff_media`, `set_media`,
  `UNCAPTURED`, and the deff captures' `timing.json` that `display.py:213` plays), the code leffs
  (`Lamps.leff_code`), and `tf.lamps.parse_show` run on every packaged show (lamp entries and pulses read back).
- Inserts: the ROM's list-4 lamp rules from a BL scan of the rule constructor 0x00017500 with r1 = 4 (7: 0x010024dc,
  0x0100b228, 0x01022854, 0x01023a84, 0x0102ede0, 0x01030f80, 0x01035ea8) plus the OS rules (0x0001801c,
  0x000182ac, 0x00019a0c, 0x01008528), their lamp tables read from the ROM, against the game's lamp rules
  (`battles.py:1065`, `energon.py:96`, `lanes.py:56`, `os_layer.py:513-531, 1050, 1626`).

Labels: **code-proven** (decompile reading), **confirmed** (code + probe).

## Counts

| Kind | rows | match | differs | missing | extra | unverifiable |
|---|---|---|---|---|---|---|
| leff | 178 | 80 | 80 | 17 | 0 | 1 |
| lamp group | 148 | 7 | 0 | 20 | 0 | 121 |
| insert (lamps 1-62; 63-80 in one row) | 63 | 26 | 19 | 18 | 0 | 0 |
| ROM lamp rule | 10 | 3 | 4 | 3 | 0 | 0 |
| engine | 13 | 2 | 9 | 2 | 0 | 0 |
| **all** | **412** | **118** | **112** | **60** | **0** | **122** |

The 80 matching leffs are mostly ones with nothing to draw: never started on either side, 0-tick leffs, flasher-only
shows (their pulses parse), and the 13 code leffs checked against their ROM function (13, 14, 39, 46, 54, 62, 70, 79,
87, 47, 55, 63, 71).

## Findings

Every differs or missing row falls under one of these lines (row ids given). Severity: high = a whole feature wrong
for the player; medium = visible on the playfield; low = small or rare.

| id | ROM | Game | Where (game) | Proof | Label | Sev |
|---|---|---|---|---|---|---|
| L-G01; leffs L-001 009 012 036 037 043 045 053 061 069 078 086 099 102 104 106 110 114 118 120 123 128 132 136 142 147 156 158 159 163 175 | each leff lights its lamps tick by tick (31 started leffs with lamps; attract leff 1: 30,221 lamp writes) | no leff lights or clears any lamp: `parse_show` reads colours with `'?([0-9a-fA-F]+)'?` and the shows write `"ffffff"`, so 0 lamp entries are read from all 113 shows (flasher pulses parse) | lamps.py:78 | test_L_show_lamps_parsed (0 of 113), test_L_attract_leff1 (layer empty, ROM 17 lamps at tick 5), test_L_leff_shows_in_game | confirmed | high |
| leffs L-011 020 027-029 032 040 048-050 056-058 064-066 072-074 080-082 088-090 097 098 100 101 124 139 141 143 145 148 157 160 164 166-169 176-178 | 45 started leffs draw from game state, from the caller's lamp (+0x30: pops 27-29, lanes 97/98/100/101, energon 139/141, 2-bank 143/145, Optimus 169), flasher patterns every 4 ticks (32, 40, 148, 157, 160, 176, 177...) or the GI (11, 20, 48-50...) | started, draw nothing (no show lamps, no leff_code); the rom_differences row "Lamp effects" already lists this as interim | lamps.py:463 | e.g. leff_097 0x0102dda4, leff_040 0x01024328; test_L_arg_leffs, test_L_rule_leff_no_draw | confirmed | medium |
| L-G13, L-R06, L-R07, L-I04-07, L-I23-26, L-I35, L-I48, L-I54 | rules write solid with 0x00007858 and off with 0x00007714, both clearing the flash bit | rules call lamp_on / lamp_off, which keep the flash bit: a lit Energon target and a completed battle insert keep flashing | energon.py:101, battles.py:1091 | test_L_energon_lit_solid (state 2, ROM 1), test_L_battle_completed_solid (2, ROM 1) | confirmed | medium |
| L-R06 | Energon rule 0x01030f80: in a multiball (0x0103096c false) all three inserts off | no multiball case: they keep flashing | energon.py:96 | test_L_energon_multiball ([2,2,2], ROM [0,0,0]) | confirmed | medium |
| L-G02 | 0x000073cc inverts the flash phase every 10 ticks (counter 0x0003148c = 10, once per 16 ms tick): 0.32 s period | FLASH_TICKS = 5: 0.16 s period | lamps.py:27 | decompile 7069-7072; test_L_flash_phase (0.08 s phases) | confirmed | medium |
| L-R04, L-I12 16 31 36 43 47 | 0x01023a84: a shot's X lamp (table 0x040c6f58) is solid while its multiplier >= 2 | only the roving 3X leff 39 lights X lamps | combos.py:104 | decompile 71909-71930 | code-proven | medium |
| L-R02, L-I29 57 58 | 0x0100b228: lamps 29, 57, 58 flash while a Megatron lock is lit (0x02111d50) and no mode runs | not drawn | none | decompile 54712-54750 | code-proven | medium |
| L-R07, L-I22 27 28 | 0x01035ea8 draws the 11 requirement inserts (table 0x040c7a14), including MEGATRON 27, OPTIMUS 22, SENTINEL 28 | only the 8 battle inserts are drawn | battles.py:1088 | table read from the ROM | code-proven | medium |
| L-R05, L-I20 21 | 0x0102ede0: 2-bank 21/20 flash (not hit) or solid (hit) outside multiballs and timed modes | not drawn | none | decompile 80783-80810 | code-proven | medium |
| L-I60-62 | bumper lamps are drawn only by the pop leffs 27-29 (lamp from table 0x040c74d4) | never lit | none | leff_029 0x0102d138 | code-proven | medium |
| L-G04 | leff_start conflicts on a shared lamp group (0x00009570) or coil group (0x0000611c); the new leff is refused if lower, or equal and the running leff lacks flags & 2; otherwise the conflicting leffs are killed | refused only by a strictly higher running leff sharing a flasher; lamp groups ignored; the lower leff keeps running | display.py:618 | decompile 7598-7631 | code-proven | medium |
| L-G07 | 29 leffs switch the GI (owner 0x000314c4) | no GI output | vpx_hardware.py:23 | leff_ops frames `gi` | code-proven | medium |
| L-G08; groups L-GRP-001-004 022 052 062 075 078 109 135-137 139 140 142 143 145-147 | a leff naming a lamp group gets the group cleared under it; groups used with a constant by leffs 34, 36, 76, 84, 95, 104, 147, 151, 176/177 and the lamp tests | no lamp groups (no rom_group_N tags; Lamps.group(N) is empty) | lamps.py:410, 474 | leff_start 7652-7655; group BL scan | code-proven | medium |
| L-044 052 060 068 084 085 151 154 | lamp rules start them: mode flasher patterns 44/52/60/68, wizard all-collected 84/85, a fade of lamp 30 (151), super spinner lit (154) | never started | none | rule list; leff_044 0x01027ffc, leff_151 0x0100252c, leff_154 0x010327bc | code-proven | medium |
| L-I15 19 34 39 40 44 | a battle's lit shots blink through its rule leff (106 ... 136): groups toggled every 3 ticks on a priority-8 layer | lamp_flash on the game image at the compositor phase | battles.py:1081 | leff_106 0x010188cc | code-proven | low |
| L-R01, L-I30 | 0x010024dc: leaf_18b4() returns 1, so lamp 30 flashes all game | lamp 30 only as the Bumblebee battle shot | battles.py:1081 | decompile 46976, 47418 | code-proven | low |
| L-I59 | lamp 59 is drawn by leffs 54/70, 177 (group 143) and 172 | 54/70 by code; 177 draws nothing | lamps.py:207 | lamp group 143 | code-proven | low |
| L-G05 | a leff without groups started again runs a second task beside the first | stops and restarts the running copy | display.py:635 | leff_start | code-proven | low |
| L-092, L-095 | lamp rules (conds 0x010314ac, side_choice_running) start and stop them | started at ball start only, never stopped by a rule | side.py:75 | rule list | code-proven | low |
| L-076, L-077 | 0x01011ed4 starts them for either side (open QA M8) | Autobot only | wizard.py:49 | decompile 58379 | code-proven | low |
| L-018, L-019 | started with the tournament (deff 0x1d) and ticket (deff 0x1e) awards | not modelled | none | BL scan 0x0001e084, 0x0001b414 | code-proven | low |
| L-002-008, L-R10, L-I02 | service menu and lamp tests (deff 3 + leff 2; start_leff_3-8); lamp 2 blinks with lamp 1 when a tournament is allowed | no tf_service mode file; lamp 2 never lit | os_layer.py:1429 | start_deff_3 0x0000ed90; 0x00019a0c | code-proven | low |
| L-G03 | plane 0 is shown 1 strobe pass, plane 1 two (0x000113fc): one-plane lamps at 1/3 or 2/3 (leffs 1, 37, 95, 147, 151) | on/off only | lamps.py:141, 598 | decompile 0x000113fc | code-proven | low |
| L-G06 | a rule is not evaluated when gf_state matches neither 0 nor its mask: its leff keeps running | rule leffs stopped in attract, end of ball and bonus | os_layer.py:485 | leff_start_user_177b4 | code-proven | low |
| L-G11 | looping leffs run their lead-in (up to 15 ticks) | the package keeps one cycle; the lead-in is left out | rom/tools/leff_package.py:5 | package docstring | code-proven | low |
| L-G12 | the lamp routines are 0x000077a0, 0x0000765c, 0x00007858, 0x00007714, 0x00007814 | docstrings cite Tron's [0x83f4], [0x82b0], FUN_01015094 | lamps.py:349-361 | decompile 7195-7380 | code-proven | low |

Still open from earlier passes and in this scope: M8 (L-076 / L-077).

## Unverifiable, and what agent A would need to decode

1. **121 lamp groups** are used only through game tables (the group id is read from a table, so r0 comes from a
   register at 98 call sites of the group routines). Agent A: one table listing every group's users (routine and
   table address), e.g. the shot tables 0x040c69f8 / 0x040c6a00 (battle rule leffs), 0x040c729c (mode leffs),
   0x040c66e4 (wizard).
2. **Leff 149**: `start_leff_149` 0x010019c8 (5,000 points, sound 0x267) has no BL caller and no aligned pointer to
   it. Agent A: find its caller (a function-pointer table entry, or dead code).
3. **L-G06**: whether the end of ball kills the rule-leff tasks by another path (task_kill of type 3). If it does,
   the game's stop at the end of ball is right.
