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
- game/media/dmd/deff_NNN/fNNN.png   the distinct frames of each captured display effect
- game/slides/deffs/deff_NNN.tscn    one GMC slide per display effect (build_deffs), plus deff_NNN_side1.tscn for
                                     the effects that draw the player's side (SIDE_VARIANTS: the capture is the
                                     Decepticon side, the Autobot one is made from it with the ROM's own image or
                                     message)

The score display (deff 19) is drawn live from its draw calls (tf/score_screen.py).

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


DMD_COLOR = "Color(1, 0.45, 0.05, 1)"
DEFFS = os.path.join(PKG, "media", "dmd", "deffs")
PANEL_LR = "216cc"          # return address of the status panel's score draw in older captures' text records
PANEL_CALLS = ("102f2ec", "102f36c")    # call sites of the status panel's two score rows (text records)
PANEL_WIDTH = 41            # columns 0-40: the panel and its separator


def deff_rows():
    import csv
    with open(os.path.join(PKG, "event_map.csv"), encoding="utf-8") as f:
        return {int(r["deff"]): r for r in csv.DictReader(f)}


def capture_frames(folder, timing):
    """[(RGBA image, ms)] of the capture: grey levels (level x 17) as white with the level in every channel,
    so the slide's DMD tint gives the colour."""
    from PIL import Image
    out = []
    for f in timing.get("frames") or []:
        img = Image.open(os.path.join(folder, "frames", "%04d.png" % f["i"])).convert("L")
        out.append((Image.merge("RGBA", (img, img, img, Image.new("L", img.size, 255))), max(1, int(f["dur_ms"]))))
    return out


def panel_level(timing, frames):
    """The palette level the deff draws the status panel at (None: no panel). The capture's panel shows one
    player's score: its brightest dot in columns 0-38 is the level (deff 38 draws it dim)."""
    texts = [t for p in timing.get("pages") or [] for t in p["texts"]]
    if not any((str(t.get("lr")) == PANEL_LR or t.get("call_site") in PANEL_CALLS) and t["x"] == 38
               for t in texts):
        return None
    top = max((img.crop((0, 0, PANEL_WIDTH - 2, 32)).getextrema()[0][1] for img, _ in frames), default=255)
    return max(1, round(top / 17)) if top else 15


def fit_formats():
    """{(deff, x, y): (format, [font ids])} of the ROM's fit-font printf texts (text_printf_msg_fit_page: the first
    font of the list in which the text fits the width), from rom_data/dmd/deff_text_formats.csv."""
    import csv
    out = {}
    path = os.path.join(ROOT, "rom", "rom_data", "dmd", "deff_text_formats.csv")
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if "fit" not in r["helper"] or "%" not in r["text"] or not r["font_list"]:
                continue
            try:
                key = (int(r["deff"]), int(r["x"], 0), int(r["y"], 0))
            except ValueError:
                continue
            out[key] = (r["text"], [int(n) for n in r["font_list"].split()])
    return out


def page_texts(deff_id, texts, fits):
    """A page's text records, a fit-font text as one record: the drawn one (its font the list's pick) with the
    format ("source"), the font list ("fl") and the width it had to fit ("w") of the fit call before it."""
    out, skip = [], False
    for i, t in enumerate(texts):
        if skip:
            skip = False
            continue
        if t["font"] > 255 and t.get("width", -1) > 0 and i + 1 < len(texts):
            fmt = fits.get((deff_id, t["x"], t["y"]))
            drawn = texts[i + 1]
            skip = True
            if fmt and drawn["str"] == t["str"]:
                out.append(dict(drawn, source=t.get("source") or fmt[0], fl=fmt[1], w=t["width"],
                                call_site=str(t.get("call_site", t.get("lr", "")))))
            continue
        out.append(t)
    return out


