"""The Visual Pinball X overlay (config.yaml + hw_vpx.yaml + tf/vpx_hardware.py) answers the table's controller
calls as VPinMAME does, and scripts/vpx_table.py rewrites the table script's loader. The calls go to the platform
the way MPF's "vpcom_bridge" BCP handler sends them (scripts/vpx_bridge.py --check drives a live game the same way).
The ball moves the way the Transformers Pro table's script moves it (bsTrough, sw23, Drain_Hit)."""
import asyncio
import os
import sys
import time

from mpf.tests.MpfBcpTestCase import MpfBcpTestCase

from tests.tf_test import ROOT, TfTestCase

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import vpx_bridge  # noqa: E402
import vpx_table  # noqa: E402

TROUGH = (21, 20, 19, 18)       # bsTrough.InitSwitches Array(21, 20, 19, 18): 21 is the eject end


class TestVpx(TfTestCase, MpfBcpTestCase):

    def get_config_file(self):
        return "../../tests/machine_vpx.yaml"     # relative to game/config

    def get_platform(self):
        return False                              # the overlay's own platform

    def _initialize_machine(self):
        """MPF waits in init_phase_5 until the table connects: connect as the bridge's Run() does."""
        init = asyncio.ensure_future(self.machine.initialize())
        end = time.time() + 60
        while not init.done() and not self._exception:
            self.loop.run_once()
            platform = getattr(self.machine, "hardware_platforms", {}).get("virtual_pinball")
            if platform is not None and not platform._started.is_set():
                self.assertTrue(platform.vpx_start())
            self.assertLess(time.time(), end, "MPF did not start")
        init.result()
        self.machine.events.process_event_queue()
        self.advance_time_and_run(.001)

    def vpx(self, subcommand, **kwargs):
        return getattr(self.machine.hardware_platforms["virtual_pinball"], "vpx_" + subcommand)(**kwargs)

    def set_switch(self, number, value, run=0.05):
        self.assertTrue(self.vpx("set_switch", number=number, value=value))
        self.advance_time_and_run(run)

    def solenoids(self):
        return dict(self.vpx("changed_solenoids"))

    def start_game(self):
        for number in TROUGH:                       # bsTrough.Balls = 4
            self.set_switch(number, True)
        self.advance_time_and_run(2)
        self.assertEqual(4, self.machine.ball_devices["bd_trough"].balls)
        self.set_switch(16, -1)                     # START (VBScript True is -1)
        self.set_switch(16, 0, run=2)
        self.assertModeRunning("game")

    def serve_and_plunge(self):
        """What the table does when solenoid 1 fires: SolTrough kicks the ball out of 21 (and pulses the jam
        switch 22 on the way), the ball rolls into the shooter lane (23); the plunger sends it away."""
        self.set_switch(21, False)
        self.set_switch(22, True, run=0.01)
        self.set_switch(22, False, run=0.3)
        self.set_switch(23, True, run=1)
        self.set_switch(23, False, run=2)
        self.set_switch(8, True)                    # left top lane: playfield valid
        self.set_switch(8, False, run=1)

    def test_numbers_match_pinmame(self):
        sw = self.machine.switches
        for name, number in (("s_l_flipper_button", "84"), ("s_r_flipper_button", "82"),
                             ("s_tilt_pendulum", "-7"), ("s_slam_tilt", "-6"), ("s_left_coin_slot", "65"),
                             ("s_start_button", "16"), ("s_back", "-3"), ("s_select", "0"),
                             ("s_trough_1_r", "21"), ("s_coin_door_open", "-4")):
            self.assertEqual(number, sw[name].hw_switch.number, name)
        self.assertEqual("1", self.machine.coils["c_trough_up_kicker"].hw_driver.number)
        self.assertEqual("17", self.machine.coils["c_flash_decepticon"].hw_driver.number)
        self.assertEqual("aux1", self.machine.coils["c_aux_1_ticket_advance"].hw_driver.number)
        self.assertEqual("1", self.machine.lights["l_start_button"].hw_drivers["white"][0].hw_number)

    def test_game_through_the_bridge(self):
        self.assertEqual([[0, 255]], self.vpx("changed_gi_strings"))   # GI on: the table's GI_PWM
        self.assertEqual([], self.vpx("changed_gi_strings"))            # then nothing changes
        for number in TROUGH:
            self.set_switch(number, True)
        self.advance_time_and_run(2)
        self.assertNotIn(33, self.solenoids())      # flippers off in attract

        self.set_switch(16, -1)
        self.set_switch(16, 0, run=2)
        self.assertModeRunning("game")
        sols = self.solenoids()
        self.assertEqual(255, sols.get(1), sols)    # trough up-kicker: reported though the pulse is over
        self.assertEqual(255, sols.get(33))         # flippers enabled: the table's fast flips take over
        self.assertEqual(0, self.solenoids().get(1))    # then off at the next poll
        self.assertNotIn(1, self.solenoids())           # and nothing more until it fires again

        self.set_switch(84, True)                   # left flipper button: coil 15 follows it
        self.assertEqual(255, self.solenoids().get(15))
        self.set_switch(84, False)
        self.assertEqual(0, self.solenoids().get(15))

        self.vpx("changed_lamps")
        self.machine.lights["l_start_button"].on()
        self.machine.lights["l_roll_out"].color("808080")
        self.advance_time_and_run(.1)
        lamps = dict(self.vpx("changed_lamps"))
        self.assertEqual(255, lamps[1])             # 0-255: core.vbs scales by 1/255 with UseVPMModSol = 2
        self.assertEqual(128, lamps[3])
        self.machine.lights["l_start_button"].off()
        self.advance_time_and_run(.1)
        self.assertEqual(0, dict(self.vpx("changed_lamps")).get(1))     # the game's own lamps change too
        self.assertTrue(self.vpx("set_switch", number=86, value=True))      # swURFlip: no such switch, no error
        self.assertFalse(self.vpx("get_switch", number=86))
        self.assertTrue(self.vpx("get_switch", number=18))

    def test_ball_plays_and_drains(self):
        """The trough, the shooter lane and the drain as the table reports them: MPF counts the ball out and back."""
        self.start_game()
        self.assertEqual(255, self.solenoids().get(1))
        self.serve_and_plunge()
        self.assertEqual(1, self.machine.playfield.balls)
        self.assertEqual(3, self.machine.ball_devices["bd_trough"].balls)
        self.assertTrue(self.machine.tf.pf_valid)
        self.machine.tf.kill_ball_save()
        self.assertEqual(0, self.solenoids().get(1))        # the table polls every frame: the kicker is off
        self.set_switch(21, True, run=10)           # Drain_Hit: bsTrough.AddBall, the ball lands on 21
        self.assertEqual(2, self.machine.game.player.ball)
        self.assertEqual(255, self.solenoids().get(1))      # the next ball is served

    def test_slings_fire_their_coils(self):
        """solLSling / solRSling animate the table's sling arms: MPF fires 13 and 14 on 26 and 27, in play only."""
        self.vpx("pulsesw", number=26)
        self.advance_time_and_run(.01)
        self.assertNotIn(13, {n for n, v in self.solenoids().items() if v})     # attract: no autofires
        self.start_game()
        self.solenoids()
        self.vpx("pulsesw", number=26)
        self.vpx("pulsesw", number=30)              # top pop bumper
        self.advance_time_and_run(.01)
        sols = self.solenoids()
        self.assertEqual(255, sols.get(13), sols)
        self.assertEqual(255, sols.get(9), sols)

    def test_coin_door_cuts_the_coils(self):
        self.start_game()
        self.assertEqual(255, self.solenoids().get(33))
        self.set_switch(-4, True)                   # End: the door opens (the table script toggles -4)
        self.assertTrue(self.vpx("get_switch", number=-4))
        self.assertEqual(4, self.machine.tf.display.fg)                # "50V / 20V DISABLED"
        self.assertEqual(0, self.solenoids().get(33))                  # fast flips off: no flipper power
        self.machine.coils["c_left_slingshot"].pulse()
        self.set_switch(84, True)
        self.assertEqual({}, {n: v for n, v in self.solenoids().items() if v})   # nothing drives
        self.set_switch(84, False)
        self.set_switch(-4, False)                  # closed: power back, the flippers with it
        self.assertEqual(255, self.solenoids().get(33))

    def test_tilt_turns_the_flippers_off(self):
        self.start_game()
        self.serve_and_plunge()
        self.assertEqual(255, self.solenoids().get(33))
        for _ in range(3):                          # adj: tilt warnings, then the tilt
            self.vpx("pulsesw", number=-7)
            self.advance_time_and_run(2)
            if self.machine.tf.tilted:
                break
        self.assertTrue(self.machine.tf.tilted)
        self.assertEqual(0, self.solenoids().get(33))

    def test_pulse_switch_and_stop(self):
        self.assertTrue(self.vpx("pulsesw", number=-6))
        self.assertTrue(self.vpx("stop"))           # the table closed (no quit: the bridge did not start MPF)


