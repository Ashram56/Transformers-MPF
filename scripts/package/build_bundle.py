#!/usr/bin/env python3
"""Build the prebuilt bundle of Transformers Pro (docs/package.md): the game as it runs, nothing left to make on the machine.

    python scripts/package/build_bundle.py --pup-zip PACK.zip        # universal bundle (arm64 + x86_64) in dist/
    python scripts/package/build_bundle.py --target x86_64 --version 2026.11.02 --out /some/folder --pup-zip PACK.zip
    python scripts/package/build_bundle.py --no-pup                    # a bundle without PuP support

The builder is the platform's, the same for every game: `python -m mpf_godot bundle` of MPF-Godot-Packaging, which knows no
game. Everything about this game is in scripts/package/game_package.json; this script only adds what the platform asks the
game to do around it (MPF-Godot-Packaging platforms/game-bundles.md, rules 12 and 13):

1. checks that the package is complete (build_package.py: setup.py made every generated file);
2. makes the PuP media offline, here: with --pup-zip the pack is unpacked on this builder and scripts/pup_setup.py writes
   pup_media/tf_180 (the manifest, the pack's music and pictures; the mp4s stay the pack's, played by the platform's GoZen),
   which the bundle carries. The machine that runs the game only unpacks the author's zip (pup.extract_only);
3. calls the platform's builder with game_package.json.

MPF-Godot-Packaging's common/games/build_game_package.py runs this (the Stern SAM convention) after scripts/setup.py, with
--target, --version, --out and --pup-zip. Set MPF_GODOT_PACKAGING to its checkout when it is not beside this repository.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/
sys.path.insert(0, HERE)
import build_package  # noqa: E402
import toolchain as tc  # noqa: E402

ROOT = tc.ROOT
PUP_MEDIA = "pup_media/tf_180"                 # [pup] media_dir of game/pup.cfg
VIDEO = (".mp4", ".m4v", ".mov", ".avi", ".wmv", ".webm", ".mkv", ".f4v")


def platform_dir():
    """The MPF-Godot-Packaging checkout: MPF_GODOT_PACKAGING, the one build_game_package.py puts on PYTHONPATH, or beside us."""
    cands = [os.environ.get("MPF_GODOT_PACKAGING")] + os.environ.get("PYTHONPATH", "").split(os.pathsep)
    cands += [os.path.join(os.path.dirname(ROOT), n) for n in ("MPF-Godot-Packaging", "mpf-godot-packaging", "MPF-Godot")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "mpf_godot", "bundle.py")):
            return os.path.abspath(c)
    raise SystemExit("MPF-Godot-Packaging not found: clone it beside this repository or set MPF_GODOT_PACKAGING")


def pup_media_problem():
    """Why pup_media/tf_180 cannot go in a bundle (None when it can): missing, or videos converted instead of played as they are."""
    path = os.path.join(ROOT, PUP_MEDIA, "manifest.json")
    if not os.path.exists(path):
        return "no " + PUP_MEDIA + "/manifest.json"
    with open(path, encoding="utf-8") as f:
        files = json.load(f).get("files", {})
    converted = [k for k, v in files.items() if k.lower().endswith(VIDEO) and not v.get("native")]
    if converted:
        return "{} videos were converted (Theora) instead of kept as they are, e.g. {}: the platform's GoZen plays the mp4s " \
               "(rule 7)".format(len(converted), converted[0])
    return None


def make_pup_media(zip_):
    """Unpack the pack on this builder and write pup_media/tf_180 with the game's own PuP setup (videos only probed)."""
    env = {k: v for k, v in os.environ.items() if k not in ("TF_PUP", "TF_GOZEN", "TF_NATIVE_VIDEO")}
    env["TF_PUP_ZIP"] = zip_
    print("== PuP media, made here from " + zip_, flush=True)
    if subprocess.run([tc.python(), os.path.join(ROOT, "scripts", "pup_setup.py")], cwd=ROOT, env=env).returncode:
        raise SystemExit("the PuP Pack could not be installed and its media made (above)")


def spec(with_pup):
    with open(build_package.CONTRACT, encoding="utf-8") as f:
        out = json.load(f)
    if not with_pup:
        out.pop("pup", None)
        out["copy"] = [p for p in out["copy"] if p != PUP_MEDIA]
        out["optional"] = [p for p in out.get("optional", []) if p != PUP_MEDIA]
    else:
        out["optional"] = [p for p in out.get("optional", []) if p != PUP_MEDIA]     # required now
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--target", choices=["arm64", "x86_64", "all"], default="all",
                   help="arm64: Raspberry Pi and Jetson (ETC2 textures); x86_64: a PC (S3TC); all: both (default)")
    p.add_argument("--version", help="default: the platform's YYYY.MM.DD-<short commit>")
    p.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where the archive goes (default dist/)")
    p.add_argument("--pup-zip", help="the author's PuP Pack zip (a path or URL): its media for the game are made here and shipped "
                                     "in the bundle; the pack itself never is")
    p.add_argument("--no-pup", action="store_true", help="a bundle without PuP support (the strict ROM game only)")
    p.add_argument("--no-archive", action="store_true", help="stop after staging; leave the folder")
    a = p.parse_args(argv)
    if a.pup_zip and a.no_pup:
        p.error("--pup-zip and --no-pup exclude each other")
    if a.pup_zip:
        make_pup_media(a.pup_zip)
    bad = build_package.problems(build_package.load())
    if bad:
        raise SystemExit("the package is not complete:\n  " + "\n  ".join(bad))
    if not a.no_pup:
        why = pup_media_problem()
        if why:
            raise SystemExit("PuP media: {}. Give the pack's zip with --pup-zip ZIP (its media are made here, never on the "
                             "machine that runs the game), or --no-pup for a bundle without the PuP".format(why))
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    fd, spec_path = tempfile.mkstemp(prefix="game_package.", suffix=".json", dir=out)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(spec(not a.no_pup), f, indent=1)
    cmd = [sys.executable, "-m", "mpf_godot", "bundle", spec_path, "--root", ROOT, "--target", a.target, "--out", out]
    cmd += (["--version", a.version] if a.version else []) + (["--no-archive"] if a.no_archive else [])
    plat = platform_dir()
    env = dict(os.environ, PYTHONPATH=plat + os.pathsep + os.environ.get("PYTHONPATH", ""))
    if not env.get("GODOT"):
        env["GODOT"] = tc.godot_path()
    print("$ " + " ".join(cmd), flush=True)
    try:
        return subprocess.run(cmd, cwd=plat, env=env).returncode
    finally:
        os.remove(spec_path)


if __name__ == "__main__":
    sys.exit(main())
