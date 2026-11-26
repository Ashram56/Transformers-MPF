# QA against the strict rule

The owner's strict rule of 2026-11-24 ([CLAUDE.md](../../CLAUDE.md)) and the audit method of MPF-Godot-Packaging
`agents/recreation.md` ("have the rules reviewed against the decompile": independent read-only reviewers, one
scope each, every finding proved; the review fixes nothing, the fixes follow from the reports). One folder per
pass.

## Pass of 2026-11-26: the MPF conversion against the ROM code

Owner, 2026-11-26: the QA matrix also covers the conversion to MPF (configs, generated config, shows, Python and
GDScript) and checks it against the decompiled code, not against the specs. Five independent read-only reviews,
each one matrix row per element of its scope (verdicts: match, differs, missing, extra, unverifiable):

| Scope | Matrix | Report | Rows | match | differs | missing | extra | unverifiable |
|---|---|---|---|---|---|---|---|---|
| MPF devices, settings, audits, pricing, service menu | [matrix_devices.csv](2026-11-26/matrix_devices.csv) | [report_devices.md](2026-11-26/report_devices.md) | 830 | 705 | 29 | 59 | 3 | 34 |
| Display: 155 deffs, deff engine, score screen, fonts, text formats | [matrix_display.csv](2026-11-26/matrix_display.csv) | [report_display.md](2026-11-26/report_display.md) | 182 | 89 | 40 | 18 | 1 | 34 |
| Lamps: 178 leffs, 148 lamp groups, inserts, lamp rules, engine | [matrix_lamps.csv](2026-11-26/matrix_lamps.csv) | [report_lamps.md](2026-11-26/report_lamps.md) | 412 | 118 | 112 | 60 | 0 | 122 |
| Sounds (every call site) and rule-driven coils | [matrix_sounds_coils.csv](2026-11-26/matrix_sounds_coils.csv) | [report_sounds_coils.md](2026-11-26/report_sounds_coils.md) | 900 | 306 | 68 | 492 | 0 | 34 |
| Rules: switch handlers, code runs, functional diagram, cited addresses, constants | [matrix_rules.csv](2026-11-26/matrix_rules.csv) | [report_rules.md](2026-11-26/report_rules.md) | 771 | 643 | 81 | 4 | 9 | 34 |
| **total** | | | **3,095** | **1,861** | **330** | **633** | **13** | **258** |

Each matrix is rebuilt by the `probe_*` script next to it (command in its report). Scores equal the ROM code on all
58 switch rows and 137 of 138 scenario marks; devices, numbers, coil pulses, pricing, deff priorities and the
package's deff and leff data match the code mechanically. The departures are in how the game plays that data.

### High

| id | What | Where |
|---|---|---|
| L-G01 | no leff lights a lamp: `parse_show` misses the shows' double-quoted colours (0 of 113 shows read) | lamps.py:78 |
| SC1 | every battle hit sound plays twice (op list + Battle.hit_media) | battles.py:284 |
| V-TXT1 | `%P1//S/%` plurals wrong ("SHOOT 11 SHOT", "3 COMBO") | media_bridge.py:35 |
| V-SC1 | main score font and row from 1,000,000 up (table 0x040c75d0) | score_screen.py:18 |
| D-SM-MODE / V003 | ~~no service menu~~ fixed (see Fixed); its icons and live tests are open (docs/rom_differences.md) | - |
| SC4 | ~~the hint speech slot 0x02111f54 is never played~~ fixed (see Fixed) | - |

Medium and low: the findings tables of each report. Fixes follow, high first, each with a regression test.

### Fixed (regression tests in [tests/test_qa_2026_11_26.py](../../tests/test_qa_2026_11_26.py))

| id | Fix | ROM |
|---|---|---|
| L-G01 | `parse_show` reads the shows' double-quoted colours: the leffs light their lamps (52 shows with lamps) | leff op lists |
| L-G02 | flash phase 10 ticks (FLASH_TICKS) | `0x000073cc` |
| SC1 | the battle hit call plays once, with its argument (Display.own_sounds keeps the op list from playing it again) | `0x010189a8` |
| V-TXT1 | `%P1//S/%` picks choice n-1 clamped to the last: "0 COMBOS", "SHOOT 11 SHOTS" | `0x0002fef0`, deff_044 op list |
| V-SC1 | main score font and row by value, table 0x040c75d0 (font 17 row 18 from 1,000,000) | `0x0102f11c`, `0x0102fa40` |
| R-F8, V-ENG2, L-G12 (citations) | the Tron 1.74 addresses still cited are replaced by tf_180 routines or marked inferred | see the commit |

