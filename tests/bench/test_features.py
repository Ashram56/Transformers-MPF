"""The scoring features outside the battles and multiballs: Energon and the twelve Allspark awards, extra ball
and special, pop bumpers, spinner, Bumblebee letters and double scoring, the 2-bank and fast scoring, lanes,
skill shots, combos and shot multipliers, bonus (rom/rules/modes/allspark_and_energon.md, scoring_features.md,
combos_and_multipliers.md, game_flow.md)."""
from tests.bench.driver import AUTOBOT, BenchCase


class FeatureCase(BenchCase):

    def points(self):
        return [e["points"] for e in self.events("score_add")]

    def allspark(self, item):
        """Bank an Allspark and collect award `item` (1-12) at the left eject."""
        self.tf.forced["allspark"] = [item - 1]
        self.pd.allspark_lit = self.pd.get("allspark_lit", 0) + 1
        self.mark()
        self.eject()
        self.assertIn(74 + item, self.audits(), "Allspark award {} was not given".format(item))
        self.wait(6)
        self.settle()

    def bonus(self):
        """Drain and return the bonus added at the end of the ball."""
        player = self.game.player
        before = player.score
        self.mark()
        self.end_ball()
        return player.score - before


class TestEnergon(FeatureCase):

    def test_three_targets_bank_an_allspark(self):
        """5.1: an unlit target 75,000 (deff 124), a lit one 10,000, the third 250,000 + 25,000 x sets (deff
        125): one Allspark banked, the targets unlit."""
        self.start_game()
        self.mark()
        self.shoot("energon_left")
        self.shoot("energon_left")
        self.shoot("energon_center")
        self.assertEqual(3, self.pd.energon_lit)
        self.shoot("energon_right")
        got = self.points()
        for value in (75000, 10000, 250000):
            self.assertIn(value, got)
        self.assertEqual(2, got.count(75000))
        self.assertIn(125, self.deffs())
        self.assertEqual((0, 1, 1), (self.pd.energon_lit, self.pd.energon_sets, self.pd.allspark_lit))
        self.wait(3)
        self.mark()
        self.complete_energon()
        self.assertIn(275000, self.points())
        self.assertEqual(2, self.pd.allspark_lit)

    def test_nothing_lights_during_a_multiball(self):
        self.start_game()
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        lit = self.pd.energon_lit
        self.mark()
        self.shoot("energon_left")
        self.assertIn(5000, self.points())
        self.assertEqual(lit, self.pd.energon_lit)


