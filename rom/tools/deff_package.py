"""Write the display effects (deffs) of the MPF package from their code (deff_lift.py + deff_render.py).

For each deff: rom/rom_data/dmd/deff_ops/deff_NNN.json (the op list, every op with the ROM address of its call)
and rom/mpf_package/media/dmd/deffs/deff_NNN/ (frames/NNNN.png, the frames where the DMD changes, level x 17
grey; timing.json, the same keys the game reads: frames, ended_ms, sounds, leffs, pages and their texts).
Times: ticks of the OS task loop (task_sleep); one tick is 64 IO interrupts of 250 us [0x000114b0], 16.0 ms
nominal; ms here are ticks x TICK_MS, the game's tick (game/tf/os_layer.py TICK, 16.26 ms: the tick is a
minimum, the loop runs late when a pass is long).

Every variant of a deff drawn from game state (deff_variants.py, deff_NNN__<name>.json) gets its own frames and
timing in deff_NNN/variants/<name>/ (deff_package.py --ops-variants renders them from the op lists already in
rom_data/dmd/deff_ops/, without the lift).

Usage: TF_ROM=tf_180.bin deff_package.py LIFT_DIR [deff ...]
       TF_ROM=tf_180.bin deff_package.py --ops-variants [deff ...]
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import deff_render  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROMDIR = os.path.join(HERE, "..")
PKG_DEFFS = os.path.join(ROMDIR, "mpf_package", "media", "dmd", "deffs")
OPS_DIR = os.path.join(ROMDIR, "rom_data", "dmd", "deff_ops")
TICK_MS = 16.0                     # the OS tick from the code: 64 IO interrupts of 250 us [0x000114b0] (owner, 2026-11-25)
PANEL_SITES = ("0x0102f2ec", "0x0102f36c")


def compact_ops(doc):
    out = []
    for o in doc["ops"]:
        o = {k: v for k, v in o.items() if not (k == "task" and v == 128)}
        out.append(o)
    return out


def package(doc, variant=None):
    """variant: a variant's name (deff_NNN__<name>.json): its frames and timing go in deff_NNN/variants/<name>/
    and its op list stays where save_variant wrote it."""
    n = doc["deff"]
    frames = deff_render.render(doc)
    end = doc.get("end_tick")
    last = end if end is not None else doc.get("ran_ticks")
    folder = os.path.join(PKG_DEFFS, "deff_%03d" % n)
    if variant:
        folder = os.path.join(folder, "variants", variant)
    fdir = os.path.join(folder, "frames")
    os.makedirs(fdir, exist_ok=True)
    for p in glob.glob(os.path.join(fdir, "*.png")):
        os.remove(p)
    for p in glob.glob(os.path.join(folder, "*.gif")):
        os.remove(p)
    # the frames where the DMD changes; a tick shown twice keeps its last composition
    by_tick = {}
    for t, dots, _ in frames:
        by_tick[t] = dots
    seq = []
    for t in sorted(by_tick):
        if not seq or not np.array_equal(seq[-1][1], by_tick[t]):
            seq.append((t, by_tick[t]))
    recs = []
    for i, (t, dots) in enumerate(seq):
        nxt = seq[i + 1][0] if i + 1 < len(seq) else max(last or t + 1, t + 1)
        Image.fromarray((dots * 17).astype(np.uint8), "L").save(os.path.join(fdir, "%04d.png" % i))
        recs.append({"i": i, "tick": t, "t_ms": round(t * TICK_MS, 1), "dur_ms": round((nxt - t) * TICK_MS, 1)})
    pages, cur = [], None
    for o in doc["ops"]:
        if o["op"] == "text":
            if cur is None or cur["tick"] != o["t"]:
                cur = {"tick": o["t"], "t_ms": round(o["t"] * TICK_MS, 1), "texts": []}
                pages.append(cur)
            t = {"str": o["text"], "font": o["font"], "x": o["x"], "y": o["y"], "flags": o["flags"],
                 "call_site": o["at"][2:].lstrip("0"), "page": o["page"]}
            if o.get("printf"):
                t["source"] = o.get("format")          # the printf format: the game draws the value live
                t["msg"] = o.get("msg")
            if "font_list" in o:
                t["font_list"] = o["font_list"]
                t["width"] = o.get("fit", 0)
            cur["texts"].append(t)
    sounds = [{"tick": o["t"], "t_ms": round(o["t"] * TICK_MS, 1), "call": "%x" % o["call"], "deff": n,
               "sample": o.get("sample"), "at": o["at"]}
              for o in doc["ops"] if o["op"] in ("sound", "sound_after")]
    leffs = [{"tick": o["t"], "t_ms": round(o["t"] * TICK_MS, 1), "leff": o["leff"], "at": o["at"]}
             for o in doc["ops"] if o["op"] == "leff"]
    deffs = [{"tick": o["t"], "deff": o["deff"], "at": o["at"]} for o in doc["ops"] if o["op"] == "deff"]
    # deff_prio_set (most often 0x010305a0 near the end): the effect lowers its own priority, so a waiting
    # effect or the score display (deff 19) takes the DMD from that tick (deff 140: tick 105 [0x0100b90c])
    prio = [{"tick": o["t"], "t_ms": round(o["t"] * TICK_MS, 1), "priority": o["prio"], "at": o["at"]}
            for o in doc["ops"] if o["op"] == "prio"]
    timing = {"deff": n, "fn": doc["fn"], "flags": doc["flags"], "priority": doc["priority"],
              "background": bool(doc["flags"] & 1), "tag": "code",
              "note": "decoded from the deff's function in tf_180 (rom/tools/deff_lift.py): op list "
                      "rom/rom_data/dmd/deff_ops/deff_%03d.json; frames drawn from the ROM's images and fonts "
                      "(rom/tools/deff_render.py)" % n,
              "end_tick": end, "ended_ms": round(end * TICK_MS, 1) if end is not None else None,
              "ran_ticks": doc.get("ran_ticks"), "tick_ms": TICK_MS,
              "panel": any(t["call_site"] in [s[2:].lstrip("0") for s in PANEL_SITES]
                           for p in pages for t in p["texts"]),
              "frames": recs, "sounds": sounds, "leffs": leffs, "deffs": deffs, "priority_changes": prio, "pages": pages,
              "inputs": doc.get("reads", [])[:50], "detached_tasks": doc.get("detached", [])}
    if doc.get("variant"):          # a deff drawn from game state: the state this one ran with (deff_variants.py)
        timing["variant"] = doc["variant"]
        timing["other_variants"] = doc.get("other_variants", [])
    if variant:
        timing["note"] = timing["note"].replace("deff_%03d.json" % n, "deff_%03d__%s.json" % (n, variant))
    with open(os.path.join(folder, "timing.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(timing, f, indent=1)
    if variant:
        return len(recs)
    os.makedirs(OPS_DIR, exist_ok=True)
    with open(os.path.join(OPS_DIR, "deff_%03d.json" % n), "w", encoding="utf-8", newline="\n") as f:
        json.dump({k: v for k, v in doc.items() if k != "ops"} | {"ops": compact_ops(doc)}, f,
                  separators=(",", ":"))
        f.write("\n")
    return len(recs)


def save_variant(doc, name):
    """Another state's op list (deff_variants.py), next to the packaged one: deff_NNN__<name>.json."""
    os.makedirs(OPS_DIR, exist_ok=True)
    with open(os.path.join(OPS_DIR, "deff_%03d__%s.json" % (doc["deff"], name)), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump({k: v for k, v in doc.items() if k != "ops"} | {"ops": compact_ops(doc)}, f,
                  separators=(",", ":"))
        f.write("\n")


def ops_variants(ids):
    """The variants' frames from their saved op lists (rom_data/dmd/deff_ops/deff_NNN__<name>.json)."""
    for p in sorted(glob.glob(os.path.join(OPS_DIR, "deff_*__*.json"))):
        doc = json.load(open(p))
        if ids and doc["deff"] not in ids or "error" in doc:
            continue
        name = os.path.basename(p)[:-5].split("__", 1)[1]
        print(doc["deff"], name, package(doc, name), "frames")


def main():
    if sys.argv[1] == "--ops-variants":
        ops_variants([int(x) for x in sys.argv[2:]])
        return
    src = sys.argv[1]
    ids = [int(x) for x in sys.argv[2:]]
    for p in sorted(glob.glob(os.path.join(src, "deff_*.json"))):
        doc = json.load(open(p))
        if ids and doc["deff"] not in ids:
            continue
        base = os.path.basename(p)[:-5]
        if "__" in base:
            save_variant(doc, base.split("__", 1)[1])
            if "error" not in doc:
                print(doc["deff"], base.split("__", 1)[1], package(doc, base.split("__", 1)[1]), "frames")
            continue
        doc["other_variants"] = sorted(os.path.basename(q)[:-5].split("__", 1)[1]
                                       for q in glob.glob(os.path.join(src, base + "__*.json")))
        if "error" in doc:
            print(doc["deff"], "error", doc["error"])
            continue
        print(doc["deff"], package(doc), "frames")


if __name__ == "__main__":
    main()
