"""Draw a deff's frames from its op list (deff_lift.py), the way the ROM's display library draws them.

Every primitive is re-implemented from its routine in the decompile; images and glyphs are decoded from the
ROM image (images.py); nothing comes from an emulator.

- page: 32 rows x 128 bytes, low nibble the shade, high nibble the mask (CPU_BOARD_IO.md section 3.2).
- show(fg, bg) [0x00020134]: the DMD shows, per dot, mask = fg >> 4, dot = (bg & mask) | (fg & ~mask), low
  4 bits (the mixer: PinMAME's model, external; every TF effect that sets fg to 0xff means "background here").
- fill (0x0001fb60 / 0x0001fcc4), rect (0x0001fdc4, x0..x1 and y0..y1 inclusive, clipped), frame (0x0001f910:
  the four edges), copy (0x0001fbe8), copy_rect (0x0001fc28), remap (0x01006bb8: dot = table[dot & 0xf]).
- bitmap(img, page, x, y, a, b) [0x00023d28 -> 0x00022324 / 0x00022480]: a = 0: each image byte is copied
  unless it equals b; a = palette: byte < 16 -> palette[byte], else 0xff, copied unless equal to b.
- bitmap_masked(img, page, x, y, palette) [0x00023c7c -> 0x00022058 / 0x000221bc]: palette 0: every byte
  copied; else byte < 16 -> palette[byte], else 0xff, every byte written.
- text_draw_str(str, page, font, flags, x, y, palette) [0x00021878]: flags & 2 centres on x (x -= width >> 1),
  else flags & 4 right-aligns (x = x + 1 - width); width is text_width [0x00021378] (extent of the glyph
  boxes, offsets included). Each glyph: font record +4 glyph table (8 bytes: banked image pointer, s16 x
  offset, s16 y offset), drawn at (x + xoff, y - h + yoff + 1), bitmap_masked(palette) when the font's +0xc
  word is 0, else bitmap(palette, b = 0xff); the pen then moves w + spacing (+0xa) + xoff.
- dissolve(ticks) [0x01034758]: 7 steps; per step, dots in reading order take the next byte of the 80-byte
  table 0x040c76e8 (8 per row of the table, 10 rows, starting at row = step); 0 keeps the pair shown before,
  otherwise the work pair; the panel columns 0-40 are cleared and the panel drawn; then the work pair.

Panel: `panel` ops (0x0102f200, the status panel: scores, player, ball, credits) are not drawn here; the
frames say which ticks have it and the game draws it live (tf/score_screen.py).
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, banked, fu32  # noqa: E402
import images  # noqa: E402

FONT_COUNT, FONT_TABLE = fu32(0x30e7c), fu32(0x30e80)     # OS resource block (fonts.py)
DISSOLVE_TABLE = 0x0c76e8                                  # 0x040c76e8 in the data window (file offset)

_ptr_index = None
_rid_index = None
_cache = {}


def _maps():
    global _ptr_index, _rid_index
    if _ptr_index is None:
        _ptr_index, _rid_index = {}, {}
        for i in range(images.NMAX):
            p = fu32(images.TABLE + 4 * i)
            if p == 0xffffffff or banked(p) + 13 >= len(ROM):
                continue
            _ptr_index.setdefault(p, i)
            _rid_index.setdefault(images.header(i)["rid"], i)
    return _ptr_index, _rid_index


def image(i):
    """Raw bytes (h, w) of image i: delta formats on the image whose rid is one less (images.py)."""
    if i in _cache:
        return _cache[i]
    h = images.header(i)
    prev = None
    if h["format"] in (3, 9):
        j = _maps()[1].get(h["rid"] - 1)
        if j is not None and j != i:
            p = image(j)
            if p.shape == (h["h"], h["w"]):
                prev = bytes(p.tobytes())
    out = images.decode(i, prev)
    _cache[i] = out
    return out


def image_at(ptr):
    return image(_maps()[0][ptr])


class Font:
    def __init__(self, f):
        o = FONT_TABLE + f * 0x14
        self.rng, self.gl, self.height, self.spacing, self.masked, self.bank = struct.unpack_from("<IIHhIB", ROM, o)
        base = self.bank * 0x800000
        self.glyphs = {}
        k, p = 0, base + self.rng
        while ROM[p]:
            lo, hi = ROM[p], ROM[p + 1]
            for c in range(lo, hi + 1):
                g = base + self.gl + 8 * k
                ptr = fu32(g)
                xo, yo = struct.unpack_from("<hh", ROM, g + 4)
                self.glyphs[c] = (ptr, xo, yo)
                k += 1
            p += 2


_fonts = {}


def font(f):
    if f not in _fonts:
        _fonts[f] = Font(f)
    return _fonts[f]


def text_width(s, f):
    fo = font(f)
    pen = lo = hi = 0
    for ch in s.encode("latin1"):
        g = fo.glyphs.get(ch)
        if g is None:
            continue
        ptr, xo, yo = g
        w = image_at(ptr).shape[1]
        pen += xo
        lo, hi = min(lo, pen), max(hi, pen)
        pen += w
        lo, hi = min(lo, pen), max(hi, pen)
        pen += fo.spacing
    return hi - lo


class Screen:
    def __init__(self):
        self.pages = {}
        self.shown = (0, 0)

    def page(self, n):
        if n not in self.pages:
            self.pages[n] = np.zeros((32, 128), np.uint8)
        return self.pages[n]

    # -- primitives ---------------------------------------------------------------------------------------
    def blit(self, img, n, x, y, pal, skip, masked):
        dst = self.page(n)
        h, w = img.shape
        for yy in range(max(0, -y), min(h, 32 - y)):
            for xx in range(max(0, -x), min(w, 128 - x)):
                v = int(img[yy, xx])
                if pal is not None:
                    v = pal[v] if v < 16 else 0xff
                if not masked and v == skip:
                    continue
                dst[y + yy, x + xx] = v

    def text(self, o):
        s, f, flags, x, y = o["text"], o["font"], o["flags"], o["x"], o["y"]
        if f >= FONT_COUNT:
            return
        if flags & 2:
            x -= text_width(s, f) >> 1
        elif flags & 4:
            x = x + 1 - text_width(s, f)
        fo = font(f)
        pal = o.get("palette")
        for ch in s.encode("latin1"):
            g = fo.glyphs.get(ch)
            if g is None:
                continue
            ptr, xo, yo = g
            img = image_at(ptr)
            h, w = img.shape
            if fo.masked == 0:
                self.blit(img, o["page"], x + xo, y - h + yo + 1, pal, None, True)
            else:
                self.blit(img, o["page"], x + xo, y - h + yo + 1, pal, 0xff, False)
            x += w + fo.spacing + xo

    def compose(self, fg, bg):
        f, b = self.page(fg), self.page(bg)
        mask = f >> 4
        return ((b & mask) | (f & ~mask & 0xff)) & 0xf

    def apply(self, o):
        k = o["op"]
        if k == "fill":
            self.page(o["page"])[:] = o["value"]
        elif k == "rect":
            x0, y0, x1, y1 = o["x0"], o["y0"], o["x1"], o["y1"]
            if x0 < 0 or x1 < 0 or x0 > 127 or x1 < x0 or y0 < 0 or y1 > 31 or y1 < y0:
                return
            self.page(o["page"])[y0:y1 + 1, x0:min(x1, 127) + 1] = o["value"]
        elif k == "frame":
            p, v = self.page(o["page"]), o["value"]
            x0, y0, x1, y1 = o["x0"], o["y0"], o["x1"], o["y1"]
            p[y0, x0:x1 + 1] = v
            p[y1, x0:x1 + 1] = v
            p[y0:y1 + 1, x0] = v
            p[y0:y1 + 1, x1] = v
        elif k == "copy":
            self.page(o["dst"])[:] = self.page(o["src"])
        elif k == "copy_rect":
            src = self.page(o["src"]).reshape(-1)
            dst = self.page(o["dst"]).reshape(-1)
            so, do_ = o["sy"] * 128 + o["sx"], o["dy"] * 128 + o["dx"]
            for r in range(o["h"]):
                a, b = so + r * 128, do_ + r * 128
                n = min(o["w"], 4096 - a, 4096 - b)
                if n > 0:
                    dst[b:b + n] = src[a:a + n]
        elif k == "remap":
            p = self.page(o["page"])
            x0, y0, x1, y1 = o["x0"], o["y0"], o["x1"], o["y1"]
            m = np.array(o["map"], np.uint8)
            box = p[y0:y1 + 1, x0:x1 + 1]
            p[y0:y1 + 1, x0:x1 + 1] = m[box & 0xf]
        elif k == "bitmap":
            pal = None if not o["a"] else o.get("palette")
            self.blit(image(o["img"]), o["page"], sx(o["x"]), sx(o["y"]), pal, o["b"] & 0xff, False)
        elif k == "bitmap_masked":
            pal = None if not o["a"] else o.get("palette")
            self.blit(image(o["img"]), o["page"], sx(o["x"]), sx(o["y"]), pal, None, True)
        elif k == "text":
            self.text(o)


def sx(v):
    return v - (1 << 32) if v & 0x80000000 else v


def render(doc):
    """Frames [(tick, dots 32x128, panel shown)] and the lift's events, from one deff_lift document."""
    scr = Screen()
    frames = []
    panel_pages = set()
    table = ROM[DISSOLVE_TABLE:DISSOLVE_TABLE + 80]
    for o in doc["ops"]:
        k = o["op"]
        if k == "panel":
            panel_pages.add(o["page"])
        elif k == "show":
            frames.append((o["t"], scr.compose(o["fg"], o["bg"]), o["fg"] in panel_pages or o["bg"] in panel_pages))
            scr.shown = (o["fg"], o["bg"])
        elif k == "dissolve":
            frames.extend(dissolve(scr, o, table))
        else:
            if k in ("fill", "copy") and o.get("page", o.get("dst")) in panel_pages:
                panel_pages.discard(o.get("page", o.get("dst")))
            scr.apply(o)
    return frames