def value_texts(timing, frames, deff_id=None, fits=None):
    """The deff's texts printed from a printf format (A's text records: "source" holds the ROM's format, e.g.
    "%,02lu"), the status panel's aside: [slot], and per frame the slots it shows. A frame shows the texts of
    the last page composed before it; a slot counts for a frame only where the frame's dots are exactly the
    captured string drawn in its font (texts still moving or blinking stay baked in the frame); pages that hold
    only the status panel's rows do not count as compositions. Those dots are
    cleared from the frame (they were drawn over the page) and the slide draws the slot's text live. A fit-font
    text's slot also has "fl" and "w": the slide picks the font for the live text as the ROM does."""
    import bisect
    import gen_fonts
    fonts = {int(f["id"]): f for f in json.load(open(os.path.join(GAME, "fonts", "fonts.json"),
                                                     encoding="utf-8"))["fonts"]}
    get = gen_fonts.load_images()
    # the status panel recomposes its own rows every frame: a page with only those keeps the deff's last page
    pages = [p for p in timing.get("pages") or [] if any(t.get("call_site") not in PANEL_CALLS for t in p["texts"])]
    starts = [p["t_ms"] for p in pages]
    slots, keys, per_frame = [], {}, []
    for (img, _), rec in zip(frames, timing.get("frames") or []):
        shown = []
        k = bisect.bisect_right(starts, rec["t_ms"]) - 1
        for t in page_texts(deff_id, pages[k]["texts"], fits or {}) if k >= 0 else []:
            if "%" not in str(t.get("source", "")) or t.get("call_site") in PANEL_CALLS or t["font"] not in fonts:
                continue
            canvas = [[None] * 128 for _ in range(32)]
            gen_fonts.render(get, fonts[t["font"]], t["str"], t["x"], t["y"], t["flags"], canvas)
            lit = [(x, y, v) for y, row in enumerate(canvas) for x, v in enumerate(row) if v]
            px = img.load()
            if not lit or any(round(px[x, y][0] / 17) != v for x, y, v in lit):
                continue
            key = (t.get("call_site"), t["font"], t["x"], t["y"], t["flags"], t["source"])
            if key not in keys:
                keys[key] = len(slots)
                slots.append({"t": t["str"], "f": t["font"], "x": t["x"], "y": t["y"], "a": t["flags"],
                              "source": t["source"]})
                if "fl" in t:
                    slots[-1].update(fl=t["fl"], w=t["w"])
            for x, y, _ in lit:
                px[x, y] = (0, 0, 0, 255)
            shown.append(keys[key])
        per_frame.append(sorted(set(shown)))
    return slots, per_frame


