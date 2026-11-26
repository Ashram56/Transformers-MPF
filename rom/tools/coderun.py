"""Run one ROM task function of tf_180 by itself, its OS calls answered by Python, to list what it does.

This is how the display effects (deffs) and lamp effects (leffs) are decoded from the code instead of from
emulator captures (strict rule, owner 2026-11-24; no waiver, 2026-11-25). The game code of the effect
function runs instruction by instruction from the ROM image (Unicorn, ARM mode); every OS service it calls
that draws, sounds, lights, sleeps or reads the game state is a stub here, which records the call (with its
call site, the return address in the effect's own code) and returns. Nothing of PinMAME is used: no
hardware, no frame, no timing comes from an emulator run of the machine. What comes out is the effect's
own sequence of calls, in OS ticks, which is what its code says; the drawing is done afterwards from the
ROM's images and fonts (deff_render.py).

The OS calls are named and addressed from the decompile (rom/code/tf_decompiled.c); the semantics of each
stub are read from the routine at that address and given next to it. A call the effect makes that has no
stub runs as ROM code (small helpers: page fill, palette, arithmetic).

Tasks: the effect is a task; `task_sleep(n)` [0x0000acfc] ends its turn for n ticks (n = 0 counts as 1, the
routine stores n - 1 and the scheduler runs a task whose counter is 0 on the next pass). Tasks it creates
(`task_create` [0x0000aa04], `task_create_unique` [0x0000ab4c]) run in the same scheduler, after the
current turn, in creation order, like the OS task list.

Usage as a library: Runner(TF_ROM path).run(fn, inputs) -> list of ops.
"""
import ctypes
import os
import struct

import unicorn as uc
from unicorn import arm_const as A

ROM_PATH = os.environ.get("TF_ROM", "")

OS_END = 0x34058                      # reset copies 0..0x34058 to internal SRAM (rom_extraction.md section 2)
GAME_BASE, GAME_FILE, GAME_SIZE = 0x01000000, 0x40000, 0x6f090
STOP = 0x0003f000                     # return address of a task's top call: the task ended
SCRATCH = 0x02600000                  # task structs, outside the ROM's RAM (the 0x02000000 block is mapped
STACKS = 0x02700000                   # 8 MB; NVRAM uses 0x02100000-0x0211ffff): one 0x4000 stack per task
TASK_STRUCT = 0x68                    # task_create memset(s, 0, 0x68) [0x0000aa04]
TASK_CURRENT = 0x000314b0             # task_current: literal of task_sleep at 0x0000ad5c
WINDOW = 0x800000
BANK_REG, BANK_READBACK = 0x02580000, 0x01180000   # flash bank register and its read-back (0x00031534, 0x000315ec)
PAGE_BASE = 0x01080000                # DMD pages, 30 x 0x1000 (CPU_BOARD_IO.md)
MAX_TICKS = 4000                      # cap for effects that never end by themselves (background deffs)
MAX_INSN = 60_000_000


def rd32(m, a):
    return struct.unpack("<I", bytes(m.mem_read(a, 4)))[0]


def rd16(m, a):
    return struct.unpack("<H", bytes(m.mem_read(a, 2)))[0]


def cstr(m, a, n=200):
    b = bytes(m.mem_read(a, n))
    return b.split(b"\0")[0].decode("latin1")


NOTE = object()                       # a stub that returns NOTE only looks at the call


class TaskEnded(Exception):
    pass


class Task:
    def __init__(self, tid, fn, struct_addr, stack):
        self.tid, self.fn, self.struct, self.stack = tid, fn, struct_addr, stack
        self.ctx = None
        self.wake = 0
        self.alive = True
        self.started = False


