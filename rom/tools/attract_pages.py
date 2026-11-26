"""The attract pages of deff 1 (game over / attract) [0x0103c584], run as ROM code.

deff 1 walks the page table at 0x00030d10 (39 entries of (condition, page function), static data in the ROM
image, ended by a page of 0; nothing writes it at start-up): for entry i it calls condition(pass) (a 0 condition
always passes), and when it passes it creates the page as a child task (task_create_same_id_ac20, flags 0x300)
with the pass number at task +0x30, then sleeps 1 tick at a time until the page task has ended
(task_count_b3b0) or the right flipper (bits_changed_on_68b4(.., 2)) goes on: next entry. The left flipper
(bit 1) goes back one entry (and one pass before entry 0). After the last entry the pass counts up by one.

This tool boots the machine as switch_lift.py does (global constructors, OS init, flipper drivers 0x01005fb8), runs
the ROM's own factory resets (adjustments error_log_530_all_728 [0x00000728], game factory_reset_game_265e8
[0x000265e8]: replay, high scores, last scores; high_score_tables_init_190bc [0x000190bc]) and then, per state:
- evaluates the 39 conditions for passes 1 to 5;
- lifts every page function alone, as a task with the pass at +0x30, keeping only the ops of that task and its
  children, until it ends (at most 3,000 ticks): its op list and its length in ticks;
- runs deff 1 itself for two passes (factory state) to give the page order and the tick each page starts.

States (inputs written to NVRAM the way the ROM writes them; the values are test inputs, not ROM data):
  factory      after the factory resets: credits 0, no last game
  credits      3 credits in the credit system record (NVRAM 0x02111008: s32 position, u8 credits, ~sum8)
  free_play    adjustment 34 FREE PLAY = YES (u32 + ~sum8 at 0x02102110, as adj_get [0x00000340] reads it)
  replays      adjustment 14 REPLAY LEVELS = 4 (REPLAY TYPE AUTO: level n at n x AUTO REPLAY START,
               adj_replay_levels_adj_get_1c07c [0x0001c07c])
  last_game    2 players (0x02110900), scores 12,345,670 and 3,456,780 (0x021109e4): the left panel
  custom_msg   a custom message in NVRAM 0x02110040 (text, flag 0x02110081, ~sum8 at 0x02110082)
  tournament   tournament record 0 of type 4 (+0x124) with 5 levels (+0x31), started (+0x2c = 1), begun now
               for 30 days (+0xfc start, +0x10c length: tournament_2c000 [0x0002c000] turns a type 4
               record past its end into type 2 each 62 ticks), and a
               previous record 9 of type 2 (tournament_1ec8c [0x0001ec8c]); checksums as tournament_get
               [0x0001ec30] checks them

Writes rom/rom_data/dmd/deff_ops/deff_001__page<NN>[_<state>].json (one per page; a state suffix where the
state changes what the page draws) and rom/rom_data/dmd/attract_pages.json (table, conditions per state and
pass, lengths, the deff 1 schedule, the source of every variable text).

Usage: TF_ROM=/path/tf_180.bin python3 rom/tools/attract_pages.py
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ball_search  # noqa: E402
import coderun  # noqa: E402
import deff_lift  # noqa: E402
import deff_package  # noqa: E402
import switch_lift  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DMD = os.path.join(HERE, "..", "rom_data", "dmd")
OPS = os.path.join(DMD, "deff_ops")
TABLE = 0x00030d10
N_ENTRIES = 39
DEFF1 = 0x0103c584
MAX_TICKS = 3000

# what each condition tests, read from the decompile (rom/code/tf_decompiled.c) at the address given
CONDITIONS = {
    0: "is_one_c20 [0x01000c20]: pass == 1 (GAME OVER only on the first pass)",
    1: "none (always)",
    **{2 + k: "0x%05x: check_task_29_1c174(%d) [0x0001c174] != 0: in attract (state bit 0x10) "
              "adj_replay_levels_adj_get_1c07c(%d), replay level %d is set" % (0x270ec + 0x20 * k, k + 1, k + 1, k + 1)
       for k in range(4)},
    **{6 + k: "hstd_show_2_%d [0x%08x]: hstd_entry_if_allowed_186d0(2, %d) [0x000186d0] (Autobot table entry "
              "%d) and, when tournament_get_type [0x0001e8c0] == 4, only on passes divisible by 5"
              % (k, 0x010004d4 + 0x60 * k, k, k) for k in range(5)},
    **{11 + k: "hstd_show_3_%d [0x%08x]: hstd_entry_if_allowed_186d0(3, %d) (Decepticon table entry %d), same "
               "tournament rule" % (k, 0x010006b4 + 0x60 * k, k, k) for k in range(5)},
    16: "0x010027c4: hstd_entry_if_allowed_186d0(4, 0) (combo champion)",
    17: "0x01002958: hstd_entry_if_allowed_186d0(5, 0) (table 5 champion)",
    18: "tournament_state_1_27670 [0x00027670]: tournament type 4 and record +0x2c == 1",
    19: "tournament_type_is_4_277d0 [0x000277d0]: tournament type 4",
    20: "0x00027558: tournament record level count (+0x31) > 4 (the 5th level)",
    **{21 + k: "tournament_level_%d [0x%08x]: tournament type 4 and +0x31 > %d"
               % (k + 1, (0x000273cc, 0x00027418, 0x00027468, 0x000274b8, 0x00027508)[k], k) for k in range(5)},
    26: "tournament_active_27270 [0x00027270]: tournament type 4 and record +0x28 == 0 (bump 'n win)",
    27: "tournament_started_27a3c [0x00027a3c]: tournament type 4 and record +0x2c != 0",
    28: "0x00027e2c: tournament_1ec8c [0x0001ec8c] finds a previous record of type 2",
    **{29 + k: "0x%05x: previous record (tournament_1ec8c) with +0x31 > %d"
               % ((0x27c3c, 0x27c9c, 0x27d00, 0x27d64, 0x27dc8)[k], k) for k in range(5)},
    34: "none (always)",
    35: "none (always)",
    36: "none (always)",
    37: "0x0002b0f0: mov r0, #0 (never: the clock page is not shown)",
    38: "adj_custom_message_260 [0x01000260]: adjustment 2 CUSTOM MESSAGE == 1 and error_text_get_4d08 "
        "[0x00004d08] != 0 (the NVRAM custom message 0x02110040 when its ~sum8 and flag 0x02110081 are set, "
        "else the region message region_msg_55c0 [0x000055c0])",
}

# the variable texts: return address of the drawing call -> where the value comes from
LEFT_PANEL = ("draw_way_palette_identity_2f200 [0x0102f200] on the bg page (x < 41): in attract (state bit "
              "0x10) no player is up; one line per player of the last game, num_players [0x0001a94c] "
              "(0x02110900), each player_score_1cacc(n) [0x0001cacc] (0x021109e4 + 4 (n - 1)) through msg "
              "0x502 '%,02lu'; the combo counters 0x021120ac / 0x021120ae (msgs 0x6d1-0x6d3) and the "
              "separator rect x = 40")
SOURCES = {
    0x0102f2ec: LEFT_PANEL, 0x0102f36c: LEFT_PANEL, 0x0102f504: LEFT_PANEL, 0x0102f5a8: LEFT_PANEL,
    0x0102f620: LEFT_PANEL, 0x0102f6cc: LEFT_PANEL,
    0x01000188: "credits_text_44a4(DAT_00030e9e, buf) [0x000044a4]: free_play_4464 -> 'FREE PLAY', else "
                "counter_progress_41f8 of the credit system record (NVRAM 0x02111008) through msgs "
                "0x284 / 0x285 / 0x286; drawn fit (font list 0x040c5b80, width 0x53) at y 0x3c (off the page) "
                "to pick the font",
    0x010001c4: "the same text, drawn in the font the fit picked, centred at x 0x54",
    0x01000bb8: "adj_replay_award_1c21c(buf, n) [0x0001c21c]: replay level n, first line (before '\\n')",
    0x01000be0: "adj_replay_award_1c21c: second line (the replay score, adj_replay_levels_adj_get_1c07c)",
    0x01000944: "msg 0x700 'AUTOBOT' for table 2, 0x701 'DECEPTICON' for table 3 [0x010008f4]",
    0x01000968: "hstd_entry_get_185c8(table, entry) [0x000185c8] +0x14 through pick_language_entry_98a4 "
                "(GRAND CHAMPION, HIGH SCORE #n)",
    0x010009b0: "hstd_entry_if_allowed_186d0(table, entry): the record's initials (NVRAM high score table)",
    0x01000a00: "the entry's own format function (hstd_entry_get +0x10) when it has one",
    0x01000a60: "msg [0x00030e96] (0x502 '%,02lu') with the record's score +0x18 [0x01000a50]",
    0x01002850: "hstd_entry_get_185c8(4, 0) +0x14 (COMBO CHAMPION)",
    0x0100287c: "hstd_entry_if_allowed_186d0(4, 0): initials",
    0x010028ac: "msg 0x6e0 '%,02lu COMBO%P1//S/%' with the record +0x18 (the combo count)",
    0x010029e4: "hstd_entry_get_185c8(5, 0) +0x14 (BEST COMBO CHAMPION)",
    0x01002a10: "hstd_entry_if_allowed_186d0(5, 0): initials",
    0x01002a60: "msg 0x6e1 '%d-WAY' fit (font list 0x040c5c68) with (record +0x18) & 0xf and (record +0x18) >> 16",
    0x01000cb0: "msg 0x1db GAME OVER (fixed)",
    0x01000460: "msg 0x360 (fixed; font per language, table 0x040c5ba4)",
    0x0100048c: "msg 0x361 (fixed)",
    0x010004b4: "msg 0x362 (fixed)",
    0x010003a8: "error_text_get_4d08 [0x00004d08] (the custom message) cut at each '\\n' by error_text_store_4df8 "
                "[0x00004df8], one line each, font from list 0x040c5b94 (the first whose widest line < 0x54)",
    0x0002773c: "msg 0x4bd (fixed)",
    0x00027774: "tournament_font_text_1f170 [0x0001f170]: the prize pool of the record, as money",
    0x00027990: "msg 0x4d9 / 0x4db / 0x4dd by the days left (0, 1, more), fit from 0x040c9448",
    0x000279d4: "msg + 1 of the same with the days left: (start +0xfc + length +0x10c) - the clock now, in days",
    0x0002b220: "msg 0x22b CLOCK NOT SET (fixed; the page is never shown)",
    0x000275e8: "msg 0x4bb (fixed)",
    0x00027614: "msg 0x4bc (fixed)",
    0x00028ecc: "the level line: msg 0x4d4 with the level (the ranked pages), msg 0x4d5 when record +0x28 == 0 "
                "(bump 'n win) [0x00027400 .. 0x00027df4]",
    0x00028efc: "the level's leader: record +0x34 + 0x28 (level - 1)",
    0x00028fc4: "msg [0x00030e96] (0x502) with the level's score, record +0x4c + 0x28 (level - 1)",
    0x00028f84: "msg 0x4d4 with the level (bump 'n win mode)",
    0x00027330: "msg 0x4be (fixed)",
    0x0002736c: "msg [0x00030e96] with record +0x118 (the bump 'n win score)",
    0x00027b74: "msg 0x4ca (one winner) / 0x4cb with record +0x31 (the number of levels), fit from 0x040c9454",
    0x00027c00: "msg 0x4cc (+0x2c == 1) / 0x4cd with +0x31, on the frames where (frame & 2) == 0 (blinks)",
    0x00027ed4: "msg 0x4d2 (type 4) / 0x4d3 with the previous record's +0x31",
}


class PageRunner(switch_lift.SwitchRunner):
    """Keeps only the ops of one task and its children (root), so a page's op list is its own."""
    root = None

    def op(self, kind, **kw):
        t = self.cur
        while t is not None and t is not self.root:
            t = getattr(t, "parent", None)
        if self.root is None or t is None:
            return {"op": kind}
        return super().op(kind, **kw)


