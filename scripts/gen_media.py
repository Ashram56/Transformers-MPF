#!/usr/bin/env python3
"""Build the Godot (GMC) media of the game from the ROM extraction's package (rom/mpf_package).

Generated (all git-ignored, rebuilt by scripts/setup.py):
- game/sounds/<track>/snd_XXXX.wav   every ROM sample (GMC finds sounds by file name). Music with an intro and a
                                     looped body (sounds.yaml loop_start_at) gets a RIFF "smpl" loop from that
                                     point to the end, which Godot's WAV importer reads (loop mode "Detect From
                                     WAV"): the intro plays once, the body loops, as the ROM's stream script does.
- game/fonts/                        the ROM fonts (scripts/gen_fonts.py)
- game/tf/media_data.json            sound pools (one per ROM sound call) and display effect facts for
                                     tf/media_bridge.py

Display effects: none yet. The package has the ROM's images and animations but not which deff plays which
frames, at what timing, with what text (the ROM extraction's display captures, pending). Until then
tf/media_bridge.py draws the score display (deff 19) and attract (deff 1) from ROM fonts (tf/score_screen.py)
and the other deffs show nothing (the previous screen stays, as on the ROM between effects).

Usage: .venv/bin/python scripts/gen_media.py [--only-data]
"""
import glob
import json
import os
import shutil
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "rom", "mpf_package")
GAME = os.path.join(ROOT, "game")
sys.path.insert(0, os.path.dirname(__file__))


def load_yaml(path):
    from ruamel.yaml import YAML
    with open(path, encoding="utf-8") as f:
        return YAML(typ="safe").load(f)


def seconds(text):
    text = str(text).strip()
    if text.endswith("ms"):
        return float(text[:-2]) / 1000
    return float(text.rstrip("s"))


def with_loop(data, loop_start_s):
    """The WAV bytes with a "smpl" chunk looping from loop_start_s to the last sample frame."""
    rate = struct.unpack_from("<I", data, 24)[0]
    block = struct.unpack_from("<H", data, 32)[0]
    pos, frames = 12, 0
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
        if cid == b"data":
            frames = size // block
        pos += 8 + size + (size & 1)
    start = min(int(round(loop_start_s * rate)), max(frames - 1, 0))
    smpl = struct.pack("<9I", 0, 0, 1000000000 // rate, 60, 0, 0, 0, 1, 0) + \
        struct.pack("<6I", 0, 0, start, frames - 1, 0, 0)
    body = data[12:] + b"smpl" + struct.pack("<I", len(smpl)) + smpl
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def build_sounds(only_data):
    cfg = load_yaml(os.path.join(PKG, "config", "sounds.yaml"))
    sounds = cfg["sounds"]
    if not only_data:
        for name, s in sounds.items():
            track = s.get("track", "sfx")
            src = glob.glob(os.path.join(PKG, "media", "sounds", "*", s["file"]))
            if not src:
                continue
            dst_dir = os.path.join(GAME, "sounds", track)
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, name + ".wav")
            if s.get("loop_start_at") is not None:
                with open(src[0], "rb") as f:
                    data = with_loop(f.read(), seconds(s["loop_start_at"]))
                if not os.path.exists(dst) or open(dst, "rb").read() != data:
                    with open(dst, "wb") as f:
                        f.write(data)
            elif not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src[0]):
                shutil.copyfile(src[0], dst)
    pools = {}
    for name, p in (cfg.get("sound_pools") or {}).items():
        members = p["sounds"]
        if isinstance(members, str):
            members = [m.strip() for m in members.split(",")]
        members = [m.split("|")[0].strip() for m in members if m.split("|")[0].strip() in sounds]
        if not members:
            continue
        call = int(name.split("_")[1], 16)
        pools[call] = {"type": p.get("type", "random"), "samples": members,
                       "track": sounds[members[0]].get("track", "sfx")}
    return pools


def build_deffs(only_data):
    """Display effects with frames: none until the ROM extraction's captures (see the module docstring)."""
    return {}


def main():
    import gen_fonts
    import toolchain
    only_data = "--only-data" in sys.argv
    if not only_data or not os.path.exists(os.path.join(GAME, "fonts", "fonts.json")):
        gen_fonts.build()
    data = {"pools": build_sounds(only_data), "deffs": build_deffs(only_data)}
    with open(os.path.join(GAME, "tf", "media_data.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=0, sort_keys=True)
    if not only_data:
        os.makedirs(os.path.join(GAME, "media"), exist_ok=True)
        toolchain.write_media_stamp()
    print("media: {} sound pools, {} display effects".format(len(data["pools"]), len(data["deffs"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
