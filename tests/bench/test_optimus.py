"""The center lane's Optimus access, the Optimus Prime battle and the two Optimus multiballs
(rom/rules/modes/optimus_multiball.md), with the adjustments 67, 85 and 87."""
from tests.bench.driver import AUTOBOT, BATTLE_SHOTS, BenchCase

NAMES = {name: shot for shot, name in BATTLE_SHOTS.items()}


class OptimusCase(BenchCase):

    def lit(self, side):
        return [name for shot, name in BATTLE_SHOTS.items() if shot < 6 and side.lit & (1 << shot)]


class TestOptimusDecepticon(OptimusCase):

    def test_access_battle_and_multiball(self):
        """Four center lanes (2,500 each, deff 141) start the battle (200,000, audit 0x6b); 2 x adj 67 + 1 hits
        on Optimus then 2,000,000 and the multiball: three balls, flags 0x22 / 0x49, requirement 5 collected."""
        self.start_game()
        self.assertEqual(3, self.tf.adj[67] * 2 + 1)
        before = self.score
        for n in (1, 2, 3):
            self.shoot("center")
            self.assertEqual(n, self.pd.opt_access)
        self.assertEqual(3, self.deffs().count(141))
        self.shoot("center")
        self.assertTrue(self.tf.flag(0x46))
        self.assertIn(0x6b, self.audits())
        self.assertIn(200000, [e["points"] for e in self.events("score_add")])
        self.assertGreater(self.score, before)
        self.mark()
        hits = 0
        while not self.feature("optimus").running():
            self.shoot("optimus")
            hits += 1
            self.assertLessEqual(hits, 9)
        self.assertEqual(4, hits)                                   # 3 left + the one that starts it
        side = self.feature("optimus").running()
        self.assertIn(2000000, [e["points"] for e in self.events("score_add")])
        self.assertTrue(self.tf.flag(0x22) and self.tf.flag(0x49))
        self.assertFalse(self.tf.flag(0x46))
        self.assertIn(0x70, self.audits())
        self.assertEqual([1, 0], self.feature("wizard").reqs()[5])
        self.wait(12)
        self.settle()
        self.assertEqual(3, self.game.balls_in_play)
        self.check()

    def test_jackpots_doubles_and_super(self):
        """A lit shot is a jackpot and lights Optimus for the double; six of each then Optimus scores the super:
        requirement 5 completed, every shot lit again."""
        self.start_game()
        side = self.start_optimus_multiball()
        self.wait(12)
        self.settle()
        self.mark()
        for _ in range(6):
            self.assertEqual(1, side.phase)
            self.shoot_any(self.lit(side)[-1])
            self.assertEqual(2, side.phase)
            self.shoot("optimus")
        self.assertEqual(3, side.phase)
        self.assertEqual((6, 6), (self.audits().count(0x71), self.audits().count(0x72)))
        self.shoot("optimus")
        self.assertIn(0x73, self.audits())
        self.assertEqual((1, 0x3f), (side.phase, side.lit))
        self.assertEqual([1, 1], self.feature("wizard").reqs()[5])
        self.check(settled=False)

    def test_center_lane_is_blocked_during_a_multiball(self):
        """The access does not count while a multiball runs: 1,000, no deff 141."""
        self.start_game()
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        access = self.pd.get("opt_access", 0)
        self.mark()
        self.shoot("center")
        self.assertEqual(access, self.pd.get("opt_access", 0))
        self.assertNotIn(141, self.deffs())

    def test_ends_with_one_ball(self):
        self.start_game()
        side = self.start_optimus_multiball()
        self.wait(12)
        self.settle()
        self.wait_ball_save()
        self.drain(2)
        self.wait(8)
        self.assertFalse(side.active or side.alive)
        self.assertFalse(self.tf.flag(0x22))
        self.assertIn(68, self.deffs())
        self.settle()
        self.assertEqual(1, self.game.balls_in_play)
        self.check()
        self.shoot("center")                                        # the access counts again
        self.assertEqual(1, self.pd.opt_access)


class TestOptimusAutobot(OptimusCase):
    SIDE = AUTOBOT

    def test_jackpot_double_and_super_at_the_lock(self):
        """Autobot: a lit shot is a jackpot and alone stays lit for its double; six doubles light the super at
        the Megatron lock."""
        self.start_game()
        side = self.start_optimus_multiball()
        self.assertTrue(self.tf.flag(0x1f))
        self.wait(12)
        self.settle()
        self.mark()
        for _ in range(6):
            self.assertEqual(1, side.phase)
            name = self.lit(side)[-1]
            self.shoot_any(name)
            self.assertEqual((2, 1 << NAMES[name]), (side.phase, side.lit))
            self.shoot_any(name)
        self.assertEqual(3, side.phase)
        self.lock()
        self.assertIn(0x6f, self.audits())
        self.assertEqual([1, 1], self.feature("wizard").reqs()[5])
        self.assertEqual(1, side.phase)
        self.check(settled=False)


class TestOptimusAdjustments(OptimusCase):

    def test_adj_67_sets_the_hits(self):
        """adj 67 OPTIMUS DIFFICULTY: the battle needs 2 x level + 1 hits before the starting one."""
        for level in (0, 1, 3):
            with self.subTest(adj_67=level):
                self.set_adj(67, level)
                self.start_game()
                for _ in range(4):
                    self.shoot("center")
                self.assertTrue(self.tf.flag(0x46))
                hits = 0
                while not self.feature("optimus").running():
                    self.shoot("optimus")
                    hits += 1
                    self.assertLessEqual(hits, 12)
                self.assertEqual(2 * level + 2, hits)
                self.end_game()

    def test_adj_87_keeps_the_progress(self):
        """adj 87 OPTIMUS MB MEMORY: YES restores the lit shots of the last multiball, NO relights them all."""
        for value, lit in ((1, 5), (0, 6)):
            with self.subTest(adj_87=value):
                self.set_adj(87, value)
                self.set_adj(31, 5)
                self.start_game()
                side = self.start_optimus_multiball()
                self.wait(12)
                self.settle()
                self.shoot_any(self.lit(side)[-1])
                self.shoot("optimus")                               # one jackpot + double: five shots left
                self.assertEqual(5, bin(side.remaining).count("1"))
                self.end_ball()
                self.plunge()
                side = self.start_optimus_multiball()
                self.assertEqual(lit, bin(side.lit).count("1"))
                self.end_game()

    def test_adj_85_stops_the_motor(self):
        """adj 85 OPTIMUS MOTOR DISABLED [0x00017120]: the figure's motor never runs; the rules go on."""
        for value in (0, 1):
            with self.subTest(adj_85=value):
                self.set_adj(85, value)
                self.start_game()
                self.mark()
                self.start_optimus_multiball()
                self.wait(10)
                motor = self.events("coil", coil=30)
                self.assertEqual(bool(motor), not value)
                self.end_game()