| R-F1, SC5 | the ramp entrances play 0x273 / 0x272 on every hit | `0x010337e8`, `0x010338dc` |
| R-F2, SC3 | deff 91's call by the lit battle bit (0x170-0x177), not by side | `0x01022608` |
| L-G13, L-R06 | completed battle inserts and lit Energon targets solid (flash bit cleared); Energon inserts off in a multiball | `0x00007858`, `0x01030f80` |
| L-R04 | a shot's X lamp (12 16 47 43 31 36) solid at 2X or more, else off | `0x01023a84`, table `0x040c6f58` |
| L-R02 | lamps 29, 57, 58 flash while a Megatron lock is lit and nothing blocks it, else off | `0x0100b228`, `0x0100b0b8` |
| L-R07 | the 11 requirement inserts (27 Megatron, 22 Optimus, 28 Sentinel, the 8 battles) drawn from the requirements: solid completed, flashing collected | `0x01035ea8`, table `0x040c7a14` |
| L-I60-62 | the pop leffs 27-29 blink their bumper lamp 60 / 61 / 62 | `0x0102d138`, table `0x040c74d2` |
| L-151, L-154, L-084, L-085 | rule leffs started: 151 (all BUMBLEBEE letters), 154 (super spinner lit, flasher ramp of 14 patterns), 84 / 85 (all requirements completed, no multiball, flag 0x3c clear); 44 / 52 / 60 / 68 need nothing: their conditions return 0 in tf_180 | `0x010018bc`, `0x01032094`, `0x010327bc`, `0x010363b4`, `0x0103692c`; `0x0100c90c`, `0x0100e7c8`, `0x0102805c`, `0x0102a16c` |
| L-G06 | rule leffs follow their record's mode mask (not evaluated, so left running, outside it); end of ball kills those without task flag 0x100, ball start kills all | `0x000176ec`, `0x00019e44`, `0x00019d30`, rules/leff_rules.csv |
| SC4 | hint speech task 0xc6: set by the side choice, the side mode start and the Allspark shot; started by the left eject after the show tasks and by deff 141 at frame 10 (battle_ironhide, battle_shockwave and combos now match the reference's sounds 16 / 16) | `0x01025030`, `0x01024fe8`, `0x0102523c`, `0x01025294`, `0x010250f4` |
| CC1-CC3, R-F10 | ball feed timings from the code instead of Tron traces: save re-serve (type 1) after the 31-tick settle, outlane save (type 2) without one, multiball balls after the settle and the shooter's 125-tick task 0x16, 6-tick polls, no fixed device hold (the sounds trace now matches, 162 checks OK) | `0x0103b128`, `0x0103aba4`, `0x0103aa5c`, `0x0103ab6c`, `0x0103a7a4`, table `0x040d17fc` |
| Optimus motor | the motor's time limit 468 ticks and the 157-poll after-run going up, instead of the observed 7.65 s | `0x00016c88`, `0x00016830`, table `0x040c702e` |
| deff 140 | BALL LOCKED drops to priority 0x20 at tick 105 (adj 69 = NO) and the score deff 19 takes the DMD there (1.70 s after the start, ROM 1.73 s); leff 168 still stops at the deff task's exit, as its exit handler does | `0x0100b7f0`, `0x0100b90c`, exit `0x0100b5e4` |
| L-G04 | leff_start's conflict test: a running leff sharing a lamp of the new one's lamp group or a coil of its coil group refuses it when higher, or equal without flag bit 2; otherwise it is killed (a killed rule leff restarts when it can). Coil groups read from the ROM into rom/rom_data/io/coil_groups.json (rom/tools/coil_groups.py). Leff counts closer to the references in 5 scenarios, megatron_decepticon one more | `0x00007c10`, `0x00009570`, `0x0000611c`, tables `0x040d1510`, `0x040cf65c` |
| V-ENG4 | the 19 show deffs of deff_sequence_flippers_6480 (battle and multiball intros, 140, 149, 146, 43) end when one flipper is held and the other pressed, before their priority drop | `0x01006480`, `0x00006860`-`0x000068b4` |
| D-HS-COMBO | the high scores have the ROM's 17 entries in 5 lists: HIGHEST SCORES, AUTOBOT / DECEPTICON HIGHEST SCORES by the player's side, COMBO CHAMPION and BEST COMBO CHAMPION with adj 90-95; the ROM's default names | tables `0x040cf948`, `0x040cfc48`, `0x00018d54`, `0x01007508`, `0x01007578`, `0x0100279c`, `0x010028f4`, `0x010028c4`, `0x01002a7c` |
| SC2 | deff 94 (Starscream's hit) plays the animation of the shots left (+0x34, at most 8) or the final one, each with its own length and sounds, from agent A's op lists `deff_094__shotsN` / `__final` (`display.deff_variant`) | `0x010189a8`, table `0x040c6a60` |
| SC9 | the bonus at a multiplier above 1 adds task_sleep(4) and one counting page per multiplier (8 frames, 4 from 6X), then sound 0x76 before 0x79; deff 25 and the bonus award come that much later (scoring.jsonl 2X confirms 0x79 at tick 79) | `0x01000ffc`, `0x010014b8` |
| SC10 | the wizard side award deff 83 runs routine +0x34 of its side's table: speech 0x11c-0x121 / 0x11a (Decepticon), 0x122-0x127 (Autobot) at tick 63 through task `0x01006a9c` or after the animation, 0x119 queued after Autobot routines 6-11; op lists `deff_083__<side>_animN` run in the ROM code (`rom/tools/deff_variants.py`); wizard_all_hail_megatron speech counts now equal the reference | `0x01011750`, tables `0x040c6770` / `0x040c67a0`, `0x01006a9c`, `0x00025364` |
| D-SM-MODE | SELECT opens the service menu (mode `tf_service`, `game/tf/service.py`): title, the 17 menus as 0xeb3c builds them, the adjustment editors (edit, store, default marker), the audits, the 13 installs and the resets; texts from agent A's walk of the ROM code (`rom/rom_data/settings/service_screens.json`); what it does not draw yet is a row of docs/rom_differences.md | `0x0000eb3c`, `0x0103f960`, `0x0000ed90`, `0x0104b3e4`, `0x0104b244`, `0x0104b584`, `0x0104b728`, `0x0104196c`, `0x01041b10` |
| SC16 (pick) | a call's sample pick skips the samples of its no-repeat memory (+0x0e, 34 calls) and of the speech ring (the last 9 speech samples, 29 calls), as snd_resolve_call does; the voice priority and take-over (+0x10 / +0x11, snd_start_sample) stay open | `0x00025044`, `0x00025b3c`, `0x00025a14`, `0x00024ae4` |
| V050, V066, V071, V072 | deff 50 by shot (+0x30) and deff 66 / 71 / 72 by their random video take the length, sounds and leffs of that run's op list (`deff_variant`); the frames stay the packaged run's (docs/rom_differences.md) | `0x010237ac`, `0x0102ad30`, `0x0100d214`, `0x0100d550` |
| V097, V101, V105, V113, V121 | 0 shots left: "SHOOT LIT SHOT" in the shots slot; Devastator state 1 "SHOOT R. ORBIT" (msg 0x645) | `0x0101f580`, `0x01016d7c` |
| V124, V125 | deffs 124 / 125 last 156 / 142 ticks, 0x13f at tick 70, from their op lists (were 1.0 s / 2.0 s inferred) | `0x01030b94`, `0x01031038` |
| L-R05, L-I20 21 | the 2-bank lamps 21 / 20 flash outside multiballs and timed modes, off in them (the player mask that would make them solid is only ever cleared in the code) | `0x0102ede0`, `0x0102e994`, table `0x040c7568` |
| L-G07 | the 30 leffs whose code switches the GI (owner 0x000314c4) turn it off and on at their op lists' ticks, and give it back at their end; the VPX bridge reports GI string 0 at 0 while it is off | leff_081 `0x010119d8`, leff op lists frames `gi` |
| L-G08 | a leff with a lamp group owns the group's lamps (off) from its start, as leff_start clears them in the leff image and flash mask | `0x00007c10`, `0x000084cc`, `0x000086d4` |
| D-AUD-11 | TOTAL EARNINGS is the units counter 7 times the unit value of the pricing selected now, in its money format ("USD 3.25" for 13 units at USA 10), was coins x 25 cents | `0x00026e7c`, `0x00026f74` |
| V-ENG5, SC14 | rule and music order: Megatron, wizard side, Optimus, WMB above double scoring, fast scoring, battles | `0x000178b0`, FUN_00017834 |
| R-F4 | validation sets game flag 0x10 (event 0x6a hook); the playfield-valid tests read pf_valid instead of the made-up flag 0x1c | LAB_010060a4, `0x0000d8c4` |
| R-F5 | no 1 s Optimus time gate (the lockout is task 0x54) | `0x01025de4`, `0x010262f0` |
| D-AUD-2, 13, 16, 22, 24, 27, 47, 72 | percentages over paid plays (c17); audits 13 and 72 are 0; average score per player, /10 x 10 | `0x00026c94` ... `0x00026c3c` |
| D-SW-51-EDGE | the Optimus target's handler runs on the opening edge (+0xe 0x1800) | `0x0000dc44` |

| R-F3, R-F11 | right orbit: token 7, task 0x47 (plunge, center lane), token 9 cancel the shot in that order; the 187-unit timers last 2.99 s (16 ms OS loop); gate held 93 ticks | `0x01033530`, `0x0002bd48`, `0x0102c0a8` |
| SC8 | initials entry sounds 0x04c / 0x04d / 0x04e | `0x0103c840`, words `0x00030eac`-`0x00030eb0` |
| D-ADJ-25, D-ADJ-89 | no free game cap (no reader of adj 25); the ball after a lock is auto-launched only when adj 89 = 1 | `0x0100a074` |
| V-TXT3, V-SC6 | `%i` printed as a number ("3X BONUS"); players not up drawn at level 3 | `0x0002fef0`, `0x0102f200` |

All 24 trace scenarios compare the same or better after these fixes (161 checks OK; the sounds and switches
scenarios match further: 29 of 29 and 55 of 87 sound events in order, before 28 and 51).

### Open after the fixes (2026-11-26)

- ~~V-SC2, V-SC7, V-SC8, V-SC9~~ fixed 2026-11-26 (after agent A's answer): the three counters count one per
  tick (0x0102f9ec on event 0x21, rom/rules/event_hooks.csv), cleared by event 0x13 at the end of ball_start
  [0x00019e40] -> [0x0102f958], award value from event 0x4d [0x0102f998], combo from [0x01002f0c]. The score
  blanks 7 of 14 ticks after 0x3e idle ticks (sweep once the playfield is valid), the award fades over 0x1a
  ticks, the combo texts slide (tf/score_screen.py StatusCounters; tests/test_qa_2026_11_26.py
  test_score_status_counters). Deffs 26 and 40 draw the same panel, refreshed every tick (V-SC11).
- ~~SC16 (voices)~~ fixed 2026-11-26: snd_start_sample [0x00024ae4] voice allocation. Each sample's script
  bytes 1-2 (voice mask, voices taken; rom/rom_data/sound/sample_voices.csv from rom/tools/sample_voices.py);
  a playing sample's voices are taken over when its call's priority (+0x10) is lower, or equal with its
  take-over flag (+0x11); free voices first, then the slot that has played longest; else the sample does not
  start (os_layer._voice_plan, sound_refused). The hint task logs each refused try (allspark_energon: sound
  events match up to #57, was #20); the battle hit sound plays from the hit deff's first run, after the
  Allspark warning (battle_blackout: #15, was #11). Test test_sound_voices.
- ~~Deff variant frames~~ fixed 2026-11-26: the 73 variant op lists are rendered from the code
  (rom/tools/deff_package.py --ops-variants into deffs/deff_NNN/variants/<name>/); gen_media writes one slide
  per variant (media_data "variants") and media_bridge plays the variant's slide.
- ~~V010, V015, V017 (credit line)~~ fixed 2026-11-26: deff_017_insert_coins [0x01000000] draws the credit line
  (msg_get_user_44a4 [0x000044a4]) and, every other 15-tick frame, PRESS START (0x31a) when leaf_19988
  [0x00019988] allows a start, else INSERT COINS (0x31b): two live slots (gen_media credit_slots).
  V010/V013/V015/V017 and every deff whose code has no priority drop keep their priority to the end
  (display.deff_holds: hold 0).
- ~~V002 (volume)~~ fixed 2026-11-26: coin-door MINUS / PLUS outside the service menu [0x0000f008]: deff 2 (task
  0xb [0x0000eeb0], with 0x01e in attract by on_event_62 [0x01006054]); with deff 2 up the volume
  (0x02110250, 0-0x3f, 0x28 [0x00025fb0]) steps by one; BACK takes deff 2 away.
- ~~V014~~ fixed 2026-11-26: in attract both flipper buttons start deff 14 [0x00026608]; one stops it.
- V001 attract pages: asked agent A for the page table 0x00030d10 and a lift of each page with real state.
- Low rows fixed 2026-11-26:
  - ~~CC6~~ knocker [0x00019378 / 0x00019420]: a queue served one at a time on event 0x21, coil 64 ms then
    0x2e ticks, sound 0x19 (adj 35) then 0x1f ticks.
  - ~~R-F6~~ deff 44 [0x0102de6c]: 0x05a at frame 25 when a multiplier is lit.
  - ~~SC7~~ deff 77 [0x0100f3b4]: anim 0 retries 0x0f4 through task 0x95 [0x010069d4] (0x2e tries, each logged);
    else task [0x0100f360] plays 0x0f5 after 0x8c ticks (0x4d for anim 3, which then chains 0x0f6).
  - ~~SC11~~ event 0x19 (credit added) sets flag 0x12 [0x01005ebc] (the game set flag 47); event 0x2d
    [0x01005f84] -> play_sound_045 [0x01005f00]: 0x045 when that flag is set, no credit and a partial credit.
    0x267 with 5,000 and leff 149 [0x010019c8] has no caller (no BL, no literal, no PC-relative ADD in the game
    code): dead code, nothing to play.
  - ~~SC12~~ task 0x9b [0x01006138]: 0x24 only if it does not play; at sample 0x28f's script cue (op 0x0d,
    snd_op_set_8c [0x000245a8], 26.19 s) voice 0 fades (1 step per 2 ticks to 0x100, start 0 inferred) and the
    sample stops at its end.
  - ~~SC13~~ service beeps: BACK 0x009, MINUS 0x00a, PLUS 0x00b, SELECT 0x00c (0x0000ecfc-0x0000ed2c), reset
    done 0x00d (0x0000ed3c) [0x0103f960] [0x0104196c].
  - ~~SC15~~ music entry 0 [0x010068e4]: battle music whenever the battle can progress, validation not needed.
  - ~~SC17~~ deff_126_0_more_sub [0x01006ae0] (os_layer.speech_once): 0x265 at deff 126 frame 15 (flag 0x30,
    else 0x264) [0x0102eaec], 0x25f from Energon task 0x97 (flag 0x47) [0x01030984]; at most twice a game, not
    while task 0x96 runs, in a multiball or on the last ball; the flag only when the sample started (snd_play's
    return, [0x01006b5c]).
  - ~~SC18~~ deff 140 [0x0100b7f0]: the side's lock call plays its samples in order (per-player count,
    snd_play2 [0x00025250]), the third lock chains the call's last sample (snd_play_after [0x00025284]).
  - ~~CC4~~ Megatron release [0x0100a3b8 case 3]: coil 3 one tick after each ball's 0x13d, 25 ticks per ball.
  - ~~CC5~~ lock entry [0x0100a3b8 case 2]: up to 3 coil-3 nudges of 4 ms, 0x5d ticks apart, while the jam
    switch 42 is closed or the device count moves.
  - ~~V014~~, ~~V002~~: above.
  - Batch 2 (2026-11-26):
    - FMT6 audits [0x0002700c]: value, then "p% OF GAMES" (q digits before) over audit 0x1d, two lines in
      font 8 from y 0x16 (draw_lifetime_s [0x01046598]).
    - adj 84 / 85: the orbit gate (vtable +0x24 adj_is_1_2c0cc) and the Optimus motor (+0x74 [0x00017120])
      do nothing when their adjustment disables the device.
    - Two-bank difficulty adj 82 [0x0102e8f8]: the first level, +1 per start [0x0102e9c0], 5 + 2 x level
      targets (12 at most).
    - Switches 3 and 38-42 count for the skill shot windows (event 0x6b [0x0000ddf8]).
    - M8: the side qualify leffs 77 / 76 for both sides [0x0100ff80] [0x0100ff58]; a requirement poke asks no
      evaluation.
    - Skill-shot window ends: the rules are evaluated (tasks 0xb2 [0x010314d8], 0xb4 [0x0103173c]).
    - Leff end: leff_free_7df0 [0x00007df0] sets 0x31488 when the leff had a lamp or coil group, and the rules
      hook [0x01006240] then evaluates the whole leff rule list (list 3) unless task 0x29 runs. The game only
      retried refused leffs: wizard_multiball now starts 77 / 76 when leff 96 ends, as the ROM does.
    - Battle arrows: each battle's rule leff (106-136, battles.md 8) owns the orange arrows and toggles the lit
      shots every 3 ticks (lamp_bit_flash_78dc [0x000078dc]); Ratchet flashes the doubled ones and holds the others.
    - ~~D-SW-45~~ sw_captive_ball [0x01033b14]: audit 72 in every state, tilt and attract included.
    - ~~D-CR-DELAY~~ task_0x13 [0x00003f00]: adj 62 single-tick sleeps, the coin dropped at the first refusal.
    - D-SW-DEB, D-SW-ERR, D-SW-15, D-SW-D19: rows in rom_differences.md (MPF limit / not modelled hardware).
    - Flippers: decoded by agent A (table 0x040cf590, io_isr [0x000114b0]); the waiver is no longer used.
    - ~~R-F9~~ the leff rules run in the ROM's list order: all priority 0, each registration at the head
      [0x00017580], the constructors run last first [0x0002c0c8] (`rom/tools/rule_order.py`,
      `rom/rom_data/rules/leff_rule_order.json`); the made-up `order=` keys are gone.
    - ~~R-F7~~ leffs 103 and 170 already pulse 18 x 3 and 17 times from agent A's decoded shows; leff 40
      [0x01024328] (Allspark banked) now pulses coil 32 for 100 ms every 4 ticks with the 14 patterns of
      0x040c6ff4 while the playfield is valid and ball search is off.
    - ~~L-R01~~, ~~L-I30~~ arcade_lamp_rule [0x010024dc]: return_one_18b4 [0x010018b4] is 1, lamp 30 flashes all
      game; the battle arrows leave it alone.
    - ~~L-092~~, ~~L-095~~ leff rules: 92 while the skill shot task 0xb2 runs (check_task_b2_314ac [0x010314ac]),
      95 while the side choice runs (side_choice_running [0x01033e84]); the window start requests the rules
      [0x01031518].
    - ~~L-076~~, ~~L-077~~: fixed with M8. L-018 / L-019 (tournament and ticket awards): not modelled
      (rom_differences.md).
    - ~~V084~~, ~~V089~~ the priority drops at the first 0x20 op of the final run (deff 84 tick 162, deff 89 tick
      140, deff_prio_set through [0x010305a0]): wizard_all_hail_megatron deff and leff starts now match.
      ~~V047~~ deff 47 raises its own priority to 0x80 at frame 0x16, tick 44 (deff_prio_set_own_20e84
      [0x0102c6dc]); the game takes every such step from agent A's op lists (display.py PRIO_STEPS).
    - ~~V-SC11~~ the deffs that draw the status panel (draw_way_palette_identity_2f200 [0x0102f200], deffs 26 and
      40 too) refresh it every tick instead of every 0.25 s, sent only when it changed.
    - V005, V007, V011, V012, V016, V018, V034-V037, V033, V-SC4, V-TXT2, L-G03, L-G05, L-G11: rows in
      rom_differences.md (machine states and tournament / ticket hardware not modelled, MPF limits).
    - ~~SC6~~ the animation sound tables (frame_sound_step_2fcb0 [0x0102fcb0]): agent A's
      `deff_anim_tables.csv` gives one op list per animation; the game plays the chained 0x1f entries
      (snd_play_after_if) after the running sample ends, picks the Optimus hit animation by hit number
      [0x010262f0] (reset at the battle start [0x010261cc]) and the Megatron ones from the index 0 up.
      0x092 and 0x0df-0x0e1 stay unplayed: no caller in the code.
    - ~~V129~~ deff_129_double [0x01003c5c]: 0x27a, then at tick 20 the 0x27b samples 0, 1, 2, 0 each queued after
      the previous one (snd_play_after_handle_2539c [0x0002539c]); the trace-timed list is gone.
    - ~~L-I59~~ leff_177 [0x01027024] (Optimus battle ready): the super-lit loop of leff_085 on coil group 57 (31, 25).
    - Deff 65's animation index: task_create clears the task block (memset 0x68), and [0x01029bf4] sets +0x38 only
      for deff 66; deff 65 runs animation 0, as the game does (agent A's deff_anim_tables.csv note is for 66).
    - ~~CC7~~ the Allspark eject is coil_pulse_now(22, 64 ms) [0x0100a9b0] (the traces log 130 ms).
    - ~~D-ADJ-69-use~~ adj 69 VIRTUAL LOCK = YES: the Megatron device keeps no ball (adj_get(0x45) == 1 [0x0100a278]);
      the lock counts and the ball is kicked back.
    - ~~D-CR-SNDS~~ the credit sounds from their hooks: event 0x19 [0x01005ebc] 0x043 and flag 0x12, event 0x1a
      [0x01005ed8] 0x042, event 0x51 (service credit, [0x0000f008]) [0x01005eec] 0x044 (it was missing).
    - D-AUD-47 (already fixed, [0x00026c3c]), D-AUD-FMT6 (FMT6 above), D-SW-45-disp / -STATE (D-SW-45),
      D-SW-51-disp (D-SW-51-EDGE), D-ADJ-25-use / D-CR-FGL (D-ADJ-25), L-I04-07 / L-I23-26 / L-I35 / L-I48 /
      L-I54 (L-G13, L-R06), CC2 / CC3 (CC1-CC3): fixed under the grouped ids.
    - D-SW-DOOR, D-CR-CUSTOM, L-002-008, L-R10, L-I02: rows in rom_differences.md.
    - ~~M12~~ (2026-11-25) the jackpot speech samples come from the mode's counter, not a random pick: deffs 71 / 72
      (0xca / 0xd2, DAT_00034db8, back to 0 below 10 jackpots [0x0100c430]), 77 / 78 (0xe4 / 0xf7, DAT_00034e2c, 0 on
      the Megatron shot, the tenth jackpot, the third double and the super [0x0100e29c]), 59 (0x7f, DAT_00035308,
      0 at the start and the super [0x01027b74]); deff 65 plays sample 0 (its +0x34 is never set).
    - ~~F14~~ (2026-11-25) slam_tilt [0x0001d534] has no game test: in attract too, deff 24, leff 12, 0x018 and the reset
      task 0x39; the service menu (state & 0x100) and a running task 0x39 stop it.
    - ~~F16~~ (2026-11-25): the slings 26 / 27 [0x01033104] [0x010331a4] and switches 3, 38-42 count (above).
    - ~~F17~~ (2026-11-25) ball_search_tick [0x00017c60] has no multiball test: the search no longer waits for the
      multiball save and grace (no trace changes). The count reset through the switch-timeout object 0x31608
      [0x00017d60] stays approximated by the playfield switches (doubtful in the report).
    - P19 (2026-11-25): row in rom_differences.md (no switch fails on virtual or VPX hardware).
    - ~~M14~~ (2026-11-25) task ids from the code: Megatron end tasks 0xbb / 0xbf with their totals shown by 0x8b /
      0x8c [0x0100c790] [0x0100e61c]; Optimus Decepticon intro 0x72 [0x01029a08]; side mode done deff 84 task 0x7a
      [0x01010174], total deff 85 as show 0x7b when completed and, at the end of ball, task 0x8f waiting for the
      display (0x753 ticks, [0x010102f4]); no total when it is 0 [0x01010330].
    - ~~M11~~ (2026-11-25): adj 89 and adj 69 both read now (D-ADJ-89, D-ADJ-69-use).
    - ~~R-F12~~ diagram node MSH now gives the code's min(10,000 + 10,000 x started + 5,000 x hits, 75,000)
      [0x0101fd34].
  - Row "Rule leff restarts" removed: not a departure. The rules are evaluated by the poll hooks of task_sleep
    [0x0000acfc] -> [0x0000b648] -> event 0x4a [0x01006240], in the context of the task that sleeps; when it is the
    rule leff itself, task_group_running_b780 [0x0000b780] skips the current task and the rule calls leff_start
    again, which refuses it (iVar7 == task_current, [0x00007c10]). The leff keeps running: the second
    leff_start in the traces (177 at optimus_autobot.jsonl 33.36 s, 47 at 71.34 / 71.89 s) is a refused call.
  - Row "Battle hit deff sounds" fixed: each hit deff's speech plays its sample +0x44 (2 below the animation index
    +0x34: 9 or 10 - shots left, 0 past the call's count) after 0x5d ticks (0x7d for deff 94, none on its last hit;
    snd_play_delayed_6a9c [0x01006a9c] or a child task that dies with the deff), Blackout chains 0x1c4 / 0x1c5
    [0x0101db34] (battle_blackout: both 0x1c4 at their times), Devastator 0x1e4 [0x01017068], 0x1f ticks on its
    last hit.
  - Nothing left open in either pass: every finding is fixed from the code or has its row in rom_differences.md
    (2026-11-26, 171 of the trace checks OK, the rest the known sample-pick and timing rows).

## Pass of 2026-11-25

Three independent read-only reviews, each with the decompile, the ROM and the game in its test harness:

| Scope | Report | Probes | Findings |
|---|---|---|---|
| OS layer and game flow | [report_os.md](2026-11-25/report_os.md) | [probe_os.py](2026-11-25/probe_os.py) | 18 (F1-F18) |
| Modes and multiballs | [report_modes.md](2026-11-25/report_modes.md) | [probe_modes.py](2026-11-25/probe_modes.py) | 15 (M1-M15) |
| Playfield scoring | [report_playfield.md](2026-11-25/report_playfield.md) | `probe_playfield_*.py` on [qa_base.py](2026-11-25/qa_base.py) | 20 (P1-P20) |

Run a probe file from the repository folder: `.venv/bin/python -m pytest -q -s -p no:cacheprovider
docs/qa/2026-11-25/probe_os.py` (the playfield ones need `--rootdir docs/qa/2026-11-25`). A probe prints what
the game does next to what the ROM does; after a fix it prints the ROM's value. The probes were written against
the game before the fixes; the regression tests are in [tests/test_qa_2026_11_25.py](../../tests/test_qa_2026_11_25.py).

### The strict rule, mechanically (`python tools/check_strict_rule.py .`)

| Check | State |
|---|---|
| Rule text in CLAUDE.md | passes |
| `docs/boards_inventory.md` | **passes** since 2026-11-26: the ARM game program is `complet` (every function named from its code, the flipper drive decoded); the two Xilinx CPLDs are left undecoded by the owner's decision ("On ne les décode pas") |
| Captured data | **passes** (was 266 failures): the flipper times in `coils.csv` are decoded from the code since 2026-11-26 (table 0x040cf590 run each 1 ms by io_isr [0x000114b0]: 40 ms pulse, hold 1 ms on / 11 ms off, `rom/tools/flipper_drive.py`); the owner's waiver of 2026-11-25 is no longer used. Decoded from the code by agent A on 2026-11-25: all 153 deffs (the 38 game-state ones per state, `rom/tools/deff_variants.py`), all leff shows, 33 coil times, every adjustment value text ([pinmame_waivers.md](../pinmame_waivers.md)) |
| Functional diagram | passes: [functional_diagram.md](../functional_diagram.md), assembled after the fact from A's specs, each address checked by `tests/test_functional_diagram.py` |

### Fixed in this pass (each with a regression test)

| id | What | ROM |
|---|---|---|
| F1 | the right orbit collects a lit extra ball (deff 54) | `0x01033488` → `0x01007b74` |
| F2, F3 | special lit with lamp 53 and deff 55, collected at the right orbit with deff 56; extra ball lit shows deff 53 | `0x01008528`, `0x01008684`, `0x01007b40` |
| M1 | every multiball keeps scoring in its 218-tick end window (wizard: 312) | gates `0x0100be84`, `0x0100dec0`, `0x010276e0`, `0x01029754`, `0x01036590` |
| M2 | Megatron Decepticon progress saved per player with adj 88 YES | `0x0100e0bc` |
| M3 | Megatron Autobot doubles do not time out before M = 3 | `0x0100c10c` |
| M4 | Optimus Decepticon super x the center lane multiplier | `0x01029bf4` |
| M13 | the never-set grace flags 0x26 / 0x2a are no longer set | grep: only `game_flag_clear` |
| P1 | BONUS HOLD and BONUS X HOLD last one ball; no held bonus stored when tilted | `0x01000d58`, `0x01000f68` |
| F13 | the OS-layer files cite tf_180's routines, not Tron 1.74's: about 110 citations (bracketed addresses, `FUN_` names, RAM and the power table) re-cited by matching each Tron routine of Tron-Legacy-LE-ROM-Decryption `code/tron_game_decompiled_v2.c` against the tf_180 decompile (normalised bodies), ties settled by reading both; still marked Tron: the score-display music rules (Tron 0x0100f594 / 0x0100f5c8), no tf_180 match yet (`any_multiball` cites tf_180's `0x01006704`) | e.g. serve_ball `0x0103b39c`, score_add `0x0001caf0`, multiball_start `0x0103aec0`, end of ball `0x00019e44`, slam `0x0001d534` |

| P2 | the lit shot multiplier is raised before the shot's combo award (FUN_010237ac first in every shot handler) | `0x010237ac`, `0x01033824` |
| P3 | the skill shots end on any 3 distinct switches posting event 0x6b (slings and pops count) | hook `0x010313cc` |
| P4, P5 | mystery item 10 weight 0 only with a lit multiplier or the roving 3X; double and fast scoring starts clear flag 0x13 | `0x01023494`, `0x010039a0`, `0x01004394` |
| P6, P12, P16 | double scoring: the countdown never pauses, 0x285 once per run at the first count in 5..10, 125-tick tail, ADD MORE TIME in the tail revives it | `0x010038dc`, `0x0100393c`, `0x0100396c`, `0x01003a8c` |
| P7, P8, P9 | fast scoring: pops and top lanes hold it 156 ticks; 11 x 6-tick steps; +1,000 on a cycle's first target only, leffs 144 / 145, +10 counts on the completing hit; the tails are not timed modes | `0x01032f8c`, `0x01004220`, `0x010047b8`, `0x010067bc` |
| M5, P10, P11 | the center lane / Optimus lockout is task 0x54 (62 ticks, started by sw 51); sw 51 ignored while 0x54 or 0x4e run; the fast award and double sounds in every handler but sw 6's | `0x01033d3c`, `0x01033b3c`, `0x010332e4` |
| F4, F5 | a held plumb bob warns every 62 ticks then tilts (task 0x2e); the bob counts in the end of ball and a tilt there removes the bonus | `0x0001dc58`, `0x0001dc14`, `0x00019e44` |
| F6 | an equal-priority deff replaces the running one only when its flags & 3 | `0x00020498` |
| F10 | the end of ball waits for the longest flag-0x2000 task, at most 937 ticks | `0x00019e44`, DAT_00033324 |
| F11 | the Megatron lock entry adds a bonus count and resets the ball search | `0x0100a31c` |
| M6 | the super-lit leffs 47 / 55 / 63 / 71 pulse their coil group every 8 ticks (a higher leff owning the flashers wins); Megatron's run by their lamp rules | `0x010286f8`, `0x0102a83c`, `0x0100d038`, `0x0100ef64`, `0x0100d004`, `0x0100ef30` |
| M7 | ADD-A-BALL offered while a multiball flag is set or in the first 156 ticks of its end task; award with ball save 312 / grace 187 | `0x01006760`, `0x01024a20`, `0x01024a60`, `0x0100c7e8` |
| M9 | Starscream's lit pair moves each counted second with fewer than 6 shots left, unless a ramp entrance in the last 93 ticks | `0x01017824`, `0x010337e8`, `0x010338dc` |
| F7 | each decoded deff holds for its own tail (1, 2 or 10 ticks), read from agent A's op lists | `0x0103058c`, `0x0002108c` |
| F8 | ball save: ends when fewer than 7 ticks are left (adj 38 = 5: 312 ticks) | `0x00017a28` |
| P13, P17, P18, P20 | skill shot second lane lamp 50 / 49; spinner sample index reset each ball; deff 124 arg 0 before the new bit; item 4 text capped at 25 | `0x010335d0`, `0x0103361c`, `0x01032484`, `0x010309a4`, `0x01000f18` |
| F9 | match: the number steps by 10 past the players when the rate is reached; 0x072 / 0x073 at frame 60 of deff 38, the award after frame 68 with 0x074 and 24 more frames; MATCH OFF shows no deff 38 (tournament not modelled) | `0x00019668`, `0x0100820c`, `0x00019874` |
| P14, P15 | lanes rotate on every flipper press but in gf_state & 0x311, killing the group's leffs first; a lane completion always shows deff 44 with FUN_010236e8's result | `0x01032d5c`, `0x0102db28`, `0x010236e8` |
| F12 | tilt() and the multiball task validate the playfield | `0x0001db40`, `0x0103aba4`, `0x0000d8c4` |
| M10, M15 | the lock re-arm copies every player's count (ROM quirk kept); deff 139 gets the locked count | `0x0100af0c` |
| F15 | no change needed: the ball save does not survive a tilt in the ROM, as in the game. Approved capture [tilt_ball_save.jsonl](../../rom/rules/traces/tilt_ball_save.jsonl) (waiver row in [pinmame_waivers.md](../pinmame_waivers.md)): tilt 2.87 s, drain 3.64 s inside the save, end of ball, next ball's save 6.57 s, no re-serve | `0x0001db40` |
All 24 trace scenarios give the same comparison before and after these fixes, except two coil burst counts that M6 moves (megatron_decepticon, optimus_autobot); the trace replay runs at the code's 16.0 ms tick, scaled to the traces' 16.15 ms (counted on code-timed spans; the 16.26 ms used before drifted 0.3 s over a battle and gave battle_blackout an extra bonus).

### Open (proved, not fixed yet)

High first. Each line's detail, proof and game line are in its report.

| id | What | Sev |
|---|---|---|
| P19 (row; F14, F16-F18, M8, M11, M12, M14 fixed) | smaller differences (lengths, ids, args, sample picks, rare adjustments) | low |

M8 was closed on 2026-11-26 from the code (both sides, [0x0100ff80] [0x0100ff58]; batch 2 above).

### For agent A (one batched request)

The spec errors the reviews found are at the end of each report (game_flow.md 7, megatron_multiball.md 4,
optimus_multiball.md 2, wizard_modes.md 1, scoring_features.md 3, allspark_and_energon.md 1,
combos_and_multipliers.md 1). Decoding still needed for the strict rule: each deff's draw function (frames,
length, hold tail, sounds), each leff's function and the lamp groups (table 0x040d1510), the coil pulses of the
game's `coil_pulse` calls, the adjustment value formatter 0x0002aebc, the ball search task `0x0103b778`, the serve
and multiball tasks (`0x0103b39c`, `0x01039db4`, `0x0103aba4`).

Status 2026-11-25 (agent A): the deffs (all 153), the leffs and lamp groups (all), the coil pulses (33 of 35) and
the adjustment formatters (all 15, 0x0002aebc included) are decoded from the code; what stays open is listed in
[pinmame_waivers.md](../pinmame_waivers.md). The 20 spec errors are corrected in `rom/rules/modes/` (each
line cites its routine and the QA id). The ball search's coil sweep is decoded from its task (`rom/tools/ball_search.py`,
`rom/rom_data/io/ball_search_ops.json`: Optimus coil 0, top pop 5, left eject and Megatron lockup 6, right pop 10,
bottom pop 15, slings 20 and 25 ticks, end 30; the game's `BALL_SEARCH_SWEEP` is the same, one tick later); still
open there: the queued auto-launch's wait, the motor and gate from the event handlers. The serve and multiball
tasks are read from the code in `rom/rules/modes/ball_feed.md` (device settles 31 / 46 / 62 ticks from table
0x040d17fc, the shooter task's 125 ticks, 6-tick polls); the game's Tron-derived `MB_EJECT_TICKS`,
`MB_FIRST_EJECT_TICKS`, `SAVE_SERVE_TICKS` and `DEVICE_BUSY_TICKS` are for agent C to re-derive from it.

### Owner decisions

1. Decided 2026-11-25: no waiver for the captured data; agent A decodes it ([pinmame_waivers.md](../pinmame_waivers.md)).
   Decided later the same day: the flipper times may stay as measured until decoded; running the ROM's own code in
   Unicorn counts as decoding; the tick is the code's 16.0 ms (the game's `os_layer.py` TICK still says 16.26).
2. Decided 2026-11-25: the two Xilinx XC95144XL CPLDs are not decoded (fixed function, no game rule); `docs/boards_inventory.md` lists them with the unchecked boards.
3. Decided 2026-11-25: PinMAME capture approved for F15 only (row in [pinmame_waivers.md](../pinmame_waivers.md)); it confirmed the game.
