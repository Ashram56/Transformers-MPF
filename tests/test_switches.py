"""Switch scores from the ROM extraction's per-switch trace (rom/rules/switches_and_shots.md, observed)."""
from tests.tf_test import TfTestCase


class TestSwitchScores(TfTestCase):

    def start_ball(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)

    def hit(self, name):
        before = self.machine.game.player.score
        self.hit_and_release_switch(name)
        self.advance_time_and_run(2)
        return self.machine.game.player.score - before

    def test_slings_pops_and_handlers(self):
        self.start_ball()
        self.assertEqual(440, self.hit("s_left_slingshot"))
        self.assertEqual(440, self.hit("s_right_slingshot"))
        self.assertEqual(3170, self.hit("s_top_bumper"))
        self.assertEqual(560, self.hit("s_l_ramp_entrance"))
        self.assertEqual(30, self.hit("s_megatron_back_door"))
        self.assertEqual(5060, self.hit("s_left_top_lane"))       # lane 2500 (interim) + handler 2560
        sounds = [int(e["call"], 16) for e in self.tf.trace.of("sound")]
        self.assertTrue({0x15a, 0x15c} <= set(sounds))
        self.assertIn(46, [e["id"] for e in self.tf.trace.of("deff_start")])

    def test_side_choice_ends_on_a_playfield_switch(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertEqual(40, self.tf.display.bg)
        self.hit_and_release_switch("s_left_slingshot")
        self.advance_time_and_run(0.5)
        self.assertIn(41, [e["id"] for e in self.tf.trace.of("deff_start")])
