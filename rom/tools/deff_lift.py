"""Decode each display effect (deff) of tf_180 from its code: the op list of its draw function.

Runs the deff's function from the deff table (0x040ce7c4, 8-byte records: fn, flags u16, priority u8;
`deff_start` [0x000209b4]) with coderun.Runner and records, in OS ticks, every call it makes to the display
library (page fills and copies, rectangles, bitmaps, text), the page flips (what is on the DMD from that tick),
its sounds, lamp effects, other deffs, the tasks it starts, and where it ends. Each op carries `at`, the return
address of the call in the effect's code, so each value is cited by its ROM address.

Inputs an effect reads from the game (current player, side, adjustments, mode counters, random picks) are
listed per op where they are read, and set by `--state` scenarios; random_below [0x0000ba94] is answered by a
policy (0 by default; `--rng all` runs each variant).

Usage: TF_ROM=tf_180.bin deff_lift.py OUT_DIR [deff ...]   ->  OUT_DIR/deff_NNN.json
"""
import json
import os
import re
import struct
import sys

import unicorn as uc
from unicorn import arm_const as A

sys.path.insert(0, os.path.dirname(__file__))
import coderun  # noqa: E402
from coderun import rd32, cstr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DECOMP = os.path.join(HERE, "..", "code", "tf_decompiled.c")
DEFF_TABLE = 0x040ce7c4                # deff_start [0x000209b4]: fn at +0, flags u16 at +4, priority u8 at +6
N_DEFFS = 0x9c                         # deff_start rejects id 0 and id > 0x9b


