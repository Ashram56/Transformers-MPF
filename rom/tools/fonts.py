"""Font table -> fonts.json. Usage: python3 fonts.py OUT.json
Source: OS resource block (file 0x30e7c count = 27, 0x30e80 table = file 0x123478), 20-byte records, same layout as
Tron (AGENTS.md section 7): +0 char-range list, +4 glyph table (8 B per char: banked image ptr, s16 x off, s16 y off),
+8 u16 height, +0xa s16 spacing, +0xc u32 masked, +0x10 u8 flash bank of the lists."""
import json, os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
from rom import *
from images import TABLE as IMG_TAB, NMAX as NIMG
OUT = sys.argv[1]
img_index = {fu32(IMG_TAB + 4 * i): i for i in range(NIMG)}
def img_hdr(p):
    o = banked(p); rid, grp, fl, w, h, fm = struct.unpack_from('<HHIhhB', ROM, o)
    return dict(rid=rid, w=w, h=h, format=fm)
NF, FT = fu32(0x30e7c), fu32(0x30e80)
fonts = []
for f in range(NF):
    o0 = FT + f * 0x14
    rng_p, gl_p, height, spacing, masked, bank = struct.unpack_from('<IIHhIB', ROM, o0)
    base = bank * 0x800000; ranges = []; o = base + rng_p
    while ROM[o]: ranges.append((ROM[o], ROM[o + 1])); o += 2
    glyphs, k = {}, 0
    for lo, hi in ranges:
        for c in range(lo, hi + 1):
            g = base + gl_p + 8 * k; ip = fu32(g); xo, yo = struct.unpack_from('<hh', ROM, g + 4); hd = img_hdr(ip)
            glyphs[chr(c)] = dict(code=c, image=img_index.get(ip), image_ptr='0x%08x' % ip, rid=hd['rid'], w=hd['w'], h=hd['h'],
                                  x_offset=xo, y_offset=yo, advance=hd['w'] + xo + spacing)
            k += 1
    imgs = [g['image'] for g in glyphs.values() if g['image'] is not None]
    fonts.append(dict(font=f, record_file_offset='0x%x' % o0, height=height, spacing=spacing, masked=bool(masked), bank=bank,
                      ranges=[[chr(lo), chr(hi)] for lo, hi in ranges], range_list_file_offset='0x%x' % (base + rng_p),
                      glyph_table_file_offset='0x%x' % (base + gl_p), image_first=min(imgs) if imgs else None,
                      image_last=max(imgs) if imgs else None, chars=''.join(glyphs), glyphs=glyphs))
doc = {'source': 'ROM tf_180 (Transformers Pro 1.80): font table file 0x%x, %d fonts (OS resource block 0x30e7c)' % (FT, NF), 'tag': 'code',
       'placement': {'glyph_blit': 'x_draw = pen_x + x_offset; y_draw = y - h + y_offset + 1 (Tron text_draw_str; same OS generation, '
                                   'tf_180 renderer is 0x21878, not re-derived)',
                     'pen_advance': 'pen_x += w + x_offset + spacing',
                     'flags': {'2': 'centre', '4': 'right-align'},
                     'image': 'image number = img_NNNNN.png in mpf_package/media/rom_images_all.zip'},
       'fonts': fonts}
json.dump(doc, open(OUT, 'w'), indent=1)
for f in fonts: print(f['font'], f['height'], f['spacing'], f['masked'], f['image_first'], f['image_last'], f['chars'][:60])
