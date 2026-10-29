"""The game's package contract (scripts/package/game_package.json): every path it lists exists after `setup.py`.

The bundle is built by the platform from this folder; a path the contract forgets is missing at run time (the DMD
slides and media_data.json were, once). Generated paths are only required once setup has made them."""
import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT = os.path.join(ROOT, "scripts", "package", "game_package.json")
BUILT = os.path.join(ROOT, "game", "config", "rom")        # made by gen_config.py (tests rerun it, so check slides too)
SLIDES = os.path.join(ROOT, "game", "slides", "deffs")


def ignored(rel):
    return subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0


class PackageContract(unittest.TestCase):
    def setUp(self):
        with open(CONTRACT, encoding="utf-8") as f:
            self.contract = json.load(f)

    def test_identity(self):
        self.assertTrue(self.contract["id"])
        self.assertIn("mpf-gmc", self.contract["platform_addons"])

    def test_generated_files_are_listed(self):
        """The generated, git-ignored files the game reads at run time must be in `copy`: git ls-files does not see them."""
        for rel in ("game/config/rom", "game/sounds", "game/media", "game/fonts", "game/slides/deffs",
                    "game/tf/media_data.json"):
            self.assertIn(rel, self.contract["copy"])

    def test_pack_and_cabinet_data_stay_out(self):
        for rel in ("pup_pack", "pup_media", "game/data", "game/pup.local.cfg"):
            self.assertIn(rel, self.contract["never"])
        self.assertTrue(self.contract["pup"]["install"])
        self.assertFalse([p for p in self.contract["copy"] if "pup_pack" in p or p.endswith(".bin")])

    def test_listed_paths_exist(self):
        if not os.path.isdir(SLIDES):
            self.skipTest("the game was not built (python scripts/setup.py)")
        missing = [rel for rel in self.contract["copy"] if not os.path.exists(os.path.join(ROOT, rel))]
        self.assertEqual(missing, [])

    def test_tracked_paths_exist(self):
        """Paths that git tracks are in the checkout whatever the build state."""
        for rel in self.contract["copy"]:
            if not ignored(rel):
                self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)


if __name__ == "__main__":
    unittest.main()
