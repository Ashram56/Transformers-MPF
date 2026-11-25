"""Name the decompile's unnamed functions (FUN_xxxxxxxx) of tf_180 from what their code does.

Each name comes from one rule, applied in this order, with its evidence (all read from the decompile and the
ROM's own tables; nothing from an emulator):
  switch     the handler of a switch in the switch table (rom_data/io/switches.csv, column handler)
  task       a task entry point: the function given to task_create / task_create_unique / a child task, with
             the task id when the caller passes a constant
  hook       an event handler: event_hook_add(list, event, fn)
  deff, leff, sound, adj, audit, msg
             what the function starts, reads or counts when that is its one clear purpose (deff_start(n),
             leff_start(n), snd_play(n), adj_get(n), audit_add(n), the text of the one message it draws)
  wrapper    a body that only calls one named function
  getter     returns one RAM word; setter writes one RAM word
  sub        called by one named function only: <caller>_sub
  uses       calls named functions: <first callee>_user (structural)
  table, ram the first ROM table or RAM word it uses (structural)
  leaf       none of the above
The rules run until no name changes (a name found for one function can name its helpers); wrapper and sub
build only on meaningful names, never on a structural one.
The rules run until no name changes (a name found for one function can name its helpers).

Writes rom/code/function_names.csv (address, name, rule, evidence) and renames the functions in
rom/code/tf_decompiled.c (the header line is followed by the old name: `// was FUN_0103aba4`).

Usage: TF_ROM=tf_180.bin name_functions.py [--dry]
"""
import csv
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROMDIR = os.path.join(HERE, "..")
DECOMP = os.path.join(ROMDIR, "code", "tf_decompiled.c")
OUT = os.path.join(ROMDIR, "code", "function_names.csv")
HEAD = re.compile(r"^// ==== ([0-9a-f]{8}) (\S+)\n(?:// was ((?:thunk_)?FUN_[0-9a-f]{8})\n)?", re.M)
CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\(")
NUM = r"(0x[0-9a-f]+|\d+)"
KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof", "CONCAT22", "CONCAT31", "CONCAT11", "CONCAT13",
            "SUB41", "SUB42", "ZEXT14", "SEXT14"}


def slug(text, n=4):
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    return "_".join(words[:n])[:40]


