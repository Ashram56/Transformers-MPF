"""Play every reference scenario of rules/traces/ in the ROM's own code, and compare each mark with the trace.

The runner is switch_lift.py's (tf_180 in Unicorn: the module constructors [0x0002c0f4], game_init
[0x00019c64], then each 16 ms tick the OS loop [0x0002bd48], the due tasks and [0x0000b648]; a switch change
goes through the dispatcher's rules [0x0000dc44]). This file adds the rest of the tracer's commands
(rom/tools/trace/tf_ref.cpp), with the same ball model, so that the scenario's inputs are the same:

  start N           game_init for player 1, then per extra player four coins (D1 = 129, coin handler
                    0x00019c40) and the START button (switch 16, sw_start_button [0x0001a6e4])
  hit SW [MS]       closed MS (60) ms, then 100 ms; switch 3 (left eject) stays closed until coil 22 kicks;
                    38..41 (Megatron lock) take the ball into the lock (lock switches fill from 41 back)
  drain [left|right]  outlane 24 / 29 first, then the ball enters the trough (trough switches 21 back to 18)
  plunge, autoplunge S  the shooter lane (switch 23) empties now / S seconds after the ball arrived (0: never)
  button B [MS]     left / right flipper (D9 = 137, D11 = 139), tilt (D17 = 145), start (16), tournament (15)
  poke ADDR V [4]   writes RAM as the tracer does
  wait S, mark TEXT

Coil 1 moves a ball from the trough to the shooter lane, coil 2 launches it, coil 22 empties the left eject,
coil 3 releases one locked ball (as the tracer). Python only records: score_add, events, audits, game flags,
deff / leff / sound starts (the routines themselves run as ROM code).

Per mark the report gives the code run's points, awards (value and the ROM function that awarded it),
sounds, deffs and leffs, and the same columns read from the trace (confirmation only, never the source).
random_below answers 0 in the code run, so a random pick (the side at adj 65 RANDOM, a speech variant) can
differ from the emulator's.

Usage: TF_ROM=tf_180.bin python3 scenario_lift.py OUT_DIR [SCENARIO ...]
  writes OUT_DIR/<scenario>.json (op lists per mark) and OUT_DIR/summary.csv (one row per mark)
"""
import bisect
import collections
import csv
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import coderun  # noqa: E402
import deff_lift  # noqa: E402
from deff_lift import S  # noqa: E402
import switch_lift  # noqa: E402
from switch_lift import rd32, TICK_S  # noqa: E402

HERE = switch_lift.HERE
TRACES = os.path.join(HERE, "..", "rules", "traces")
SCORES = 0x021109e4            # the players' scores (u32 x 4), score_add [0x0001caf0]
BUTTONS = {"left": 137, "right": 139, "tilt": 145, "start": 16, "tournament": 15}
SPEECH = ("0x14c", "0x14d")    # task 0xc6 [0x010250f4], a random pick retried every tick


def ticks(s):
    return int(math.ceil(s / TICK_S - 1e-9))


