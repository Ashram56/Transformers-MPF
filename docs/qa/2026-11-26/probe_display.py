"""QA 2026-11-26, display conversion (scope V): one matrix row per deff (1-155) plus the engine, score screen, fonts and
text-format rows, game against the decompiled ROM code. Read-only: it writes only matrix_display.csv next to itself.

Run from the repository folder: .venv/bin/python docs/qa/2026-11-26/probe_display.py
Sources (ROM side): rom/rom_data/dmd/deffs.csv (deff table 0x040ce7c4), rom/rom_data/dmd/deff_ops/deff_NNN*.json (agent A's
op lists, the deff functions run as ROM code), rom/code/tf_decompiled.c (constant deff ids passed to deff_start
0x000209b4, the show tasks 0x01006350 / 0x01006480, the idle wait 0x0100664c, the deff rules FUN_00017834).
Game side: what game/tf/display.py loads (event_map.csv priorities, HOLD_TICKS_BY_DEFF), media_table.load (run lengths,
sounds, leffs), the slides scripts/gen_media.py builds (run here with only_data, nothing written), game/tf/media_bridge.py
format_rom_text, and an AST scan of game/tf for the deff ids the game starts.
"""
import ast
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "game"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
OUT = os.path.join(os.path.dirname(__file__), "matrix_display.csv")
OPS = os.path.join(ROOT, "rom", "rom_data", "dmd", "deff_ops")
TICK_MS = 16.0


def rom_table():
    return {int(r["deff"]): r for r in csv.DictReader(open(os.path.join(ROOT, "rom/rom_data/dmd/deffs.csv")))}


