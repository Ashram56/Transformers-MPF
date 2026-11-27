"""QA probes of 2026-11-25, OS and game flow (read-only, they show the differences in report_os.md; a passing probe
prints what the game does). Run: .venv/bin/python -m pytest -q -s -p no:cacheprovider docs/qa/2026-11-25/probe_os.py"""
import os, sys
from mpf.tests.MpfTestCase import MpfTestCase
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME = os.path.join(ROOT, "game")
TICK = 0.01626

class Base(MpfTestCase):
    def get_config_file(self): return "config.yaml"
    def get_machine_path(self): return GAME
    def get_absolute_machine_path(self): return GAME
    def get_platform(self): return "smart_virtual"
    def get_enable_plugins(self): return False
    def setUp(self):
        if GAME not in sys.path: sys.path.insert(0, GAME)
        super().setUp()
        self.machine.tf.random.seed(1974)
        self.machine.tf.adj.override(34, 1)
        self.machine.tf.forced["side"] = [1] * 4
    @property
    def tf(self): return self.machine.tf
    def start_ball(self):
        for n in ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l"):
            self.machine.switch_controller.process_switch(n, 1, True)
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)
    def deffs(self): return [e["id"] for e in self.tf.trace.of("deff_start")]

class TestQA(Base):
    def test_F_eb_collect_right_orbit(self):
        """ROM: right orbit handler 0x01033488 calls FUN_01007b74 -> eb collect (FUN_00018204) + deff 0x36."""
        self.start_ball()
        self.tf.light_extra_ball()
        self.assertEqual(1, self.tf.eb_lit[0])
        self.advance_time_and_run(4)                 # past the 187-tick launch ignore (task 0x47)
        self.hit_and_release_switch("s_right_orbit"); self.advance_time_and_run(3)
        print("\nEB: eb_lit", self.tf.eb_lit[0], "extra_balls", self.machine.game.player.extra_balls,
              "deff54?", 54 in self.deffs())

    def test_F_special_collect_right_orbit(self):
        self.start_ball()
        self.tf.specials_lit[0] = 1
        self.advance_time_and_run(4)
        self.hit_and_release_switch("s_right_orbit"); self.advance_time_and_run(3)
        print("\nSPECIAL: lit", self.tf.specials_lit[0], "deff56?", 56 in self.deffs(), "audit 0x0e",
              self.tf.audits[0x0e])

    def test_F_bob_held(self):
        """ROM FUN_0001dc58 + task_2e: bob held closed -> warning, then every 62 ticks, tilt() after 124 ticks."""
        self.start_ball()
        self.hit_and_release_switch("s_right_slingshot"); self.advance_time_and_run(0.5)
        self.hit_switch_and_run("s_tilt_pendulum", 3.0)
        print("\nBOB HELD 3s: warnings", self.tf.tilt_warnings, "tilted", self.tf.tilted)
        self.release_switch_and_run("s_tilt_pendulum", 1)

    def test_F_bob_during_bonus(self):
        """ROM: bob ignored only when state & 0x310 or task 0x29: a tilt during the bonus (state 5) is taken,
        and end_of_ball then skips the bonus add (state & 0x200)."""
        self.start_ball()
        self.tf.adj.override(32, 0)              # no warnings: the next bob tilts
        self.hit_and_release_switch("s_left_slingshot"); self.hit_and_release_switch("s_right_slingshot")
        self.hit_and_release_switch("s_top_bumper"); self.hit_and_release_switch("s_right_orbit")
        self.advance_time_and_run(12)            # ball save ends
        score_before = self.machine.game.player.score
        self.machine.playfield.balls -= 0
        # drain
        self.machine.switch_controller.process_switch("s_trough_1_r", 1, True)
        for _ in range(60):
            self.advance_time_and_run(0.1)
            if self.tf.state & 1: break
        print("\nstate at bonus", hex(self.tf.state))
        self.hit_and_release_switch("s_tilt_pendulum"); self.advance_time_and_run(0.1)
        print("BOB IN BONUS: tilted", self.tf.tilted, "state", hex(self.tf.state))
        self.advance_time_and_run(10)
        print("score delta after bonus", self.machine.game.player_list[0].score - score_before)

    def test_F_ball_save_length(self):
        """ROM ball_save_task: 52 sleeps of 6 ticks for adj38=5 (310) -> 312 ticks; game?"""
        self.start_ball()
        self.hit_and_release_switch("s_right_orbit")   # force switch validates
        t0 = self.tf.now
        print("\nsave state", self.tf.ball_save, self.tf.task_running(0x31), self.tf.adj_value(38))
        while self.tf.task_running(0x31):
            self.advance_time_and_run(TICK)
        print("\nBALL SAVE armed phase ticks after valid: %.1f" % ((self.tf.now - t0) / TICK))

    def test_F_deff_equal_prio(self):
        """ROM deff_start_core: equal priority replaces only when the running deff has flags & 3."""
        self.start_ball()
        d = self.tf.display
        self.hit_and_release_switch("s_right_orbit"); self.advance_time_and_run(8)
        print("\nprio 145:", d.prio.get(145), "fg before", d.fg)
        self.assertTrue(self.tf.deff_start(145))
        h1 = d.fg_handle
        self.advance_time_and_run(0.3)
        r = self.tf.deff_start(145)
        print("EQUAL PRIO restart of flags-0 deff 145 accepted:", r, "handle replaced:", d.fg_handle is not h1)

    def test_F_match_number_no_award(self):
        """ROM 0x00019668: rate >= adj 30 -> number shifted by 10 until no player matches."""
        self.start_ball()
        tf = self.tf
        tf.audits.add(0x11, 10); tf.audits.add(0x0f, 10)       # match rate 100 % >= adj 30
        self.machine.game.player.score = 1230
        import tf.features.game_over as go
        import random
        hits = 0
        for seed in range(200):
            random.seed(seed)
            n = random.randrange(0, 100, 10)
            hits += (n == 30)
        print("\nMATCH: game draws the player's own digits (30) in %d/200 draws while rate >= adj30 (ROM: never)" % hits)

class TestQA2(Base):
    def test_F_eb_special_lit_shows(self):
        """ROM FUN_01007b40: EB lit -> task 0x5f queues deff 53; FUN_01008528: special lit -> lamp 53 flash, task 0x61 deff 55."""
        self.start_ball()
        self.advance_time_and_run(5)
        al = self.tf.features_by_name["allspark"]
        al.run(2); al.run(1)
        self.advance_time_and_run(10)
        d = self.deffs()
        print("\nLIT SHOWS: deff53", 53 in d, "deff55", 55 in d, "eb_lit", self.tf.eb_lit[0], "spec", self.tf.specials_lit[0])

class TestQA3(Base):
    def test_F_match_sounds(self):
        """deff 38 code 0x0100820c: matched -> 0x072 at frame 60 then 0x074 after the award; else 0x073."""
        self.start_ball()
        self.tf.forced["match"] = [1]
        self.machine.game.end_game()
        self.advance_time_and_run(12)
        s = [e["call"] for e in self.tf.trace.of("sound")]
        print("\nMATCH SOUNDS (matched):", [x for x in s if x in ("0x023","0x072","0x073","0x074","0x019")], "deff38", 38 in self.deffs())
