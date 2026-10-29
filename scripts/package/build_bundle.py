#!/usr/bin/env python3
"""Build the universal prebuilt bundle of Transformers Pro (docs/bundle.md).

    python scripts/package/build_bundle.py [--out DIR] [--check-only]

The builder itself is the platform's (Ashram56/MPF-Godot-Packaging, `python -m mpf_godot bundle`, method in its
platforms/game-bundles.md). This file is only the game's part: refuse a stale or missing build, check that no
cabinet data, ROM or PuP Pack file is in the way, then call the platform builder with bundle_spec.json
(--target all: both texture formats, imported offline). Run after `python scripts/setup.py`.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import toolchain as tc  # noqa: E402

SPEC = os.path.join(ROOT, "bundle_spec.json")
FORBIDDEN = ("*.bin", "tf_*.zip")


def problems():
    """What stops a build: a stale or missing generated build, or files that must never be packed."""
    out = []
    why = tc.media_stale(ROOT)
    if why:
        out.append("generated media: " + why + " (run `python scripts/setup.py`)")
    # git-ignored files the game needs at run time, made by setup.py; bundle_spec.json "copy" must list each one
    for rel in ("game/config/rom", "game/sounds", "game/media", "game/fonts", "game/slides/deffs", "game/tf/media_data.json"):
        if not os.path.exists(os.path.join(ROOT, rel)):
            out.append(rel + " is missing (run `python scripts/setup.py`)")
    game = os.path.join(ROOT, "game")
    for dirpath, dirs, names in os.walk(game):
        if dirpath == game:
            dirs[:] = [d for d in dirs if d != ".godot"]    # the import's own .bin caches are packed on purpose
        for n in names:
            if n.endswith((".bin", ".local.cfg")):
                out.append("never in a bundle: " + os.path.relpath(os.path.join(dirpath, n), ROOT))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where the platform builder writes (default dist/)")
    p.add_argument("--check-only", action="store_true", help="only the game's checks")
    a = p.parse_args()
    bad = problems()
    for line in bad:
        print("bundle: " + line, file=sys.stderr)
    if bad:
        return 1
    if a.check_only:
        print("bundle: checks passed")
        return 0
    try:
        import mpf_godot  # noqa: F401
    except ImportError:
        print("bundle: the platform builder is not installed. Install MPF-Godot-Packaging "
              "(clone it, `python -m mpf_godot setup`, and run this script with its checkout on PYTHONPATH)", file=sys.stderr)
        return 2
    # game/tf/media_table.py reads rom/mpf_package/media/dmd/deffs/deff_*/timing.json at run time: the platform
    # builder copies named paths only, so the spec for this build lists them (the frames are generated into game/media).
    with open(SPEC, encoding="utf-8") as f:
        spec = json.load(f)
    spec["copy"] += sorted(os.path.relpath(p, ROOT).replace(os.sep, "/") for p in glob.glob(
        os.path.join(ROOT, "rom", "mpf_package", "media", "dmd", "deffs", "deff_*", "timing.json")))
    build_spec = os.path.join(ROOT, ".bundle_spec.build.json")
    with open(build_spec, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1)
    cmd = [sys.executable, "-m", "mpf_godot", "bundle", build_spec, "--target", "all", "--out", a.out]
    print("bundle: $ " + " ".join(cmd))
    try:
        return subprocess.run(cmd, cwd=ROOT).returncode
    finally:
        os.remove(build_spec)


if __name__ == "__main__":
    sys.exit(main())
