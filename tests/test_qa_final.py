"""Regression tests of the final pass, the MPF code against the decoded code (docs/qa/final/mpf_vs_code.csv): each
asserts the ROM's behaviour at the address cited by its row."""
from tests.test_qa_2026_11_25 import QaCase

TICK = 0.016


class TestFinalPass(QaCase):
    def hit(self, name, wait=0.5):
        before = self.score()
        self.hit_and_release_switch(name)
        self.advance_time_and_run(wait)
        return self.score() - before

    def sounds(self):
        return [e.get("call") for e in self.tf.trace.of("sound")]

    def test_f003_pop_burst_total_starts_with_the_task(self):
        """start_leff_33 [0x0102c8c8]: the hit that starts task 0x51 starts the burst total again, the others add up
        while the task runs, even after deff 46 has gone (62 ticks) and before the task ends (93 idle ticks)."""
        self.start()
        pops = self.tf.features_by_name["pops"]
        self.hit("s_top_bumper", 0.2)
        first = pops.total
        self.advance_time_and_run(62 * TICK + 0.1)      # deff 46 over, task 0x51 still idling
        self.assertTrue(self.tf.task_running(0x51))
        self.hit("s_top_bumper", 0.2)
        self.assertGreater(pops.total, first)
        self.advance_time_and_run(2)                    # the task ends
        self.hit("s_top_bumper", 0.2)
        self.assertEqual(self.tf.pd.pop_value - 1000, pops.total)

    def test_f006_fast_scoring_task_0xad(self):
        """[0x0100416c]: call 0x291 0x271 ticks after the start while task 0xac runs; after the tail the mode's
        tasks still run until 0xad wakes without 0xac ([0x0100462c]), so a switch still scores the award."""
        self.start()
        fs = self.tf.features_by_name["twobank"]
        fs.start()
        fs.started_now = False                          # started here, not by a 2-bank hit
        self.advance_time_and_run(0x271 * TICK + 0.2)
        self.assertIn("0x291", self.sounds())
        self.assertTrue(fs.ad_running)
        fs.counting = False                             # the countdown is over: the tail
        fs.stop(speech=False)
        self.assertTrue(fs.live())
        before = self.score()
        self.hit("s_left_slingshot", 0.2)
        self.assertGreaterEqual(self.score() - before, fs.value)
        self.advance_time_and_run(0x271 * TICK + 2)
        self.assertFalse(fs.live())

    def test_f012_add_player_speech_by_index(self):
        """Event 0x46 hook [0x0100601c]: call 0x48 with argument players - 1, the sample of that index."""
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(1)
        played = []
        orig = self.tf.sound
        self.tf.sound = lambda call, in_deff=0, index=None: played.append((call, index)) or orig(call, in_deff, index)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(0.5)
        self.assertIn((0x048, 1), played)

    def test_f013_no_launch_sound_on_a_bounce(self):
        """sw_shooter_lane [0x01032dfc]: no 0x56 when the lane opens while task 0x3d (6 ticks) runs."""
        self.start()
        n = self.sounds().count("0x056")
        self.hit_and_release_switch("s_shooter_lane")
        self.advance_time_and_run(0.3)
        self.assertEqual(n, self.sounds().count("0x056"))

    def test_f002_trough_kick_hold_off_from_power_up(self):
        """coil_pulse_queue_serve [0x00003758]: the first queued pulse since power-up has no hold-off."""
        self.assertFalse(self.tf._pulse_queue_used)
        self.start()
        self.assertTrue(self.tf._pulse_queue_used)
