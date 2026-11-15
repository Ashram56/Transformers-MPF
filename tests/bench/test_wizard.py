"""The wizard requirements, the side mode (All Hail Megatron / Autobots Roll Out) and the Wizard Multiball
(rom/rules/modes/wizard_modes.md): each one alone, and the whole road played shot by shot with no shortcut."""
from tests.bench.driver import AUTOBOT, BenchCase
from tests.bench.test_battles import LONG_TIMERS

WIZARD_SHOTS = ("eject", "left_orbit", "left_ramp", "center", "right_orbit", "right_ramp")    # wizard index


class TestSideMode(BenchCase):

    def qualify(self, reqs=range(0, 5)):
        self.start_game()
        self.poke_wizard(reqs)

    def test_starts_at_the_allspark(self):
        """[0x0100fff0]: own side's five completed: the Allspark starts it: 1,000,000, flags 0x3c and 0x3d, audit
        0x7e, requirement 10, the other side's first battle lit [0x01022dbc], the Optimus access restarted."""
        self.qualify()
        self.shoot("center")
        self.assertEqual(1, self.pd.opt_access)
        self.mark()
        self.eject()
        wizard = self.feature("wizard")
        self.assertTrue(wizard.side_running)
        self.assertTrue(self.tf.flag(0x3c) and self.tf.flag(0x3d))
        self.assertIn(0x7e, self.audits())
        self.assertIn(1000000, [e["points"] for e in self.events("score_add")])
        self.assertEqual([1, 1], wizard.reqs()[10])
        self.assertEqual(0x10, self.pd.battle_lit)
        self.assertEqual(0, self.pd.opt_access)
        self.assertTrue(self.tf.flag(0x48))
        self.check(settled=False)

    def test_autobot_side_lights_starscream(self):
        self.tf.forced["side"] = [0] * 4
        self.SIDE = AUTOBOT
        self.qualify(range(5, 10))
        self.eject()
        self.assertTrue(self.feature("wizard").side_running)
        self.assertEqual(0x01, self.pd.battle_lit)

    def test_shots_super_and_end(self):
        """Each shot twice: 500,000 + 50,000 x shots made; all twelve: the Allspark scores their sum and ends
        the mode (audit 0x80, total deff 85). It cannot start again (flag 0x3d)."""
        self.qualify()
        self.eject()
        wizard = self.feature("wizard")
        self.wait(8)
        self.mark()
        made = 0
        for name in WIZARD_SHOTS * 2:
            before = wizard.side_sum
            self.shoot_any(name)
            self.assertEqual(500000 + 50000 * made, wizard.side_sum - before, name)
            made += 1
        self.assertEqual(12, self.audits().count(0x7f))
        total = wizard.side_sum
        before = self.score
        self.shoot("left_ramp")                                     # made twice already: nothing from the mode
        self.assertEqual(total, wizard.side_sum)
        self.assertTrue(wizard.side_super_lit())
        self.eject()
        self.assertIn(0x80, self.audits())
        self.assertFalse(wizard.side_running)
        self.assertFalse(self.tf.flag(0x3c))
        self.assertGreaterEqual(self.score - before, total)
        self.wait(15)
        self.assertIn(85, self.deffs())
        self.eject()
        self.assertFalse(wizard.side_running)
        self.settle()
        self.check()

    def test_not_during_a_battle_or_a_multiball(self):
        """[0x0100ff80]: a timed battle or a multiball blocks the start."""
        self.start_game()
        self.start_battle()
        self.poke_wizard(range(0, 5))
        self.eject()
        self.assertFalse(self.feature("wizard").side_running)

    def test_a_drain_ends_it(self):
        self.qualify()
        self.eject()
        self.end_ball()
        self.assertFalse(self.feature("wizard").side_running)
        self.assertFalse(self.tf.flag(0x3c))
        self.assertTrue(self.tf.flag(0x3d))
        self.plunge()
        self.settle()
        self.check_fresh_ball()


