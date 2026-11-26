"""Lift the display effects whose frames depend on game state, once per state the caller sets.

deff_lift.py runs each deff with the task arguments at 0 and an empty RAM. 38 deffs read state that the code
sets before or after `deff_start` [0x000209b4]: words the caller stores into the deff's task (`deff_args.py`),
RAM the deff reads (tournament record, player variables), or the answer of an OS getter. Each entry of
VARIANTS gives that state, cited to the ROM address where the code sets it; the first variant of a deff is the
one packaged (`deff_package.py`), every variant's op list goes in rom/rom_data/dmd/deff_ops/ as
deff_NNN.json (first) and deff_NNN__<name>.json (others), so the game side can draw each one.

Usage: TF_ROM=tf_180.bin deff_variants.py OUT_DIR [deff ...]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import deff_lift  # noqa: E402

SHOT_MULT = 0x040c6f58     # shot multiplier records, 0x14 bytes per shot 1..6 (FUN_010237ac [0x010237ac])
HS_ENTRY = 0x040cf948      # high-score entries, 0x20 bytes each (registry 0x00030bcc: base, count 18, stride)
SCRATCH = 0x02700000       # free RAM for the structures a caller builds on its stack
TOURNEY = 0x02100000       # tournament record 0 (300 bytes), tournament_get [0x0001ec30] with index 0x02100bb8 = 0


def tournament(credits=1, score=0):
    """A valid tournament record: tournament_get [0x0001ec30] returns it when its checksum at +0x128 is the
    complement of the byte sum FUN_00001c50 [0x00001c50] of its first 0x128 bytes (written as in 0x0001e810)."""
    rec = bytearray(300)
    rec[0x30] = credits                                  # credits for a game: deff 16 [0x0103de04]
    rec[0x118:0x11c] = score.to_bytes(4, "little")       # the score: FUN_0001e810 [0x0001e810] stores it
    s = 0
    for b in rec[:0x128]:
        s = (s + b) & 0xffff
    rec[0x128:0x12a] = ((~s) & 0xffff).to_bytes(2, "little")
    return {TOURNEY: bytes(rec)}


def u16(v):
    return v.to_bytes(2, "little")


def initials_struct(title, prompt_a, prompt_b, place, chars):
    """The 0x24-byte entry record FUN_0001e328 [0x0001e328] builds for deff 36 (its stack at sp+0x48):
    +0x00 the letters entered (zero), +0x18 the place (msg 0x4c7), +0x1c title msg (printed with the player at
    +0x22), +0x1e / +0x20 the prompt msgs, +0x23 the number of letters."""
    rec = bytearray(0x24)
    rec[0x18:0x1c] = place.to_bytes(4, "little")
    rec[0x1c:0x1e], rec[0x1e:0x20], rec[0x20:0x22] = u16(title), u16(prompt_a), u16(prompt_b)
    rec[0x22], rec[0x23] = 1, chars
    return {SCRATCH: bytes(rec)}


def battle_bg(addr, start, why):
    """A battle's running display: the shots left of player 1 (u16 at addr), set to the start count."""
    return [("start", {"ram": {addr: u16(start)}}, why),
            ("lit", {"ram": {addr: u16(0)}}, why + "; 0 shots left: the shoot-lit-shot text")]


