"""Regression tests for the findings of the QA pass of 2026-11-26 (the MPF conversion against the ROM code,
docs/qa/README.md): each asserts the ROM's behaviour at the address cited."""
import glob
import os
import sys
import unittest

from tests.tf_test import TfTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "game") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "game"))
from tf import lamps, media_bridge, score_screen  # noqa: E402


class TestConversionPure(unittest.TestCase):
    def test_leff_shows_light_lamps(self):
        """The packaged shows write "ffffff"; parse_show must read them (QA L-G01): leff 1 lights lamps."""
        steps = lamps.parse_show(os.path.join(ROOT, "rom/mpf_package/config/shows/lampfx_001.yaml"))
        self.assertTrue(any(v != lamps.BLACK for s in steps for v in s[1].values()))
        shows = glob.glob(os.path.join(ROOT, "rom/mpf_package/config/shows/lampfx_*.yaml"))
        with_lamps = sum(1 for f in shows if any(s[1] for s in lamps.parse_show(f)))
        self.assertGreater(with_lamps, 40)

    def test_flash_phase_is_ten_ticks(self):
        """lamp_compositor_tick [0x000073cc]: the flash phase flips every 10 ticks (QA L-G02)."""
        self.assertEqual(10, lamps.FLASH_TICKS)

    def test_plural_pick(self):
        """vsprintf [0x0002fef0] %P1//S/%: choice n-1 clamped to the last (deff_044 op list "0 COMBOS")."""
        f = media_bridge.format_rom_text
        self.assertEqual("0 COMBOS", f("%d COMBO%P1//S/%", [0]))
        self.assertEqual("1 COMBO", f("%d COMBO%P1//S/%", [1]))
        self.assertEqual("SHOOT 11 SHOTS", f("SHOOT %u SHOT%P1//S/%", [11]))
        self.assertEqual("2ND", f("%P1/1ST/2ND/3RD/4TH/5TH//%", [], [2]))

    def test_score_font_by_value(self):
        """table 0x040c75d0 [0x0102f11c]: 1,500,000 is drawn in font 17 on row 18 (QA V-SC1)."""
        self.assertEqual((17, 18), next(e[1:] for e in score_screen.SCORE_TABLE if 1500000 >= e[0]))
        self.assertEqual((26, 21), next(e[1:] for e in score_screen.SCORE_TABLE if 0 >= e[0]))
        self.assertEqual((22, 18), next(e[1:] for e in score_screen.SCORE_TABLE if 123456789 >= e[0]))


