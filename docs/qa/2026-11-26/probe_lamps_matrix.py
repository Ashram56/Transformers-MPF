"""QA 2026-11-26, lamp conversion: writes matrix_lamps.csv (read-only on the game).

Run from the repository folder: .venv/bin/python docs/qa/2026-11-26/probe_lamps_matrix.py
Sources: agent A's leff table and lift (rom/rom_data/io/lamp_effects.csv, leff_ops/), the deff op lists
(rom/rom_data/dmd/deff_ops/), the lamp groups (lamp_groups.json), the Ghidra decompile (leff_start / rule calls),
and the game (game/tf/lamps.py parse_show on every packaged show, the features' leff starts listed below by hand).
ROM_EXTRA holds the leff_start call sites outside the decompiled functions, found by scanning the ROM for BL to
leff_start 0x00007c10 with r0 loaded by an immediate (rom/tools/rom.py bl_callers + capstone; needs the ROM).
"""
import collections
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "game"))
from tf.lamps import parse_show  # noqa: E402

IO = os.path.join(ROOT, "rom", "rom_data", "io")
SHOWS = os.path.join(ROOT, "rom", "mpf_package", "config", "shows")
OUT = os.path.join(os.path.dirname(__file__), "matrix_lamps.csv")

LEFFS = {int(r["leff"]): r for r in csv.DictReader(open(os.path.join(IO, "lamp_effects.csv"), encoding="utf-8"))}
OPS = {n: json.load(open(os.path.join(IO, "leff_ops", "leff_%03d.json" % n))) for n in LEFFS}
GROUPS = {int(k): v for k, v in json.load(open(os.path.join(IO, "lamp_groups.json"))).items()}

# ---------------------------------------------------------------- ROM: who starts each leff
DEC = open(os.path.join(ROOT, "rom", "code", "tf_decompiled.c"), encoding="utf-8").read().split("\n")
rom_start = collections.defaultdict(list)
cur = ("?", "?")
for i, line in enumerate(DEC):
    m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", line)
    if m:
        cur = ("0x" + m.group(1), m.group(2))
        continue
    for m in re.finditer(r"\bleff_start\((0x[0-9a-f]+|\d+)\)", line):
        rom_start[int(m.group(1), 0)].append("%s %s (dec %d)" % (cur[0], cur[1], i + 1))
    m = re.search(r"ram_00033dfc_user\(&DAT_[0-9a-f]+,3,([^,]+),(0x[0-9a-f]+|\d+),(0x[0-9a-f]+|\d+)", line)
    if m:
        rom_start[int(m.group(2), 0)].append("rule %s cond %s mask %s (dec %d)" % (cur[0], m.group(1), m.group(3), i + 1))
ROM_EXTRA = {
    9: ["0x0001db40 tilt: packed deff 0x15 / leff 9 (local_10 = 0x00090015)"],
    11: ["0x0001da8c adj_tilt_warnings: packed deff 0x17 / leff 11"],
    17: ["0x0001c3bc in task 0x33 LAB_0001c360 of replay_award 0x0001c410 (after deff 0x1c starts)"],
    18: ["0x0001e084 in task 0x34 LAB_0001e028 of 0x0001e194 (tournament score, after deff 0x1d)"],
    19: ["0x0001b414 in task 0x35 LAB_0001b3b8 of 0x0001b494 (tickets, after deff 0x1e)"],
    27: ["0x0102cb7c start_leff_26 0x0102ca98: table 0x040c74d2 per pop (arg lamp 0x040c74d4)"],
    28: ["0x0102cb7c start_leff_26 0x0102ca98: table 0x040c74d2"],
    29: ["0x0102cb7c start_leff_26 0x0102ca98: table 0x040c74d2"],
}
for k, v in ROM_EXTRA.items():
    rom_start[k] = v + rom_start[k]
for p in sorted(glob.glob(os.path.join(ROOT, "rom", "rom_data", "dmd", "deff_ops", "*.json"))):
    name = os.path.basename(p)[:-5]
    for m in re.finditer(r'"op":"leff","at":"(0x[0-9a-f]+)","leff":(\d+)', open(p).read()):
        s = "%s deff op (%s)" % (m.group(1), name)
        if s not in rom_start[int(m.group(2))]:
            rom_start[int(m.group(2))].append(s)