# deff -> [(name, {"args": {task offset: (size, value)}, "ram": {addr: bytes}, "state": {getter: value},
#                  "pages": (fg, bg)}, why)]; the first variant is the one packaged
VARIANTS = {
    14: [("score", {"pages": (1, 2)}, "called inside the score display: the work pages are the pair the score "
                                      "deff allocated (FUN_0103d828 [0x0103d828] draws on them)"),
         ("tournament", {"pages": (1, 2), "ram": {0x00031468: u16(0x10)}},
          "DAT_00031468 bit 0x10, a tournament game: the credits line FUN_000044a4 [0x0103d828]")],
    16: [("tournament", {"ram": tournament(1)}, "tournament_get [0x0001ec30] returns record 0; +0x30 credits "
                                                "for a tournament game (FUN_0001a6fc [0x0001a6fc] starts it)")],
    18: [("tournament", {"ram": tournament(1, 0), "args": {0x30: (4, 0)}},
          "FUN_0001a6fc [0x0001a6fc]: +0x30 = the record's +0x28 (0, a tournament); the score at +0x118")],
    32: [("place1", {"args": {0x30: (1, 1), 0x34: (4, HS_ENTRY + 0x20), 0x38: (4, SCRATCH + 0x100),
                              0x3c: (1, 3), 0x40: (2, 0x367), 0x44: (2, 0x368)}},
          "high_score_entry [0x00018d54]: +0x30 place, +0x34 entry, +0x38 name, +0x3c 3 letters "
          "(adj 0x3c not 1), +0x40 / +0x44 msgs 0x367 / 0x368")],
    33: [("place1", {"args": {0x30: (1, 1), 0x34: (4, HS_ENTRY + 0x20), 0x38: (4, 0), 0x3c: (4, 0)}},
          "FUN_00018c04 [0x00018c04]: +0x30 place, +0x34 the entry (grand champion table, entry 1), "
          "+0x38 / +0x3c no award"),
         ("award", {"args": {0x30: (1, 1), 0x34: (4, HS_ENTRY + 0x20), 0x38: (4, 1), 0x3c: (4, 1)}},
          "FUN_00018c04 [0x00018c04]: award type adj 1 (msg 0x371), 1 of it")],
    36: [("name", {"args": {0x30: (4, SCRATCH)}, "ram": initials_struct(0x4c5, 0x36b, 0x36c, 1, 0x14)},
          "FUN_0001e328 [0x0001e328]: the tournament name entry, 20 letters"),
         ("initials", {"args": {0x30: (4, SCRATCH)}, "ram": initials_struct(0x4c6, 0x36d, 0x36e, 1, 4)},
          "FUN_0001e328 [0x0001e328]: the tournament initials entry, 4 letters")],
    50: [("shot%d_x%d" % (s, lv), {"args": {0x30: (4, SHOT_MULT + s * 0x14), 0x34: (1, lv)}},
          "FUN_010237ac [0x010237ac]: +0x30 = shot record 0x040c6f58 + shot * 0x14, +0x34 = the shot's new level")
         for s in range(1, 7) for lv in (2, 3)],
    51: [("side%d" % v, {"args": {0x34: (1, v)}},
          "deff_051 [0x01024080] reads +0x34 (1, 2 or 4); no caller in the code starts it") for v in (2, 1, 4)],
    66: [("video%d" % k, {"state": {"rng": k}, "args": {0x34: (2, 0)}},
          "deff_066 [0x0102ad30]: random_below(3) picks the video (table 0x040c749c)") for k in range(3)],
    71: [("video%d" % k, {"state": {"rng": k}, "args": {0x34: (2, 0)}},
          "deff_071 [0x0100d214]: random_below(5) picks the video (table 0x040c6474)") for k in range(5)],
    72: [("video%d" % k, {"state": {"rng": k}, "args": {0x34: (2, 0)}},
          "deff_072 [0x0100d550]: random_below(4) picks the video") for k in range(4)],
    97: battle_bg(0x02111e9c, 11, "Shockwave: 11 shots at start FUN_0101e228 [0x0101e228]"),
    101: battle_bg(0x02111e94, 11, "Blackout: 11 shots at start FUN_0101c804 [0x0101c804]"),
    105: battle_bg(0x02111e54, 10, "Devastator: 10 shots at start FUN_01015b50 [0x01015b50]") + [
        ("rover", {"ram": {0x02111e54: u16(10), 0x000313b4: b"\x01"}},
         "Devastator, DAT_000313b4 = 1: the rover text msg 0x645 [0x01016d7c]")],
    113: battle_bg(0x02111e8c, 10, "Ironhide: 10 shots at start FUN_0101abd0 [0x0101abd0]"),
    121: battle_bg(0x02111e2c, 11, "Ratchet: 11 shots at start FUN_010120d4 [0x010120d4]"),
    94: [("shots%d" % n, {"args": {0x30: (4, 0), 0x34: (2, n), 0x3c: (1, 0)}},
          "deff_094 [0x010189a8]: +0x34 = shots left picks the animation in table 0x040c6a60 (9 routines; above 8 "
          "it takes 8), +0x3c = 0 a hit; shots0 (all at 0) is the one packaged") for n in range(0, 9)] + [
        ("final", {"args": {0x30: (4, 0), 0x34: (2, 0), 0x3c: (1, 1)}},
         "deff_094 [0x010189a8]: +0x3c != 0, the last hit: animation 1 of table 0x040c6a60, then the end frames")],
    124: [("target%d" % t, {"args": {0x30: (4, 0), 0x34: (4, t)}},
           "energon target lit, 0x01030a90 (deff_start(0x7c)): +0x30 = the set's other lit targets, +0x34 = the "
           "target's bit (1, 2 or 4)") for t in (1, 2, 4)],
    125: [("target%d" % t, {"args": {0x30: (4, t)}},
           "energon set completed, 0x01030a90 (deff_start(0x7d)): +0x30 = the bit of the target that completed it")
          for t in (1, 2, 4)],
    140: [("%s_lock%d" % (side, n), {"args": {0x30: (1, n)}, "state": {"side": sv},
                                      "ram": {0x02111d58: struct.pack("<I", 0x294), 0x02111d68: struct.pack("<I", 0x297)}},
           "deff_140_locked [0x0100b7f0]: +0x30 = the lock number (sound table 0x040c62aa, follow-ups 0x040c62cc / "
           "0x040c62c0 / 0x040c62b4 by side), player_side %d; the per-player lock speech calls 0x02111d58 = 0x294 "
           "(Autobot) and 0x02111d68 = 0x297 (Decepticon) as current_player_wrap_ab5c [0x0100ab5c] sets them "
           "at player start" % sv)
          for side, sv in (("decepticon", 2), ("autobot", 1)) for n in (1, 2, 3)],
    152: [("one", {"args": {0x30: (2, 1), 0x34: (2, 1), 0x38: (1, 8), 0x3c: (1, 1), 0x40: (2, 0)}},
           "deff_152 [0x01006e30]: images +0x40 + first-1 .. last-1 by +0x3c, +0x38 ticks each; no caller in "
           "the code starts it: one image")],
}
# the others read only values the game draws live (scores, counts): one run with the state at 0
DEFAULT = [1, 3, 19, 25, 34, 48, 58, 64, 70, 76, 81, 87, 123, 126, 127, 135, 139, 147, 149, 150]
for _d in DEFAULT:
    VARIANTS[_d] = [("default", {}, "state at 0: the values it prints are drawn live by the game")]


