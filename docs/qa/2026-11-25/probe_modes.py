"""QA probes (read-only): drive the game's mode features directly and print where they differ from the ROM."""
import os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _ROOT)
from mpf.tests.MpfTestCase import MpfTestCase
GAME = os.path.join(_ROOT, "game")
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
        self.tf = self.machine.tf
        self.tf.random.seed(1974)
        self.tf.adj.override(34, 1)
        self.tf.forced["side"] = [1] * 4
    def start(self):
        for n in ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l"):
            self.machine.switch_controller.process_switch(n, 1, True)
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)
    def score(self): return self.machine.game.player.score

class T(Base):
    def test_1_megatron_end_window(self):
        """ROM [0x0100be84]/[0x0100dec0]/[0x010276e0]/[0x01029754]: rules run while flag OR end task 0xbb-0xbc..."""
        self.start()
        for name, side_no in (("megatron", 1), ("megatron", 2), ("optimus", 1), ("optimus", 2)):
            f = self.tf.features_by_name[name]; s = f.sides[side_no]
            self.tf.pd["side"] = side_no
            if name == "megatron": s.start()
            else: s.start(1)
            s.active = True
            s.multiball_end()            # down to one ball: ROM keeps scoring for 218 ticks
            self.advance_time_and_run(0.5)
            before = self.score()
            shot = 6 if (name, side_no) == ("megatron", 1) else 0
            if name == "optimus" and side_no == 1: r = s.shot(0)
            else: r = s.shot(shot)
            print("PROBE1 %s side %d: shot %d 0.5 s after multiball_end scored %d (ROM: a jackpot)" % (name, side_no, shot, self.score() - before))
            s.kill()

    def test_2_autobot_timeout_before_M3(self):
        """ROM [0x0100c10c]: the 312-tick timeout waits while M (0x34dac) < 3; after the first jackpot M = 2."""
        self.start()
        f = self.tf.features_by_name["megatron"]; s = f.sides[1]
        self.tf.pd["side"] = 1
        s.start()
        s.shot(6)                         # jackpot: phase 2, M = 2
        print("PROBE2 after jackpot phase=%d mask=%#x m=%d" % (s.phase, s.mask, s.m))
        self.advance_time_and_run(330 * TICK)
        print("PROBE2 %.2f s later phase=%d mask=%#x m=%d (ROM: still phase 2, mask 0x3f, M 2)" % (330 * TICK, s.phase, s.mask, s.m))
        s.kill()

    def test_3_decepticon_megatron_save(self):
        """ROM [0x0100e0bc]: adj 88 (default 1) restores e2e/e30/mask/phase per player."""
        self.start()
        print("PROBE3 adj88 =", self.tf.adj[88])
        f = self.tf.features_by_name["megatron"]; s = f.sides[2]
        self.tf.pd["side"] = 2
        s.start()
        for shot in (0, 1, 2, 4):
            s.shot(shot)
        print("PROBE3 after 4 jackpots: jp=%d mask=%#x" % (s.jp, s.mask))
        s.multiball_end(); self.advance_time_and_run(5); s.kill()
        s.start()
        before = self.score(); s.shot(0)
        print("PROBE3 next D Megatron MB: jp=%d mask=%#x, shot 0 scored %d (ROM: jp 4 restored, mask 0x68, shot 0 unlit -> 0; or lit value 200,000)" % (s.jp, s.mask, self.score() - before))
        s.kill()

    def test_4_optimus_decepticon_super_mult(self):
        """ROM [0x01029bf4] phase 3: score_add(mult(table 0x040c7400[6] slot 4 = center) * super)."""
        self.start()
        f = self.tf.features_by_name["optimus"]; s = f.sides[2]
        self.tf.pd["side"] = 2
        s.start(1)
        self.tf.shot_mult = lambda shot: 2 if shot == 3 else 1   # center lane 2x
        s.phase, s.lit, s.remaining = 3, 0x40, 0
        before = self.score(); s.optimus()
        print("PROBE4 Optimus D super with center 2x scored %d (ROM: 2 x 1,000,000 = 2,000,000)" % (self.score() - before))
        s.kill()

class T2(Base):
    def test_5_center_lane_repeat(self):
        """ROM [0x01033b3c]: sw 11's rules are gated by task 0x54 only (started by sw 51); a second center lane
        0.5 s after the first runs its rules again. Starscream running: an unlit center lane = 25,000 each."""
        self.start()
        b = self.tf.features_by_name["battles"]
        ss = b.battles[0]
        ss.start(); ss.lit = 0           # nothing lit: every main shot is the unlit 25,000
        self.advance_time_and_run(1.0)
        res = []
        for _ in range(2):
            before = self.score()
            self.hit_and_release_switch("s_center_lane")
            self.advance_time_and_run(0.5)
            res.append(self.score() - before)
        print("PROBE5 two center lanes 0.5 s apart scored", res, "(ROM: both run the battle rule, 25,000 + handler each)")
        self.advance_time_and_run(2.0)
        self.hit_and_release_switch("s_center_lane"); self.advance_time_and_run(0.3)
        before = self.score()
        self.hit_and_release_switch("s_optimus_prime"); self.advance_time_and_run(0.5)
        print("PROBE5 Optimus 0.3 s after a center lane scored", self.score() - before,
              "(ROM: sw 51 [0x01033d3c] not gated by sw 11: Starscream shot 3 again, +25,000)")

class T3(Base):
    def test_6_super_lit_flasher(self):
        """ROM leff_063 [0x0100d038] (rule [0x0100d004]: flag 0x25 and phase 3): coilgroup_pulse every 8 ticks while
        the super is lit; same for leff_047/055/071. Count coil pulses in 2 s of 'super lit'."""
        self.start()
        f = self.tf.features_by_name["megatron"]; s = f.sides[1]
        self.tf.pd["side"] = 1
        s.start()
        self.advance_time_and_run(8)
        s.jp = 9; s.shot(6)                   # the 10th award: super lit
        n0 = len(self.tf.trace.of("coil"))
        l0 = [e for e in self.tf.trace.of("leff_start")][-3:]
        self.advance_time_and_run(2.0)
        coils = self.tf.trace.of("coil")[n0:]
        print("PROBE6 phase=%d, leff_start tail=%s, coil events in 2 s of super lit: %d %s (ROM: a flasher pulse every 8 ticks, ~15)"
              % (s.phase, [e.get("id") for e in l0], len(coils), sorted({e.get("coil") for e in coils})))
        s.kill()
