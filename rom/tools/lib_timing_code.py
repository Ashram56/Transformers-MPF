"""Set the frame time and x position of the dmd_library animations from the deff op lists run in ROM code
(rom_data/dmd/deff_ops/*.json, deff_lift.py: every image a deff draws, with its tick and x).

frame_ms: the median number of ticks between two consecutive images of one animation drawn by one deff, times
the 16.0 ms tick (owner, 2026-11-25); x_on_128: the x the code draws it at most often. Tags say "code (deff op
lists: deffs ...)". An animation no deff op list draws gets them from the frame players' call sites in rom/code/tf_decompiled.c:
anim_play_frames_main_2ff60 [0x0102ff60] and its variants (0x0102fd3c, 0x0102fe64, 0x01030064, 0x01030188) take
(first image, last image, speed, loops, ...), draw the frame at x = 0x29 (41) and step to the next image every
`speed` ticks (count_down_step_2fc5c [0x0102fc5c]), so frame_ms = speed x 16 ms. The image loops of the
game code (`v = first; do { ... bitmap_draw2(v, page, x, ...); ... task_sleep(n); v++ } while (v < end)`, e.g.
[0x0101cef8]) give frame_ms = n x 16 ms and their x. Anything else keeps its value and tag.

Usage: python3 lib_timing_code.py [--dry]
"""
import collections
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OPS = os.path.join(HERE, "..", "rom_data", "dmd", "deff_ops")
LIB = os.path.join(HERE, "..", "mpf_package", "media", "dmd_library", "index.json")
TICK_MS = 16.0
DECOMP = os.path.join(HERE, "..", "code", "tf_decompiled.c")
PLAYERS = r"anim_play_frames_(?:main_2ff60|hold_2fd3c|2fe64|snd_copy_30064|plain_30188)"


def num(s):
    s = s.strip()
    s = re.sub(r"^&DAT_", "0x", s)
    try:
        return int(s, 0)
    except ValueError:
        return None


def player_calls():
    """[(first, last, speed, header of the caller)] from the frame players' call sites with constant arguments."""
    out, head = [], None
    for ln in open(DECOMP, encoding="utf-8"):
        if ln.startswith("// ==== "):
            head = ln.split()[2]
        m = re.search(PLAYERS + r"\(([^;]*)\);", ln)
        if m and not ln.lstrip().startswith(("int ", "void ", "//")):
            a = [num(x) for x in m.group(1).split(",")]
            if len(a) >= 3 and None not in a[:3]:
                out.append((a[0], a[1], a[2], head))
    return out


def image_loops():
    """[(first, last, ticks, x, header)] from the image loops of the decompile."""
    src = open(DECOMP, encoding="utf-8").read()
    out = []
    for part in re.split(r"^(?=// ==== [0-9a-f]{8} )", src, flags=re.M):
        m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", part)
        if not m:
            continue
        for v, first in re.findall(r"\b(\w+) = (0x[0-9a-f]+|\d+);\n", part):
            d = re.search(r"bitmap_draw2?\(%s,\w+,(0x[0-9a-f]+|\d+)," % re.escape(v), part)
            e = re.search(r"while \(%s < (0x[0-9a-f]+|\d+)\)" % re.escape(v), part)
            t = re.search(r"task_sleep\((0x[0-9a-f]+|\d+)\)", part[d.end():] if d else "")
            if d and e and t:
                out.append((int(first, 0), int(e.group(1), 0) - 1, int(t.group(1), 0), int(d.group(1), 0), m.group(2)))
    return out


def main():
    lib = json.load(open(LIB))
    by = {}
    for a in lib:
        for i in range(a["first_image"], a["last_image"] + 1):
            by[i] = a["name"]
    dt = collections.defaultdict(list)
    xs = collections.defaultdict(collections.Counter)
    who = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(OPS, "deff_*.json"))):
        d = json.load(open(p))
        last = {}                                  # per page: the last image drawn (img, name, tick)
        for o in d["ops"]:
            i = o.get("img")
            if i is None or by.get(i) is None:
                continue
            n = by[i]
            xs[n][o.get("x", 0)] += 1
            who[n].add(d["deff"])
            prev = last.get(n)
            if prev and i == prev[0] + 1 and o["t"] > prev[1]:
                dt[n].append(o["t"] - prev[1])
            last[n] = (i, o["t"])
    k = m = 0
    for a in lib:
        n = a["name"]
        if xs[n]:
            m += 1
            a["x_on_128"] = xs[n].most_common(1)[0][0] if a["w"] < 128 else 0
            a["x_tag"] = "code (deff op lists: deffs %s)" % " ".join(map(str, sorted(who[n])))
            a["deffs"] = sorted(who[n])
        if dt[n]:
            k += 1
            a["frame_ms"] = round(statistics.median(dt[n]) * TICK_MS)
            a["frame_ms_tag"] = "code (median of %d steps in the deff op lists, %d ms ticks)" % (len(dt[n]), TICK_MS)
    calls = player_calls()
    s_ = 0
    for a in lib:
        if a.get("frame_ms_tag", "").startswith("code"):
            continue
        hit = [c for c in calls if c[0] <= a["last_image"] and c[1] >= a["first_image"] and c[2] > 0]
        if hit:
            sp = collections.Counter(c[2] for c in hit).most_common(1)[0][0]
            a["frame_ms"] = round(sp * TICK_MS)
            a["frame_ms_tag"] = "code (frame player speed %d at %s)" % (sp, " ".join(sorted({c[3] for c in hit})[:4]))
            if not a.get("x_tag", "").startswith("code"):
                a["x_on_128"] = 0x29 if a["w"] < 128 else 0
                a["x_tag"] = "code (frame player draws at x = 0x29 [0x0102ff60])"
            s_ += 1
    print("frame time from the frame players' call sites", s_, "(%d calls)" % len(calls))
    loops, l_ = image_loops(), 0
    for a in lib:
        if a.get("frame_ms_tag", "").startswith("code"):
            continue
        hit = [c for c in loops if c[0] <= a["last_image"] and c[1] >= a["first_image"] and c[2] > 0]
        if hit:
            t = collections.Counter(c[2] for c in hit).most_common(1)[0][0]
            a["frame_ms"] = round(t * TICK_MS)
            a["frame_ms_tag"] = "code (image loop, task_sleep(%d), at %s)" % (t, " ".join(sorted({c[4] for c in hit})[:4]))
            if not a.get("x_tag", "").startswith("code"):
                a["x_on_128"] = hit[0][3] if a["w"] < 128 else 0
                a["x_tag"] = "code (image loop draws at x = %d)" % hit[0][3]
            l_ += 1
    print("frame time from the image loops", l_, "(%d loops)" % len(loops))
    left = [a["name"] for a in lib if not a.get("frame_ms_tag", "").startswith("code")]
    for a in lib:                                  # what the code does not show is said so
        if a["name"] in left and "no constant" not in a.get("frame_ms_tag", ""):
            a["frame_ms_tag"] += "; code: no deff op list draws it and no frame player or image loop names it " \
                                 "with constants (played through a table, or unused)"
    print("x from code", m, "frame time from code", k, "of", len(lib), "; not drawn by a deff:", len(left))
    if "--dry" not in sys.argv:
        json.dump(lib, open(LIB, "w"), indent=1)
    return left


if __name__ == "__main__":
    main()
