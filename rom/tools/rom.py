"""Reader for tf_180.bin (Stern Transformers Pro 1.80, SAM). Set TF_ROM to the image path."""
import os, struct
ROM_PATH = os.environ.get("TF_ROM", os.path.join(os.path.dirname(__file__), "..", "in", "tf_180.bin"))
ROM = open(ROM_PATH, "rb").read()
OS_END = 0x34058          # reset copies 0..0x34058 to SRAM; RAM block starts here
GAME_BASE, GAME_FILE, GAME_SIZE = 0x01000000, 0x40000, 0x6f090
def foff(a):
    if a < 0x100000: return a
    if GAME_BASE <= a < GAME_BASE + 0x100000: return a - GAME_BASE + GAME_FILE
    if 0x04000000 <= a < 0x04800000: return a - 0x04000000
    return None
def banked(p): return (p >> 24) * 0x800000 + (p & 0xffffff)
def u8(a): return ROM[foff(a)]
def u16(a): return struct.unpack_from("<H", ROM, foff(a))[0]
def s16(a): return struct.unpack_from("<h", ROM, foff(a))[0]
def u32(a): return struct.unpack_from("<I", ROM, foff(a))[0]
def s32(a): return struct.unpack_from("<i", ROM, foff(a))[0]
def fu32(o): return struct.unpack_from("<I", ROM, o)[0]
def cstr(a, maxlen=400):
    o = foff(a)
    if o is None: return None
    e = ROM.find(b"\0", o)
    if e < 0 or e - o > maxlen: return None
    return ROM[o:e].decode("latin1")
def isstr(a):
    s = cstr(a, 80)
    return s is not None and len(s) > 0 and all(32 <= ord(c) < 127 or c == '\n' for c in s)
def name_table(a, stride=24, maxn=400):
    """24-byte name records: 5 language pointers + 0. Returns list of English names."""
    out = []
    for i in range(maxn):
        p = u32(a + stride * i)
        if not (0x04000000 <= p < 0x04800000 and isstr(p)): break
        out.append(cstr(p))
    return out
_md = None
def md():
    global _md
    if _md is None:
        import capstone
        _md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM); _md.detail = True
    return _md
def disasm(a, size=0x200):
    o = foff(a); return list(md().disasm(ROM[o:o + size], a))
def bl_callers(target):
    out = []
    for lo, hi in [(0, OS_END), (GAME_BASE, GAME_BASE + GAME_SIZE)]:
        o0 = foff(lo)
        for i in range((hi - lo) // 4):
            w = struct.unpack_from("<I", ROM, o0 + i * 4)[0]
            if (w >> 25) & 7 == 5 and (w >> 28) != 0xf:
                off = w & 0xffffff
                if off & 0x800000: off -= 0x1000000
                pc = lo + i * 4
                if pc + 8 + off * 4 == target: out.append(pc)
    return out
def lit_users(lit_addr, lo=None, hi=None):
    """Instructions 'ldr rX, [pc, #imm]' that load the word at lit_addr."""
    out=[]
    for a in range(max(0,lit_addr-4096) & ~3, lit_addr, 4):
        w=struct.unpack_from('<I',ROM,foff(a))[0]
        if (w & 0x0f7f0000)==0x051f0000:   # ldr rd,[pc,#+-imm]
            off=w&0xfff; t=a+8+(off if w&(1<<23) else -off)
            if t==lit_addr: out.append(a)
    return out
def func_start(a, maxback=0x2000):
    """Walk back to the nearest 'stmdb sp!, {..lr}' (push with lr)."""
    for b in range(a, a-maxback, -4):
        w=struct.unpack_from('<I',ROM,foff(b))[0]
        if (w & 0xffff4000)==0xe92d4000: return b
    return None