class TestTableScript(TfTestCase):

    SCRIPT = ('Option Explicit\r\nDim UseVPMModSol : UseVPMModSol = 2\r\nLoadVPM "01550000", "SAM.VBS", 3.26\r\n'
              'Sub Table1_Init\r\n\tController.Run GetPlayerHWnd\r\nEnd Sub\r\n'
              'Sub Table1_KeyDown(ByVal Keycode)\r\n\tIf vpmKeyDown(keycode) Then Exit Sub\r\nEnd Sub\r\n')

    def test_loader_swapped(self):
        out = vpx_table.patch_script(self.SCRIPT)
        self.assertNotIn('\r\nLoadVPM', out)
        self.assertIn('LoadMPF "SAM.VBS"\r\n', out)
        self.assertIn('CreateObject("TransformersMPF.Controller")', out)
        self.assertIn('Was: LoadVPM "01550000", "SAM.VBS", 3.26', out)
        self.assertNotIn("\n\n", out.replace("\r\n", "\r"))          # line ends stay CRLF
        self.assertIn('Sub Table1_Init\r\n\tController.Run GetPlayerHWnd\r\nEnd Sub\r\n', out)
        # End toggles the coin door (switch -4) before core.vbs sees the key
        self.assertIn('Sub Table1_KeyDown(ByVal Keycode)\r\n\tIf Keycode = 207 Then Controller.Switch(-4) = '
                      'Not Controller.Switch(-4) : Exit Sub', out)
        with self.assertRaises(ValueError):                        # twice is refused
            vpx_table.patch_script(out)

    def test_bridge_changes_are_vpinmame_arrays(self):
        self.assertIsNone(vpx_bridge.changes([]))                   # Empty: nothing changed
        self.assertEqual([[15, 255], [33, 0]], vpx_bridge.changes([["15", 255], [33, 0]]))

    def test_bridge_lamps_follow_the_output_mode(self):
        """UseVPMModSol = 2 (SolMask(2) = 2): lamps and GI 0-255; otherwise lamps 0/1 and GI 0-8."""
        class Link:
            def call(self, subcommand, **kwargs):
                return {"changed_lamps": [[1, 255], [2, 40]], "changed_gi_strings": [[0, 255]]}[subcommand]
        c = vpx_bridge.Controller()
        c.link = Link()
        self.assertEqual([[1, 1], [2, 0]], c.ChangedLamps())
        self.assertEqual([[0, 8]], c.ChangedGIStrings())
        c.SetSolMask(2, 2)
        self.assertEqual([[1, 255], [2, 40]], c.ChangedLamps())
        self.assertEqual([[0, 255]], c.ChangedGIStrings())
        self.assertTrue(c.Lamp(1))
        self.assertIsNone(c.RawDmdPixels())