def setup_for(var):
    def setup(r):
        for addr, data in var.get("ram", {}).items():
            r.m.mem_write(addr, data)
        if "pages" in var:
            for key, page in zip(("fg", "bg"), var["pages"]):
                r.m.mem_write(deff_lift.WORK[key], struct.pack("<I", page))
    return setup


def init_for(var):
    def init(r, task):
        for off, (size, value) in var.get("args", {}).items():
            r.m.mem_write(task.struct + off, value.to_bytes(size, "little"))
    return init


def lift_variant(runner, deff, info, var):
    runner.state = dict(var.get("state", {}))
    runner.state.setdefault("rng", 0)
    ops = runner.run(info["fn"], setup=setup_for(var), init_main=init_for(var), max_ticks=1500)
    return {"deff": deff, "fn": "0x%08x" % info["fn"], "flags": info["flags"], "priority": info["priority"],
            "end_tick": runner.ended_tick, "ran_ticks": runner.now, "detached": runner.detached, "ops": ops,
            "reads": runner.reads,
            "unmodelled_page_writes": {"0x%08x" % k: v for k, v in runner.unmodelled.items()}}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    deff_lift.work_pages()
    r = deff_lift.DeffRunner()
    table = deff_lift.deff_table(r.m)
    ids = [int(x) for x in sys.argv[2:]] or sorted(VARIANTS)
    for d in ids:
        for i, (name, var, why) in enumerate(VARIANTS[d]):
            try:
                res = lift_variant(r, d, table[d], var)
            except Exception as e:      # noqa: BLE001
                res = {"deff": d, "fn": "0x%08x" % table[d]["fn"], "error": str(e), "ops": r.ops}
            res["variant"] = {"name": name, "why": why, "args": {"0x%x" % k: v[1] for k, v in var.get("args", {}).items()},
                              "ram": {"0x%08x" % k: v.hex() for k, v in var.get("ram", {}).items()},
                              "state": var.get("state", {}), "pages": var.get("pages")}
            fn = "deff_%03d.json" % d if i == 0 else "deff_%03d__%s.json" % (d, name)
            with open(os.path.join(out, fn), "w") as f:
                json.dump(res, f, indent=0)
            print(d, name, res.get("error") or "end %s ops %d" % (res["end_tick"], len(res["ops"])))


if __name__ == "__main__":
    main()
