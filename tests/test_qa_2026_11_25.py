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


class TestPlayfield(QaCase):
    def hit(self, name, wait=0.5):
        before = self.score()
        self.hit_and_release_switch(name)
        self.advance_time_and_run(wait)
        return self.score() - before

    def test_lit_multiplier_doubles_its_own_combo(self):
        """FUN_010237ac(shot) runs first in every shot handler [0x01033824]: the shot that takes the lit 2X
        scores its combo at 2X (QA P2)."""
        self.start()
        self.hit("s_right_orbit_spinner")                   # a force switch ends the skill shots
        self.hit("s_l_ramp_exit")                           # combo window opens
        self.tf.pd.mult_lit = True
        before = len(self.tf.trace.of("score_add"))
        self.hit("s_r_ramp_exit")
        self.assertEqual(2, self.tf.pd.shot_mult[4])
        self.assertIn(300000, [e.get("points") for e in self.tf.trace.of("score_add")[before:]])

    def test_slings_and_pops_end_the_skill_shots(self):
        """Event 0x6b hook 0x010313cc counts slings and pops: 3 distinct end both skill shots (QA P3)."""
        self.start()
        for name in ("s_left_slingshot", "s_right_slingshot", "s_top_bumper"):
            self.hit(name)
        skill = self.tf.features_by_name["skill_shot"]
        self.assertFalse(skill.top or skill.super)
        self.assertEqual(30, self.hit("s_megatron_back_door"))

    def test_item_10_offered_with_all_shots_at_2x(self):
        """0x01023494 gives item 10 weight 0 only when a multiplier is lit or the roving 3X runs (QA P4)."""
        self.start()
        allspark = self.tf.features_by_name["allspark"]
        self.tf.pd.shot_mult = [2] * 6
        self.tf.pd.allspark_last = 0
        self.assertGreater(allspark.weights()[9], 0)
        self.tf.pd.mult_lit = True
        self.assertEqual(0, allspark.weights()[9])

    def test_double_and_fast_scoring_starts_clear_add_time_flag(self):
        """game_flag_clear(0x13) in 0x010039a0 and 0x01004394 (QA P5)."""
        self.start()
        for name in ("bumblebee", "twobank"):
            self.tf.flag_set(0x13)
            self.tf.features_by_name[name].start()
            self.assertFalse(self.tf.flag(0x13), name)
            self.tf.features_by_name[name].stop()

    def test_fast_scoring_targets_and_tail(self):
        """[0x010047b8]: +1,000 on the first target of a cycle only, +10 counts on the completing hit; the
        250-tick tail is no timed mode and +10 there restarts the countdown (QA P8, P9)."""
        self.start()
        fs = self.tf.features_by_name["twobank"]
        fs.start()
        self.advance_time_and_run(6)
        value, count = fs.value, fs.count
        fs._fast_target(50)
        self.assertEqual(value + 1000, fs.value)
        fs._fast_target(37)
        self.assertEqual((value + 1000, min(count + 10, 90)), (fs.value, fs.count))
        fs.counting, fs.count = False, 0                  # in the tail
        self.assertFalse(self.tf.timed_mode_running())
        fs._fast_target(50)
        self.assertEqual(value + 1000, fs.value)          # no +1,000 outside the countdown
        fs._fast_target(37)
        self.assertTrue(fs.counting)
        self.assertEqual(10, fs.count)
        fs.stop()

    def test_pops_hold_the_fast_scoring_countdown(self):
        """Pops start the 156-tick hold task 0x59 [0x01032f8c], battle or not (QA P7)."""
        self.start()
        fs = self.tf.features_by_name["twobank"]
        fs.start()
        self.advance_time_and_run(6)
        count = fs.count
        for _ in range(8):
            self.hit("s_top_bumper", 0.75)
        self.assertEqual(count, fs.count)
        fs.stop()

    def test_center_lane_locked_after_an_optimus_hit(self):
        """Task 0x54 [0x01033d3c] (62 ticks): the center lane right after an Optimus hit scores only its 30
        [0x01033b3c], a repeat Optimus hit nothing (QA M5, P11)."""
        self.start()
        self.hit("s_right_orbit_spinner")
        self.hit_and_release_switch("s_optimus_prime")
        self.advance_time_and_run(0.15)
        self.assertTrue(self.tf.task_running(0x54))
        self.assertEqual(30, self.hit("s_center_lane", 0.1))
        self.assertEqual(0, self.hit("s_optimus_prime", 0.2))

    def test_sw6_gives_no_fast_scoring_award(self):
        """sw 6's handler [0x010332e4] calls neither FUN_010047b8 nor FUN_01003a64 (QA P10)."""
        self.start()
        fs = self.tf.features_by_name["twobank"]
        fs.start()
        self.advance_time_and_run(6)
        total = fs.total
        self.hit("s_left_orbit_top")
        self.assertEqual(total, fs.total)
        fs.stop()


