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

    def test_f042_super_spinner_total_starts_with_the_task(self):
        """play_sound_270 [0x010320a4]: the spin that starts task 0x49 starts the super total again; the others
        add up while the task runs (93 idle ticks)."""
        self.start()
        spinner = self.tf.features_by_name["spinner"]
        spinner.light_super()
        self.advance_time_and_run(6)
        value = self.tf.pd.super_spin_value
        self.hit("s_right_orbit_spinner", 0.2)
        self.assertEqual(value, spinner.super_total)
        self.hit("s_right_orbit_spinner", 0.2)
        self.assertEqual(2 * value, spinner.super_total)
        self.advance_time_and_run(2)                    # task 0x49 ends
        self.hit("s_right_orbit_spinner", 0.2)
        self.assertEqual(value, spinner.super_total)

    def test_f045_replay_waits_for_any_foreground_deff(self):
        """Task 0x33 [0x0001c360]: deff 28 REPLAY waits while a non-background deff is on the display
        (deff_not_background_210a8 [0x000210a8]), a pop's deff 46 included, then starts with leff 17."""
        self.start()
        self.advance_time_and_run(4)                    # the launch deff over
        self.hit("s_top_bumper", 0.1)
        self.assertEqual(46, self.tf.display.fg)
        self.tf.replay_award(1)
        self.advance_time_and_run(0.3)
        self.assertNotIn(28, [e["id"] for e in self.tf.trace.of("deff_start")])
        self.advance_time_and_run(3)
        self.assertIn(28, [e["id"] for e in self.tf.trace.of("deff_start")])
        self.assertIn(17, [e["id"] for e in self.tf.trace.of("leff_start")])

    def test_f049_switch_test(self):
        """SWITCH TEST [0x0104cae4]: the grid (images 0xa4 / 0xa7), a dot (0xa5) per closed switch, the new closure's
        name, LAST SW. #n and wire colours at x 89, sound 0x00f; PLUS is a switch there (LAST SW. D-23), BACK leaves."""
        from tf import rom_draw
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("SWITCH MENU", "MAIN MENU / SWITCH MENU")
        mode._open_page({"text": "SWITCH TEST"})
        self.advance_time_and_run(0.1)
        self.assertEqual(["SWITCH TEST", "NONE"], rom_draw.lines_of(mode.draw()))
        self.hit_switch_and_run("s_left_slingshot", 0.1)
        draw = mode.draw()
        self.assertEqual(["SWITCH TEST", "LEFT SLINGSHOT", "LAST SW. #26", "GRN-RED / TAN-RED"],
                         rom_draw.lines_of(draw))
        self.assertTrue(any(d.get("i") == 0xa5 for d in draw))
        self.assertIn("0x00f", self.sounds())
        self.release_switch_and_run("s_left_slingshot", 0.1)
        self.assertEqual(["SWITCH TEST", "NONE", "LAST SW. #26"], rom_draw.lines_of(mode.draw()))
        self.hit_and_release_switch("s_plus")
        self.advance_time_and_run(0.1)
        self.assertEqual("SWITCH TEST", rom_draw.lines_of(mode.draw())[0])
        self.assertEqual("switch_test", mode.page["kind"])
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)

    def test_f050_single_coil_test(self):
        """SINGLE COIL TEST [0x01046f4c]: COIL TEST / the coil / #n / its wires; PLUS skips the hidden coils
        (flag 0x800 [0x01046eec]); SELECT pulses the coil for its test time; BACK leaves."""
        from tf import rom_draw
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("COIL MENU", "MAIN MENU / COIL MENU")
        mode._open_page({"text": "SINGLE COIL TEST"})
        self.advance_time_and_run(0.1)
        self.assertEqual(["COIL TEST", "TROUGH UP-KICKER", "#1", "YEL-VIO / BRN-BLK"], rom_draw.lines_of(mode.draw()))
        for _ in range(3):
            self.hit_and_release_switch("s_plus")
            self.advance_time_and_run(0.05)
        self.advance_time_and_run(0.05)                 # the pass draws before it reads the buttons
        self.assertEqual("#5", rom_draw.lines_of(mode.draw())[2])     # coil 4 is hidden
        n = len([e for e in self.tf.trace.of("coil") if e["on"]])
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        self.assertGreater(len([e for e in self.tf.trace.of("coil") if e["on"]]), n)
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)

    def test_f051_single_flash_lamp_test(self):
        """SINGLE FLASH LAMP TEST [0x010492b8]: the flashers only (flags & 0x1004 == 4), from coil 17."""
        from tf import rom_draw
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("FLASH LAMPS MENU", "MAIN MENU / FLASH LAMPS MENU")
        mode._open_page({"text": "SINGLE FLASH LAMP TEST"})
        self.advance_time_and_run(0.1)
        self.assertEqual(["FLASH LAMP TEST", "FLASH: DECEPTICON", "#17", "ORG / VIO-BRN"], rom_draw.lines_of(mode.draw()))
        self.hit_and_release_switch("s_minus")
        self.advance_time_and_run(0.1)
        self.assertEqual("#32", rom_draw.lines_of(mode.draw())[2])     # wraps to the last flasher
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)

    def test_f052_cycling_coil_test(self):
        """CYCLING COIL TEST [0x01046a98]: each coil's test pulse, then 0x3e passes of 2 ticks, then the next one."""
        from tf import rom_draw
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("COIL MENU", "MAIN MENU / COIL MENU")
        mode._open_page({"text": "CYCLING COIL TEST"})
        self.advance_time_and_run(0.5)
        self.assertEqual(["CYCLING COIL TEST", "TROUGH UP-KICKER", "#1", "YEL-VIO / BRN-BLK"],
                         rom_draw.lines_of(mode.draw()))
        self.advance_time_and_run(0x3e * 2 * TICK + 0.2)
        self.assertEqual("#2", rom_draw.lines_of(mode.draw())[2])
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)
