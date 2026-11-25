# QA 2026-11-26: sounds and rule-driven coils against the tf_180 decompile

Independent read-only review. Matrix: [matrix_sounds_coils.csv](matrix_sounds_coils.csv) (900 rows). Labels:
**code-proven** (decompile reading), **confirmed** (code + probe: the game's own traces, written by
`tests/scenario.py` for the 25 scenarios, compared with the reference traces, which only confirm the code).

## Scope

- **Sounds**: every sound call site of `rom/code/tf_decompiled.c` (712: `snd_play` [0x000251f4], `snd_play2`
  [0x00025250], `snd_play_arg` [0x00025224], `snd_play_after` [0x00025284] and its wrappers [0x00025340 / 0x00025364
  / 0x0002539c], direct `snd_resolve_call` [0x00025044], the fixed-call wrappers [0x0000ecfc-0x0000ed4c, 0x0002b7d8,
  0x0002b7e0], the repeat task 0x95 `leaf_6a20` [0x01006a20] and the delayed task `leaf_6a9c` [0x01006a9c];
  S001-S712), plus 121 calls the reference traces show from callers with no literal site (S713-S833), the sound call
  fields (F01-F07) and the music table (M01-M21).
- **Coils**: the game's rule-driven coil calls and tick constants (C01-C39): serve, eject, multiball feed, ball
  search, Optimus kicker and motor, Megatron lock, Allspark eject, knocker, shaker, gate, flippers. Leff flashers
  are in the lamps review; the devices' default_pulse_ms and eject timeouts in the devices review.

## Method

1. [probe_sounds_sites.py](probe_sounds_sites.py) parses the decompile into functions and lists every site
   (function, line, API, the literal call or expression), with the deff whose function it is, and the sounds of the
   code-decoded deff op lists (timing.json, instruction address `at`).