def loop_period(frames):
    """The shortest run of frames that repeats through the whole recording, or None (a looping deff's capture
    stops mid-cycle: looping the whole recording would jump back from the middle of the cycle)."""
    import hashlib
    h = [hashlib.md5(img.tobytes()).hexdigest() for img, _ in frames]
    n = len(h)
    return next((p for p in range(1, n // 2 + 1) if all(h[i] == h[i + p] for i in range(n - p))), None)


# Effects that draw the player's side (1 Autobot, 2 Decepticon, byte 0x02112107 + player): every capture ran on
# the Decepticon side, so the Autobot slide is the capture with the ROM's Autobot image or message in its place.
# image: (Decepticon image, Autobot image, x, y, rows): deff 40 [0x01034198] draws 0x2234 (Decepticon) or 0x2232
#        (Autobot) at 41, 0 on its background page; rows 25-31 are covered by the text band, so only rows 0-24
#        show the image (observed: those rows of every frame are exactly image 8756). The one frame of 0x2233
#        (both logos, drawn on the tick the side changes) is left out (inferred: 1 tick).
# text: (font, x, y, flags, Decepticon text, Autobot text): deff 41 [0x01034424] draws message 0x683 DECEPTICON
#       or 0x682 AUTOBOT, blinking; frames where the captured text is not exactly drawn stay as they are.
SIDE_VARIANTS = {
    40: {"image": (0x2234, 0x2232, 41, 0, 25)},
    41: {"text": (16, 0x54, 0x12, 2, "DECEPTICON", "AUTOBOT")},
}


def side_frames(deff_id, frames):
    """The Autobot side's frames of a SIDE_VARIANTS effect, made from the (Decepticon) capture's frames."""
    import gen_fonts
    spec = SIDE_VARIANTS[deff_id]
    get = gen_fonts.load_images()
    out = []
    for img, ms in frames:
        img = img.copy()
        px = img.load()
        if "image" in spec:
            old, new, x0, y0, rows = spec["image"]
            a, b = get(old), get(new)
            level_of = lambda v: 0 if v == gen_fonts.TRANSPARENT else v
            if all(px[x0 + x, y0 + y][0] == level_of(a[y][x]) * 17
                   for y in range(rows) for x in range(len(a[0])) if x0 + x < 128):
                for y in range(rows):
                    for x, v in enumerate(b[y]):
                        if x0 + x < 128:
                            level = level_of(v) * 17
                            px[x0 + x, y0 + y] = (level, level, level, 255)
        if "text" in spec:
            font_id, x, y, flags, old, new = spec["text"]
            fonts = {int(f["id"]): f for f in json.load(open(os.path.join(GAME, "fonts", "fonts.json"),
                                                             encoding="utf-8"))["fonts"]}
            was = [[None] * 128 for _ in range(32)]
            gen_fonts.render(get, fonts[font_id], old, x, y, flags, was)
            lit = [(cx, cy, v) for cy, row in enumerate(was) for cx, v in enumerate(row) if v]
            if lit and all(round(px[cx, cy][0] / 17) == v for cx, cy, v in lit):
                for cx, cy, _ in lit:
                    px[cx, cy] = (0, 0, 0, 255)
                now = [[None] * 128 for _ in range(32)]
                gen_fonts.render(get, fonts[font_id], new, x, y, flags, now)
                for cy, row in enumerate(now):
                    for cx, v in enumerate(row):
                        if v is not None:
                            px[cx, cy] = (v * 17, v * 17, v * 17, 255)
        out.append((img, ms))
    return out


def write_slide(deff_id, frames, loop, folder_rel, panel, values=None, name=None):
    """values: (slots, slots per frame) of value_texts, drawn by a "Values" node (tf/deff_values.gd)."""
    import hashlib
    name = name or "deff_{:03d}".format(deff_id)
    ext, entries, seen = [], [], {}
    for img, ms in frames:
        digest = hashlib.md5(img.tobytes()).hexdigest()
        if digest not in seen:
            fname = "{}f{:03d}.png".format(name[9:] + "_" if len(name) > 8 else "", len(seen))
            img.save(os.path.join(GAME, folder_rel, fname))
            seen[digest] = "t{}".format(len(seen))
            ext.append('[ext_resource type="Texture2D" path="res://{}/{}" id="{}"]'.format(folder_rel, fname,
                                                                                         seen[digest]))
        entries.append('{{"duration": {:.1f}, "texture": ExtResource("{}")}}'.format(ms, seen[digest]))
    has_values = bool(values and values[0])
    parts = ['[gd_scene load_steps={} format=3]'.format(len(ext) + 3 + (1 if panel is not None else 0)
                                                        + (1 if has_values else 0)), '',
             '[ext_resource type="Script" path="res://addons/mpf-gmc/classes/mpf_slide.gd" id="slide"]']
    if panel is not None:
        parts.append('[ext_resource type="Script" path="res://tf/rom_screen.gd" id="screen"]')
    if has_values:
        parts.append('[ext_resource type="Script" path="res://tf/deff_values.gd" id="values"]')
    parts += ext
    parts += ['', '[sub_resource type="SpriteFrames" id="frames"]',
              'animations = [{{"frames": [{}], "loop": {}, "name": &"default", "speed": 1000.0}}]'.format(
                  ", ".join(entries), "true" if loop else "false")]
    parts += ['', '[node name="{}" type="Control"]'.format(name), 'layout_mode = 3', 'anchors_preset = 0',
              'offset_right = 128.0', 'offset_bottom = 32.0', 'script = ExtResource("slide")', '',
              '[node name="Background" type="ColorRect" parent="."]', 'layout_mode = 0',
              'offset_right = 128.0', 'offset_bottom = 32.0', 'color = Color(0, 0, 0, 1)', '',
              '[node name="Anim" type="AnimatedSprite2D" parent="."]', 'modulate = {}'.format(DMD_COLOR),
              'sprite_frames = SubResource("frames")', 'autoplay = "default"', 'centered = false']
    if panel is not None:                      # the live status panel (tf/score_screen.py panel_draw)
        parts += ['', '[node name="Panel" type="Control" parent="."]', 'layout_mode = 0',
                  'offset_right = 128.0', 'offset_bottom = 32.0', 'script = ExtResource("screen")']
    if has_values:                             # the printf texts, drawn live on the frames that show them
        parts += ['', '[node name="Values" type="Control" parent="."]', 'layout_mode = 0',
                  'offset_right = 128.0', 'offset_bottom = 32.0', 'script = ExtResource("values")',
                  'metadata/slots = {}'.format(json.dumps(json.dumps(values[0]))),
                  'metadata/frames = {}'.format(json.dumps(json.dumps(values[1])))]
    with open(os.path.join(GAME, "slides", "deffs", name + ".tscn"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")
    return name


def build_deffs(only_data):
    """One slide per captured display effect: the ROM's frames at their observed times (a background deff
    loops its shortest repeating cycle). Where the deff draws the status panel, the capture's panel columns
    (0-40, the score 00 of the capture run) are cleared and the live panel is drawn over them. Deffs with no
    captured frame (the ROM drew nothing in the capture window, or they read live state) are left out;
    deff 19 is drawn from its draw calls (tf/score_screen.py)."""
    from PIL import ImageDraw
    import fsutil
    rows = deff_rows()
    fits = fit_formats()
    out = {}
    if not only_data:
        fsutil.clear_dir(os.path.join(GAME, "slides", "deffs"))
        fsutil.clear_dir(os.path.join(GAME, "media", "dmd"))
    for folder in sorted(glob.glob(os.path.join(DEFFS, "deff_*"))):
        deff_id = int(os.path.basename(folder).split("_")[1])
        if deff_id == 19:
            continue
        with open(os.path.join(folder, "timing.json"), encoding="utf-8") as f:
            timing = json.load(f)
        if not timing.get("frames"):
            continue
        frames = capture_frames(folder, timing)
        panel = panel_level(timing, frames)
        loop = rows.get(deff_id, {}).get("background_loop") == "yes"
        slots, per_frame = value_texts(timing, frames, deff_id, fits)
        out[deff_id] = {"slide": "deff_{:03d}".format(deff_id), "source": "reference", "text": [], "loop": loop,
                        "panel": panel, "args": [], "values": [v["source"] for v in slots]}
        if deff_id in SIDE_VARIANTS:
            out[deff_id]["sides"] = {"1": "deff_{:03d}_side1".format(deff_id)}
        if only_data:
            continue
        if panel is not None:
            for img, _ in frames:
                ImageDraw.Draw(img).rectangle((0, 0, PANEL_WIDTH - 1, 31), fill=(0, 0, 0, 255))
        if loop:
            period = loop_period(frames)
            frames = frames[:period] if period else frames
            per_frame = per_frame[:len(frames)]
        rel = "media/dmd/deff_{:03d}".format(deff_id)
        os.makedirs(os.path.join(GAME, rel), exist_ok=True)
        write_slide(deff_id, frames, loop, rel, panel, (slots, per_frame))
        if deff_id in SIDE_VARIANTS:
            name = "deff_{:03d}_side1".format(deff_id)
            write_slide(deff_id, side_frames(deff_id, frames), loop, rel, panel, (slots, per_frame), name=name)
    return out


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