def wr(r, adr, data):
    r.m.mem_write(adr, bytes(data))


def sum8(data):
    return sum(data) & 0xff


def sum16(data):
    return sum(data) & 0xffff


def set_adj(r, n, value):
    """adj_get [0x00000340]: u32 value then ~sum8 of its 4 bytes, at the adjustment's NVRAM address (table
    0x040cb20c + n * 0x20)."""
    adr = struct.unpack("<I", bytes(r.m.mem_read(0x040cb20c + n * 0x20, 4)))[0]
    v = struct.pack("<i", value)
    wr(r, adr, v + bytes([~sum8(v) & 0xff]))


def tourney_record(rtype, levels, started, mode, start=0):
    rec = bytearray(300)
    rec[0xfc:0x104] = struct.pack("<Q", start)              # start, seconds (date_to_seconds_c29c)
    rec[0x10c:0x114] = struct.pack("<Q", 30 * 86400)        # length: tournament_2c000 [0x0002c000] ends it after
    rec[0x28:0x2c] = struct.pack("<I", mode)
    rec[0x2c:0x30] = struct.pack("<I", started)
    rec[0x30] = 1
    rec[0x31] = levels
    for k in range(5):                      # each level's name (+0x34 + 0x28 k) and its score (+0x4c + 0x28 k)
        rec[0x34 + 0x28 * k:0x34 + 0x28 * k + 6] = b"LVL %d\0" % (k + 1)
        rec[0x4c + 0x28 * k:0x50 + 0x28 * k] = struct.pack("<I", 10000000 * (k + 1))
    rec[0x118:0x11c] = struct.pack("<I", 50000000)
    rec[0x11c:0x120] = struct.pack("<I", 100)
    rec[0x124:0x128] = struct.pack("<I", rtype)
    rec[0x128:0x12a] = struct.pack("<H", ~sum16(rec[:0x128]) & 0xffff)   # nvram_block_128_ok_1dd14
    return bytes(rec)


