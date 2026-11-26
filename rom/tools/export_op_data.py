"""Write what the game's op player (game/tf/op_player.py) needs from the ROM beyond the PNGs: the raw bytes of the
images whose PNG loses information, and the dissolve tables.

The PNG export (export_images.py) keeps the shade (low nibble) and transparency (byte 0xff) of each dot, which is
what a bitmap op needs for most images. 264 images also carry other mask nibbles (bytes 0x10-0xfe: the high
nibble is the dot's mask in the show mixer, deff_render.py compose [0x00020134]); the PNG turns them into level
15. For those, rom/mpf_package/media/rom_images_mask.zip holds img_NNNNN.bin = u16 w, u16 h, then w*h bytes as
the ROM's image decoder gives them (images.py), so the game's op player (game/tf/op_player.py) draws them exactly.

The dissolve [0x01034758] steps through an 80-byte table (8 per row, 10 rows; 0 keeps the dot shown before):
rom/rom_data/dmd/dissolve_tables.json maps each table address the op lists name ("table" of a dissolve op) to its
80 bytes.

Usage: TF_ROM=tf_180.bin python3 rom/tools/export_op_data.py
"""
import os
import struct
import sys
import zipfile

sys.setrecursionlimit(20000)
sys.path.insert(0, os.path.dirname(__file__))
import glob  # noqa: E402
import json  # noqa: E402

import deff_render  # noqa: E402
import images  # noqa: E402
from rom import ROM, foff  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "mpf_package", "media", "rom_images_mask.zip")
OPS = os.path.join(HERE, "..", "rom_data", "dmd", "deff_ops")
TABLES = os.path.join(HERE, "..", "rom_data", "dmd", "dissolve_tables.json")


def main():
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for i in images.valid_ids():
            try:
                a = deff_render.image(i)
            except Exception:   # noqa: BLE001  (an image the decoder does not take is not in the PNG zip either)
                continue
            if ((a >= 16) & (a < 255)).any():
                h, w = a.shape
                info = zipfile.ZipInfo("img_%05d.bin" % i, date_time=(2026, 1, 1, 0, 0, 0))
                z.writestr(info, struct.pack("<HH", w, h) + a.tobytes(), zipfile.ZIP_DEFLATED)
                n += 1
    print(n, "images with mask nibbles ->", OUT)
    tables = set()
    for path in glob.glob(os.path.join(OPS, "*.json")):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if '"dissolve"' in text:
            tables |= {o["table"] for o in json.loads(text).get("ops", []) if o["op"] == "dissolve"}
    out = {t: list(ROM[foff(int(t, 16)):foff(int(t, 16)) + 80]) for t in sorted(tables)}
    with open(TABLES, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f)
        f.write("\n")
    print(len(out), "dissolve tables ->", TABLES)


if __name__ == "__main__":
    main()