# ---------------------------------------------------------------- game: who starts each leff (read by hand)
F = "game/tf/features/"
GAME = {
    1: F + "attract.py:46", 9: "os_layer.py:1577", 11: "os_layer.py:1556", 12: F + "slam_tilt.py:43",
    13: "os_layer.py:787", 14: "os_layer.py:1198", 15: "os_layer.py:1281,1680", 16: "os_layer.py:1152",
    17: "os_layer.py:948", 20: F + "optimus.py:345 rule", 175: F + "optimus.py:345 rule", 176: F + "optimus.py:345 rule",
    177: F + "optimus.py:346 rule", 21: F + "allspark.py:124", 22: F + "allspark.py:133",
    23: F + "megatron.py:631,645", 24: F + "megatron.py:631,645", 25: F + "megatron.py:631", 26: F + "pops.py:94",
    27: F + "pops.py:95", 28: F + "pops.py:95", 29: F + "pops.py:95", 32: F + "allspark.py:58 rule", 33: F + "pops.py:137",
    35: F + "combos.py:148", 37: F + "combos.py:66 rule", 38: F + "combos.py:173", 39: F + "combos.py:71 rule",
    40: F + "allspark.py:56 rule", 45: F + "optimus.py:150", 53: F + "optimus.py:150",
    46: F + "optimus.py:337 rule", 54: F + "optimus.py:337 rule", 47: F + "optimus.py:342 rule", 55: F + "optimus.py:342 rule",
    48: F + "optimus.py:164", 49: F + "optimus.py:164", 50: F + "optimus.py:164", 56: F + "optimus.py:164",
    57: F + "optimus.py:164", 58: F + "optimus.py:164", 51: F + "optimus.py:216", 59: F + "optimus.py:216",
    61: F + "megatron.py:123", 69: F + "megatron.py:123", 62: F + "megatron.py:404 rule", 70: F + "megatron.py:404 rule",
    63: F + "megatron.py:410 rule", 71: F + "megatron.py:410 rule", 64: F + "megatron.py:138,252", 65: F + "megatron.py:138",
    66: F + "megatron.py:252", 72: F + "megatron.py:138", 73: F + "megatron.py:138", 74: F + "megatron.py:374",
    67: F + "megatron.py:157", 75: F + "megatron.py:157", 76: F + "wizard.py:104 rule (Autobot only)",
    77: F + "wizard.py:104 rule (Autobot only)", 78: F + "wizard.py:249", 79: F + "wizard.py:91 rule",
    80: F + "wizard.py:98 rule", 81: F + "wizard.py:267", 82: F + "wizard.py:280", 83: F + "wizard.py:294",
    86: F + "wizard.py:317", 87: F + "wizard.py:99 rule", 88: F + "wizard.py:100 rule", 89: F + "wizard.py:332",
    91: F + "wizard.py:361", 92: F + "side.py:75 (ball start)", 95: F + "side.py:75 (ball start, choosing)",
    97: F + "lanes.py:88", 98: F + "lanes.py:88", 99: F + "lanes.py:88", 100: F + "lanes.py:88", 101: F + "lanes.py:88",
    102: F + "lanes.py:88", 103: F + "battles.py:909", 104: F + "battles.py:752 rule", 120: F + "battles.py:442",
    106: F + "battles.py:748 rule", 110: F + "battles.py:748 rule", 114: F + "battles.py:748 rule",
    118: F + "battles.py:748 rule", 123: F + "battles.py:748 rule", 128: F + "battles.py:748 rule",
    132: F + "battles.py:748 rule", 136: F + "battles.py:748 rule", 124: F + "battles.py:750 rule",
    139: F + "energon.py:93", 141: F + "energon.py:93", 140: F + "energon.py:72", 142: F + "energon.py:80",
    143: F + "twobank.py:106", 144: F + "twobank.py:119,227", 145: F + "twobank.py:217",
    147: F + "twobank.py:73 rule", 148: F + "twobank.py:73 rule", 159: F + "twobank.py:76 rule",
    160: F + "twobank.py:76 rule", 164: F + "twobank.py:250", 150: F + "bumblebee.py:73", 152: F + "spinner.py:64",
    155: F + "spinner.py:98", 156: F + "bumblebee.py:90", 157: F + "bumblebee.py:51 rule", 167: F + "megatron.py:476",
    168: F + "megatron.py:573", 169: F + "optimus.py:402", 170: F + "optimus.py:411", 174: F + "optimus.py:426",
    178: F + "optimus.py:448",
}
# deffs whose capture (timing.json) or UNCAPTURED entry starts the leff with the deff (game/tf/display.py:213)
for p in glob.glob(os.path.join(ROOT, "rom", "mpf_package", "media", "dmd", "deffs", "deff_*", "timing.json")):
    d = json.load(open(p))
    for e in d.get("leffs") or []:
        GAME.setdefault(int(e["leff"]), "display.py:213 with deff %d" % d["deff"])
for leff, where in ((107, "battles.py:91"), (109, "battles.py:92"), (126, "battles.py:93"), (133, "battles.py:94"),
                    (134, "battles.py:95"), (48, "optimus.py:70"), (49, "optimus.py:70"), (51, "optimus.py:71"),
                    (74, "megatron.py:88"), (167, "megatron.py:88"), (89, "wizard.py:67"), (165, "twobank.py:71")):
    GAME.setdefault(leff, F + where + " UNCAPTURED")

