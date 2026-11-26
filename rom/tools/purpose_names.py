"""Name the structural functions of the decompile by what they do (after name_functions.py and refine_names.py).

name_functions.py gave every function a name; about 1,560 of them are structural (the routine they call, the
table or RAM they use, the function that calls them). This pass reads each one's body in rom/code/tf_decompiled.c
and names it from the effects the code shows, each read from a call with a constant argument and resolved through
the ROM's own tables (nothing from an emulator):

  text    text_* drawing a message: the message text (table 0x040dc0f0, English)
  deff    deff_start(n) [0x000209b4]          leff   leff_start(n) [0x00007c10]
  sound   snd_play(n) [0x000251f4]            score  score_add [0x0001caf0]
  audit   audit_add(n) [0x00000c3c]: the audit's name (table 0x040cd5a4)
  adj     adj_get(n) [0x00000340]: the adjustment's name (table 0x040cb20c)
  flag    game_flag_set / clear / test(n) [0x00005a88 / 0x00005a38 / 0x00005b58]
  coil    coil_pulse* (n): the coil's name (table 0x040ce3d4)
  lamp    lamp_* (n) with a lamp number: the lamp's name (table 0x040d0dfc); lamp_group_* (n): the group
  switch  sw_* / switch_* (n): the switch's name (table 0x040e2c20)
  task    task_create(id, ..) [0x0000aa04], task_kill(id) [0x0000ae1c]
  event   event_post(n) [0x00006e50]
  calls   the semantic functions it calls (a name that says what it does, not a structural one)
Functions with none of these are named from the shape of their body: a field getter or setter of the object
they are passed, a walk over a RAM list, a test, arithmetic. The name keeps the address suffix so it stays unique.

Writes rom/code/function_names.csv (rule "purpose", the facts as evidence) and renames in the decompile and the
files of rom/, docs/ and game/tf/ that name the old names (refine_names.py's rename()).

Usage: TF_ROM=tf_180.bin python3 purpose_names.py [--dry]
"""
import csv
import os
import re
import sys

import refine_names as rn
import rom

STRUCTURAL = {"uses", "leaf", "ram", "table", "wrapper", "sub", "subsystem"}
GENERIC = {"current_player", "error_log", "error_log_wrap", "task_sleep", "memcpy", "memset", "strcpy", "strlen",
           "fatal_halt", "Reset", "random_below", "task_current", "num_players", "player_side"}
FIELDS = os.path.join(rn.ROMDIR, "rom_data")


def table(path, key, name):
    out = {}
    for r in csv.DictReader(open(os.path.join(FIELDS, path), encoding="utf-8")):
        try:
            out[int(r[key], 0)] = r[name]
        except (ValueError, KeyError):
            pass
    return out


SWITCHES = table("io/switches.csv", "number", "name")
LAMPS = table("io/lamps.csv", "lamp", "name")
COILS = table("io/coils.csv", "coil", "name")
AUDITS = table("settings/audits.csv", "audit", "name")
ADJS = table("settings/adjustments.csv", "adj", "name")


def msg_text(i):
    """Message i of the message table 0x040dc0f0 (one pointer per language, English first)."""
    try:
        return rom.cstr(rom.u32(rom.u32(0x040dc0f0 + 4 * i)))
    except Exception:  # noqa: BLE001
        return ""


def slug(s, words=3):
    w = re.findall(r"[A-Za-z0-9]+", s.replace("%", " "))
    w = [x.lower() for x in w if not re.fullmatch(r"(d|u|lu|s|x|\d*l?u)", x.lower())]
    return "_".join(w[:words])


def num(s):
    s = s.strip().lstrip("(").rstrip(")")
    s = re.sub(r"^\((u?int|ushort|short|char|byte|undefined\d?)\)", "", s)
    try:
        return int(s, 0)
    except ValueError:
        return None


CALL = re.compile(r"\b([A-Za-z_][A-Za-z_0-9]*)\(([^;{}]*?)\)")


