"""Write the lamp effects (leffs) of the MPF package from their code (leff_lift.py).

For each leff: rom/rom_data/io/leff_ops/leff_NNN.json (the lift: lamp states per tick, coil pulses, sounds,
effects started, each with its ROM address) and rom/mpf_package/config/shows/lampfx_NNN.yaml (the MPF show),
then rom/rom_data/io/lamp_effects.csv (one row per leff of the table 0x040cfe00; the columns the game reads).
A leff that never ends by itself (it runs until stopped) is written as its lead-in then one cycle: the shortest
period after which its lamp states and pulses repeat exactly, found in its tick sequence; the show's header and
the column loop_step give the step the cycle starts at, where the player loops back (QA L-G11). Lamp levels: both planes "ffffff", one plane "7f7f7f", none "000000" (leff_lift.py).

Usage: TF_ROM=tf_180.bin leff_package.py LIFT_DIR [leff ...]
"""
import collections
import csv
import glob
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, foff, u32  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROMDIR = os.path.join(HERE, "..")
SHOWS = os.path.join(ROMDIR, "mpf_package", "config", "shows")
OPS_DIR = os.path.join(ROMDIR, "rom_data", "io", "leff_ops")
CSV = os.path.join(ROMDIR, "rom_data", "io", "lamp_effects.csv")
TICK_MS = 16.0                     # the OS tick from the code: 64 IO interrupts of 250 us [0x000114b0] (owner, 2026-11-25)
COL = {0: "000000", 1: "7f7f7f", 2: "7f7f7f", 3: "ffffff"}
COIL_GROUPS = 0x040cf65c           # coilgroup_pulse [0x00005fd4]: 0-terminated coil lists


def names():
    pkg = os.path.join(ROMDIR, "mpf_package")
    lights, coils = {}, {}
    for m in re.finditer(r"\n  (l_\w+):\n    number: (\d+)", open(os.path.join(pkg, "config/lights.yaml")).read()):
        lights[int(m.group(2))] = m.group(1)
    for m in re.finditer(r"\n  (c_\w+):\n    number: (\d+)", open(os.path.join(pkg, "config/coils.yaml")).read()):
        coils[int(m.group(2))] = m.group(1)
    return lights, coils


def coil_group(g):
    p = u32(COIL_GROUPS + 4 * g)
    o, out = foff(p), []
    while o is not None and ROM[o] and len(out) < 40:
        out.append(ROM[o])
        o += 1
    return out


def events(doc, lights, coils):
    """{tick: {"lights": {name: colour}, "coils": {name: ms}}} of the lamp changes and pulses."""
    ev = collections.defaultdict(lambda: {"lights": {}, "coils": {}})
    prev = {}
    for f in doc["frames"]:
        for k, v in f["lamps"].items():
            n = int(k)
            if n in lights and prev.get(n) != COL[v]:
                ev[f["t"]]["lights"][lights[n]] = COL[v]
                prev[n] = COL[v]
    for o in doc["ops"]:
        if o["op"] in ("coil", "coil_fn"):
            targets = [o["coil"] & 0xff]
        elif o["op"] in ("coil_group", "coil_group_fn"):
            targets = coil_group(o["group"] & 0xffff)
        else:
            continue
        for c in targets:
            if c in coils:
                ev[o["t"]]["coils"][coils[c]] = o["ms"] & 0xffff
    return dict(sorted(ev.items()))


