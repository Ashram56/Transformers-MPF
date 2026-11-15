"""The operator adjustments: every one of the ROM's 98 (rom/rom_data/settings/adjustments.csv) is either shown by a
bench test to change the game, or listed here with the reason it has no test (docs/test_bench.md "Adjustments").

COVERAGE maps each adjustment to the test that proves its effect ("module::Class::test"), or to one of:
- ROM_UNUSED: the ROM's game code never reads it (code: no reader in rom/code/tf_decompiled.c);
- NOT_MODELLED: the ROM reads it and the game does not yet (a row in docs/rom_differences.md);
- MACHINE: it sets the cabinet, the pricing, the sound or the high-score tables, not the rules; the bench does not
  cover it.
test_every_adjustment_is_accounted_for fails when an adjustment is missing or when a named test does not exist, so
a new rule that reads an adjustment has to come with its test."""
import csv
import importlib
import os

from tests.bench.driver import BenchCase

ROM_UNUSED, NOT_MODELLED, MACHINE = "rom unused", "not modelled", "machine"
FLOW, FEAT, MEG, OPT, WIZ, BAT, ADJ = ("test_game_flow", "test_features", "test_megatron", "test_optimus",
                                       "test_wizard", "test_battles", "test_adjustments")
TIMERS = BAT + "::TestBattleEnds::test_timer_adjustments"

COVERAGE = {
    1: ROM_UNUSED, 2: MACHINE, 3: MACHINE, 4: MACHINE, 5: ROM_UNUSED, 6: ROM_UNUSED, 7: MACHINE, 8: ROM_UNUSED,
    9: ROM_UNUSED, 10: MACHINE,
    11: ADJ + "::TestReplay::test_adj_11_13_15_auto_replay", 12: MACHINE,
    13: ADJ + "::TestReplay::test_adj_11_13_15_auto_replay", 14: ADJ + "::TestReplay::test_adj_14_17_fixed_levels",
    15: ADJ + "::TestReplay::test_adj_11_13_15_auto_replay", 16: MACHINE,
    17: ADJ + "::TestReplay::test_adj_14_17_fixed_levels", 18: ADJ + "::TestReplay::test_adj_14_17_fixed_levels",
    19: MACHINE, 20: MACHINE, 21: MACHINE,
    22: FLOW + "::TestSpecial::test_adj_22_special_limit", 23: FLOW + "::TestSpecial::test_adj_23_special_award",
    24: ROM_UNUSED, 25: ROM_UNUSED, 26: FLOW + "::TestExtraBall::test_adj_26_extra_ball_limit", 27: ROM_UNUSED,
    28: MACHINE, 29: MACHINE, 30: MACHINE,
    31: FLOW + "::TestBalls::test_adj_31_balls_per_game", 32: FLOW + "::TestTilt::test_adj_32_tilt_warnings",
    33: MACHINE, 34: ADJ + "::TestMachine::test_adj_34_free_play", 35: MACHINE,
    36: FLOW + "::TestGameOver::test_adj_36_game_restart", 37: ROM_UNUSED,
    38: FLOW + "::TestBalls::test_adj_38_ball_save_time", 39: FLOW + "::TestBalls::test_adj_39_timed_plunger",
    40: FLOW + "::TestBalls::test_adj_40_flipper_ball_launch",
    41: ADJ + "::TestMachine::test_adj_41_coin_door_ball_saver",
    42: FLOW + "::TestSide::test_adj_42_competition_mode", 43: ROM_UNUSED, 44: MACHINE, 45: ROM_UNUSED,
    46: NOT_MODELLED, 47: ROM_UNUSED,
    48: MACHINE, 49: MACHINE, 50: MACHINE, 51: MACHINE, 52: MACHINE, 53: MACHINE, 54: MACHINE, 55: MACHINE,
    56: MACHINE, 57: MACHINE, 58: MACHINE, 59: MACHINE, 60: MACHINE, 61: MACHINE, 62: MACHINE,
    63: ADJ + "::TestMachine::test_adj_63_lost_ball_recovery",
    64: FLOW + "::TestTilt::test_adj_64_coin_door_disables_the_tilt",
    65: FLOW + "::TestSide::test_adj_65_transformers_select",
    66: BAT + "::TestModeStartDifficulty::test_adj_66_sets_the_lit_shots",
    67: OPT + "::TestOptimusAdjustments::test_adj_67_sets_the_hits",
    68: MEG + "::TestLockDifficulty::test_adj_68_needs_energon_sets",
    69: MEG + "::TestVirtualLock::test_adj_69_keeps_no_ball",
    70: FEAT + "::TestBumblebee::test_adj_70_sets_the_first_letters", 71: ROM_UNUSED,
    72: TIMERS, 73: TIMERS, 74: TIMERS, 75: TIMERS, 76: ADJ + "::TestRules::test_adj_76_bumblebee_timer",
    77: TIMERS, 78: ADJ + "::TestRules::test_adj_78_mudflap_ball_save", 79: TIMERS,
    80: FEAT + "::TestBumblebee::test_adj_80_sets_the_time", 81: ADJ + "::TestRules::test_adj_81_fast_scoring_timer",
    82: FEAT + "::TestTwoBank::test_adj_82_sets_the_hits",
    83: FLOW + "::TestExtraBall::test_adj_83_wizard_requirements_light_the_extra_ball",
    84: ADJ + "::TestRules::test_adj_84_orbit_gate", 85: OPT + "::TestOptimusAdjustments::test_adj_85_stops_the_motor",
    86: WIZ + "::TestWizardMultiball::test_adj_86_resets_the_collected_requirements_each_ball",
    87: OPT + "::TestOptimusAdjustments::test_adj_87_keeps_the_progress",
    88: ADJ + "::TestRules::test_adj_88_megatron_memory",
    89: MEG + "::TestAutofireAfterLock::test_adj_89_no_leaves_the_ball_to_the_player",
    90: NOT_MODELLED, 91: NOT_MODELLED, 92: NOT_MODELLED, 93: NOT_MODELLED, 94: NOT_MODELLED, 95: NOT_MODELLED,
    96: ADJ + "::TestMachine::test_adj_96_shaker", 97: ROM_UNUSED, 98: ROM_UNUSED,
}


