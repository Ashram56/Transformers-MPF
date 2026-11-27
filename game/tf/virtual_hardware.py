"""Desktop / MPF Monitor only (hw_virtual.yaml overlay): the trough's balls roll toward the eject end.

MPF's smart_virtual platform takes a ball out of the trough by clearing the first active ball switch
(s_trough_1_r, the eject end) and adds one on the first free switch, so the trough switches never show the
real trough's behaviour: after an eject the remaining balls roll down to switch 1 (R), and a drained ball
lands behind them. Here, a moment after any trough switch changes, the balls in the trough are packed onto
switches 1 (R), 2, 3, 4 (L) in that order. The ball count never changes, so MPF's trough counting is not
disturbed. The rules code is unchanged; the unit tests and scenarios do not load this overlay.

The Megatron lock (VirtualLock) works the same way, as the table's ball stack does (the VPX table's
bsKickerMegaTron, docs/vpx/switches.csv: slot 1 = s_m_tron_lock_1_back first): a click on any lock switch in MPF
Monitor (pressed then released) is a ball entering the lock; it rolls to the first free place from #1 (back) and
keeps its switch active until the lock's coil kicks it out (smart_virtual clears a switch then). So the ball device
bd_megatron counts the balls as on the machine.
"""
from mpf.core.custom_code import CustomCode

TROUGH = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")     # eject end first
ROLL_MS = 150


class VirtualTrough(CustomCode):

    def on_load(self):
        self.machine.events.add_handler("init_phase_4", self._start)

    def _start(self, **kwargs):
        del kwargs
        for name in TROUGH:
            for state in (0, 1):
                self.machine.switch_controller.add_switch_handler(name, self._changed, state=state)

    def _changed(self):
        self.delay.reset(ms=ROLL_MS, callback=self._roll, name="roll")

    def _roll(self):
        controller = self.machine.switch_controller
        switches = [self.machine.switches[name] for name in TROUGH]
        balls = sum(1 for switch in switches if controller.is_active(switch))
        for position, switch in enumerate(switches):
            wanted = position < balls
            if controller.is_active(switch) != wanted:
                controller.process_switch_obj(switch, int(wanted), logical=True)


LOCK = ("s_m_tron_lock_1_back", "s_megatron_lock_2", "s_megatron_lock_3", "s_megatron_lock_4")


class VirtualLock(CustomCode):
    """The Megatron lock's balls: a press of a lock switch adds a ball (its release does not take it away), a
    switch cleared by the eject coil (smart_virtual) takes one; the balls are packed onto #1 (back) to #4."""

    def on_load(self):
        self.balls = 0
        self.pressed = set()
        self.packing = False
        self.machine.events.add_handler("init_phase_4", self._start)

    def _start(self, **kwargs):
        del kwargs
        controller = self.machine.switch_controller
        self.balls = sum(1 for name in LOCK if controller.is_active(self.machine.switches[name]))
        for name in LOCK:
            controller.add_switch_handler(name, self._entered, state=1, callback_kwargs={"name": name})
            controller.add_switch_handler(name, self._left, state=0, callback_kwargs={"name": name})

    def _entered(self, name):
        if self.packing:
            return
        self.balls = min(self.balls + 1, len(LOCK))
        self.pressed.add(name)
        self.delay.reset(ms=ROLL_MS, callback=self._roll, name="roll")

    def _left(self, name):
        if self.packing:
            return
        if name in self.pressed:            # the click's release: the ball stays in the lock
            self.pressed.discard(name)
        else:                               # the eject coil took a ball (smart_virtual)
            self.balls = max(self.balls - 1, 0)
        self.delay.reset(ms=ROLL_MS, callback=self._roll, name="roll")

    def _roll(self):
        controller = self.machine.switch_controller
        self.packing = True
        try:
            for position, name in enumerate(LOCK):
                switch = self.machine.switches[name]
                wanted = position < self.balls
                if controller.is_active(switch) != wanted:
                    controller.process_switch_obj(switch, int(wanted), logical=True)
                    if not wanted:
                        self.pressed.discard(name)
        finally:
            self.packing = False