def ops(name):
    p = os.path.join(OPS, name + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def rom_hold(o):
    """(ticks of priority 0x20 at the end, ticks from the FIRST 0x20 drop) of an op list; None: no drop."""
    pr = [x for x in o["ops"] if x["op"] == "prio" and x.get("prio") == 0x20]
    if not pr or o["end_tick"] is None:
        return None, None
    return o["end_tick"] - pr[-1]["t"], o["end_tick"] - pr[0]["t"]


def rom_callers():
    src = open(os.path.join(ROOT, "rom/code/tf_decompiled.c"), encoding="utf-8").read()
    num = r"(0x[0-9a-fA-F]+|\d+)"
    pats = {"deff_start": r"\bdeff_start\(" + num + ",", "show6350": r"\bdeff_start_user_6350\(" + num + ",",
            "show6480": r"\btask_sleep_user_6480\(" + num + ",", "idle664c": r"\bdeff_start_user_664c\(" + num + ",",
            "rule": r"\bram_00033dd4_user_17834\([^,]+,[^,]+,[^,]+," + num + ","}
    out = {}
    for fm in re.finditer(r"^// ==== ([0-9a-f]{8}) (\S+)\n(.*?)(?=^// ==== |\Z)", src, re.M | re.S):
        addr, name, body = fm.groups()
        for kind, p in pats.items():
            for m in re.finditer(p, body):
                d = int(m.group(1), 0)
                if d:
                    out.setdefault(d, []).append("%s 0x%s %s" % (kind, addr, name))
    # variable ids read from the code: tilt 0x0001db40 (local 0x00090015: deff 0x15), tilt warning 0x0001da8c
    # (deff 0x17), fast-scoring targets 0x0102e9c0 (0x83 when the count was 1, else 0x7e)
    for d, c in ((21, "deff_start 0x0001db40 tilt (packed id)"), (23, "deff_start 0x0001da8c adj_tilt_warnings (packed id)"),
                 (131, "deff_start 0x0102e9c0 (id 0x83 when count was 1)"), (126, "deff_start 0x0102e9c0 (id 0x7e)")):
        out.setdefault(d, []).append(c)
    return out


def game_refs():
    names = re.compile(r"(deff|DEFF|^intro$|^bg$|_BG$|^SIDE_INTRO$|^WMB_INTRO$)")
    calls = {"_deff": 0, "deff_start": 0, "show": 1, "when_idle": 1, "deff_rule": 1, "queue": 1, "start": 0,
             "deff_stop": 0}
    out = {}

    def add(d, f, line, how):
        if isinstance(d, int) and 1 <= d <= 155:
            out.setdefault(d, []).append("%s:%d %s" % (f, line, how))
    for path in glob.glob(os.path.join(ROOT, "game/tf/**/*.py"), recursive=True):
        f = os.path.relpath(path, ROOT)
        if f.endswith(("display.py", "media_bridge.py", "media_table.py")):
            continue
        for node in ast.walk(ast.parse(open(path).read())):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    ns = t.elts if isinstance(t, ast.Tuple) else [t]
                    vs = (node.value.elts if isinstance(node.value, ast.Tuple) else []) if isinstance(t, ast.Tuple) \
                        else [node.value]
                    for n, v in zip(ns, vs):
                        nm = n.id if isinstance(n, ast.Name) else (n.attr if isinstance(n, ast.Attribute) else "")
                        if "TICKS" in nm:
                            continue
                        if names.search(nm) and isinstance(v, ast.Constant) and isinstance(v.value, int):
                            add(v.value, f, node.lineno, nm)
                        if re.match(r"^(JP|DJ|SUPER)$", nm) and isinstance(v, ast.Tuple) and v.elts \
                                and isinstance(v.elts[0], ast.Constant):
                            add(v.elts[0].value, f, node.lineno, nm)
            if isinstance(node, ast.Call):
                fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                if fn in calls and len(node.args) > calls[fn]:
                    a = node.args[calls[fn]]
                    for x in (a.body, a.orelse) if isinstance(a, ast.IfExp) else (a,):
                        if isinstance(x, ast.Constant) and isinstance(x.value, int):
                            add(x.value, f, node.lineno, fn if fn != "deff_stop" else "deff_stop only")
    return out


# Per-deff findings read from the decompile and the game by hand (id -> (verdict, aspect note)); see report_display.md
MANUAL = {
    1: ("differs", "attract pages: child tasks 0x01000c30 / 0x01000120 / 0x010001e4 / 0x01000cd0 / 0x010003e4 cycle every 750 ticks and print live state (last scores via FUN_0102f200, credits 0x01000188 / 0x010001c4, the pages that read high scores and replay); the slide is the lifted run with zero state, no printf slots: CREDITS 0 and score 00 are baked (FREE PLAY, real scores and high scores never shown)"),
    19: ("differs", "drawn live by score_screen.py: the main score font / row from 1,000,000 up (V-SC1), the dim level of other players (V-SC6), and the flash bar, award value, combo text and highlight missing (V-SC2, V-SC7-V-SC9)"),
    10: ("differs", "deff_017_insert_coins 0x01000000 draws the credit text msg_get_user_44a4(+0x30) at 0x010000a0 every frame and PRESS START / INSERT COINS (0x31a / 0x31b by leaf_19988); the slide has the credit line baked empty (lifted with state 0) and media_bridge drops the credits= argument (credits.py:119); no hold in the code, the game holds 10 ticks"),
    15: ("differs", "same function as deff 10 (0x01000000): credit line baked empty, credits= dropped (os_layer.py:1024); no hold in the code, the game holds 10 ticks"),
    17: ("differs", "same function as deff 10 (0x01000000): credit line baked empty, credits= dropped (credits.py:158); no hold in the code, the game holds 10 ticks"),
    4: ("unverifiable", "started from the power handler table 0x040c7f68 (FUN_00007088, entry 0 = FUN_00007028) per os_layer.py:1473; the id is not a constant in the decompile"),
    2: ("missing", "volume display: ROM starts it from 0x0000ee1c / 0x0000f2a8 (coin door +/-); the game has no volume display"),
    3: ("missing", "service menu: ROM start_deff_3 0x0000ed90; the game has no service menu (no tf_service mode, no tf/service.py) though os_layer.py:1429 starts it"),
    5: ("missing", "boot/version screen: ROM start_deff_5 0x00006ecc; never started by the game"),
    7: ("missing", "region lock-out screen: ROM start_deff_7 0x00005630; not in the game (rare)"),
    11: ("missing", "LOCATING PINBALLS: ROM task_ball_search 0x0103b5e4 (missing balls at start); game never starts it"),
    12: ("missing", "OPERATOR ALERT / DEVICE MALFUNCTION: ROM 0x010383a8 / 0x010387ac / 0x01038b80 / 0x010391a0; game never starts it"),
    14: ("missing", "ROM starts it from 0x000068ec / 0x00026608 (flipper buttons); the game only stops it (flippers.py:39, :50)"),
    16: ("missing", "tournament: ROM sw_tournament_start 0x0001a6fc; tournament not modelled"),
    18: ("missing", "BUMP 'N' WIN: ROM sw_tournament_start 0x0001a6fc; not modelled"),
    34: ("missing", "tournament initials: ROM start_deff_34 0x0001e810; not modelled"),
    35: ("missing", "tournament: ROM start_deff_34_sub 0x0001e328; not modelled"),
    36: ("missing", "tournament initials: ROM 0x0001e328; not modelled"),
    37: ("missing", "tournament place: ROM 0x0001e328; not modelled"),
    50: ("differs", "variants: the shot name (text_draw_msg 0x01023d5c, e.g. ALLSPARK / LEFT LOOP) and the level come from +0x30/+0x34 [0x010237ac]; the slide is the shot1_x2 run and combos.py:172 passes no values, so every shot shows ALLSPARK 2X"),
    51: ("match", "no caller in the code (agent A, deff_051__side1.json 'why'); none in the game"),
    52: ("differs", "slot '%iX BONUS' is not parsed by media_bridge.SPEC (no %i): the text shows literally and the next slots shift (probe); sounds at 0.2 / 1.63 s (allspark.py:39, trace) vs code 0x144 at tick 12 (0.192 s), 0x141 at tick 100 (1.600 s)"),
    66: ("differs", "random_below(3) [0x0102ad30] picks 1 of 3 videos (198 / 225 / 253 ticks); the game always plays video 0 (optimus.py:288 anim is only posted for the PuP)"),
    71: ("differs", "random_below(5) [0x0100d214]: 5 videos (221 / 217 / 220 / 245 / 224 ticks); the game always plays video 0"),
    72: ("differs", "random_below(4) [0x0100d550]: 4 videos (261 / 270 / 297 / 269 ticks); the game always plays video 0"),
    97: ("differs", "0 shots left draws SHOOT LIT SHOT (text_draw_msg 0x0101f580); the game keeps the 'SHOOT %u SHOT%P1' slot (and its plural is wrong, V-TXT1)"),
    101: ("differs", "0 shots left: SHOOT LIT SHOT (deff_101__lit.json); the game keeps the count slot"),
    105: ("differs", "0 shots left: SHOOT LIT SHOT; rover state DAT_000313b4 = 1: SHOOT R. ORBIT (0x01016eb0); the game keeps the count slot"),
    113: ("differs", "0 shots left: SHOOT LIT SHOT (deff_113__lit.json); the game keeps the count slot"),
    121: ("differs", "0 shots left: SHOOT LIT SHOT (deff_121__lit.json); the game keeps the count slot"),
    124: ("differs", "op list empty (lifter ran +0x34 = 0, deff_124 returns): code 31 frames x task_sleep(5) then hold(1, 0x20) = 156 ticks (2.50 s); game set_media 1.0 s (energon.py:37), no slide (gen_media skips 0 frames): the screen keeps the previous frame"),
    125: ("differs", "op list stops at t 0 (+0x30 = 0): code 27 frames x 5 ticks then hold(2, 0x20) = 137 ticks (2.19 s), 0x13e at 0, 0x13f at frame 14 (1.12 s); game set_media 2.0 s, 0x13f at 1.13 s (energon.py:38), no slide"),
    129: ("differs", "sounds: code 0x27a at 0, 0x27b at tick 20 then queued after the sample (sound_after); game plays 5 calls at trace times (bumblebee.py:28)"),
    140: ("unverifiable", "sounds depend on the side and lock count (table 0x040c62aa, sample counters 0x02111d78 / 0x02111d88); the op list ran one state (error 108 at tick 105)"),
    33: ("differs", "award variant (FUN_00018c04: AWARD 1 TICKET drawn by text_draw_str) not in the slide; the game prints only the slots"),
    48: ("match", "no starter in the code (combos_and_multipliers.md); the game never starts it (combos.py:21)"),
    143: ("match", "never started in the code (optimus_multiball.md:166); none in the game"),
    49: ("unverifiable", "starter not found by agent A (combos_and_multipliers.md:136); the game never starts it"),
    127: ("unverifiable", "starter not found by agent A (scoring_features.md:188); the game never starts it"),
    145: ("unverifiable", "starter not found by agent A (scoring_features.md:90); the game never starts it"),
    47: ("differs", "the code drops its priority to 128 at tick 44 (op prio, deff_047.json) before the 2-tick hold; the game keeps the table priority until the hold (display.py deff_holds takes only the last 0x20 op)"),
    84: ("differs", "priority 0x20 from tick 162 (first prio op) to 247: an 85-tick replaceable tail; the game holds 2 ticks (last op only)"),
    89: ("differs", "priority 0x20 from tick 140 to 277: a 137-tick replaceable tail; the game holds 2 ticks (last op only)"),
    40: ("match", "side variants: the game builds the Autobot slide from image 0x2232 (gen_media SIDE_VARIANTS); started by the side-choice rule (player_side_user, rule 0x00034cec)"),
    41: ("match", "side sound 0x57 / 0x58 picked by side (side.py:100), code default 0x58 at 0"),
}
# deffs whose printf slots use %P1//S/% (plural): the game's format_rom_text prints the singular for 0 and >= 3
PLURAL = re.compile(r"%P1//S/%")


def main():
    from tf import display, media_table, media_bridge
    import gen_media
    rom = rom_table()
    prio, background = display.deff_table()
    media = media_table.load(display.PKG)
    slides = gen_media.build_deffs(True)            # what setup builds from the package (nothing written)
    callers = rom_callers()
    refs = game_refs()
    rows = []
    for d in range(1, 156):
        r = rom[d]
        o = ops("deff_%03d" % d)
        variants = sorted(os.path.basename(p)[10:-5] for p in glob.glob(os.path.join(OPS, "deff_%03d__*.json" % d)))
        rprio, rflags = int(r["priority"]), int(r["flags"], 16)
        notes, verdicts = [], []
        rc = callers.get(d, [])
        gr = [x for x in refs.get(d, []) if "deff_stop only" not in x]
        started = bool(gr)
        # priority, background flag
        gbg = d in background
        if prio.get(d) != rprio or gbg != bool(rflags & 1):
            verdicts.append("differs")
            notes.append("prio/bg %s/%s vs %s/%s" % (prio.get(d), gbg, rprio, bool(rflags & 1)))
        # length
        end = o["end_tick"]
        info = media.get(d)
        gsec = info.seconds if info else 0.0
        rlen = "loop" if rflags & 1 else ("until stopped" if end is None else "%d ticks (%.3f s)" % (end, end * TICK_MS / 1000))
        if end is not None and end > 0 and abs(gsec - end * TICK_MS / 1000) > 0.0005:
            verdicts.append("differs")
            notes.append("length %.3f s vs %d ticks" % (gsec, end))
        # hold tail
        last, first = rom_hold(o)
        ghold = display.HOLD_TICKS_BY_DEFF.get(d, display.HOLD_TICKS)
        if end and not rflags & 1 and started:
            if last is None:
                verdicts.append("differs")
                notes.append("no hold in the code (priority kept to the end); game drops to 0x20 for its last %d ticks (HOLD_TICKS default)" % ghold)
            elif last != ghold:
                verdicts.append("differs")
                notes.append("hold %d vs %d" % (ghold, last))
        rhold = "-" if last is None else ("%d" % last if first == last else "%d (first drop %d)" % (last, first))
        # sounds and leffs played inside the deff
        rs = [(x["t"], x["call"]) for x in o["ops"] if x["op"] in ("sound", "sound_after")]
        late = [s for s in rs if end and s[0] >= end]
        if late and started:
            verdicts.append("differs")
            notes.append("sounds after the deff end by a detached task dropped by display._media: %s" % late)
        rl = [x["leff"] for x in o["ops"] if x["op"] == "leff"]
        gs = [(round(t * 1000 / TICK_MS), c) for t, c in (info.sounds if info else [])]
        if info and (sorted(gs) != sorted(rs) or info.leffs != rl):
            verdicts.append("differs")
            notes.append("package sounds/leffs differ from the op list")
        # slide
        sl = slides.get(d)
        has_frames = bool(json.load(open(os.path.join(display.PKG, "media/dmd/deffs/deff_%03d/timing.json" % d))).get("frames"))
        if d == 19:
            slide = "drawn live (score_screen.py)"
        elif sl:
            slide = "slide %s%s" % (sl["slide"], " +%d printf slots" % len(sl["values"]) if sl["values"] else "")
        else:
            slide = "no slide"
            if has_frames:
                verdicts.append("missing")
                notes.append("frames in the package but no slide")
        plural = [v for v in (sl or {}).get("values", []) if PLURAL.search(v)]
        if plural and started:
            verdicts.append("differs")
            notes.append("plural slot %s printed singular for 0 and >= 3 (V-TXT1)" % plural[0])
        # callers
        if rc and not gr and d not in MANUAL:
            verdicts.append("missing")
            notes.append("ROM starts it, the game never does")
        if not rc and d not in MANUAL and not (rflags & 1 and d in (1, 19)):
            verdicts.append("unverifiable")
            notes.append("ROM starter not a constant id in the decompile (indirect)")
        if d in MANUAL:
            verdicts.append(MANUAL[d][0])
            notes.append(MANUAL[d][1])
        if variants and d not in MANUAL and d not in (14, 36):
            notes.append("other code variants not in the slide: %s" % " ".join(variants))
        order = ("missing", "differs", "extra", "unverifiable", "match")
        verdict = next((v for v in order if v in verdicts), "match")
        rom_value = "fn %s prio %d flags 0x%x; %s; hold %s; sounds %s; leffs %s; starters %s" % (
            r["fn"], rprio, rflags, rlen, rhold,
            " ".join("%d:0x%03x" % s for s in rs[:6]) + (" ..." if len(rs) > 6 else "") or "-",
            " ".join(map(str, rl)) or "-", "; ".join(rc[:3]) + (" ..." if len(rc) > 3 else "") or "-")
        game_value = "prio %s bg %s; %s; hold %s; %s; starts %s" % (
            prio.get(d), "yes" if gbg else "no",
            "loop" if gbg else ("%.3f s" % gsec if gsec else "until stopped"), ghold if not gbg else "-", slide,
            "; ".join(gr[:2]) or "none")
        loc = (gr[0].split(" ")[0] if gr else "game/tf/display.py:87")
        rows.append(["V%03d" % d, "deff %d %s" % (d, r["texts"][:40].replace("|", "/")), "deff",
                     "0x%08x" % int(r["fn"], 16), rom_value, loc, game_value, verdict,
                     "; ".join(notes) or "table, op list deff_%03d.json, package timing, regenerated slide data all equal" % d])
    rows += EXTRA
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "element", "kind", "rom_address", "rom_value", "game_location", "game_value", "verdict", "proof"])
        w.writerows(rows)
    from collections import Counter
    print(Counter(r[7] for r in rows))
    # the text-format probe
    f = media_bridge.format_rom_text
    print("plural:", [f("%d COMBO%P1//S/%", [n]) for n in (0, 1, 2, 3, 11)], "ROM ops: '0 COMBOS' (deff_019.json), 'SHOOT 11 SHOTS' (deff_097.json)")
    print("%iX:", media_bridge.format_values(["%iX BONUS", "%,02lu", "SHOT MULTIPLER%P1//S/%"], [3, 20000]))
    print("%P own arg:", media_bridge.format_values(["PLAYER %d", "YOU ARE IN %P1/1ST/2ND/3RD/4TH/5TH//% PLACE!"], [1, 3]))
    from tf import score_screen
    print("score fonts:", [(s, score_screen.score_draw([s], 1, 1, "FREE PLAY")[-3]) for s in (50000, 150000, 1500000, 150000000)])


