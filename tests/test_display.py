"""The interim screens (tf/score_screen.py) drawn in the ROM's fonts: the score display (deff 19) and attract."""
import json
import os
import unittest

from tests.tf_test import GAME, TfTestCase

FONTS = os.path.join(GAME, "fonts", "fonts.json")


class TestScoreScreen(TfTestCase):

    def test_score_display_in_game(self):
        from tf import score_screen
        sent = []
        self.tf.media.text_show = lambda slide, lines, priority, **extra: sent.append((slide, priority, extra))
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        slide, priority, extra = sent[-1]
        self.assertEqual("rom_screen", slide)
        self.assertEqual(1, priority)                           # deff 19's ROM priority
        self.assertEqual(["00", "BALL 1", "FREE PLAY"], [d["t"] for d in extra["draw"]])
        two = score_screen.score_draw([1234560, 0], 2, 3, "CREDITS 2")
        self.assertEqual(["1,234,560", "00", "BALL 3", "CREDITS 2"], [d["t"] for d in two])
        self.assertEqual([score_screen.SMALL, score_screen.MEDIUM], [d["f"] for d in two[:2]])


@unittest.skipUnless(os.path.exists(FONTS), "fonts not generated (scripts/gen_media.py)")
class TestFonts(unittest.TestCase):

    def test_font_table(self):
        with open(FONTS, encoding="utf-8") as f:
            fonts = {font["id"]: font for font in json.load(f)["fonts"]}
        self.assertEqual(27, len(fonts))                       # tf_180 font table, file 0x123478
        self.assertEqual(",0123456789", "".join(sorted(fonts[23]["glyphs"])))
        self.assertEqual(18, fonts[23]["height"])