def st_credits(r):
    rec = struct.pack("<iB", -1, 3)
    wr(r, 0x02111008, rec + bytes([~sum8(rec) & 0xff]))


def st_free_play(r):
    set_adj(r, 34, 1)


def st_replays(r):
    set_adj(r, 14, 4)


def st_last_game(r):
    wr(r, 0x02110900, b"\2")
    wr(r, 0x021109e4, struct.pack("<IIII", 12345670, 3456780, 0, 0))


def st_custom_msg(r):
    txt = b"WELCOME\nTO THE ARCADE"
    blk = bytearray(0x42)
    blk[:len(txt)] = txt
    blk[0x41] = 1
    wr(r, 0x02110040, bytes(blk) + bytes([~sum8(blk) & 0xff]))


def st_tournament(r):
    buf = r.OS_STACK - 0x100                # the clock now: clock_read_c624 [0x0000c624], date_to_seconds_c29c
    r.call(0x0000c624, buf)
    now = r.call(0x0000c29c, buf) | r.m.reg_read(coderun.A.UC_ARM_REG_R1) << 32
    wr(r, 0x02100bb8, struct.pack("<I", 0))
    wr(r, 0x02100000, tourney_record(4, 5, 1, 0, now))
    wr(r, 0x02100000 + 9 * 300, tourney_record(2, 5, 1, 1))


