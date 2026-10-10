"""PuP Pack (docs/pup.md): the trigger map covers the pack, the engine fires its rows as PinUP Player does, and
the game sends them to Godot and drops the ROM music only once Godot's PuP player is ready."""
import csv
import os
import sys
import unittest
from unittest import mock

from tests.tf_test import GAME, ROOT, TfTestCase

sys.path.insert(0, GAME)
from pup_runtime import engine, settings   # noqa: E402

CFG = settings.load()
PACK = settings.pack_dir(CFG)
MAP = settings.map_path(CFG)
HAVE_PACK = os.path.exists(os.path.join(PACK, "triggers.pup"))


class TestSettings(unittest.TestCase):

    def test_env_off(self):
        with mock.patch.dict(os.environ, {"TF_PUP": "0"}):
            self.assertFalse(settings.load()["pup"]["enabled"])
        self.assertTrue(CFG["pup"]["enabled"])

    def test_three_screens_and_pack_music(self):
        pup = CFG["pup"]
        self.assertEqual(["backglass", "dmd", "topper"], pup["windows"])
        self.assertEqual([2, 11, 12, 13, 14, 15], CFG["backglass"]["layers"])
        self.assertEqual([0], CFG["topper"]["layers"])
        self.assertTrue(CFG["dmd"]["dmd"])
        self.assertEqual(4, pup["music_screen"])
        self.assertTrue(pup["ost_music"])          # the owner's choice: the pack's music, not the ROM's
        self.assertEqual("tf.media", pup["bridge"])

    def test_mapped_effects_exist(self):
        """An effect renumbered upstream would leave PuP rows on dead events."""
        with open(os.path.join(ROOT, "rom", "mpf_package", "event_map.csv"), encoding="utf-8") as f:
            deffs = {int(row["deff"]) for row in csv.DictReader(f)}
        trigger_map = engine.load_map(MAP)
        names = [engine.parse_event(e)[0] for events in trigger_map["dmd"].values() for e in events]
        names += list(trigger_map["counters"]) + [r for rs in trigger_map["counters"].values() for r in rs]
        for name in names:
            if name.startswith("tf_deff_"):
                self.assertIn(int(name[len("tf_deff_"):]), deffs, name)


@unittest.skipUnless(HAVE_PACK, "PuP Pack not checked out (git submodule update --init pup_pack)")
class TestEngine(unittest.TestCase):

    def setUp(self):
        self.sent, self.t = [], [0.0]
        self.engine = engine.build(PACK, MAP, self.sent.append, lambda: self.t[0])

    def ids(self):
        return [c["trigger"] for c in self.sent]

    def test_only_known_rows_unmapped(self):
        # the Decepticon side's second-round lock videos (no game event tells the rounds apart yet)
        self.assertEqual([208, 209, 210], [r.id for r in self.engine.unmapped])

    def test_overlay_at_start(self):
        self.engine.on_event("pup_boot")
        self.assertEqual([246], self.ids())        # D0: the backglass overlay picture

    def test_side_choice(self):
        self.engine.on_event("tf_deff_40", state={"side": 1})
        self.assertIn(249, self.ids())             # Choose - Autobot - BG
        self.assertNotIn(252, self.ids())
        self.assertIn(366, self.ids())             # its music on screen 4
        self.sent.clear()
        self.engine.on_event("tf_deff_41", state={"side": 2})
        self.assertIn(270, self.ids())             # Chosen - Decepticon - BG
        self.assertIn(349, self.ids())             # Decepticon main music (SetBG)

    def test_battle_hits_by_number(self):
        self.engine.on_event("tf_deff_100")        # Blackout intro
        self.assertIn(28, self.ids())
        self.sent.clear()
        self.engine.on_event("tf_deff_102", values=[100], hit=1, completed=0)
        self.assertEqual([29], self.ids())         # Blackout 1
        self.sent.clear()
        self.engine.on_event("tf_deff_102", values=[100], hit=3, completed=0)
        self.assertEqual([31], self.ids())         # Blackout 3
        self.sent.clear()
        self.engine.on_event("tf_deff_102", values=[100], hit=11, completed=1)
        self.assertEqual([38], self.ids())         # Blackout Completed

    def test_counted_jackpots(self):
        self.engine.on_event("tf_deff_75")         # Megatron multiball, Decepticon intro
        self.sent.clear()
        self.engine.on_event("tf_deff_77", values=[100000])
        self.engine.on_event("tf_deff_77", values=[125000])
        self.assertEqual([214, 215], [i for i in self.ids() if i in (214, 215, 216)])

    def test_drain(self):
        self.engine.on_event("tf_deff_25", values=[])
        self.assertTrue({3, 328, 329, 330, 367} <= set(self.ids()))


