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
        before = len([e for e in os_.trace.of("sound") if e.get("call") == "0x181"])
        os_.display.fg = 94
        os_.display._media(94)
        self.advance_time_and_run(1)
        after = len([e for e in os_.trace.of("sound") if e.get("call") == "0x181"])
        self.assertEqual(before, after)


class TestMediumFixes(TfTestCase):
    def start(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)

    def sounds(self):
        return [int(e.get("call"), 16) for e in self.tf.trace.of("sound")]

    def test_ramp_entrance_sounds(self):
        """snd_play(0x273) [0x010337e8] / snd_play(0x272) [0x010338dc] on every hit (QA R-F1, SC5)."""
        self.start()
        n = (self.sounds().count(0x273), self.sounds().count(0x272))
        from tf.switches import SW
        self.hit_and_release_switch(SW[4])
        self.advance_time_and_run(0.2)
        self.hit_and_release_switch(SW[35])
        self.advance_time_and_run(0.2)
        self.assertEqual((n[0] + 1, n[1] + 1), (self.sounds().count(0x273), self.sounds().count(0x272)))

    def test_mode_start_sound_by_lit_battle(self):
        """deff 91 [0x01022608] plays 0x170 + the lit battle's bit position (QA R-F2, SC3)."""
        from tf.features import battles
        self.assertEqual(0x172, battles.MS_SOUND.get(4, 0x170))
        self.assertEqual(0x170, battles.MS_SOUND.get(1, 0x170))

    def test_validation_sets_flag_0x10(self):
        """Event 0x6a hook LAB_010060a4 sets game flag 0x10 (QA R-F4)."""
        self.start()
        self.tf._validate()
        self.assertTrue(self.tf.flag(0x10))

    def test_rule_order(self):
        """Multiballs above fast / double scoring above battles (QA V-ENG5, SC14)."""
        by_deff = {r[2]: r[0] for r in self.tf.display.rules}
        from tf.features import bumblebee, twobank, battles
        self.assertGreater(by_deff[bumblebee.DS_BG_DEFF], by_deff[twobank.FS_BG_DEFF])
        self.assertGreater(by_deff[twobank.FS_BG_DEFF], battles.RULE_PRIORITY)
        self.assertGreater(min(p for p in by_deff.values() if p >= 0x75), by_deff[bumblebee.DS_BG_DEFF])

    def test_percentage_audits_divide_by_paid_plays(self):
        """[0x00026c48] etc.: c9 x 100 / c17; SOFTWARE METER and RECENT REPLAY PERCENT are 0 (QA D-AUD)."""
        a = self.tf.audits
        for c, v in ((17, 10), (18, 10), (9, 6), (8, 30), (7, 40)):
            a.counts[c] = v
        self.assertEqual(60, a.value(16))
        self.assertEqual(0, a.value(13))
        self.assertEqual(0, a.value(72))