class ScenarioRunner(switch_lift.SwitchRunner):
    def __init__(self, rom_path=None):
        super().__init__(rom_path)
        self.inplay = self.locked = 0
        self.eject = False
        self.auto = 1.0                # the tracer's default auto plunge, seconds after the ball arrives
        self.shooter_at = 0

    def op(self, kind, **kw):
        d = super().op(kind, **kw)
        if kind in ("pulse", "pulse_queued", "coil", "coil_fn") and kw.get("coil") in (3, 22):
            self.sim.append(kw["coil"])
        return d

    def simulate(self):
        todo = list(self.sim)
        was = self.shooter
        super().simulate()            # coils 1 and 2
        if self.shooter and not was:
            self.shooter_at = self.now
        for coil in todo:
            if coil == 22 and self.eject:
                self.eject = False
                self.edge(3, False)
                self.op("sim", what="left_eject")
            elif coil == 3 and self.locked:
                self.locked -= 1
                self.edge(41 - self.locked, False)
                self.inplay += 1
                self.op("sim", what="lock_release", locked=self.locked)
        if self.shooter and self.auto > 0 and (self.now - self.shooter_at) * TICK_S > self.auto:
            self.plunge("plunged")

    def plunge(self, what="plunged"):
        if self.shooter:
            self.inplay += 1
        super().plunge(what)

    def pulse(self, sw, ms):
        self.edge(sw, True)
        self.step(self.now + max(1, ticks(ms / 1000.0)))
        self.edge(sw, False)

    def hit(self, sw, ms=60):
        if sw == 3:
            self.eject = True
            self.edge(3, True)
            self.step(self.now + ticks(0.05))
        elif 38 <= sw <= 41:
            if self.inplay > 0 and self.locked < 4:
                self.inplay -= 1
                self.locked += 1
                self.edge(41 - (self.locked - 1), True)
            self.step(self.now + ticks(0.05))
        else:
            self.pulse(sw, ms)
        self.step(self.now + switch_lift.AFTER_TICKS)

    def drain(self, via):
        if self.inplay <= 0:
            self.op("sim", what="drain_ignored_no_ball")
            return
        if via == "left":
            self.pulse(24, 60)
        elif via == "right":
            self.pulse(29, 60)
        self.inplay -= 1
        self.trough += 1
        self.edge(21 - (self.trough - 1), True)
        self.op("sim", what="drain", trough=self.trough)
        self.step(self.now + ticks(0.1))

    def button(self, b, ms):
        sw = BUTTONS[b]
        if ms < 0:
            self.edge(sw, True)
        elif ms == 0:
            self.edge(sw, False)
        else:
            self.pulse(sw, ms)
            self.step(self.now + ticks(0.05))


def scores(r):
    return sum(struct.unpack("<4I", bytes(r.m.mem_read(SCORES, 16))))


def run(path):
    """One scenario: the op list and the points of each mark."""
    r = ScenarioRunner()
    switch_lift.random_inputs(r, path)
    segs, cur = [], None

    def close():
        if cur is not None:
            cur["points"] = (scores(r) if started else 0) - cur.pop("s0")
            cur["ops"] = [o for o in r.ops if o["op"] in switch_lift.RECORD + ("sim", "fault", "masked", "random")]
            segs.append(cur)
        r.ops = []
    started = False
    for ln in open(path):
        w = ln.split("#")[0].split()
        if not w:
            continue
        c = w[0]
        if not started and c not in ("start", "mark", "autoplunge"):
            continue                   # attract mode before the first start is not run (game_init starts the run)
        if c == "mark":
            close()
            cur = {"mark": " ".join(w[1:]), "tick": r.now if started else 0, "s0": scores(r) if started else 0}
        elif c == "start":
            n = int(w[1]) if len(w) > 1 else 1
            if not started:
                switch_lift.start_game(r)
                started = True
                n -= 1
            for _ in range(n):         # as the tracer: four coins (left slot D1 = 129), then START
                for _ in range(4):
                    r.pulse(129, 300)
                    r.step(r.now + ticks(0.3))
            for _ in range(n):
                r.pulse(16, 300)
                r.step(r.now + ticks(0.6))
        elif c == "wait":
            r.step(r.now + int(round(float(w[1]) / TICK_S)))
        elif c == "hit":
            r.hit(int(w[1]), float(w[2]) if len(w) > 2 else 60)
        elif c == "drain":
            r.drain(w[1] if len(w) > 1 else "")
        elif c == "plunge":
            r.plunge()
        elif c == "autoplunge":
            r.auto = float(w[1])
        elif c == "button":
            r.button(w[1], float(w[2]) if len(w) > 2 else 100)
        elif c == "poke":
            adr, v = int(w[1], 16), int(w[2])
            r.m.mem_write(adr, struct.pack("<I", v) if len(w) > 3 and w[3] == "4" else bytes([v & 0xff]))
        else:
            raise SystemExit("unknown command %s in %s" % (c, path))
    close()
    return segs


