#!/usr/bin/env python3
"""Interim rom_data/fonts.json for tf_180, until the ROM extraction delivers its own: the ROM's font table read
the way the Tron extraction reads trn_174h's (Tron asset repo rom_data/tools/fonts.py, same OS code).

Needs the ROM: TF_ROM=<path to tf_180.bin> python scripts/interim_fonts.py. Writes game/config/interim/fonts.json
in the Tron format (scripts/gen_fonts.py reads rom/rom_data/fonts.json first, else this one).

Source [code]: the OS resource block (rom/tools/images.py: file 0x30e78) gives 27 fonts at file 0x123478, 20-byte
records: +0 u32 char-range list, +4 u32 glyph table (8 B per char: u32 banked image pointer, s16 x offset,
s16 y offset), +8 u16 height, +0xa s16 spacing, +0xc u32 masked, +0x10 u8 flash bank of both lists.
The record layout is Tron's (inferred the same: the OS code of both ROMs is the same SAM OS).
"""
import json
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "rom", "tools"))
from rom import ROM, banked  # noqa: E402

FONT_TABLE = 0x123478
FONT_COUNT = 27
IMAGE_TABLE = 0x123694
IMAGE_COUNT = 10212
OUT = os.path.join(ROOT, "game", "config", "interim", "fonts.json")


def u32(o): return struct.unpack_from("<I", ROM, o)[0]
def s16(o): return struct.unpack_from("<h", ROM, o)[0]


def main():
    img_index = {u32(IMAGE_TABLE + 4 * i): i for i in range(IMAGE_COUNT)}
    fonts = []
    for f in range(FONT_COUNT):
        a = FONT_TABLE + 0x14 * f
        rng_p, gl_p = u32(a), u32(a + 4)
        height, spacing, masked, bank = struct.unpack_from("<H", ROM, a + 8)[0], s16(a + 10), u32(a + 12), ROM[a + 16]
        base = bank * 0x800000
        ranges, o = [], base + rng_p
        while ROM[o]:
            ranges.append((ROM[o], ROM[o + 1]))
            o += 2
        glyphs, k = {}, 0
        for lo, hi in ranges:
            for c in range(lo, hi + 1):
                g = base + gl_p + 8 * k
                ip, xo, yo = u32(g), s16(g + 4), s16(g + 6)
                h_o = banked(ip)
                rid, w, h = struct.unpack_from("<H", ROM, h_o)[0], s16(h_o + 8), s16(h_o + 10)
                glyphs[chr(c)] = dict(code=c, image=img_index.get(ip), image_ptr="0x%08x" % ip, rid=rid, w=w, h=h,
                                      x_offset=xo, y_offset=yo, advance=w + xo + spacing)
                k += 1
        imgs = [g["image"] for g in glyphs.values() if g["image"] is not None]
        fonts.append(dict(font=f, record_file_offset="0x%x" % a, height=height, spacing=spacing,
                          masked=bool(masked), bank=bank, ranges=[[chr(lo), chr(hi)] for lo, hi in ranges],
                          image_first=min(imgs) if imgs else None, image_last=max(imgs) if imgs else None,
                          chars="".join(glyphs), glyphs=glyphs))
    doc = {
        "source": "ROM tf_180 (Transformers Pro 1.80): font table file 0x%x, %d fonts (interim, C's reader)"
                  % (FONT_TABLE, FONT_COUNT),
        "tag": "code",
        "placement": {
            "glyph_blit": "x_draw = pen_x + x_offset; y_draw = y - h + y_offset + 1 (y = baseline row)",
            "pen_advance": "pen_x += w + x_offset + spacing",
            "flags": {"2": "centre: x -= text_width // 2", "4": "right: x = x + 1 - text_width"},
            "masked": "true: pixel 255 in the glyph image is transparent",
            "image": "index into the ROM image table = NNNN.png in rom/mpf_package/media/rom_images_all.zip",
        },
        "fonts": fonts,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
    for font in fonts:
        print(font["font"], font["height"], font["spacing"], font["masked"], font["image_first"],
              font["image_last"], font["chars"][:60])
    return 0


if __name__ == "__main__":
    sys.exit(main())