2. [probe_sounds_matrix.py](probe_sounds_matrix.py) gives each site its verdict: a fixed service call is missing (the
   game's service menu is silent); a call the deff's op list holds is played by display._media
   (game/tf/display.py:218), so match; a call the game names in a sound context is matched to that line; else
   missing; about 60 sites were read by hand (the MANUAL table in the script).
3. [probe_sounds_traces.py](probe_sounds_traces.py) counts each call in the game's traces against the reference
   traces per ROM caller function (the reference `caller` field mapped to the function heads); where the counts
   differ the row's verdict follows and the proof gives the per-scenario delta. Reproduce:
   `.venv/bin/python -m tests.scenario <s> OUT/<s>.jsonl` per scenario, `probe_sounds_traces.py OUT tr.csv`,
   `probe_sounds_matrix.py tr.csv matrix_sounds_coils.csv`. (8 scenarios end with an MPF `game.player`
   AttributeError after the trace is written; their traces are complete.)
4. Coils were read against rom/rules/modes/ball_feed.md (agent A, code) and the routines themselves; the shaker
   also against the game traces (coil 8: 207/207 bursts).

## Counts

| kind | match | differs | missing | extra | unverifiable | rows |
|---|---|---|---|---|---|---|
| sound sites (S) | 272 | 49 | 491 | 0 | 21 | 833 |
| sound fields (F) | 4 | 2 | 0 | 0 | 1 | 7 |
| music (M) | 12 | 9 | 0 | 0 | 0 | 21 |
| coils (C) | 18 | 8 | 1 | 0 | 12 | 39 |
| **total** | **306** | **68** | **492** | **0** | **34** | **900** |

Of the 491 missing sound sites: 208 are service / test beeps, 176 battle hit animations (SC2), 107 rule and
deff-branch sounds.

## Findings

| id | ROM does | game does | game file:line | rows | proof | sev |
|---|---|---|---|---|---|---|
| SC1 | each hit deff plays its hit call once: snd_play2(0x181, task+0x40) in deff_094 [0x010189a8]; likewise 0x195 deff_098, 0x1ab deff_102, 0x1d1 deff_106, 0x1ee deff_110, 0x201 deff_114, 0x21c deff_118, 0x236 deff_122 | twice at the same instant: from the op list (display._media) and from Battle.hit_media | battles.py:284; display.py:218 | S193 S213 S239 S263 S302 S330 S366 S381 | confirmed: 2x every hit (battle_starscream 32.31 s), ref 6 / game 12 etc. | high |
| SC2 | hit deffs call an animation function from a per-battle table by shots left (deff_094: 0x040c6a60[task+0x34]), each with its own sounds (0x182-0x18d, 0x196-0x1a3, 0x1ac-0x1c8, 0x1d8-0x1e1, 0x1f0-0x1fb, 0x202-0x213, 0x21d-0x22f, 0x239-0x251) | only the decoded animation's sounds, on every hit | display.py:218 | 176 "battle hit animation" rows; extra S141 S238 S309 S310 S358 S361 | confirmed: battle_ratchet 0x239-0x243 ref 11 game 0; 0x234 ref 1 game 5 | medium |
| SC3 | deff 91 plays by battle bit: 2: 0x171, 4: 0x172, 8: 0x173, 0x10: 0x174, 0x20: 0x175, 0x40: 0x176, 0x80: 0x177, else 0x170 [0x01022608] | 0x174 Autobot / 0x170 Decepticon | battles.py:71, 908 | S387-S394 | confirmed: 0x171-0x177 ref 24 game 0; 0x170 +17, 0x174 +10 | medium |
| SC4 | hint speech slot 0x02111f54 set by [0x01024fe8] (0x145) and [0x01025030] (0x14e, or random 0x148-0x14a Autobot / 0x14c-0x14d Decepticon), played via snd_play2 | never | - | S805-S809 | confirmed: 0x145 37, 0x149 21, 0x14d 43, 0x14e 28; game 0 | high |
| SC5 | ramp entrances play 0x273 [0x010337e8] / 0x272 [0x010338dc] every hit | timer only | switches.py:84 | S482 S483 | confirmed: ref 5 game 0 | medium |
| SC6 | jackpot / super animations play table-driven sound scripts (snd_play_after_user [0x0102fcb0]) | only the decoded variant's entries, some repeated | display.py:218 | S464 S465 S748-S796 S813-S818 S833 | confirmed: 0x080-0x099, 0x0cb-0x0f2 missing; 0x085/0x094/0x0d3/0x1e9/0x1ea +5..+7 | medium |
| SC7 | deff 77 repeats 0x0f4 0x2e times (task 0x95) [0x0100f3b4/0x010069d4]; task [0x0100f360] plays 0x0f5 then 0x0f6 | 0x0f4 10x; 0x0f5/0x0f6 never | megatron.py | S059 S117 S118 | confirmed: ref 46 game 10 | low |
| SC8 | initials entry (deff 32 [0x0103c840], deff 36 [0x0103e460]) plays the OS constants 0x04c/0x04d/0x04e (0x00030eac-0x00030eb0) | SOUNDS all None | high_scores.py:44 | S504-S507 S510-S513 | code-proven (constants read with rom.py) | medium |
| SC9 | deff branch sounds: bonus 0x076 [0x01000ffc], 0x05a deff 44, 0x27a deff 129, 0x2b1-0x2b4 deff 144, 0x09c/0x09f deff 60, 0x265 deff 126, 0x05d deff 50, 0x291 [0x0100415c], hit-deff tails, deff 88/89 0x132-0x138 | not in the decoded op list, no feature plays them | display.py:218 | 44 "no deff op list entry" rows | confirmed where exercised (0x076 2/0, 0x132 6/0) | medium |
| SC10 | wizard delayed speech 0x11a [0x01011078], 0x11c [0x01010b98], 0x120 [0x01010cd8], 0x124 [0x01011310], 0x11d-0x121 | 0x11c 13x, 0x11a 1x, others never | wizard.py | S126-S129 S799-S802 | confirmed: 0x11a -6, 0x11c +11 | medium |
| SC11 | attract: 0x045 on event 0x2d [0x01005f84]; 0x01e on event 0x62 [0x01006054]; 0x267 with 5,000 + leff 149 [0x010019c8] | none | attract.py | S054 S056 S030 | code-proven | low |
| SC12 | 0x24 only if not playing, then a volume fade [0x01006138] | always, no fade (F18 open) | game_over.py:72 | S057 | code-proven | low |
| SC13 | service / test beeps (0x009-0x00e, 0x010; switch test 0x00f) | silent except the power-off cancel 0x009 | settings.py:332 | 208 "service" rows, S484 S485 S610 S678 S679 | code-proven | low |
| SC14 | music table [0x000178b0], first true wins: Megatron A/D, wizard side, Optimus A/D, WMB, double scoring, fast scoring, battles, fallback | game: double/fast 0x80 > wizard 0x70 > Megatron/Optimus 0x60 > battles 0x40 | display.py:404; twobank.py:74; bumblebee.py:50; wizard.py:84-85; megatron.py:403; optimus.py:336 | M03-M10 | code-proven | medium |
| SC15 | entry 0 [0x010068e4] plays 0x31/0x34 whenever the battle can progress, before validation too | only after validation | optimus.py:388 | M01 | code-proven | low |
| SC16 | priority +0x10 / take-over +0x11; no-repeat memory +0x0e (34 calls) and speech ring +0x12 (29 calls) steer the pick [0x00025044, 0x00025b3c] | every call plays; uniform pick | os_layer.py:597, 607 | F03 F04 | code-proven | medium |
| SC17 | deff 126 sub 0x25f/0x265 [0x01006ae0], deff 126 0x264 | 0x25f +4, 0x264 +2, 0x265 -2 | energon.py:74 | S062 S463 S819 S820 | confirmed | low |
| SC18 | deff 140 lock call 0x294-0x299 [0x0100b7f0] | one fewer per Megatron scenario | megatron.py:572 | S827 S828 | confirmed 4/3 | low |
| CC1 | drain save re-serve (type 1): settle 31 ticks, then kick [0x0103b128] | SAVE_SERVE_TICKS 48 (Tron) | os_layer.py:68, 1288 | C03 | code-proven | medium |
| CC2 | outlane save (type 2): no settle [0x0103b128] | SAVE_EJECT_TICKS 39 | os_layer.py:58, 1677 | C04 | code-proven | medium |
| CC3 | MB feed: settle 31; next balls also wait task 0x16 (125 ticks); 6-tick polls; no fixed device hold [0x0103aba4/0x0103aa5c/0x0103ab6c] | MB_FIRST_EJECT_TICKS 51, MB_EJECT_TICKS 101, DEVICE_BUSY_TICKS 149 (Tron) | os_layer.py:61, 64, 67 | C08-C10 | code-proven | medium |
| CC4 | Megatron release: 0x13d + leff 25 + coil 3 (5 ticks) + 20 ticks per ball, equal 25-tick steps [0x0100a3b8] | coils 0.13/0.61/0.93/1.33 s | megatron.py:82 | C22 | code-proven | low |
| CC5 | Megatron entry: up to 3 coil-3 nudges of 4 ms, 93 ticks apart [0x0100a3b8 case 2] | none | megatron.py | C23 | code-proven | low |
| CC6 | knocker coil 24 64 ms, then 46 ticks before the next knock [0x00019420] | all knocks at once | os_layer.py:964 | C30 | code-proven | low |
| CC7 | Allspark coil 22 64 ms [0x0100a9b0] | trace logs 130 ms | allspark.py:31 | C28 | code-proven | low |

Rule sounds that match: slings, launch 0x056 (53/53), tilt 0x016/0x017, knocker 0x019, lanes, pops, energon,
2-bank, spinner, Bumblebee, Optimus 0x2a1/0x2a3/0x2aa, Megatron device 0x13b-0x13d, Allspark 0x157/0x158, coins,
ball saved, every decoded op-list sound. Coils that match: serve settle, timed plunger, ball search sweep, lost-ball
feed, Optimus kicker (15 ticks / 64 ms / 47 ticks [0x01033cfc]), Allspark eject (54 ticks), the device settles, the
shaker (207/207 bursts), trough and auto-launch pulses, flippers.

## Unverifiable, and what agent A must decode

1. The reader that plays the hint slot 0x02111f54 (SC4).
2. The starters of tasks 5fd0 (0x04a) and b5a0; the caller of start_leff_149 (0x267); the event handlers behind the
   tilt speech 0x052/0x053 (the game matches the traces, but no code site is cited) and the wizard speech
   0x11d-0x121.
3. The writers of the RAM calls 0x00033390, 0x00033392 and 0x0003379c.
4. The computed calls in deffs 28, 29, 30, 41, 48, 56, 60, 81, 84 and in the Blackout task 0x0101db34.
5. Which channel each stub call 0x001-0x008 stops.
6. Coils: the queued-pulse wait (FUN_00001f70 / 00003758: the search's auto-launch slot and the Megatron kick
   latency); the search gate, motor and task length (event 0xc / 0xd handlers); the Optimus motor limit (vtable
   +0xec); the orbit gate's time unit (leaf_2bc28(0x35384, 0x4d) [0x010332e4]); task 0x3c's starter; the later-serve
   extra 6 ticks; the autofire-after-lock delay; leaf_a374's caller; deff 140's flasher tasks (lamps review).

F18 stays open (SC12).
