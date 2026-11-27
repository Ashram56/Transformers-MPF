"""The desktop overlay's virtual devices (tf/virtual_hardware.py): a click on a trough or lock switch is a ball that
stays until the device ejects it."""
from tests.tf_test import TfTestCase


class TestVirtualLock(TfTestCase):

    def setUp(self):
        super().setUp()
        from tf.virtual_hardware import VirtualLock
        self.lock = VirtualLock(self.machine, "virtual_lock")
        self.lock._start()

    def click(self, name):
        self.machine.switch_controller.process_switch(name, 1, True)
        self.advance_time_and_run(0.05)
        self.machine.switch_controller.process_switch(name, 0, True)

    def active(self):
        return [n for n in ("s_m_tron_lock_1_back", "s_megatron_lock_2", "s_megatron_lock_3", "s_megatron_lock_4")
                if self.machine.switch_controller.is_active(self.machine.switches[n])]

    def test_clicked_balls_stay_and_stack_from_the_back(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(4)
        self.assertIsNotNone(self.machine.game)
        self.click("s_megatron_lock_4")
        self.advance_time_and_run(0.3)
        self.assertEqual(self.active(), ["s_m_tron_lock_1_back"])
        self.assertEqual(self.lock.balls, 1)
        self.advance_time_and_run(3)            # the game's ball hold keeps it
        self.assertEqual(self.active(), ["s_m_tron_lock_1_back"])
        self.assertEqual(self.machine.ball_devices["bd_megatron"].balls, 1)
        self.click("s_megatron_lock_4")
        self.advance_time_and_run(3)
        self.assertEqual(self.active(), ["s_m_tron_lock_1_back", "s_megatron_lock_2"])

    def test_an_eject_takes_the_ball(self):
        self.fill_trough()
        self.click("s_megatron_lock_3")
        self.advance_time_and_run(0.3)
        self.assertEqual(self.lock.balls, 1)
        self.advance_time_and_run(5)            # no game: the device kicks the unexpected ball out
        self.assertEqual(self.active(), [])
        self.assertEqual(self.lock.balls, 0)


class TestVirtualTrough(TfTestCase):

    def test_a_clicked_drain_serves_the_next_ball(self):
        from tf.virtual_hardware import VirtualTrough
        trough = VirtualTrough(self.machine, "virtual_trough")
        trough._start()
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(3)
        sw = self.machine.switch_controller
        self.assertTrue(sw.is_active(self.machine.switches["s_shooter_lane"]))
        self.assertEqual(3, trough.balls)
        sw.process_switch("s_shooter_lane", 0, True)       # plunged
        self.advance_time_and_run(1)
        from tf.switches import SW
        self.hit_and_release_switch(SW[10])                 # a switch that validates the playfield
        self.advance_time_and_run(30)                       # past the ball save
        sw.process_switch("s_trough_4_l", 1, True)          # MPF Monitor click: the ball drains
        self.advance_time_and_run(0.05)
        sw.process_switch("s_trough_4_l", 0, True)
        self.advance_time_and_run(8)
        self.assertEqual(2, self.machine.game.player.ball)
        self.assertTrue(sw.is_active(self.machine.switches["s_shooter_lane"]))
        self.assertEqual(3, trough.balls)