STATES = {"factory": None, "credits": st_credits, "free_play": st_free_play, "replays": st_replays,
          "last_game": st_last_game,
          "custom_msg": st_custom_msg, "tournament": st_tournament}


def machine(state):
    r = PageRunner()
    for base, size in ball_search.IO_REGIONS:
        r.m.mem_map(base, size)
    r.reset()
    switch_lift.boot(r)
    r.keep = True
    r.call(0x00000728)          # adjustments to their factory values
    r.call(0x000265e8)          # game factory reset: replay, high scores, last scores
    r.call(0x000190bc)          # high score tables to their defaults
    if STATES[state]:
        STATES[state](r)
    return r


def table(r):
    return [struct.unpack("<II", bytes(r.m.mem_read(TABLE + 8 * i, 8))) for i in range(N_ENTRIES + 1)]


def conditions(r, tab):
    return {p: [1 if c == 0 else int(r.call(c, p) & 0xff != 0) for c, _ in tab[:N_ENTRIES]] for p in range(1, 6)}


def lift(r, fn, pas):
    r.ops = []
    t = r.new_task(0x40, fn, 0x300)
    r.m.mem_write(t.struct + 0x30, struct.pack("<I", pas))
    r.root = t
    start = r.now
    while t.alive and r.now < start + MAX_TICKS:
        r.step(r.now + 1)
    r.root = None
    ops = []
    for o in r.ops:
        o = dict(o)
        o["t"] -= start
        o.pop("task", None)
        ops.append(o)
    return ops, (r.now - start if not t.alive else None)


def schedule(r, tab, ticks):
    """deff 1 itself: the tick each page task starts."""
    r.ops = []
    t = r.new_task(0x40, DEFF1, 4)
    r.root = t
    start = r.now
    r.step(start + ticks)
    r.root = None
    names = {fn: i for i, (_, fn) in enumerate(tab)}
    return [{"t": o["t"] - start, "entry": names.get(int(o["fn"], 16)), "fn": o["fn"]}
            for o in r.ops if o["op"] == "task" and int(o["fn"], 16) in names]


def texts(ops):
    out, seen = [], set()
    for o in ops:
        if o["op"] != "text":
            continue
        key = (o["at"], o["text"])
        if key in seen:
            continue
        seen.add(key)
        d = {"at": o["at"], "text": o["text"], "helper": o.get("helper")}
        for k in ("msg", "format", "varargs", "font", "x", "y", "page"):
            if k in o:
                d[k] = o[k]
        src = SOURCES.get(int(o["at"], 16))
        if src:
            d["source"] = src
        out.append(d)
    return out