CODE_LEFFS = {  # leffs the game draws with code (Lamps.leff_code), and how they compare
    13: ("os_layer.py:1213", "match", "toggle lamp 3 every max(2, left/31) ticks, 10 above 0x138: same as 0x00028168"),
    14: ("os_layer.py:1213", "match", "waits valid playfield, toggles while task 0x31: same as 0x00028224"),
    39: (F + "combos.py:104", "match", "X lamp of the roving index toggled every 3 ticks, others released: 0x010239bc"),
    46: ("lamps.py:207", "match", "lit shots' lamps on/off every 3 ticks (table 0x040c729c), unlit released"),
    54: ("lamps.py:207", "match", "as 46 (lamp 59 for Optimus)"),
    62: ("lamps.py:207", "match", "as 46"),
    70: ("lamps.py:207", "match", "as 46 (+ lamp 59)"),
    79: ("lamps.py:242", "match", "hit counts solid / rest every 3 ticks; super: group 0x3d (12-15) on then off every 8 ticks (9164/941c): the game's SUPER_SWEEP order equals group 61"),
    87: ("lamps.py:242", "match", "as 79 (3 lamps a shot)"),
    47: ("lamps.py:226", "match", "coilgroup_pulse(18, 0x20) every 8 ticks while valid and no ball search (QA M6)"),
    55: ("lamps.py:226", "match", "coil group 22, as 47"),
    63: ("lamps.py:226", "match", "coil group 26, as 47"),
    71: ("lamps.py:226", "match", "coil group 31, as 47"),
}
ARG_LAMP = {27, 28, 29, 97, 98, 100, 101, 139, 141, 143, 145, 162, 169, 171}     # draw the lamp passed at +0x30
GI_LEFFS = sorted(n for n, d in OPS.items() if any(f.get("gi") is not None for f in d["frames"]))
STATE_DESC = {
    20: "music-synced GI / effect task (0x01006f1c reads sound state 0x040c5edc)",
    32: "Super pops lit: coil_pulse_fn patterns (table 0x040c751c) every 4 ticks while valid, no ball search",
    40: "Allspark banked: coil 0x20 PWM patterns (0x040c6ff4) every 4 ticks", 44: "flasher 0x1f patterns (0x040c72f4) every 4 ticks",
    52: "flasher patterns every 4 ticks (coil group 20)", 60: "flasher patterns every 4 ticks (coil group 25)",
    68: "flasher patterns every 4 ticks (coil group 30)", 77: "flasher patterns (coil group 34)", 80: "flasher patterns (coil group 35)",
    85: "flasher patterns (coil group 36)", 88: "flasher patterns (coil group 37)", 124: "flasher patterns (coil group 46)",
    148: "flasher patterns (coil group 14)", 154: "Super spinner lit: patterns 0x040c7680 every 4 ticks",
    157: "flasher patterns (coil group 48)", 160: "flasher patterns (coil group 49)", 176: "flasher patterns (coil group 56)",
    177: "flasher patterns (coil group 57)", 34: "combo arrows (game: never started, as the ROM)",
}


def show_counts(name):
    """(lamp entries, coil pulses) as the packaged yaml holds them, and as tf.lamps.parse_show reads them."""
    path = os.path.join(SHOWS, name + ".yaml")
    text = open(path, encoding="utf-8").read()
    raw_l = len(re.findall(r'^    l_\w+: "[0-9a-f]{6}"$', text, re.M))
    raw_c = len(re.findall(r"pulse_ms:", text))
    steps = parse_show(path)
    return raw_l, raw_c, sum(len(s[1]) for s in steps), sum(len(s[2]) for s in steps)


