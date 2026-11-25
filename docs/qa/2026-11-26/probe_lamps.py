"""QA probes of 2026-11-26, lamp conversion (read-only; each prints the game's value next to the ROM's).
Run: .venv/bin/python -m pytest -q -s -p no:cacheprovider docs/qa/2026-11-26/probe_lamps.py"""
import json
import os
import sys

from mpf.tests.MpfTestCase import MpfTestCase

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME = os.path.join(ROOT, "game")
OPS = os.path.join(ROOT, "rom", "rom_data", "io", "leff_ops")
TICK = 0.016


def rom_frame_lamps(leff, upto):
    """Lamps the ROM's leff (agent A's lift of its code) has lit (any plane) at tick `upto`."""
    doc = json.load(open(os.path.join(OPS, "leff_%03d.json" % leff)))
    state = {}
    for f in doc["frames"]:
        if f["t"] > upto:
            break
        state.update({int(k): v for k, v in f["lamps"].items()})
    return sorted(n for n, v in state.items() if v)


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
    def tf(self): return self.machine.tf

    def start_ball(self):
        for n in ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l"):
            self.machine.switch_controller.process_switch(n, 1, True)
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 2)

    def layer_lamps(self, leff):
        entry = self.tf.lamps.leff_players.get(leff)
        if not entry:
            return None
        layer = entry[1]
        return sorted(layer.mask), sorted(layer.image)


class TestLamps(Base):
    def test_L_show_lamps_parsed(self):
        """ROM: every leff show lights lamps (leff_ops frames). Game: parse_show reads "ffffff" (double quotes)?"""
        from tf.lamps import parse_show
        shows = os.path.join(ROOT, "rom", "mpf_package", "config", "shows")
        n = lit = 0
        for name in sorted(os.listdir(shows)):
            steps = parse_show(os.path.join(shows, name))
            n += 1
            lit += any(s[1] for s in steps)
        print("\nL-show-parse: shows", n, "with any lamp parsed by tf.lamps.parse_show:", lit)

    def test_L_attract_leff1(self):
        """ROM leff 1 [0x01009e78] lights lamps from tick 0 (leff_001.json). Game: what its layer draws."""
        self.advance_time_and_run(3)
        print("\nL-001: running", self.tf.leffs.is_running(1), "layer (mask, image)", self.layer_lamps(1),
              "| ROM lamps lit at tick 5:", len(rom_frame_lamps(1, 5)))

    def test_L_leff_shows_in_game(self):
        """Start show leffs in a game; ROM lamps at tick 20 vs the game's layer image 20 ticks in."""
        self.start_ball()
        for leff in (45, 61, 99, 120, 95, 13):
            self.tf.leff_start(leff)
            self.advance_time_and_run(20 * TICK)
            print("\nL-%03d: game layer" % leff, self.layer_lamps(leff), "| ROM lit by tick 20:", rom_frame_lamps(leff, 20))
            self.tf.leff_stop(leff)

    def test_L_arg_leffs(self):
        """ROM leff 97 [0x0102dda4] toggles the lamp passed at +0x30 every 2 ticks (10 times); 27 [0x0102d138] the pop's
        lamp; 139 [0x0100999c] lights it 8 ticks. Game: what the layer draws."""
        self.start_ball()
        for leff in (97, 27, 139, 171, 172):
            started = self.tf.leff_start(leff)
            self.advance_time_and_run(3 * TICK)
            print("\nL-%03d: started" % leff, started, "layer", self.layer_lamps(leff))

    def test_L_flash_phase(self):
        """ROM lamp_compositor_tick [0x000073cc]: the flash phase inverts every 10 ticks (counter 0x0003148c = 10).
        Game: measure the period of a flashing insert's raw output."""
        self.start_ball()
        lamps = self.tf.lamps
        lamps.lamp_flash(53)
        changes, last, t = [], lamps.raw[53], 0.0
        for _ in range(200):
            self.advance_time_and_run(0.004)
            t += 0.004
            if lamps.raw[53] != last:
                changes.append(round(t, 3))
                last = lamps.raw[53]
        gaps = [round(b - a, 3) for a, b in zip(changes, changes[1:])]
        print("\nL-flash: game phase lengths (s)", gaps[:6], "| ROM: 10 ticks = 0.160 s")

    def test_L_rule_leff_no_draw(self):
        """Rule leffs the ROM draws from game state (e.g. 40 [0x01024328] Allspark banked, coil group 39): the game's
        layer when its rule starts it."""
        self.start_ball()
        for leff in (40, 20, 104, 92):
            self.tf.leff_start(leff, loop=True)
            self.advance_time_and_run(10 * TICK)
            print("\nL-%03d rule leff: layer" % leff, self.layer_lamps(leff))

    def test_L_energon_lit_solid(self):
        """ROM energon lamp rule 0x01030f80: a lit target is on with the flash bit cleared (0x00007858, solid).
        Game energon.py:101 lamp_on keeps the flash bit set by the unlit frame before."""
        self.start_ball()
        self.advance_time_and_run(4)
        self.tf.pd.energon_lit = 1                  # left target lit (bit 1)
        self.tf.request_refresh()
        self.advance_time_and_run(1)
        lamps = self.tf.lamps
        print("\nL-INS-48: energon_lit", self.tf.pd.get("energon_lit"),
              "lamp 48 state (0 off, 1 solid, 2 flashing):", lamps.lamp_state(48), "| ROM: 1 (solid)")

    def test_L_energon_multiball(self):
        """ROM 0x01030f80: during a multiball (0x0103096c false) all three energon inserts off (0x00007714)."""
        self.start_ball()
        self.tf.flags.add(0x1f)              # a multiball running flag (any_multiball 0x01006704 tests 6 flags)
        self.tf.request_refresh()
        self.advance_time_and_run(1)
        print("\nL-INS-35/48/54 in a multiball: any_multiball", self.tf.any_multiball() if hasattr(self.tf, "any_multiball") else "?",
              "states", [self.tf.lamps.lamp_state(n) for n in (48, 54, 35)], "| ROM: [0, 0, 0]")

    def test_L_battle_completed_solid(self):
        """ROM 0x01035ea8: a completed battle's insert is solid (0x00007858). Game battles.py:1091 lamp_on after the
        started frame's lamp_flash leaves the flash bit."""
        self.start_ball()
        pd = self.tf.pd
        feat = [f for f in self.tf.features if hasattr(f, "battles")][0]
        bit_insert = [(x.bit, x.insert) for x in feat.battles][0]
        pd.battle_started = bit_insert[0]
        self.tf.request_refresh(); self.advance_time_and_run(0.5)
        s1 = self.tf.lamps.lamp_state(bit_insert[1])
        pd.battle_completed = bit_insert[0]
        self.tf.request_refresh(); self.advance_time_and_run(0.5)
        print("\nL-INS-battle: insert", bit_insert[1], "started state", s1, "completed state",
              self.tf.lamps.lamp_state(bit_insert[1]), "| ROM: 2 then 1 (solid)")