def csvmap(path, key, val):
    out = {}
    with open(os.path.join(ROMDIR, path), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get(key) and r.get(val):
                out.setdefault(r[key], r[val])
    return out


def messages(ids):
    """The ROM's text for each message id, by running msg_get [0x000099f0] as ROM code."""
    if not os.environ.get("TF_ROM"):
        return {}
    sys.path.insert(0, HERE)
    import coderun
    r = coderun.Runner()
    r.reset()
    r.m.mem_write(0x00031494, b"\0\0\0\0")       # English
    out = {}
    for i in sorted(ids):
        try:
            out[i] = coderun.cstr(r.m, r.call(0x000099f0, i), 60)
        except Exception:      # noqa: BLE001
            pass
    return out


def main():
    dry = "--dry" in sys.argv
    src = open(DECOMP, encoding="utf-8").read()
    heads = list(HEAD.finditer(src))
    funcs = {}            # addr -> dict
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(src)
        addr = int(m.group(1), 16)
        funcs[addr] = {"name": m.group(2), "orig": m.group(3) or m.group(2), "body": src[m.end():end]}
    by_name = {f["name"]: a for a, f in funcs.items()}
    by_name.update({f["orig"]: a for a, f in funcs.items()})
    unnamed = {a for a, f in funcs.items() if f["name"].startswith("FUN_") or f["name"].startswith("thunk_FUN_")}

    # calls and callers
    calls = {}
    callers = defaultdict(set)
    for a, f in funcs.items():
        body = f["body"]
        cs = []
        for c in CALL.findall(body):
            if c in by_name and by_name[c] != a and c not in KEYWORDS:
                cs.append(by_name[c])
        calls[a] = cs
        for c in set(cs):
            callers[c].add(a)

    switches = defaultdict(list)
    with open(os.path.join(ROMDIR, "rom_data", "io", "switches.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["handler"] and r["handler"] != "0x0":
                switches[int(r["handler"], 16)].append(r["name"])
    adj_names = {int(k): v for k, v in csvmap("rom_data/settings/adjustments.csv", "adj", "name").items()}
    audit_names = {int(k): v for k, v in csvmap("rom_data/settings/audits.csv", "audit", "name").items()}

    names, rule, evid = {}, {}, {}

    def give(a, n, r, e):
        if a in unnamed and a not in names:
            names[a], rule[a], evid[a] = n, r, e

    # switch handlers
    for a, sws in switches.items():
        give(a, "sw_" + slug(sws[0]) + ("_etc" if len(set(sws)) > 1 else ""), "switch",
             "handler of switch(es) " + "; ".join(sorted(set(sws))[:4]) + " (switch table)")
    # tasks and hooks: scan every call site
    task_re = re.compile(r"\b(task_create|FUN_0000ab4c|FUN_0000ac20)\(([^,]+),\s*(?:\(code \*\))?&?(FUN_[0-9a-f]{8}|LAB_[0-9a-f]{8}|[a-z_][a-z0-9_]*)\b")
    hook_re = re.compile(r"\bevent_hook_add\(([^,]+),\s*" + NUM + r",\s*&?(FUN_[0-9a-f]{8}|[a-z_][a-z0-9_]*)\b")
    for a, f in funcs.items():
        for m in task_re.finditer(f["body"]):
            tgt = by_name.get(m.group(3))
            if tgt is None:
                continue
            tid = m.group(2).strip()
            if m.group(1) == "FUN_0000ac20":
                tid, f_ = m.group(2), m.group(3)
            idtxt = tid if re.fullmatch(NUM, tid) else ""
            give(tgt, ("task_%s" % idtxt if idtxt else "task") + "_of_" + f["name"][:28], "task",
                 "task entry started by %s [0x%08x] (%s, id %s)" % (f["name"], a, m.group(1), tid))
        for m in hook_re.finditer(f["body"]):
            tgt = by_name.get(m.group(3))
            if tgt is not None:
                ev = int(m.group(2), 0)
                give(tgt, "on_event_%02x" % ev, "hook", "event_hook_add(%s, 0x%x, ..) in %s [0x%08x]"
                     % (m.group(1).strip(), ev, f["name"], a))

    # single-purpose rules
    msg_ids = set()
    for a in unnamed:
        for m in re.finditer(r"text_\w*msg\w*\(" + NUM, funcs[a]["body"]):
            msg_ids.add(int(m.group(1), 0))
    msgs = messages(msg_ids)

    def one(pattern, body):
        vals = {int(x, 0) for x in re.findall(pattern, body)}
        return vals.pop() if len(vals) == 1 else None

    for a in sorted(unnamed):
        b = funcs[a]["body"]
        d = one(r"\bdeff_start\(" + NUM, b)
        if d is not None:
            give(a, "start_deff_%d" % d, "deff", "deff_start(%d)" % d)
            continue
        lf = one(r"\bleff_start\(" + NUM, b)
        if lf is not None:
            give(a, "start_leff_%d" % lf, "leff", "leff_start(%d)" % lf)
            continue
        adj = one(r"\badj_get\(" + NUM, b)
        if adj is not None and adj in adj_names:
            give(a, "adj_" + slug(adj_names[adj]), "adj", "adj_get(%d) %s" % (adj, adj_names[adj]))
            continue
        au = one(r"\baudit_add\(" + NUM, b)
        if au is not None and au in audit_names:
            give(a, "count_" + slug(audit_names[au]), "audit", "audit_add(%d) %s" % (au, audit_names[au]))
            continue
        ms = one(r"text_\w*msg\w*\(" + NUM, b)
        if ms is not None and msgs.get(ms, "").strip():
            give(a, "draw_" + slug(msgs[ms]), "msg", "draws msg 0x%x \"%s\"" % (ms, msgs[ms][:40]))
            continue
        sd = one(r"\bsnd_play\(" + NUM, b)
        if sd is not None:
            give(a, "play_sound_%03x" % sd, "sound", "snd_play(0x%x)" % sd)
            continue
        if not calls[a]:
            g = re.fullmatch(r"\s*\{\s*return (?:\(\w+\))?(DAT_[0-9a-f]{8});\s*\}\s*", b.split(")", 1)[-1] if False else
                             b[b.find("{"):b.rfind("}") + 1] + " ")
            body = b[b.find("{"):b.rfind("}") + 1]
            g = re.fullmatch(r"\{\s*return (?:\([\w *]+\))?(DAT_[0-9a-f]{8});\s*\}", body)
            if g:
                give(a, "get_" + g.group(1).lower(), "getter", "returns %s" % g.group(1))
                continue
            s_ = re.fullmatch(r"\{\s*(DAT_[0-9a-f]{8}) = [^;]+;\s*return;\s*\}", body)
            if s_:
                give(a, "set_" + s_.group(1).lower(), "setter", "writes %s" % s_.group(1))
                continue

    # propagation: wrappers, helpers of one named caller, users of named callees. Only from a name that says
    # something (the ROM's named functions, the rules above, and what was derived from them), never from a
    # structural one (uses, leaf)
    SEMANTIC = {"switch", "task", "hook", "deff", "leff", "sound", "adj", "audit", "msg", "getter", "setter",
                "wrapper", "sub"}

    def cur(x):
        return names.get(x, funcs[x]["name"])

    def meaningful(x):
        if x in names:
            return rule[x] in SEMANTIC
        return not funcs[x]["name"].startswith(("FUN_", "thunk_FUN_"))

    def base(n):
        return re.sub(r"(_(sub|wrap|user))+$", "", n)[:36]

    for _ in range(12):
        changed = False
        for a in sorted(unnamed - set(names)):
            cs = calls[a]
            named_cs = [c for c in cs if meaningful(c)]
            if len(set(cs)) == 1 and named_cs:
                give(a, base(cur(named_cs[0])) + "_wrap", "wrapper", "only calls %s [0x%08x]" % (cur(named_cs[0]), named_cs[0]))
                changed = True
                continue
            cl = [c for c in callers[a] if meaningful(c)]
            if len(callers[a]) == 1 and cl:
                p = cl[0]
                give(a, base(cur(p)) + "_sub", "sub", "called only by %s [0x%08x]" % (cur(p), p))
                changed = True
        if not changed:
            break
    for a in sorted(unnamed - set(names)):
        named_cs = [c for c in calls[a] if meaningful(c)]
        b = funcs[a]["body"]
        tables = re.findall(r"DAT_(04[0-9a-f]{6})", b)
        rams = re.findall(r"DAT_(0[0-3][0-9a-f]{6})", b)
        if named_cs:
            give(a, base(cur(named_cs[0])) + "_user", "uses", "calls %s" % ", ".join(
                "%s [0x%08x]" % (cur(c), c) for c in list(dict.fromkeys(named_cs))[:3]))
        elif tables:
            give(a, "table_%s_reader" % tables[0], "table", "reads ROM table 0x%s" % tables[0])
        elif rams:
            give(a, "ram_%s_user" % rams[0], "ram", "uses RAM 0x%s" % ", 0x".join(list(dict.fromkeys(rams))[:3]))
        else:
            give(a, "leaf", "leaf", "no call to a named function, no table or RAM symbol"
                 + ("" if not calls[a] else " (calls only unnamed ones)"))

    # unique names: suffix with the address
    final = {}
    count = defaultdict(int)
    for a in names:
        count[names[a]] += 1
    for a in sorted(names):
        n = names[a]
        final[a] = n if count[n] == 1 and n not in by_name else "%s_%x" % (n, a & 0xffffff)

    if not final:
        print("nothing left to name; function_names.csv kept")
        return
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["address", "name", "was", "rule", "evidence"])
        for a in sorted(final):
            w.writerow(["0x%08x" % a, final[a], funcs[a]["orig"], rule[a], evid[a]])
    stats = defaultdict(int)
    for a in final:
        stats[rule[a]] += 1
    print(len(final), "named;", dict(sorted(stats.items(), key=lambda x: -x[1])))
    if dry:
        return

    # rename in the decompile: every identifier; the header line keeps its form `// ==== ADDR NAME` (the tools
    # parse it) and the old name follows on its own line `// was FUN_xxxxxxxx`
    ren = {funcs[a]["name"]: final[a] for a in final}
    out = re.sub(r"\b(thunk_FUN_[0-9a-f]{8}|FUN_[0-9a-f]{8})\b", lambda m: ren.get(m.group(1), m.group(1)), src)
    old = {final[a]: funcs[a]["orig"] for a in final}
    out = re.sub(r"^// ==== ([0-9a-f]{8}) (\S+)\n(?!// was )",
                 lambda m: "// ==== %s %s\n// was %s\n" % (m.group(1), m.group(2), old[m.group(2)])
                 if m.group(2) in old else m.group(0), out, flags=re.M)
    with open(DECOMP, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)


if __name__ == "__main__":
    main()
