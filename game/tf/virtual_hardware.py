"""Desktop / MPF Monitor only (hw_virtual.yaml overlay): the trough and the Megatron lock keep their balls the way the
machine does.

MPF Monitor's click on a switch is a press and a release. smart_virtual counts a device's balls from its active
switches, so a click on a trough or lock switch (a drain, a ball entering the lock) put a ball in and took it out
again 50-100 ms later, before the device counted it: no drain, no new ball in the shooter lane, no lock. And it takes
a ball out by clearing the first active switch and adds one on the first free switch, so the switches never showed
the real trough's behaviour.

Here each device keeps its own ball count: a press of one of its switches is a ball arriving (its release does not
take it away); a ball leaves only when the device ejects (its event balldevice_<name>_ejecting_ball, then
smart_virtual clears a switch). A moment after any change the balls are packed onto the switches from the eject end:
the trough's 1 (R), 2, 3, 4 (L), as its balls roll down; the lock's #1 (back) to #4, as the table's ball stack
bsKickerMegaTron fills (docs/vpx/switches.csv: slot 1 = s_m_tron_lock_1_back). The rules code is unchanged; the unit
tests and scenarios do not load this overlay.
"""
from mpf.core.custom_code import CustomCode

TROUGH = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")     # eject end first
LOCK = ("s_m_tron_lock_1_back", "s_megatron_lock_2", "s_megatron_lock_3", "s_megatron_lock_4")
ROLL_MS = 150


class _StackedDevice(CustomCode):
    """A ball device whose balls stack on its switches in order (SWITCHES, eject end first)."""

    SWITCHES = ()
    DEVICE = ""

    def on_load(self):
        self.balls = 0
        self.pressed = set()        # switches pressed by a click: their release keeps the ball
        self.ejecting = 0           # ejects announced by the device: the next unexplained clear is one of them
        self.packing = False
        self.machine.events.add_handler("init_phase_4", self._start)

    def _start(self, **kwargs):
        del kwargs
        controller = self.machine.switch_controller
        self.balls = sum(1 for name in self.SWITCHES if controller.is_active(self.machine.switches[name]))
        for name in self.SWITCHES:
            controller.add_switch_handler(name, self._entered, state=1, callback_kwargs={"name": name})
            controller.add_switch_handler(name, self._left, state=0, callback_kwargs={"name": name})
        self.machine.events.add_handler("balldevice_{}_ejecting_ball".format(self.DEVICE), self._ejecting)

    def _ejecting(self, **kwargs):
        del kwargs
        self.ejecting += 1

    def _entered(self, name):
        if self.packing:
            return
        self.balls = min(self.balls + 1, len(self.SWITCHES))
        self.pressed.add(name)
        self.delay.reset(ms=ROLL_MS, callback=self._roll, name="roll")

    def _left(self, name):
        if self.packing:
            return
        if self.ejecting:                   # the eject took a ball (smart_virtual cleared a switch)
            self.ejecting -= 1
            self.balls = max(self.balls - 1, 0)
        self.pressed.discard(name)          # else a click's release: the ball stays
        self.delay.reset(ms=ROLL_MS, callback=self._roll, name="roll")

    def _roll(self):
        controller = self.machine.switch_controller
        self.packing = True
        try:
            for position, name in enumerate(self.SWITCHES):
                switch = self.machine.switches[name]
                wanted = position < self.balls
                if controller.is_active(switch) != wanted:
                    controller.process_switch_obj(switch, int(wanted), logical=True)
                    if not wanted:
                        self.pressed.discard(name)
        finally:
            self.packing = False


class VirtualTrough(_StackedDevice):
    """A click on a trough switch is a drained ball; the balls roll to switch 1 (R)."""
    SWITCHES, DEVICE = TROUGH, "bd_trough"


class VirtualLock(_StackedDevice):
    """A click on a Megatron lock switch is a ball entering the lock; it stays until the lock kicks it out."""
    SWITCHES, DEVICE = LOCK, "bd_megatron"
