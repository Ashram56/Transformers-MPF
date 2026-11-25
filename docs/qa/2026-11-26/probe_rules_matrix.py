"""QA 2026-11-26 (scope R): build matrix_rules.csv from the two probes' outputs and this pass's readings.

Inputs (OUTDIR from probe_rules_marks.py; ADDR from probe_rules_addresses.py):
  .venv/bin/python docs/qa/2026-11-26/probe_rules_marks.py OUTDIR switches game_flow scoring combos \
      allspark_energon megatron_autobot optimus_autobot battle_blackout wizard_multiball
  .venv/bin/python docs/qa/2026-11-26/probe_rules_addresses.py > ADDR
  .venv/bin/python docs/qa/2026-11-26/probe_rules_matrix.py OUTDIR ADDR > docs/qa/2026-11-26/matrix_rules.csv
Sections: R-SW (switch_handlers.csv rows), R-CR (code_runs.csv marks of the replayed scenarios), R-DG
(functional_diagram.md nodes), R-AD (distinct ROM addresses cited in game/), R-K (tick constants).
"""
import csv
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HDR = ["id", "element", "kind", "rom_address", "rom_value", "game_location", "game_value", "verdict", "proof"]
SCEN = ["switches", "game_flow", "scoring", "combos", "allspark_energon", "megatron_autobot", "optimus_autobot",
        "battle_blackout", "wizard_multiball"]

# ---------------------------------------------------------------- R-SW: causes of the switch-row differences
SW_NOTE = {
    ("2", "first"): ("differs", "flags: event 0x6a hook LAB_010060a4 sets game flag 0x10 and on_event_6a_3bcf4 [0x0103bcf4] clears 0xc/0xd; game sets 0x1c citing [0x0100f25c] (Tron; inside ram_00001d80_user) os_layer.py:1008 (R-F4)"),
    ("4", "first"): ("missing", "snd_play(0x273) first in sw_l_ramp_entrance [0x010337e8]; switches.py:87 only sets timer 0xc (R-F1)"),
    ("4", "repeat"): ("missing", "same as first hit (R-F1)"),
    ("35", "first"): ("missing", "snd_play(0x272) first in sw_r_ramp_entrance [0x010338dc] (R-F1)"),
    ("35", "repeat"): ("missing", "same as first hit (R-F1)"),
    ("5", "first"): ("differs", "deff_091_0_more [0x01022608] picks 0x170..0x177 by the lit battle bit (task+0x38 = DAT_02111ecc[p], set by start_deff_91 [0x01020074]); battle_lit 4 -> 0x172; game MS_SOUND by side only battles.py:71/908 (R-F2); flashers 18/21/23 x18 (leff 103) vs x6 (lamps scope, R-F7)"),
    ("10", "first"): ("differs", "as sw 5 first: 0x172 vs 0x170 (R-F2); leff 103 flasher count (R-F7)"),
    ("12", "repeat"): ("differs", "as sw 5 first: 0x172 vs 0x170 (R-F2); leff 103 flasher count (R-F7)"),
    ("11", "first"): ("differs", "leff 170 [0x010264b8] pulses coil group 53 (coil 31, 100 ms) 17 times, game once (R-F7)"),
    ("11", "repeat"): ("differs", "as first (R-F7)"),
    ("25", "first"): ("differs", "deff 44 plays 0x059 then speech 0x05a 75 ticks later (task 2); game plays 0x059 only (R-F6)"),
    ("49", "first"): ("differs", "leff 40 [0x01024328] pulses coil 32 (Allspark flash) every 4 ticks via 0x01024364; game none (R-F7)"),
    ("49", "repeat"): ("differs", "leff 40 coil 32 pulses missing (R-F7)"),
    ("50", "first"): ("unverifiable", "code run ends the Blackout battle (0x1cb, deff 103, leff 116) at this hit, 400 ticks before the game and the emulator trace (trace column of switch_handlers.csv agrees with the game); coil 32 as sw 49 (R-F7)"),
    ("50", "repeat"): ("unverifiable", "0x1cc = Blackout timing as above; deff 126 speech 0x264/0x265 is a random pick (trace 0x265, game 0x264); coil 19 x3 vs coil 32 (R-F7)"),
    ("51", "first"): ("differs", "coil 32 leff 40 pulses missing (R-F7); rest equal"),
    ("51", "repeat"): ("unverifiable", "game shows the Blackout end here (0x1cb 0x1cc, deff 103, leff 116) like the emulator; code run had it at sw 50 (timing of the code run); coil 32 (R-F7)"),
}


