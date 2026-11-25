"""The value labels of the adjustments whose formatter is a function (ADJ_FMT 0x040ca7a4 {fn, msg list}).

Each formatter is the ROM's own routine, run to its return as ROM code (coderun.Runner, nothing stubbed: msg_get
[0x000099f0] with language 0 at 0x31494, vsprintf [0x0002fef0], the pricing tables), formatter(buf, value) -> the
string in buf. What each routine does, read from the decompile (FORMATTERS below), is the documentation; running it
gives the exact strings.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import coderun  # noqa: E402

FORMATTERS = {
    0x2aebc: 'sprintf(buf, "%d" [0x040c9b48], v) via 0x2fdac',
    0x2af08: 'sprintf(buf, "%d%%" [0x040c9b50], v)',
    0x26a8c: 'vsprintf(buf, msg_get(*(u16 *)0x30e96 = 0x502) = "%,02lu", v); "," = a comma every 3 digits (vsprintf 0x2fef0)',
    0x268fc: 'v = 0: msg 0x2fd; v = 16: msg 0x2fe; else "%2d:%02d" (v / 60, v % 60)',
    0x26b5c: 'v = 0: msg 0x2ff; else "%d:%02d" (v / 60, v % 60)',
    0x2696c: 'v = 0: msg 0x2b0; v = 10: msg 0x2b1; else "%d"',
    0x269b8: 'v = 0: msg 0x2ae; v = 10: msg 0x2af; else "%d"',
    0x26a08: 'v = 11: msg 0x2f9; else "%d%%"',
    0x26a4c: 'msg +0x10 of pricing record v of credit system RAM 0x30e9e (FUN_00004678)',
    0x26abc: 'v = 0: msg 0x2a7; v = 6: ""; else "%d"',
    0x26b08: 'v = 0: msg 0x308; else the language string of entry v of list 0x00030ce0 (0xe3a0, 0x98a4)',
    0x2aecc: 'v = 0: msg 1; else "%d" [0x040c9b4c]',
    0x2ae7c: 'v = 0x3d: msg 0x288; else "%d"',
    0x1035f70: 'v = 0: msg 0x6e2; else "%d"',
    0x10037b0: 'sprintf(buf, msg 0x6df, v & 0xf, v >> 16)',
}
BUF = 0x02500000
LANGUAGE = 0x31494
_r = None


def run(fn, v):
    """formatter fn applied to v, as the ROM computes it."""
    global _r
    if _r is None:
        _r = coderun.Runner()
        _r.reset()
        _r.m.mem_write(LANGUAGE, b"\0")
    _r.m.mem_write(BUF, b"\0" * 64)
    _r.call(fn, BUF, v & 0xffffffff)
    return bytes(_r.m.mem_read(BUF, 64)).split(b"\0")[0].decode("latin1")