def facts(body, names, structural, renames=None):
    renames = renames or {}
    """[(kind, text for the name, evidence)] in the order of the body."""
    out = []
    for m in CALL.finditer(body):
        fn, args = m.group(1), m.group(2)
        a0 = num(args.split(",")[0]) if args else None
        msg = None
        if fn.startswith("text_") and "msg" in fn and a0 is not None:
            msg = msg_text(a0)
            if slug(msg):
                out.append(("text", "draw_" + slug(msg), "%s(0x%x) '%s'" % (fn, a0, msg[:30])))
        elif fn == "deff_start" and a0 is not None:
            out.append(("deff", "show_deff_%d" % a0, "deff_start(%d)" % a0))
        elif fn == "leff_start" and a0 is not None:
            out.append(("leff", "run_leff_%d" % a0, "leff_start(%d)" % a0))
        elif fn in ("snd_play", "snd_play2") and a0 is not None:
            out.append(("sound", "play_snd_%x" % a0, "%s(0x%x)" % (fn, a0)))
        elif fn == "score_add":
            out.append(("score", "add_score", "score_add"))
        elif fn == "audit_add" and a0 is not None and a0 in AUDITS:
            out.append(("audit", "count_" + slug(AUDITS[a0], 4), "audit_add(%d) %s" % (a0, AUDITS[a0])))
        elif fn == "adj_get" and a0 is not None and a0 in ADJS:
            out.append(("adj", "adj_" + slug(ADJS[a0], 4), "adj_get(%d) %s" % (a0, ADJS[a0])))
        elif fn in ("game_flag_set", "game_flag_clear", "game_flag_test") and a0 is not None:
            out.append(("flag", "%s_flag_%x" % (fn.split("_")[-1], a0), "%s(0x%x)" % (fn, a0)))
        elif fn.startswith("coil_pulse") and a0 is not None and a0 in COILS:
            out.append(("coil", "pulse_" + slug(COILS[a0]), "%s(%d) %s" % (fn, a0, COILS[a0])))
        elif fn.startswith("lamp_group") and a0 is not None:
            out.append(("lamp", "lamp_group_%d" % a0, "%s(%d)" % (fn, a0)))
        elif fn.startswith("lamp_") and a0 is not None and a0 in LAMPS:
            out.append(("lamp", "lamp_" + slug(LAMPS[a0]), "%s(%d) %s" % (fn, a0, LAMPS[a0])))
        elif (fn.startswith("sw_") or fn.startswith("switch_")) and a0 is not None and a0 in SWITCHES:
            out.append(("switch", "sw_" + slug(SWITCHES[a0]), "%s(%d) %s" % (fn, a0, SWITCHES[a0])))
        elif fn in ("task_create", "task_running", "task_kill") and a0 is not None:
            verb = {"task_create": "start", "task_running": "check", "task_kill": "kill"}[fn]
            out.append(("task", "%s_task_%x" % (verb, a0), "%s(0x%x)" % (fn, a0)))
        elif fn == "event_post" and a0 is not None:
            out.append(("event", "post_event_%x" % a0, "event_post(0x%x)" % a0))
        elif fn in names and fn not in structural and fn not in GENERIC and not fn.startswith("FUN_"):
            out.append(("calls", renames.get(fn, fn), "calls %s" % renames.get(fn, fn)))
    return out


