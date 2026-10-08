"""Attract mode: deff 1 (the attract pages) and leff 1 (the attract lamp show).

Started at power-up and after every game (OS event 0x08, Tron [0x000015d4]): deff 1 and leff 1. On tf_180 both
are in the deff and leff tables with Tron's priorities and flags (deff 1: priority 1, background; leff 1:
priority 1); what leff 1 draws (game code 0x01009e78) comes with the ROM extraction's lamp effects, and the
attract pages with its display effects. Tron's attract timings (power-up to deff 1: 0.992 s) are kept.
"""
from tf.features import Feature

ORDER = 6
BOOT_SECONDS = 0.992        # power-up -> deff 1 + leff 1 (Tron traces/attract_and_service.jsonl t 0.99)


class Attract(Feature):
    name = "attract"
    HOOKS = ("attract_start",)

    def __init__(self, os_):
        super().__init__(os_)
        self.machine.events.add_handler("init_phase_5", self._power_up)
        self.machine.events.add_handler("game_starting", self.stop)
        self._handle = None

    def _power_up(self, **kwargs):
        self._handle = self.machine.clock.schedule_once(lambda: self.start(), BOOT_SECONDS)

    def stop(self, **kwargs):
        if self._handle:
            self.machine.clock.unschedule(self._handle)
            self._handle = None
        if self.os.leffs.is_running(1):
            self.os.leff_stop(1)

    def attract_start(self):
        self.start()

    def start(self):
        self._handle = None
        if self.os.game:
            return
        self.os.deff_start(1)
        self.os.leff_start(1, loop=True)


feature = Attract
