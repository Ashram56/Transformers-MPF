#!/usr/bin/env python3
"""Start the installed bundle with its saved settings: scripts/run.py plus the flags kept in game/options.json.

    python scripts/package/start.py                 # as saved (bundle.json run.start)
    python scripts/package/start.py --seconds 20    # any run.py option; one given here wins over the saved one
    python scripts/package/start.py -- --rendering-driver opengl3   # Godot arguments after --

The platform adds the board's Godot arguments (MPF_GAME_ARGS) after the command (bundle.json run.game_args), and run.py
passes everything after `--` to Godot. Settings are changed with scripts/package/bundle_options.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/
sys.path.insert(0, HERE)

import bundle_options  # noqa: E402
import run  # noqa: E402


def merge(saved, given):
    """The saved flags without those the command line sets again (--name or --name=value, either form). Only the part of
    `given` before Godot's `--` counts."""
    def name(a):                    # --free-play and --no-free-play are one setting
        return a.split("=", 1)[0].replace("--no-", "--", 1)

    head = given[:given.index("--")] if "--" in given else given
    names = {name(a) for a in head if a.startswith("--")}
    out, i = [], 0
    while i < len(saved):
        a = saved[i]
        if name(a) in names:
            i += 1 if "=" in a or i + 1 >= len(saved) or saved[i + 1].startswith("--") else 2
            continue
        out.append(a)
        i += 1
    return out + list(given)


def main(argv=None):
    given = list(sys.argv[1:] if argv is None else argv)
    return run.main(merge(bundle_options.run_args(), given))


if __name__ == "__main__":
    sys.exit(main() or 0)
