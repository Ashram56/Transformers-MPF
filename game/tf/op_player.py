"""Live replay of a display effect's op list: the deff's draw calls run again each tick, with the game's values.

A deff in LIVE (tf/media_bridge.py) is not shown from its captured frames: its op list (the lift of its code,
rom/tools/deff_lift.py, compacted by scripts/gen_media.py into game/media/live_ops/) is replayed tick by tick on
page buffers, and every printf text takes the value the rules give for its call site (site_values, as for the
frame slides). The page transitions of the ROM (copy_rect row remaps, deff 25's page change
os_hook_call_203d0(10) [0x010357e0] [0x01035810] [0x0103582c]) then carry the live values, which a frame captured
from a code run cannot.

The primitives are those of rom/tools/deff_render.py, each from its routine in the decompile:
- page: 32 rows x 128 bytes, low nibble the shade, high nibble the mask (show mixer).
- show(fg, bg) [0x00020134]: per dot, mask = fg >> 4, dot = (bg & mask) | (fg & ~mask), low 4 bits.
- fill [0x0001fb60], rect [0x0001fdc4] (inclusive, clipped), frame [0x0001f910], copy [0x0001fbe8],
  copy_rect [0x0001fc28] (flat row copy), remap [0x01006bb8], invert [0x0002b808].
- bitmap [0x00023d28]: a = 0 copies each byte unless it equals b; a = palette: byte < 16 -> palette[byte], else
  0xff, copied unless equal to b. bitmap_masked [0x00023c7c]: every byte written (through the palette if a).
- text_draw_str [0x00021878]: flags & 2 centres, flags & 4 right-aligns on x (text_width [0x00021378]: extent of
  the glyph boxes); each glyph at (x + xoff, y - h + yoff + 1), masked when the font's +0xc word is 0, else
  bitmap(palette, b = 0xff); the pen moves w + spacing + xoff.
- dissolve [0x01034758]: 7 steps through the 80-byte table 0x040c76e8, columns 0-40 cleared, then the work pair.

Images: rom/mpf_package/media/rom_images_all.zip (grey = level, alpha 0 = byte 0xff), and the exact bytes of the
images with other mask nibbles from rom_images_mask.zip (rom/tools/export_op_data.py). Fonts: game/fonts/
fonts.json (scripts/gen_fonts.py: each glyph is a ROM image, "below" = the ROM's y offset).
"""
import gzip
import io
import json
import os
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
IMAGES_ZIP = os.path.join(ROOT, "rom", "mpf_package", "media", "rom_images_all.zip")
MASKS_ZIP = os.path.join(ROOT, "rom", "mpf_package", "media", "rom_images_mask.zip")
FONTS_JSON = os.path.join(HERE, "..", "fonts", "fonts.json")
OPS_DIR = os.path.join(HERE, "..", "media", "live_ops")
W, H = 128, 32
PANEL_FIRST, PANEL_END = 0x0102f200, 0x0102f800     # the status panel's printf sites [0x0102f200] (0x0102f2ec-0x0102f6cc)

# show(fg, bg) [0x00020134] for every (fg, bg) byte pair: index fg << 8 | bg
_MIX = bytes(((b & (f >> 4)) | (f & ~(f >> 4) & 0xff)) & 0xf for f in range(256) for b in range(256))

_zips = {}
_docs = {}                  # op list name -> its document (OpPlayer.load)
_images = {}
_blits = {}
_fonts = None


def _zip(path):
    if path not in _zips:
        _zips[path] = zipfile.ZipFile(path) if os.path.exists(path) else None
    return _zips[path]