class TestAllsparkAwards(FeatureCase):

    def test_the_allspark_spends_one_banked_award(self):
        self.start_game()
        self.complete_energon()
        self.wait(3)
        self.tf.forced["allspark"] = [2]
        self.mark()
        self.eject()
        self.assertIn(52, self.deffs())
        self.assertIn(200000, self.points())                        # item 3: 200,000
        self.assertEqual(0, self.pd.allspark_lit)
        self.mark()
        self.eject()                                                # none banked: no award
        self.assertNotIn(52, self.deffs())

    def test_special_is_lit_then_collected_at_the_right_orbit(self):
        """Item 1 [0x01008528]: the SPECIAL insert; the right orbit collects it [0x01008684]: adj 23 CREDIT."""
        self.start_game()
        self.allspark(1)
        self.assertIn(55, self.deffs())
        self.assertEqual(1, self.tf.specials_lit[0])
        credits = self.tf.credit_model.credits if hasattr(self.tf.credit_model, "credits") else None
        self.mark()
        self.shoot("right_orbit")
        self.assertEqual(0, self.tf.specials_lit[0])
        self.assertIn(0x0e, self.audits())
        self.assertIn(56, self.deffs())
        if credits is not None:
            self.assertEqual(credits + 1, self.tf.credit_model.credits)
        self.mark()
        self.wait(4)
        self.shoot("right_orbit")
        self.assertNotIn(0x0e, self.audits())

    def test_extra_ball_is_lit_then_collected_at_the_right_orbit(self):
        """Item 2 [0x01007b40]: deff 53; the right orbit collects it [0x01007b74]: the same player shoots again."""
        self.start_game(players=2)
        self.allspark(2)
        self.assertIn(53, self.deffs())
        self.assertEqual(1, self.tf.eb_lit[0])
        self.mark()
        self.shoot("right_orbit")
        self.assertEqual(0, self.tf.eb_lit[0])
        self.assertEqual(1, self.game.player.extra_balls)
        self.assertIn(54, self.deffs())
        self.assertIn(9, self.audits())
        self.end_ball()
        self.assertEqual((1, 1), (self.game.player.number, self.game.player.ball))
        self.assertTrue(self.tf.shoot_again)
        self.plunge()
        self.end_ball()
        self.assertEqual(2, self.game.player.number)

    def test_bonus_multiplier_and_holds(self):
        """Items 4, 8, 9: bonus X + 1; BONUS HOLD keeps the bonus for the next ball [0x01000f68]; BONUS X HOLD
        keeps the multiplier."""
        self.start_game()
        self.allspark(4)
        self.assertEqual(2, self.pd.bonus_x)
        self.allspark(8)
        self.assertTrue(self.tf.flag(0x4b))
        self.allspark(9)
        self.assertTrue(self.tf.flag(0x4a))
        self.validate()
        count = self.pd.bonus_count
        first = self.bonus()
        self.assertEqual((670 * count + 125000) * 2, first)
        self.plunge()
        self.assertEqual(2, self.pd.bonus_x)
        self.assertEqual(670 * count + 125000, self.pd.bonus_held)
        self.validate()
        count2 = self.pd.bonus_count
        self.assertEqual((670 * count2 + 670 * count + 125000) * 2, self.bonus())

    def test_add_a_ball_only_in_a_multiball_and_once(self):
        """Item 5: offered (and then certain) only while a multiball runs and flag 0x14 is clear."""
        self.start_game()
        allspark = self.feature("allspark")
        self.assertEqual(0, allspark.weights()[4])
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        self.wait_ball_save()
        self.drain(2)
        self.wait(3)
        self.settle()
        self.assertEqual(2, self.game.balls_in_play)
        self.assertGreaterEqual(allspark.weights()[4], 1000)
        self.pd.allspark_lit = 1
        self.mark()
        self.eject()
        self.assertIn(74 + 5, self.audits())
        self.wait(10)
        self.settle()
        self.assertEqual(3, self.game.balls_in_play)
        self.assertTrue(self.tf.flag(0x14))
        self.assertEqual(0, allspark.weights()[4])
        self.check()

    def test_add_a_ball_is_offered_again_on_the_next_ball(self):
        """Flag 0x14 is reset at each ball start (rom_data/io/game_flags.csv: attribute 5)."""
        self.start_game()
        self.tf.flag_set(0x14)
        self.end_ball()
        self.plunge()
        self.assertFalse(self.tf.flag(0x14))

    def test_add_more_time_only_in_a_timed_mode(self):
        """Item 6: only while a timed mode runs: the battle's timer gets its adjustment's seconds again."""
        self.start_game()
        allspark = self.feature("allspark")
        self.assertEqual(0, allspark.weights()[5])
        battle = self.start_battle("ss")
        self.wait(12)
        self.assertGreaterEqual(allspark.weights()[5], 1000)
        before = battle.seconds
        self.pd.allspark_lit = 1
        self.mark()
        self.eject()
        self.assertIn(74 + 6, self.audits())
        self.assertGreater(battle.seconds, before)
        self.assertEqual(0, allspark.weights()[5])

    def test_pops_score_and_super_pops(self):
        """Items 7 and 12: the pop base grows; super pop bumpers score 50,000 a hit."""
        self.start_game()
        base = self.pd.get("pop_base", 3000)
        self.allspark(7)
        self.assertGreater(self.pd.pop_base, base)
        self.allspark(12)
        self.assertTrue(self.pd.super_pops)
        self.mark()
        self.shoot("pop_top")
        self.wait(1)
        self.assertIn(50000, self.points())

    def test_super_spinner(self):
        """Item 11: each spin scores 50,000 while flag 0x4c is set."""
        self.start_game()
        self.allspark(11)
        self.assertTrue(self.pd.super_spinner)
        self.mark()
        self.shoot("spinner")
        self.wait(1)
        self.assertIn(50000, self.points())

    def test_shot_multipliers_double_the_shot_that_takes_them(self):
        """Item 10 + [0x010237ac]: the next main shot goes to 2X first, so its own award is already doubled."""
        self.start_game()
        self.allspark(10)
        self.assertTrue(self.pd.get("mult_lit"))
        lit = next(i for i in (2, 3, 1, 4) if self.pd.ms_lit & (1 << i))
        name = {1: "left_orbit", 2: "left_ramp", 3: "right_ramp", 4: "right_orbit"}[lit]
        self.mark()
        self.shoot(name)
        self.assertIn(50, self.deffs())
        self.assertIn(2 * 10000, self.points())                     # the first mode-start hit, doubled
        self.assertNotIn(10000, self.points())