class TestOsFixes(QaCase):
    def test_held_plumb_bob_tilts(self):
        """FUN_0001dc58 starts task 0x2e [0x0001dc14]: a bob held closed warns every 62 ticks, then tilts (QA F4)."""
        self.start()
        self.hit_switch_and_run("s_tilt_pendulum", 62 * TICK * 2 + 0.2)
        self.assertTrue(self.tf.tilted)
        self.release_switch_and_run("s_tilt_pendulum", 0.1)

    def test_bob_counts_while_the_ball_ends(self):
        """The bob is ignored only while gf_state & 0x310, so a tilt during the end of ball removes the bonus
        (QA F5, [0x00019e44])."""
        self.start()
        self.tf.state |= 0x04                              # end of ball
        self.hit_and_release_switch("s_tilt_pendulum")
        self.advance_time_and_run(0.1)
        self.assertEqual(1, self.tf.tilt_warnings)
        self.tf.state &= ~0x04

    def test_equal_priority_deff_needs_flags(self):
        """deff_start_core [0x00020498]: an equal priority start replaces the running deff only when its
        flags & 3 (QA F6). Deffs 28 (flags & 3 = 0) and 13 (flags & 3 set) are both priority 240."""
        self.start()
        disp = self.tf.display
        disp.start(28)
        disp.start(13)
        self.assertEqual(28, disp.fg)
        disp.start(13)
        disp.fg, disp.fg_prio = 13, disp.prio[13]
        disp.start(28)
        self.assertEqual(28, disp.fg)

    def test_end_of_ball_waits_the_longest_hook(self):
        """[0x00019e44]: the wait is the longest flag-0x2000 task, capped at DAT_00033324 = 937 ticks (QA F10)."""
        from game.tf import os_layer
        self.start()
        hooks = self.tf.hooks
        saved = list(hooks.get("ball_end_wait", ()))
        hooks["ball_end_wait"] = [lambda: 300, lambda: 100]
        waits = [fn() for fn in hooks["ball_end_wait"]]
        self.assertEqual(300, min(max(waits), os_layer.END_BALL_WAIT_MAX))
        hooks["ball_end_wait"] = saved
        self.assertEqual(937, os_layer.END_BALL_WAIT_MAX)

    def test_lock_entry_adds_a_bonus_count(self):
        """[0x0100a31c] inlines 0x01032d2c: FUN_01000dfc(1), +1 bonus count (QA F11)."""
        self.start()
        count = self.tf.pd.get("bonus_count", 0)
        self.tf.features_by_name["megatron"]._handle(back_door=True)
        self.assertEqual(count + 1, self.tf.pd.get("bonus_count", 0))

    def test_super_lit_flashers(self):
        """leff_063 [0x0100d038]: while the Autobot super is lit (rule FUN_0100d004), coil group 26 (the Megatron
        flasher, table 0x040cf65c) pulses every 8 ticks on a valid playfield (QA M6)."""
        self.start()
        self.hit_and_release_switch("s_right_orbit_spinner")
        self.advance_time_and_run(0.5)
        side = self.tf.features_by_name["megatron"].sides[1]
        side.active, side.phase = True, 3
        self.tf.request_refresh()
        self.advance_time_and_run(0.1)
        before = len([e for e in self.tf.trace.of("coil") if e.get("coil") == 28 and e.get("on")])
        self.advance_time_and_run(8 * TICK * 10)
        after = len([e for e in self.tf.trace.of("coil") if e.get("coil") == 28 and e.get("on")])
        self.assertGreaterEqual(after - before, 8)
        side.active = False

    def test_add_a_ball_offered_in_the_first_156_end_ticks(self):
        """FUN_01006760: a multiball flag or the end task under its first id (0xbb sleeps 156 ticks, then renames
        itself 0xbc [0x0100c7e8]); the award is FUN_0103aff4(1, 0, 312, 187) [0x01024a60] (QA M7)."""
        self.start()
        side = self.tf.features_by_name["megatron"].sides[1]
        allspark = self.tf.features_by_name["allspark"]
        side.active = side.alive = True
        self.tf.flag_set(side.flag)
        side.multiball_end()
        self.advance_time_and_run(100 * TICK)
        self.assertTrue(self.tf.add_ball_open())
        self.assertGreater(allspark.weights()[4], 0)
        allspark.run(5)
        mb = self.tf.trace.of("multiball_start")[-1]
        self.assertEqual((312, 187), (mb.get("save_ticks"), mb.get("grace_ticks")))
        self.assertTrue(side.active and self.tf.flag(0x14))
        self.tf.flag_clear(0x14)
        side.multiball_end()
        self.advance_time_and_run(170 * TICK)
        self.assertFalse(self.tf.add_ball_open())
        self.assertEqual(0, allspark.weights()[4])

    def test_starscream_pair_moves_each_second(self):
        """FUN_01017824: with fewer than 6 shots left the lit pair moves each counted second, not within 93
        ticks of a ramp entrance (tokens 0xc / 0xd set by [0x010337e8] / [0x010338dc]) (QA M9)."""
        self.start()
        ss = self.tf.features_by_name["battles"].battles[0]
        ss.setup()
        ss.pd[ss.left_key] = 5
        ss.seconds = 20
        pair = ss.pair
        ss.second()
        self.assertEqual((pair + 1) % 8, ss.pair)
        self.hit_and_release_switch("s_l_ramp_entrance")
        self.advance_time_and_run(0.1)
        ss.second()
        self.assertEqual((pair + 1) % 8, ss.pair)
        ss.pd[ss.left_key] = 6
        self.advance_time_and_run(2)
        ss.second()
        self.assertEqual((pair + 1) % 8, ss.pair)


