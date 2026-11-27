"""QA 2026-11-26, scope D: runtime probes of the device / settings findings (read-only; each prints the game's
value next to the ROM's). Run from the repository folder:
.venv/bin/python -m pytest -q -s -p no:cacheprovider docs/qa/2026-11-26/probe_devices_game.py"""
import os
import sys

from mpf.tests.MpfTestCase import MpfTestCase

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME = os.path.join(ROOT, "game")


class Base(MpfTestCase):
    def get_config_file(self): return "config.yaml"
    def get_machine_path(self): return GAME
    def get_absolute_machine_path(self): return GAME
    def get_platform(self): return "smart_virtual"
    def get_enable_plugins(self): return False

    def setUp(self):
        if GAME not in sys.path:
            sys.path.insert(0, GAME)
        super().setUp()
        self.machine.tf.random.seed(1974)
        self.machine.tf.adj.override(34, 1)
        self.machine.tf.forced["side"] = [1] * 4

    @property
    def tf(self):
        return self.machine.tf

    def start_ball(self):
        for n in ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l"):
            self.machine.switch_controller.process_switch(n, 1, True)
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)


class TestDevices(Base):
    def test_SM_service_menu(self):
        """ROM: SELECT opens the service menu (0x0000eb3c). Game: starts mode tf_service, which does not exist."""
        self.advance_time_and_run(1)
        self.hit_and_release_switch("s_select")
        self.advance_time_and_run(1)
        print("\nD-SM-MODE: 'tf_service' in modes:", "tf_service" in self.machine.modes, "| in_service:",
              self.tf.in_service, "| ROM: service menu MAIN MENU items 1,2,3,4,99,98,5")

    def test_AUD_percentages(self):
        """ROM (audits.csv formulas): % audits divide by c17 (paid plays); 13 and 72 are always 0."""
        a = self.tf.audits
        a.counts.update({17: 10, 18: 10, 8: 60, 9: 6, 10: 2, 14: 1, 16: 1, 7: 40})
        rom = {2: (2 + 1 + 0 + 1) * 100 // 10, 16: 6 * 100 // 10, 22: 2 * 100 // 10, 24: 1 * 100 // 10,
               27: 1 * 100 // 10, 13: 0, 72: 0}
        for n, v in rom.items():
            print("\nD-AUD-%d: game %s | ROM %s" % (n, a.value(n), v), end="")
        print()

    def test_SW51_edge(self):
        """ROM: sw 51 handler runs on the opening edge (+0xe 0x1800). Game: closing edge + 5 ticks; a 1 s hold."""
        self.start_ball()
        self.advance_time_and_run(4)
        before = self.machine.game.player.score
        self.hit_switch_and_run("s_optimus_prime", 0.5)
        held = self.machine.game.player.score - before
        self.release_switch_and_run("s_optimus_prime", 0.5)
        print("\nD-SW-51-EDGE: score while held %d, after release %d | ROM: 0 while held, all after release" % (
            held, self.machine.game.player.score - before))

    def test_ADJ89_autofire(self):
        """ROM 0x0100a074: autofire after a lock only when adj 89 = 1. Game: _serve ignores adj 89."""
        src = open(os.path.join(GAME, "tf", "features", "megatron.py"), encoding="utf-8").read()
        body = src.split("def _serve(self):")[1].split("\n    def ")[0]
        print("\nD-ADJ-89-SEM: adj 89 read in _serve:", "adj" in body.replace("adj 89", ""),
              "| ROM: adj_get(0x59) == 1 gates the autofire")

    def test_ADJ25_free_game_limit(self):
        """ROM: no adj_get(25) call site. Game: award() caps free games at adj 25."""
        self.start_ball()
        self.tf.adj.override(25, 0)
        got = self.tf.credit_model.award(1)
        print("\nD-CR-FGL: adj 25 = 0 -> credits awarded %d | ROM: no reader of adj 25 (1)" % got)