class TestConversionGame(TfTestCase):
    def test_slam_tilt_in_attract(self):
        """slam_tilt [0x0001d534] has no game test: in attract the slam shows deff 24, leff 12, sound 0x018 and
        starts the reset task 0x39 (QA F14)."""
        self.advance_time_and_run(1)
        self.assertFalse(self.machine.game)
        self.hit_switch_and_run("s_slam_tilt", 0.1)
        self.assertIn(24, [e["id"] for e in self.tf.trace.of("deff_start")])
        self.assertTrue(self.tf.task_running(0x39))
        self.release_switch_and_run("s_slam_tilt", 6)
        self.assertFalse(self.tf.task_running(0x39))

    def test_score_status_counters(self):
        """deff 19 [0x0102f200] [0x0102fa40] with the counters of 0x0102f9ec (event 0x21, one per tick): after
        0x3e idle ticks the current score blanks 7 of every 14 ticks; the last award fades over 0x1a ticks; a 2-way
        combo slides "2-WAY" / "COMBO" up (QA V-SC2, V-SC7, V-SC8, V-SC9)."""
        T = 0.016
        st = score_screen.StatusCounters(T)
        st.clear(0.0)
        st.scored(250000, 0.0)
        boxes = lambda d: [x["r"] for x in d if "r" in x and x.get("l") == 0]
        texts = lambda d: {x["t"]: x for x in d if "t" in x}
        d = score_screen.score_draw([250000], 1, 1, "FREE PLAY", status=(st, 0.0))
        award = [x for x in d if x.get("t") == "250,000" and x["y"] == 13]
        self.assertEqual(13, award[0]["l"])                 # award at row 13, palette entry 15 = 0x1a >> 1
        self.assertEqual([], boxes(d))
        d = score_screen.score_draw([250000], 1, 1, "FREE PLAY", status=(st, 30 * T))
        self.assertEqual(2, sum(1 for x in d if x.get("t") == "250,000"))   # faded out: panel and main score
        d = score_screen.score_draw([250000], 1, 1, "FREE PLAY", status=(st, 63 * T))
        self.assertEqual([[0, 1, 40, 6], [41, 2, 87, 22]], boxes(d))     # panel row and main score blanked
        self.assertEqual([], boxes(score_screen.score_draw([250000], 1, 1, "", status=(st, 70 * T))))
        # a smaller score within 0x10 ticks keeps the award value [0x0102f998]
        st.scored(1000, 5 * T)
        self.assertEqual(250000, st.award)
        st.scored(1000, 20 * T)
        self.assertEqual(1000, st.award)
        # playfield valid: the sweep, growing from the top row of the main score's box
        self.assertEqual((2, 2), score_screen.main_box(250000, 0x3f, True))
        self.assertIsNone(score_screen.main_box(250000, 0x3e, True))
        st.combo(2, 3, 0.0)
        d = score_screen.panel_draw([250000], 1, status=(st, 3 * T))
        self.assertEqual(24, texts(d)["2-WAY"]["y"])        # (0x4b - 3) / 3
        self.assertEqual(30, texts(d)["COMBO"]["y"])
        self.assertEqual(32, texts(d)["3 COMBOS"]["y"])
        self.assertNotIn("2-WAY", texts(score_screen.panel_draw([0], 1, status=(st, 0x5e * T))))

    def test_battle_hit_sound_once(self):
        """deff_094 [0x010189a8] plays snd_play2(0x181, ..) once per hit (QA SC1)."""
        os_ = self.tf
        os_.display.own_sounds.add((94, 0x181))
        info = os_.display.media.get(94)
        if info is None or not any(c == 0x181 for _, c in info.sounds):
            self.skipTest("deff 94 op list has no 0x181")
        before = len([e for e in os_.trace.of("sound") if e.get("call") == "0x181"])
        os_.display.fg = 94
        os_.display._media(94)
        self.advance_time_and_run(1)
        after = len([e for e in os_.trace.of("sound") if e.get("call") == "0x181"])
        self.assertEqual(before, after)


class TestAttractPages(TfTestCase):
    def test_attract_walk(self):
        """deff 1 [0x0103c584] walks table 0x00030d10: pass 1 at factory settings starts GAME OVER (tick 0),
        CREDITS (127), REPLAY AT (254), the ten high scores (381-1524), the combo champions, the logo (1905), the
        animation (2139), LEARN MORE (2401); pass 2 skips GAME OVER (rom/rules/modes/attract.md, QA V001)."""
        from tf import attract_pages, rom_draw as rd
        import json
        factory = json.load(open(os.path.join(ROOT, "rom/rom_data/dmd/attract_pages.json")))["schedule_factory"]
        w = self.tf.attract_walker
        seen = []
        w.start(0.0)
        t = 0
        for _ in range(len(factory)):
            seen.append({"t": t, "entry": w.entry})
            t += attract_pages.length(w.entry) + 1
            w.started = t * 0.016
            w.next()
        self.assertEqual([(e["t"], e["entry"]) for e in factory][:len(seen)],
                         [(e["t"], e["entry"]) for e in seen][:len(factory)])
        self.assertGreaterEqual(w.passes, 2)
        self.assertNotEqual(seen[-1]["entry"], 0)
        panel = []
        self.assertIn("GAME OVER", rd.lines_of(attract_pages.screen(self.tf, 0, 10, panel)))
        lines = rd.lines_of(attract_pages.screen(self.tf, 6, 10, panel))
        self.assertEqual(["AUTOBOT", "GRAND CHAMPION", "OPT", "75,000,000"], lines)
        hs = self.tf.features_by_name["high_scores"]
        hs.entries[5] = {"name": "VIN", "score": 123456780}
        self.assertEqual(["AUTOBOT", "GRAND CHAMPION", "VIN", "123,456,780"],
                         rd.lines_of(attract_pages.screen(self.tf, 6, 10, panel)))
        self.assertIn(self.tf.media.credits_text(), rd.lines_of(attract_pages.screen(self.tf, 1, 10, panel)))