HAND_ROWS = r"""id,element,kind,rom_address,rom_value,game_location,game_value,verdict,proof
L-G01,leff show playback (all 113 packaged shows),engine,0x00007c10,each leff's lamps per tick (leff_ops lift; shows lampfx_NNN.yaml write colours as "ffffff" / "7f7f7f" / "000000"),game/tf/lamps.py:78,"parse_show's colour regex accepts only unquoted or single-quoted values: 0 lamp entries parsed from all 113 shows, so no leff lights or clears any lamp (flasher pulses still parsed)",differs,confirmed: probe test_L_show_lamps_parsed (0 of 113) and test_L_attract_leff1 / test_L_leff_shows_in_game (layers empty while the ROM lights 17-27 lamps)
L-G02,flash phase of flashing inserts,engine,0x000073cc,"lamp_compositor_tick: counter 0x0003148c reloaded with 10, phase 0x00031490 inverted when it reaches 0; called once per 16 ms tick (main loop 0x0002bd48): 10 ticks on, 10 off (0.32 s period)",game/tf/lamps.py:27,"FLASH_TICKS = 5: 5 ticks on, 5 off (0.16 s period)",differs,confirmed: decompile 0x000073cc lines 7069-7072; probe test_L_flash_phase (0.08 s phases vs 0.16 s)
L-G03,lamp brightness levels (two planes),engine,0x000113fc,"two 10-byte planes per image; the strobe 0x000113fc shows plane 0 for 1 pass and plane 1 for 2 passes (1 << plane): one plane only = 1/3 or 2/3 brightness, both = full",game/tf/lamps.py:141,"binary: any colour other than 000000 is full on (ShowPlayer), output white or black (lamps.py:598)",differs,code-proven: 0x000113fc; levels 1/2 used by leffs 1 37 95 147 151 (leff_ops frames)
L-G04,leff start arbitration,engine,0x00007c10,"conflict when the lamp groups (0x00009570, table 0x040d1510) or coil groups (0x0000611c, 0x040cf65c) of the new and a running leff share a member; the new one is refused if its priority is lower, or equal and the running leff's flags & 2 = 0; otherwise every conflicting running leff is killed (0x0000b7e4)",game/tf/display.py:618,"refused only while a running leff with a strictly higher priority pulses one of its flashers; lamp groups ignored; a lower conflicting leff keeps running (layers); equal priority never refuses",differs,code-proven: leff_start decompile lines 7598-7631
L-G05,same leff started again,engine,0x00007c10,"a leff with lamp group 0 and coil group 0 never conflicts, even with itself: a second task runs beside the first; one with groups conflicts with itself (equal priority: refused unless its flags & 2, then killed and restarted)",game/tf/display.py:635,"always stops the running copy and restarts it",differs,code-proven: leff_start (0x00009570 / 0x0000611c return 0 for group 0)
L-G06,lamp rule leffs outside play,engine,0x000177b4,"a list-3 rule is evaluated only when gf_state 0x00031468 is 0 or & its mask (0x20 or 0); otherwise nothing is done: the leff keeps its state",game/tf/os_layer.py:485,"active_game false in attract, end of ball and bonus: every rule leff is stopped (leff_stop)",differs,code-proven: leff_start_user_177b4; whether the end of ball kills these leff tasks by another path not traced
L-G07,GI switched by leffs,engine,0x000314c4,"29 leffs switch the GI on and off (leff_ops frames gi: 9 11 12 20 43 45 48-50 53 56-58 61 64-66 69 72-74 81 82 89 90 164 166-168 178; owner 0x000314c4)",game/tf/vpx_hardware.py:23,"no GI output in MPF (comment: the extraction found no GI output); GI always on",missing,code-proven: leff_lift.py GI_OWNER / GI_BITS; leff_ops frames
L-G08,lamp group cleared under a leff,engine,0x00007c10,"a leff whose record names a lamp group gets the group's lamps cleared in the override planes 0x00036394 with the mask 0x000363a8 set (0x000084cc, 0x000086d4): off under the effect (leffs 92 99 102 120 142 146 158 163 172)",game/tf/lamps.py:474,"layer mask = the lamps named in the show (empty after L-G01); no lamp groups in the game (no rom_group_N tags)",missing,code-proven: leff_start lines 7652-7655
L-G09,a deff's exit kills its leff,engine,0x0000b7e4,"each deff that starts a leff kills it in its exit path (0x0000b7e4, 87 call sites with the deff's leff id)",game/tf/display.py:324,"_end_fg stops the deff's leffs (timing.json / UNCAPTURED) when the deff ends",match,code-proven: BL scan of 0x0000b7e4 (r0 immediates = the deff-started leff ids)
L-G10,one-shot leff length,engine,0x040cfe00,"each leff task ends when its function returns (end_tick of the lift at 16 ms)",game/tf/display.py:606,"ends after run_ms of lamp_effects.csv (end_tick x 16.0 ms)",match,lamp_effects.csv end_tick / run_ms (read by display.Leffs)
L-G11,lead-in of looping shows,engine,0x040cfe00,"a looping leff runs its lead-in (e.g. leff 95: 15 ticks, 1: 5, 6: 15, 76 / 84: 15) before the repeating cycle",rom/tools/leff_package.py:5,"the package writes one cycle only; the game starts on the cycle (lead-in left out)",differs,leff_package.py docstring; lamp_effects.csv note column
L-G12,ROM routine citations in lamps.py,engine,0x00007858,"tf_180 lamp API: on 0x000077a0, off 0x0000765c, on + flash bit cleared 0x00007858, off + flash bit cleared 0x00007714, flash bit 0x00007814 on 0x00036388, toggle 0x000078dc",game/tf/lamps.py:349,"cites lamp_on_solid [0x83f4], lamp_off_all [0x82b0], FUN_01015094 (Tron 1.74 addresses; in tf_180 0x83f4 is inside a group routine, 0x82b0 inside strcmp_user_8294)",differs,decompile lines 7195-7380
L-G13,lamp off keeps the flash bit,engine,0x00007714,"the ROM lamp rules write off and solid with 0x00007714 / 0x00007858, which clear the flash bit",game/tf/features/energon.py:101,"rules call lamp_on / lamp_off, which keep the flash bit: an insert that flashed keeps flashing once 'on' (energon lit target, completed battle insert)",differs,confirmed: probes test_L_energon_lit_solid (state 2 vs 1) and test_L_battle_completed_solid (2 vs 1)
L-R01,lamp rule 0x010024dc (lamp 30),lamp_rule,0x010024dc,"list-4 rule (mask 0x20, registered 0x01002650): leaf_18b4() is always 1, so lamp 30 BUMBLEBEE (CAPTIVE BALL) is on with its flash bit: flashing all game",game/tf/features/battles.py:1081,"lamp 30 drawn only as the Bumblebee battle's orange shot (ORANGE[BEE]): flashing while that shot is lit, else off",differs,code-proven: decompile 47418-47445
L-R02,lamp rule 0x0100b228 (lamps 29 57 58),lamp_rule,0x0100b228,"list-4 rule (mask 0x20): when error_log_user_b0b8 (no Megatron / Optimus / wizard mode running and mtl_lit 0x02111d50 set) lamps 29 CHALLENGE MEGATRON, 57, 58 MEGATRON flash; else off with flash cleared",-,"no rule draws 29 / 57 / 58 (lit locks are not shown)",missing,code-proven: decompile 54712-54750; grep of game/tf for these lamps
L-R03,lamp rule 0x01022854 (mode start arrows),lamp_rule,0x01022854,"table 0x040c6d00 (5 shots: red / purple 14/13 18/17 45/46 33/32 38/37): mode_start_lit 0x02111eec & bit and clu_start_allowed: the side's lamp flashes, the other off; (unused mask 0x02111f0c: solid); else both off",game/tf/features/battles.py:1070,"MS_LAMPS: allowed and ms_lit bit: the side's lamp flashes, the other off; else off",match,code-proven: decompile 70876-70930; battles.md 0x02111f0c never set
L-R04,lamp rule 0x01023a84 (X lamps),lamp_rule,0x01023a84,"table 0x040c6f58 entries 1-6 (lamps 12 16 47 43 31 36): solid (0x00007858) when the shot's multiplier byte >= 2, else off (0x00007714)",game/tf/features/combos.py:104,"only the roving 3X leff 39 toggles one X lamp; nothing lights the X lamp of a shot at 2X / 3X",missing,code-proven: decompile 71909-71930; table bytes read from the ROM
L-R05,lamp rule 0x0102ede0 (2-bank 20 21),lamp_rule,0x0102ede0,"lamps 21 / 20 (table 0x040c756d): off during a multiball or timed mode (0x0102e994); else a target not hit (0x02112098) flashes, a hit one solid",-,"no rule draws 20 / 21",missing,code-proven: decompile 80783-80810
L-R06,lamp rule 0x01030f80 (Energon 48 54 35),lamp_rule,0x01030f80,"during a multiball (0x0103096c false) all three off (0x00007714); else unlit on + flash, lit solid (0x00007858)",game/tf/features/energon.py:96,"unlit flash, lit lamp_on (keeps flash, L-G13); no multiball case: they keep flashing in a multiball",differs,confirmed: probes test_L_energon_multiball ([2 2 2] vs [0 0 0]) and test_L_energon_lit_solid
L-R07,lamp rule 0x01035ea8 (requirement inserts),lamp_rule,0x01035ea8,"11 lamps of table 0x040c7a14 (27 7 6 5 4 22 23 24 25 26 28) from the requirement words 0x0211210c: completed byte set: solid; else started byte: flashing; else off",game/tf/features/battles.py:1088,"the 8 battle inserts (7 6 5 4 23 24 25 26) from battle_started / battle_completed; completed keeps flashing (L-G13); Megatron 27, Optimus 22, Sentinel 28 not drawn",differs,confirmed for the solid state: probe test_L_battle_completed_solid; code-proven for 27 / 22 / 28 (grep)
L-R08,shoot again lamp,lamp_rule,0x0001801c,"flag 9: on + flash; extra balls pending (0x00031614): solid; else off",game/tf/os_layer.py:513,"flag 9 flash; extra_balls: lamp_on_solid; else lamp_off",match,code-proven: decompile ball_start_sub_1801c
L-R09,extra ball lamp 55,lamp_rule,0x000182ac,"flashing while the player's extra ball is lit, else off",game/tf/os_layer.py:525,"eb_lit: lamp_flash, else lamp_off",match,code-proven (QA F3 pass)
L-R10,start button lamps,lamp_rule,0x00019a0c,"task 0x2d: lamp 1 (credit) and lamp 2 TOURNAMENT START (tournament allowed) 8 ticks on / 8 off in attract; 0x00019b28 solid with credit",game/tf/os_layer.py:1050,"lamp 1 as the ROM; lamp 2 never lit (tournament not modelled)",differs,code-proven: decompile error_log_user_19a0c
L-I01,START BUTTON (1),insert,0x00019a0c,blink 8/8 in attract with credit; solid in game with credit,game/tf/os_layer.py:1050,same,match,L-R10
L-I02,TOURNAMENT START BUTTON (2),insert,0x00019a0c,blinks with lamp 1 when a tournament is allowed (DAT_00030e9d),-,never lit,missing,L-R10; tournament not modelled
L-I03,ROLL OUT / shoot again (3),insert,0x0001801c,L-R08 plus leffs 13 / 14 blinking it during multiball / ball save,game/tf/os_layer.py:513,same (leffs 13 / 14 by code),match,L-R08; leff_013 / leff_014 compared
L-I04,DEVASTATOR (4),insert,0x01035ea8,requirement 4: solid completed / flashing started / off,game/tf/features/battles.py:1088,"battle bits; completed stays flashing",differs,L-R07 / L-G13
L-I05,BLACKOUT (5),insert,0x01035ea8,requirement 3,game/tf/features/battles.py:1088,completed stays flashing,differs,L-R07 / L-G13
L-I06,SHOCKWAVE (6),insert,0x01035ea8,requirement 2,game/tf/features/battles.py:1088,completed stays flashing,differs,L-R07 / L-G13
L-I07,STARSCREAM (7),insert,0x01035ea8,requirement 1,game/tf/features/battles.py:1088,completed stays flashing,differs,confirmed: probe test_L_battle_completed_solid (insert 7)
L-I08,LEFT OUTLANE (8),insert,0x0102db28,"lane lamp on (0x000077a0, both planes) when its lane is made, group 76 cleared at completion; leff 97 / 98 blink it",game/tf/features/lanes.py:56,"lit set solid, cleared at completion (the blink leffs 97 / 98 draw nothing: L-097, L-098)",match,code-proven: 0x0102db28 / 0x0102e208 (0x000077a0 both planes)
L-I09,LEFT RETURN LANE (9),insert,0x0102db28,as 8,game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I10,RIGHT RETURN LANE (10),insert,0x0102e208,as 8 (group 77),game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I11,RIGHT OUTLANE (11),insert,0x0102e208,as 8 (group 77),game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I12,ALLSPARK (X) (12),insert,0x01023a84,solid at 2X+ (L-R04); roving 3X blink (leff 39),game/tf/features/combos.py:104,roving blink only,missing,L-R04
L-I13,ALLSPARK (PURPLE) (13),insert,0x01022854,mode start arrow (L-R03),game/tf/features/battles.py:1070,same,match,L-R03
L-I14,ALLSPARK (RED) (14),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I15,ALLSPARK (ORANGE) (15),insert,0x010188cc,"battle shot: the battle's rule leff (106 110 114 118 123 128 132 136) toggles the lit shots' groups every 3 ticks on its layer (prio 8), unlit shots forced off; mode rule leffs 46/54/62/70 likewise",game/tf/features/battles.py:1081,"lamp_flash on the game image at the compositor phase (5 ticks, L-G02) under the rule leffs, which draw nothing (L-G01)",differs,code-proven: leff_106 0x010188cc (task_sleep 3)
L-I16,LEFT ORBIT (X) (16),insert,0x01023a84,X lamp (L-R04),game/tf/features/combos.py:104,roving blink only,missing,L-R04
L-I17,LEFT ORBIT (PURPLE) (17),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I18,LEFT ORBIT (RED) (18),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I19,LEFT ORBIT (ORANGE) (19),insert,0x010188cc,battle shot (as 15),game/tf/features/battles.py:1081,as 15,differs,as L-I15
L-I20,RIGHT 2 BANK TARGET BOT (20),insert,0x0102ede0,L-R05,-,not drawn,missing,L-R05
L-I21,RIGHT 2 BANK TARGET TOP (21),insert,0x0102ede0,L-R05,-,not drawn,missing,L-R05
L-I22,OPTIMUS PRIME (22),insert,0x01035ea8,requirement 5 (L-R07),-,not drawn,missing,L-R07
L-I23,BUMBLEBEE (23),insert,0x01035ea8,requirement 6,game/tf/features/battles.py:1088,completed stays flashing,differs,L-R07 / L-G13
L-I24,IRONHIDE (24),insert,0x01035ea8,requirement 7,game/tf/features/battles.py:1088,completed stays flashing,differs,L-R07 / L-G13
L-I25,MUDFLAP / SKIDS (25),insert,0x01035ea8,requirement 8,game/tf/features/battles.py:1088,completed stays flashing,differs,L-R07 / L-G13
L-I26,RATCHET (26),insert,0x01035ea8,requirement 9,game/tf/features/battles.py:1088,completed stays flashing,differs,L-R07 / L-G13
L-I27,MEGATRON (27),insert,0x01035ea8,requirement 0,-,not drawn,missing,L-R07
L-I28,SENTINEL PRIME (28),insert,0x01035ea8,requirement 10,-,not drawn,missing,L-R07
L-I29,CHALLENGE MEGATRON (29),insert,0x0100b228,"flashing while a lock is lit (L-R02); Megatron / Optimus mode shot (rule leffs 46 62 70)",game/tf/lamps.py:207,"only the mode rule leffs' code (shot_blink) draw it",missing,L-R02
L-I30,BUMBLEBEE (CAPTIVE BALL) (30),insert,0x010024dc,flashing all game (L-R01),game/tf/features/battles.py:1081,Bumblebee battle shot only,differs,L-R01
L-I31,RIGHT RAMP (X) (31),insert,0x01023a84,X lamp,game/tf/features/combos.py:104,roving blink only,missing,L-R04
L-I32,RIGHT RAMP (PURPLE) (32),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I33,RIGHT RAMP (RED) (33),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I34,RIGHT RAMP (ORANGE) (34),insert,0x010188cc,battle shot,game/tf/features/battles.py:1081,as 15,differs,as L-I15
L-I35,ENERGON (RIGHT) (35),insert,0x01030f80,L-R06,game/tf/features/energon.py:96,L-R06,differs,L-R06
L-I36,RIGHT ORBIT (X) (36),insert,0x01023a84,X lamp,game/tf/features/combos.py:104,roving blink only,missing,L-R04
L-I37,RIGHT ORBIT (PURPLE) (37),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I38,RIGHT ORBIT (RED) (38),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I39,RIGHT ORBIT (ORANGE) (39),insert,0x010188cc,battle shot,game/tf/features/battles.py:1081,as 15,differs,as L-I15
L-I40,CENTER LANE (ORANGE) (40),insert,0x010188cc,battle shot,game/tf/features/battles.py:1081,as 15,differs,as L-I15
L-I41,CENTER LANE (RED) (41),insert,-,"no list-4 rule or constant write: drawn only by leffs (79 / 87 shot groups, attract)",game/tf/lamps.py:242,wizard rule leffs by code,match,lamp groups 54 / 64 vs wizard.py SIDE_LAMPS / WMB_LAMPS
L-I42,CENTER LANE (PURPLE) (42),insert,-,as 41,game/tf/lamps.py:242,as 41,match,as L-I41
L-I43,CENTER LANE (X) (43),insert,0x01023a84,X lamp,game/tf/features/combos.py:104,roving blink only,missing,L-R04
L-I44,LEFT RAMP (ORANGE) (44),insert,0x010188cc,battle shot,game/tf/features/battles.py:1081,as 15,differs,as L-I15
L-I45,LEFT RAMP (RED) (45),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I46,LEFT RAMP (PURPLE) (46),insert,0x01022854,mode start arrow,game/tf/features/battles.py:1070,same,match,L-R03
L-I47,LEFT RAMP (X) (47),insert,0x01023a84,X lamp,game/tf/features/combos.py:104,roving blink only,missing,L-R04
L-I48,ENERGON (LEFT) (48),insert,0x01030f80,L-R06,game/tf/features/energon.py:96,L-R06,differs,confirmed: probes test_L_energon_lit_solid / test_L_energon_multiball
L-I49,TOP LANE (RED/BOT) (49),insert,0x0102e208,as 8 (group 77),game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I50,TOP LANE (PURPLE/BOT) (50),insert,0x0102db28,as 8 (group 76),game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I51,TOP LANE (PURPLE/TOP) (51),insert,0x0102db28,as 8,game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I52,TOP LANE (RED/TOP) (52),insert,0x0102e208,as 8,game/tf/features/lanes.py:56,as 8,match,as L-I08
L-I53,SPECIAL (53),insert,0x01008528,flashing while lit (0x01008528); off at collect (0x01008684),game/tf/os_layer.py:1626,same,match,code-proven (QA F2 pass)
L-I54,ENERGON (CENTER) (54),insert,0x01030f80,L-R06,game/tf/features/energon.py:96,L-R06,differs,L-R06
L-I55,EXTRA BALL (55),insert,0x000182ac,L-R09,game/tf/os_layer.py:525,same,match,L-R09
L-I56,LAMP #56,insert,-,no writer found (no constant write; not in any lamp group),-,never driven,match,lamp_groups.json; BL scan of the lamp API
L-I57,MEGATRON (BOTTOM) (57),insert,0x0100b228,flashing while a lock is lit (L-R02),-,not drawn,missing,L-R02
L-I58,MEGATRON (TOP) (58),insert,0x0100b228,flashing while a lock is lit (L-R02),-,not drawn,missing,L-R02
L-I59,OPTIMUS PRIME CHALLENGE (59),insert,0x01027024,"drawn by leffs only: 54 / 70 (mode shot), 177 (group 143, battle done), 172 (arg)",game/tf/lamps.py:207,"54 / 70 by code; 177 and 172 draw nothing",differs,L-177; lamp group 143
L-I60,TOP BUMPER (60),insert,0x0102d138,"pop leff 27 blinks it (arg lamp from table 0x040c74d4): toggled every 3 ticks x4, then plane 2 / plane 1 phases",-,not drawn (L-027),missing,code-proven: leff_029 0x0102d138
L-I61,RIGHT BUMPER (61),insert,0x0102d138,pop leff 28 (as 60),-,not drawn,missing,as L-I60
L-I62,BOTTOM BUMPER (62),insert,0x0102d138,pop leff 29 (as 60),-,not drawn,missing,as L-I60
L-I63,LAMP #63-#80 (unused outputs),insert,-,"no rule or group drives them; only the attract leff 1 writes them (off)",-,never driven,match,leff_001.json lamps; lamp_groups.json
"""

