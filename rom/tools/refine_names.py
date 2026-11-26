"""Refine the structural function names of name_functions.py (rules uses, leaf, ram, table, and the wrapper / sub
names built on them) into names that say what the function is for.

Two rules, in this order, each with its evidence (read from the decompile and the ROM's tables, nothing from an
emulator):
  hand       rom/code/function_names_hand.csv: functions read one by one (address, name, evidence)
  subsystem  the function uses the RAM or ROM structure of one OS subsystem (SUBSYSTEMS below, each with the
             routine that shows what the structure is): <prefix>_<address>
A function that uses two subsystems keeps the first in SUBSYSTEMS' order. A semantic name of name_functions.py
(switch, task, hook, deff, leff, sound, adj, audit, msg, getter, setter) is kept, but for a hand name.

Writes rom/code/function_names.csv (name, rule, evidence; `was` kept) and renames the functions in
rom/code/tf_decompiled.c and in the docs and code of rom/, docs/ and game/tf/ that name them.

Usage: python3 refine_names.py [--dry]
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROMDIR = os.path.join(HERE, "..")
DECOMP = os.path.join(ROMDIR, "code", "tf_decompiled.c")
NAMES = os.path.join(ROMDIR, "code", "function_names.csv")
HAND = os.path.join(ROMDIR, "code", "function_names_hand.csv")
STRUCTURAL = {"uses", "leaf", "ram", "table", "wrapper", "sub", "subsystem"}

# (prefix, first address, end address, what it is and the routine that shows it)
SUBSYSTEMS = [
    ("snd_chan", 0x00037b94, 0x00037b94 + 8 * 0xa0,
     "the 8 sound channels (0xa0 each), stepped by snd_fiq_mix [0x000261fc]"),
    ("snd_ramp", 0x00038254, 0x00038274 + 8 * 0x1c, "the sound volumes and ramps, snd_fiq_mix [0x000261fc]"),
    ("snd_script", 0x0003249c, 0x000324e0, "the sound script opcodes, snd_chan_script_step [0x000246e8]"),
    ("coil_slot", 0x00035b00, 0x00035b10 + 0x28 * 0x28,
     "the coil outputs and the 40 coil pulse slots (0x28 each), io_isr [0x000114b0]"),
    ("coil_queue", 0x00031434, 0x00031450, "the queued pulse list, coil_pulse_queue_serve [0x00003758]"),
    ("motor", 0x000315f4, 0x000315f8, "the list of motors, motor_poll_all [0x00016b7c]"),
    ("sw_matrix", 0x000368da, 0x00036950, "the switch rows the IO interrupt reads, io_isr [0x000114b0]"),
    ("lamp_layer", 0x00036374, 0x0003639c, "the lamp layers, lamp_compositor_tick [0x000073cc]"),
    ("dmd_page", 0x00037654, 0x0003765c, "the DMD page allocator, dmd_page_alloc"),
    ("deff_active", 0x00032464, 0x00032468, "the running deff and its priority, deff_start_core_user"),
    ("tournament", 0x02100bb8, 0x02100bbc, "the tournament settings, tournament_get"),
    ("lamp_group", 0x040d1510, 0x040d1510 + 0x94 * 4,
     "the lamp group table (0x93 groups, each a 0-ended lamp list; error 0x30 outside), [0x000083dc]"),
    ("switch_rec", 0x040e2c20, 0x040e3740 + 0x20 * 0x20,
     "the switch records (matrix 0x20 each, dedicated from 0x040e3740), [0x0000d2d4]"),
    ("coil_rec", 0x040ce3d4, 0x040ce3d4 + 0x1c * 0x29, "the coil records (0x1c each), coil_slot_of [0x00001e50]"),
    ("game_device", 0x040d17fc, 0x040d17fc + 0x24 * 5,
     "the game's ball device records (0x24 each), balldev_count_switches"),
]


def load_funcs(src):
    heads = list(re.finditer(r"^// ==== ([0-9a-f]{8}) (\S+)\n", src, re.M))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(src)
        out[int(m.group(1), 16)] = (m.group(2), src[m.end():end])
    return out


def subsystem(body):
    used = [int(x, 16) for x in re.findall(r"DAT_([0-9a-f]{8})", body)]
    used += [int(x, 16) for x in re.findall(r"PTR_[A-Za-z_]*([0-9a-f]{8})", body)]
    for prefix, lo, hi, what in SUBSYSTEMS:
        hit = [u for u in used if lo <= u < hi]
        if hit:
            return prefix, "uses 0x%08x: %s" % (hit[0], what)
    return None


def main():
    dry = "--dry" in sys.argv
    src = open(DECOMP, encoding="utf-8").read()
    funcs = load_funcs(src)
    rows = list(csv.DictReader(open(NAMES, encoding="utf-8")))
    by_addr = {int(r["address"], 16): r for r in rows}
    hand = {int(r["address"], 16): r for r in csv.DictReader(open(HAND, encoding="utf-8"))}
    taken = {n for n, _ in funcs.values()}
    seen = {}
    for a, (n, _) in funcs.items():
        seen[n] = seen.get(n, 0) + 1
    shared = {n for n, k in seen.items() if k > 1}     # two thunks of one routine share a name: left as they are
    ren = {}
    for a, h in sorted(hand.items()):
        old = funcs[a][0]
        r = by_addr.get(a)
        if r is None:                      # named by hand before name_functions.py (snd_play, ...): only the csv
            r = {"address": "0x%08x" % a, "name": old, "was": old, "rule": "", "evidence": ""}
            rows.append(r)
            by_addr[a] = r
        if h["name"] != old:
            if h["name"] in taken:
                raise SystemExit("name %s taken" % h["name"])
            ren[old] = h["name"]
            taken.add(h["name"])
        r.update(name=h["name"], rule="hand", evidence=h["evidence"])
    for a, r in sorted(by_addr.items()):
        if a in hand or r["rule"] not in STRUCTURAL or funcs[a][0] in shared:
            continue
        s = subsystem(funcs[a][1])
        if not s:
            continue
        name = "%s_%x" % (s[0], a & 0xffffff)
        old = funcs[a][0]
        if name != old:
            if name in taken:
                raise SystemExit("name %s taken" % name)
            ren[old] = name
            taken.add(name)
        r.update(name=name, rule="subsystem", evidence=s[1])
    # a sub / wrapper name follows its parent's name (the address in its evidence), as name_functions.py builds it
    cur = {a: ren.get(n, n) for a, (n, _) in funcs.items()}
    for _ in range(4):
        for a, r in sorted(by_addr.items()):
            m = re.search(r"\[0x([0-9a-f]{8})\]", r["evidence"])
            t = re.match(r"(.*?)(_sub|_wrap)(_[0-9a-f]+)?$", cur[a])
            if (r["rule"] not in ("sub", "wrapper") or not m or not t or int(m.group(1), 16) not in cur
                    or funcs[a][0] in shared):
                continue
            parent = cur[int(m.group(1), 16)]
            name = re.sub(r"(_(sub|wrap|user))+$", "", parent)[:36] + t.group(2) + (t.group(3) or "")
            if name == cur[a] or name in taken:
                continue
            ren[funcs[a][0]] = name
            taken.add(name)
            cur[a] = r["name"] = name
            r["evidence"] = re.sub(r"\S+ \[0x%s\]" % m.group(1), "%s [0x%s]" % (parent, m.group(1)), r["evidence"], count=1)
    rows.sort(key=lambda r: int(r["address"], 16))
    stats = {}
    for r in rows:
        stats[r["rule"]] = stats.get(r["rule"], 0) + 1
    print(len(ren), "renamed;", dict(sorted(stats.items(), key=lambda x: -x[1])))
    if dry:
        return
    with open(NAMES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["address", "name", "was", "rule", "evidence"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    rename(ren)


def rename(ren):
    """Rename functions (old -> new) in the decompile and in the .md, .py and .csv files of rom/, docs/ and game/tf/
    that name them (function_names.csv and function_names_hand.csv excepted: they keep the old name in `was`)."""
    if not ren:
        return
    pat = re.compile(r"\b(" + "|".join(sorted(map(re.escape, ren), key=len, reverse=True)) + r")\b")
    files = [DECOMP]
    repo = os.path.abspath(os.path.join(ROMDIR, ".."))
    for d, _, fs in [w for top in ("rom", "docs", os.path.join("game", "tf")) for w in os.walk(os.path.join(repo, top))]:
        if "/." in d or d.endswith("__pycache__"):
            continue
        for fn in fs:
            p = os.path.join(d, fn)
            if (fn.endswith((".md", ".py", ".csv")) and os.path.abspath(p) != os.path.abspath(__file__)
                    and os.path.abspath(p) not in (os.path.abspath(NAMES), os.path.abspath(HAND))):
                files.append(p)
    for p in files:
        t = open(p, encoding="utf-8").read()
        n = pat.sub(lambda m: ren[m.group(1)], t)
        if n != t:
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(n)


if __name__ == "__main__":
    main()