def sw_rows(out):
    rows = []
    src = {(r["switch"], r["hit"]): r for r in csv.DictReader(open(os.path.join(ROOT, "rom", "rules", "switch_handlers.csv")))}
    for i, r in enumerate(csv.DictReader(open(os.path.join(out, "switch_handlers.cmp.csv"))), 1):
        s = src[(r["switch"], r["hit"])]
        rom = "%s pts; snd %s; deff %s; leff %s; coils %s; audits %s; flags %s" % (
            s["score_total"], re.sub(r"\[[^\]]*\]", "", s["sounds"]).strip() or "-", s["deffs"] or "-",
            s["leffs"] or "-", s["coils"] or "-", s["audit_counters"] or "-", s["flags"] or "-")
        if r["diff"] == "same":
            verdict, note, game = "match", "all columns equal", "%s pts; same sounds/deffs/leffs/coils/audits/flags" % r["game_points"]
        else:
            verdict, note = SW_NOTE.get((r["switch"], r["hit"]), ("differs", ""))
            game = "%s pts; %s" % (r["game_points"], r["detail"])
            if r["diff"] == "deffs" and not note:
                verdict = "match"
        rows.append(["R-SW-%02d" % i, "sw %s %s (%s hit)" % (r["switch"], r["name"], r["hit"]), "switch handler",
                     "0x%08x" % int(s["handler"], 16), rom, "game/tf/switches.py:78 + hooks sw_%s" % r["switch"], game,
                     verdict, "probe_rules_marks.py switches (mark %s; Decepticon side, fresh ball after validating sling, hits 2.19 s apart as rom/tools/switch_lift.py); %s" % (r["mark"], note)])
    return rows


# ---------------------------------------------------------------- R-CR: code_runs marks
CR_NOTE = {
    "speech": "speech / deff-internal sound variant (random pick or deff tail across the mark)",
    "eject": "Allspark mystery draw: code run random_below answers 0 (SPECIAL, deff 55, 0x066/0x067); game replays the emulator's pick (#! random) -> 149; leff 21 is started only when snd_play(0x157) is accepted [0x0100a788 case 7], refused in the code run",
}


RULE_DEFFS = {"101", "58", "40"}      # background deffs the deff rules restart (caller 0x0001794c); the game logs them rule=1
MUSIC = {"0x01d", "0x01e", "0x01f", "0x020", "0x076"}    # music-channel calls (music start / duck), sound scope


def classify(detail):
    """(verdict, proof) for a code_runs mark whose points are equal."""
    code, game = {}, {}
    for part in detail.split("; "):
        m = re.match(r"(\w+) code (.*?) game ?(.*)$", part)
        if m:
            code[m.group(1)] = set(m.group(2).split())
            game[m.group(1)] = set(m.group(3).split())
    notes, rest = [], {}
    for k in code:
        c_only, g_only = code[k] - game[k], game[k] - code[k]
        if k == "deffs":
            if c_only & RULE_DEFFS:
                notes.append("code-only deff %s = rule restart of the background deff (the game logs it rule=1)" % " ".join(sorted(c_only & RULE_DEFFS)))
            c_only -= RULE_DEFFS
            if "149" in g_only or c_only & {"55", "53"}:
                return "unverifiable", "points equal; " + detail + " (" + CR_NOTE["eject"] + ")"
        if k == "leffs" and "21" in g_only:
            notes.append("leff 21 = eject warning, started only when snd_play(0x157) is accepted [0x0100a788 case 7]; refused in the code run, played in the emulator")
            g_only = g_only - {"21"}
        if k == "sounds":
            mus = (c_only | g_only) & MUSIC
            if mus:
                notes.append("music-channel calls %s differ (sound scope)" % " ".join(sorted(mus)))
            c_only, g_only = c_only - MUSIC, g_only - MUSIC
        if c_only or g_only:
            rest[k] = (sorted(c_only), sorted(g_only))
    if "0x172" in str(rest) and "0x170" in str(rest):
        notes.append("R-F2 mode-start sound")
    if "0x05a" in str(rest):
        notes.append("R-F6 deff 44 speech 0x05a")
    if "0x273" in str(rest) or "0x272" in str(rest):
        notes.append("R-F1 ramp entrance sound")
    if not rest:
        return "match", "points equal; only " + "; ".join(notes)
    if "0x1cb" in str(rest) or "0x1cc" in str(rest):
        return "unverifiable", ("points equal; Blackout battle end: the code run ends it about 400 ticks before the "
                                "game and the emulator trace (both agree); %s" % detail)
    if "'76'" in str(rest) or "'80'" in str(rest) or "'82'" in str(rest):
        notes.append("after a RAM poke of the requirements / counters: open M8 (leffs 76/77 [0x01011ed4]) and the poke's rule refresh")
    txt = "; ".join("%s code-only %s game-only %s" % (k, " ".join(a) or "-", " ".join(b) or "-") for k, (a, b) in rest.items())
    if not any(n.startswith("R-F") for n in notes):
        notes.append("speech / deff-internal sound or leff across the mark (sounds / lamps scope)")
    return "differs", "points equal; " + txt + " (" + "; ".join(notes) + ")"