def find_cycle(ev, ran):
    """(start, period) in ticks of the shortest exact repeat of the events from start to the end of the run
    (at least two periods long), or None."""
    ticks = sorted(ev)
    if len(ticks) < 3:
        return None
    sig = {t: json.dumps(ev[t], sort_keys=True) for t in ticks}
    for s0 in ticks[:max(1, len(ticks) // 2)]:
        for t1 in [t for t in ticks if t > s0]:
            per = t1 - s0
            if s0 + 2 * per > ran:
                break
            if all(sig.get(t + per) == sig[t] for t in ticks if s0 <= t and t + per < ran) and \
                    all(t - per in sig for t in ticks if t >= s0 + per):
                return s0, per
    return None


def steps_of(ev, start, end, state0=None):
    ticks = [t for t in ev if start <= t < end]
    out = []
    for i, t in enumerate(ticks):
        nxt = ticks[i + 1] if i + 1 < len(ticks) else end
        st = {"duration": "%dms" % max(1, round((nxt - t) * TICK_MS))}
        lights = dict(ev[t]["lights"])
        if i == 0 and state0:
            lights = dict(state0, **lights)
        if lights:
            st["lights"] = dict(sorted(lights.items()))
        if ev[t]["coils"]:
            st["coils"] = dict(sorted(ev[t]["coils"].items()))
        out.append(st)
    return out


def dump_show(path, header, steps):
    lines = ["#show_version=6\n"] + ["# %s\n" % h for h in header]
    for s in steps:
        lines.append("- duration: %s\n" % s["duration"])
        if "lights" in s:
            lines.append("  lights:\n")
            lines += ['    %s: "%s"\n' % kv for kv in s["lights"].items()]
        if "coils" in s:
            lines.append("  coils:\n")
            for k, v in s["coils"].items():
                lines.append("    %s:\n      action: pulse\n      pulse_ms: %d\n" % (k, v))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(lines))


def started_by():
    src = open(os.path.join(ROMDIR, "code", "tf_decompiled.c"), encoding="utf-8").read()
    sites, cur = collections.defaultdict(set), None
    for line in src.split("\n"):
        m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", line)
        if m:
            cur = "0x%x %s" % (int(m.group(1), 16), m.group(2))
            continue
        for m2 in re.finditer(r"\bleff_start\((0x[0-9a-f]+|\d+)\)", line):
            sites[int(m2.group(1), 0)].add(cur)
    return sites


def package(doc, lights, coils, sites):
    n = doc["leff"]
    ev = events(doc, lights, coils)
    end, ran = doc.get("end_tick"), doc.get("ran_ticks")
    loops = end is None
    note, body, loop_step = "", [], ""
    if not loops:
        body = steps_of(ev, 0, max(end, 1))
        note = "ends by itself after %d ticks (%d ms)" % (end, round(end * TICK_MS))
    else:
        cyc = find_cycle(ev, ran)
        if cyc:
            s0, per = cyc
            state0 = {}
            for t in sorted(ev):
                if t <= s0:
                    state0.update(ev[t]["lights"])
            lead = steps_of(ev, 0, s0) if s0 else []
            body = lead + steps_of(ev, s0, s0 + per, state0)
            loop_step = len(lead)
            note = "runs until stopped: a cycle of %d ticks (%d ms)%s" % (
                per, round(per * TICK_MS), "; after a lead-in of %d ticks (steps 0-%d)" % (s0, len(lead) - 1)
                if lead else "")
        elif ev:
            last = max(ev)
            body = steps_of(ev, 0, last + 1)
            note = "runs until stopped; sets this state and holds it" if len(ev) == 1 else \
                "runs until stopped; no exact cycle in %d ticks: the show is the first %d ticks" % (ran, last + 1)
    show = ""
    if body and any("lights" in s or "coils" in s for s in body):
        show = "lampfx_%03d" % n
        dump_show(os.path.join(SHOWS, show + ".yaml"),
                  ["ROM lamp effect (leff) %d, function %s, decoded from its code (rom/tools/leff_lift.py; "
                   "ticks in rom/rom_data/io/leff_ops/leff_%03d.json). %s." % (n, doc["fn"], n, note),
                   "Colors: ffffff = on, 7f7f7f = one plane only (dim / blink phase), 000000 = off."], body)
    os.makedirs(OPS_DIR, exist_ok=True)
    with open(os.path.join(OPS_DIR, "leff_%03d.json" % n), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, separators=(",", ":"))
        f.write("\n")
    used = sorted({k for s in body for k in s.get("lights", {})})
    pulsed = sorted({k for s in body for k in s.get("coils", {})})
    return {"leff": n, "fn": doc["fn"], "flags": "0x%04x" % doc["flags"], "lamp_group": doc["group"],
            "lamp_group_lamps": " ".join(map(str, doc["group_lamps"])), "coil_group": doc["coil_group"],
            "priority": doc["priority"], "end_tick": "" if end is None else end,
            "run_ms": round(end * TICK_MS) if end is not None else "", "loops": "yes" if loops else "",
            "loop_step": loop_step,
            "show": show, "steps": len(body), "lamps_used": len(used), "coils_pulsed": " ".join(pulsed),
            "sounds": " ".join(sorted({"%x" % o["call"] for o in doc["ops"] if o["op"] == "sound"})),
            "deffs_started": " ".join(sorted({str(o["deff"]) for o in doc["ops"] if o["op"] == "deff"})),
            "leffs_started": " ".join(sorted({str(o["leff"]) for o in doc["ops"] if o["op"] == "leff"})),
            "started_by_code": " | ".join(sorted(sites.get(n, []))),
            "note": note or "no lamp or flasher of its own when run with no game state (it reads the game, "
                             "or a caller's argument)", "tag": "code"}


def main():
    src = sys.argv[1]
    lights, coils = names()
    sites = started_by()
    rows = []
    for p in sorted(glob.glob(os.path.join(src, "leff_*.json"))):
        doc = json.load(open(p))
        if "error" in doc:
            print(doc["leff"], "error", doc["error"])
            continue
        rows.append(package(doc, lights, coils, sites))
    keep = {int(os.path.basename(p)[7:10]) for p in glob.glob(os.path.join(SHOWS, "lampfx_*.yaml"))}
    for n in keep - {r["leff"] for r in rows if r["show"]}:
        os.remove(os.path.join(SHOWS, "lampfx_%03d.yaml" % n))
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "leffs,", sum(1 for r in rows if r["show"]), "shows")


if __name__ == "__main__":
    main()
