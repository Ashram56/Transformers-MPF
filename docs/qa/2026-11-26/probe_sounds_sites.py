"""QA 2026-11-26 (sounds): list every sound call site of the tf_180 decompile and look up the game's use of it.

Read-only. Parses rom/code/tf_decompiled.c into functions (// ==== ADDR NAME), finds every call of the sound
API (snd_play 0x000251f4, snd_play_arg 0x00025224, snd_play2 0x00025250, snd_play_after 0x00025284 and its
wrappers 0x00025340 / 0x00025364 / 0x0002539c, the fixed-call wrappers 0x0000ecfc-0x0000ed4c / 0x0002b7d8 /
0x0002b7e0) and writes one row per site: containing function, line, API, call id (literal) or expression.
For each literal it lists where the game names that call: deff timing.json sounds (code-decoded deff ops, with
the instruction address `at`), and the game's Python / YAML (hex literal search).
Usage: probe_sounds_sites.py OUT_CSV
"""
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEC = os.path.join(ROOT, "rom", "code", "tf_decompiled.c")
API = {
    "snd_play": "snd_play", "snd_play_arg": "snd_play_arg", "snd_resolve_call_user_25250": "snd_play2",
    "snd_play_after": "snd_play_after", "snd_play_after_wrap_25340": "snd_play_after",
    "snd_play_after_wrap_25364": "snd_play_after_if", "snd_play_after_wrap_2539c": "snd_play_after_if",
}
FIXED = {"snd_resolve_call_user_ecfc": 9, "snd_resolve_call_user_ed0c": 10, "snd_resolve_call_user_ed1c": 11,
         "snd_resolve_call_user_ed2c": 12, "snd_resolve_call_user_ed3c": 13, "snd_resolve_call_user_ed4c": 14,
         "snd_resolve_call_user_2b7d8": 0x11, "snd_resolve_call_user_2b7e0": 0x12}
SKIP_FN = set(API) | set(FIXED) | {"snd_resolve_call", "snd_resolve_call_wrap", "snd_play_arg"}


def functions():
    cur = None
    for n, line in enumerate(open(DEC, encoding="utf-8", errors="replace"), 1):
        m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", line)
        if m:
            cur = (int(m.group(1), 16), m.group(2))
            continue
        yield cur, n, line


def lit(expr):
    expr = expr.strip()
    m = re.fullmatch(r"\(?(?:ushort|short)?\)?\s*(0x[0-9a-fA-F]+|\d+)", expr)
    return int(m.group(1), 0) if m else None


def first_arg(line, start):
    depth, i, out = 0, start, ""
    while i < len(line):
        c = line[i]
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                return out
            depth -= 1
        elif c == "," and depth == 0:
            return out
        out += c
        i += 1
    return out


def rom_sites():
    rows = []
    for fn, n, line in functions():
        if fn is None or fn[1] in SKIP_FN:
            continue
        for m in re.finditer(r"\b(leaf_6a20|leaf_6a9c)\(", line):     # sound tasks: 0x95 repeat [0x01006a20], delayed [0x01006a9c]
            if fn[1] in ("leaf_6a20", "leaf_6a9c"):
                continue
            arg = first_arg(line, m.end())
            rows.append(dict(fn=fn, line=n, api="snd_task_repeat" if m.group(1) == "leaf_6a20" else "snd_task_delayed",
                             call=lit(arg), expr=line.strip()[:60]))
        for m in re.finditer(r"\b(snd_[a-z_0-9]+)\(", line):
            name = m.group(1)
            if name in FIXED:
                rows.append(dict(fn=fn, line=n, api="snd_fixed", call=FIXED[name], expr=name))
            elif name == "snd_resolve_call":         # a direct resolve: (call, handle, &arg, with_arg)
                arg = first_arg(line, m.end())
                rows.append(dict(fn=fn, line=n, api="snd_resolve_call", call=lit(arg), expr=arg.strip()))
            elif name in API:
                arg = first_arg(line, m.end())
                rows.append(dict(fn=fn, line=n, api=API[name], call=lit(arg), expr=arg.strip()))
    return rows


def fn_ranges():
    heads = sorted({int(m.group(1), 16) for m in re.finditer(r"// ==== ([0-9a-f]{8}) ", open(DEC, errors="replace").read())})
    return {a: (heads[i + 1] if i + 1 < len(heads) else a + 0x1000) for i, a in enumerate(heads)}


def deff_fns():
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "rom", "rom_data", "dmd", "deffs.csv"))):
        if r["fn"] not in ("", "0x0"):
            out.setdefault(int(r["fn"], 16), []).append(int(r["deff"]))
    return out


def deff_sounds():
    out = {}
    for p in glob.glob(os.path.join(ROOT, "rom", "mpf_package", "media", "dmd", "deffs", "deff_*", "timing.json")):
        d = json.load(open(p))
        for s in d.get("sounds") or []:
            out.setdefault(int(str(s["call"]), 16), []).append((d["deff"], s["at"], s["tick"]))
    return out


def game_refs():
    refs = {}
    files = glob.glob(os.path.join(ROOT, "game", "tf", "**", "*.py"), recursive=True)
    for p in files:
        for n, line in enumerate(open(p, encoding="utf-8"), 1):
            code = line.split("#")[0]
            for m in re.finditer(r"\b0x([0-9a-fA-F]{1,3})\b", code):
                refs.setdefault(int(m.group(1), 16), []).append("%s:%d" % (os.path.relpath(p, ROOT), n))
    return refs


def main():
    out = sys.argv[1]
    ds, gr, rng, dfn = deff_sounds(), game_refs(), fn_ranges(), deff_fns()
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fn", "fn_name", "line", "api", "call", "expr", "deff_of_fn", "deff_timing_in_fn", "deff_timing_any", "game_hex_refs"])
        for r in rom_sites():
            c = r["call"]
            w.writerow(["0x%08x" % r["fn"][0], r["fn"][1], r["line"], r["api"], "" if c is None else "0x%03x" % c,
                        r["expr"], " ".join(str(d) for d in dfn.get(r["fn"][0], [])),
                        " ".join("d%d@%s+t%d" % (d, a, t) for d, a, t in ds.get(c, [])
                                 if r["fn"][0] <= int(a, 16) < rng[r["fn"][0]]) if c is not None else "",
                        " ".join("d%d" % d for d, a, t in ds.get(c, [])) if c is not None else "",
                        " ".join(gr.get(c, [])[:12]) if c is not None else ""])


if __name__ == "__main__":
    main()
