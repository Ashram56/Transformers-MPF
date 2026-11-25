"""QA 2026-11-26 (scope R): compare the game's scenario replay, mark by mark, with agent A's runs of the same
scenarios inside the ROM code (rom/rules/traces/code_runs.csv, rom/rules/switch_handlers.csv).

Read-only: runs `python -m tests.scenario <name> <out>` with the trace written outside the repository, then
prints one line per mark: the code run's value next to the game's, for points, sounds, deffs, leffs (and, for
the `switches` scenario, coils, audits and game flags from switch_handlers.csv).

Usage (from the repository folder):
  .venv/bin/python docs/qa/2026-11-26/probe_rules_marks.py OUTDIR switches [scenario ...]
  OUTDIR: a scratch folder for the game traces; the comparison goes to stdout and OUTDIR/<scenario>.cmp.csv
"""
import collections
import csv
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TRACES = os.path.join(ROOT, "rom", "rules", "traces")
SPEECH = {"0x14c", "0x14d"}        # scenario_lift.py: random speech pick task 0xc6 [0x010250f4], left out there
REF_TICK = 0.01615                 # tests/scenario.py: game trace times are reference seconds
OS_AUDITS = {59, 60, 61, 62, 63, 64}


def game_segments(path):
    segs, cur = collections.OrderedDict(), None
    for ln in open(path):
        e = json.loads(ln)
        if e["ev"] == "mark":
            cur = e["text"]
            segs[cur] = []
        elif cur is not None:
            segs[cur].append(e)
    return segs


def coil_pulses(evs):
    """{coil: [duration in code ticks of 16 ms, ...]} from the on / off edges."""
    on, out = {}, collections.defaultdict(list)
    for e in evs:
        if e["ev"] != "coil":
            continue
        c = e["coil"]
        if e["on"]:
            on[c] = e["t"]
        elif c in on:
            out[c].append(int(round((e["t"] - on.pop(c)) / REF_TICK)) * 16)
    for c, t0 in on.items():
        out[c].append(-1)       # still on at the next mark
    return out


def code_coils(txt):
    """'18:64ms x3 23:64ms x2' / '18/23:32ms x3' -> {coil: count}."""
    out = collections.Counter()
    toks = txt.split()
    i = 0
    while i < len(toks):
        m = re.match(r"([\d/]+):(\d+)ms", toks[i])
        n = 1
        if i + 1 < len(toks) and re.match(r"x\d+$", toks[i + 1]):
            n = int(toks[i + 1][1:])
            i += 1
        if m:
            for c in m.group(1).split("/"):
                out[int(c)] += n
        i += 1
    return out


def game_cols(evs):
    snd = [e["call"] for e in evs if e["ev"] == "sound"]
    return {
        "points": sum(e["delta"] for e in evs if e["ev"] == "score"),
        "sounds": sorted(set(snd) - SPEECH),
        "deffs": sorted({str(e["id"]) for e in evs if e["ev"] == "deff_start" and e["id"] != 19
                         and not e.get("rule")}),     # rule-restarted background deffs: display housekeeping
        "leffs": sorted({str(e["id"]) for e in evs if e["ev"] == "leff_start"}),
        "audits": sorted({e["id"] for e in evs if e["ev"] == "audit" and e["id"] not in OS_AUDITS}),
        "coils": {c: len(v) for c, v in coil_pulses(evs).items()},
        "flags": sorted(["+%d" % e["flag"] for e in evs if e["ev"] == "flag_set"]
                        + ["-%d" % e["flag"] for e in evs if e["ev"] == "flag_clear"]),
        "awards": sorted(e["points"] * e.get("multiplier", 1) for e in evs if e["ev"] == "score_add"),
    }


