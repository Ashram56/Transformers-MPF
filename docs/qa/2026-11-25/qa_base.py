"""Copy of tests/tf_test.py without running gen_config.py (read-only QA)."""
import os, sys
from mpf.tests.MpfTestCase import MpfTestCase
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME = os.path.join(ROOT, "game")

class QaBase(MpfTestCase):
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
        self.machine.tf.adj.override(38, 0)          # no ball save, so a drain ends the ball
    @property
    def tf(self): return self.machine.tf
    def fill_trough(self):
        for name in ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l"):
            self.machine.switch_controller.process_switch(name, 1, True)
        self.advance_time_and_run(2)
    def start_ball(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)
    def hit(self, name, wait=2):
        before = self.machine.game.player.score
        self.hit_and_release_switch(name)
        self.advance_time_and_run(wait)
        return self.machine.game.player.score - before
    def drain(self):
        """drain the ball: put it in the trough."""
        self.machine.switch_controller.process_switch("s_trough_1_r", 1, True)
        self.advance_time_and_run(1)

    def validate(self):
        for n in ("s_l_ramp_entrance", "s_r_ramp_entrance", "s_captive_ball"):
            self.hit(n, 0.3)

    def next_ball(self):
        self.validate()
        self.advance_time_and_run(20)
        b = self.machine.game.player.ball
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.advance_time_and_run(15)
        self.release_switch_and_run("s_shooter_lane", 2)
