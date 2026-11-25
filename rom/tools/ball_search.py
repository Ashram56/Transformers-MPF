"""Decode the ball search of tf_180 from its code: which coils it fires, in which order, for how long.

The search task FUN_0103b778 [0x0103b778] (task 0x2b, started by the ball-search countdown) posts event 0xd and,
when no handler refuses, counts audit 0x25 and runs, in this order:
  FUN_000025e8 [0x000025e8]  every coil 1..0x23 of the coil registry 0x00030b48 whose flags have none of 0xa0dc:
                             its search routine (+8) or a pulse of its search time (+0x12 ms) by FUN_00002160
  FUN_00006778 [0x00006778]  every ball device: its kick coil, the same way (FUN_000066a4)
  FUN_00002afc, FUN_0001d4c8 empty in this ROM
  FUN_0103be8c [0x0103be8c]  the four game devices of table 0x040d17fc (FUN_0103bdd8): eject or re-serve
  FUN_00003018 [0x00003018]  the three pop bumpers (FUN_00002f3c), FUN_00003518 [0x00003518] the two slingshots
then posts event 0xc, posts 0xe, and waits while task 0x2b runs (6 ticks a turn).

FUN_00002160 [0x00002160] starts a pulse at once (FUN_00002078: the coil's slot in 0x00035b10, 0x28 bytes) and
sleeps one tick at a time while the slot still holds it (FUN_00001da4); the 1 ms IO pass [0x000114b0] clears the
slot when the pulse time is over. The pulse starts at the next 1 ms pass, inside the tick, so a pulse of n ms
holds the search n // 16 + 1 ticks (64 ms: 5 ticks; the 16.0 ms tick, owner 2026-11-25). The queued form FUN_00001f70 [0x00001f70] waits its turn in the list 0x00031434 served once a
tick by FUN_00003758 [0x00003758] in the OS loop FUN_0002bd48 (from the next tick, one queued pulse at a time,
6 ticks between two).

Runs FUN_0103b778 in Unicorn (coderun / leff_lift runners) with those pulse routines answered in Python, every
other routine as ROM code. Usage: TF_ROM=tf_180.bin ball_search.py OUT_JSON
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import leff_lift  # noqa: E402
from deff_lift import S  # noqa: E402

TICK_MS = 16.0
SEARCH_TASK = 0x0103b778


class SearchRunner(leff_lift.LeffRunner):
    def __init__(self, rom_path=None):
        super().__init__(rom_path)
        a = self.arg
        st = self.stub
        self.pulses = {}                     # handle -> end tick
        self.queued = []                     # end ticks of the queued pulses

        def pulse_now(r):                    # FUN_00002078(coil, ms, ...): the pulse starts now
            coil, ms = a(0) & 0xff, a(1) & 0xffff
            h = len(r.pulses) + 1
            r.pulses[h] = r.now + ms // int(TICK_MS) + 1
            r.op("pulse", coil=coil, ms=ms, caller=r.caller_chain())
            return h
        st(S("FUN_00002078"), "pulse_now", pulse_now)

        def pulse_queued(r):                 # FUN_00001f70: one at a time, 6 ticks apart (FUN_00003758)
            coil, ms = a(0) & 0xff, a(1) & 0xffff
            start = max([r.now + 1] + [e + 6 for e in r.queued])
            h = len(r.pulses) + 1
            r.pulses[h] = start + ms // int(TICK_MS) + 1
            r.queued.append(r.pulses[h])
            r.op("pulse_queued", coil=coil, ms=ms, start=start, caller=r.caller_chain())
            return h
        st(S("FUN_00001f70"), "pulse_queued", pulse_queued)

        def active(r):                       # FUN_00001da4(coil, handle, queued too): still pulsing
            return 1 if r.pulses.get(a(1), 0) > r.now else 0
        st(S("FUN_00001da4"), "pulse_active", active)

        def event(r):
            r.op("event", id=a(0) & 0xffff)
            return 1
        st(S("event_post"), "event_post", event)
        st(S("audit_add"), "audit_add", lambda r: (r.op("audit", id=a(0) & 0xffff, n=a(1)), 0)[1])
        st(S("task_running"), "task_running",
           lambda r: 1 if any(t.alive and t.tid == (a(0) & 0xffff) for t in r.tasks if t is not r.main) else 0)

    def caller_chain(self):
        return "0x%08x" % self.caller()


IO_REGIONS = ((0xfff00000, 0xe0000), (0x02800000, 0x800000), (0x03000000, 0x1000000))   # peripherals, as RAM


def boot(r):
    """The OS init FUN_00006ecc [0x00006ecc] (coil slots, pop and sling tables, heap) and the game's device
    registration 0x01005fb8 (FUN_00006194(device registry) [0x00006194]), run as ROM code."""
    r.call(0x00006ecc)
    r.call(0x01005fb8)


def main():
    r = SearchRunner()
    for base, size in IO_REGIONS:
        r.m.mem_map(base, size)
    ops = r.run(SEARCH_TASK, setup=boot, max_ticks=600, main_tid=0x2b)
    out = {"task": "0x%08x" % SEARCH_TASK, "tick_ms": TICK_MS, "end_tick": r.ended_tick, "ops": ops}
    with open(sys.argv[1], "w") as f:
        json.dump(out, f, indent=1)
    for o in ops:
        if o["op"] in ("pulse", "pulse_queued", "coil", "coil_fn", "coil_group", "event", "audit", "sleep"):
            print(o["t"], o["op"], {k: v for k, v in o.items() if k not in ("t", "op", "task")})
    print("end", r.ended_tick)


if __name__ == "__main__":
    main()