def trace_marks(path):
    segs, cur = collections.OrderedDict(), None
    for ln in open(path):
        e = json.loads(ln)
        if e["ev"] == "mark":
            cur = e["text"]
            segs[cur] = []
        elif cur is not None:
            segs[cur].append(e)
    return segs


class Fn:
    def __init__(self):
        src = open(os.path.join(HERE, "..", "code", "tf_decompiled.c"), encoding="utf-8").read()
        self.starts = sorted(int(m.group(1), 16) for m in re.finditer(r"^// ==== ([0-9a-f]{8}) ", src, re.M))

    def __call__(self, a):
        a = int(a, 16) if isinstance(a, str) else a
        if a in (coderun.STOP, 0x14f38):         # the switch handler's own tail call (0x14f38: its return)
            return "handler"
        return "0x%x" % self.starts[bisect.bisect_right(self.starts, a) - 1]


def columns(code_ops, fn):
    snd = [("0x%03x" % o["call"]) for o in code_ops if o["op"] == "sound"]
    return {
        "awards": sorted("%d (%s)" % (o["value"], fn(o["at"])) for o in code_ops if o["op"] == "score"),
        "sounds": sorted(set(snd) - set(SPEECH)),
        "deffs": sorted({str(o["deff"]) for o in code_ops if o["op"] == "deff" and o["deff"] != 19}),
        "leffs": sorted({str(o["leff"]) for o in code_ops if o["op"] == "leff"}),
    }


def trace_columns(evs, fn):
    return {
        "points": sum(e["delta"] for e in evs if e["ev"] == "score"),
        "awards": sorted("%d (%s)" % (e["points"], fn(e["caller"])) for e in evs if e["ev"] == "score_add"),
        "sounds": sorted({e["call"] for e in evs if e["ev"] == "sound"} - set(SPEECH)),
        "deffs": sorted({str(e["id"]) for e in evs if e["ev"] == "deff_start" and e["id"] != 19}),
        "leffs": sorted({str(e["id"]) for e in evs if e["ev"] == "leff_start"}),
    }


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    names = sys.argv[2:] or sorted(f[:-4] for f in os.listdir(TRACES) if f.endswith(".txt"))
    deff_lift.work_pages()
    fn = Fn()
    rows = []
    for name in names:
        segs = run(os.path.join(TRACES, name + ".txt"))
        with open(os.path.join(out, name + ".json"), "w") as f:
            json.dump({"scenario": "rules/traces/%s.txt" % name, "tick_ms": 16.0, "segments": segs}, f, indent=0)
        tr = trace_marks(os.path.join(TRACES, name + ".jsonl"))
        for g in segs:
            c = columns(g["ops"], fn)
            c["points"] = g["points"]
            t = trace_columns(tr.get(g["mark"], []), fn)
            diff = [k for k in ("points", "awards", "sounds", "deffs", "leffs") if c[k] != t[k]]
            rows.append({"scenario": name, "mark": g["mark"], "tick": g["tick"], "points": c["points"],
                         "awards": " + ".join(c["awards"]), "sounds": " ".join(c["sounds"]),
                         "deffs": " ".join(c["deffs"]), "leffs": " ".join(c["leffs"]),
                         "trace": "same" if not diff else "differs: " + "; ".join(
                             "%s (trace %s)" % (k, t[k] if k == "points" else " ".join(t[k]) or "-")
                             for k in diff)})
        n = [x for x in rows if x["scenario"] == name]
        print(name, "marks", len(n), "points equal", sum("points" not in x["trace"] for x in n),
              "all equal", sum(x["trace"] == "same" for x in n), flush=True)
    with open(os.path.join(out, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