rows = []


def row(i, element, kind, addr, rom_value, loc, game_value, verdict, proof):
    rows.append(dict(id=i, element=element, kind=kind, rom_address=addr, rom_value=rom_value, game_location=loc,
                     game_value=game_value, verdict=verdict, proof=proof))


for n in sorted(LEFFS):
    r = LEFFS[n]
    starters = rom_start.get(n, [])
    gstart = GAME.get(n)
    gi = n in GI_LEFFS
    if r["show"]:
        raw_l, raw_c, got_l, got_c = show_counts(r["show"])
    else:
        raw_l = raw_c = got_l = got_c = 0
    rom_draw = []
    if raw_l:
        rom_draw.append("%d lamp writes over %s steps (%s lamps)" % (raw_l, r["steps"], r["lamps_used"]))
    if raw_c:
        rom_draw.append("%d flasher pulses" % raw_c)
    if n in ARG_LAMP:
        rom_draw.append("blinks the lamp its caller passes (+0x30)")
    if n in STATE_DESC:
        rom_draw.append(STATE_DESC[n])
    if gi:
        rom_draw.append("switches the GI")
    if not rom_draw:
        rom_draw.append("no output (%s)" % r["note"])
    rom_value = "prio %s, %s; starters: %s; draws: %s" % (
        r["priority"], "until stopped" if r["loops"] else "%s ticks" % (r["end_tick"] or "0"),
        " | ".join(starters) if starters else "none found", "; ".join(rom_draw))
    if n in CODE_LEFFS:
        loc, verdict, how = CODE_LEFFS[n]
        game_value = "starter: %s; drawn by code: %s" % (gstart or "none", how)
        draws_ok = True
        loc = "game/tf/" + loc if not loc.startswith("game/") else loc
    else:
        loc = "game/tf/lamps.py:78" if r["show"] else "game/tf/lamps.py:463"
        draws = []
        if r["show"]:
            draws.append("show %s parsed: %d of %d lamp entries, %d of %d pulses" % (r["show"], got_l, raw_l, got_c, raw_c))
        else:
            draws.append("no show, no leff_code: draws nothing")
        game_value = "starter: %s; %s" % (gstart or "none", "; ".join(draws))
        draws_ok = (got_l == raw_l and got_c == raw_c and n not in ARG_LAMP and n not in STATE_DESC and not gi)
    if not starters and not gstart:
        verdict, proof = "match", "never started in the ROM (decompile + BL scan) nor in the game"
        if n == 149:
            verdict, proof = "unverifiable", "start_leff_149 0x010019c8 (5,000, 0x267, leff 149) has no BL caller nor aligned pointer: caller unknown; game never starts it"
    elif starters and not gstart:
        verdict = "missing"
        proof = "ROM starts it (%s); no start in game/tf" % starters[0].split(" (dec")[0]
    elif gstart and not starters:
        verdict, proof = "extra", "game starts it; no leff_start / rule / deff op in the ROM"
    else:
        verdict = "match" if draws_ok else "differs"
        proof = "starters both sides; " + ("drawing compared with the ROM function" if n in CODE_LEFFS else
                                          "parse_show regex misses double-quoted colours (lamps.py:78); probe test_L_show_lamps_parsed" if raw_l and not got_l
                                          else "nothing drawn for a leff the ROM draws from state/arg/GI" if not draws_ok
                                          else "show = lift (pulses parsed)")
    if n == 149:
        verdict, proof = "unverifiable", ("start_leff_149 0x010019c8 (5,000, sound 0x267, leff 149) has no BL caller and no "
                                          "aligned pointer to it: its caller is unknown; the game never starts leff 149")
    if n in (76, 77):
        verdict, proof = "differs", "rule 0x01011ed4 starts 76/77 on zuse_qualify_enabled for either side; game Autobot only (open QA M8); also draws (G01)"
    if n in (92, 95):
        verdict = "differs"
        proof = ("ROM: lamp rule (cond %s) starts and stops it; game: leff_start at ball start only (side.py:75), "
                 "never stopped by a rule; draws nothing (G01)") % ("task_running_wrap_314ac" if n == 92 else "side_choice_running")
    if n in (18, 19):
        proof += "; tournament / ticket awards not modelled"
    if n in (2, 3, 4, 5, 6, 7, 8):
        proof += "; service menu / lamp tests (start_leff_N in 0x0104xxxx, deff 3) not in the game (no tf_service mode)"
    sev = ""
    row("L-%03d" % n, "leff %d (%s)" % (n, r["fn"]), "leff", r["fn"], rom_value,
        loc, game_value, verdict, proof)