class TestLowFixes(QaCase):
    def test_ball_save_length(self):
        """ball_save_task [0x00017a28]: adj 38 = 5 saves 5 x 62 = 310 -> 52 sleeps of 6 = 312 ticks (QA F8)."""
        self.start()
        self.hit_and_release_switch("s_right_orbit_spinner")
        self.advance_time_and_run(0.05)
        self.tf._arm_ball_save()
        start = self.tf.now
        while self.tf.ball_save == "armed" and self.tf.now - start < 10:
            self.advance_time_and_run(TICK)
        self.assertAlmostEqual(312, round((self.tf.now - start) / TICK), delta=2)

    def test_skill_shot_second_lane_lamp(self):
        """The second lane award of a top-lane skill shot lights 50 / 49 [0x010335d0] / [0x0103361c] (QA P13)."""
        self.start()
        lanes = self.tf.features_by_name["lanes"]
        lanes.lane_award(8, 50)
        self.assertIn(50, lanes.lit("left"))
        self.assertNotIn(51, lanes.lit("left"))

    def test_spinner_sample_reset_each_ball(self):
        """[0x01032484]: the spinner sound's sample index back to 0 at each ball (QA P17)."""
        self.start()
        spinner = self.tf.features_by_name["spinner"]
        spinner.sample = 3
        spinner.ball_start()
        self.assertEqual(0, spinner.sample)

    def test_lock_lit_rearms_every_player(self):
        """[0x0100af0c]: DAT_02111d4c = DAT_02111d48 re-arms every player's count; deff 139 gets the locked
        count (QA M10, M15)."""
        self.start()
        mt = self.tf.features_by_name["megatron"]
        pd = self.tf.pd
        pd.mtl_level, pd.mtl_need, pd.mtl_count, pd.mtl_lit, pd.mtl_locked = 3, 2, 1, 0, 1
        mt.blocked = lambda: False
        mt.lock_completion()
        self.assertEqual((1, 2), (pd.mtl_lit, pd.mtl_count))
        self.assertTrue(all(p.get("mtl_count") == p.get("mtl_need", 1) for p in self.tf.players))