class Runner:
    """One machine image. stubs: {address: (name, handler(runner, args) -> return value or None)}."""

    def __init__(self, rom_path=None):
        rom_path = rom_path or ROM_PATH
        self.rom = open(rom_path, "rb").read()
        m = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_ARM)
        m.mem_map(0, 0x100000)
        m.mem_write(0, self.rom[:0x100000])            # OS, then RAM whose initial values are the ROM's bytes
        m.mem_map(GAME_BASE, 0x80000)
        m.mem_write(GAME_BASE, self.rom[GAME_FILE:GAME_FILE + GAME_SIZE])
        m.mem_map(PAGE_BASE, 0x20000)
        m.mem_map(0x01100000, 0x100000)                # switches, DMD page registers, bank read-back
        m.mem_map(0xfffe0000, 0x20000)                 # AT91 peripherals (timers, AIC): zero
        m.mem_map(0x02000000, 0x800000)
        m.mem_map(0x04000000, 0x800000)
        m.mem_write(0x04000000, self.rom[:0x800000])
        self.m = m
        # the flash bank window 0x04800000 is host memory (a bank switch copies into it, set_bank); while the
        # sound FIQ runs (window_mmio) it is read through Python instead, since the mixer changes bank for
        # every voice it reads
        self._win = ctypes.create_string_buffer(WINDOW)
        self._bank_data = {}
        m.mem_map_ptr(0x04800000, WINDOW, uc.UC_PROT_ALL, ctypes.addressof(self._win))
        self._mmio = False
        self._window = None
        self.set_bank(0)
        # the bank register itself (0x02580000, the literal at 0x00031534): the sound code writes it directly
        # (the FIQ's sample reads, snd_op_voice_start [0x00024498]), not through FUN_00011274
        m.hook_add(uc.UC_HOOK_MEM_WRITE, lambda m_, acc, adr, size, val, d: self.set_bank(val & 0xff),
                   begin=BANK_REG, end=BANK_REG)
        self.base_ctx = m.context_save()
        self.ram0 = bytes(m.mem_read(0, 0x100000))
        self.bank = 0
        self.on_tick = None
        self.stubs = {}
        self.hooked = set()
        m.hook_add(uc.UC_HOOK_MEM_UNMAPPED, self._unmapped)

    # ---- set-up -------------------------------------------------------------------------------------
    def stub(self, addr, name, fn):
        self.stubs[addr] = (name, fn)
        if addr not in self.hooked:
            self.m.hook_add(uc.UC_HOOK_CODE, self._hook, begin=addr, end=addr)
            self.hooked.add(addr)

    def _unmapped(self, m, access, address, size, value, data):
        self.fault = "unmapped access 0x%08x at pc 0x%08x lr 0x%08x" % (
            address, m.reg_read(A.UC_ARM_REG_PC), m.reg_read(A.UC_ARM_REG_LR))
        return False

    def set_bank(self, bank):
        """Flash bank in the 0x04800000 window: FUN_00011274(bank) [0x00011274]; a banked pointer is
        bank << 24 | offset (FUN_000112a0 [0x000112a0]); bank N is file offset N * 0x800000."""
        old = getattr(self, "bank", 0)
        if bank != self._window and not self._mmio:
            ctypes.memmove(self._win, self._bank(bank), WINDOW)
            self._window = bank
        self.m.mem_write(BANK_READBACK, bytes([bank & 0xff]))   # read back by the FIQ (0x000315ec) to restore it
        self.bank = bank
        return old

    def _bank(self, bank):
        buf = self._bank_data.get(bank)
        if buf is None:
            data = self.rom[bank * WINDOW:(bank + 1) * WINDOW]
            buf = self._bank_data[bank] = ctypes.create_string_buffer(data + b"\0" * (WINDOW - len(data)), WINDOW)
        return buf

    def window_mmio(self, on):
        """Between two runs only: read the bank window through Python (each read from the bank the register
        holds at that moment), or map it back as memory holding the current bank."""
        m = self.m
        if on and not self._mmio:
            m.mem_unmap(0x04800000, WINDOW)

            def rd(uc_, off, size, d):
                a = self.bank * WINDOW + off
                return int.from_bytes(self.rom[a:a + size], "little")
            m.mmio_map(0x04800000, WINDOW, rd, None, lambda *a: None, None)
            self._mmio = True
        elif not on and self._mmio:
            m.mem_unmap(0x04800000, WINDOW)
            m.mem_map_ptr(0x04800000, WINDOW, uc.UC_PROT_ALL, ctypes.addressof(self._win))
            self._mmio = False
            self._window = None
            self.set_bank(self.bank)

    # ---- state --------------------------------------------------------------------------------------
    def reset(self):
        m = self.m
        m.mem_write(0, self.ram0)
        m.mem_write(PAGE_BASE, b"\0" * 0x20000)
        m.mem_write(0x02000000, b"\0" * 0x800000)
        m.context_restore(self.base_ctx)
        self.set_bank(0)
        self.tasks, self.now, self.ops, self.cur = [], 0, [], None
        self.insn = 0
        self.ended_tick = None
        self.detached = []

    def call(self, addr, *args):
        """Run one ROM routine to its return (an initialisation routine, outside the task model)."""
        m = self.m
        m.context_restore(self.base_ctx)
        for i, v in enumerate(args):
            m.reg_write(A.UC_ARM_REG_R0 + i, v)
        m.reg_write(A.UC_ARM_REG_SP, STACKS + 0x4000 * 30)
        m.reg_write(A.UC_ARM_REG_LR, STOP)
        m.emu_start(addr, STOP, count=MAX_INSN)
        return m.reg_read(A.UC_ARM_REG_R0)

    def arg(self, i):
        """Argument i of the call being stubbed (r0-r3, then the stack)."""
        m = self.m
        if i < 4:
            return m.reg_read(A.UC_ARM_REG_R0 + i)
        return rd32(m, m.reg_read(A.UC_ARM_REG_SP) + 4 * (i - 4))

    def caller(self):
        return self.m.reg_read(A.UC_ARM_REG_LR)

    def op(self, kind, **kw):
        d = {"t": self.now, "op": kind, "at": "0x%08x" % self.caller(), "task": self.cur.tid if self.cur else None}
        d.update(kw)
        self.ops.append(d)
        return d

    # ---- tasks --------------------------------------------------------------------------------------
    def new_task(self, tid, fn, flags=0):
        """A task in a free slot (struct in SCRATCH, own stack); it runs from the next turn on."""
        used = {t.slot for t in self.tasks if t.alive}
        slot = next(i for i in range(21) if i not in used) if len(used) < 21 else None
        if slot is None:
            raise RuntimeError("too many tasks")
        s = SCRATCH + slot * 0x80
        m = self.m
        m.mem_write(s, b"\0" * 0x80)
        m.mem_write(s, struct.pack("<HHI", tid & 0xffff, flags & 0xffff, fn))
        t = Task(tid, fn, s, STACKS + 0x4000 * (slot + 1))
        t.slot = slot
        t.parent = self.cur
        t.wake = self.now + (1 if self.cur is not None else 0)
        self.tasks = [x for x in self.tasks if x.alive] + [t]
        return t

    def kill(self, pred):
        for t in self.tasks:
            if t.alive and t is not self.cur and pred(t):
                t.alive = False

    def sleep(self, ticks):
        """End the current task's turn: task_sleep semantics [0x0000acfc]."""
        self.cur.wake = self.now + max(1, ticks)
        self._yield()

    def _yield(self):
        m = self.m
        m.reg_write(A.UC_ARM_REG_PC, m.reg_read(A.UC_ARM_REG_LR))
        self.cur.ctx = m.context_save()
        self._switch = True
        m.emu_stop()

    def _hook(self, m, address, size, data):
        st = self.stubs.get(address)
        if st is None:
            return
        name, fn = st
        self._switch = False
        r = fn(self)
        if r is NOTE:                          # a note: the routine itself runs on
            return
        if self._switch:
            return
        if r is not None:
            m.reg_write(A.UC_ARM_REG_R0, r & 0xffffffff)
        m.reg_write(A.UC_ARM_REG_PC, m.reg_read(A.UC_ARM_REG_LR))

    def _count(self, m, address, size, data):
        self.insn += 1

    def run(self, fn, setup=None, max_ticks=MAX_TICKS, main_tid=0x80, main_flags=4, init_main=None):
        """Run fn as a task until every task ended or max_ticks; returns the op list."""
        self.reset()
        if setup:
            setup(self)
        main = self.new_task(main_tid, fn, main_flags)
        self.main = main
        if init_main:
            init_main(self, main)
        m = self.m
        while True:
            live = [t for t in self.tasks if t.alive]
            if self.on_tick and self.now != getattr(self, "_last_tick", None):
                self._last_tick = self.now
                self.on_tick(self)
            if not main.alive and self.ended_tick is None:
                self.ended_tick = self.now
            if not main.alive:          # the effect ended: tasks it left running are listed, not run on
                self.detached = ["0x%08x" % t.fn for t in live]
                break
            if not live:
                break
            ready = [t for t in live if t.wake <= self.now]
            if not ready:
                self.now = min(t.wake for t in live)
                if self.now > max_ticks:
                    break
                continue
            t = ready[0]
            self.cur = t
            m.mem_write(TASK_CURRENT, struct.pack("<I", t.struct))
            if not t.started:
                t.started = True
                m.context_restore(self.base_ctx)
                m.reg_write(A.UC_ARM_REG_SP, t.stack)
                m.reg_write(A.UC_ARM_REG_LR, STOP)
                m.reg_write(A.UC_ARM_REG_R0, t.struct)
                pc = t.fn
            else:
                m.context_restore(t.ctx)
                pc = m.reg_read(A.UC_ARM_REG_PC)
            self._switch = False
            self.fault = None
            try:
                m.emu_start(pc, STOP, count=MAX_INSN)
            except uc.UcError as e:
                raise RuntimeError("%s: %s" % (e, self.fault or "pc 0x%08x" % m.reg_read(A.UC_ARM_REG_PC)))
            if not self._switch:
                if m.reg_read(A.UC_ARM_REG_PC) != STOP:
                    raise RuntimeError("task 0x%x stopped at 0x%08x (instruction budget)" % (
                        t.tid, m.reg_read(A.UC_ARM_REG_PC)))
                t.alive = False
                self.op("task_end", fn="0x%08x" % t.fn)
            self.cur = None
            if t.wake <= self.now and t.alive:
                t.wake = self.now + 1
        return self.ops