def dissolve(scr, o, table):
    """0x01034758: the work pair (fg, bg) is the last one allocated before the call (o['work'])."""
    out = []
    wf, wb = o["work"]
    sf, sb = scr.shown
    t = o["t"]
    step_ticks = max(1, o["ticks"])
    for step in range(7):
        nf, nb = np.zeros((32, 128), np.uint8), np.zeros((32, 128), np.uint8)
        col, row = 0, step
        fw, bw, fs, bs = scr.page(wf), scr.page(wb), scr.page(sf), scr.page(sb)
        for y in range(32):
            for x in range(128):
                if table[col + row * 8] == 0:
                    nf[y, x], nb[y, x] = fs[y, x], bs[y, x]
                else:
                    nf[y, x], nb[y, x] = fw[y, x], bw[y, x]
                col += 1
                if col > 7:
                    col = 0
                    row = row + 1 if row < 9 else 0
        nf[:, 0:41] = 0
        mask = nf >> 4
        out.append((t + step * step_ticks, ((nb & mask) | (nf & ~mask & 0xff)) & 0xf, True))
    f, b = scr.page(wf), scr.page(wb)
    mask = f >> 4
    out.append((t + 7 * step_ticks, ((b & mask) | (f & ~mask & 0xff)) & 0xf, True))
    scr.shown = (wf, wb)
    return out
