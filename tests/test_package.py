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
        for rel in ("pup_pack", "game/data", "game/pup.local.cfg", "game/options.json"):
            self.assertIn(rel, self.contract["never"])
        self.assertTrue(self.contract["pup"]["install"])
        self.assertFalse([p for p in self.contract["copy"] if "pup_pack" in p or p.endswith(".bin")])

    def test_platform_rules(self):
        """MPF-Godot-Packaging platforms/game-bundles.md: the page's settings tool, a start check (rule 9), the board's Godot
        arguments taken (rule 6), the pack only unpacked on the machine and its media made at the build (rules 12, 13)."""
        run = self.contract["run"]
        self.assertEqual(run["start"], "python3 scripts/package/start.py")
        self.assertTrue(run["game_args"])
        self.assertEqual(run["check"], "python3 scripts/package/check.py")
        self.assertEqual(self.contract["options"]["tool"], "scripts/package/bundle_options.py")
        self.assertTrue(self.contract["pup"]["extract_only"])
        self.assertIn("pup_media/tf_180", self.contract["copy"])
        self.assertNotIn("pup_media", self.contract["keep_on_update"])      # a new version brings its own (rule 13)
        for rel in [run["start"].split()[1], run["check"].split()[1], self.contract["options"]["tool"],
                    self.contract["pup"]["install"].split()[1], self.contract["monitor"]["layout"], self.contract["monitor"]["image"]]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)

    def test_listed_paths_exist(self):
        if not os.path.isdir(SLIDES):
            self.skipTest("the game was not built (python scripts/setup.py)")
        missing = [rel for rel in self.contract["copy"] if rel not in self.contract.get("optional", [])
                   and not os.path.exists(os.path.join(ROOT, rel))]
        self.assertEqual(missing, [])

    def test_tracked_paths_exist(self):
        """Paths that git tracks are in the checkout whatever the build state."""
        for rel in self.contract["copy"]:
            if not ignored(rel):
                self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)


class Settings(unittest.TestCase):
    """scripts/package/bundle_options.py, the settings tool the platform's page runs (list, get, set, unset)."""

    def setUp(self):
        import sys
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "scripts", "package"))
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import bundle_options
        self.bo = bundle_options
        self.tmp = tempfile.TemporaryDirectory()
        self.game = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_is_the_page_format(self):
        """The page draws groups, then bool/choice/other fields; the first-run default sets pup.enabled."""
        schema = self.bo.load_schema()
        groups = {g["id"] for g in schema["groups"]}
        for o in schema["options"]:
            self.assertIn(o["group"], groups, o["id"])
            self.assertTrue(o["label"])
            self.assertIn(o["type"], ("bool", "choice", "integer", "size"))
            self.assertEqual(self.bo.convert(o, o["default"]), o["default"])
        self.assertIn("pup.enabled", self.bo.by_id(schema))

    def test_round_trip(self):
        bo, game = self.bo, self.game
        with open(os.path.join(game, "pup.local.cfg"), "w", encoding="utf-8") as f:
            f.write("; my cabinet\n[dmd]\nscreen=1\n")
        bo.set_values({"free_play": "false", "dmd_size": "512x128", "pup.enabled": "true", "pup.topper.screen": "2"}, game)
        self.assertEqual(bo.get_values(game=game), {"free_play": False, "dmd_size": "512x128", "pup.enabled": True,
                                                     "pup.dmd.screen": 1, "pup.topper.screen": 2})
        self.assertEqual(bo.run_args(game), ["--no-free-play", "--dmd-size", "512x128"])
        with open(os.path.join(game, "pup.local.cfg"), encoding="utf-8") as f:
            self.assertIn("; my cabinet", f.read())
        bo.set_values({"pup.layout": "fullscreen"}, game)
        cfg = open(os.path.join(game, "pup.local.cfg"), encoding="utf-8").read()
        self.assertIn('layout="manual"', cfg)
        self.assertEqual(bo.get_values(["pup.layout"], game), {"pup.layout": "fullscreen"})
        self.assertEqual([bo.cfg_read(os.path.join(game, "pup.local.cfg"), s, k) for s, k in
                          (("backglass", "fullscreen"), ("dmd", "fullscreen"), ("dmd", "screen"))], ["true", "true", "1"])   # screen 1 kept
        bo.set_values({"pup.layout": "stack"}, game)
        self.assertEqual(bo.cfg_read(os.path.join(game, "pup.local.cfg"), "pup", "layout"), '"stack"')
        bo.unset_values(["pup.layout"], game)
        bo.unset_values(["free_play", "pup.enabled"], game)
        self.assertEqual(sorted(bo.get_values(game=game)), ["dmd_size", "pup.dmd.screen", "pup.topper.screen"])
        for oid, bad in (("pup.video_volume", "200"), ("pup.layout", "manual"), ("dmd_size", "big"), ("nope", "1")):
            with self.assertRaises(bo.OptionError):
                bo.set_values({oid: bad}, game)

    def test_start_merges_saved_and_given(self):
        import start
        self.assertEqual(start.merge(["--no-free-play", "--dmd-size", "512x128"], ["--free-play", "--", "--dmd-size"]),
                         ["--dmd-size", "512x128", "--free-play", "--", "--dmd-size"])
        self.assertEqual(start.merge(["--dmd-size", "512x128"], ["--", "--rendering-driver", "opengl3"]),
                         ["--dmd-size", "512x128", "--", "--rendering-driver", "opengl3"])

    def test_check_passes_on_a_built_game(self):
        if not os.path.isdir(SLIDES):
            self.skipTest("the game was not built (python scripts/setup.py)")
        import sys
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "package", "check.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
