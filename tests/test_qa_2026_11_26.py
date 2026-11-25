"""Regression tests for the findings of the QA pass of 2026-11-26 (the MPF conversion against the ROM code,
docs/qa/README.md): each asserts the ROM's behaviour at the address cited."""
import glob
import os
import sys
import unittest

from tests.tf_test import TfTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "game") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "game"))
from tf import lamps, media_bridge, score_screen  # noqa: E402


class TestConversionPure(unittest.TestCase):
    def test_leff_shows_light_lamps(self):
        """The packaged shows write "ffffff"; parse_show must read them (QA L-G01): leff 1 lights lamps."""
        steps = lamps.parse_show(os.path.join(ROOT, "rom/mpf_package/config/shows/lampfx_001.yaml"))
        self.assertTrue(any(v != lamps.BLACK for s in steps for v in s[1].values()))
        shows = glob.glob(os.path.join(ROOT, "rom/mpf_package/config/shows/lampfx_*.yaml"))
        with_lamps = sum(1 for f in shows if any(s[1] for s in lamps.parse_show(f)))
        self.assertGreater(with_lamps, 40)

    def test_flash_phase_is_ten_ticks(self):
        """lamp_compositor_tick [0x000073cc]: the flash phase flips every 10 ticks (QA L-G02)."""
        self.assertEqual(10, lamps.FLASH_TICKS)

    def test_plural_pick(self):
        """vsprintf [0x0002fef0] %P1//S/%: choice n-1 clamped to the last (deff_044 op list "0 COMBOS")."""
        f = media_bridge.format_rom_text
        self.assertEqual("0 COMBOS", f("%d COMBO%P1//S/%", [0]))
        self.assertEqual("1 COMBO", f("%d COMBO%P1//S/%", [1]))
        self.assertEqual("SHOOT 11 SHOTS", f("SHOOT %u SHOT%P1//S/%", [11]))
        self.assertEqual("2ND", f("%P1/1ST/2ND/3RD/4TH/5TH//%", [], [2]))

    def test_score_font_by_value(self):
        """table 0x040c75d0 [0x0102f11c]: 1,500,000 is drawn in font 17 on row 18 (QA V-SC1)."""
        self.assertEqual((17, 18), next(e[1:] for e in score_screen.SCORE_TABLE if 1500000 >= e[0]))
        self.assertEqual((26, 21), next(e[1:] for e in score_screen.SCORE_TABLE if 0 >= e[0]))
        self.assertEqual((22, 18), next(e[1:] for e in score_screen.SCORE_TABLE if 123456789 >= e[0]))


class TestConversionGame(TfTestCase):
    def test_battle_hit_sound_once(self):
        """deff_094 [0x010189a8] plays snd_play2(0x181, ..) once per hit (QA SC1)."""
        os_ = self.tf
        os_.display.own_sounds.add((94, 0x181))
        info = os_.display.media.get(94)
        if info is None or not any(c == 0x181 for _, c in info.sounds):
            self.skipTest("deff 94 op list has no 0x181")
        before = len([e for e in os_.trace.of("sound") if e.get("call") == 0x181])
        os_.display.fg = 94
        os_.display._media(94)
        self.advance_time_and_run(1)
        after = len([e for e in os_.trace.of("sound") if e.get("call") == 0x181])
        self.assertEqual(before, after)