class TestWizardMultiball(BenchCase):

    def start(self):
        self.start_game()
        self.poke_wizard(range(11))
        self.tf.flag_set(0x3d)
        self.mark()
        self.eject()
        wizard = self.feature("wizard")
        self.assertTrue(wizard.wmb_running)
        return wizard

    def test_start_resets_the_road(self):
        """[0x010363ec]: four balls, flag 0x3e, audit 0x97, 1,000,000; the wizard reset [0x01035ad0] clears the
        requirements and the battles and lights the side's first battle again [0x01022aa0]; flag 0x3d cleared."""
        self.start_game()
        self.start_battle()
        self.end_ball()
        self.plunge()
        self.assertEqual(0x01, self.pd.battle_started)
        self.poke_wizard(range(11))
        self.tf.flag_set(0x3d)
        self.mark()
        self.eject()
        wizard = self.feature("wizard")
        self.assertTrue(wizard.wmb_running and self.tf.flag(0x3e))
        self.assertFalse(self.tf.flag(0x3d))
        self.assertIn(0x97, self.audits())
        self.assertEqual([[0, 0]] * 11, wizard.reqs())
        self.assertEqual((0, 0), (self.pd.battle_started, self.pd.battle_completed))
        self.assertEqual(0x01, self.pd.battle_lit)
        self.wait(14)
        self.settle()
        self.assertEqual(4, self.game.balls_in_play)
        self.check()

    def test_shots_and_super(self):
        """Each shot three times: 500,000 + 50,000 x shots this round; all eighteen: the Allspark scores the
        sum (audit 0x99) and the round starts over."""
        wizard = self.start()
        self.wait(14)
        self.settle()
        made = 0
        for name in WIZARD_SHOTS * 3:
            before = wizard.wmb_sum
            self.shoot_any(name)
            self.assertEqual(500000 + 50000 * made, wizard.wmb_sum - before, name)
            made += 1
        total = wizard.wmb_sum
        before = self.score
        self.eject()
        self.assertIn(0x99, self.audits())
        self.assertGreaterEqual(self.score - before, total)
        self.assertEqual(([0] * 6, 0), (wizard.wmb_counts, wizard.wmb_sum))
        self.assertTrue(wizard.wmb_running)
        self.check(settled=False)

    def test_ends_with_one_ball_then_the_battles_start_again(self):
        wizard = self.start()
        self.wait(14)
        self.settle()
        self.wait_ball_save()
        self.drain(3)
        self.wait(8)
        self.assertFalse(wizard.wmb_running or wizard.wmb_alive)
        self.assertFalse(self.tf.flag(0x3e))
        self.assertIn(90, self.deffs())
        self.settle()
        self.check()
        self.assertEqual("ss", self.start_battle().key)             # the road starts over

    def test_a_timed_battle_does_not_block_it(self):
        """[0x010363b4]: only a multiball or the side mode blocks the start (not a timed battle)."""
        self.start_game()
        self.start_battle()
        self.poke_wizard(range(11))
        self.tf.flag_set(0x3d)
        self.eject()
        self.assertTrue(self.feature("wizard").wmb_running)

    def test_adj_86_resets_the_collected_requirements_each_ball(self):
        """adj 86 [0x010359d4]: YES clears the collected counts (the extra ball's road) at each ball start."""
        for value, kept in ((0, 1), (1, 0)):
            with self.subTest(adj_86=value):
                self.set_adj(86, value)
                self.start_game()
                self.start_battle()
                self.assertEqual(1, self.feature("wizard").reqs()[1][0])
                self.end_ball()
                self.plunge()
                self.assertEqual(kept, self.feature("wizard").reqs()[1][0])
                self.end_game()


class TestTheWholeRoad(BenchCase):
    """No poke: every requirement is played, on the Decepticon side then the Autobot battles the side mode opens."""
    ADJ = {**LONG_TIMERS, 31: 10}

    def battle(self, key):
        battle = self.start_battle()
        self.assertEqual(key, battle.key)
        self.complete_battle(battle)
        self.wait(14)
        self.settle()
        self.check()

    def test_from_the_first_ball_to_the_wizard_multiball(self):
        self.start_game()
        wizard = self.feature("wizard")
        for key in ("ss", "sw", "bo", "dv"):
            self.battle(key)
        self.assertEqual(0x0f, self.pd.battle_completed)
        # Megatron multiball up to its super jackpot
        side = self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        names = {"left_orbit": 1, "left_ramp": 2, "center": 3, "right_ramp": 4, "right_orbit": 5}
        for _ in range(60):
            if wizard.reqs()[0][1]:
                break
            if side.phase == 1:
                lit = [n for n, s in names.items() if side.mask & (1 << s)]
                self.shoot(lit[0]) if lit else self.lock()
            elif side.phase == 2:
                self.shoot("center")
            else:
                self.shoot("optimus")
        self.assertEqual([1, 1], wizard.reqs()[0][:2])
        self.wait_ball_save()
        self.drain(self.game.balls_in_play - 1)
        self.wait(10)
        self.settle()
        self.check()
        self.assertTrue(wizard.side_qualifies())
        # the side mode
        self.eject()
        self.assertTrue(wizard.side_running)
        self.wait(8)
        for name in WIZARD_SHOTS * 2:
            self.shoot_any(name)
        self.eject()
        self.assertFalse(wizard.side_running)
        self.wait(15)
        self.settle()
        self.assertEqual(0x10, self.pd.battle_lit)
        # the other side's battles
        for key in ("bb", "ih", "mf", "ra"):
            self.battle(key)
            if key == "mf":
                self.wait_ball_save()
                self.drain(self.game.balls_in_play - 1)
                self.wait(10)
                self.settle()
        self.assertEqual(0xff, self.pd.battle_completed)
        # Optimus multiball up to its super
        side = self.start_optimus_multiball()
        self.wait(12)
        self.settle()
        for _ in range(40):
            if wizard.reqs()[5][1]:
                break
            if side.phase == 1:
                lit = [n for i, n in enumerate(("eject", "left_orbit", "left_ramp", "center", "right_ramp",
                                               "right_orbit")) if side.lit & (1 << i)]
                self.shoot_any(lit[-1])
            else:
                self.shoot("optimus")
        self.assertTrue(wizard.all_done(), wizard.reqs())
        self.wait_ball_save()
        self.drain(self.game.balls_in_play - 1)
        self.wait(10)
        self.settle()
        self.check()
        # the wizard multiball
        self.eject()
        self.assertTrue(wizard.wmb_running)
        self.wait(14)
        self.settle()
        self.assertEqual(4, self.game.balls_in_play)
        self.check()
        self.end_game()
        self.check()