def cr_rows(out):
    rows, n = [], 0
    for sc in SCEN:
        p = os.path.join(out, sc + ".cmp.csv")
        if not os.path.exists(p):
            continue
        code = {(r["scenario"], r["mark"]): r for r in csv.DictReader(open(os.path.join(ROOT, "rom", "rules", "traces", "code_runs.csv")))}
        for r in csv.DictReader(open(p)):
            n += 1
            c = code[(sc, r["mark"])]
            pts_ok = r["code_points"] == r["game_points"]
            if r["diff"] == "same":
                verdict, why = "match", "points, sounds, deffs, leffs equal"
            elif not pts_ok:
                verdict, why = "unverifiable", "points differ only by the random mystery award (code run random_below = 0); " + r["detail"]
            else:
                verdict, why = classify(r["detail"])
            rows.append(["R-CR-%02d" % n, "%s / %s" % (sc, r["mark"]), "scenario mark (code run)", "tick %s" % c["tick"],
                         "%s pts; awards %s; snd %s; deff %s; leff %s" % (c["points"], c["awards"] or "-", c["sounds"] or "-", c["deffs"] or "-", c["leffs"] or "-"),
                         "tests/scenario.py %s" % sc, "%s pts" % r["game_points"], verdict,
                         "probe_rules_marks.py %s vs rom/rules/traces/code_runs.csv; %s" % (sc, why)])
    return rows


