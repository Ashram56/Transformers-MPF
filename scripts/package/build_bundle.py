#!/usr/bin/env python3
"""Build the universal prebuilt bundle of Transformers Pro (docs/bundle.md).

    python scripts/package/build_bundle.py [--out DIR] [--check-only]

The builder itself is the platform's (Ashram56/MPF-Godot-Packaging, `python -m mpf_godot bundle`, method in its
platforms/game-bundles.md). This file is only the game's part: refuse a stale or missing build, check that no
cabinet data, ROM or PuP Pack file is in the way, then call the platform builder with bundle_spec.json
(--target all: both texture formats, imported offline). Run after `python scripts/setup.py`.
"""
import argparse
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
    for rel in ("game/config/rom", "game/sounds", "game/fonts"):
        if not os.path.isdir(os.path.join(ROOT, rel)):
            out.append(rel + " is missing (run `python scripts/setup.py`)")
    game = os.path.join(ROOT, "game")
    for dirpath, _, names in os.walk(game):
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
              "(pip install git+https://github.com/Ashram56/MPF-Godot-Packaging) and run again, or run\n"
              "  python -m mpf_godot bundle bundle_spec.json --target all", file=sys.stderr)
        return 2
    cmd = [sys.executable, "-m", "mpf_godot", "bundle", SPEC, "--target", "all", "--out", a.out]
    print("bundle: $ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