def doc(n, fn, cond, state, pas, ops, length):
    return {"deff": 1, "fn": "0x%08x" % fn, "flags": 0x300, "priority": None, "end_tick": length,
            "ran_ticks": length if length is not None else MAX_TICKS, "detached": 0, "reads": 0,
            "unmodelled_page_writes": {},
            "variant": {"name": "page%02d" % n, "why": "deff 1 [0x0103c584] page entry %d of 0x00030d10 run alone "
                        "(attract_pages.py), condition %s; state %s, pass %d" % (n, cond, state, pas),
                        "args": {"pass": pas}, "ram": {}, "state": {"attract": state}, "pages": None},
            "ops": ops}


def main():
    deff_lift.work_pages()
    states = {}
    for state in STATES:
        r = machine(state)
        tab = table(r)
        conds = conditions(r, tab)
        pages = {}
        for i, (c, fn) in enumerate(tab[:N_ENTRIES]):
            pas = next((p for p in range(1, 6) if conds[p][i]), 1)
            ops, length = lift(r, fn, pas)
            pages[i] = {"pass": pas, "length_ticks": length, "drawn": any(o["op"] in ("text", "bitmap", "show")
                                                                         for o in ops),
                        "texts": texts(ops), "ops": ops}
        states[state] = {"conditions": {str(p): v for p, v in conds.items()}, "pages": pages}
        print(state, "pages shown on pass 1:", [i for i, v in enumerate(conds[1]) if v])

    r = machine("factory")
    tab = table(r)
    sched = schedule(r, tab, 6000)

    # the op lists: the factory run of each page, plus a state variant where the drawing differs
    os.makedirs(OPS, exist_ok=True)
    written = []
    for i, (c, fn) in enumerate(tab[:N_ENTRIES]):
        base = states["factory"]["pages"][i]
        sig = lambda p: [(o["at"], o.get("text")) for o in p["ops"] if o["op"] in ("text", "bitmap", "show")]
        shown = lambda s: any(states[s]["conditions"][str(p)][i] for p in range(1, 6))
        first = next((s for s in STATES if shown(s) and states[s]["pages"][i]["drawn"]), None)
        if first is None and base["drawn"]:
            first = "factory"                 # never shown (entry 37): its op list all the same
        base = states[first]["pages"][i] if first else base
        for state in STATES:
            p = states[state]["pages"][i]
            if state != first and (not shown(state) or not p["drawn"] or sig(p) == sig(base)):
                continue
            if state == first and not p["drawn"]:
                continue
            name = "page%02d" % i + ("" if state == "factory" else "_" + state)
            d = doc(i, fn, CONDITIONS.get(i), state, p["pass"], p["ops"], p["length_ticks"])
            d["variant"]["name"] = name
            deff_package.save_variant(d, name)
            written.append(name)
    # deff 1's own op list names its variants
    p1 = os.path.join(OPS, "deff_001.json")
    if os.path.exists(p1):
        d1 = json.load(open(p1))
        others = sorted({v for v in d1.get("other_variants", []) if not v.startswith("page")} | set(written))
        d1["other_variants"] = others
        with open(p1, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d1, f, separators=(",", ":"))
            f.write("\n")

    out = {"deff": 1, "fn": "0x%08x" % DEFF1, "table": "0x%08x" % TABLE, "tick_ms": 16.0,
           "walk": __doc__.split("\n\n")[1].replace("\n", " "),
           "entries": [{"entry": i, "condition": "0x%08x" % c if c else None, "page": "0x%08x" % fn,
                        "tests": CONDITIONS.get(i),
                        "op_lists": [w for w in written if w == "page%02d" % i or w.startswith("page%02d_" % i)],
                        "by_state": {s: {"shown_on_passes": [p for p in range(1, 6) if v["conditions"][str(p)][i]],
                                         "pass_lifted": v["pages"][i]["pass"],
                                         "length_ticks": v["pages"][i]["length_ticks"],
                                         "drawn": v["pages"][i]["drawn"],
                                         "texts": v["pages"][i]["texts"]}
                                     for s, v in states.items()}}
                       for i, (c, fn) in enumerate(tab[:N_ENTRIES])],
           "schedule_factory": sched}
    with open(os.path.join(DMD, "attract_pages.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print("op lists:", len(written), "; deff 1 page starts in 6000 ticks:", [(s["t"], s["entry"]) for s in sched])


if __name__ == "__main__":
    main()