# ---------------------------------------------------------------- R-DG: functional diagram nodes
DG = [
    # (section, node, address, label, game_location, verdict, proof)
    ("1", "GS", "0x00019c64", "Game start (event 0x2f, state 0x20, audit 17)", "game/tf/os_layer.py:1105", "match", "game_flow p1_ball1_plunge equal (points, deffs, sounds); no citation of 0x00019c64 in game (R-F9)"),
    ("1", "BS", "0x00019d30", "Ball start (event 0x12, kill tasks 0x80)", "game/tf/os_layer.py:1138", "match", "game_flow all ball starts equal"),
    ("1", "PI", "0x010318cc", "Per-player init, skill counters", "game/tf/features/skill_shot.py:29", "match", "game_flow p1/p2 skill marks equal; address not cited in game"),
    ("1", "PB", "0x01023418", "Per-ball init, shot multipliers", "game/tf/features/combos.py:56", "match", "combos marks points equal; address not cited in game"),
    ("1", "SV", "0x0103b39c", "serve_ball(3)", "game/tf/os_layer.py:1176", "differs", "serve / eject tick constants are Tron-trace values (R-K8), sequence equal in game_flow"),
    ("1", "SK", "0x01031518", "Skill shots armed", "game/tf/features/skill_shot.py:1", "match", "game_flow p1_hands_free_skill_lane, p2_super_skill points equal"),
    ("1", "VP", "0x0000e264", "Valid playfield", "game/tf/os_layer.py:1004", "differs", "flag id 0x1c set instead of the ROM's 0x10 (LAB_010060a4) and 0xc/0xd not cleared (R-F4); points equal"),
    ("1", "VP", "0x00017acc", "Ball save (adj 38)", "game/tf/os_layer.py:1189", "match", "game_flow p1_drain_in_ball_save equal; 312 ticks fixed (F8)"),
    ("1", "TL", "0x0001da8c", "Tilt warning", "game/tf/os_layer.py:1549", "match", "game_flow tilt_warning_1 equal; _2 lacks 0x01e (music duck, low)"),
    ("1", "TL", "0x0001db40", "Tilt", "game/tf/os_layer.py:1562", "match", "game_flow tilt equal"),
    ("1", "EB", "0x00019e44", "End of ball", "game/tf/os_layer.py:1687", "match", "game_flow drains equal; 937-tick wait (F10)"),
    ("1", "EB", "0x01000ffc", "Bonus", "game/tf/features/bonus.py:62", "match", "game_flow p2_drain, scoring after_fast_scoring bonus points equal"),
    ("1", "RO", "0x0001abb4", "Player rotation", "game/tf/os_layer.py:1687", "match", "game_flow p2_* marks equal; not cited in game"),
    ("1", "GO", "0x0001a144", "Game over", "game/tf/features/game_over.py:1", "match", "game_flow game_over equal; not cited in game"),
    ("1", "HS", "0x00018d54", "High score entry", "game/tf/features/high_scores.py:1", "differs", "initials deff cited as Tron 0x010346e8 (tf deff 32 is 0x0103c840) (R-F9); flow not replayed"),
    ("1", "MT", "0x00019668", "Match", "game/tf/features/game_over.py:22", "match", "F9 fixed 2026-11-25; game_flow game_over equal"),
    ("2", "S3", "0x0100a788", "sw 3 Allspark eject", "game/tf/features/allspark.py:106", "match", "allspark_energon collect marks: points equal except the random mystery draw; warning leff 21 per snd_play result [0x0100a788 case 7]"),
    ("2", "S5", "0x01033244", "sw 5/6 left orbit", "game/tf/features/battles.py:964", "differs", "token 7 = 0xbb = 187 ticks [0x01033354/0x010332e4] decremented each tick by 0x0000ff60; game ORBIT_TOKEN_S 2.26 s (R-F3)"),
    ("2", "MS", "0x01020074", "Mode-start shots", "game/tf/features/battles.py:893", "differs", "value min(10,000 x (started+1) + 5,000 x hits, 75,000) [0x0101fd34] equal; sound 0x170 vs battle-lit 0x170-0x177 (R-F2)"),
    ("2", "S10", "0x01033824", "sw 10 left ramp", "game/tf/switches.py:78", "match", "switches sw_10 points equal (sound R-F2)"),
    ("2", "S14", "0x01033918", "sw 14 right ramp", "game/tf/switches.py:78", "match", "switches sw_14 equal"),
    ("2", "S12", "0x01033488", "sw 12 right orbit", "game/tf/features/battles.py:993", "differs", "code: token 7 up -> clear, else task 0x47 (187 ticks, killed by the first sw 12) -> ignore once, else token 9 up -> clear; game: time windows 3.0 s / 187 ticks, repeats inside never clear (R-F3)"),
    ("2", "S11", "0x01025de4", "sw 11 center lane", "game/tf/features/optimus.py:396", "differs", "extra 1.0 s HIT_IGNORE_S not in 0x01025de4 (R-F5); switches sw_11 equal"),
    ("2", "S38", "0x0100a3b8", "sw 38-41 Megatron lock", "game/tf/features/megatron.py:521", "match", "megatron_autobot lock1-4 equal"),
    ("2", "S38", "0x0100a420", "lock score call", "game/tf/features/megatron.py:521", "match", "megatron_autobot lock1-4 points equal"),
    ("2", "S51", "0x010262f0", "sw 51 Optimus target", "game/tf/features/optimus.py:436", "differs", "extra 1.0 s HIT_IGNORE_S (R-F5); optimus_autobot battle_hits points equal"),
    ("2", "SP", "0x01032f8c", "pops", "game/tf/features/pops.py:36", "match", "switches sw_30-32, scoring pops_* equal"),
    ("2", "PO", "0x0102ca98", "Pop value", "game/tf/features/pops.py:6", "match", "scoring pops_fast / pops_after_pause equal"),
    ("2", "PO", "0x0102c8c8", "Pop award", "game/tf/features/pops.py:4", "match", "as above"),
    ("2", "MV", "0x01022cf8", "Move lit battle", "game/tf/features/battles.py:868", "match", "battle_blackout poke/qualify equal points"),
    ("2", "SPIN", "0x01033a08", "spinner", "game/tf/features/spinner.py:1", "match", "switches sw_34, scoring spinner equal"),
    ("2", "SPV", "0x01032294", "Spinner value", "game/tf/features/spinner.py:1", "match", "scoring spinner equal"),
    ("2", "SPV", "0x010320a4", "Spinner award", "game/tf/features/spinner.py:1", "match", "scoring spinner equal"),
    ("2", "BB", "0x01033adc", "Bumblebee target", "game/tf/features/bumblebee.py:1", "match", "switches sw_1, scoring bumblebee points equal (0x27a speech variant)"),
    ("2", "DS", "0x01001a70", "Double scoring", "game/tf/features/bumblebee.py:1", "match", "scoring during/after_double_scoring points equal"),
    ("2", "DS", "0x010039a0", "Double scoring start", "game/tf/features/bumblebee.py:1", "match", "as above"),
    ("2", "TB", "0x01033c00", "2-bank sw 50", "game/tf/features/twobank.py:1", "match", "switches sw_50, scoring two_bank points equal"),
    ("2", "TB", "0x01033c40", "2-bank sw 37", "game/tf/features/twobank.py:1", "match", "switches sw_37 equal"),
    ("2", "FS", "0x0102e9c0", "Fast scoring award", "game/tf/features/twobank.py:73", "match", "scoring during/after_fast_scoring points equal"),
    ("2", "FS", "0x01004394", "Fast scoring start", "game/tf/features/twobank.py:1", "match", "as above"),
    ("2", "EN", "0x010309a4", "Energon", "game/tf/features/energon.py:31", "match", "switches sw_2/46/49, allspark_energon energon_* equal"),
    ("2", "ENC", "0x01030b34", "Set complete -> lock count", "game/tf/features/energon.py:83", "match", "allspark_energon energon_center_completes equal"),
    ("2", "LN", "0x0102db28", "Left lanes", "game/tf/features/lanes.py:32", "differs", "scoring lanes_left: deff 44 speech 0x05a missing (R-F6); points equal"),
    ("2", "LN", "0x0102e208", "Right lanes", "game/tf/features/lanes.py:32", "match", "scoring lanes_right equal"),
    ("2", "SM", "0x010236e8", "Light shot multipliers", "game/tf/features/combos.py:56", "match", "switches sw_25, combos equal points"),
    ("2", "SM", "0x010237ac", "Shot multiplier raise", "game/tf/features/combos.py:56", "match", "P2 fixed; combos equal points"),
    ("2", "CB", "0x01002f0c", "Combo award", "game/tf/features/combos.py:1", "match", "combos 4 marks points equal"),
    ("2", "CB", "0x01002be4", "Combo window start", "game/tf/features/combos.py:43", "match", "DAT_00034b8c = 0x138 (312), task 0x92 steps of 7: WINDOW_TICKS 312, STEP_TICKS 7"),
    ("2", "CB", "0x01002b5c", "Combo window task", "game/tf/features/combos.py:43", "match", "as above"),
    ("2", "CB", "0x040c5c7c", "Combo table", "game/tf/features/combos.py:1", "match", "combos points equal; table not cited in game"),
    ("3", "L0", "0x0100ada4", "Lock level = adj 68", "game/tf/features/megatron.py:382", "match", "megatron_autobot lock marks equal; not cited"),
    ("3", "L0", "0x0100acb4", "Completions needed", "game/tf/features/megatron.py:382", "match", "as above"),
    ("3", "GATE", "0x0100ae6c", "Lock may light", "game/tf/features/megatron.py:451", "match", "megatron_autobot equal"),
    ("3", "CNT", "0x0100af0c", "mtl_count -1, 5,000", "game/tf/features/megatron.py:451", "match", "allspark_energon energon_set2/3 equal"),
    ("3", "ENT", "0x0100b0b8", "Lock entry", "game/tf/features/megatron.py:521", "match", "megatron_autobot lock1-3 equal"),
    ("3", "LCK", "0x0100b130", "BALL n LOCKED, 25,000", "game/tf/features/megatron.py:521", "match", "lock1-3 points equal (lock3 lacks music duck 0x01e, low)"),
    ("3", "MBA", "0x0100c200", "Start A 250,000 deff 69", "game/tf/features/megatron.py:594", "match", "megatron_autobot lock4 equal"),
    ("3", "MBD", "0x0100e0bc", "Start D 100,000 deff 75", "game/tf/features/megatron.py:288", "unverifiable", "megatron_decepticon not replayed in this pass (2026-11-25 modes review)"),
    ("3", "RA", "0x0100c430", "A rules", "game/tf/features/megatron.py:180", "match", "megatron_autobot jackpot/double/super points equal"),
    ("3", "RD", "0x0100e29c", "D rules", "game/tf/features/megatron.py:288", "unverifiable", "not replayed in this pass"),
    ("3", "END", "0x0100c814", "One ball left, grace", "game/tf/features/megatron.py:172", "match", "megatron_autobot drains equal"),
    ("3", "END", "0x0100c790", "Total deff 74/80", "game/tf/features/megatron.py:150", "match", "drains equal"),
    ("3", "LV", "0x0100ad70", "Level +1, relock", "game/tf/features/megatron.py:382", "match", "cited; megatron_autobot drains equal"),
    ("3", "HOLD", "0x0100a1f8", "Device keeps balls", "game/tf/features/megatron.py:1", "match", "cited; megatron_autobot equal"),
    ("4", "CL", "0x01025de4", "Center lane x4", "game/tf/features/optimus.py:396", "differs", "HIT_IGNORE_S 1.0 s not in code (R-F5); optimus_autobot access points equal"),
    ("4", "OB", "0x010262f0", "Optimus battle hits", "game/tf/features/optimus.py:436", "differs", "as above (R-F5)"),
    ("4", "OA", "0x01027994", "Start A", "game/tf/features/optimus.py:458", "match", "optimus_autobot mb_start points equal"),
    ("4", "RA", "0x01027b74", "A rules", "game/tf/features/optimus.py:237", "match", "optimus_autobot jackpot1/double1/super points equal"),
    ("4", "OD", "0x01029a08", "Start D", "game/tf/features/optimus.py:275", "unverifiable", "optimus_decepticon not replayed in this pass"),
    ("4", "RD", "0x01029bf4", "D rules", "game/tf/features/optimus.py:275", "unverifiable", "not replayed in this pass"),
    ("4", "E", "0x01027ec0", "A end, total deff 62", "game/tf/features/optimus.py:210", "match", "optimus_autobot drains equal; not cited"),
    ("4", "E", "0x01029fa4", "D end, total deff 68", "game/tf/features/optimus.py:210", "unverifiable", "not replayed; not cited"),
    ("5", "R", "0x0101fe98", "Reset per player", "game/tf/features/battles.py:893", "match", "cited; battle_blackout qualify equal"),
    ("5", "Q", "0x0101fdac", "Qualifying allowed", "game/tf/features/battles.py:831", "match", "cited"),
    ("5", "Q", "0x01022ca8", "Start allowed", "game/tf/features/battles.py:831", "match", "cited"),
    ("5", "MSH", "0x01020074", "Mode-start shot hit", "game/tf/features/battles.py:893", "differs", "sound (R-F2); diagram label '10,000 + 5,000 x hits' omits + 10,000 x started (code 0x0101fd34; game right)"),
    ("5", "ST", "0x01022e08", "Battle start 100,000", "game/tf/features/battles.py:914", "match", "battle_blackout qualify points equal"),
    ("5", "ST", "0x01035af0", "Wizard item", "game/tf/features/wizard.py:138", "match", "wizard_multiball poke/start equal points"),
    ("5", "RL", "0x0101ffa0", "Relight random unlit shot", "game/tf/features/battles.py:893", "match", "switches sw_5/10/12 equal (random forced); not cited"),
    ("5", "MV", "0x01022cf8", "Move lit battle", "game/tf/features/battles.py:868", "match", "battle_blackout poke_battle_lit_4 equal"),
    ("5", "B1", "0x0101795c", "Starscream", "game/tf/features/battles.py:326", "unverifiable", "battle_starscream not replayed; not cited"),
    ("5", "B2", "0x0101e400", "Shockwave", "game/tf/features/battles.py:355", "unverifiable", "not replayed; not cited"),
    ("5", "B3", "0x0101caa4", "Blackout", "game/tf/features/battles.py:379", "match", "battle_blackout 4 marks points equal; not cited"),
    ("5", "B4", "0x01015dc0", "Devastator", "game/tf/features/battles.py:410", "unverifiable", "not replayed; not cited"),
    ("5", "B5", "0x010142dc", "Bumblebee battle", "game/tf/features/battles.py:450", "unverifiable", "not replayed; not cited"),
    ("5", "B6", "0x0101adc8", "Ironhide", "game/tf/features/battles.py:570", "unverifiable", "not replayed; not cited"),
    ("5", "B7", "0x01019150", "Mudflap and Skids", "game/tf/features/battles.py:600", "unverifiable", "not replayed"),
    ("5", "B8", "0x01012318", "Ratchet", "game/tf/features/battles.py:693", "unverifiable", "not replayed; not cited"),
    ("5", "EN", "0x010230d0", "Battle end", "game/tf/features/battles.py:307", "match", "battle_blackout poke_remaining_1 points equal; not cited"),
    ("5", "KL", "0x01023048", "Killed", "game/tf/features/battles.py:299", "unverifiable", "no kill in replayed marks; not cited"),
    ("5", "KL", "0x010232d4", "Kill hooks", "game/tf/features/battles.py:299", "unverifiable", "cited only as a lamp-rule order key"),
    ("6", "A", "0x0100a754", "Allspark eject", "game/tf/features/allspark.py:48", "match", "allspark_energon collect marks"),
    ("6", "MY", "0x010243b4", "Mystery award", "game/tf/features/allspark.py:189", "unverifiable", "random draw differs between the code run and the emulator (allspark_collect_3)"),
    ("6", "AB", "0x01024a60", "Add-a-ball", "game/tf/features/allspark.py:225", "match", "312 / 187 (M7)"),
    ("6", "SM", "0x0100fff0", "Side mode start", "game/tf/features/wizard.py:232", "match", "wizard_multiball start_aro points equal"),
    ("6", "SM", "0x01010174", "Side mode rules", "game/tf/features/wizard.py:222", "match", "aro_shot / aro_super points equal"),
    ("6", "SME", "0x010103c0", "Side mode end, deff 85", "game/tf/features/wizard.py:70", "match", "wizard_multiball marks equal; not cited (0x01010330 cited)"),
    ("6", "WZ", "0x010363ec", "Wizard MB start", "game/tf/features/wizard.py:298", "match", "start_wizard_mb points equal"),
    ("6", "WZ", "0x010365c4", "Wizard MB rules", "game/tf/features/wizard.py:298", "match", "wmb_shots / last_shot / super_wizard equal points"),
    ("6", "WZE", "0x0103686c", "One ball left", "game/tf/features/wizard.py:364", "match", "drains equal; not cited"),
    ("6", "WZE", "0x010367c4", "One ball left (2)", "game/tf/features/wizard.py:364", "match", "drains equal; not cited"),
    ("6", "WZE", "0x01036814", "Wizard total", "game/tf/features/wizard.py:364", "match", "drains equal; not cited"),
    ("6", "REQ", "0x01035af0", "Requirements, extra ball adj 83", "game/tf/features/wizard.py:138", "match", "cited; poke marks (leffs 76/77 = open M8)"),
    ("7", "SMU", "0x01023538", "Shot multiplier", "game/tf/features/combos.py:56", "match", "cited; combos equal"),
    ("7", "SMU", "0x01023650", "Roving 3X", "game/tf/features/combos.py:52", "match", "cited"),
    ("7", "SML", "0x010236e8", "Light shot multipliers", "game/tf/features/combos.py:56", "match", "cited"),
    ("7", "BON", "0x01000f38", "Bonus X", "game/tf/features/bonus.py:27", "match", "bonus points equal in game_flow / scoring; not cited (0x01000f68/f18 cited)"),
    ("7", "PV", "0x0102c8c8", "Pop value decay", "game/tf/features/pops.py:4", "match", "scoring pops_after_pause equal"),
    ("7", "SH", "0x040c7620", "Shaker patterns", "game/tf/os_layer.py:138", "match", "cited (shaker coil 8 pulses equal in switches marks)"),
]


