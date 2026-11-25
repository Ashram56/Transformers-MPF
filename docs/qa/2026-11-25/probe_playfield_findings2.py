from qa_base import QaBase


class T(QaBase):
    def f(self, name):
        return self.tf.features_by_name[name]

    def snd(self, n0):
        return [e["call"] for e in self.tf.trace.of("sound")[n0:]]

    def test_F9_tails(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        tb = self.f("twobank")
        tb.start()
        self.advance_time_and_run(5)
        tb.count = 0
        self.advance_time_and_run(1.5)                # one more count: now in the 250-tick tail (ROM task 0xae)
        print("F9 fast scoring in tail: counting", tb.counting, "running", tb.running,
              "timed_mode_running", self.tf.timed_mode_running())
        left0 = self.tf.pd.twobank_left
        n0 = len(self.tf.trace.of("score_add"))
        self.hit("s_r_2_bank_target_top", 0.3)
        print("F9 2-bank in tail:", [e["points"] for e in self.tf.trace.of("score_add")[n0:]], "left", left0, "->",
              self.tf.pd.twobank_left, "(ROM 0x0102e994: 0xac not running -> 75,000 and left - 1)")
        n0 = len(self.tf.trace.of("sound"))
        self.hit("s_top_bumper", 0.3)
        print("F9 pop sound in fast-scoring tail:", self.snd(n0), "(ROM 0x0102c804: 0x15b/0x15c, task 0xac only)")

    def test_F9b_ds_tail(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        b = self.f("bumblebee")
        b.start()
        b.count = 0
        self.advance_time_and_run(1.2)
        n0 = len(self.tf.trace.of("sound"))
        self.hit("s_top_bumper", 0.3)
        print("F9b DS tail running", b.running, "pop sounds", self.snd(n0), "(ROM: 0x15c + 0x27c/0x27d; game 0x15d)")

    def test_F11_center_after_optimus(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        self.hit("s_l_ramp_exit", 0.5)                  # combo window open
        self.hit("s_optimus_prime", 0.3)
        n0 = len(self.tf.trace.of("score_add"))
        self.hit("s_center_lane", 0.5)
        print("F11 center lane 0.3 s after Optimus:", [e["points"] for e in self.tf.trace.of("score_add")[n0:]],
              "(ROM 0x01033b3c: task 0x54 running -> no combo, only the 30)")
        n0 = len(self.tf.trace.of("score_add"))
        self.hit("s_optimus_prime", 0.05)
        self.hit("s_optimus_prime", 0.5)
        print("F11 Optimus twice within 0x54:", [e["points"] for e in self.tf.trace.of("score_add")[n0:]],
              "(ROM 0x01033d3c: second hit returns before its 30)")

    def test_F12_warning_sound(self):
        self.tf.adj.override(80, 10)
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        n0 = len(self.tf.trace.of("sound"))
        self.f("bumblebee").start()
        self.advance_time_and_run(14)
        s = self.snd(n0)
        print("F12 adj 80 = 10: 0x285 played", "0x285" in s, "(ROM: at count 9)", [x for x in s if x.startswith("0x28")])

    def test_F13_skill_lane_completion(self):
        self.start_ball()
        self.tf.pd.lanes_left = {51, 8, 9}
        self.hit("s_left_top_lane", 0.5)               # hands-free skill shot: two lane awards
        print("F13 lit after skill shot completing the group:", self.tf.pd.lanes_left,
              "(ROM 0x010335d0: 2nd call FUN_0102db28(0x32) lights 50)")

    def test_F17_deff44_rove(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        self.tf.pd.shot_mult = [2] * 6
        self.f("combos").shot_mult_light()           # roving 3X starts
        n0 = len(self.tf.trace.of("deff_start"))
        self.tf.pd.lanes_left = {50, 51, 8}
        self.hit("s_left_return_lane", 0.5)
        print("F17 deffs on group complete with roving 3X running:",
              [e["id"] for e in self.tf.trace.of("deff_start")[n0:]], "(ROM 0x0102db28: deff 44 always)")
