"""The game around the rules: balls per game, ball save, tilt, extra balls, players, the end of the game
(rom/rules/modes/game_flow.md), with the operator adjustments that shape them."""
from tests.bench.driver import AUTOBOT, BALLS, DECEPTICON, BenchCase


class TestBalls(BenchCase):

    def test_adj_31_balls_per_game(self):
        for balls in (1, 3, 5):
            with self.subTest(adj_31=balls):
                self.set_adj(31, balls)
                self.start_game()
                played = 0
                while self.game:
                    played += 1
                    self.assertEqual(played, self.game.player.ball)
                    self.end_ball()
                    self.plunge()
                self.assertEqual(balls, played)
                self.wait(12)
                self.settle()
                self.check()

    def test_adj_38_ball_save_time(self):
        """adj 38 BALL SAVE TIME: a drain within the time gives the ball back (deff 20, audit 0x2b); OFF: the
        ball ends."""
        for value, saved in ((5, True), (0, False)):
            with self.subTest(adj_38=value):
                self.set_adj(38, value)
                self.start_game()
                self.validate()
                self.mark()
                self.drain(1)
                self.wait(6)
                self.plunge()
                self.assertEqual(saved, self.game.player.ball == 1)
                self.assertEqual(saved, 20 in self.deffs())
                self.end_game()

    def test_ball_save_runs_out(self):
        self.start_game()
        self.validate()
        self.wait_ball_save()
        self.assertFalse(self.tf.ball_save)
        self.drain(1)
        self.wait(10)
        self.assertEqual(2, self.game.player.ball)

    def test_adj_39_timed_plunger(self):
        """adj 39 TIMED PLUNGER: the ball is launched for the player after that many seconds; OFF: it waits."""
        for value, launched in ((0, False), (5, True)):
            with self.subTest(adj_39=value):
                self.set_adj(39, value)
                self.start_game(plunge=False)
                self.wait(12)
                self.assertEqual(launched, self.census()[1] == 0, "census {}".format(self.census()))
                self.end_game()

    def test_adj_40_flipper_ball_launch(self):
        """adj 40 FLIPPER BALL LAUNCH: LEFT: the left flipper button launches the ball in the shooter lane."""
        for value, launched in ((0, False), (1, True)):
            with self.subTest(adj_40=value):
                self.set_adj(40, value)
                self.start_game(plunge=False)
                self.wait(3)
                self.hit_and_release_switch("s_l_flipper_button")
                self.wait(3)
                self.assertEqual(launched, self.census()[1] == 0, "census {}".format(self.census()))
                self.end_game()


class TestTilt(BenchCase):

    def test_adj_32_tilt_warnings(self):
        """adj 32 TILT WARNINGS: that many warnings (deff 23), the next bob tilts: the ball ends without bonus."""
        for warnings in (0, 2, 3):
            with self.subTest(adj_32=warnings):
                self.set_adj(32, warnings)
                self.start_game()
                self.validate()
                self.mark()
                for n in range(warnings):
                    self.hit("s_tilt_pendulum", wait=1.5)
                    self.assertFalse(self.tf.tilted)
                self.assertEqual(warnings, self.deffs().count(23))
                self.hit("s_tilt_pendulum", wait=1.5)
                self.assertTrue(self.tf.tilted)
                before = self.game.player.score
                self.shoot("left_ramp")                         # nothing scores on a tilted ball
                self.assertEqual(before, self.game.player.score)
                player = self.game.player
                self.drain(self.rolling())
                self.wait(12)
                self.assertEqual(before, player.score)          # no bonus
                self.assertNotIn(25, self.deffs())
                self.plunge()
                self.assertFalse(self.tf.tilted)
                self.settle()
                self.check_fresh_ball()
                self.end_game()

    def test_tilt_during_a_multiball_ends_everything(self):
        self.set_adj(32, 0)
        self.start_game()
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        self.hit("s_tilt_pendulum", wait=1)
        self.assertTrue(self.tf.tilted)
        self.drain(self.rolling())
        self.wait(12)
        self.plunge()
        self.settle()
        self.assertEqual(2, self.game.player.ball)
        self.assertEqual(1, self.game.balls_in_play)
        self.check_fresh_ball()
        self.check()

    def test_adj_64_coin_door_disables_the_tilt(self):
        """adj 64 COIN DOOR DISABLE TILT [0x00024344]: with the door open the bob is ignored."""
        for value, tilted in ((0, True), (1, False)):
            with self.subTest(adj_64=value):
                self.set_adj(32, 0)
                self.set_adj(64, value)
                self.start_game()
                self.validate()
                self.sw("s_coin_door_open", 1)
                self.wait(1)
                self.hit("s_tilt_pendulum", wait=1.5)
                self.assertEqual(tilted, self.tf.tilted)
                self.sw("s_coin_door_open", 0)
                self.wait(1)
                self.end_game()


class TestExtraBall(BenchCase):

    def light_and_collect(self):
        self.feature("awards").eb_light()
        self.wait(4)
        self.shoot("right_orbit")
        self.wait(4)

    def test_adj_26_extra_ball_limit(self):
        """adj 26 EXTRA BALL LIMIT [0x00018204]: that many extra balls a game, then 3,000,000 instead."""
        for limit in (0, 1, 2):
            with self.subTest(adj_26=limit):
                self.set_adj(26, limit)
                self.start_game()
                given = []
                for _ in range(3):
                    before = self.game.player.extra_balls
                    self.light_and_collect()
                    given.append(self.game.player.extra_balls - before)
                self.assertEqual([1] * limit + [0] * (3 - limit), given)
                self.end_game()

    def test_adj_83_wizard_requirements_light_the_extra_ball(self):
        """adj 83 BONUS EXTRA BALL AT: the extra ball is lit when that many wizard requirements were collected
        (once a game: flag 0x15, the player's own)."""
        for at in (1, 2):
            with self.subTest(adj_83=at):
                self.set_adj(83, at)
                self.set_adj(31, 5)
                self.start_game()
                for n in range(1, 3):
                    self.start_battle()
                    self.assertEqual(1 if n >= at else 0, self.tf.eb_lit[0])
                    self.end_ball()
                    self.plunge()
                self.end_game()

    def test_an_extra_ball_plays_the_same_ball_number(self):
        self.start_game()
        self.light_and_collect()
        self.end_ball()
        self.assertEqual(1, self.game.player.ball)
        self.plunge()
        self.settle()
        self.check_fresh_ball()
        self.end_ball()
        self.assertEqual(2, self.game.player.ball)


