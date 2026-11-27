"""QA 2026-11-26 (sounds, coils): count the sound calls and coil pulses of the game against the reference traces.

Read-only confirmation step (traces only confirm the code). The game's traces are written first with
`.venv/bin/python -m tests.scenario <name> CAND_DIR/<name>.jsonl` for every rom/rules/traces/*.txt (not into
captures/). For each sound call: how many times the reference plays it (per ROM caller function: the reference
event's `caller` is the return address inside the calling function, mapped to the decompile's function heads)
and how many times the game does, per scenario; min(ref, game) counts as reproduced.
Usage: probe_sounds_traces.py CAND_DIR OUT_CSV
"""
import bisect
import collections
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEC = os.path.join(ROOT, "rom", "code", "tf_decompiled.c")


def heads():
    hs = sorted((int(m.group(1), 16), m.group(2)) for m in
                re.finditer(r"// ==== ([0-9a-f]{8}) (\S+)", open(DEC, errors="replace").read()))
    return [h[0] for h in hs], {a: n for a, n in hs}


def events(path, ev):
    out = []
    for line in open(path, encoding="utf-8"):
        if '"%s"' % ev not in line:
            continue
        e = json.loads(line)
        if e.get("ev") == ev:
            out.append(e)
    return out


def main():
    cand_dir, out = sys.argv[1], sys.argv[2]
    addrs, names = heads()
    per_call = collections.defaultdict(lambda: [0, 0, collections.Counter(), collections.Counter()])
    for ref in sorted(glob.glob(os.path.join(ROOT, "rom", "rules", "traces", "*.jsonl"))):
        name = os.path.basename(ref)[:-6]
        cand = os.path.join(cand_dir, name + ".jsonl")
        if not os.path.exists(cand):
            continue
        r = events(ref, "sound")
        c = events(cand, "sound")
        rc = collections.Counter(int(e["call"], 16) for e in r)
        cc = collections.Counter(int(e["call"], 16) for e in c)
        for call in set(rc) | set(cc):
            row = per_call[call]
            row[0] += rc[call]
            row[1] += cc[call]
            if rc[call] != cc[call]:
                row[3][name] = cc[call] - rc[call]
        for e in r:
            a = int(e.get("caller", "0x0"), 16)
            i = bisect.bisect_right(addrs, a) - 1
            fn = addrs[i] if i >= 0 else 0
            per_call[int(e["call"], 16)][2]["0x%08x %s" % (fn, names.get(fn, "?"))] += 1
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["call", "ref_n", "game_n", "ref_callers", "scenario_delta_game_minus_ref"])
        for call in sorted(per_call):
            ref_n, game_n, callers, delta = per_call[call]
            w.writerow(["0x%03x" % call, ref_n, game_n, " | ".join("%s x%d" % kv for kv in callers.most_common()),
                        " ".join("%s:%+d" % kv for kv in sorted(delta.items()))])


if __name__ == "__main__":
    main()
