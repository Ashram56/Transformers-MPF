"""Decode what each playfield switch does in a game of tf_180 by running its handler as ROM code.

The OS switch dispatcher switch_dispatch_debounce [0x0000dc44], on a closure that passes the switch record's
game-state mask (+0x0e against DAT_00031468): task_create(id +0x14, fn +0x00, flags +0x0c, 0x300) with
+0x30 = the switch number and +0x34 = the record's argument (+0x04), then event 0x6c (mask bit 0x2000) or
0x6b (bit 0x1000) with the switch number. The switch records are 0x20 bytes at 0x040e2c20 + n * 0x20.

This runs, in Unicorn (coderun runners), the OS init and the game's device registration (ball_search.boot),
game_init [0x00019c64] (event 0x2f, the player and mode inits, ball_start [0x00019d30], serve_ball(3)), then
the scenario of rules/traces/switches.txt: the validating left sling, then every playfield switch hit twice,
2 s (125 ticks) apart, every task the game starts running on between hits. event_post, score_add, audit_add
and every other routine run as ROM code; the run records the calls (with the caller's ROM address):
score_add [0x0001caf0] and the player's score at DAT_021109e4, sounds, deffs, leffs, coil pulses, audits.

Usage: TF_ROM=tf_180.bin switch_lift.py OUT_JSON [OUT_CSV [TRACE_JSONL]]
  OUT_JSON  rom_data/rules/switch_lift.json (the op lists), OUT_CSV  rules/switch_handlers.csv (the table),
  TRACE_JSONL  rules/traces/switches.jsonl: adds the column `trace` (confirmation only, rule 4)
"""
import collections
import csv
import json
import os
import struct
import sys

import unicorn as uc
from unicorn import arm_const as A

sys.path.insert(0, os.path.dirname(__file__))
import ball_search  # noqa: E402
import coderun  # noqa: E402
from coderun import NOTE, rd32  # noqa: E402
import deff_lift  # noqa: E402
from deff_lift import S  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SW_TABLE = 0x040e2c20          # switch records, 0x20 bytes, number n at + n * 0x20 (error_log_wrap_d2d4 [0x0000d2d4])
DED_TABLE = 0x040e3740         # dedicated switches 0x81.. (D1..D32): record at + (n - 0x81) * 0x20 (same routine)


_STARTS = []


def func_of(addr):
    """The decompile's function that holds addr."""
    import bisect
    import re
    if not _STARTS:
        src = open(os.path.join(HERE, "..", "code", "tf_decompiled.c"), encoding="utf-8").read()
        _STARTS.extend(sorted(int(m.group(1), 16) for m in re.finditer(r"^// ==== ([0-9a-f]{8}) ", src, re.M)))
    return _STARTS[bisect.bisect_right(_STARTS, addr) - 1]


def record(sw):
    """The switch's record, as error_log_wrap_d2d4 [0x0000d2d4] finds it."""
    return SW_TABLE + sw * 0x20 if sw < 0x41 else DED_TABLE + (sw - 0x81) * 0x20
SCORE_P1 = 0x021109e4          # player scores, u32 each (sw_energon_left [0x01033a28] adds into it)
GAME_STATE = 0x00031468        # DAT_00031468, the game-state bits the dispatcher masks with
THUNKS = 0x02680000            # free RAM for the event thunks and dummy effect structs
TICK_S = 0.016                 # the OS tick, 16.0 ms (owner 2026-11-25)
CLOSED_TICKS = 4               # the tracer's hit (rom/tools/trace/tf_ref.cpp pulse): switch closed 60 ms,
AFTER_TICKS = 8                # then 100 ms before the next command. The emulator overshoots each step, so the
#                                scenario's hits came 2.18 s apart (switches.jsonl marks, 19.58 to 144.03 s over
#                                57 hits), not 2.16: 8 ticks here reproduce that spacing (137 ticks = 2.19 s).
#                                This is the test's input timing, not a value of the ROM; one row depends on it
#                                (2-bank top, repeat: 75,000 once the Blackout battle timer has run out).
RECORD = ("score", "sound", "deff", "leff", "coil", "coil_fn", "coil_group", "coil_group_fn", "pulse",
          "pulse_queued", "audit", "error", "flag_set", "flag_clear", "sim")
