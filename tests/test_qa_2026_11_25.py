"""Regression tests for the findings the QA pass of 2026-11-25 fixed (docs/qa/README.md): each asserts the
ROM's behaviour at the address cited."""
from tests.tf_test import TfTestCase

TICK = 0.016


class QaCase(TfTestCase):
    def start(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)

    def score(self):
        return self.machine.game.player.score

    def deffs(self):
        return [e.get("id") for e in self.tf.trace.of("deff_start")]


class TestOsAwards(QaCase):
    def test_extra_ball_collected_at_right_orbit(self):
        """[0x01033488] -> [0x01007b74]: a lit extra ball is collected by the right orbit, deff 54 (QA F1)."""
        self.start()
        self.tf.light_extra_ball()
        self.advance_time_and_run(4)                 # past the launch ignore (task 0x47, 187 ticks)
        self.hit_and_release_switch("s_right_orbit")
        self.advance_time_and_run(1)
        self.assertEqual(0, self.tf.eb_lit[0])
        self.assertEqual(1, self.machine.game.player.extra_balls)
        self.assertIn(54, self.deffs())

    def test_special_lit_and_collected(self):
        """[0x01008528] lights lamp 53 with deff 55; [0x01008684] collects it at the right orbit, deff 56 (QA F2, F3)."""
        self.start()
        self.tf.light_special()
        self.tf.light_extra_ball()
        self.advance_time_and_run(6)
        self.assertIn(55, self.deffs())
        self.assertIn(53, self.deffs())
        self.tf.eb_lit[0] = 0
        self.hit_and_release_switch("s_right_orbit")
        self.advance_time_and_run(4)
        self.assertEqual(0, self.tf.specials_lit[0])
        self.assertIn(56, self.deffs())


class TestMultiballs(QaCase):
    def test_jackpots_score_in_the_end_window(self):
        """Gates [0x0100be84] [0x0100dec0] [0x010276e0] [0x01029754]: the shot rules run while the end task runs
        (218 ticks after the drop to one ball) (QA M1)."""
        self.start()
        for name, side_no, shot in (("megatron", 1, 6), ("megatron", 2, 0), ("optimus", 1, 0), ("optimus", 2, 0)):
            side = self.tf.features_by_name[name].sides[side_no]
            self.tf.pd["side"] = side_no
            side.start() if name == "megatron" else side.start(1)
            side.active = True
            side.multiball_end()
            self.advance_time_and_run(0.5)
            before = self.score()
            side.shot(shot)
            self.assertGreater(self.score() - before, 0, (name, side_no))
            side.kill()

    def test_autobot_doubles_wait_for_m3(self):
        """[0x0100c10c]: the double-jackpot timeout waits while M < 3 (QA M3)."""
        self.start()
        side = self.tf.features_by_name["megatron"].sides[1]
        self.tf.pd["side"] = 1
        side.start()
        side.shot(6)
        self.advance_time_and_run(330 * TICK)
        self.assertEqual((2, 0x3f), (side.phase, side.mask))
        side.kill()

    def test_decepticon_megatron_progress_saved(self):
        """[0x0100e0bc]: adj 88 YES restores the Decepticon jackpot count, mask and phase (QA M2)."""
        self.start()
        self.assertEqual(1, self.tf.adj[88])
        side = self.tf.features_by_name["megatron"].sides[2]
        self.tf.pd["side"] = 2
        side.start()
        for shot in (0, 1, 2, 4):
            side.shot(shot)
        side.multiball_end()
        self.advance_time_and_run(5)
        side.kill()
        side.start()
        self.assertEqual((4, 0x68), (side.jp, side.mask))
        side.kill()

    def test_optimus_decepticon_super_multiplied(self):
        """[0x01029bf4] phase 3: the super x the center lane's multiplier (QA M4)."""
        self.start()
        side = self.tf.features_by_name["optimus"].sides[2]
        self.tf.pd["side"] = 2
        side.start(1)
        self.tf.shot_mult = lambda shot: 2 if shot == 3 else 1
        side.phase, side.lit, side.remaining = 3, 0x40, 0
        before = self.score()
        side.optimus()
        self.assertEqual(2000000, self.score() - before)
        side.kill()


class TestBonusHold(QaCase):
    def test_holds_last_one_ball(self):
        """[0x01000d58]: BONUS HOLD (0x4b) and BONUS X HOLD (0x4a) are cleared at the next ball start (QA P1)."""
        self.start()
        allspark = self.tf.features_by_name["allspark"]
        allspark.run(8)
        allspark.run(9)
        allspark.run(4)
        for _ in range(5):
            self.hit_and_release_switch("s_left_slingshot")
            self.advance_time_and_run(0.3)
        self.assertTrue(self.tf.flag(0x4a) and self.tf.flag(0x4b))
        for ball in (2, 3):
            self.next_ball()
            self.assertEqual(ball, self.machine.game.player.ball)
            self.assertFalse(self.tf.flag(0x4a) or self.tf.flag(0x4b))
            if ball == 2:
                self.assertEqual(2, self.tf.pd.bonus_x)
            else:
                self.assertEqual((1, 125000), (self.tf.pd.bonus_x, self.tf.pd.bonus_held))

    def next_ball(self):
        """Validate the playfield, wait out the ball save, drain the ball into the trough, plunge the next."""
        for name in ("s_l_ramp_entrance", "s_r_ramp_entrance", "s_captive_ball"):
            self.hit_and_release_switch(name)
            self.advance_time_and_run(0.3)
        self.advance_time_and_run(20)
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.advance_time_and_run(15)
        self.release_switch_and_run("s_shooter_lane", 2)