def shape(body, sig):
    """A name from the shape of a function with no effect: its fields, RAM, loops, return."""
    ret = sig.split("(")[0].split()[0] if sig else "void"
    fields = re.findall(r"param_1 \+ (0x[0-9a-f]+)\)", body)
    rams = re.findall(r"DAT_([0-9a-f]{8})", body)
    lines = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    loop = "while" in body or "for (" in body
    writes = re.findall(r"\*\([^)]*\)\(param_1 \+ (0x[0-9a-f]+)\) =", body)
    if loop and rams:
        return "walk_list_%s" % rams[0][-5:], "a loop over RAM 0x%s" % rams[0]
    if loop:
        return "loop", "a loop, no named call"
    if writes and len(lines) < 14:
        return "set_field_%s" % writes[0][2:], "writes param_1 + %s" % writes[0]
    if fields and ret != "void" and len(lines) < 14:
        return "get_field_%s" % fields[0][2:], "returns from param_1 + %s" % fields[0]
    if rams and ret != "void":
        return "read_ram_%s" % rams[0][-5:], "reads RAM 0x%s" % rams[0]
    if rams:
        return "write_ram_%s" % rams[0][-5:], "writes RAM 0x%s" % rams[0]
    if ret in ("bool", "char", "undefined1", "byte") or "return 1" in body:
        return "test", "returns a test, no named call"
    return "calc", "arithmetic on its arguments, no named call"


def compose(fs):
    """Two most telling distinct facts, in kind order."""
    order = ["text", "deff", "leff", "audit", "adj", "coil", "switch", "lamp", "flag", "sound", "score", "event",
             "task", "calls"]
    seen, pick = set(), []
    for k in order:
        for kind, word, _ in fs:
            if kind == k and word not in seen:
                seen.add(word)
                pick.append(word)
                break
        if len(pick) == 2:
            break
    if not pick or all(k == "calls" for k, _, _ in fs if _ in pick) and not any(
            k != "calls" for k, w, _ in fs if w == pick[0]):
        return ""                              # only calls: the old structural name says as much
    return "_".join(pick)


def main():
    dry = "--dry" in sys.argv
    src = open(rn.DECOMP, encoding="utf-8").read()
    parts = re.split(r"^(?=// ==== [0-9a-f]{8} )", src, flags=re.M)
    funcs = {}
    for p in parts:
        m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", p)
        if m:
            funcs[int(m.group(1), 16)] = (m.group(2), p)
    rows = list(csv.DictReader(open(rn.NAMES, encoding="utf-8")))
    names = {v[0] for v in funcs.values()}
    count = {}
    for n, _ in funcs.values():
        count[n] = count.get(n, 0) + 1
    by_name = {r["name"]: r for r in rows}
    used = set(names)
    renames, stats = {}, {}
    # rounds: a function named in one round is a semantic callee in the next
    for rnd in range(6):
        structural = {r["name"] for r in rows if r["rule"] in STRUCTURAL}
        structural |= {o for o, n in renames.items() if by_name.get(o) is None}
        todo = []
        for r in rows:
            if r["rule"] not in STRUCTURAL or r["rule"] == "subsystem":
                continue
            a = int(r["address"], 16)
            name, body = funcs.get(a, (r["was"], ""))
            if count.get(name, 0) > 1:
                continue                      # two thunks share the name: left as they are
            fs = facts(body.split("\n", 2)[-1], names, structural_old(structural, renames), renames)
            word = compose(fs)
            if word:
                todo.append((r, a, name, word, "; ".join(e for _, _, e in fs[:6])))
        if not todo:
            break
        for r, a, name, word, ev in todo:
            new = re.sub(r"_+", "_", "%s_%x" % (word[:60], a & 0xfffff)).strip("_")
            while new in used:
                new += "_"
            used.add(new)
            renames[name] = new
            r["name"], r["rule"], r["evidence"] = new, "purpose", ev[:300]
        stats[rnd] = len(todo)
    left = sum(1 for r in rows if r["rule"] in STRUCTURAL)
    print("renamed per round", stats, "total", len(renames), "structural left", left)
    if dry:
        for o, n in list(renames.items())[:: max(1, len(renames) // 60)]:
            print(o, "->", n, "|", by_name.get(n, {}).get("evidence", "")[:100])
        return
    with open(rn.NAMES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    rn.rename(renames)


def structural_old(structural, renames):
    """Old names still structural (bodies hold the old names)."""
    back = {n: o for o, n in renames.items()}
    return {back.get(n, n) for n in structural}

if __name__ == "__main__":
    main()