# ---------------------------------------------------------------- lamp groups (table 0x040d1510)
game_tuples = set()
for p in glob.glob(os.path.join(ROOT, "game", "tf", "**", "*.py"), recursive=True):
    for m in re.finditer(r"[\(\[]((?:\s*\d{1,2}\s*,){1,30}\s*\d{1,2}\s*,?)\s*[\)\]]", open(p).read()):
        nums = tuple(int(x) for x in m.group(1).replace(" ", "").strip(",").split(","))
        if all(1 <= x <= 80 for x in nums):
            game_tuples.add((frozenset(nums), os.path.relpath(p, ROOT)))
leff_group_users = collections.defaultdict(list)
for n, r in LEFFS.items():
    if int(r["lamp_group"] or 0):
        leff_group_users[int(r["lamp_group"])].append(n)
GROUP_DIRECT = {  # constant group arguments to the 28 group functions (BL scan, r0 immediate): site -> user
    1: "0x010089f0 lampgroup_count", 2: "0x01007ee4, 0x01009964", 3: "18 sites, e.g. 0x01007ebc (leffs 43, 61...)",
    4: "18 sites, e.g. 0x01007e90", 22: "0x01023c34 group toggle (leff 36 X lamps)", 52: "leff 76 0x01010474 (sweep)",
    54: "leff 79 0x01010780", 61: "leff 79 0x010109e8 (super sweep)", 62: "leff 84 0x010368dc (sweep)",
    64: "leff 87 0x01036ce8", 71: "leff 87 0x010370a8 (super sweep)", 76: "lanes 0x0102db18 (left lanes complete)",
    77: "lanes 0x0102e1f8 (right lanes complete)", 78: "leff 34 0x01003190 (combo arrows)", 136: "leff 147 0x0102ef10",
    137: "leff 151 0x01002580", 143: "leff 176/177 0x01026f78", 145: "leff 95 0x010340b4", 146: "leff 95 0x010340c4",
    147: "leff 104 0x01023194"}
