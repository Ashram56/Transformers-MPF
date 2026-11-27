"""QA proofs, playfield scoring features (read-only harness: qa_base.py)."""
from qa_base import QaBase


class T(QaBase):
    def f(self, name):
        return self.tf.features_by_name[name]

    def test_F2_mult_upgrade_after_combo(self):
        """ROM: every major-shot handler calls FUN_010237ac(shot) FIRST, then FUN_01002f0c (combo, uses
        FUN_01023538) -> the combo on the shot that takes the lit 2X is doubled."""
        self.start_ball()
        self.hit("s_right_orbit_spinner")                 # end the skill shots
        self.hit("s_l_ramp_exit")                         # window opens (way 1)
        self.tf.pd.mult_lit = True
        before = len(self.tf.trace.of("score_add")) if hasattr(self.tf.trace, "of") else 0
        n0 = len(self.tf.trace.of("score_add"))
        d = self.hit("s_r_ramp_exit", 0.5)
        print("F2 score events:", [ {k: v for k, v in e.items() if k != "t"} for e in self.tf.trace.of("score_add")[n0:]])
        print("F2 right ramp after lit mult: delta", d, "shot_mult", self.tf.pd.shot_mult,
              "combo part (game) = 150,000; ROM = 2 x 150,000 = 300,000")

    def test_F3_skill_shot_slings_pops(self):
        """ROM: slings/pops post event 0x6b (0x01033104, 0x010331a4, 0x01032f8c) -> hook 0x010313cc
        switch_timeout_obj_add(0x31400/0x3140c, count 3): 3 distinct end both skill shots."""
        self.start_ball()
        for n in ("s_left_slingshot", "s_right_slingshot", "s_top_bumper"):
            self.hit(n, 0.5)
        sk = self.f("skill_shot")
        print("F3 after sling, sling, pop: top armed", sk.top, "super armed", sk.super,
              "back door delta", self.hit("s_megatron_back_door"), "(ROM: 30, both ended)")

    def test_F15_unlit_lane_ends_super(self):
        """ROM FUN_01031630 always calls FUN_010319f4 (kills 0xb2-0xb5): the unlit lane ends the super too."""
        self.start_ball()
        self.hit("s_right_top_lane", 0.5)                 # unlit lane for a Decepticon player
        print("F15 after unlit lane: super armed", self.f("skill_shot").super,
              "back door delta", self.hit("s_megatron_back_door"), "(ROM: 30)")

    def test_F4_item10_weight(self):
        self.start_ball()
        a = self.f("allspark")
        self.tf.pd.shot_mult = [2] * 6
        w_all2 = a.weights()[9]
        self.tf.pd.shot_mult = [1] * 6
        self.tf.pd.mult_lit = True
        w_lit = a.weights()[9]
        print("F4 item 10 weight: all shots 2X ->", w_all2, "(ROM 100: FUN_01023494 returns 3, roving 3X);",
              "multiplier already lit ->", w_lit, "(ROM 0)")

    def test_F5_flag13(self):
        self.start_ball()
        self.tf.flag_set(0x13)
        self.f("bumblebee").start()
        ds = self.tf.flag(0x13)
        self.f("bumblebee").stop()
        self.tf.flag_set(0x13)
        self.f("twobank").start()
        print("F5 flag 0x13 after double scoring start:", ds, "after fast scoring start:", self.tf.flag(0x13),
              "(ROM: cleared by 0x010039a0 / 0x01004394); item 6 weight now", self.f("allspark").weights()[5])

    def test_F6_double_scoring_hold(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        b = self.f("bumblebee")
        b.start()
        c0 = b.count
        self.tf.pf_valid = False
        self.advance_time_and_run(5)
        print("F6 double scoring count", c0, "->", b.count, "after 5 s with playfield not valid",
              "(ROM 0x010038dc ignores 0x0100683c: about 4-5 counts down)")

    def test_F7_fast_scoring_pops_pause(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        tb = self.f("twobank")
        tb.start()
        self.advance_time_and_run(6)
        c0 = tb.count
        for _ in range(12):
            self.hit("s_top_bumper", 0.5)
        print("F7 fast scoring count", c0, "->", tb.count, "over 6 s of pops every 0.5 s",
              "(ROM: each pop restarts task 0x59 for 156 ticks -> 0x0100683c holds 0x01004220: no count lost)")

    def test_F8_fast_scoring_cycle_value(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        tb = self.f("twobank")
        tb.start()
        self.advance_time_and_run(5)
        v0 = tb.value
        self.hit("s_r_2_bank_target_top", 0.5)
        self.hit("s_r_2_bank_target_bot", 0.5)
        ids = [e["id"] for e in self.tf.trace.of("deff_start")]
        leffs = [e["id"] for e in self.tf.trace.of("leff_start")]
        print("F8 fast value", v0, "->", tb.value, "(ROM 0x010047b8: +1000 for the first only, 11000);",
              "deff 135 count", ids.count(135), "(ROM 1); leff 144 count", leffs.count(144), "/145", leffs.count(145))

    def test_F10_sw6_fast_award(self):
        self.start_ball()
        self.hit("s_right_orbit_spinner")
        tb = self.f("twobank")
        tb.start()
        self.advance_time_and_run(5)
        self.hit("s_left_slingshot", 0.5)
        t0 = tb.total
        self.hit("s_left_orbit_top", 0.5)
        print("F10 fast scoring total", t0, "->", tb.total, "after sw6 (ROM 0x010332e4 never calls 0x010047b8)")
