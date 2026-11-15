"""The reference-trace regression: every scenario of rom/rules/traces replayed and compared with the ROM's trace,
then checked against the committed state of that comparison (tests/bench/trace_baseline.json).

The game does not match the ROM's traces everywhere yet (docs/rom_differences.md), so "all traces equal" cannot be
the test. The baseline records, per scenario and event kind, how far the game matches today: OK, or the first
differing event, or how many lamp samples / coil bursts match. A change is a regression when a kind that matched
no longer does, differs earlier, or matches fewer samples. An improvement is reported; run
`scripts/bench.py --update-baseline` to record it.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACES = os.path.join(ROOT, "rom", "rules", "traces")
BASELINE = os.path.join(os.path.dirname(__file__), "trace_baseline.json")
KINDS = "score,deff_start,sound,leff_start,audit,multiball_start,lamp,coil"
STRICT_KINDS = ("score", "audit", "multiball_start")     # these must stay equal to the ROM where they are today


def scenarios():
    return sorted(f[:-4] for f in os.listdir(TRACES) if f.endswith(".txt"))


def run(name):
    """Replay one scenario and compare it: {kind: status line}."""
    env = dict(os.environ, PYTHONPATH=ROOT)
    replay = subprocess.run([sys.executable, "-m", "tests.scenario", name], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    check = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "trace_check.py"), name, "--events", KINDS],
                           cwd=ROOT, env=env, capture_output=True, text=True)
    out = {}
    for line in check.stdout.splitlines():
        m = re.match(r"(\w+)\s+(OK|DIFF)\s*(.*)", line)
        if m and m.group(1) in KINDS.split(","):
            out[m.group(1)] = (m.group(2) + " " + m.group(3)).strip()
    if not out:
        out["error"] = (replay.stderr or check.stderr or "no comparison")[-400:]
    return out


def level(status):
    """How far a status matches, as a number that grows with the match."""
    if status.startswith("OK"):
        return float("inf")
    m = re.search(r"at event #(\d+)", status)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)/(\d+)", status)
    if m:
        return int(m.group(1)) - int(m.group(2))        # samples missing, as a negative number
    return -1e9


def compare(name, now, baseline):
    """(regressions, improvements) of one scenario against its baseline entry."""
    worse, better = [], []
    for kind in KINDS.split(","):
        new, old = now.get(kind, "missing"), baseline.get(kind)
        if old is None:
            continue
        if level(new) < level(old):
            worse.append("{} {}: {} (was: {})".format(name, kind, new, old))
        elif level(new) > level(old):
            better.append("{} {}: {} (was: {})".format(name, kind, new, old))
    if "error" in now:
        worse.append("{}: {}".format(name, now["error"]))
    return worse, better


def load_baseline():
    with open(BASELINE, encoding="utf-8") as f:
        return json.load(f)


def save_baseline(results):
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, sort_keys=True)
        f.write("\n")
