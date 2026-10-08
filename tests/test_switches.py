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
        self.assertEqual(500030, self.hit("s_megatron_back_door"))    # super skill shot (ends both)
        self.assertEqual(2500 + 2560, self.hit("s_left_top_lane"))     # lane lamp + handler
        sounds = [int(e["call"], 16) for e in self.tf.trace.of("sound")]
        self.assertTrue({0x15a, 0x15c} <= set(sounds))
        self.assertIn(46, [e["id"] for e in self.tf.trace.of("deff_start")])

    def test_hands_free_skill_shot(self):
        """game_flow.md 5.1 (game_flow.jsonl t 18.79): the Decepticon lane, 350,000 and both lane lamps."""
        self.start_ball()
        self.assertEqual(350000 + 2 * 2500 + 2560, self.hit("s_left_top_lane"))
        self.assertIn(42, [e["id"] for e in self.tf.trace.of("deff_start")])

    def test_side_choice_ends_on_a_playfield_switch(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertEqual(40, self.tf.display.bg)
        self.hit_and_release_switch("s_left_slingshot")
        self.advance_time_and_run(0.5)
        self.assertIn(41, [e["id"] for e in self.tf.trace.of("deff_start")])

    def test_pop_runs_its_lamp_effect(self):
        """A pop starts leff 26, whose captured show pulses the pop bumper flasher (lampfx_026.yaml)."""
        self.start_ball()
        coils = self.tf.lamps.coil_numbers
        self.hit("s_top_bumper")
        self.assertIn(26, [e["id"] for e in self.tf.trace.of("leff_start")])
        pulsed = {e["coil"] for e in self.tf.trace.of("coil") if e["on"]}
        self.assertIn(coils["c_flash_pop_bumper"], pulsed)
        self.assertTrue(self.tf.lamps.leff_info[1][0] == "lampfx_001" and self.tf.lamps.leff_info[1][1] == -1)

    def quick(self, name, wait=0.17):
        before = self.machine.game.player.score
        self.hit_and_release_switch(name)
        self.advance_time_and_run(wait)
        return self.machine.game.player.score - before

    def test_pops_grow_on_quick_hits(self):
        """scoring_features.md 4.1: 3,000, 4,000 ... while the pops keep being hit; back to 3,000 after 93 ticks."""
        self.start_ball()
        self.assertEqual([3170, 4170, 5170], [self.quick("s_top_bumper") for _ in range(3)])
        self.advance_time_and_run(2)
        self.assertEqual(3170, self.quick("s_right_bumper"))

    def test_lanes_complete(self):
        """combos_and_multipliers.md 5 (scoring.jsonl t 36.45-46.72, Decepticon): the Megatron lanes light the
        shot multipliers, the Optimus lanes add 1 to the bonus multiplier."""
        self.start_ball()
        self.hit("s_right_orbit_spinner")                           # a force switch ends the skill shot
        self.assertEqual([2500 + 2560, 2500 + 2560, 2500 + 100000],
                         [self.hit(n) for n in ("s_left_top_lane", "s_left_top_lane", "s_left_outlane")])
        self.assertEqual(10000 + 1090, self.hit("s_left_return_lane"))
        self.assertTrue(self.tf.pd.mult_lit)
        for name in ("s_right_top_lane", "s_right_top_lane", "s_right_return_lane"):
            self.hit(name)
        self.assertEqual(10000 + 100000, self.hit("s_right_outlane"))
        self.assertEqual(2, self.tf.pd.bonus_x)
        self.assertIn(45, [e["id"] for e in self.tf.trace.of("deff_start")])

    def test_bumblebee_double_scoring(self):
        """scoring_features.md 4.3: 7 hits from 2 letters (EASY), the 9th letter doubles every score."""
        self.start_ball()
        awards = [self.hit("s_bumblebee_target") for _ in range(7)]
        self.assertEqual([20030, 25030, 30030, 35030, 40030, 45030, 50060], awards)
        self.assertEqual(2, self.tf.pf_mult)
        self.assertEqual(880, self.hit("s_left_slingshot"))

    def test_two_bank_and_fast_scoring(self):
        """scoring_features.md 4.4: 7 hits of 75,000, then the next starts fast scoring (100,000)."""
        self.start_ball()
        for _ in range(7):
            self.assertEqual(75030, self.hit("s_r_2_bank_target_top"))
        self.assertEqual(100030, self.hit("s_r_2_bank_target_bot"))
        self.assertEqual(9, self.tf.pd.twobank_left)
        self.assertEqual(440 + 10000, self.hit("s_left_slingshot"))   # every switch scores fast_value

    def test_combos(self):
        """combos_and_multipliers.md 4 (combos.jsonl): 2-way 150,000, 3-way 175,000; the left ramp is also a lit
        mode-start shot (battles.md 4.2: 15,000 as the second one); the center lane adds 2,500 (Optimus access)."""
        self.start_ball()
        self.hit("s_left_orbit_top")
        self.assertEqual(150000 + 15000 + 1170, self.hit("s_l_ramp_exit"))
        self.assertEqual(175000 + 2500 + 30, self.hit("s_center_lane"))
