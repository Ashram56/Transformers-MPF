#!/usr/bin/env python3
"""Check the complete game package of Transformers Pro (scripts/package/game_package.json).

    python scripts/package/build_package.py [--list]

The game builds its own package (`python scripts/setup.py` makes every generated file: config, sounds, media, fonts,
display-effect slides, media_data.json, the Godot import) and describes it in game_package.json. This script only
checks that the package is complete: every path the contract lists exists, none of the never-lists is staged. The bundle
itself is made from this folder by the platform (MPF-Godot-Packaging, `python -m mpf_godot bundle`), which knows no game.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import toolchain as tc  # noqa: E402

CONTRACT = os.path.join(HERE, "game_package.json")


def load():
    with open(CONTRACT, encoding="utf-8") as f:
        return json.load(f)


def listed(contract):
    """Every path the package holds besides the tracked folders: the files `copy` names (generated ones included)."""
    return list(contract["copy"])


def missing(contract):
    """Paths the contract lists that are not on disk."""
    return [rel for rel in listed(contract) if not os.path.exists(os.path.join(ROOT, rel))]


def problems(contract):
    """What stops a package: a stale media build, a listed path that is missing, ROM or cabinet files in the way."""
    out = []
    why = tc.media_stale(ROOT)
    if why:
        out.append("generated media: " + why + " (run `python scripts/setup.py`)")
    out += [rel + " is listed in game_package.json but missing (run `python scripts/setup.py`)" for rel in missing(contract)]
    game = os.path.join(ROOT, contract.get("game_dir", "game"))
    for dirpath, dirs, names in os.walk(game):
        if dirpath == game:
            dirs[:] = [d for d in dirs if d != ".godot"]    # the import's own .bin caches belong in the package
        for n in names:
            if n.endswith((".bin", ".local.cfg")):
                out.append("never in a package: " + os.path.relpath(os.path.join(dirpath, n), ROOT))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--list", action="store_true", help="print the paths the contract lists")
    a = p.parse_args()
    contract = load()
    if a.list:
        print("\n".join(listed(contract)))
        return 0
    bad = problems(contract)
    for line in bad:
        print("package: " + line, file=sys.stderr)
    if not bad:
        print("package: complete ({} listed paths)".format(len(listed(contract))))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