def run_game(name, out):
    path = os.path.join(out, name + ".jsonl")
    subprocess.run([sys.executable, "-m", "tests.scenario", name, path], cwd=ROOT, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def compare_code_runs(name, segs):
    rows = []
    for r in csv.DictReader(open(os.path.join(TRACES, "code_runs.csv"))):
        if r["scenario"] != name:
            continue
        g = game_cols(segs.get(r["mark"], []))
        code = {"points": int(r["points"]), "sounds": sorted(set(r["sounds"].split()) - SPEECH),
                "deffs": sorted(r["deffs"].split()), "leffs": sorted(r["leffs"].split())}
        diff = [k for k in ("points", "sounds", "deffs", "leffs") if code[k] != g[k]]
        rows.append({"scenario": name, "mark": r["mark"], "code_points": code["points"], "game_points": g["points"],
                     "diff": " ".join(diff) or "same",
                     "detail": "; ".join("%s code %s game %s" % (k, " ".join(map(str, code[k])) if k != "points"
                                                                 else code[k],
                                                                 " ".join(map(str, g[k])) if k != "points"
                                                                 else g[k]) for k in diff)})
    return rows


RULE_CALLER = "0x0001794c"          # the deff rules' background (re)start (scripts/trace_check.py RULE_CALLERS)


def code_rule_deffs():
    """{mark: {deff}} the code run started from the deff rules (caller 0x0001794c), left out like the game's."""
    d = json.load(open(os.path.join(ROOT, "rom", "rom_data", "rules", "switch_lift.json")))
    out = collections.defaultdict(set)
    for s in d["segments"]:
        fg = {str(o["deff"]) for o in s["ops"] if o["op"] == "deff" and o["at"] != RULE_CALLER}
        out[s.get("mark")] = {str(o["deff"]) for o in s["ops"] if o["op"] == "deff" and o["at"] == RULE_CALLER} - fg
    return out


def compare_switches(segs):
    rows = []
    rule = code_rule_deffs()
    for r in csv.DictReader(open(os.path.join(ROOT, "rom", "rules", "switch_handlers.csv"))):
        mark = "sw_%s%s" % (r["switch"], "" if r["hit"] == "first" else "_again")
        g = game_cols(segs.get(mark, []))
        snd = set()
        for t in re.sub(r"\[[^\]]*\]", "", r["sounds"]).split():
            if t.startswith("0x"):
                snd.add(t)
        code = {
            "points": int(r["score_total"] or 0),
            "sounds": sorted(snd - SPEECH),
            "deffs": sorted({t for t in r["deffs"].split() if t.isdigit()} - {"19"} - rule[mark]),
            "leffs": sorted(set(r["leffs"].split())),
            "audits": sorted({int(x) for x in r["audit_counters"].split()} - OS_AUDITS),
            "coils": dict(code_coils(r["coils"])),
            "flags": sorted(r["flags"].split()),
        }
        diff = [k for k in code if code[k] != g[k]]

        def show(v):
            if isinstance(v, dict):
                return " ".join("%s:x%d" % kv for kv in sorted(v.items())) or "-"
            if isinstance(v, list):
                return " ".join(map(str, v)) or "-"
            return str(v)
        rows.append({"switch": r["switch"], "name": r["name"], "hit": r["hit"], "handler": r["handler"],
                     "mark": mark, "code_points": code["points"], "game_points": g["points"],
                     "diff": " ".join(diff) or "same",
                     "detail": "; ".join("%s code %s game %s" % (k, show(code[k]), show(g[k])) for k in diff)})
    return rows


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:]:
        segs = game_segments(run_game(name, out))
        rows = compare_code_runs(name, segs)
        if name == "switches":
            srows = compare_switches(segs)
            with open(os.path.join(out, "switch_handlers.cmp.csv"), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(srows[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(srows)
            for r in srows:
                print("SW", r["switch"], r["hit"], r["diff"], "|", r["detail"])
        with open(os.path.join(out, name + ".cmp.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(name, "marks", len(rows), "points equal", sum(r["code_points"] == r["game_points"] for r in rows),
              "all equal", sum(r["diff"] == "same" for r in rows))
        for r in rows:
            if r["diff"] != "same":
                print("  ", r["mark"], "|", r["detail"])


if __name__ == "__main__":
    main()
