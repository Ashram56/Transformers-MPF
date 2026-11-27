"""QA 2026-11-26 (sounds and rule-driven coils): build matrix_sounds_coils.csv.

Read-only. Inputs: the sound call sites of the decompile (probe_sounds_sites.py, imported), the trace comparison
written by probe_sounds_traces.py (TRACE_CSV: game traces from tests/scenario.py against rom/rules/traces), the
deff op lists' sounds (timing.json, code-decoded) and the game's sources. Verdict per site:
  1. a fixed service call (0x009-0x00e, 0x010-0x012) in the service / test code: the game's service menu plays no
     sound (game/tf/settings.py), so missing, except the coin-door power-off cancel 0x009 (os_layer.py:1416);
  2. a literal call whose deff op list (timing.json) has it inside this function (or anywhere in the op list of the
     deff this function is): the game plays it when it runs the deff (display._media), match;
  3. a literal call the game names in a sound context: match (game file:line);
  4. else missing;
  5. MANUAL (below) overrides 1-4 for the sites read by hand (non-literal calls, rule handlers);
  6. the trace comparison then marks a call the game plays fewer times (missing / differs) or more times (differs),
     and turns a "missing" into match when the game plays the call as often as the reference from this function.
Usage: probe_sounds_matrix.py TRACE_CSV OUT_CSV
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_sounds_sites as ps  # noqa: E402

ROOT = ps.ROOT
SOUND_CTX = re.compile(r"sound|SOUND|music|MUSIC|speech|SPEECH|UNCAPTURED|KICK_ONE|RELEASE|CALL|_SOUNDS")

# (fn, call or line) -> (verdict, game_location, game_value, proof)
MANUAL = {
    ("0x000178b0", "x"): ("differs", "game/tf/display.py:404", "rules sorted by game priority",
                          "bg_entry_eval: first true entry of the music table plays its call if not playing; order "
                          "differs, see rows S-MUSIC"),
    ("0x0001da8c", "x"): ("match", "game/tf/os_layer.py:1557", "0x016",
                          "tilt warning: local_14 = 0x16 [0x0001da8c]; trace 6/6"),
    ("0x0001db40", "x"): ("match", "game/tf/os_layer.py:1578", "0x017", "tilt: local_c = 0x17 [0x0001db40]; trace 3/3"),
    ("0x00025fb8", "x"): ("unverifiable", "-", "-", "serial debug console (strcmp/atoi command 'play'); not game play"),
    ("0x01000ffc", "x"): ("match", "game/tf/features/bonus.py:24", "0x21 Autobot / 0x20 Decepticon",
                          "deff 25 helper: call = side 1 ? 0x21 : 0x20 [0x01000ffc]"),
    ("0x010038dc", "x"): ("match", "game/tf/features/bumblebee.py:34", "0x284..0x280 at 5..1",
                          "task 0xc3: table 0x040c5d18[count] [0x010038dc]"),
    ("0x01003a64", "0x27c"): ("match", "game/tf/features/bumblebee.py:30", "0x27c",
                              "double scoring switch sounds [0x01003a64] via hook scoring_switch"),
    ("0x01003a64", "0x27d"): ("match", "game/tf/features/bumblebee.py:30", "0x27d",
                              "snd_resolve_call(0x27d) [0x01003a64]"),
    ("0x010069d4", "x"): ("differs", "game/tf/features/megatron.py", "0x0f4 10 times",
                          "task 0x95 repeats its call (deff 77 leaf_6a20(0xf4, 0x2e): 46 plays); trace "
                          "megatron_decepticon ref 46 game 10"),
    ("0x01006ae0", "x"): ("differs", "game/tf/features/energon.py:74", "0x25f once per lit target",
                          "deff 126 sub plays param (0x25f / 0x265) [0x01006ae0]; trace: 0x25f +4, 0x265 -2"),
    ("0x01006a58", "x"): ("match", "game/tf/display.py:218", "delayed calls of the deff op lists",
                          "delayed sound task (leaf_6a9c) [0x01006a58]: one row per leaf_6a9c call below"),
    ("0x0100b5a0", "x"): ("unverifiable", "-", "-", "delayed sound task like 0x01006a58; starter not located"),
    ("0x0100b7f0", "x"): ("match", "game/tf/features/megatron.py:572", "lock_music() of the side",
                          "deff 140: snd_play2(per-player lock call 0x294-0x299) [0x0100b7f0]; trace 0x294 3/4, 0x297 3/4"),
    ("0x0101db34", "x"): ("unverifiable", "-", "-", "snd_play_after(uVar1) computed in the Blackout hit task"),
    ("0x0102fcb0", "x"): ("missing", "game/tf/display.py:218", "only the decoded variant's entries",
                          "table-driven deff sound scripts (snd_play_after_user [0x0102fcb0]); trace: 0x080-0x099, "
                          "0x0cb-0x0f2 missing, 0x085/0x094/0x0d3/0x1e9/0x1ea extra"),
    ("0x01033104", "x"): ("match", "game/tf/switches.py:106", "0x159 Autobot / 0x15a Decepticon",
                          "sw_left_slingshot: side 1 ? 0x159 : 0x15a [0x01033104]; trace 0x159 8/8 0x15a 24/24"),
    ("0x010331a4", "x"): ("match", "game/tf/switches.py:106", "0x159 / 0x15a", "sw_right_slingshot [0x010331a4]"),
    ("0x0000f008", "0x009"): ("match", "game/tf/os_layer.py:1416", "0x009", "power-off warning cancel [0x0000f008]"),
    ("0x01006138", "0x024"): ("differs", "game/tf/features/game_over.py:72", "0x24 always, no fade",
                              "0x24 only if game over state and not playing, then volume fade [0x01006138] (QA F18 open)"),
    ("0x01006138", "0x04b"): ("match", "game/tf/features/game_over.py:73", "0x4b 124 ticks later",
                              "task_sleep(0x7c) then 0x4b [0x01006138]"),
    ("0x01006054", "0x01e"): ("missing", "-", "-", "event 0x62 handler plays 0x1e in attract (state & 0x10) [0x01006054]"),
    ("0x01005f00", "0x045"): ("missing", "game/tf/features/attract.py", "no attract sound",
                              "attract speech 0x45 via event 0x2d (state & 0x118 == 0x10) [0x01005f84]"),
    ("0x01005fd0", "0x04a"): ("unverifiable", "-", "-", "task 93 ticks then 0x4a if flag 6 [0x01005fd0]; starter "
                              "not located (switch_lift.json lists the function)"),
    ("0x010019c8", "0x267"): ("missing", "-", "-", "5,000 + 0x267 + leff 149 [0x010019c8]; caller via a table, not "
                              "located; the game has no 0x267"),
    ("0x010337e8", "0x273"): ("missing", "game/tf/switches.py:84", "timer only",
                              "sw_l_ramp_entrance plays 0x273 on every hit [0x010337e8]; trace switches ref 3 game 0"),
    ("0x010338dc", "0x272"): ("missing", "game/tf/switches.py:84", "timer only",
                              "sw_r_ramp_entrance plays 0x272 on every hit [0x010338dc]; trace switches ref 2 game 0"),
    ("0x010339d0", "0x00f"): ("missing", "-", "-", "switch test (state & 0x100) Optimus up [0x010339d0]: service"),
    ("0x010339ec", "0x00f"): ("missing", "-", "-", "switch test (state & 0x100) Optimus down [0x010339ec]: service"),
    ("0x0100a3b8", "0x13b"): ("match", "game/tf/features/megatron.py:77", "0x13b at 0 and 0.243 s",
                              "Megatron device case 7: 0x13b + leff 23, again at tick 15 [0x0100a3b8]"),
    ("0x0100a3b8", "0x13c"): ("match", "game/tf/features/megatron.py:77", "0x13c at 0.505 s",
                              "case 9 after the 31-tick loop: 0x13c + leff 24 [0x0100a3b8]"),
    ("0x0100a3b8", "0x13d"): ("match", "game/tf/features/megatron.py:80", "0x13d every 0.40 s",
                              "release loop: 0x13d + leff 25, pulse (5 ticks) + sleep 20 = 25 ticks [0x0100a3b8]"),
    ("0x0100a788", "0x157"): ("match", "game/tf/features/allspark.py:122", "0x157 + leff 21, eject 54 ticks later",
                              "case 7: 0x157 + leff 21, loop 0x35 + 1 ticks [0x0100a788]; trace 0x157 ok"),
    ("0x0100a788", "0x158"): ("match", "game/tf/features/allspark.py:131", "0x158 + leff 22",
                              "case 4/9: 0x158 + leff 22 unless state & 0x310 (game masks 0x312) [0x0100a788]; "
                              "trace 29/30 (switches -1)"),
    ("0x01022608", "0x170"): ("differs", "game/tf/features/battles.py:908", "0x170 Decepticon / 0x174 Autobot",
                              "deff 91: call by the battle bit (2: 0x171, 4: 0x172, 8: 0x173, 0x10: 0x174, 0x20: "
                              "0x175, 0x40: 0x176, 0x80: 0x177, else 0x170) [0x01022608]; game picks by side"),
}

# Music table (rom/rom_data/sound/music_table.csv: the deff-rule list bg_entry_eval [0x000178b0] walks in this order,
# first true entry wins, plays its deff unless running and its call unless playing) against the game's deff rules
# (os.deff_rule, display.select: highest game priority first, then os.base_music()).
MUSIC_ROWS = [
    ("entry 0 side choice / ball start", "0x010068e4", "deff 40 + 0x1a/0x1b while choosing, else deff 19 + 0x1c/0x1d; "
     "0x31/0x34 instead whenever the battle can progress (dbattle_can_progress), checked first in the list",
     "game/tf/features/optimus.py:388", "0x31/0x34 only once ball_validated; else side.py MUSIC", "differs",
     "code: side_choice_running_user [0x010068e4] overrides with 0x31/0x34 before validation and during the choice; "
     "optimus.base_music needs ball_validated"),
    ("entry 0 condition", "0x010068b4", "game flag 0x10 clear and ram_000314d8_user() false",
     "game/tf/display.py:408", "rules below PREVALID_PRIO skipped until valid", "match",
     "code [0x010068b4]; game: score display rule before validation"),
    ("entry 1 Megatron Autobot", "0x0100cee0", "deff 70 + 0x38, list position 1", "game/tf/features/megatron.py:403",
     "deff 70 + 0x38 priority 0x60", "differs",
     "order: the game ranks 2-bank fast scoring / Bumblebee (0x80) and wizard (0x70) above it; ROM ranks it above them"),
    ("entry 2 Megatron Decepticon", "0x0100ee0c", "deff 76 + 0x3b, position 2", "game/tf/features/megatron.py:403",
     "deff 76 + 0x3b priority 0x60", "differs", "order as entry 1"),
    ("entry 3 wizard side mode", "0x01010958", "deff 82 + 0x3c, position 3", "game/tf/features/wizard.py:84",
     "deff 82 + 0x3c priority 0x70", "differs", "game puts it above Megatron (0x70 > 0x60); ROM below"),
    ("entry 4 Optimus Autobot", "0x010285a0", "deff 58 + 0x32, position 4", "game/tf/features/optimus.py:336",
     "deff 58 + 0x32 priority 0x60", "differs", "game: below wizard side (ROM too) but below Bumblebee / fast scoring"),
    ("entry 5 Optimus Decepticon", "0x0102a6e4", "deff 64 + 0x35, position 5", "game/tf/features/optimus.py:336",
     "deff 64 + 0x35 priority 0x60", "differs", "as entry 4"),
    ("entry 6 wizard multiball", "0x01037018", "deff 87 + 0x3d, position 6", "game/tf/features/wizard.py:85",
     "deff 87 + 0x3d priority 0x70", "differs", "game ranks it above Megatron / Optimus; ROM below them"),
    ("entry 7 Bumblebee double scoring (task 0xc3)", "0x01003ec8", "deff 130 + 0x26, position 7",
     "game/tf/features/bumblebee.py:50", "deff 130 + 0x026 priority 0x80", "differs",
     "game ranks it first; ROM below every multiball (positions 1-6)"),
    ("entry 8 fast scoring", "0x010049fc", "deff 133 + 0x27, position 8 (mask 0)", "game/tf/features/twobank.py:74",
     "deff 133 + 0x027 priority 0x80", "differs", "as entry 7"),
] + [("entry %d battle %s" % (9 + i, name), fn, "deff %d + 0x%02x, position %d" % (d, m, 9 + i),
      "game/tf/features/battles.py:744", "deff %d + 0x%02x priority 0x40" % (d, m), "match",
      "below every other mode rule in both; battles.py per-battle (bg, music) as the table")
     for i, (name, fn, d, m) in enumerate((("Ratchet", "0x010138d0", 121, 0x2f), ("Bumblebee", "0x010153c0", 109, 0x2c),
                                           ("Devastator", "0x01016f4c", 105, 0x2b), ("Starscream", "0x01018884", 93, 0x28),
                                           ("Mudflap", "0x0101a414", 117, 0x2e), ("Ironhide", "0x0101c0e4", 113, 0x2d),
                                           ("Blackout", "0x0101da18", 101, 0x2a), ("Shockwave", "0x0101f5a4", 97, 0x29)))] + [
    ("entry 17 fallback", "0x01006970", "deff 19 + 0x1e Autobot / 0x1f Decepticon; 0x31/0x34 when the battle can progress",
     "game/tf/features/side.py:65", "MUSIC play by side; optimus.base_music 0x31/0x34", "match",
     "code [0x01006970]; trace 0x1e 16/17, 0x1f 28/30 (one-off timing)"),
    ("music only when not playing", "0x000178b0", "snd_play(call) unless the call is playing (ram_00037b94_user_255d4)",
     "game/tf/display.py:440", "plays when music != self.music", "match", "code [0x000178b0]"),
    ("strict mode TF_PUP=0", "0x000178b0", "the ROM's music calls", "game/tf/display.py:440",
     "the same calls (PuP replaces them only when enabled)", "match", "docs/pup.md; game plays os.sound(music)"),
]

# Rule-driven coils (the game's own coil calls and tick constants) against the code.
COIL_ROWS = [
    ("serve: trough kick after the settle", "coil", "0x0103b128", "settle +0x10 = 31 ticks, kick on the next tick",
     "game/tf/os_layer.py:56", "SERVE_EJECT_TICKS 32", "match", "code [0x0103b128], ball_feed.md"),
    ("serve: later balls +6 ticks", "coil", "0x0103b128", "same 31-tick settle for every type-3 serve",
     "game/tf/os_layer.py:57", "LATER_SERVE_EXTRA_TICKS 6 (trace)", "unverifiable",
     "trace-derived; code shows no per-ball difference beyond the feeder poll (2 ticks); not decoded further"),
    ("ball save re-serve (drain, type 1)", "coil", "0x0103b128", "type 1: settle 31 ticks, kick, auto-launch",
     "game/tf/os_layer.py:68", "SAVE_SERVE_TICKS 48 (Tron traces)", "differs",
     "code: serve task settles +0x10 = 31 ticks for type 1 [0x0103b128]; 48 is Tron's"),
    ("outlane save serve (type 2)", "coil", "0x0103b128", "types 2 and 8: no settle, kick at once",
     "game/tf/os_layer.py:58", "SAVE_EJECT_TICKS 39", "differs",
     "code: 'types 2 and 8 without a settle' [0x0103b128] (ball_feed.md step 2)"),
    ("auto-launch after a type 1/2/6 serve", "coil", "0x0103b39c", "auto-launch flag +0x30 for types 1, 2, 6; coil 2",
     "game/tf/os_layer.py:1288", "add_ball(player_controlled=False) -> c_auto_launch", "match",
     "code [0x0103b39c]; MPF mechanical eject of bd_shooter_lane"),
    ("auto-launch task 0x3c", "coil", "0x01032dfc", "not located (sw_shooter_lane starts 0x3e 125 and 0x47 187 ticks)",
     "game/tf/os_layer.py:59", "AUTO_LAUNCH_TICKS 12 (inferred)", "unverifiable", "inferred in the game; task 0x3c's "
     "starter not found in the decompile"),
    ("shooter lane task 0x3e / 0x47 / 0x3d", "coil", "0x01032dfc", "0x3e 125 ticks, 0x47 187 ticks, 0x3d 6 ticks "
     "(no launch sound while 0x3d runs)", "game/tf/os_layer.py:1089", "launch sound 4 ticks after the lane opens",
     "match", "code [0x01032dfc]; trace 0x056 53/53"),
    ("multiball: first ball", "coil", "0x0103aba4", "trough ready (1-tick polls) + settle 31 ticks, then the kick",
     "game/tf/os_layer.py:67", "MB_FIRST_EJECT_TICKS 51 (Tron)", "differs", "code [0x0103aa5c] settle +0x10 = 31"),
    ("multiball: next balls", "coil", "0x0103aa5c", "settle 31 + wait task 0x16 (125 ticks) of the previous ball, "
     "6-tick polls", "game/tf/os_layer.py:61", "MB_EJECT_TICKS 101 (Tron)", "differs",
     "code [0x0103aa5c] / [0x0103a7a4]: >= 156 ticks plus the ball's travel"),
    ("multiball: device busy", "coil", "0x0103ab6c", "6-tick polls while state 0x100 or a ball sits in the shooter lane",
     "game/tf/os_layer.py:64", "DEVICE_BUSY_TICKS 149 fixed after a device release", "differs",
     "code [0x0103ab6c]: no fixed hold; 149 is Tron's"),
    ("multiball: leff 13 and save counters", "coil", "0x0103aba4", "leff 13 at the task start, off when the first counter "
     "runs out", "game/tf/os_layer.py:784", "leff 13 one tick after the call, off at the save end", "match",
     "code [0x0103aba4]"),
    ("timed plunger", "coil", "0x0103a6d0", "adj 39 x 62 ticks, then kick the shooter (coil 2)",
     "game/tf/os_layer.py:1185", "adj 39 x SECOND (62)", "match", "code [0x0103a6d0]"),
    ("ball search sweep", "coil", "0x0103b778", "Optimus 0, top pop 5, left eject + lockup 6, auto-launch 6 (queued), "
     "right pop 10, bottom pop 15, slings 20 / 25; 64 ms each", "game/tf/os_layer.py:82",
     "1, 6, 7, 11, 14, 16, 21, 26 (+1 start tick)", "match",
     "rom/rom_data/io/ball_search_ops.json (code run); auto-launch 14 is from a trace (the queued pulse's wait open)"),
    ("ball search auto-launch slot", "coil", "0x00001f70", "queued pulse, served by 0x00003758: wait not decoded",
     "game/tf/os_layer.py:83", "tick 14 (trace)", "unverifiable", "ball_feed.md: code open"),
    ("ball search orbit gate", "coil", "0x0103b778", "from the event 0xc / 0xd handlers: not decoded",
     "game/tf/os_layer.py:85", "(32, 91) ticks (trace)", "unverifiable", "ball_feed.md: code open"),
    ("ball search Optimus motor", "coil", "0x0103b778", "from the event handlers: not decoded", "game/tf/os_layer.py:86",
     "33 ticks, then MOVE_S", "unverifiable", "ball_feed.md: code open"),
    ("ball search task lengths", "coil", "0x0103b778", "task 0x2b loop (task_running(0x2b)): not decoded",
     "game/tf/os_layer.py:69", "EVENT 36, TICKS 104, RUN 496 (traces)", "unverifiable", "ball_feed.md: code open"),
    ("lost ball feed", "coil", "0x0103b8e0", "5th search with adj 63: deff 13, serve type 2", "game/tf/os_layer.py:87",
     "LOST_BALL_SEARCH 5, serve(2)", "match", "code [0x0103b8e0]"),
    ("Optimus hit kicker", "coil", "0x01033cfc", "task 0x54: sleep 15, coil 12 64 ms, sleep 47",
     "game/tf/features/optimus_mech.py:29", "HIT_DELAY 15, KICKER_MS 64, HIT_TAIL 47", "match",
     "code task_0x54_of_FUN_01033d3c [0x01033cfc]"),
    ("Optimus motor time limit", "coil", "0x010253b8", "mech object vtable +0xec: not decoded",
     "game/tf/features/optimus_mech.py:28", "MOVE_S 7.65 (simulator)", "unverifiable", "observed only"),
    ("Megatron kick (one ball)", "coil", "0x0100a3b8", "case 9: 0x13c + leff 24 and coil 3 64 ms in the same call, "
     "31 ticks after 0x13b", "game/tf/features/megatron.py:78", "KICK_ONE_COIL 0.61 s (0x13c at 0.505 s)",
     "unverifiable", "code [0x0100a3b8]; FUN_00002078's queue latency not decoded (trace value)"),
    ("Megatron release (balls 2-4)", "coil", "0x0100a3b8", "per ball: 0x13d + leff 25, pulse coil 3 (5 ticks) + sleep 20 "
     "= 25 ticks", "game/tf/features/megatron.py:82", "RELEASE_COILS 0.13, 0.61, 0.93, 1.33 s (steps 0.48 / 0.32 / 0.40)",
     "differs", "code [0x0100a3b8]: equal 25-tick steps; sounds in RELEASE keep 0.40 s steps, the coils do not"),
    ("Megatron entry nudge", "coil", "0x0100a3b8", "case 2: up to 3 x coil 3 for 4 ms, 93 ticks apart, while sw 42 is "
     "closed or the count changed", "game/tf/features/megatron.py", "none", "missing", "code [0x0100a3b8] case 2"),
    ("Megatron lock coil 3 (leaf_a374)", "coil", "0x0100a374", "coil 3 64 ms + task 0x58 62 ticks", "-", "-",
     "unverifiable", "caller not located"),
    ("Megatron lock settle", "coil", "0x040d17fc", "device settle 46 ticks (table 0x040d17fc)",
     "game/tf/features/megatron.py:54", "SETTLE_TICKS 46", "match", "ball_feed.md table"),
    ("Megatron autofire after lock", "coil", "0x0100a3b8", "not decoded", "game/tf/features/megatron.py:55",
     "SERVE_TICKS 155 (trace)", "unverifiable", "observed 2.51 s"),
    ("Allspark eject", "coil", "0x0100a788", "case 7: 0x157 + leff 21, 54 ticks, then case 4/9: 0x158 + leff 22 and "
     "coil 22 64 ms", "game/tf/features/allspark.py:24", "EJECT_TICKS 54; c_left_eject default 64 ms", "match",
     "code [0x0100a788] (loop 0x35 + 1)"),
    ("Allspark eject log", "coil", "0x0100a9b0", "coil 22 64 ms", "game/tf/features/allspark.py:31",
     "coil_log(22, 130) in the trace", "differs", "the game's trace logs 130 ms (observed); the code pulses 64 ms; "
     "the real pulse is MPF's default 64"),
    ("Allspark settle", "coil", "0x040d17fc", "device settle 46 ticks", "game/tf/features/allspark.py:22",
     "SETTLE_TICKS 47", "match", "46 + the start tick"),
    ("knocker coil 24", "coil", "0x00019420", "adj 44 = 2: coil 24 64 ms, then 46 ticks before the next queued knock",
     "game/tf/os_layer.py:964", "pulse at once for every knock, no spacing", "differs",
     "code [0x00019420]: DAT_000375c8 = 0x2e between knocks"),
    ("shaker patterns", "coil", "0x010307a0", "pattern 1/2/3 = 200/384/1024 ms (table 0x040c7620), adj 96 >= min, "
     "not in state 0x310", "game/tf/os_layer.py:139", "SHAKER_MS 200/384/1024", "match",
     "code; game traces: coil 8 207/207 bursts over the 24 scenarios"),
    ("shaker in deffs", "coil", "0x010307a0", "the deffs of shaker.csv", "game/tf/os_layer.py:735",
     "shaker_deff from shaker.csv", "match", "rom/rom_data/io/shaker.csv"),
    ("shaker fast scoring award", "coil", "0x01004644", "tail call shaker(1, 3)", "game/tf/features/twobank.py:51",
     "AWARD_SHAKER (1, 3)", "match", "shaker.csv row 8"),
    ("trough kicker", "coil", "0x0100a13c", "coil 1 64 ms", "rom/mpf_package/config/coils.yaml:9", "64 ms", "match",
     "coil_pulses.csv"),
    ("auto-launch coil", "coil", "0x0100a1e0", "coil 2 64 ms", "game/tf/os_layer.py:1510", "c_auto_launch default", "match",
     "coil_pulses.csv"),
    ("orbit gate on the left orbit", "coil", "0x010332e4", "gate object leaf_2bc28(0x35384, 0x4d)",
     "game/tf/features/battles.py:971", "hold 91 ticks", "unverifiable",
     "the gate object's time unit is not decoded (0x4d = 77); switch_handlers.csv code run: 1488 ms"),
    ("flippers off at tilt / slam", "coil", "0x0001db40", "tilt: flipper relay off", "game/tf/os_layer.py:1581",
     "flipper.disable()", "match", "code [0x0001db40]"),
    ("flippers on at ball start", "coil", "0x00019d30", "ball_start enables the flippers", "game/tf/os_layer.py:1761",
     "flipper.enable()", "match", "code"),
    ("deff 140 flasher tasks", "coil", "0x0100bb3c", "deff 140 starts coil_pulse_fn_user_bb3c (coil 28 100 ms) and "
     "coil_pulse_user 0x0100bb78 (28 / 21 48 ms)", "game/tf/lamps.py:520", "only through leff 168", "unverifiable",
     "flasher bursts are the lamps review's; megatron traces show extra/missing 21 / 28 bursts"),
]

# initials entry (deff 32 [0x0103c840], deff 36 [0x0103e460]): the OS constants 0x00030eac / 0x00030eae / 0x00030eb0
# hold calls 0x04c / 0x04d / 0x04e (ROM read with rom/tools/rom.py u16); 0x00033390 / 0x00033392 / 0x0003379c are RAM
# (0 at reset, set at run time)
for _fn, _lines in (("0x0103c840", (92890, 92917, 92935, 92940)), ("0x0103e460", (93974, 94001, 94012, 94017))):
    for _l in _lines:
        MANUAL[(_fn, "L%d" % _l)] = ("missing", "game/tf/features/high_scores.py:44", "SOUNDS all None",
                                     "initials entry plays the OS constant calls 0x04c (letter) / 0x04d (move) / 0x04e "
                                     "(select) [0x00030eac-0x00030eb0]; the game's SOUNDS are None")
for _fn, _l in (("0x0103c840", 92810), ("0x0103ce90", 92976), ("0x0103e208", 93761), ("0x010475fc", 98858)):
    MANUAL[(_fn, "L%d" % _l)] = ("unverifiable", "game/tf/features/high_scores.py:44", "SOUNDS None",
                                 "RAM call (0x00033390 / 0x00033392 / 0x0003379c, 0 at reset): its writer not located")

# Sound call fields (rom/rom_data/sound/sound_calls.csv, decoded by rom/tools/sound_fields.py from snd_resolve_call
# [0x00025044] / snd_start_sample [0x00024ae4] / FUN_00025b3c) against the game's media data (game/tf/media_data.json
# pools, built from rom/mpf_package/config/sounds.yaml) and os_layer.sound / media_bridge.sound.
FIELD_ROWS = [
    ("sample lists of the 702 calls", "0x040dee08", "+0x08 sample list per call", "game/tf/media_data.json",
     "694 pools with the same sample count; calls 0x001-0x008 are channel stops", "match",
     "mechanical: pools vs sound_calls.csv n_samples (694 same, 3 empty, 0 differ)"),
    ("cue +0x0c", "0x00024ae4", "0 in every call (start of sample)", "game/tf/media_bridge.py:402", "plays from the start",
     "match", "sound_calls.csv cue column"),
    ("priority +0x10 and take-over +0x11", "0x00025044", "a channel playing a lower priority (or equal with flag bit 0) "
     "is taken over; else the call is refused", "game/tf/os_layer.py:607", "no channel model; sound_refused() only for "
     "the Allspark warning 0x157", "differs", "code [0x00025044]; the game plays every call on MPF's bus"),
    ("no-repeat memory +0x0e (34 calls) and speech ring +0x12 (29 calls)", "0x00025b3c",
     "a random pick skips the call's last n samples and the 9 last speech samples (ring 0x00038354)",
     "game/tf/os_layer.py:597", "uniform os.pick over all samples", "differs", "code [0x00025b3c] / [0x00025044]"),
    ("pool type", "0x00025044", "random pick (or the argument of snd_play2)", "game/tf/media_bridge.py:395",
     "random_force_all, index when the rules pass one", "match", "media_bridge.sound"),
    ("channel stop calls 0x001-0x008", "0x00025044", "stub calls 1-8 (deff 25 plays 0x001 at its end)",
     "game/tf/media_bridge.py:384", "any of 1-8 stops the music", "unverifiable",
     "which channel each stub stops is not decoded"),
    ("music bus and loop", "0x00025044", "music samples loop from the stream script's label", 
     "rom/mpf_package/config/sounds.yaml", "track music, loops -1, loop_start_at", "match", "sounds.yaml header"),
]
SERVICE_LO = 0x0103e000


def game_sound_refs():
    refs = {}
    for root, _, files in os.walk(os.path.join(ROOT, "game", "tf")):
        for name in files:
            if not name.endswith(".py"):
                continue
            p = os.path.join(root, name)
            for n, line in enumerate(open(p, encoding="utf-8"), 1):
                code = line.split("#")[0]
                if not SOUND_CTX.search(code):
                    continue
                for m in re.finditer(r"\b0x([0-9a-fA-F]{1,3})\b", code):
                    refs.setdefault(int(m.group(1), 16), []).append("%s:%d" % (os.path.relpath(p, ROOT), n))
    return refs


def traces(path):
    out = {}
    for r in csv.DictReader(open(path)):
        out[int(r["call"], 16)] = (int(r["ref_n"]), int(r["game_n"]), r["ref_callers"], r["scenario_delta_game_minus_ref"])
    return out


def main():
    tr, out = traces(sys.argv[1]), sys.argv[2]
    ds, rng, dfn, refs = ps.deff_sounds(), ps.fn_ranges(), ps.deff_fns(), game_sound_refs()
    rows = []
    sites = ps.rom_sites()
    literal_fns = {}
    for s in sites:
        if s["call"] is not None:
            literal_fns.setdefault(s["call"], set()).add(s["fn"][0])
    for i, s in enumerate(sites, 1):
        fa, fname = s["fn"]
        call = s["call"]
        chex = "0x%03x" % call if call is not None else None
        fkey = "0x%08x" % fa
        deffs = dfn.get(fa, [])
        where = "%s%s" % (fname, " (deff %s)" % "/".join(map(str, deffs)) if deffs else "")
        in_fn = [(d, a, t) for d, a, t in ds.get(call, []) if fa <= int(a, 16) < rng[fa] or d in deffs] \
            if call is not None else []
        element = "sound %s %s line %d" % (chex or s["expr"][:40], s["api"], s["line"])
        rom_value = "%s %s" % (s["api"], chex or s["expr"][:60])
        game_loc, game_val, proof, sev = "-", "-", "", ""
        manual = MANUAL.get((fkey, "L%d" % s["line"])) or MANUAL.get((fkey, chex)) or (
            MANUAL.get((fkey, "x")) if call is None else None)
        if manual:
            verdict, game_loc, game_val, proof = manual
        elif call is not None and call in (9, 10, 11, 12, 13, 14, 0x10, 0x11, 0x12) and not in_fn and (
                fa >= SERVICE_LO or fa in (0x0002a45c, 0x0000f290, 0x01025844, 0x0000f008, 0x01044f04)):
            verdict, game_val = "missing", "service menu plays no sound"
            game_loc = "game/tf/settings.py:332"
            proof = "service / test code; game settings.py has no sound call"
        elif in_fn:
            d, a, t = in_fn[0]
            verdict, game_loc, game_val = "match", "rom/mpf_package/media/dmd/deffs/deff_%03d/timing.json" % d, \
                "deff %d tick %d" % (d, t)
            proof = "deff op list at %s, played by game/tf/display.py:218 _media" % a
        elif call is not None and refs.get(call):
            verdict, game_loc, game_val = "match", refs[call][0], chex
            proof = "game names %s in a sound context (%d refs)" % (chex, len(refs[call]))
        elif call is None:
            verdict, proof = "unverifiable", "computed call; not read by hand"
        else:
            verdict = "missing"
            proof = "no deff op list entry in this function and no game reference"
            if fa < SERVICE_LO and any(k in fname for k in ("dmd_page_alloc_pair_user", "play_sound_", "draw_")):
                proof = ("battle hit animation picked from a table by shots left (e.g. deff_094 0x040c6a60); "
                         "the game plays only the decoded animation's sounds")
        if call is not None and call in tr:
            ref_n, game_n, callers, delta = tr[call]
            # snd_play2 / snd_play_after / the sound tasks are logged with a caller inside the sound code or the
            # task dispatcher, not the calling function
            mine = callers.find(fkey) >= 0 or (s["api"] != "snd_play" and any(
                g in callers for g in ("0x00025250", "0x000254b4", "0x00014f1c", "0x00025284")))
            if manual:
                proof += "; trace ref %d game %d" % (ref_n, game_n)
            elif ref_n != game_n and (mine or verdict != "match"):
                if game_n == 0:
                    verdict = "missing"
                elif verdict == "match" or verdict == "missing":
                    verdict = "differs"
                proof += "; trace ref %d game %d (%s)" % (ref_n, game_n, delta)
            elif ref_n and ref_n == game_n:
                proof += "; trace %d/%d" % (game_n, ref_n)
                if verdict == "missing" and mine:
                    verdict, game_loc, game_val = "match", (refs.get(call) or ps.game_refs().get(call) or ["-"])[0], chex
        rows.append(["S%03d" % i, element, "sound", fkey, rom_value + " in " + where, game_loc, game_val, verdict,
                     proof])
    # calls the traces show from indirect callers (dispatcher, snd_play2 / snd_play_after internals) with no
    # literal site in the decompile
    n = len(rows)
    for call, (ref_n, game_n, callers, delta) in sorted(tr.items()):
        if call in literal_fns or not ref_n:
            continue
        first = callers.split(" x")[0]
        fkey = first.split()[0]
        if ref_n == game_n:
            verdict = "match"
        elif game_n == 0:
            verdict = "missing"
        else:
            verdict = "differs"
        refl = refs.get(call, ["-"])[0]
        n += 1
        rows.append(["S%03d" % n, "sound 0x%03x (indirect)" % call, "sound", fkey,
                     "0x%03x from %s" % (call, callers[:90]), refl, "0x%03x x%d" % (call, game_n), verdict,
                     "no literal site: caller from the reference traces (traces confirm only); ref %d game %d %s"
                     % (ref_n, game_n, delta)])
    for i, (el, fn, rv, gl, gv, v, pr) in enumerate(MUSIC_ROWS, 1):
        rows.append(["M%02d" % i, "music " + el, "music", fn, rv, gl, gv, v, pr])
    for i, (el, fn, rv, gl, gv, v, pr) in enumerate(FIELD_ROWS, 1):
        rows.append(["F%02d" % i, el, "sound_field", fn, rv, gl, gv, v, pr])
    for i, (el, kind, fn, rv, gl, gv, v, pr) in enumerate(COIL_ROWS, 1):
        rows.append(["C%02d" % i, el, kind, fn, rv, gl, gv, v, pr])
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "element", "kind", "rom_address", "rom_value", "game_location", "game_value", "verdict",
                    "proof"])
        w.writerows(rows)
    print(len(rows), "sound rows")


if __name__ == "__main__":
    main()