class TestPopsAndSpinner(FeatureCase):

    def test_pop_value_grows_and_falls_back(self):
        """4.1: 3,000 then + 1,000 a hit; back to the base 93 ticks after the last one."""
        self.start_game()
        self.mark()
        for _ in range(3):
            self.hit("s_top_pop_bumper" if "s_top_pop_bumper" in self.machine.switches else
                     self.switch_name(30), wait=0.2)
        got = [p for p in self.points() if p >= 3000]
        self.assertEqual([3000, 4000, 5000], got[:3])
        self.wait(3)
        self.mark()
        self.shoot("pop_top")
        self.wait(0.5)
        self.assertIn(3000, self.points())

    def test_spinner(self):
        """4.2: 2,500 a spin."""
        self.start_game()
        self.mark()
        for _ in range(4):
            self.hit(self.switch_name(34), wait=0.1)
        self.wait(1)
        self.assertEqual(4, self.points().count(2500))


class TestBumblebee(FeatureCase):

    def letters(self):
        return self.pd.bb_letters

    def test_letters_start_double_scoring(self):
        """4.3: adj 70 EASY starts with 2 letters; the ninth starts double scoring for adj 80 counts: every
        score x 2, then back to 1."""
        self.set_adj(80, 10)
        self.start_game()
        self.validate()                                             # the countdown holds until the playfield is valid
        self.assertEqual(2, self.letters())
        self.mark()
        for n in range(2, 9):
            self.shoot("bumblebee")
            self.assertIn(10000 + 5000 * n, self.points())
        self.assertEqual(2, self.tf.pf_mult)
        self.assertIn(105, self.audits())
        self.wait(6)
        self.mark()
        before = self.score
        self.shoot("energon_left")
        self.assertEqual(2 * (75000 + 1110), self.score - before)   # the target and its switch, x 2
        self.wait(25)
        self.assertEqual(1, self.tf.pf_mult)
        self.assertEqual(1, self.letters())                         # the next word starts at 1
        self.settle()
        self.check()

    def test_adj_70_sets_the_first_letters(self):
        for value, letters in ((0, 2), (1, 1), (2, 0)):
            with self.subTest(adj_70=value):
                self.set_adj(70, value)
                self.start_game()
                self.assertEqual(letters, self.letters())
                self.end_game()

    def test_adj_80_sets_the_time(self):
        """adj 80 DOUBLE SCORING TIMER: 10 counts end before 30 do."""
        ends = {}
        for value in (10, 30):
            self.set_adj(80, value)
            self.start_game()
            self.validate()
            for _ in range(7):
                self.shoot("bumblebee")
            self.assertEqual(2, self.tf.pf_mult)
            start = self.now
            for _ in range(60):
                if self.tf.pf_mult == 1:
                    break
                self.wait(1)
            ends[value] = self.now - start
            self.end_game()
        self.assertAlmostEqual(20 * 66 * 0.01626, ends[30] - ends[10], delta=3)

    def test_a_drain_ends_double_scoring(self):
        self.start_game()
        for _ in range(7):
            self.shoot("bumblebee")
        self.assertEqual(2, self.tf.pf_mult)
        self.end_ball()
        self.plunge()
        self.check_fresh_ball()


class TestTwoBank(FeatureCase):

    def start_fast(self):
        for _ in range(30):
            if self.feature("twobank").running:
                return
            self.shoot("bank_top")
        self.fail("fast scoring did not start")

    def test_fast_scoring(self):
        """4.4: adj 82 EASY: 7 hits make it ready (75,000 each), the next starts it: 100,000, audit 106; every
        switch scores the fast value; it ends after adj 81 counts and the next needs 9 hits."""
        self.set_adj(81, 10)
        self.start_game()
        self.validate()
        self.assertEqual(7, self.pd.twobank_left)
        self.mark()
        for n in range(7):
            self.shoot("bank_top")
        self.assertEqual(7, self.points().count(75000))
        self.assertEqual(0, self.pd.twobank_left)
        self.assertIn(131, self.deffs())
        self.shoot("bank_top")
        self.assertTrue(self.feature("twobank").running)
        self.assertIn(106, self.audits())
        self.assertIn(100000, self.points())
        self.assertEqual(9, self.pd.twobank_left)
        self.wait(8)
        self.mark()
        self.shoot("sling_left")
        self.assertIn(10000, self.points())
        self.wait(30)
        self.assertFalse(self.feature("twobank").running)
        self.assertIn(137, self.deffs())
        self.settle()
        self.check()

    def test_adj_82_sets_the_hits(self):
        """adj 82 [0x0102e8f8]: the first fast scoring needs 5 + 2 x level hits, at most 12."""
        for value, hits in ((0, 5), (1, 7), (2, 9), (3, 11), (4, 12)):
            with self.subTest(adj_82=value):
                self.set_adj(82, value)
                self.start_game()
                self.assertEqual(hits, self.pd.twobank_left)
                self.end_game()

    def test_a_drain_ends_fast_scoring(self):
        self.start_game()
        self.start_fast()
        self.end_ball()
        self.plunge()
        self.check_fresh_ball()