def image(n):
    """(w, h, bytes) of ROM image n, as the ROM's decoder gives it."""
    if n in _images:
        return _images[n]
    out = None
    masks = _zip(MASKS_ZIP)
    name = "img_%05d" % n
    if masks is not None and name + ".bin" in masks.NameToInfo:
        raw = masks.read(name + ".bin")
        w, h = struct.unpack_from("<HH", raw)
        out = (w, h, raw[4:4 + w * h])
    else:
        z = _zip(IMAGES_ZIP)
        if z is not None and name + ".png" in z.NameToInfo:
            from PIL import Image  # noqa: PLC0415
            im = Image.open(io.BytesIO(z.read(name + ".png"))).convert("RGBA")
            w, h = im.size
            px = im.tobytes()
            out = (w, h, bytes(0xff if px[i + 3] == 0 else px[i] // 17 for i in range(0, len(px), 4)))
    _images[n] = out
    return out


def fonts():
    global _fonts
    if _fonts is None:
        _fonts = {}
        if os.path.exists(FONTS_JSON):
            with open(FONTS_JSON, encoding="utf-8") as f:
                _fonts = {int(font["id"]): font for font in json.load(f)["fonts"]}
    return _fonts


def text_width(s, font):
    """text_width [0x00021378]: the extent of the glyph boxes, x offsets included."""
    pen = lo = hi = 0
    for ch in s:
        g = font["glyphs"].get(ch)
        if g is None:
            continue
        pen += g["xoff"]
        lo, hi = min(lo, pen), max(hi, pen)
        pen += g["w"]
        lo, hi = min(lo, pen), max(hi, pen)
        pen += font["spacing"]
    return hi - lo


def _segments(n, pal, skip, masked):
    """The runs of dots an image writes: [(row, col, bytes)] (bitmap skips the bytes equal to b)."""
    key = (n, pal, skip, masked)
    if key in _blits:
        return _blits[key]
    img = image(n)
    out = []
    if img is not None:
        w, h, data = img
        for y in range(h):
            row = data[y * w:(y + 1) * w]
            if pal is not None:
                row = bytes(pal[v] if v < 16 else 0xff for v in row)
            if masked:
                out.append((y, 0, row))
                continue
            x = 0
            while x < w:
                if row[x] == skip:
                    x += 1
                    continue
                x0 = x
                while x < w and row[x] != skip:
                    x += 1
                out.append((y, x0, row[x0:x]))
    _blits[key] = out
    return out


def _sx(v):
    return v - (1 << 32) if v & 0x80000000 else v


class OpPlayer:
    """One run of a deff's op list. advance(tick, site_values) applies the ops due by `tick` and returns the
    screen shown then (4096 dot levels 0-15, row by row), or None when no new frame was shown."""

    def __init__(self, ops, name=None, loop=None):
        """loop: [start, period] in ticks for a deff whose code never ends (scripts/gen_media.py loop_ticks): past
        the recorded run, the ticks from start on repeat with that period, replayed from a copy of the state the
        run had at start."""
        self.name = name
        self.ops = ops
        self.loop = loop
        self.saved = None           # (op index, pages, shown) at the loop's start tick
        self.offset = 0             # ticks taken off the caller's tick by the cycles already replayed
        self.i = 0
        self.pages = {}
        self.shown = (0, 0)
        self.pending = []           # dissolve frames still to show: [(tick, dots)]
        self.frame = None

    @classmethod
    def load(cls, name):
        """The player of game/media/live_ops/<name>.json.gz (scripts/gen_media.py), None when not generated; each
        op list is read once."""
        if name not in _docs:
            path = os.path.join(OPS_DIR, name + ".json.gz")
            if not os.path.exists(path):
                return None
            with gzip.open(path, "rt", encoding="utf-8") as f:
                _docs[name] = json.load(f)
        doc = _docs[name]
        return cls(doc["ops"], name, doc.get("loop"))

    def page(self, n):
        p = self.pages.get(n)
        if p is None:
            p = self.pages[n] = bytearray(W * H)
        return p

    def advance(self, tick, site_values=None):
        """Run the ops up to `tick` (ticks since the deff's start); a looping deff's ticks past its run go round its
        cycle (loop)."""
        tick -= self.offset
        if self.loop and self.ops:
            start, period = self.loop
            end = self.ops[-1]["t"]
            if self.saved is None and tick >= start:
                self._run(start - 1, site_values)
                self.saved = (self.i, {k: bytearray(v) for k, v in self.pages.items()}, self.shown, self.frame,
                              list(self.pending))
            while tick > end and self.saved is not None:
                tick -= period
                self.offset += period
                i, pages, self.shown, self.frame, pending = self.saved
                self.i, self.pages, self.pending = i, {k: bytearray(v) for k, v in pages.items()}, list(pending)
        return self._run(tick, site_values)

    def _run(self, tick, site_values):
        new = None
        while self.i < len(self.ops) and self.ops[self.i]["t"] <= tick:
            o = self.ops[self.i]
            self.i += 1
            k = o["op"]
            if k == "show":
                new = self.compose(o["fg"], o["bg"])
                self.shown = (o["fg"], o["bg"])
                self.pending = []
            elif k == "dissolve":
                self.pending = self.dissolve(o)
            else:
                self.apply(o, site_values or {})
        while self.pending and self.pending[0][0] <= tick:
            new = self.pending.pop(0)[1]
        if new is not None:
            self.frame = new
        return new

    def printf_keys(self):
        """The deff's printf texts ("site|format"), in the order its code first draws them, the status panel's
        [0x0102f200] left out: where the rules pass a deff's values in order and the frames held no slot."""
        out = []
        for o in self.ops:
            if o["op"] == "text" and o.get("site") and not PANEL_FIRST <= int(o["site"], 16) < PANEL_END:
                key = o["site"] + "|" + o["format"]
                if key not in out:
                    out.append(key)
        return out

    def done(self):
        return self.i >= len(self.ops) and not self.pending

    # -- primitives ---------------------------------------------------------------------------------------
    def compose(self, fg, bg):
        f, b = self.page(fg), self.page(bg)
        return bytes(_MIX[(x << 8) | y] for x, y in zip(f, b))

    def blit(self, n, page, x, y, pal, skip, masked):
        dst = self.page(page)
        for yy, xx, run in _segments(n, pal, skip, masked):
            row = y + yy
            if row < 0 or row >= H:
                continue
            a, b = x + xx, x + xx + len(run)
            lo, hi = max(a, 0), min(b, W)
            if lo < hi:
                dst[row * W + lo:row * W + hi] = run[lo - a:hi - a]

    def text(self, o, site_values):
        from tf.media_bridge import format_rom_text  # noqa: PLC0415
        font = fonts().get(o["font"])
        if font is None:
            return
        s = o["text"]
        site = o.get("site")
        if site is not None:
            # by call site and format ("site|format": one helper prints several formats, deff 52), else by site;
            # a string is the text already formatted, None keeps the code run's text
            v = site_values.get(site + "|" + o["format"], site_values.get(site))
            if isinstance(v, str):
                s = v
            elif v is not None:
                s = format_rom_text(o["format"], [v, v])
            if v is not None and o.get("font_list"):
                # text_printf_msg_fit_page: the first font of the list in which the text fits o["fit"] dots
                for f in o["font_list"]:
                    if f in fonts() and text_width(s, fonts()[f]) <= o["fit"]:
                        break
                font = fonts().get(f, font)
        x, y, flags = o["x"], o["y"], o["flags"]
        if flags & 2:
            x -= text_width(s, font) >> 1
        elif flags & 4:
            x = x + 1 - text_width(s, font)
        pal = o.get("palette")
        pal = tuple(pal) if pal else None
        for ch in s:
            g = font["glyphs"].get(ch)
            if g is None:
                continue
            img = image(g["image"])
            h = img[1] if img else g["h"]
            if font["masked"] == 0:
                self.blit(g["image"], o["page"], x + g["xoff"], y - h + g["below"] + 1, pal, None, True)
            else:
                self.blit(g["image"], o["page"], x + g["xoff"], y - h + g["below"] + 1, pal, 0xff, False)
            x += g["w"] + font["spacing"] + g["xoff"]

    def apply(self, o, site_values):
        k = o["op"]
        if k == "fill":
            self.page(o["page"])[:] = bytes([o["value"] & 0xff]) * (W * H)
        elif k == "rect":
            x0, y0, x1, y1 = o["x0"], o["y0"], o["x1"], o["y1"]
            if x0 < 0 or x1 < 0 or x0 > 127 or x1 < x0 or y0 < 0 or y1 > 31 or y1 < y0:
                return
            p, v = self.page(o["page"]), bytes([o["value"] & 0xff]) * (min(x1, 127) + 1 - x0)
            for y in range(y0, y1 + 1):
                p[y * W + x0:y * W + x0 + len(v)] = v
        elif k == "frame":
            p, v = self.page(o["page"]), o["value"] & 0xff
            x0, y0, x1, y1 = o["x0"], o["y0"], o["x1"], o["y1"]
            for x in range(max(x0, 0), min(x1, 127) + 1):
                for y in (y0, y1):
                    if 0 <= y < H:
                        p[y * W + x] = v
            for y in range(max(y0, 0), min(y1, 31) + 1):
                for x in (x0, x1):
                    if 0 <= x < W:
                        p[y * W + x] = v
        elif k == "copy":
            self.page(o["dst"])[:] = self.page(o["src"])
        elif k == "copy_rect":
            src, dst = self.page(o["src"]), self.page(o["dst"])
            so, do_ = o["sy"] * W + o["sx"], o["dy"] * W + o["dx"]
            for r in range(o["h"]):
                a, b = so + r * W, do_ + r * W
                n = min(o["w"], W * H - a, W * H - b)
                if n > 0 and a >= 0 and b >= 0:
                    dst[b:b + n] = src[a:a + n]
        elif k == "invert":
            p = self.page(o["page"])
            for y in range(o["y"], min(o["y"] + o["h"], H)):
                for x in range(o["x"], min(o["x"] + o["w"], W)):
                    p[y * W + x] = 0xf if p[y * W + x] == 0 else 0
        elif k == "remap":
            p, m = self.page(o["page"]), o["map"]
            for y in range(o["y0"], o["y1"] + 1):
                for x in range(o["x0"], o["x1"] + 1):
                    p[y * W + x] = m[p[y * W + x] & 0xf] & 0xff
        elif k == "bitmap":
            pal = tuple(o["palette"]) if o["a"] and o.get("palette") else None
            self.blit(o["img"], o["page"], _sx(o["x"]), _sx(o["y"]), pal, o["b"] & 0xff, False)
        elif k == "bitmap_masked":
            pal = tuple(o["palette"]) if o["a"] and o.get("palette") else None
            self.blit(o["img"], o["page"], _sx(o["x"]), _sx(o["y"]), pal, None, True)
        elif k == "text":
            self.text(o, site_values)

    def dissolve(self, o):
        """[0x01034758]: the work pair (fg, bg) is the last one allocated before the call (o['work'])."""
        table = o.get("table")          # 0x040c76e8, 80 bytes (8 per row, 10 rows; 0 keeps the dot shown before)
        wf, wb = o["work"]
        sf, sb = self.shown
        fw, bw, fs, bs = self.page(wf), self.page(wb), self.page(sf), self.page(sb)
        step_ticks = max(1, o["ticks"])
        out = []
        for step in range(7 if table else 0):
            nf, nb = bytearray(W * H), bytearray(W * H)
            col, row = 0, step
            for i in range(W * H):
                if table[col + row * 8] == 0:
                    nf[i], nb[i] = fs[i], bs[i]
                else:
                    nf[i], nb[i] = fw[i], bw[i]
                col += 1
                if col > 7:
                    col = 0
                    row = row + 1 if row < 9 else 0
            for y in range(H):
                nf[y * W:y * W + 41] = bytes(41)
            out.append((o["t"] + step * step_ticks, bytes(_MIX[(x << 8) | y] for x, y in zip(nf, nb))))
        out.append((o["t"] + 7 * step_ticks, self.compose(wf, wb)))
        self.shown = (wf, wb)
        return out


def dots_hex(dots, clear_cols=0):
    """The dots as Godot's L8 image data, hex: level * 17 per dot; columns below clear_cols black (the status
    panel drawn over them live, tf/score_screen.py)."""
    out = bytearray(d * 17 for d in dots)
    if clear_cols:
        for y in range(H):
            out[y * W:y * W + clear_cols] = bytes(clear_cols)
    return out.hex()