class TestMediumFixes(TfTestCase):
    def start(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)

    def sounds(self):
        return [int(e.get("call"), 16) for e in self.tf.trace.of("sound")]

    def test_ramp_entrance_sounds(self):
        """snd_play(0x273) [0x010337e8] / snd_play(0x272) [0x010338dc] on every hit (QA R-F1, SC5)."""
        self.start()
        n = (self.sounds().count(0x273), self.sounds().count(0x272))
        from tf.switches import SW
        self.hit_and_release_switch(SW[4])
        self.advance_time_and_run(0.2)
        self.hit_and_release_switch(SW[35])
        self.advance_time_and_run(0.2)
        self.assertEqual((n[0] + 1, n[1] + 1), (self.sounds().count(0x273), self.sounds().count(0x272)))

    def test_mode_start_sound_by_lit_battle(self):
        """deff 91 [0x01022608] plays 0x170 + the lit battle's bit position (QA R-F2, SC3)."""
        from tf.features import battles
        self.assertEqual(0x172, battles.MS_SOUND.get(4, 0x170))
        self.assertEqual(0x170, battles.MS_SOUND.get(1, 0x170))

    def test_validation_sets_flag_0x10(self):
        """Event 0x6a hook LAB_010060a4 sets game flag 0x10 (QA R-F4)."""
        self.start()
        self.tf._validate()
        self.assertTrue(self.tf.flag(0x10))

    def test_rule_order(self):
        """Multiballs above fast / double scoring above battles (QA V-ENG5, SC14)."""
        by_deff = {r[2]: r[0] for r in self.tf.display.rules}
        from tf.features import bumblebee, twobank, battles
        self.assertGreater(by_deff[bumblebee.DS_BG_DEFF], by_deff[twobank.FS_BG_DEFF])
        self.assertGreater(by_deff[twobank.FS_BG_DEFF], battles.RULE_PRIORITY)
        self.assertGreater(min(p for p in by_deff.values() if p >= 0x75), by_deff[bumblebee.DS_BG_DEFF])

    def test_percentage_audits_divide_by_paid_plays(self):
        """[0x00026c48] etc.: c9 x 100 / c17; SOFTWARE METER and RECENT REPLAY PERCENT are 0 (QA D-AUD)."""
        a = self.tf.audits
        for c, v in ((17, 10), (18, 10), (9, 6), (8, 30), (7, 40)):
            a.counts[c] = v
        self.assertEqual(60, a.value(16))
        self.assertEqual(0, a.value(13))
        self.assertEqual(0, a.value(72))

    def test_x_lamps_follow_multipliers(self):
        """Lamp rule [0x01023a84]: a shot's X lamp is solid at 2X or more, off below (QA L-R04)."""
        from tf.features import combos
        self.start()
        self.tf.pd.shot_mult = [1, 2, 1, 1, 1, 2]
        self.tf.rules_refresh()
        lamps = self.tf.lamps
        self.assertEqual([False, True, False, False, False, True],
                         [lamps.lamp_test(n) and not lamps.lamp_flashing(n) for n in combos.X_LAMPS])

    def test_two_bank_lamps(self):
        """Lamp layer [0x0102ede0]: the 2-bank lamps 21 and 20 flash outside multiballs and timed modes (QA L-R05)."""
        self.start()
        self.tf.rules_refresh()
        self.assertTrue(all(self.tf.lamps.lamp_flashing(n) for n in (21, 20)))

    def test_leff_switches_gi(self):
        """leff_081 [0x010119d8] switches the GI (owner 0x000314c4): off at tick 9, on at its end (QA L-G07)."""
        self.start()
        from tf.os_layer import TICK
        lamps = self.tf.lamps
        lamps.leff_play(81)
        self.advance_time_and_run(10 * TICK)
        self.assertEqual(0, lamps.gi)
        lamps.leff_end(81)
        self.assertEqual(1, lamps.gi)

    def test_leff_owns_its_lamp_group(self):
        """leff_start [0x00007c10]: a leff with a lamp group owns the group's lamps from its start (QA L-G08)."""
        self.start()
        leff = next(l for l, c in sorted(self.tf.leffs.claims.items()) if c[0] and l in self.tf.lamps.leff_info)
        self.tf.lamps.leff_play(leff)
        entry = self.tf.lamps.leff_players.get(leff)
        if entry:
            self.assertTrue(set(self.tf.leffs.claims[leff][0]) <= entry[1].mask)

    def test_code_leffs_lamps_and_flashers(self):
        """The code leffs (QA L-G code leffs): leff_097 [0x0102dda4] toggles the caller's lamp (+0x30) 10 times, 2
        ticks apart, then ends; leff_139 (fn 0x0100999c) holds it on 8 ticks; leff_044 [0x01027ffc] ramps coil 0x1f
        every 4 ticks while the playfield is valid."""
        self.start()
        from tf.os_layer import TICK
        lamps = self.tf.lamps
        lamps.leff_play(97, lamp=50)
        layer = lamps.leff_players[97][1]
        self.assertEqual(({50}, {50}), (layer.mask, layer.image))
        self.advance_time_and_run(2 * TICK + 0.001)
        self.assertEqual(set(), layer.image)
        self.advance_time_and_run(20 * TICK)
        self.assertNotIn(97, lamps.leff_players)
        lamps.leff_play(139, lamp=48)
        self.assertIn(48, lamps.leff_players[139][1].image)
        self.advance_time_and_run(9 * TICK)
        self.assertNotIn(139, lamps.leff_players)
        pulsed = []
        orig = lamps.flasher
        lamps.flasher = lambda name, ms=30, owner=None, power=None: pulsed.append((name, ms, power))
        try:
            self.tf.pf_valid = True
            lamps.leff_play(44)
            self.advance_time_and_run(9 * TICK)
            lamps.leff_end(44)
        finally:
            lamps.flasher = orig
        names = {num: name for name, num in lamps.coil_numbers.items()}
        self.assertGreaterEqual(len(pulsed), 2)
        self.assertEqual((names[0x1f], 100), pulsed[0][:2])
        self.assertLess(pulsed[0][2], pulsed[1][2])

    def test_optimus_music_gi_beat(self):
        """leff_020 [0x01006f1c]: the GI blinks 2 ticks on the battle music's beat (table 0x040c5edc)."""
        self.start()
        from tf.os_layer import TICK
        lamps = self.tf.lamps
        self.tf.sound(0x31)
        self.assertTrue(self.tf.sound_playing(0x31))
        changes = []
        self.machine.events.add_handler("tf_gi", lambda **kwargs: changes.append((self.tf.now, kwargs["on"])))
        t0 = self.tf.now
        lamps.leff_play(20)
        self.advance_time_and_run(60 * TICK)
        offs = [round((t - t0) / TICK) for t, on in changes if not on]
        self.assertEqual(0, offs[0])
        self.assertTrue(any(abs(o - 37) <= 1 for o in offs[1:]), offs)
        lamps.leff_end(20)
        self.assertEqual(1, lamps.gi)

    def test_lock_lamps_flash_while_lock_lit(self):
        """Lamp rule [0x0100b228]: lamps 29, 57, 58 flash while a lock is lit, else off (QA L-R02)."""
        self.start()
        lamps = self.tf.lamps
        self.tf.pd.mtl_lit = 1
        self.tf.rules_refresh()
        self.assertTrue(all(lamps.lamp_flashing(n) for n in (29, 57, 58)))
        self.tf.pd.mtl_lit = 0
        self.tf.rules_refresh()
        self.assertFalse(any(lamps.lamp_test(n) for n in (29, 57, 58)))

    def test_virtual_lock_keeps_no_ball(self):
        """adj 69 MEGATRON M.B. VIRTUAL LOCK = YES: the device's target count is 0 [0x0100a278]; the lock counts and
        the ball is kicked back (QA D-ADJ-69-use)."""
        self.start()
        mtl = self.tf.features_by_name["megatron"]
        saved = self.tf.adj[69]
        self.tf.adj[69] = 1
        self.tf.pd.mtl_lit, self.tf.pd.mtl_locked = 1, 0
        mtl.pending = 1
        mtl._handle(back_door=False)
        self.assertEqual((1, 0), (self.tf.pd.mtl_locked, mtl.locked_held))
        self.tf.adj[69] = saved

    def test_locked_balls_kicked_in_another_multiball(self):
        """[0x0100a1f8] -> [0x0103a2c0] -> device loop [0x010391a0]: the first ball as any kickout after the 46-tick
        settle, each next one 62 + 31 ticks later with 0x13c and leff 24 ([0x0100a3b8] case 9)."""
        self.start()
        mtl = self.tf.features_by_name["megatron"]
        released = []
        self.machine.events.add_handler("tf_megatron_release", lambda **kwargs: released.append(self.tf.now))
        mtl.locked_held = 2
        self.tf.flag_set(0x3c)
        mtl._keep_check()
        self.advance_time_and_run(5)
        self.assertEqual(2, len(released))
        self.assertAlmostEqual(93 * 0.016, released[1] - released[0], delta=0.05)
        self.tf.flag_clear(0x3c)

    def test_jackpot_speech_samples_in_order(self):
        """The jackpot deffs play their speech's samples in turn from the side's counter, 0 past the call's count
        ([0x0100c430] 0xca / 0xd2, [0x0100e29c] 0xe4 / 0xf7; QA M12)."""
        self.start()
        side = self.tf.features_by_name["megatron"].sides[1]          # the Autobot side
        side.seq = 0
        n = len(self.tf.sample_lengths(0xd2))
        picks = [side.sample(0xd2) for _ in range(n + 1)]
        self.assertEqual(list(range(n)) + [0], picks)
        side.seq = 0                                   # the Decepticon's Megatron shot: 0, not advanced
        self.assertEqual((0, 0), (side.sample(0xe4, advance=False), side.seq))

    def test_requirement_inserts(self):
        """Lamp rule [0x01035ea8]: the 11 requirement inserts, solid completed, flashing collected (QA L-R07)."""
        from tf.features import wizard
        self.start()
        req = [[0, 0] for _ in range(11)]
        req[0] = [1, 0]
        req[5] = [1, 1]
        self.tf.pd.wiz_req = req
        self.tf.rules_refresh()
        lamps = self.tf.lamps
        self.assertTrue(lamps.lamp_flashing(27))
        self.assertTrue(lamps.lamp_test(22) and not lamps.lamp_flashing(22))
        self.assertFalse(lamps.lamp_test(28))
        self.assertEqual(wizard.REQ_LAMPS[1:5], (7, 6, 5, 4))

    def test_bumper_lamps(self):
        """leff_029 [0x0102d138]: a pop's own leff blinks its bumper lamp 60 / 61 / 62 (QA L-I60-62)."""
        from tf.switches import SW
        self.start()
        seen = set()
        self.hit_and_release_switch(SW[30])
        for _ in range(10):
            self.advance_time_and_run(0.016)
            if self.tf.lamps.lights.get(60) and self.tf.lamps.lights[60].stack:
                seen.add(60)
        self.assertIn(60, seen)

    def test_rule_leff_table(self):
        """leff_rules.csv: the rule records' mask and end-of-ball kill (game_flow.md 5.8, QA L-G06)."""
        info = self.tf.leff_rule_info
        self.assertEqual((0x20, False), info[37])        # kept: task flag 0x100
        self.assertEqual((0x20, True), info[40])         # killed by task_kill(0, 0x100) [0x00019e44]

    def test_hint_speech(self):
        """Task 0xc6 [0x010250f4]: the Allspark shot's hint 0x145 plays 125 ticks after hint_speech_start (QA SC4)."""
        self.start()
        self.tf.hook("hint_set_allspark")
        self.assertTrue(self.tf.flag(0x48))
        n = self.sounds().count(0x145)
        self.assertTrue(self.tf.hook("hint_start"))
        self.advance_time_and_run(2.1)
        self.assertEqual(n + 1, self.sounds().count(0x145))
        self.assertEqual(1, self.tf.pd.hint_index)

    def test_sound_voices(self):
        """snd_start_sample [0x00024ae4]: a speech call of priority 1 without take-over (0x0b1) is refused while
        another such speech holds voice 0x02; a priority 193 take-over speech (0x11e) takes the voice and
        stops it (QA SC16)."""
        self.start()
        tf = self.tf
        tf.sound_refused(0x0b1)
        tf._slots = [x for x in tf._slots if not x["voices"] & 0x02]   # nothing else on the speech voice
        self.assertIsNotNone(tf.sound(0x0b1))
        self.assertTrue(tf.sound_refused(0x0b1))
        self.assertIsNone(tf.sound(0x0b1))
        self.assertFalse(tf.sound_refused(0x11e))
        self.assertIsNotNone(tf.sound(0x11e))
        self.assertEqual([0x11e], [s["call"] for s in tf._slots if s["voices"] & 0x02])

    def test_intro_flipper_skip(self):
        """[0x01006480]: one flipper held, the other pressed, ends a show deff (QA V-ENG4)."""
        self.start()
        self.advance_time_and_run(4)
        self.tf.show(0x73, 140, values=[1])
        self.advance_time_and_run(0.3)
        self.assertEqual(140, self.tf.display.fg)
        self.hit_switch_and_run("s_l_flipper_button", 0.1)
        self.hit_and_release_switch("s_r_flipper_button")
        self.advance_time_and_run(0.1)
        self.release_switch_and_run("s_l_flipper_button", 0.1)
        self.assertNotEqual(140, self.tf.display.fg)
        self.assertIsNone(self.tf.display.show)

    def test_hit_deff_variants(self):
        """deff 94 [0x010189a8]: the shots left (+0x34, table 0x040c6a60) pick the animation, its length and
        sounds (QA SC2)."""
        from tf.display import deff_variant
        from tf.os_layer import TICK
        v3, v8, fin = deff_variant(94, "shots3"), deff_variant(94, "shots8"), deff_variant(94, "final")
        self.assertAlmostEqual(188 * TICK, v3.seconds)
        self.assertIn((94 * TICK, 389), v3.sounds)
        self.assertIn((266 * TICK, 390), v8.sounds)
        self.assertAlmostEqual(430 * TICK, fin.seconds)
        self.assertIsNone(deff_variant(94, "shots9"))
        self.start()
        self.advance_time_and_run(4)
        self.tf.display.start(94, variant="shots3", values=[0])
        self.advance_time_and_run(94 * TICK + 0.05)
        self.assertIn(389, self.sounds())

    def test_bonus_multiplier_pages(self):
        """[0x01000ffc]: a multiplier above 1 adds task_sleep(4) and one page per multiplier (8 frames, 4 from 6X),
        then 0x76 (QA SC9; scoring.jsonl 2X: 0x79 at tick 79 of deff 25)."""
        from tf.features.bonus import x_extra_ticks
        self.assertEqual((0, 12, 36, 44), (x_extra_ticks(1), x_extra_ticks(2), x_extra_ticks(5), x_extra_ticks(7)))

    def test_side_award_speech(self):
        """deff 83 [0x01011750]: routine +0x34 of table 0x040c6770 / 0x040c67a0 picks the speech (QA SC10)."""
        from tf.display import deff_variant
        self.assertIn(0x11e, [c for _, c in deff_variant(83, "decepticon_anim2").sounds])
        self.assertIn(0x11a, [c for _, c in deff_variant(83, "decepticon_anim9").sounds])
        self.assertIn(0x125, [c for _, c in deff_variant(83, "autobot_anim9").sounds])

    def test_service_menu(self):
        """SELECT opens the service menu (0x0000eb3c, deff 3 [0x0103f960]); PLUS walks a menu, SELECT edits an
        adjustment and stores it, BACK climbs out (QA D-SM-MODE; screens from service_screens.json)."""
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(0.1)
        mode = self.machine.modes["tf_service"]
        self.assertTrue(mode.active)
        self.assertTrue(self.tf.in_service)
        from tf import rom_draw
        texts = lambda: rom_draw.lines_of(mode.draw())       # noqa: E731
        self.assertIn("SERVICE MENU", texts())
        self.hit_and_release_switch("s_select")
        self.assertEqual(["GO TO DIAGNOSTICS MENU"], texts())
        for _ in range(2):
            self.hit_and_release_switch("s_plus")
        self.assertEqual(["GO TO ADJUSTMENTS MENU"], texts())
        self.hit_and_release_switch("s_select")
        self.hit_and_release_switch("s_plus")
        self.hit_and_release_switch("s_select")             # FEATURE ADJUSTMENTS
        self.assertEqual("FEATURE ADJUSTMENT #1", texts()[0])
        num = mode.page["list"][0]
        before = self.tf.adj[num]
        self.hit_and_release_switch("s_select")             # edit
        self.hit_and_release_switch("s_plus")
        self.hit_and_release_switch("s_select")             # store
        self.assertNotEqual(before, self.tf.adj[num])
        self.tf.adj[num] = before
        for _ in range(3):
            self.hit_and_release_switch("s_back")
        self.advance_time_and_run(0.1)
        self.assertFalse(mode.active)
        self.assertFalse(self.tf.in_service)

    def test_custom_pricing_editor(self):
        """SET CUSTOM PRICING [0x01044f7c]: credits per unit step, INSTALL after a step that gives credits,
        coin_pricing_set_48a8 [0x000048a8] stores the ladder; adj 28 = CUSTOM then credits by it (QA D-CR-CUSTOM)."""
        from tf.service import CustomPricing, price_summary
        cm = self.tf.credit_model
        saved = (list(cm.custom_ladder), cm.custom_valid, self.tf.adj[28])
        cm.custom_ladder, cm.custom_valid = [], False
        ed = CustomPricing(cm)
        self.assertEqual((0, False), (ed.pos, ed.end))
        ed.select()                         # step 1: 0 credits
        ed.plus()                           # step 2: 1 credit
        self.assertIn("$0.50", [d.get("t") for d in ed.draw()])
        ed.select()                         # step 3
        ed.minus()                          # 0 -> INSTALL (step 2 gives credits)
        self.assertTrue(ed.end)
        self.assertTrue(ed.select())
        self.assertEqual(([0, 1], True), (cm.custom_ladder, cm.custom_valid))
        self.assertEqual("1/0.50", price_summary([0, 1], 2, lambda u: cm.unit_money(u, "plain")))
        self.tf.adj[28] = 68
        self.assertEqual((0, 1), cm.pricing()[1])
        cm.custom_ladder, cm.custom_valid, self.tf.adj[28] = saved
        # from the menu: UTILITIES > SET CUSTOM PRICING (adj_game_pricing [0x010457c4]), then BACK leaves it
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        mode = self.machine.modes["tf_service"]
        mode.title = False
        mode._open_menu("UTILITIES", "MAIN MENU / UTILITIES")
        mode._open_page({"text": "SET CUSTOM PRICING", "kind": "item"})
        self.advance_time_and_run(0.2)
        self.assertEqual("custom", mode.page["kind"])
        self.hit_and_release_switch("s_plus")
        self.hit_and_release_switch("s_select")
        self.hit_and_release_switch("s_minus")       # INSTALL
        self.hit_and_release_switch("s_select")       # installs
        self.hit_and_release_switch("s_select")       # continue
        self.assertEqual((68, [1]), (self.tf.adj[28], cm.custom_ladder))
        self.assertIsNone(mode.page)
        cm.custom_ladder, cm.custom_valid, self.tf.adj[28] = saved
        mode.stop()

    def test_total_earnings(self):
        """TOTAL EARNINGS [0x00026e7c]: units counter 7 x the current pricing's unit value, in its money format
        [0x00026f74] ("USD 3.25" for 13 units at USA 10; QA D-AUD-11)."""
        self.tf.audits.counts[7] = 13
        self.assertEqual("USD 3.25", self.tf.audits.text(11))
        self.tf.audits.counts[7] = 0
        self.assertEqual("USD 0.00", self.tf.audits.text(11))

    def test_sample_pick_memory(self):
        """snd_resolve_call [0x00025044]: a call's no-repeat memory (+0x0e) and the speech ring (0x00038354, the
        last 9 speech samples) steer the pick: 7 plays of 0x0b1 (7 samples, memory 4, speech) are 7 different
        samples (QA SC16)."""
        picks = []
        for _ in range(7):
            i = self.tf._sample_pick(0xb1, 7)
            self.tf._sample_remember(0xb1, i)
            picks.append(i)
        self.assertEqual(7, len(set(picks)))

    def test_battle_shoot_lit_shot(self):
        """0 shots left: the battle background draws "SHOOT LIT SHOT" (deff 97 [0x0101f580]); Devastator in state
        1 "SHOOT R. ORBIT" (msg 0x645 [0x01016d7c]) (QA V097-V121)."""
        self.start()
        from tf.display import deff_variant
        if not deff_variant(97, "lit"):
            self.skipTest("no deff 97 lit op list")
        b = next(x for x in self.tf.features_by_name["battles"].battles if x.bg == 97)
        self.tf.pd[b.left_key] = 0
        self.assertEqual("lit", b.background_values()["variant"])          # its code run with 0 shots left
        self.tf.pd[b.left_key] = 3
        self.assertIsNone(b.background_values()["variant"])
        self.assertEqual("SHOOT 3 SHOTS", self.tf.media.deff_lines(97, {})["values"][1])
        dv = next(x for x in self.tf.features_by_name["battles"].battles if x.bg == 105)
        dv.active, dv.state = True, 1
        self.assertEqual("rover", dv.background_values()["variant"])       # DAT_000313b4 = 1: msg 0x645
        dv.active = False

    def test_high_score_lists(self):
        """Tables 0x040cf948 / 0x040cfc48: 17 entries in 5 lists, the side lists and the two combo champions with
        adj 90-95 (QA D-HS-COMBO)."""
        hs = self.tf.features_by_name["high_scores"]
        hs.reset(3)
        self.assertEqual(17, len(hs.entries))
        self.assertEqual(("OPT", 20), (hs.entries[5]["name"], hs.entries[15]["score"]))
        self.assertEqual("TRIPLE 5-WAY", hs.score_text(16, (5 << 16) | 3))
        self.assertEqual("21 COMBOS", hs.score_text(15, 21))
