#!/usr/bin/env python3
"""Can this unpacked bundle start? Exits 0 when it can, else prints why and exits 1. A few seconds, no display.

    python scripts/package/check.py        # bundle.json run.check (MPF-Godot-Packaging platforms/game-bundles.md, rule 9)

The platform's builder runs it on the extracted archive and its setup page before it installs a bundle (MPF_BUNDLE_CHECK=1);
a failure refuses the bundle and leaves the running game alone. It checks what the platform's import check cannot see:
every path of the package contract (game_package.json) is there, the saved settings read, MPF imports, the MPF config
files parse, the Godot project and the PuP settings load. Nothing is started and nothing is written.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/
sys.path.insert(0, HERE)


def problems():
    out = []
    with open(os.path.join(HERE, "game_package.json"), encoding="utf-8") as f:
        contract = json.load(f)
    optional = set(contract.get("optional", []))
    out += ["missing " + rel for rel in contract["copy"]
            if rel not in optional and not os.path.exists(os.path.join(ROOT, rel))]
    if not os.path.isfile(os.path.join(ROOT, "game", "project.godot")):
        out.append("missing game/project.godot")
    try:
        import bundle_options
        bundle_options.get_values()
        bundle_options.run_args()
    except Exception as e:                  # noqa: BLE001  a broken game/options.json or pup.local.cfg
        out.append("the saved settings cannot be read: {}".format(e))
    try:
        import run  # noqa: F401  (the start chain: run.py, gmc_patch, pup_setup, toolchain, the PuP settings)
        import pup_setup
        pup_setup.status()
    except Exception as e:                  # noqa: BLE001
        out.append("the start scripts do not load: {!r}".format(e))
    try:
        from mpf.file_interfaces.yaml_interface import YamlInterface
    except ImportError as e:
        out.append("MPF is not importable by this Python ({}): {}".format(sys.executable, e))
    else:
        files = sorted(glob.glob(os.path.join(ROOT, "game", "config", "*.yaml")) +
                       glob.glob(os.path.join(ROOT, "game", "config", "rom", "*.yaml")) +
                       glob.glob(os.path.join(ROOT, "game", "modes", "*", "config", "*.yaml")))
        if not files:
            out.append("no MPF config in game/config")
        for path in files:
            try:
                YamlInterface().load(path)
            except Exception as e:          # noqa: BLE001
                out.append("{} does not parse: {}".format(os.path.relpath(path, ROOT), e))
    return out


def main():
    bad = problems()
    for line in bad:
        print("check: " + line, file=sys.stderr)
    if not bad:
        print("check: the game can start")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
