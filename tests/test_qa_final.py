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

    def _lamp_page(self, text):
        from tf import rom_draw
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("LAMP MENU", "MAIN MENU / LAMP MENU")
        mode._open_page({"text": text})
        self.advance_time_and_run(0.1)
        return mode, rom_draw

    def test_f053_single_lamp_test(self):
        """SINGLE LAMP TEST [0x0104a6c8]: the lamp, LAMP #n, its column / row wires (tables 0x00030c20 / 0x00030c14);
        leff 3 blinks it every 8 ticks; MINUS wraps to lamp 0x50; BACK leaves."""
        mode, rd = self._lamp_page("SINGLE LAMP TEST")
        self.assertEqual(["SINGLE LAMP TEST", "START BUTTON", "LAMP #1", "YEL-BRN / RED-BRN"], rd.lines_of(mode.draw()))
        self.assertIn(3, [e["id"] for e in self.tf.trace.of("leff_start")])
        lamps = self.tf.lamps
        seen = set()
        for _ in range(12):
            seen.add(lamps.composite(1))
            self.assertFalse(lamps.composite(2))
            self.advance_time_and_run(4 * TICK)
        self.assertEqual({True, False}, seen)
        self.hit_and_release_switch("s_minus")
        self.advance_time_and_run(0.1)
        self.assertEqual("LAMP #80", rd.lines_of(mode.draw())[2])
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)

    def test_f054_lamp_row_column_all_tests(self):
        """LAMP ROW TEST [0x0104aeac] (rows of 8 lamps, wire, pin and driver), LAMP COLUMN TEST [0x0104a0d0] and
        TEST ALL LAMPS [0x01049cf4] (15 passes on, 15 off)."""
        mode, rd = self._lamp_page("LAMP ROW TEST")
        self.assertEqual(["ROW LAMPS TEST", "LAMP ROW #1", "RED-BRN", "J12-P1 / Q33"], rd.lines_of(mode.draw()))
        self.assertEqual(8, len([d for d in mode.draw() if d.get("i") == 0xab]))
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        mode._open_page({"text": "LAMP COLUMN TEST"})
        self.advance_time_and_run(0.1)
        self.hit_and_release_switch("s_plus")
        self.advance_time_and_run(0.1)
        self.assertEqual(["COLUMN LAMPS TEST", "LAMP COLUMN #2", "YEL-RED", "J13-P8 / U16"], rd.lines_of(mode.draw()))
        self.assertEqual(10, len([d for d in mode.draw() if d.get("i") == 0xab]))
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        mode._open_page({"text": "TEST ALL LAMPS"})
        self.advance_time_and_run(0.1)
        self.assertEqual(["ALL LAMPS TEST", "ALL LAMPS ON"], rd.lines_of(mode.draw()))
        self.assertTrue(all(self.tf.lamps.composite(n) for n in range(1, 0x51)))
        self.advance_time_and_run(0x1e * TICK + 0.05)
        self.assertEqual(["ALL LAMPS TEST"], rd.lines_of(mode.draw()))
        self.assertFalse(any(self.tf.lamps.composite(n) for n in range(1, 0x51)))
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)

    def _diag_page(self, text):
        from tf import rom_draw
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("DIAGNOSTICS", "MAIN MENU / DIAGNOSTICS")
        mode._open_page({"text": text})
        self.advance_time_and_run(0.1)
        return mode, rom_draw

    def _leave(self, mode):
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertIsNone(mode.page)

    def test_f055_knocker_test(self):
        """KNOCKER TEST [0x010405ec]: SELECT queues a forced knock (adj_q24_option(2, 1) [0x00019378]): sound 0x019
        and ACTIVATING KNOCKER while it is pending."""
        mode, rd = self._diag_page("KNOCKER TEST")
        self.assertEqual(["KNOCKER TEST", "PRESS 'SELECT' TO ACTIVATE", "KNOCKER"], rd.lines_of(mode.draw()))
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        self.assertIn("0x019", self.sounds())
        self.assertIn("ACTIVATING KNOCKER", rd.lines_of(mode.draw()))
        self.advance_time_and_run(1)
        self.assertNotIn("ACTIVATING KNOCKER", rd.lines_of(mode.draw()))
        self._leave(mode)

    def test_f056_sound_speaker_test(self):
        """SOUND/SPEAKER TEST [0x01047ee0]: the 6 entries of 0x040e25d0; SELECT plays the call (0x01f first), BACK
        while it plays stops it and stays, BACK again leaves."""
        mode, rd = self._diag_page("SOUND/SPEAKER TEST")
        self.assertEqual(["SOUND / SPEAKER TEST", "MUSIC: DECEPTICON", "#1", "PRESS 'SELECT' TO PLAY"],
                         rd.lines_of(mode.draw()))
        self.hit_and_release_switch("s_minus")
        self.advance_time_and_run(0.1)
        self.assertEqual("#6", rd.lines_of(mode.draw())[2])
        self.hit_and_release_switch("s_plus")
        self.advance_time_and_run(0.1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        self.assertIn("0x01f", self.sounds())
        self.assertTrue(self.tf.sound_playing(0x01f))
        if self.tf.sound_playing(0x01f):
            self.assertEqual("PLAYING SOUND #1", rd.lines_of(mode.draw())[-1])
            self.hit_and_release_switch("s_back")
            self.advance_time_and_run(0.1)
            self.assertIsNotNone(mode.page)
            self.assertFalse(self.tf.sound_playing(0x01f))
        self._leave(mode)

    def test_f057_trough_dot_matrix_tests(self):
        """BALL TROUGH TEST [0x010402c0]: the trough and shooter switches in boxes, the closed ones drawn through the
        palette; SELECT serves a ball to the shooter lane. DOT MATRIX TEST [0x01047a50]: a column sweep every 6
        ticks."""
        self.fill_trough()
        mode, rd = self._diag_page("BALL TROUGH TEST")
        draw = mode.draw()
        self.assertEqual("TROUGH TEST", rd.lines_of(draw)[0])
        boxes = {(d["x"], d["y"]): d.get("inv", False) for d in draw if d.get("i") == 0xad}
        self.assertEqual(6, len(boxes))                 # 5 trough switches (the jam at 0x5f, 0), the shooter lane
        self.assertTrue(boxes[(95, 15)])                # trough #1 holds a ball
        self.assertFalse(boxes[(112, 16)])              # the shooter lane is empty
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(3)
        draw = mode.draw()
        self.assertTrue({(d["x"], d["y"]): d.get("inv", False) for d in draw if d.get("i") == 0xad}[(112, 16)])
        self._leave(mode)
        mode._open_page({"text": "DOT MATRIX TEST"})
        self.advance_time_and_run(6 * TICK * 3 + 0.01)
        bars = [d for d in mode.draw() if "r" in d and d["r"][2] == 1]
        self.assertEqual(1, len(bars))
        self.assertGreaterEqual(bars[0]["r"][0], 2)
        self._leave(mode)

    def test_f058_active_switch_and_motor_tests(self):
        """ACTIVE SWITCH TEST [0x0104b95c]: the first closed switch named; OPTIMUS PRIME MOTOR TEST [0x01025844]:
        PLUS moves the figure up (coil 30), the move times out on the virtual figure and reads FAILED."""
        self.fill_trough()
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("SWITCH MENU", "MAIN MENU / SWITCH MENU")
        mode._open_page({"text": "ACTIVE SWITCH TEST"})
        self.advance_time_and_run(0.1)
        from tf import rom_draw as rd
        lines = rd.lines_of(mode.draw())
        self.assertEqual("ACTIVE SWITCHES", lines[0])
        self.assertNotEqual("NONE", lines[1])           # the trough switches are closed
        self._leave(mode)
        mode._open_menu("GAME-SPECIFIC TESTS", "MAIN MENU / GAME-SPECIFIC TESTS")
        mode._open_page({"text": "OPTIMUS PRIME MOTOR TEST"})
        self.advance_time_and_run(0.1)
        self.assertEqual(["OPTIMUS PRIME MOTOR TEST", "44", "43", "USE -/+ OR 'SELECT' TO TEST"],
                         rd.lines_of(mode.draw()))
        self.hit_and_release_switch("s_plus")
        self.advance_time_and_run(0.1)
        self.assertIn("MOVING TO SWITCH 43", rd.lines_of(mode.draw()))
        self.advance_time_and_run(468 * TICK + 0.2)
        self.assertIn("MOVE TO SWITCH 43: FAILED", rd.lines_of(mode.draw()))
        self._leave(mode)
        self.assertFalse(self.tf.features_by_name["optimus_mech"].claimed)

    def test_f059_burn_in(self):
        """BEGIN BURN-IN [0x010476b8]: SELECT starts the coils, the display frames, leff 8 and the sounds; the time
        (NVRAM word 0x10248) counts the ticks; BACK stops and shows the time; BACK again leaves."""
        mode, rd = self._diag_page("BEGIN BURN-IN")
        self.assertEqual(["BURN-IN", "TOTAL BURN-IN TIME:", "0:00", "PRESS 'SELECT' TO START"], rd.lines_of(mode.draw()))
        coils = len([e for e in self.tf.trace.of("coil") if e["on"]])
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(2.5)
        self.assertIn(8, [e["id"] for e in self.tf.trace.of("leff_start")])
        self.assertIn("0x01f", self.sounds())
        self.assertGreater(len([e for e in self.tf.trace.of("coil") if e["on"]]), coils)
        self.assertNotEqual(self.tf.lamps.composite(1), self.tf.lamps.composite(2))     # odd / even in turn
        self.assertEqual(self.tf.lamps.composite(1), self.tf.lamps.composite(3))
        self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertEqual(["BURN-IN", "TOTAL BURN-IN TIME:", "0:02", "PRESS 'SELECT' TO START"], rd.lines_of(mode.draw()))
        self.assertFalse(self.tf.leffs.is_running(8))
        self._leave(mode)

    def test_f060_menu_icons(self):
        """post_event_5b_bitmap_draw2_3f47c [0x0103f47c]: the main menu's icons centred at y 1 (current image +0xe,
        the others +0xe + 1, table 0x00030cf8), the current item's text; a long menu scrolls between arrows 0xc /
        0xd; INSTALL REDEMPTION SYSTEM is shown with no redemption system installed (0x0002840c)."""
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        draw = mode.draw()
        self.assertEqual([(0, 10), (3, 28), (5, 46), (7, 64), (11, 82), (17, 100)],
                         [(d["i"], d["x"]) for d in draw if "i" in d])
        self.assertEqual("GO TO DIAGNOSTICS MENU", [d["t"] for d in draw if "t" in d][0])
        self.hit_and_release_switch("s_select")             # DIAGNOSTICS: 14 items, more than the row holds
        self.advance_time_and_run(0.1)
        icons = [d["i"] for d in mode.draw() if "i" in d]
        self.assertEqual(0xd, icons[-1])
        self.assertNotIn(0xc, icons)
        for _ in range(8):
            self.hit_and_release_switch("s_plus")
            self.advance_time_and_run(0.05)
        self.assertEqual([(12, 1), (31, 19), (33, 37), (34, 55), (37, 73), (39, 91), (13, 109)],
                         [(d["i"], d["x"]) for d in mode.draw() if "i" in d])     # as the ROM draws it, code run
        mode._open_menu("REDEMPTION", "MAIN MENU / GO TO REDEMPTION MENU")
        self.assertEqual("INSTALL REDEMPTION SYSTEM", mode.current()["text"])

    def test_f061_walked_screen_images(self):
        """service_walk.py frame_images: a walked screen draws the images of its last frame (ENTER CUSTOM MESSAGE:
        images 199-202 at y 26) before its texts."""
        from tf import service
        path = "MAIN MENU / GO TO UTILITIES MENU / ENTER CUSTOM MESSAGE [select]"
        draw = service.draw_of(service.screens()[path], path)
        self.assertEqual([199, 200, 201, 202], sorted(d["i"] for d in draw if "i" in d))
        self.assertTrue(any("t" in d for d in draw))