STATUS_AUDITS = {59, 60, 61, 62, 63, 64}       # switch-activity counters every closure adds (as switch_spec.py)


class SwitchRunner(ball_search.SearchRunner):
    def __init__(self, rom_path=None):
        super().__init__(rom_path)
        a = self.arg
        st = self.stub

        def note(kind, names):
            def f(r):
                r.op(kind, **dict(zip(names, [a(i) for i in range(len(names))])))
                return NOTE
            return f
        # the game state the effect runners answer in Python (deff_lift) is the ROM's own here: the current
        # player, the player count, the side byte 0x02112107 + player and the flipper buttons (the flipper
        # table 0x00031458, switches 137 / 139) are read by their ROM routines
        for name in ("current_player", "num_players", "player_side", "flipper_buttons_held"):
            self.stubs.pop(S(name), None)
        # random_below [0x0000ba94]: the emulator's draws cannot be known from the code (they depend on its
        # timing), so each draw is an input of the run like a switch hit: rand_inputs maps the ROM function
        # that draws to its answers in order; any other draw answers 0. Every draw is recorded.
        self.rand_inputs = {}

        def rnd(r):
            n = a(0)
            f = func_of(r.caller())
            q = r.rand_inputs.get(f)
            v = min(q.pop(0) if q else 0, max(n - 1, 0))
            r.op("random", n=n, value=v, fn="0x%08x" % f)
            return v
        st(S("random_below"), "random_below", rnd)
        # every award goes through score_add_player [0x0001cb0c] (score_add [0x0001caf0] applies the playfield
        # multiplier and tail-calls it; the end-of-ball bonus calls it directly): the value as scored, the caller
        # a deff lowering its own priority (error_log_user_20e84 [0x00020e84] -> leaf_20ec4 [0x00020ec4]: when the
        # active deff 0x00032464 is the task's (+0x24), its priority 0x00032466 takes the new value), also inside
        # default_user_2108c [0x0002108c] before its sleep: the display manager then lets a higher one replace it
        def set_prio(r, prio):
            if r.cur is not None:
                did = struct.unpack("<H", bytes(r.m.mem_read(r.cur.struct + 0x24, 2)))[0]
                act = struct.unpack("<H", bytes(r.m.mem_read(0x00032464, 2)))[0]
                if act and act == did:
                    r.m.mem_write(0x00032466, bytes([prio & 0xff]))
                    return 1
            return 0
        st(S("FUN_00020e84"), "deff_prio", lambda r: (r.op("prio", prio=a(0) & 0xff), set_prio(r, a(0)))[1])

        def sleep_prio(r):
            r.op("prio", prio=a(1) & 0xff)
            set_prio(r, a(1))
            r.op("sleep", ticks=a(0))
            r.sleep(a(0))
        st(S("FUN_0002108c"), "deff_prio_sleep", sleep_prio)
        st(S("score_add_player"), "score_add_player", lambda r: (r.op("score", value=a(1), player=a(0) & 0xff), NOTE)[1])
        st(S("event_post"), "event_post", note("event", ["id", "arg"]))
        st(S("audit_add"), "audit_add", note("audit", ["id", "n"]))
        st(S("game_flag_set"), "game_flag_set", note("flag_set", ["flag"]))
        st(S("game_flag_clear"), "game_flag_clear", note("flag_clear", ["flag"]))
        # deff_start and leff_start run as ROM code (the display and lamp managers keep what runs, which the
        # rules ask: wait_display_idle [0x01006878], the show tasks of task_sleep_user_6480 [0x01006480], the
        # background evaluation bg_entry_eval [0x000178b0]); the effects run as tasks like any other.
        st(S("deff_start"), "deff_start", note("deff", ["deff", "queue", "force"]))

        st(S("leff_start"), "leff_start", note("leff", ["leff"]))
        # sounds run as ROM code too (the channels at 0x00037b94 then say what plays, which the background
        # music evaluation asks, ram_00037b94_user_255d4 [0x000255d4]); each call is recorded where it is resolved
        st(S("snd_play"), "snd_play", lambda r: NOTE)
        st(S("FUN_00025250"), "snd_play_sample", lambda r: NOTE)
        st(S("snd_resolve_call"), "snd_resolve_call", note("sound", ["call"]))
        st(S("snd_play_after"), "snd_play_after", note("sound_after", ["call", "after"]))
        # the OS task list, answered on the runner's tasks (the ROM code would walk the OS's own, empty list)
        def others(r):
            return [t for t in r.tasks if t.alive and t is not r.cur]

        def flags(r, t):
            return struct.unpack("<H", bytes(r.m.mem_read(t.struct + 2, 2)))[0]

        st(S("task_running"), "task_running",                      # [0x0000b248]
           lambda r: int(any(t.tid == (a(0) & 0xffff) for t in others(r))))
        st(S("task_running_range"), "task_running_range",          # [0x0000b2ac]
           lambda r: int(any((a(0) & 0xffff) <= t.tid <= (a(1) & 0xffff) for t in others(r))))

        def kill(r):                                               # task_kill(id, keep mask) [0x0000ae1c]
            tid, keep = a(0) & 0xffff, a(1) & 0xffff
            hit = [t for t in others(r) if t.tid == tid or (tid == 0 and not flags(r, t) & keep)]
            for t in hit:
                r.exit(t)
            r.op("task_kill", id=tid, keep=keep, n=len(hit))
            return int(bool(hit))
        st(S("task_kill"), "task_kill", kill)

        def kill_range(r):                                         # task_kill_range(lo, hi) [0x0000af20]
            lo, hi = a(0) & 0xffff, a(1) & 0xffff
            hit = [t for t in others(r) if lo <= t.tid <= hi]
            for t in hit:
                r.exit(t)
            r.op("task_kill", lo=lo, hi=hi, n=len(hit))
            return int(bool(hit))
        st(S("task_kill_range"), "task_kill_range", kill_range)

        def create_once(r):                    # task_running_user_aaf8(id, fn, flags, stack): only if not running
            tid = a(0) & 0xffff
            if any(t.tid == tid for t in others(r)):
                return 0
            t = r.new_task(tid, a(1), a(2))
            r.op("task", fn="0x%08x" % t.fn, id=tid)
            return t.struct
        st(S("task_running_user_aaf8"), "task_create_once", create_once)
        def remove(r):                         # event_post_user_a9bc(task) [0x0000a9bc]: end that task now
            t = next((t for t in r.tasks if t.alive and t.struct == a(0)), None)
            if t is not None and t is not r.cur:
                r.exit(t)
                r.op("task_removed", fn="0x%08x" % t.fn, id=t.tid)
            return 0
        st(0x0000a9bc, "task_remove", remove)
        # create_child 0x0000ac20 runs as ROM code (task_create, then the parent at +0x14, its flags and args)
        st(0x0000ac20, "task_create_child", lambda r: NOTE)

        def first_in_range(r):                 # leaf_b698(lo, hi) [0x0000b698]: first task of the list in range
            lo, hi = a(0) & 0xffff, a(1) & 0xffff
            t = next((t for t in r.tasks if t.alive and lo <= t.tid <= hi), None)
            return t.struct if t else 0
        st(0x0000b698, "task_first_in_range", first_in_range)

        def first_of(r):                       # leaf_b320(ids) [0x0000b320]: another task whose id is listed
            ids, p = [], a(0)
            while p:
                v = struct.unpack("<H", bytes(r.m.mem_read(p + 2 * len(ids), 2)))[0]
                if not v:
                    break
                ids.append(v)
            t = next((t for t in others(r) if t.tid in ids), None)
            return t.struct if t else 0
        st(0x0000b320, "task_first_of", first_of)

        def set_id(r):                         # task_running_user_b4dc(id) [0x0000b4dc]: the caller takes the id
            tid = a(0) & 0xffff
            if r.cur is not None and not any(t.tid == tid for t in others(r)):
                r.cur.tid = tid
                r.m.mem_write(r.cur.struct, struct.pack("<H", tid))
            return 0
        st(0x0000b4dc, "task_set_id", set_id)
        self.keep = False
        self.main = None
        self.sim, self.trough, self.shooter = [], 4, False

    SLOTS = 60                         # task slots (coderun has 21): the effects run as tasks here too
    OS_STACK = 0x025f0000              # stack of the OS calls made between tasks (below the task structs)

    def new_task(self, tid, fn, flags=0):
        used = {t.slot for t in self.tasks if t.alive}
        slot = next((i for i in range(self.SLOTS) if i not in used), None)
        if slot is None:
            raise RuntimeError("too many tasks")
        s = coderun.SCRATCH + slot * 0x80
        self.m.mem_write(s, b"\0" * 0x80)
        self.m.mem_write(s, struct.pack("<HHI", tid & 0xffff, flags & 0xffff, fn))
        t = coderun.Task(tid, fn, s, coderun.STACKS + 0x4000 * (slot + 1))
        t.slot = slot
        t.parent = self.cur
        t.wake = self.now + (1 if self.cur is not None else 0)
        self.tasks = [x for x in self.tasks if x.alive] + [t]
        self.relink()
        return t

    def relink(self):
        """The OS task list the ROM's own walkers read (deff_start_core [0x00020498] finds the deff to end
        there): task_list_head 0x000314a0, tail 0x000314a4, each task's +0x18 previous and +0x1c next."""
        live = [t for t in self.tasks if t.alive]
        w = lambda adr, v: self.m.mem_write(adr, struct.pack("<I", v))
        w(0x000314a0, live[0].struct if live else 0)
        w(0x000314a4, live[-1].struct if live else 0)
        for i, t in enumerate(live):
            w(t.struct + 0x18, live[i - 1].struct if i else 0)
            w(t.struct + 0x1c, live[i + 1].struct if i + 1 < len(live) else 0)

    def call(self, addr, *args):
        m = self.m
        m.context_restore(self.base_ctx)
        for i, v in enumerate(args):
            m.reg_write(A.UC_ARM_REG_R0 + i, v)
        m.reg_write(A.UC_ARM_REG_SP, self.OS_STACK)
        m.reg_write(A.UC_ARM_REG_LR, coderun.STOP)
        m.emu_start(addr, coderun.STOP, count=coderun.MAX_INSN)
        return m.reg_read(A.UC_ARM_REG_R0)

    # ---- the playfield the tracer simulates (rom/tools/trace/tf_ref.cpp sim_step): 4 balls in the trough
    # (switches 21, 20, 19, 18 closed), a pulse of coil 1 moves one to the shooter lane (switch 23 closes),
    # coil 2 or the scenario's `plunge` launches it (23 opens); Optimus Prime starts down (switch 44 closed).
    def set_raw(self, sw, closed):
        """The debounced state of switch sw, as switch_dispatch_debounce [0x0000dc44] leaves it: bit n-1 of
        0x000368da, 0x000368ee and 0x00036902 (inverted for an opto, record +0x10 bit 4: error_log_wrap_d3e8
        [0x0000d3e8]). Returns the raw bit."""
        rec = record(sw)
        opto = struct.unpack("<H", bytes(self.m.mem_read(rec + 0x10, 2)))[0] & 4
        raw = int(bool(closed)) ^ int(bool(opto))
        i = sw - 1
        for base in (0x000368da, 0x000368ee, 0x00036902):
            adr = base + (i >> 4) * 2
            v = struct.unpack("<H", bytes(self.m.mem_read(adr, 2)))[0]
            v = v | (1 << (i & 15)) if raw else v & ~(1 << (i & 15))
            self.m.mem_write(adr, struct.pack("<H", v))
        return raw

    def set_trough(self):
        for i in range(4):
            self.set_raw(21 - i, i < self.trough)

    def op(self, kind, **kw):
        d = super().op(kind, **kw)
        if kind in ("pulse", "pulse_queued", "coil", "coil_fn") and kw.get("coil") in (1, 2):
            self.sim.append(kw["coil"])
        return d

    def simulate(self):
        """The tracer's ball moves for the coil pulses of this tick (sim_step)."""
        todo, self.sim = self.sim, []
        for coil in todo:
            if coil == 1 and self.trough > 0 and not self.shooter:
                self.trough -= 1
                self.shooter = True
                self.set_trough()
                for i in range(4):     # the freed trough switch opens, the shooter lane closes
                    if 21 - i == 21 - self.trough:
                        self.edge(21 - i, False)
                self.edge(23, True)
                self.op("sim", what="trough_eject", trough=self.trough)
            elif coil == 2 and self.shooter:
                self.plunge("launched")

    def plunge(self, what="plunged"):
        if self.shooter:
            self.shooter = False
            self.edge(23, False)
            self.op("sim", what=what)

    def kill(self, pred):
        for t in self.tasks:
            if t.alive and t is not self.cur and pred(t):
                self.exit(t)

    def exit(self, t):
        """A task ends (returns or is killed) as in the OS exit path event_post_user_b654 [0x0000b654] ->
        leaf_a910 [0x0000a910]: a deff task (flags 4) that is no child (+0x14 = 0) ends the active deff,
        leaf_209d4 [0x000209d4] clears deff_active_id 0x32464, its priority 0x32466 and flags 0x32467.
        Then the per-task exit calls at +0x48 (leaf_a84c [0x0000a84c], set by error_log_wrap_b598 [0x0000b598]) run."""
        t.alive = False
        self.relink()
        m = self.m
        fl = struct.unpack("<H", bytes(m.mem_read(t.struct + 2, 2)))[0]
        if fl & 8:                             # leaf_ad64 [0x0000ad64]: its children (+0x14 = it) end with it
            for c in self.tasks:
                if c.alive and c is not self.cur and rd32(m, c.struct + 0x14) == t.struct:
                    self.exit(c)
        if fl & 4 and rd32(m, t.struct + 0x14) == 0:
            m.mem_write(0x00032464, b"\0\0")
            m.mem_write(0x00032466, b"\0\0")
        for k in range(4):                     # the exit calls leaf_a84c [0x0000a84c]: fn(task, arg), then cleared
            fn = rd32(m, t.struct + 0x48 + 8 * k)
            if fn:
                arg = rd32(m, t.struct + 0x4c + 8 * k)
                m.mem_write(t.struct + 0x48 + 8 * k, b"\0\0\0\0")
                self.thunk_call(fn, t.struct, arg)
                self.op("exit_call", fn="0x%08x" % fn, task="0x%08x" % t.fn)

    def reset(self):
        if self.keep:                  # the game goes on: RAM and live tasks stay
            self.ops = []
            return
        super().reset()

    def step(self, until):
        """Run the machine until tick `until`, one OS tick at a time as the main loop ram_00031550_user
        [0x00014f68] does: the tick's OS work event_post_user_2bd48 [0x0002bd48] (event 0x20, queued pulses,
        the display queue deff_start_core_user, the lamp compositor, sounds, the switch debounce, ...), every
        task due, then the end-of-tick hooks leaf_b648 [0x0000b648]."""
        while self.now < until:
            self.clocks()
            self.os_call(0x0002bd48)
            self.run_due()
            self.os_call(0x0000b648)
            self.simulate()
            self.now += 1
        self.clocks()

    def os_call(self, fn):
        self.cur = None
        self.m.mem_write(coderun.TASK_CURRENT, b"\0\0\0\0")
        try:
            self.call(fn)
        except uc.UcError as e:
            self.op("fault", fn="0x%08x" % fn, error="%s: %s" % (e, self.fault))

    def run_due(self):
        m = self.m
        while True:
            ready = [t for t in self.tasks if t.alive and t.wake <= self.now]
            if not ready:
                return
            t = ready[0]
            self.cur = t
            m.mem_write(coderun.TASK_CURRENT, struct.pack("<I", t.struct))
            if not t.started:
                t.started = True
                m.context_restore(self.base_ctx)
                m.reg_write(A.UC_ARM_REG_SP, t.stack)
                m.reg_write(A.UC_ARM_REG_LR, coderun.STOP)
                m.reg_write(A.UC_ARM_REG_R0, t.struct)
                pc = t.fn
            else:
                m.context_restore(t.ctx)
                pc = m.reg_read(A.UC_ARM_REG_PC)
            self._switch = False
            self.fault = None
            try:
                m.emu_start(pc, coderun.STOP, count=coderun.MAX_INSN)
            except uc.UcError as e:
                self.op("fault", fn="0x%08x" % t.fn, error="%s: %s" % (e, self.fault))
                self.exit(t)
            else:
                if not self._switch:
                    self.exit(t)
                    self.op("task_end", fn="0x%08x" % t.fn)
            self.cur = None
            if t.alive and t.wake <= self.now:
                t.wake = self.now + 1

    def clocks(self):
        """The OS clocks the IO pass table_040e3c14_reader [0x000114b0] keeps (64 passes a tick):
        DAT_00031544 every pass, DAT_00031550 every 64 (the tick), DAT_0003154c every 40 (10 ms)."""
        w = lambda adr, v: self.m.mem_write(adr, struct.pack("<I", v & 0xffffffff))
        w(0x00031544, self.now * 64)
        w(0x00031550, self.now)
        w(0x0003154c, self.now * 64 // 40)

    def thunk_event(self, event, sw):
        """A task that runs event_post(event, &sw) as ROM code: mov r0, #event; ldr r1, =arg; ldr pc, =event_post."""
        self._thunk = (getattr(self, "_thunk", 0) + 1) % 32
        base = THUNKS + self._thunk * 0x40
        arg = base + 0x30
        code = struct.pack("<IIIIII", 0xe3a00000 | event, 0xe59f1004, 0xe59ff004, 0xe1a00000, arg, S("event_post"))
        self.m.mem_write(base, code)
        self.m.mem_write(arg, struct.pack("<I", sw))
        t = self.new_task(0x7e, base, 0)
        t.wake = self.now
        return t

    def thunk_call(self, fn, r0, r1):
        """A task that runs fn(r0, r1) as ROM code (ldr r0; ldr r1; ldr pc), this tick."""
        self._thunk = (getattr(self, "_thunk", 0) + 1) % 32
        base = THUNKS + self._thunk * 0x40
        code = struct.pack("<IIIIIII", 0xe59f0008, 0xe59f1008, 0xe59ff008, 0xe1a00000, r0, r1, fn)
        self.m.mem_write(base, code)
        t = self.new_task(0x7e, base, 0)
        t.wake = self.now
        return t

    def edge(self, sw, closed):
        """Switch sw changes, and switch_dispatch_debounce [0x0000dc44] handles the change once debounced: the
        record's mask +0x0e says on which edge the handler runs (raw state 1: 0x400, raw 0: 0x800), which
        game-state bits let it run (against DAT_00031468 unless that is 0); then task_create(id +0x14,
        fn +0x00, flags +0x0c) with +0x30 the switch and +0x34 the argument +0x04, and event 0x6c (mask
        0x2000) or 0x6b (0x1000) with the switch number."""
        rec = record(sw)
        fn, arg = rd32(self.m, rec), rd32(self.m, rec + 4)
        flags, mask = struct.unpack("<HH", bytes(self.m.mem_read(rec + 0x0c, 4)))
        tid = struct.unpack("<H", bytes(self.m.mem_read(rec + 0x14, 2)))[0]
        raw = self.set_raw(sw, closed)
        if not mask & (0x400 if raw else 0x800):
            return
        state = struct.unpack("<H", bytes(self.m.mem_read(GAME_STATE, 2)))[0]
        if state and not (mask & state):
            self.op("masked", switch=sw, mask=mask, state=state)
            return
        if fn:
            t = self.new_task(tid, fn, flags)
            t.wake = self.now
            self.m.mem_write(t.struct + 0x30, bytes([sw]))
            self.m.mem_write(t.struct + 0x34, struct.pack("<I", arg))
        if mask & 0x2000:
            self.thunk_event(0x6c, sw)
        elif mask & 0x1000:
            self.thunk_event(0x6b, sw)

    def hit(self, sw):
        """The scenario's hit: closed 60 ms, then open, then 100 ms before the next command."""
        self.edge(sw, True)
        self.step(self.now + CLOSED_TICKS)
        self.edge(sw, False)
        self.step(self.now + AFTER_TICKS)


def boot(r):
    """The start-up of start_deff_5_user [0x00000308]: the global constructors (0x0002c0f4 ->
    __do_global_ctors 0x0002c078, the 39 entries of 0x00033e40: each rule module's event hooks, e.g. the pop
    value at ball start 0x0102d1ec, hooked on event 0x11 by 0x0102dab8), game state 0x10, the OS init
    0x00006ecc, then the device registration 0x01005fb8 as ball_search.boot."""
    r.call(0x0002c0f4)
    r.m.mem_write(GAME_STATE, struct.pack("<H", 0x10))
    ball_search.boot(r)
    r.set_trough()
    r.set_raw(44, True)
    # start_deff_7 [0x00005630] (each OS tick until game flag 4) checks the board's ID chip through the
    # readers of 0x040c8984, hardware this runner has not got; it sets flag 4 once the check passed, else it
    # shows deff 7 (THIS MACHINE WILL NOT OPERATE IN THIS COUNTRY, priority 255). Flag 4: the check passed.
    r.call(S("game_flag_set"), 4)


def start_game(r):
    for base, size in ball_search.IO_REGIONS:
        r.m.mem_map(base, size)
    r.run(S("game_init"), setup=boot, max_ticks=1, main_tid=0x81)
    r.keep = True
    # sw_start_button [0x0001a6e4] runs game_init, then clears state bit 0x20 (the game is under way): with the
    # state at 0 every switch passes the dispatcher's mask (switch_dispatch_debounce [0x0000dc44])
    st = struct.unpack("<H", bytes(r.m.mem_read(GAME_STATE, 2)))[0]
    r.m.mem_write(GAME_STATE, struct.pack("<H", st & 0xffdf))


def random_inputs(r, path):
    """The scenario's random draws: comment lines `#! random FN V [V ...]` (the tracer ignores comments) give
    the answers of random_below when called from ROM function FN, in order."""
    for ln in open(path):
        w = ln.split()
        if w[:2] == ["#!", "random"]:
            q = r.rand_inputs.setdefault(int(w[2], 16), [])
            for v in w[3:]:
                if not v.isdigit():
                    break
                q.append(int(v))


def run_scenario(r, path):
    """The commands of a tracer scenario (rules/traces/*.txt): wait, hit, mark; one segment per mark."""
    segs, cur = [], {"mark": "start", "switch": None, "tick": r.now, "s0": rd32(r.m, SCORE_P1), "ops": []}

    def close(c):
        c["points"] = rd32(r.m, SCORE_P1) - c.pop("s0")
        c["ops"] = [o for o in r.ops if o["op"] in RECORD + ("fault", "masked", "task")]
        segs.append(c)
    for ln in open(path):
        w = ln.split("#")[0].split()
        if not w:
            continue
        if w[0] == "mark":
            close(cur)
            r.ops = []
            cur = {"mark": w[1], "switch": None, "tick": r.now, "s0": rd32(r.m, SCORE_P1), "ops": []}
        elif w[0] == "wait":
            r.step(r.now + int(round(float(w[1]) / TICK_S)))
        elif w[0] == "plunge":
            r.plunge()
        elif w[0] == "hit":
            if cur["switch"] is None:
                cur["switch"] = int(w[1])
            r.hit(int(w[1]))
    close(cur)
    return segs


def table(segs):
    """The per-switch table (rules/switch_handlers.csv) from the run: one row per hit, each value with the
    ROM routine that made it (awards: the function holding the score_add call, `handler` for the switch
    handler's own tail call)."""
    sys.path.insert(0, HERE)
    import bisect
    import re
    from leff_package import coil_group
    src = open(os.path.join(HERE, "..", "code", "tf_decompiled.c"), encoding="utf-8").read()
    starts = sorted(int(m.group(1), 16) for m in re.finditer(r"^// ==== ([0-9a-f]{8}) ", src, re.M))
    romdir = os.path.join(HERE, "..")
    sw = {int(x["number"]): x for x in csv.DictReader(open(os.path.join(romdir, "rom_data", "io", "switches.csv")))}
    role = {x["call"]: x["role"] for x in csv.DictReader(open(os.path.join(romdir, "rom_data", "sound", "sound_call_uses.csv")))}
    dname = {int(x["deff"]): x["name"] for x in csv.DictReader(open(os.path.join(romdir, "mpf_package", "event_map.csv")))}

    def fn(at):
        a = int(at, 16)
        if a == coderun.STOP:
            return "handler"
        return "0x%x" % starts[bisect.bisect_right(starts, a) - 1]

    def coils(ops):
        out = collections.Counter()
        for o in ops:
            if o["op"] in ("pulse", "pulse_queued", "coil", "coil_fn"):
                out["%d:%dms" % (o["coil"], o["ms"])] += 1
            elif o["op"] in ("coil_group", "coil_group_fn"):
                out["%s:%dms" % ("/".join(map(str, coil_group(o["group"] & 0xffff))), o["ms"])] += 1
        return " ".join(k + (" x%d" % n if n > 1 else "") for k, n in out.items())

    rows = []
    for g in segs:
        mk = g["mark"]
        if not mk.startswith("sw_"):
            continue
        n = int(mk.split("_")[1])
        ops = g["ops"]
        snd = []                       # a call retried every tick (task 0xc6's speech, 0x010250f4) counts once
        for o in ops:
            if o["op"] == "sound":
                c = "0x%03x" % o["call"]
                if snd and snd[-1][0] == c:
                    snd[-1][1] += 1
                else:
                    snd.append([c, 1])
        rows.append({
            "switch": n, "name": sw[n]["name"], "hit": "repeat" if mk.endswith("_again") else "first",
            "handler": sw[n]["handler"], "handler_arg": sw[n]["handler_arg"], "switch_flags": sw[n]["flags_0x0c"],
            "score_total": g["points"],
            "awards": " + ".join("%d (%s)" % (o["value"], fn(o["at"])) for o in ops if o["op"] == "score"),
            "sounds": " ".join(c + (" [%s]" % role[c] if role.get(c) else "") + (" x%d" % k if k > 1 else "")
                               for c, k in snd),
            "deffs": " ".join("%d %s" % (o["deff"], dname.get(o["deff"], "")) for o in ops
                              if o["op"] == "deff" and o["deff"] != 19),
            "leffs": " ".join(str(o["leff"]) for o in ops if o["op"] == "leff"),
            "coils": coils(ops),
            "audit_counters": " ".join(str(x) for x in sorted({o["id"] for o in ops if o["op"] == "audit"
                                                                and o["id"] not in STATUS_AUDITS})),
            "flags": " ".join(["+%d" % o["flag"] for o in ops if o["op"] == "flag_set"] +
                              ["-%d" % o["flag"] for o in ops if o["op"] == "flag_clear" and o["flag"] != 8]),
            "tag": "code"})
    return rows


def check(rows, trace):
    """Compare each row with the same hit in the emulator trace (switch_spec.py's reading of it): column
    `trace` says `same`, or which columns differ. Sounds 0x14c / 0x14d (the speech of task 0xc6, a random
    pick) are left out, and lists compare as sets (effects of one tick come in another order)."""
    import tempfile
    import switch_spec
    tmp = os.path.join(tempfile.mkdtemp(), "observed.csv")
    switch_spec.main(os.path.join(HERE, ".."), trace, tmp)
    obs = {(x["switch"], x["hit"]): x for x in csv.DictReader(open(tmp))}

    def norm(col, v):
        v = str(v)
        if col == "sounds":
            return sorted(x for x in v.split() if x.startswith("0x") and x not in ("0x14c", "0x14d"))
        if col == "deffs":
            return sorted(x for x in v.split() if x.isdigit())
        return sorted(v.split()) if col in ("leffs", "audit_counters", "flags") else v
    for row in rows:
        o = obs.get((str(row["switch"]), row["hit"]))
        cols = [c for c in ("score_total", "awards", "sounds", "deffs", "leffs", "audit_counters", "flags")
                if o is None or norm(c, o[c]) != norm(c, row[c])]
        row["trace"] = "same" if not cols else "differs: " + " ".join(
            "%s (trace %s)" % (c, " ".join(norm(c, o[c])) or "-") for c in cols)
    print("rows equal to the trace:", sum(r["trace"] == "same" for r in rows), "of", len(rows))


def main():
    deff_lift.work_pages()
    r = SwitchRunner()
    path = os.path.join(HERE, "..", "rules", "traces", "switches.txt")
    random_inputs(r, path)
    start_game(r)
    segs = run_scenario(r, path)
    with open(sys.argv[1], "w") as f:
        json.dump({"scenario": "rules/traces/switches.txt", "tick_ms": 16.0, "segments": segs}, f, indent=0)
    if len(sys.argv) > 2:
        rows = table(segs)
        if len(sys.argv) > 3:
            check(rows, sys.argv[3])
        with open(sys.argv[2], "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print("rows", len(rows))


if __name__ == "__main__":
    main()
