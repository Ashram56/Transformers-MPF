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
        draw = extra["draw"]
        # deff 19's capture: panel score (font 0, right edge 38, row 5), score (font 26 at 84, 21), bottom row
        self.assertEqual({"t": "00", "f": 0, "x": 38, "y": 5, "a": 4}, draw[0])
        self.assertEqual({"r": [40, 0, 1, 32]}, {k: v for k, v in draw[1].items() if k == "r"})
        self.assertEqual({"t": "00", "f": 26, "x": 84, "y": 21, "a": 2}, draw[2])
        self.assertEqual(["BALL 1", "FREE PLAY"], [d["t"] for d in draw[3:]])
        two = score_screen.score_draw([1234560, 0], 2, 3, "CREDITS 2")
        self.assertEqual(["1,234,560", "00", "00", "BALL 3", "CREDITS 2"], [d["t"] for d in two if "t" in d])
        self.assertEqual([5, 21], [d["y"] for d in two[:2]])        # player 2 of 2 on row 21

    def test_replay_row_alternates(self):
        from tf import score_screen
        self.assertFalse(score_screen.replay_phase(155))
        self.assertTrue(score_screen.replay_phase(156))
        self.assertTrue(score_screen.replay_phase(156 + 311))
        self.assertFalse(score_screen.replay_phase(156 + 312))
        self.assertTrue(score_screen.replay_phase(156 + 312 + 1250))
        draw = score_screen.score_draw([0], 1, 1, "CREDITS 0", "REPLAY AT 20,000,000", 200)
        self.assertEqual({"t": "REPLAY AT 20,000,000", "f": 0, "x": 84, "y": 30, "a": 2}, draw[-1])


@unittest.skipUnless(os.path.exists(FONTS), "fonts not generated (scripts/gen_media.py)")
class TestFonts(unittest.TestCase):

    def test_font_table(self):
        with open(FONTS, encoding="utf-8") as f:
            fonts = {font["id"]: font for font in json.load(f)["fonts"]}
        self.assertEqual(27, len(fonts))                       # tf_180 font table, file 0x123478
        self.assertEqual(",0123456789", "".join(sorted(fonts[23]["glyphs"])))
        self.assertEqual(18, fonts[23]["height"])


class TestDeffValues(unittest.TestCase):
    """Captured printf texts drawn live (scripts/gen_media.py value_texts, tf/deff_values.gd)."""

    def test_format_values(self):
        from tf.media_bridge import format_values
        self.assertEqual(["3,170"], format_values(["%,02lu"], [3170]))
        self.assertEqual(["2", "TICKETS"], format_values(["%u", "TICKET%P1//S/%"], [2]))
        self.assertEqual(["1", "TICKET"], format_values(["%u", "TICKET%P1//S/%"], [1]))
        self.assertEqual([None], format_values(["%,02lu"], []))