class TestPupMachine(TfTestCase):

    def setUp(self):
        super().setUp()
        self.pup = self.machine.modes["pup"]
        if self.pup.engine is None:
            self.skipTest("PuP Pack not checked out or PuP disabled")

    def test_triggers_reach_godot_after_ready(self):
        client = mock.Mock()
        with mock.patch.object(self.machine.bcp, "interface") as iface, \
                mock.patch.object(self.machine.bcp, "transport") as transport:
            transport.get_named_client.return_value = client
            self.machine.events.post("tf_deff_20")
            self.advance_time_and_run(1)
            self.assertFalse([c for c in iface.bcp_trigger_client.call_args_list
                              if c.kwargs["name"] == "pup_play"])          # Godot not ready: nothing sent
            self.machine.events.post("pup_ready")
            self.advance_time_and_run(1)
            self.machine.events.post("tf_deff_20")
            self.advance_time_and_run(1)
            plays = [c.kwargs for c in iface.bcp_trigger_client.call_args_list if c.kwargs["name"] == "pup_play"]
            self.assertEqual("BallSaved", plays[-1]["playlist"])
            self.assertIs(client, plays[-1]["client"])

    def test_side_from_the_players_rule_state(self):
        self.pup.ready = True                                     # as after Godot's pup_ready
        with mock.patch.object(self.pup.engine, "fire") as fire:
            self.fill_trough()
            self.hit_and_release_switch("s_start_button")
            self.advance_time_and_run(2)
            self.machine.events.post("tf_deff_41")
            self.advance_time_and_run(0.1)
            fired = [r.id for c in fire.call_args_list for r in c.args[0]]
            side = self.tf.pd.get("side")
            self.assertIn(274 if side == 2 else 271, fired)

    def test_rom_music_muted_when_pup_ready(self):
        bridge = self.tf.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        pools = bridge.data["pools"]
        music = next(c for c, p in pools.items() if p["track"] == "music")
        effect = next(c for c, p in pools.items() if p["track"] != "music" and c > 8)
        with mock.patch.object(bridge, "connected", return_value=True), \
                mock.patch.object(self.machine.bcp, "interface") as iface, \
                mock.patch.object(self.machine.bcp, "transport"):
            bridge.sound(music)                                  # before PuP: the ROM music plays
            self.assertIsNotNone(bridge.music_key)
            self.machine.events.post("pup_ready")
            self.advance_time_and_run(0.1)
            self.assertIsNone(bridge.music_key)                  # the running ROM music is stopped
            iface.reset_mock()
            bridge.sound(music)                                  # music call: dropped
            bridge.sound(effect)                                 # a sound effect still plays
            calls = [c.kwargs for c in iface.bcp_trigger_client.call_args_list if c.kwargs["name"] == "sounds_play"]
            self.assertEqual(1, len(calls))
            self.assertIsNone(bridge.music_key)

    def test_attract_cycle(self):
        self.pup.ready = True
        with mock.patch.object(self.pup.engine, "on_event") as on_event:
            self.advance_time_and_run(float(self.pup.pup.get("attract_cycle_seconds", 60)) + 1)
            self.assertIn("pup_attract_cycle", [c.args[0] for c in on_event.call_args_list])