class TestCoverage(BenchCase):

    def test_every_adjustment_is_accounted_for(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "rom", "rom_data", "settings", "adjustments.csv")
        with open(path, newline="") as f:
            numbers = [int(row["adj"]) for row in csv.DictReader(f)]
        self.assertEqual(sorted(numbers), sorted(COVERAGE), "COVERAGE and the ROM's adjustments differ")
        for num, where in COVERAGE.items():
            if where in (ROM_UNUSED, NOT_MODELLED, MACHINE):
                continue
            module, cls, test = where.split("::")
            found = getattr(getattr(importlib.import_module("tests.bench." + module), cls, None), test, None)
            self.assertIsNotNone(found, "adjustment {}: no test {}".format(num, where))

    def test_the_menu_changes_what_the_rules_read(self):
        """An adjustment set the way the service menu sets it is what tf.adj gives the rules, and it is kept."""
        self.set_adj(72, 31)
        self.assertEqual(31, self.tf.adj[72])
        self.assertEqual(31, self.tf.adj_value(72))


class TestRules(BenchCase):

    def test_adj_76_bumblebee_timer(self):
        from tests.bench.driver import AUTOBOT
        self.tf.forced["side"] = [0] * 4
        self.SIDE = AUTOBOT
        self.set_adj(76, 22)
        self.start_game()
        self.assertEqual(22, self.start_battle("bb").seconds)

    def test_adj_78_mudflap_ball_save(self):
        """adj 78 MUDFLAP/SKIDS TIMER: the multiball's ball save lasts that many seconds."""
        saves = {}
        for value in (5, 30):
            self.set_adj(78, value)
            self.tf.forced["side"] = [0] * 4
            self.start_game()
            self.mark()
            self.start_battle("mf")
            saves[value] = [e["save_ticks"] for e in self.events("multiball_start")][-1]
            self.end_game()
        self.assertEqual(6, saves[30] // saves[5])

    def test_adj_81_fast_scoring_timer(self):
        ends = {}
        for value in (10, 25):
            self.set_adj(81, value)
            self.start_game()
            self.validate()
            for _ in range(30):
                if self.feature("twobank").running:
                    break
                self.shoot("bank_top")
            start = self.now
            for _ in range(80):
                if not self.feature("twobank").counting:
                    break
                self.wait(1)
            ends[value] = self.now - start
            self.end_game()
        self.assertAlmostEqual(15 * 66 * 0.01626, ends[25] - ends[10], delta=3)

    def test_adj_84_orbit_gate(self):
        """adj 84 DISABLE ORBIT CONTROL GATE [0x0102c0cc]: YES: the left orbit no longer opens the gate (coil 5)."""
        for value in (0, 1):
            with self.subTest(adj_84=value):
                self.set_adj(84, value)
                self.start_game()
                self.wait(3)
                self.mark()
                self.shoot("left_orbit")
                self.wait(2)
                self.assertEqual(not value, bool(self.events("coil", coil=5)))
                self.end_game()

    def test_adj_88_megatron_memory(self):
        """adj 88 SAVE MEGATRON PROGRESS [0x0100c200]: YES: the Autobot multiball goes on with the jackpots made
        in the previous one; NO: it starts over."""
        for value, kept in ((1, True), (0, False)):
            with self.subTest(adj_88=value):
                self.set_adj(88, value)
                self.set_adj(31, 5)
                self.tf.forced["side"] = [0] * 4
                self.start_game()
                side = self.start_megatron_multiball()
                self.wait(12)
                self.settle()
                self.lock()                                     # the jackpot, then two doubles
                self.shoot("left_ramp")
                self.shoot("right_ramp")
                made = side.jp
                self.assertGreaterEqual(made, 1)
                self.end_ball()
                self.plunge()
                side = self.start_megatron_multiball()
                self.assertEqual(made if kept else 0, side.jp)
                self.end_game()


class TestMachine(BenchCase):

    def test_adj_34_free_play(self):
        """adj 34 FREE PLAY: NO and no credit: the start button starts nothing."""
        self.tf.adj.override(34, 0)
        self.hit_and_release_switch("s_start_button")
        self.wait(3)
        self.assertIsNone(self.game)
        self.tf.adj.override(34, 1)
        self.hit_and_release_switch("s_start_button")
        self.wait(3)
        self.assertIsNotNone(self.game)

    def test_adj_46_is_not_in_the_service_menu(self):
        """Adj 46 PLAYER COMPETITION is hidden (tf/settings.py HIDDEN); the other standard adjustments stay."""
        listed = self.tf.adj.menu("standard")
        self.assertNotIn(46, listed)
        self.assertIn(45, listed)
        self.assertIn(47, listed)

    def test_adj_41_coin_door_ball_saver(self):
        """adj 41 COINDOOR BALL SAVER [0x0001ffac]: opening the door in play saves the ball that drains next."""
        for value, saved in ((0, False), (1, True)):
            with self.subTest(adj_41=value):
                self.set_adj(41, value)
                self.start_game()
                self.validate()
                self.wait_ball_save()
                self.sw("s_coin_door_open", 1)
                self.wait(1)
                self.drain(1)
                self.wait(8)
                self.sw("s_coin_door_open", 0)
                self.plunge()
                self.assertEqual(saved, self.game.player.ball == 1)
                self.end_game()

    def test_adj_63_lost_ball_recovery(self):
        """adj 63 LOST BALL RECOVERY [0x0001f79c]: the fifth ball search in a row serves a new ball (deff 13)."""
        for value, fed in ((1, True), (0, False)):
            with self.subTest(adj_63=value):
                self.set_adj(63, value)
                self.start_game()
                self.validate()
                self.mark()
                self.wait(130)                                  # nothing moves: five searches
                self.assertEqual(fed, 13 in self.deffs())
                self.drain(self.rolling())
                self.wait(5)
                self.end_game()

    def test_adj_96_shaker(self):
        """adj 96 SHAKER MOTOR: OFF: the shaker (coil 8) never runs; MAXIMAL: fast scoring's awards shake."""
        for value in (0, 3):
            with self.subTest(adj_96=value):
                self.set_adj(96, value)
                self.set_adj(82, 0)
                self.start_game()
                self.validate()
                self.mark()
                for _ in range(8):
                    self.shoot("bank_top")
                self.wait(8)
                self.shoot("sling_left")
                self.shoot("sling_right")
                self.wait(1)
                self.assertEqual(bool(value), bool(self.events("coil", coil=8)))
                self.end_game()


class TestReplay(BenchCase):

    def add_points(self, points):
        self.tf.score_add(points)
        self.wait(2)

    def test_adj_11_13_15_auto_replay(self):
        """adj 11 REPLAY TYPE AUTO: a replay at each multiple of adj 15; adj 13 REPLAY AWARD: EXTRA BALL gives one
        (audit 10 counts the first level)."""
        self.set_adj(11, 3)
        self.set_adj(13, 3)
        self.set_adj(14, 2)
        self.set_adj(15, 5000000)
        self.start_game()
        self.validate()
        self.mark()
        self.add_points(4000000)
        self.assertNotIn(10, self.audits())
        self.add_points(1500000)
        self.assertIn(10, self.audits())
        self.assertEqual(1, self.game.player.extra_balls)
        self.add_points(5000000)
        self.assertIn(11, self.audits())

    def test_adj_14_17_fixed_levels(self):
        """adj 11 FIXED with adj 14 REPLAY LEVELS = 2: replays at adj 17 and adj 18 only."""
        self.set_adj(11, 1)
        self.set_adj(13, 3)
        self.set_adj(14, 2)
        self.set_adj(17, 6000000)
        self.set_adj(18, 9000000)
        self.set_adj(19, 10000000)
        self.start_game()
        self.validate()
        self.mark()
        self.add_points(6500000)
        self.assertEqual([10], [a for a in self.audits() if a in (10, 11, 12, 13)])
        self.add_points(3000000)
        self.assertEqual([10, 11], [a for a in self.audits() if a in (10, 11, 12, 13)])
        self.add_points(3000000)
        self.assertEqual([10, 11], [a for a in self.audits() if a in (10, 11, 12, 13)])
