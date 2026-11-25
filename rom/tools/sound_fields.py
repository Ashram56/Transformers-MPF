"""Decode the sound call fields +0x0c..+0x13 (rom_data/sound/sound_calls.csv) from the routines that read them.

A sound call is a 0x14-byte record at 0x040dee08 + call * 0x14 (snd_resolve_call [0x00025044]). The fields after
the sample list (+0x08), read by snd_resolve_call, snd_start_sample [0x00024ae4] and FUN_00025b3c [0x00025b3c]:
  +0x0c s16  cue: when not 0 the sample starts at cue n of the sample's header (header word +3 + n * 4,
             snd_start_sample, channel field +0x37c14); 0 = from the start. 0 in every call of tf_180.
  +0x0e u16  no-repeat memory: the last n samples of the call are kept in the ring at +0x00 (index at +0x04);
             a random pick skips a sample still in it (FUN_00025b3c), the start writes the ring
  +0x10 u8   priority: a channel playing a lower priority is taken over (or an equal one whose flag bit 0 is set)
  +0x11 u8   the channel's flags (0x37c2b): bit 0 = can be taken over by a call of the same priority
  +0x12 u8   speech: the started sample goes into the 9-entry ring 0x00038354 (index 0x00032490, 1..9); a random
             pick (snd_resolve_call) takes the first sample not in the call's no-repeat memory and not in that
             ring, else the last one seen that is not the latest entry of the ring
  +0x13      padding (no reader)
Adds the columns cue, no_repeat, priority, replace_equal, speech to sound_calls.csv from its raw fields.
Usage: sound_fields.py
"""
import csv
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rom_data", "sound", "sound_calls.csv")


def main():
    rows = list(csv.DictReader(open(P, encoding="utf-8")))
    fields = list(rows[0].keys())
    for k in ("cue", "no_repeat", "priority", "replace_equal", "speech"):
        if k not in fields:
            fields.append(k)
    for r in rows:
        f = int(r["flags_0x10"], 16)
        w12 = int(r["w_0x12"])
        r["cue"] = int(r["w_0x0c"])
        r["no_repeat"] = int(r["w_0x0e"])
        r["priority"] = f & 0xff
        r["replace_equal"] = (f >> 8) & 1
        r["speech"] = w12 & 0xff
    with open(P, "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "calls")


if __name__ == "__main__":
    main()
