#!/usr/bin/env python3
"""Rebuild the ROM's DMD fonts as BMFont files for Godot (1 px = 1 DMD dot).

Input: the font table as JSON, rom/rom_data/fonts.json when the ROM extraction delivers it, else the interim
game/config/interim/fonts.json (scripts/interim_fonts.py, read from tf_180's font table at file 0x123478). Each
glyph is a ROM image (rom/mpf_package/media/rom_images_all.zip, img_NNNNN.png: alpha 0 = clear, grey = level)
with the x and y offsets the ROM draws it at, so nothing is guessed from the pictures (on Tron the glyph offsets
had to be rebuilt from the captures; here they are ROM data).

Placement (text_draw_str, same SAM OS as Tron): a glyph is drawn at (pen + x_offset, y - h + y_offset + 1),
y = the baseline row; the pen moves by w + x_offset + spacing; flag 2 centres the text on x, 4 right-aligns it.

Output (git-ignored): game/fonts/rom_font_NN.fnt + .png and game/fonts/fonts.json, the metrics the slides
(tf/rom_fonts.gd) and tf/rom_draw.py read: per font id, spacing, ascent, descent and per glyph image, w, h,
xoff and below (= the ROM's y offset).
"""
import io
import json
import os
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ZIP = os.path.join(ROOT, "rom", "mpf_package", "media", "rom_images_all.zip")
SOURCES = [os.path.join(ROOT, "rom", "rom_data", "fonts.json"),
           os.path.join(ROOT, "game", "config", "interim", "fonts.json")]
OUT = os.path.join(ROOT, "game", "fonts")
TRANSPARENT = 255


def source():
    for path in SOURCES:
        if os.path.exists(path):
            return path
    raise SystemExit("fonts: no font table ({})".format(" or ".join(SOURCES)))


def load_images():
    z = zipfile.ZipFile(ZIP)
    cache = {}

    def get(i):
        if i not in cache:
            from PIL import Image
            im = Image.open(io.BytesIO(z.read("img_%05d.png" % i))).convert("RGBA")
            w, h = im.size
            px = im.load()
            cache[i] = [[TRANSPARENT if px[x, y][3] == 0 else round(px[x, y][0] / 17) for x in range(w)]
                        for y in range(h)]
        return cache[i]
    return get


def metrics(rom_fonts):
    fonts = []
    for f in rom_fonts:
        glyphs = {c: {"image": g["image"], "w": g["w"], "h": g["h"], "xoff": g["x_offset"], "below": g["y_offset"]}
                  for c, g in f["glyphs"].items() if g["image"] is not None}
        fonts.append({"id": f["font"], "height": f["height"], "spacing": f["spacing"], "masked": f["masked"],
                      "ascent": max(g["h"] - g["below"] for g in glyphs.values()),
                      "descent": max(0, max(g["below"] for g in glyphs.values())),
                      "glyphs": glyphs})
    return fonts


def text_width(font, text):
    gs = [font["glyphs"][c] for c in text if c in font["glyphs"]]
    return sum(g["w"] + g["xoff"] + font["spacing"] for g in gs) - font["spacing"] if gs else 0


def render(get, font, text, x, y, flags, canvas):
    """Draws text like text_draw_str into canvas (rows of levels, 128 x 32); y is the baseline row."""
    if flags & 2:
        x -= text_width(font, text) // 2
    elif flags & 4:
        x = x + 1 - text_width(font, text)
    for c in text:
        g = font["glyphs"].get(c)
        if g is None:                                   # characters the font lacks are skipped
            continue
        top, left = y + g["below"] - g["h"] + 1, x + g["xoff"]
        for gy, row in enumerate(get(g["image"])):
            for gx, v in enumerate(row):
                if (v != TRANSPARENT or not font["masked"]) and 0 <= left + gx < 128 and 0 <= top + gy < 32:
                    canvas[top + gy][left + gx] = 0 if v == TRANSPARENT else v
        x += g["w"] + g["xoff"] + font["spacing"]
    return canvas


def write_bmfont(font, get, out_dir):
    """rom_font_NN.fnt (BMFont text format) + rom_font_NN.png atlas, levels as grey. A masked font's clear
    pixels stay clear; an unmasked font draws its black cell (alpha 1, black) as the ROM's opaque blit does."""
    from PIL import Image
    name = "rom_font_%02d" % font["id"]
    glyphs = sorted(font["glyphs"].items(), key=lambda kv: ord(kv[0]))
    width = sum(g["w"] + 1 for _, g in glyphs) + 1
    height = max(g["h"] for _, g in glyphs) + 2
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = atlas.load()
    lines, x, asc = [], 1, font["ascent"]
    for c, g in glyphs:
        for gy, row in enumerate(get(g["image"])):
            for gx, v in enumerate(row):
                if v != TRANSPARENT:
                    px[x + gx, 1 + gy] = (v * 17, v * 17, v * 17, 255)
                elif not font["masked"]:
                    px[x + gx, 1 + gy] = (0, 0, 0, 255)
        lines.append("char id=%d x=%d y=1 width=%d height=%d xoffset=%d yoffset=%d xadvance=%d page=0 chnl=15"
                     % (ord(c), x, g["w"], g["h"], g["xoff"], asc - g["h"] + g["below"],
                        g["w"] + g["xoff"] + font["spacing"]))
        x += g["w"] + 1
    atlas.save(os.path.join(out_dir, name + ".png"))
    size = asc + font["descent"]
    head = ['info face="%s" size=%d bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 '
            'padding=0,0,0,0 spacing=0,0 outline=0' % (name, size),
            "common lineHeight=%d base=%d scaleW=%d scaleH=%d pages=1 packed=0 alphaChnl=0 redChnl=0 "
            "greenChnl=0 blueChnl=0" % (size, asc, width, height),
            'page id=0 file="%s.png"' % name, "chars count=%d" % len(glyphs)]
    with open(os.path.join(out_dir, name + ".fnt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + lines) + "\n")
    return name


def build(out_dir=OUT):
    path = source()
    with open(path, encoding="utf-8") as f:
        fonts = metrics(json.load(f)["fonts"])
    get = load_images()
    os.makedirs(out_dir, exist_ok=True)
    for font in fonts:
        write_bmfont(font, get, out_dir)
    with open(os.path.join(out_dir, "fonts.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"source": os.path.relpath(path, ROOT).replace(os.sep, "/"), "fonts": fonts}, f, indent=0,
                  sort_keys=True)
    return fonts


def main():
    fonts = build()
    print("fonts: %d ROM fonts in game/fonts (%s)" % (len(fonts), ", ".join(
        "%d:%dpx" % (f["id"], f["height"]) for f in fonts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
