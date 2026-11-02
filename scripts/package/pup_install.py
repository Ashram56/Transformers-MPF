#!/usr/bin/env python3
"""Install the PuP Pack in an installed bundle: only unpack the author's zip, nothing is converted or generated.

    python scripts/package/pup_install.py --pup-zip ZIP_OR_URL     # bundle.json pup.install

The bundle already carries what the game derives from the pack (pup_media/tf_180: the manifest, the pack's music and
pictures), made offline when the bundle was built (scripts/package/build_bundle.py --pup-zip; MPF-Godot-Packaging
platforms/game-bundles.md, rules 12 and 13). So on the machine that runs the game this only puts the pack's folder (the one
holding triggers.pup) in pup_pack/tf_180: no ffmpeg, no pip, no video add-on (GoZen is the platform's), no conversion.
The setup page does the same by itself for a pack from its library (bundle.json pup.extract_only); this command is for
the page's direct pack upload and for doing it by hand.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/

import pup_setup  # noqa: E402
import toolchain as tc  # noqa: E402
from pup_runtime import settings  # noqa: E402  (pup_setup puts game/ on the path)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--pup-zip", required=True, help="the author's zip: a file or an https URL")
    a = p.parse_args(argv)
    cfg = settings.load()
    pack, media = settings.pack_dir(cfg), settings.media_dir(cfg)
    if pup_setup.pack_from_zip(a.pup_zip, pack):
        return 1
    if not os.path.exists(os.path.join(media, "manifest.json")):
        print("this bundle carries no PuP media ({}): it was built without the pack (build_bundle.py --no-pup), so the "
              "PuP stays off; install a bundle built with --pup-zip".format(os.path.relpath(media, tc.ROOT)), file=sys.stderr)
        return 1
    print(pup_setup.status()[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
