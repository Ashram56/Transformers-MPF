"""Attract mode: deff 1 (the attract pages) and leff 1 (the attract lamp show).

Started at power-up and after every game (OS event 0x08, attract_start [0x00000a84]): deff 1 and leff 1. On tf_180 both
are in the deff and leff tables with Tron's priorities and flags (deff 1: priority 1, background; leff 1:
priority 1); what leff 1 draws (game code 0x01009e78) comes with the ROM extraction's lamp effects, and the
attract pages with its display effects (tf/attract_pages.py: the page table 0x00030d10 walked as deff 1 does,
each page drawn from its op list with live texts). Power-up: os_start_308 [0x00000308] calls start_deff_5 [0x00006ecc]
(the OS init and the boot screen, deff 5, priority 254, 125 ticks) then attract_start [0x00000a84] in the same pass, so
deff 1 and leff 1 start at once, behind the boot screen (TRANSFORMERS, "-----" and the version, the language; QA V005).
"""
from tf.attract_pages import Walker
from tf.features import Feature

ORDER = 6
BOOT_SECONDS = 0            # power-up -> deff 1 + leff 1: same pass as the boot screen (os_start_308 [0x00000308])


class Attract(Feature):
    name = "attract"
    HOOKS = ("attract_start",)

    def __init__(self, os_):
        super().__init__(os_)
        self.machine.events.add_handler("init_phase_5", self._power_up)
        self.machine.events.add_handler("game_starting", self.stop)
        self._handle = None
        os_.attract_walker = self.walker = Walker(os_)

    def _power_up(self, **kwargs):
        self._handle = self.machine.clock.schedule_once(lambda: self.start(boot=True), BOOT_SECONDS)

    def stop(self, **kwargs):
        if self._handle:
            self.machine.clock.unschedule(self._handle)
            self._handle = None
        self.walker.stop()
        if self.os.leffs.is_running(1):
            self.os.leff_stop(1)

    def attract_start(self):
        """Event 0x08 at the end of the game: the game is still being torn down, so no game check."""
        self._show()

    def start(self, boot=False):
        self._handle = None
        if self.os.game:
            return
        if boot:
            self.os.deff_start(5)                  # start_deff_5 [0x00006ecc]: the boot screen first
        self._show()

    def _show(self):
        self.walker.start(self.machine.clock.get_time())   # deff_001_game_over [0x0103c584]: entry 0, pass 1
        self.os.deff_start(1)
        self.os.leff_start(1, loop=True)


feature = Attract
