"""Energon targets (rom/rules/modes/allspark_and_energon.md 5.1; code [0x010309a4] + observed in
traces/allspark_energon.jsonl).

Three standups: left sw 2, center sw 49, right sw 46 (bits 1 / 2 / 4 of energon_lit, per player).
- During a multiball ([0x0103096c] -> [0x01006704], the multiball flags; not during a battle timer, observed
  traces/switches.jsonl 128.67 s): 5,000, sound 0x25c, leff 139; nothing lights.
- Within 10 ticks of a completed set (task 0xb0): nothing.
- A lit target, set not complete: 10,000, sound 0x25d, leff 141.
- An unlit target that is not the last: lit, 75,000, deff 124, leff 140, sound 0x25e and 0x25f one second
  later (task 0x97, observed 1.01 s).
- The third one: set complete: 250,000 + 25,000 x sets before (cap 750,000), deff 125 "ALLSPARK LIT", leff 142,
  sound 0x260 (0x13e, 0x13f from the deff); energon_sets + 1, the targets unlit, one Allspark banked
  (tf/features/allspark.py). The Megatron lock lighting it also calls comes with the Megatron spec.
The switch's own 1,110 follows (tf/switches.py). Inserts 48 / 54 / 35: unlit flash, lit solid (observed).
Deffs 124 and 125 have no capture: their lengths are inferred (1.0 s, 2.0 s), 0x13f at 1.13 s is observed.
"""
from tf.features import Feature

TARGETS = {2: 0, 49: 1, 46: 2}
LAMPS = (48, 54, 35)
ALL = 0x07
TIMED = (5000, 0x25c, 139)
RELIT = (10000, 0x25d, 141)
LIT_POINTS, LIT_DEFF, LIT_LEFF, LIT_SOUND, LIT_SOUND2, LIT_SOUND2_TICKS = 75000, 124, 140, 0x25e, 0x25f, 62
SET_DEFF, SET_LEFF, SET_SOUND = 125, 142, 0x260
SET_BASE, SET_STEP, SET_CAP = 250000, 25000, 750000
DEBOUNCE_TASK, DEBOUNCE_TICKS = 0xb0, 10
SOUND_TASK = 0x97


class Energon(Feature):
    name = "energon"
    HOOKS = ("player_first_ball", "sw_2", "sw_49", "sw_46")

    def __init__(self, os_):
        super().__init__(os_)
        os_.display.set_media(LIT_DEFF, 1.0, (), ())
        os_.display.set_media(SET_DEFF, 2.0, (), ((0.0, 0x13e), (1.13, 0x13f)))
        os_.lamp_update(self.draw)

    def player_first_ball(self):
        self.pd.energon_lit = 0
        self.pd.energon_sets = 0

    def sw_2(self):
        self.hit(0)

    def sw_49(self):
        self.hit(1)

    def sw_46(self):
        self.hit(2)

    def hit(self, index):
        os_ = self.os
        if os_.tilted:
            return
        pd = self.pd
        if os_.any_multiball():                 # [0x0103096c]
            self._award(*TIMED)
            return
        if os_.task_running(DEBOUNCE_TASK):
            return
        bit = 1 << index
        lit = pd.get("energon_lit", 0)
        if lit & bit and lit != ALL:
            self._award(*RELIT)
            return
        if (lit | bit) != ALL:
            pd.energon_lit = lit | bit
            os_.deff_start(LIT_DEFF, values=[pd.energon_lit, bit])
            os_.leff_start(LIT_LEFF)
            os_.sound(LIT_SOUND)
            os_.task_start(SOUND_TASK, LIT_SOUND2_TICKS, lambda: os_.sound(LIT_SOUND2))
            os_.score_add(LIT_POINTS)
            os_.request_refresh()
            return
        sets = pd.get("energon_sets", 0)
        os_.deff_start(SET_DEFF)
        os_.leff_start(SET_LEFF)
        os_.sound(SET_SOUND)
        os_.score_add(min(SET_BASE + SET_STEP * sets, SET_CAP))
        os_.task_start(DEBOUNCE_TASK, DEBOUNCE_TICKS)
        pd.energon_sets = min(sets + 1, 255)
        pd.energon_lit = 0
        os_.hook("allspark_bank")
        os_.request_refresh()

    def _award(self, points, sound, leff):
        os_ = self.os
        os_.sound(sound)
        os_.leff_start(leff)
        os_.score_add(points)

    def draw(self):
        lamps = self.os.lamps
        lit = self.pd.get("energon_lit", 0)
        for i, lamp in enumerate(LAMPS):
            if lit & (1 << i):
                lamps.lamp_on(lamp)
            else:
                lamps.lamp_flash(lamp)


def feature(os_):
    return Energon(os_)
