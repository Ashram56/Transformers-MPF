"""The game boots on virtual hardware and plays through: start, plunge, drains, game over, attract."""
from tests.tf_test import TfTestCase


class TestBoot(TfTestCase):

    def drain(self):
        """The ball on the playfield drains into the trough (smart_virtual: the trough switch closes)."""
        self.assertEqual(1, self.machine.playfield.balls)
        names = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")
        free = next(n for n in names if not self.machine.switches[n].state)
        self.machine.switch_controller.process_switch(free, 1, True)
        self.advance_time_and_run(10)

    def plunge(self):
        self.assertSwitchState("s_shooter_lane", 1)
        self.release_switch_and_run("s_shooter_lane", 2)     # the eject is confirmed by its timeout

    def test_attract_after_boot(self):
        self.advance_time_and_run(2)
        self.assertModeRunning("attract")
        self.assertIn(1, [e["id"] for e in self.tf.trace.of("deff_start")])
        self.assertEqual(1, self.tf.display.bg)

    def test_game_start_plunge_drain(self):
        self.fill_trough()
        self.assertModeRunning("attract")
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertModeRunning("game")
        self.assertEqual(1, self.machine.game.player.ball)
        self.assertEqual(40, self.tf.display.bg)                # the side choice (tf/features/side.py)
        self.plunge()
        self.assertEqual(19, self.tf.display.bg)                # the score display once the side is chosen
        self.hit_and_release_switch("s_left_top_lane")          # a lane: playfield valid
        self.advance_time_and_run(1)
        self.assertTrue(self.tf.pf_valid)
        self.tf.kill_ball_save()
        self.drain()
        self.assertEqual(2, self.machine.game.player.ball)

    def test_three_validating_targets(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.plunge()
        for name in ("s_left_slingshot", "s_right_slingshot"):
            self.hit_and_release_switch(name)
            self.advance_time_and_run(0.2)
        self.assertFalse(self.tf.pf_valid)
        self.hit_and_release_switch("s_top_bumper")
        self.advance_time_and_run(0.2)
        self.assertTrue(self.tf.pf_valid)

    def test_drain_before_valid_reserves_the_ball(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.plunge()
        self.drain()
        self.assertEqual(1, self.machine.game.player.ball)      # not a lost ball: served again

    def test_ball_save(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.plunge()
        self.hit_and_release_switch("s_left_top_lane")
        self.advance_time_and_run(1)
        self.assertEqual("armed", self.tf.ball_save)            # adj 38 BALL SAVE TIME 5 s
        self.drain()
        self.assertEqual(1, self.machine.game.player.ball)
        self.assertIn(20, [e["id"] for e in self.tf.trace.of("deff_start")])     # BALL SAVED
        self.assertEqual(1, self.tf.audits.get(0x2b))           # TOTAL BALLS SAVED

    def test_full_game_to_attract(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        for ball in (1, 2, 3):
            self.assertEqual(ball, self.machine.game.player.ball)
            self.plunge()
            self.hit_and_release_switch("s_left_top_lane")
            self.advance_time_and_run(1)
            self.tf.kill_ball_save()
            self.drain()
        self.advance_time_and_run(20)
        self.assertIsNone(self.machine.game)
        self.assertModeRunning("attract")
        self.assertIn(38, [e["id"] for e in self.tf.trace.of("deff_start")])    # match
        self.assertEqual(3, self.tf.audits.get(8))              # TOTAL BALLS PLAYED

    def test_tilt(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.plunge()
        self.hit_and_release_switch("s_left_top_lane")
        self.advance_time_and_run(1)
        for _ in range(3):                                      # adj 32 TILT WARNINGS 2, then the tilt
            self.hit_and_release_switch("s_tilt_pendulum")
            self.advance_time_and_run(1.5)
        self.assertTrue(self.tf.tilted)
        deffs = [e["id"] for e in self.tf.trace.of("deff_start")]
        self.assertEqual(2, deffs.count(23))                    # DANGER twice
        self.assertIn(21, deffs)                                # TILT

    def test_two_players(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(0.5)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertEqual(2, len(self.machine.game.player_list))