# Rows outside the per-deff list: engine, score screen, fonts, text formats (read by hand, proof in report_display.md)
EXTRA = [
    ["V-ENG1", "deff start priority rule", "engine", "0x00020498", "accept if active prio <= new prio and (not equal or active flags & 3); a background deff (flag 1) waits while a foreground one runs", "game/tf/display.py:160", "same test (fg_prio > new or equal and not flags & 3); background deffs start behind the foreground one", "match", "deff_start_core 0x00020498 read; display.py:146-166"],
    ["V-ENG2", "show task id range", "engine", "0x01006634", "show tasks are 0x5d-0x7e (leaf_b698(0x5d, 0x7e), task_running_range_wrap_6634)", "game/tf/display.py:13", "docstrings say 0x81-0xa7 and queue_fullscreen_deff 0x0100fbb0 (Tron); the queue itself does not use the range", "differs", "0x01006350 / 0x01006480 / 0x01006634 read; citation only (low)"],
    ["V-ENG3", "show wait: threshold and timeout", "engine", "0x01006480", "wait up to param_2 (0xea6) ticks for active prio < param_3 (0x9f) and oldest show, then deff_start; end at prio <= 0x20", "game/tf/display.py:499", "SHOW_THRESHOLD 0x9f, SHOW_TIMEOUT 0xea6, oldest first, ends at the hold", "match", "0x01006480 body; callers pass 0xea6 / 0x9f (0x55: 0x753)"],
    ["V-ENG4", "show skipped by both flippers", "engine", "0x01006480", "task_sleep_user_6480 shows (battle and multiball intros 0x2b 0x39 0x3f 0x45 0x4b 0x51 0x54 0x55 0x5c 0x60 0x64 0x68 0x6c 0x70 0x74 0x78 0x8c 0x92 0x95): one flipper held and the other pressed calls deff_stop", "game/tf/display.py:499", "no skip: the intro always runs to its hold", "missing", "flipper_buttons_held_wrap_6860 / leaf_6894 / leaf_68b4 loop then deff_stop(param_1) in 0x01006480; grep: no skip in display.py / flippers.py"],
    ["V-ENG5", "deff rule priorities", "engine", "0x00017834", "rule priority byte +7, list sorted high first (leaf_17580): multiball bg rules 7 (58 64 70 76 82 87), battles 5 (93..121), fast scoring 133 = 5, double scoring rule 0x00034bb4 = 5, side rules 0x10 / 4", "game/tf/features/twobank.py:74", "fast / double scoring 0x80, wizard 0x70, Megatron / Optimus 0x60, battles 0x40 (battles.py:85): fast / double scoring above every multiball", "differs", "calls at decompile lines 48731 50180 56887 58603 59934 61192-69312 76129 77781 89264; with fast or double scoring during a multiball the ROM shows the multiball's background deff, the game deff 133 / 130"],
    ["V-ENG6", "background deff refresh", "engine", "0x000178b0", "bg_entry_eval: first true rule (gf mask), deff_start if not running (leaf_20a90), music if not playing", "game/tf/display.py:431", "rules_refresh: same first-true selection, start on change, music on change", "match", "bg_entry_eval read"],
    ["V-ENG7", "tick for lengths and holds", "engine", "0x000114b0", "16.0 ms", "game/tf/os_layer.py:37", "TICK 0.016 (media_bridge.py:16 too)", "match", "owner decision 2026-11-25"],
    ["V-ENG8", "trace-measured deff lengths and sounds", "engine", "0x00020498", "lengths, holds and sounds come from each deff's code (deff_ops)", "game/tf/features/battles.py:89", "UNCAPTURED / set_media tables from traces in battles.py:89, megatron.py:88, optimus.py:70, wizard.py:67, combos.py:50, twobank.py:71, energon.py:37: dead for every deff the package now times (display.set_media keeps a package length), live only for 124 / 125", "extra", "display.py:281 set_media returns when the package has a length; probe lengths equal the op lists for all other deffs"],
    ["V-SC1", "score display main score font / row", "score", "0x0102fa40", "font and baseline from table 0x040c75d0 (FUN_0102f11c) by score: >= 100,000,000 font 22 y 18; >= 1,000,000 font 17 y 18; >= 100,000 font 24 y 21; else font 26 y 21; x 84 centred", "game/tf/score_screen.py:18", "fonts (26, 24, 22, 20) picked by width <= 87 (inferred), always y 21", "differs", "table read from the ROM with rom/tools/rom.py; probe prints the game's pick"],
    ["V-SC2", "score display score flash bar", "score", "0x0102fa40", "after a score change (DAT_021120b0 >= 63, 7 of every 14 frames) a box x 41-127, rows from the table (4-20 or 2-23) is drawn (error_log_user_1fd70); during a multiball a sweep (leaf_2d71c)", "game/tf/score_screen.py:48", "not drawn", "missing", "0x0102fa40 read"],
    ["V-SC3", "score display bottom row timing", "score", "0x0102fb8c", "156 frames BALL/credits, then 312 frames replay text, then 1250 BALL/credits, repeating (task_sleep(1) per frame)", "game/tf/score_screen.py:22", "FIRST_BALL_TICKS 0x9c, REPLAY_TICKS 0x138, BALL_TICKS 0x4e2", "match", "deff_019 0x0102fb8c loop read"],
    ["V-SC4", "score display replay row text", "score", "0x0102f770", "first FUN_0001e0d8 (the tournament line, via tournament_get) at x 84 y 30 font 0; else the first replay level not yet won 1-4 (0x0102f8a0 / 0x0102f804), skipped when FUN_0001e994 says so", "game/tf/media_bridge.py:288", "only REPLAY AT <level> (replay_text); no tournament line (tournament not modelled)", "differs", "0x0102f770, 0x0102f8a0 read; adj_replay_award_2f804 texts per award type not in the game (docstring says so)"],
    ["V-SC5", "score display BALL n / credits", "score", "0x0102f71c", "BALL %d font 0 flags 1 x 42 y 30; credits msg_get_user_44a4(1) font 0 flags 4 x 127 y 30", "game/tf/score_screen.py:56", "same font, flags, positions", "match", "deff_019.json text ops at 0x0102f71c / 0x0102f768"],
    ["V-SC6", "status panel scores", "score", "0x0102f200", "x 38 right-aligned font 0, row 8p-3 (2 of 2: 21); players not up drawn with palette entry 15 -> 3; tournament (flag 0x10): all full", "game/tf/score_screen.py:21", "same rows; players not up at level 6 (OTHER_LEVEL, inferred)", "differs", "0x0102f200: palette_identity(abStack_30); local_21 = 3"],
    ["V-SC7", "status panel last award value", "score", "0x0102f200", "1-2 players: the last award (get_dat_021120b4) at x 38 row 13 (or 8p+13), fading in (DAT_021120b8 < 26)", "game/tf/score_screen.py:29", "not drawn", "missing", "0x0102f200 first text_printf_msg(0x502)"],
    ["V-SC8", "status panel combo text", "score", "0x0102f200", "while DAT_021120a8 < 94: msg 0x6d1 '%d-WAY' and 0x6d2 'COMBO' / '%d COMBO%P1//S/%' font 1 x 39 sliding up (rows (75-n)/3, (93-n)/3)", "game/tf/score_screen.py:29", "not drawn (combos.py:21 says the panel shows combos)", "missing", "0x0102f200 read; deff_019.json ops at 0x0102f5a8 / 0x0102f620 / 0x0102f6cc"],
    ["V-SC9", "status panel current-player highlight", "score", "0x0102f200", "after a score change (DAT_021120b0 >= 63, 7 of 14 frames) a box x 0-39 on the current player's row (leaf_1fdc4)", "game/tf/score_screen.py:29", "not drawn", "missing", "0x0102f200 read"],
    ["V-SC10", "status panel separator", "score", "0x0102f200", "line x 40 rows 0-31 level 15 (leaf_1fdc4(page, 0x28, 0, 0x28, 0x1f, 0xf))", "game/tf/score_screen.py:37", "box(40, 0, 1, 32, level)", "match", "0x0102f200; deff_019.json rect op 0x0102f504"],
    ["V-SC11", "status panel in other deffs", "score", "0x0102f200", "deffs that call FUN_0102f200 draw it live with the same rules (V-SC6..9)", "scripts/gen_media.py:123", "panel columns 0-40 of the frames cleared and panel_draw drawn over them (at the frames' brightest level)", "differs", "same gaps as V-SC6..9 in every deff with a panel"],
    ["V-FNT1", "font table (27 fonts)", "font", "0x00123478", "27 fonts: glyph set, w, h, x_offset, image, spacing (rom_data/fonts.json)", "scripts/gen_fonts.py:132", "27 fonts, every glyph and spacing equal", "match", "probe comparison glyph by glyph"],
    ["V-FNT2", "text width and alignment", "font", "0x00021378", "text_width: sum(w + x_offset + spacing) - spacing; flags 2: x -= width >> 1; flags 4: x = x + 1 - width", "game/tf/rom_screen.gd:95", "rom_width same sum; left = x - w / 2 or x + 1 - w", "match", "rom/tools/deff_render.py docstring cites 0x00021878 / 0x00021378; rom_fonts.gd rom_width"],
    ["V-FNT3", "glyph vertical placement", "font", "0x00021878", "y_draw = y - h + y_offset + 1 (taken from Tron, tf_180's renderer 0x21878 not re-derived: rom_data/fonts.json placement)", "game/tf/rom_screen.gd:107", "label top = y - ascent + 1 with a .fnt built by gen_fonts.py", "unverifiable", "agent A has not decoded tf_180's 0x00021878"],
    ["V-FNT4", "fit-font choice", "font", "0x0002174c", "text_printf_msg_fit_page: first font of the list whose text fits the width (deff_text_formats.csv font_list)", "game/tf/deff_values.gd:48", "same (first that fits, else the last)", "match", "fit_formats() and deff_values.gd _font"],
    ["V-TXT1", "printf %P (plural / ordinal)", "text", "0x0002fef0", "%P<n> consumes its own argument, index = arg - n (unsigned), picks that '/'-separated choice, clamped to the last: '%P1//S/%' gives '' for 1 and 'S' for 0 and >= 2", "game/tf/media_bridge.py:35", "uses the last number printed, consumes nothing; '//S/' read as an ordinal list: 'S' only for 2 (0, 3, 11 print the singular)", "differs", "vsprintf 0x0002fef0 'P' branch (decompile line ~501 of the function); probe: '3 COMBO', ROM ops '0 COMBOS' (deff_019.json), 'SHOOT 11 SHOTS' (deff_097.json)"],
    ["V-TXT2", "printf %P with its own argument", "text", "0x0103e970", "'YOU ARE IN %P1/1ST/.../% PLACE!' takes the place (+0x38) as its own argument; deff 36 %P from +0x18", "game/tf/media_bridge.py:59", "format_values gives %P the previous slot's number (the player number)", "differs", "deff_text_formats.csv rows 112, 115; probe"],
    ["V-TXT3", "printf %i", "text", "0x01024740", "deff 52 '%iX BONUS' (vsprintf handles i like d)", "game/tf/media_bridge.py:19", "SPEC has no i: the text shows '%iX BONUS' and the following slots take the wrong values", "differs", "probe format_values"],
    ["V-TXT4", "printf %d %u %s %lu %,02lu %06d", "text", "0x0002fef0", "decimal, comma grouping with %,; width with 0 pad; '00' for 0 with %,02lu", "game/tf/media_bridge.py:26", "same results for the formats in deff_text_formats.csv", "match", "probe: 250K, 000042, '1/2 - 3', 00, 1,234,567"],
]


if __name__ == "__main__":
    main()
