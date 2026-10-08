"""Sounds, music and the side choice against the reference trace rom/rules/traces/sounds.jsonl (observed)."""
from tests.tf_test import TfTestCase


class TestSounds(TfTestCase):

    def sounds(self):
        return [int(e["call"], 16) for e in self.tf.trace.of("sound")]

    def deffs(self):
        return [e["id"] for e in self.tf.trace.of("deff_start")]

    def leffs(self):
        return [e["id"] for e in self.tf.trace.of("leff_start")]

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)

    def test_side_choice_and_base_music(self):
        self.start_game()
        self.assertEqual(0x1b, self.sounds()[-1])               # choose your side, Decepticon kept
        self.assertEqual([19, 40], self.deffs()[-2:])
        self.assertTrue({104, 92, 95, 14} <= set(self.leffs()))    # 14: the OS's ball save leff
        self.hit_and_release_switch("s_l_flipper_button")       # inferred: a flipper switches the side
        self.advance_time_and_run(0.1)
        self.assertEqual(0x1a, self.sounds()[-1])
        self.hit_and_release_switch("s_r_flipper_button")
        self.advance_time_and_run(0.1)
        self.assertEqual(0x1b, self.sounds()[-1])
        self.release_switch_and_run("s_shooter_lane", 0.3)
        self.assertEqual(0x056, self.sounds()[-1])              # launch sound, 4 ticks after the lane opens
        self.advance_time_and_run(1)
        self.assertIn(41, self.deffs())                         # side chosen, 37 ticks after the launch
        self.assertIn(0x058, self.sounds())                     # deff 41's own sound
        self.assertIn(96, self.leffs())                         # and its lamp effect
        self.assertEqual(0x1d, self.sounds()[-1])               # ball start music, Decepticon
        self.assertEqual(19, self.tf.display.bg)
        for name in ("s_left_slingshot", "s_right_slingshot", "s_top_bumper"):
            self.hit_and_release_switch(name)
        self.advance_time_and_run(1)
        self.assertTrue(self.tf.pf_valid)
        self.assertEqual(0x1f, self.sounds()[-1])               # main play music

    def test_tilt_sounds(self):
        self.start_game()
        self.release_switch_and_run("s_shooter_lane", 2)
        self.hit_and_release_switch("s_tilt_pendulum")
        self.advance_time_and_run(0.3)
        self.assertEqual(0x016, self.sounds()[-1])
        self.advance_time_and_run(0.3)
        self.assertEqual(0x052, self.sounds()[-1])              # 31 ticks later
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_tilt_pendulum")
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_tilt_pendulum")
        self.advance_time_and_run(0.5)
        self.assertEqual(0x017, self.sounds()[-1])
        self.advance_time_and_run(0.6)
        self.assertEqual(0x053, self.sounds()[-1])              # 62 ticks later

    def test_outlanes_lane_award_and_ball_save(self):
        self.start_game()
        self.release_switch_and_run("s_shooter_lane", 2)
        self.hit_and_release_switch("s_left_outlane")           # ball save running: saved
        self.advance_time_and_run(1)
        self.assertIn(20, self.deffs())
        self.assertTrue({0x169, 0x05e, 0x05f} <= set(self.sounds()))
        self.assertIn(97, self.leffs())
        self.tf.kill_ball_save()
        self.hit_and_release_switch("s_right_outlane")
        self.advance_time_and_run(0.2)
        self.assertIn(0x16d, self.sounds())
        self.assertIn(100, self.leffs())

    def test_coin_sounds(self):
        self.tf.adj.override(34, 0)                             # not free play
        self.hit_and_release_switch("s_right_coin_slot")
        self.advance_time_and_run(2)
        self.assertEqual(0x042, self.sounds()[-1])              # a coin that makes no credit
        for _ in range(2):
            self.hit_and_release_switch("s_right_coin_slot")
            self.advance_time_and_run(2)
        self.assertEqual([0x042, 0x042, 0x043], self.sounds())   # the third coin completes a credit (trace)

    def test_usa_10_pricing(self):
        """pricing.json verification_log (emulator): 3 quarters = 1 credit; $1 on the center slot then shows
        CREDITS 2 1/2; a quarter on the right slot gives credit 3."""
        self.tf.adj.override(34, 0)
        for _ in range(3):
            self.hit_and_release_switch("s_left_coin_slot")
            self.advance_time_and_run(1)
        self.assertEqual(1, self.tf.credit_model.credits)
        self.hit_and_release_switch("s_center_coin_slot")
        self.advance_time_and_run(1)
        self.assertEqual("CREDITS 2 1/2", self.tf.credit_model.text())
        self.hit_and_release_switch("s_right_coin_slot")
        self.advance_time_and_run(1)
        self.assertEqual(3, self.tf.credit_model.credits)