def symbols():
    out = {}
    with open(DECOMP, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", line)
            if m:
                out[m.group(2)] = int(m.group(1), 16)
    return out


SYM = symbols()


def S(name):
    """A routine's address by its name in the decompile, or by its Ghidra name FUN_xxxxxxxx (the functions were
    renamed by name_functions.py; the address is the name)."""
    if name in SYM:
        return SYM[name]
    m = re.fullmatch(r"(?:thunk_)?FUN_([0-9a-f]{8})", name)
    if m:
        return int(m.group(1), 16)
    raise KeyError(name)


class DeffRunner(coderun.Runner):
    def __init__(self, rom_path=None, state=None):
        super().__init__(rom_path)
        self.state = dict(state or {})
        self.rng = []
        self._install()
        self.in_stub = False
        self.m.hook_add(uc.UC_HOOK_MEM_WRITE, self._page_write, begin=coderun.PAGE_BASE,
                        end=coderun.PAGE_BASE + 0x1e000)

    def _page_write(self, m, access, address, size, value, data):
        pc = m.reg_read(A.UC_ARM_REG_PC)
        key = pc
        if key not in self.unmodelled:
            self.unmodelled[key] = 0
        self.unmodelled[key] += 1

    def reset(self):
        super().reset()
        self.unmodelled = {}
        self.reads = []
        self.text_note = None
        self.m.mem_write(0x00031494, b"\0\0\0\0")     # language: English (FUN_00009888 [0x00009888])

    # -- the stubs ----------------------------------------------------------------------------------------
    def _install(self):
        a = self.arg
        st = self.stub

        def rec(kind, n, names=None, ret=None, strarg=None):
            def f(r):
                args = [a(i) for i in range(n)]
                kw = {"args": args} if names is None else dict(zip(names, args))
                if strarg is not None:
                    kw["str"] = cstr(r.m, args[strarg])
                r.op(kind, **kw)
                return ret
            return f

        # scheduling [0x0000acfc task_sleep; the ones below sleep inline after their first step]
        st(S("task_sleep"), "task_sleep", lambda r: (r.op("sleep", ticks=a(0)), r.sleep(a(0))))

        def sleep_prio(r):                     # 0x0002108c: deff priority (0x00020e84) then task_sleep
            r.op("prio", prio=a(1) & 0xff)
            r.op("sleep", ticks=a(0))
            r.sleep(a(0))
        st(S("FUN_0002108c"), "deff_prio_sleep", sleep_prio)

        def flip_sleep(r):                     # 0x00020374: swap work and shown pages (0x000202ec), sleep
            swap(r)
            r.op("sleep", ticks=a(0))
            r.sleep(a(0))
        st(S("FUN_00020374"), "swap_sleep", flip_sleep)

        def show_sleep(r):                     # 0x000201f0: dmd_show_pages(work fg, work bg), sleep
            show(r, rd32(r.m, WORK["fg"]), rd32(r.m, WORK["bg"]))
            r.op("sleep", ticks=a(0))
            r.sleep(a(0))
        st(S("FUN_000201f0"), "show_sleep", show_sleep)
        st(S("FUN_00020e84"), "deff_prio", lambda r: (r.op("prio", prio=a(0) & 0xff), 1)[1])

        # the DMD pages
        def show(r, fg, bg):                   # dmd_show_pages [0x00020134]: pages <= 29; previous pair kept
            w = lambda adr, v: r.m.mem_write(adr, struct.pack("<I", v))
            w(SHOWN_PREV["bg"], rd32(r.m, SHOWN["bg"]))
            w(SHOWN_PREV["fg"], rd32(r.m, SHOWN["fg"]))
            w(SHOWN["bg"], bg)
            w(SHOWN["fg"], fg)
            r.op("show", fg=fg, bg=bg)
            return 1

        def swap(r):                           # 0x000202ec: show the work pair, draw next on the pair shown before
            wf, wb = rd32(r.m, WORK["fg"]), rd32(r.m, WORK["bg"])
            sf, sb = rd32(r.m, SHOWN["fg"]), rd32(r.m, SHOWN["bg"])
            show(r, wf, wb)
            r.m.mem_write(WORK["fg"], struct.pack("<I", sf))
            r.m.mem_write(WORK["bg"], struct.pack("<I", sb))
        st(S("dmd_show_pages"), "dmd_show_pages", lambda r: show(r, a(0), a(1)))
        st(S("FUN_000202ec"), "swap_pages", swap)
        st(S("FUN_0001fb78"), "clear_bg", self._fill("bg", 0))
        st(S("FUN_0001fb94"), "clear_fg", self._fill("fg", 0))
        st(S("FUN_0001fd04"), "fill_fg", self._fill("fg", None))
        st(S("FUN_0001fc90"), "fill_page", rec("fill", 2, ["page", "value"]))
        st(S("FUN_0001fbe8"), "copy_page", rec("copy", 2, ["dst", "src"]))
        st(S("FUN_0001fd70"), "rect", rec("rect", 6, ["page", "x0", "y0", "x1", "y1", "value"]))
        st(S("FUN_0001f8bc"), "frame_rect", rec("frame", 6, ["page", "x0", "y0", "x1", "y1", "value"]))
        def bitmap(kind, n):                   # bitmap_draw [0x00023d28], bitmap_draw2 [0x00023c7c]
            def f(r):
                args = [a(i) for i in range(n)]
                d = dict(zip(["img", "page", "x", "y", "a", "b"], args))
                if d["a"]:
                    d["palette"] = list(bytes(r.m.mem_read(d["a"], 16)))
                r.op(kind, **d)
            return f
        st(S("bitmap_draw"), "bitmap_draw", bitmap("bitmap", 6))
        st(S("bitmap_draw2"), "bitmap_draw_masked", bitmap("bitmap_masked", 5))
        # text: the helpers format the string (msg_get [0x000099f0], vsprintf [0x0002fef0]) and pick the font
        # of a fit list (text_draw_str_fit [0x00021b90]) in ROM code; the glyphs are drawn by text_draw_str
        # [0x00021878], the stub. A helper call is noted with its call site, message and printf arguments.
        for name, nfix, kind in [("text_draw_msg_page", 7, "msg"), ("text_printf_msg", 7, "msg"),
                                 ("text_printf_msg_fit_page", 8, "msg"), ("text_draw_msg_fit", 8, "msg"),
                                 ("text_draw_str_page", 7, "str"), ("text_printf_page", 7, "str"),
                                 ("text_draw_str_fit_page", 8, "str"), ("text_draw_str_fit", 8, "str")]:
            st(S(name), name, self._text_note(name, nfix, kind))
        st(S("text_draw_str"), "text_draw_str", self._text_draw)

        # the same primitives on a page pointer (0x01080000 + page * 0x1000)
        def pg(x):
            return (x - coderun.PAGE_BASE) >> 12
        st(S("FUN_0001fb60"), "clear_ptr", lambda r: (r.op("fill", page=pg(a(0)), value=0), None)[1])
        st(S("FUN_0001fcc4"), "fill_ptr", lambda r: (r.op("fill", page=pg(a(0)), value=a(1) & 0xff), None)[1])
        st(S("FUN_0001fdc4"), "rect_ptr", lambda r: (r.op(
            "rect", page=pg(a(0)), x0=a(1), y0=a(2), x1=a(3), y1=a(4), value=a(5) & 0xff), None)[1])
        st(S("FUN_0001f910"), "frame_ptr", lambda r: (r.op(
            "frame", page=pg(a(0)), x0=a(1), y0=a(2), x1=a(3), y1=a(4), value=a(5) & 0xff), None)[1])

        def copy_rect(r):                      # 0x0001fc28 (dst, src, w, h): copy a w x h block, rows of 0x80
            d, s_ = a(0) - coderun.PAGE_BASE, a(1) - coderun.PAGE_BASE
            r.op("copy_rect", dst=d >> 12, src=s_ >> 12, dx=d & 0x7f, dy=(d & 0xfff) >> 7,
                 sx=s_ & 0x7f, sy=(s_ & 0xfff) >> 7, w=a(2), h=a(3))
        st(S("FUN_0001fc28"), "copy_rect", copy_rect)

        # game-code draw helpers
        def remap(r):                          # 0x01006bb8 = 0x01006cf4 (ptr, x0, y0, x1, y1): dim a box
            d = a(0) - coderun.PAGE_BASE       # pixel = table[pixel & 0xf], table 0x040c5ec3 (16 bytes)
            r.op("remap", page=d >> 12, x0=a(1), y0=a(2), x1=a(3), y1=a(4), table="0x040c5ec3",
                 map=list(bytes(r.m.mem_read(0x040c5ec3, 16))))
        st(S("FUN_01006bb8"), "dim_box", remap)
        st(S("FUN_01006cf4"), "dim_box2", remap)

        def invert(r):                         # 0x0002b808 (x, y, w, h): the edit cursor; each dot of the box
            x, y, w, h = a(0), a(1), a(2), a(3)        # on the fg work page becomes 0xf if it was 0, else 0
            if x < 0x80 and not y & 0x80000000 and w and h and y < 0x20:
                r.op("invert", page=rd32(r.m, WORK["fg"]), x=x, y=y, w=w, h=h)
        st(S("FUN_0002b808"), "invert_box", invert)

        def dissolve(r):                       # 0x01034758(ticks): 7 steps from the shown pair to the work
            r.op("dissolve", ticks=a(0), table="0x040c76e8", work=[rd32(r.m, WORK["fg"]), rd32(r.m, WORK["bg"])])   # pair through mask table 0x040c76e8 (10 x 8),
            r.op("sleep", ticks=8 * max(1, a(0)))               # each with the panel, then the work pair
            r.sleep(8 * max(1, a(0)))
        st(S("FUN_01034758"), "dissolve", dissolve)

        # flash banks [0x00011274]
        st(S("FUN_00011274"), "flash_bank", lambda r: r.set_bank(a(0) & 0xff) & 0xf)

        # sound, lamp effects, other deffs
        def play(r):                           # snd_play(call) [0x000251f4]: a random sample of the call
            r.op("sound", call=a(0) & 0xffff)
            return 1
        st(S("snd_play"), "snd_play", play)

        def play_sample(r):                    # 0x00025250 (call, sample): that sample of the call
            r.op("sound", call=a(0) & 0xffff, sample=a(1) & 0xffff)
            return 1
        st(S("FUN_00025250"), "snd_play_sample", play_sample)

        def panel(r):                          # 0x0102f200(page): the status panel (scores, ball, credits)
            r.op("panel", page=a(0))
        # the status panel 0x0102f200 runs as ROM code: its texts are ops (call sites 0x0102f2ec, 0x0102f36c ...)

        def sound(r):                          # snd_resolve_call(call, handle, idx*, fixed) [0x00025044]
            fixed = a(3) & 0xff
            r.op("sound", call=a(0) & 0xffff, sample=(rd32(r.m, a(2)) if fixed else None))
            return 1
        st(S("snd_resolve_call"), "snd_resolve_call", sound)
        st(S("snd_play_after"), "snd_play_after", rec("sound_after", 2, ["call", "after"], ret=0))
        st(S("leff_start"), "leff_start", lambda r: (r.op("leff", leff=a(0) & 0xffff), 0x39f00)[1])
        st(S("deff_start"), "deff_start", rec("deff", 3, ["deff", "queue", "force"], ret=1))

        # tasks
        def create(r, unique):
            tid, fn = (a(0), a(1)) if unique else (a(0) if False else 0, a(0))
            if unique:
                t = r.new_task(tid, fn, a(2))
                r.kill(lambda x: x.tid == tid and x is not t)
            else:                               # task_create(id, fn, flags, stack) or helper (fn, id, flags)
                t = r.new_task(a(0), a(1), a(2))
            r.op("task", fn="0x%08x" % t.fn, id=t.tid)
            return t.struct
        st(S("task_create"), "task_create", lambda r: create(r, False))
        st(S("FUN_0000ab4c"), "task_create_unique", lambda r: create(r, True))

        def create_child(r):                   # 0x0000ac20 (fn, id, stack): child of the current task
            t = r.new_task(a(1), a(0), 0)
            r.op("task", fn="0x%08x" % t.fn, id=t.tid)
            return t.struct
        st(S("FUN_0000ac20"), "task_create_child", create_child)

        def kill_children(r):                  # 0x0000ade4 -> 0x0000ad64: end the tasks this task started
            r.kill(lambda x: x.parent is r.cur)
            r.op("kill_children")
            return 1
        st(S("FUN_0000ade4"), "kill_children", kill_children)
        st(S("FUN_0000b3b0"), "child_running",          # 0x0000b3b0: is a task of this one alive
           lambda r: int(any(x.alive and x.parent is r.cur for x in r.tasks)))

        def kill(r):
            tid = a(0) & 0xffff
            r.kill(lambda x: x.tid == tid)
            r.op("task_kill", id=tid)
            return 0
        st(S("task_kill"), "task_kill", kill)

        # game state read by effects
        def getter(name, key, default):
            def f(r):
                v = r.state.get(key, default)
                r.reads.append((name, "0x%08x" % r.caller(), v))
                return v
            return f
        st(S("current_player"), "current_player", getter("current_player", "player", 1))
        st(S("num_players"), "num_players", getter("num_players", "players", 1))
        st(S("player_side"), "player_side", getter("player_side", "side", 2))   # 2 Decepticon
        st(S("flipper_buttons_held"), "flipper_buttons_held", getter("flipper_buttons_held", "flippers", 0))

        def rnd(r):
            n = a(0)
            v = r.state.get("rng", 0)
            v = v(n, r) if callable(v) else min(v, max(n - 1, 0))
            r.rng.append((n, v, "0x%08x" % r.caller()))
            r.op("random", n=n, value=v)
            return v
        st(S("random_below"), "random_below", rnd)
        st(S("error_log"), "error_log", rec("error", 1, ["code"], ret=0))

    def _fill(self, which, value):
        def f(r):
            v = self.arg(0) & 0xff if value is None else value
            page = rd32(r.m, WORK[which])
            r.op("fill", page=page, value=v)
        return f

    def _text_note(self, name, nfix, kind):
        def f(r):
            if r.text_note is not None and r.text_note["depth_sp"] > r.m.reg_read(A.UC_ARM_REG_SP):
                return coderun.NOTE            # a helper inside a helper: the outer call is the site
            args = [self.arg(i) for i in range(nfix + 4)]
            d = {"helper": name, "at": "0x%08x" % r.caller(), "depth_sp": r.m.reg_read(A.UC_ARM_REG_SP)}
            if kind == "msg":
                d["msg"] = args[0] & 0xffff
                try:
                    lst = rd32(r.m, MSG_TABLE + 4 * d["msg"])      # msg_get [0x000099f0], language 0
                    d["format"] = cstr(r.m, rd32(r.m, lst)) if lst else None
                except uc.UcError:
                    d["format"] = None
            else:
                try:
                    d["format"] = cstr(r.m, args[0])
                except uc.UcError:
                    d["format"] = None
            if "printf" in name:
                d["printf"] = True
                d["varargs"] = args[nfix:nfix + 4]
            if nfix == 8:
                fl = args[2]
                if fl > 0x100:
                    lst = []
                    while len(lst) < 8 and rd32(r.m, fl + 4 * len(lst)):
                        lst.append(rd32(r.m, fl + 4 * len(lst)))
                    d["font_list"] = lst
                d["fit"] = args[7]
            r.text_note = d
            r.text_note_end = r.caller()
            return coderun.NOTE
        return f

    def _text_draw(self, r):
        """text_draw_str(str, buf, font, flags, x, baseline y, palette) [0x00021878]."""
        args = [self.arg(i) for i in range(7)]
        d = {"page": (args[1] - coderun.PAGE_BASE) >> 12, "text": cstr(r.m, args[0]), "font": args[2],
             "flags": args[3] & 0xff, "x": args[4] - (1 << 32 if args[4] & 0x80000000 else 0),
             "y": args[5] - (1 << 32 if args[5] & 0x80000000 else 0)}
        if args[6]:
            d["palette"] = list(bytes(r.m.mem_read(args[6], 16)))
        note = r.text_note
        if note is not None:
            d.update({k: v for k, v in note.items() if k not in ("depth_sp",)})
        o = r.op("text", **d)
        if note is not None:
            o["at"] = note["at"]
            r.text_note = None


WORK = {}
MSG_TABLE = 0x040dc0f0                                 # msg_get [0x000099f0]: per message, a list of languages
SHOWN = {"fg": 0x00037658, "bg": 0x00037654}          # dmd_show_pages [0x00020134]: current pair
SHOWN_PREV = {"fg": 0x00037668, "bg": 0x00037664}     # and the pair shown before it


def work_pages():
    """RAM of dmd_work_page_fg / _bg: literals of FUN_0001fb94 (fg) and FUN_0001fb78 (bg)."""
    import capstone
    rom = open(coderun.ROM_PATH or os.environ["TF_ROM"], "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    for key, fn in (("fg", S("FUN_0001fb94")), ("bg", S("FUN_0001fb78"))):
        for i in md.disasm(rom[fn:fn + 0x20], fn):
            m = re.match(r"r\d+, \[pc, #(0x[0-9a-f]+)\]", i.op_str)
            if i.mnemonic == "ldr" and m:
                lit = i.address + 8 + int(m.group(1), 16)
                WORK[key] = struct.unpack_from("<I", rom, lit)[0]
                break


def deff_table(m):
    out = {}
    for d in range(1, N_DEFFS):
        rec = bytes(m.mem_read(DEFF_TABLE + 8 * d, 8))
        fn, flags, prio = struct.unpack_from("<IHB", rec)
        out[d] = {"fn": fn, "flags": flags, "priority": prio}
    return out


def lift(runner, deff, info, max_ticks=1500):
    runner.state.setdefault("rng", 0)
    ops = runner.run(info["fn"], max_ticks=max_ticks)
    return {"deff": deff, "fn": "0x%08x" % info["fn"], "flags": info["flags"], "priority": info["priority"],
            "end_tick": runner.ended_tick, "ran_ticks": runner.now, "detached": runner.detached, "ops": ops,
            "reads": runner.reads, "unmodelled_page_writes": {"0x%08x" % k: v for k, v in runner.unmodelled.items()}}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    work_pages()
    r = DeffRunner()
    table = deff_table(r.m)
    ids = [int(x) for x in sys.argv[2:]] or sorted(table)
    for d in ids:
        info = table[d]
        if not info["fn"]:
            continue
        try:
            res = lift(r, d, info)
        except Exception as e:      # noqa: BLE001
            res = {"deff": d, "fn": "0x%08x" % info["fn"], "error": str(e), "ops": r.ops}
        with open(os.path.join(out, "deff_%03d.json" % d), "w") as f:
            json.dump(res, f, indent=0)
        print(d, res.get("error") or "end %s ops %d unmodelled %s" % (
            res["end_tick"], len(res["ops"]), res["unmodelled_page_writes"]))


if __name__ == "__main__":
    main()