def dg_rows():
    return [["R-DG-%03d" % i, "diagram %s node %s: %s" % (s, n, lab), "diagram node", a, lab, loc, "-", v, p]
            for i, (s, n, a, lab, loc, v, p) in enumerate(DG, 1)]


# ---------------------------------------------------------------- R-AD: cited addresses
TRON_EQUIV = {   # Tron citations still in the code, with tf_180's routine where this pass found it
    "0x0100f25c": "tf: event 0x6a hook LAB_010060a4 (sets flag 0x10)",
    "0x01036f1c": "tf deff 4 is 0x0103ee10 (deffs.csv)",
    "0x010346e8": "tf deff 32 is 0x0103c840 (deffs.csv)",
    "0x0100fbb0": "queue_fullscreen_deff: no tf_180 name yet",
    "0x01024460": "deff_hold_frames: tf uses FUN_0002108c / 0x0103058c (cited elsewhere)",
}


def ad_rows(addr):
    rows = []
    for i, r in enumerate(csv.DictReader(open(addr)), 1):
        a, cls, fn, tron = r["address"], r["class"], r["tf_function"], r["tron_head"]
        ctx = r["context"].replace("\n", " ")[:120]
        order_key = "order=" in ctx
        if tron == "yes" and a not in ("0x000314d8", "0x0100396c"):
            v, why = "differs", "Tron 1.74 function head, not a tf_180 routine; lands in %s. %s" % (fn, TRON_EQUIV.get(a, ""))
        elif order_key and cls == "inside":
            v, why = "extra", "a lamp-rule sort key written as an address (inside %s), not a ROM routine" % fn
        elif cls == "function":
            v, why = "match", "tf_180 function head %s; game context read against the routine name (read-through of all heads)" % fn
        elif cls in ("inside", "symbol_in_code"):
            v, why = "match", "call site / code offset inside %s (cited as such)" % fn
        elif cls in ("data", "rom_table", "ram"):
            v, why = "match", "%s present in the decompile" % cls
        elif cls == "rom_table_not_in_decompile":
            v, why = "unverifiable", "table address never referenced in tf_decompiled.c"
        else:
            v, why = "unverifiable", "not a ROM / RAM address the decompile names (%s)" % cls
        rows.append(["R-AD-%03d" % i, "cited %s" % a, "address citation", a, fn or cls, r["where"], ctx, v,
                     "probe_rules_addresses.py; " + why])
    return rows