class TestLanes(FeatureCase):

    def test_own_lanes_light_the_multipliers_the_others_add_bonus_x(self):
        """5: Decepticon: the four Megatron lanes light the shot multipliers (deff 44), the four Optimus lanes
        add 1 to the bonus multiplier (deff 45)."""
        self.start_game()
        self.wait(3)
        self.mark()
        for name in ("top_lane_left", "top_lane_left", "outlane_left", "return_left"):
            self.shoot(name)
            if name == "outlane_left":
                self.wait(1)
        self.assertIn(10000, self.points())
        self.assertIn(44, self.deffs())
        self.assertTrue(self.pd.get("mult_lit"))
        self.mark()
        for name in ("top_lane_right", "top_lane_right", "return_right", "outlane_right"):
            self.shoot(name)
        self.assertIn(45, self.deffs())
        self.assertEqual(2, self.pd.bonus_x)


class TestSkillShots(FeatureCase):

    def test_the_own_top_lane_is_the_skill_shot(self):
        """5.1: Decepticon: the left top lane right after the plunge: 350,000 hands free, deff 42."""
        self.start_game(plunge=False)
        self.plunge(wait=0.5)
        self.mark()
        self.hit(self.switch_name(8))
        self.assertIn(350000, self.points())
        self.assertIn(42, self.deffs())

    def test_the_other_lane_cancels_it(self):
        self.start_game(plunge=False)
        self.plunge(wait=0.5)
        self.mark()
        self.hit(self.switch_name(7))
        self.hit(self.switch_name(8))
        self.assertNotIn(42, self.deffs())

    def test_the_back_door_is_the_super_skill_shot(self):
        self.start_game(plunge=False)
        self.plunge(wait=0.5)
        self.mark()
        self.hit(self.switch_name(13))
        self.wait(1)
        self.assertIn(500000, self.points())

    def test_autobot_lane(self):
        self.tf.forced["side"] = [0] * 4
        self.SIDE = AUTOBOT
        self.start_game(plunge=False)
        self.plunge(wait=0.5)
        self.mark()
        self.hit(self.switch_name(7))
        self.assertIn(350000, self.points())


class TestCombos(FeatureCase):

    def test_two_and_three_way(self):
        """4: a main shot opens the window; the next allowed one scores 100,000 + 25,000 x way (audit 154)."""
        self.start_game()
        self.wait(3)
        self.mark()
        self.shoot("left_ramp")
        self.shoot("right_ramp")
        self.assertIn(150000, self.points())
        self.shoot("left_ramp")
        self.assertIn(175000, self.points())
        self.assertEqual(2, self.audits().count(154))

    def test_the_window_closes(self):
        self.start_game()
        self.shoot("left_ramp")
        self.wait(9)
        self.mark()
        self.shoot("right_ramp")
        self.assertNotIn(154, self.audits())


class TestBonus(FeatureCase):

    def test_bonus_counts_the_switches(self):
        """7: (670 x switches + 125,000) x the multiplier, added after deff 25."""
        self.start_game()
        for name in ("sling_left", "sling_right", "bank_top", "energon_left"):
            self.shoot(name)
        count = self.pd.bonus_count
        self.assertGreaterEqual(count, 4)
        self.assertEqual(670 * count + 125000, self.bonus())
        self.assertIn(25, self.deffs())

    def test_no_bonus_on_a_tilted_ball(self):
        self.set_adj(32, 0)
        self.start_game()
        self.shoot("sling_left")
        self.hit("s_tilt_pendulum", wait=1)
        self.mark()
        before = self.score
        self.drain(self.rolling())
        self.wait(10)
        self.assertEqual(before, self.game.player_list[0].score)
        self.assertNotIn(25, self.deffs())