CODE_EQUIV = {54: "wizard.py SIDE_LAMPS (leff 79 code)", 61: "wizard.py:60 SUPER_SWEEP (leff 79 code)",
              71: "wizard.py:60 SUPER_SWEEP (leff 87 code)", 64: "wizard.py WMB_LAMPS (leff 87 code)",
              76: "lanes.py:21 GROUPS left (completion test and clear)", 77: "lanes.py:21 GROUPS right"}
for g in sorted(GROUPS):
    lamps = GROUPS[g]
    users = []
    if g in leff_group_users:
        users.append("leff table group of leff %s (cleared under it, leff_start 0x00007c10)" % leff_group_users[g])
    if g in GROUP_DIRECT:
        users.append("constant argument at " + GROUP_DIRECT[g])
    same = sorted({f for s, f in game_tuples if s == frozenset(lamps)}) if lamps else []
    if g in CODE_EQUIV:
        same = sorted(set(same) | {CODE_EQUIV[g]})
    if g == 0:
        verdict, gv, proof = "match", "empty group (no lamps)", "group 0 is empty; leff_start skips group 0"
    elif not users:
        verdict = "unverifiable"
        gv = "no rom_group_N light tags (game/config/rom/lights.yaml): Lamps.group(%d) = []" % g + (
            "; same lamp set hard-coded in %s" % ", ".join(same) if same else "")
        proof = "users only through tables (r0 from a register at 98 BL sites); agent A to list each group's users"
    else:
        verdict = "match" if g in CODE_EQUIV else "missing"
        if g in leff_group_users and g not in CODE_EQUIV:
            users.append("game: no group cleared under a leff (L-G08)")
        gv = ("same lamp set in %s" % ", ".join(same)) if g in CODE_EQUIV else \
            ("no rom_group_N tags: Lamps.group(%d) = []" % g) + (
                "; the same lamp list exists in %s but not for this ROM use" % ", ".join(same) if same else "")
        proof = "; ".join(users)
    row("L-GRP-%03d" % g, "lamp group %d" % g, "lamp_group", "0x040d1510", "lamps %s" % lamps,
        "game/tf/lamps.py:410", gv, verdict, proof)

# ---------------------------------------------------------------- engine-level rows and inserts (by hand)
import io  # noqa: E402
for r in csv.DictReader(io.StringIO(HAND_ROWS)):
    rows.append(r)

with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "element", "kind", "rom_address", "rom_value", "game_location",
                                      "game_value", "verdict", "proof"])
    w.writeheader()
    hand = [r for r in rows if not r["id"].startswith(("L-0", "L-1", "L-GRP"))]
    rest = [r for r in rows if r not in hand]
    for r in hand + rest:
        w.writerow(r)
print("rows", len(rows), collections.Counter(r["verdict"] for r in rows))
print("leffs", collections.Counter(r["verdict"] for r in rows if r["kind"] == "leff"))
print("groups", collections.Counter(r["verdict"] for r in rows if r["kind"] == "lamp_group"))
