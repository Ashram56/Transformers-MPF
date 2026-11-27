"""Voice needs of every sample (rom/rom_data/sound/sample_voices.csv): byte 1 of the sample's stream script is the
mask of the voices it may use, byte 2 the number of voices it takes. snd_start_sample [0x00024ae4] reads both
(bVar2, bVar10) after checking byte 0 == 5. Usage: TF_ROM=tf_180.bin python rom/tools/sample_voices.py"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sound  # noqa: E402
from rom import ROM, banked  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rom_data", "sound", "sample_voices.csv")


def main():
    ents = sound.directory()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample", "script_kind", "voice_mask", "voices"])
        for i, e in enumerate(ents):
            o = banked(e[0])
            w.writerow(["0x%03x" % i, ROM[o], "0x%02x" % ROM[o + 1], ROM[o + 2]])
    print("wrote", OUT, len(ents))


if __name__ == "__main__":
    main()