# ---------------------------------------------------------------- R-K: constants
K = [
    ("TICK 16 ms", "0x000114b0", "64 x 250 us", "game/tf/os_layer.py:37", "0.016 s", "match", "owner decision 2026-11-25; FIQ setup"),
    ("SECOND = 62 ticks (ball save unit)", "0x00017a28", "adj x 0x3e", "game/tf/os_layer.py:38", "62", "match", "ball_save_task: *(task+0x30) * 0x3e"),
    ("Ball-save grace", "0x00017a28", "task_sleep(0xda) = 218", "game/tf/os_layer.py:55", "218", "match", "decompile line after leaf_b7e4(0xe)"),
    ("Ball-save poll / stop", "0x00017a28", "sleep 6, stop < 7", "game/tf/os_layer.py:1201", "6 / 7 (F8)", "match", "F8 fixed"),
    ("End-of-ball wait cap", "0x00033324", "937", "game/tf/os_layer.py:43", "937", "match", "DAT_00033324 (F10)"),
    ("Drain-side tasks 0x37/0x38", "0x00017b3c", "0x271 = 625", "game/tf/os_layer.py:73", "625", "match", "leaf_abe8(side+0x36, 0x271)"),
    ("Coin-door save / grace", "0x0103c0b8", "multiball_start(n,0,0x138,0xbb)", "game/tf/os_layer.py:88", "0x138 / 0xbb", "match", "decompile"),
    ("Serve / multiball eject ticks", "0x0103b39c", "device settles 31/46/62, shooter task 125 (ball_feed.md, table 0x040d17fc)", "game/tf/os_layer.py:56-68", "SERVE_EJECT 32, SAVE_EJECT 39, MB_EJECT 101, MB_FIRST 51, DEVICE_BUSY 149, SAVE_SERVE 48 (Tron traces)", "differs", "values say 'Tron traces'; not re-derived from 0x0103b39c / 0x01039db4 / 0x0103aba4 (open since 2026-11-25)"),
    ("Auto-launch hold", "0x0103bba0", "not decoded", "game/tf/os_layer.py:59", "12 (inferred)", "unverifiable", "agent A: the queued auto-launch's wait"),
    ("Ball search ticks", "0x0103b778", "sweep 0..30 (ball_search_ops.json), countdown DAT_00033320 10 s", "game/tf/os_layer.py:69-86", "EVENT 36, RUN 496, TICKS 104, MOTOR 33", "unverifiable", "sweep equal +1 tick (README); RUN/TICKS/EVENT are trace-fitted, not in the ops list"),
    ("Left orbit token 7", "0x01033354", "0xbb = 187 ticks (2.99 s), -1 per tick by 0x0000ff60", "game/tf/features/battles.py:50", "2.26 s (inferred from traces)", "differs", "R-F3"),
    ("Right orbit ignore after a left orbit / launch", "0x01033530", "token 7 up, or task 0x47 (leaf_abe8(0x47,0xbb) = 187 ticks) once", "game/tf/features/battles.py:60", "3.0 s window, every hit", "differs", "R-F3"),
    ("Right orbit repeat token 9", "0x01033530", "0xbb = 187 ticks, cleared by the repeat", "game/tf/features/battles.py:61", "187 ticks, never cleared by an ignored repeat", "differs", "R-F3"),
    ("Orbit gate hold", "0x0102c0a8", "1488 ms (93 ticks) in the code run", "game/tf/features/battles.py:54", "91 ticks (1456 ms, observed)", "differs", "switch_lift.json sw_5 pulse 1488 ms vs game trace 1.470 ref s"),
    ("Optimus hit ignore", "0x010262f0", "none (task 0x54, 62 ticks, in the handler)", "game/tf/features/optimus.py:53", "1.0 s", "extra", "R-F5"),
    ("Battle second", "0x0101795c", "11 x task_sleep(6) = 66", "game/tf/features/battles.py:79", "6 x 11", "match", "QA M9 / P9"),
    ("Battle pause task 0x59", "0x0100683c", "156 ticks", "game/tf/features/battles.py:78", "156", "match", "P7"),
    ("Battle grace after timer", "0x010230d0", "125 ticks", "game/tf/features/battles.py:81", "125", "match", "battles.md; battle_blackout equal"),
    ("Battle total at drain", "-", "not decoded", "game/tf/features/battles.py:86", "120 (battle_ratchet trace)", "unverifiable", "trace-only value"),
    ("Combo window", "0x01002be4", "DAT_00034b8c = 0x138, -7 per 7-tick step", "game/tf/features/combos.py:43", "312 / step 7", "match", "decompile"),
    ("Combo grace", "0x01002b5c", "*(task+0x20) = 0x7c (124)", "game/tf/features/combos.py:43", "124", "match", "decompile line 53 of the task"),
    ("Double scoring count / tail", "0x010038dc", "11 x 6 / 0x7d", "game/tf/features/bumblebee.py:31", "66 / 125", "match", "P6"),
    ("Fast scoring count / tail", "0x01004220", "11 x 6 / 250", "game/tf/features/twobank.py:42", "66 / 250", "match", "P8, P9"),
    ("Fast scoring deff 132 length", "-", "deff 132 op list", "game/tf/features/twobank.py:45", "3.97 s (capture)", "unverifiable", "capture value; agent A's deff_ops has the length"),
    ("Multiball end window", "0x0100be84", "218 (wizard 312)", "game/tf/features/megatron.py:73", "218", "match", "M1"),
    ("Megatron / Optimus save, grace", "0x0100c200", "625 / 187", "game/tf/features/megatron.py:72", "625 / 187", "match", "megatron_autobot equal"),
    ("Add-a-ball save / grace", "0x01024a60", "312 / 187", "game/tf/features/allspark.py:225", "312 / 187", "match", "M7"),
    ("Allspark eject warning wait", "0x0100a788", "case 7: sleeps until 0x35 (53) ticks then eject", "game/tf/features/allspark.py:24", "54", "match", "loop 'task_sleep(1); n + 1; break when 0x35 < n' = 54 sleeps"),
    ("Pops idle", "0x0102ca98", "93 ticks", "game/tf/features/pops.py:24", "93", "match", "pops.py cites; scoring equal"),
    ("Energon debounce task 0xb0", "0x010309a4", "10 ticks", "game/tf/features/energon.py:27", "10", "unverifiable", "not re-read in this pass"),
    ("Megatron back door", "0x01031848", "187 ticks", "game/tf/features/megatron.py:57", "187 x 0.016", "match", "token 0xbb"),
    ("Optimus motor time limit", "-", "not decoded", "game/tf/features/optimus_mech.py:28", "7.65 s (simulator)", "unverifiable", "emulator value"),
    ("Bonus deff length", "0x010014b8", "deff 25 op list", "game/tf/features/bonus.py:23", "338 (capture)", "unverifiable", "capture value"),
]


def k_rows():
    return [["R-K-%02d" % i, e, "constant", a, rv, loc, gv, v, p] for i, (e, a, rv, loc, gv, v, p) in enumerate(K, 1)]


def main():
    out, addr = sys.argv[1], sys.argv[2]
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(HDR)
    for r in sw_rows(out) + cr_rows(out) + dg_rows() + ad_rows(addr) + k_rows():
        w.writerow(r)


if __name__ == "__main__":
    main()