class TestSpecial(BenchCase):

    def collect(self):
        self.feature("awards").special_light()
        self.wait(4)
        self.shoot("right_orbit")
        self.wait(4)

    def test_adj_23_special_award(self):
        """adj 23 SPECIAL AWARD [0x0001d7a0]: CREDIT, POINTS (1,000,000 here: the OS's value) or EXTRA BALL."""
        for value in (0, 3, 4):
            with self.subTest(adj_23=value):
                self.set_adj(23, value)
                self.start_game()
                credits = self.machine.variables.get_machine_var("credits_string")
                score, balls = self.game.player.score, self.game.player.extra_balls
                self.mark()
                self.collect()
                self.assertIn(0x0e, self.audits())
                self.assertEqual(value == 4, self.game.player.extra_balls == balls + 1)
                self.assertEqual(value == 3, self.game.player.score - score >= 1000000)
                self.end_game()

    def test_adj_22_special_limit(self):
        """adj 22 SPECIAL LIMIT: past it a special scores its points and no award (no audit 0x0e)."""
        for limit in (0, 1):
            with self.subTest(adj_22=limit):
                self.set_adj(22, limit)
                self.set_adj(23, 4)
                self.start_game()
                awarded = []
                for _ in range(2):
                    self.mark()
                    self.collect()
                    awarded.append(self.audits().count(0x0e))
                self.assertEqual([1] * limit + [0] * (2 - limit), awarded)
                self.end_game()


class TestSide(BenchCase):

    def test_adj_65_transformers_select(self):
        """adj 65 TRANSFORMERS SELECT: AUTOBOT / DECEPTICON fixes each player's starting side."""
        for value, side, lit in ((1, AUTOBOT, 0x10), (2, DECEPTICON, 0x01)):
            with self.subTest(adj_65=value):
                self.set_adj(65, value)
                self.start_game()
                self.assertEqual(side, self.pd.side)
                self.assertEqual(lit, self.pd.battle_lit)
                self.end_game()

    def test_a_flipper_changes_the_side_before_the_plunge(self):
        self.start_game(plunge=False)
        self.assertEqual(DECEPTICON, self.pd.side)
        self.hit_and_release_switch("s_l_flipper_button")
        self.wait(1)
        self.assertEqual(AUTOBOT, self.pd.side)
        self.assertEqual(0x10, self.pd.battle_lit)
        self.plunge()
        self.wait(3)
        self.hit_and_release_switch("s_l_flipper_button")
        self.wait(1)
        self.assertEqual(AUTOBOT, self.pd.side)                     # not after the plunge

    def test_adj_42_competition_mode(self):
        """adj 42 COMPETITION MODE [0x01022aa0]: the first lit battle is Bumblebee whatever the side; the
        Allspark awards follow the fixed sequence (POPS first)."""
        self.set_adj(42, 1)
        self.start_game()
        self.assertEqual(0x10, self.pd.battle_lit)
        weights = self.feature("allspark").weights()
        self.assertEqual(6, weights.index(max(weights)))            # item 7 POPS SCORE


class TestGameOver(BenchCase):

    def test_the_game_ends_clean(self):
        self.start_game()
        self.start_battle()
        self.end_game()
        self.wait(15)
        self.settle()
        self.assertEqual(BALLS, self.census()[0])
        self.check()
        self.start_game()                                            # and a new game starts fresh
        self.settle()
        self.assertEqual(0, self.pd.get("battle_started", 0))
        self.check_fresh_ball()
        self.check()

    def test_adj_36_game_restart(self):
        """adj 36 GAME RESTART: the start button held from ball 2 on starts a new game; NO: it does nothing."""
        for value, restarted in ((1, True), (0, False)):
            with self.subTest(adj_36=value):
                self.set_adj(36, value)
                self.start_game()
                self.end_ball()
                self.plunge()
                self.assertEqual(2, self.game.player.ball)
                self.sw("s_start_button", 1)                     # held 62 ticks [0x00020d14]
                self.wait(1.5)
                self.sw("s_start_button", 0)
                self.wait(3)
                self.drain(self.rolling() if restarted else 0)   # the old ball goes home, then ball 1 is served
                self.wait(15)
                self.assertIsNotNone(self.game)
                self.assertEqual(restarted, self.game.player.ball == 1)
                self.plunge()
                self.settle()
                self.check()
                self.end_game()

    def test_players_join_on_the_first_ball_only(self):
        self.set_adj(36, 0)
        self.start_game(players=2)
        self.hit_and_release_switch("s_start_button")
        self.wait(1)
        self.assertEqual(3, len(self.game.player_list))
        self.end_ball()
        self.plunge()
        self.end_ball()
        self.plunge()
        self.end_ball()
        self.plunge()
        self.assertEqual((1, 2), (self.game.player.number, self.game.player.ball))
        self.hit_and_release_switch("s_start_button")
        self.wait(1)
        self.assertEqual(3, len(self.game.player_list))
