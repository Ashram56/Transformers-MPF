"""Energon targets (rom/rules/modes/allspark_and_energon.md 5.1; code [0x010309a4], confirmed by
traces/allspark_energon.jsonl).

Three standups: left sw 2, center sw 49, right sw 46 (bits 1 / 2 / 4 of energon_lit, per player).
- During a multiball ([0x0103096c] -> [0x01006704], the multiball flags only, so not during a battle timer;
  traces/switches.jsonl 128.67 s confirms): 5,000, sound 0x25c, leff 139; nothing lights.
- Within 10 ticks of a completed set (task 0xb0): nothing.
- A lit target, set not complete: 10,000, sound 0x25d, leff 141.
- An unlit target that is not the last: lit, 75,000, deff 124, leff 140, sound 0x25e and, 62 ticks later
  (task 0x97 [0x01030984]), 0x25f under speech_once [0x01006ae0] (flag 0x47; at most twice a game with 0x265).
- The third one: set complete: 250,000 + 25,000 x sets before (cap 750,000), deff 125 "ALLSPARK LIT", leff 142,
  sound 0x260 (0x13e, 0x13f from the deff); energon_sets + 1, the targets unlit, one Allspark banked
  (tf/features/allspark.py). The Megatron lock lighting it also calls comes with the Megatron spec.
The switch's own 1,110 follows (tf/switches.py). Inserts 48 / 54 / 35: unlit flash, lit solid (lamp rule [0x01030f80]).
Deffs 124 and 125 have no capture: their lengths and sounds come from their op lists (agent A, the deff code run):
124 31 frames x 5 ticks + hold = 156 ticks; 125 142 ticks, 0x13e at 0 and 0x13f at tick 70 (QA V124, V125).
"""
from tf.features import Feature

TARGETS = {2: 0, 49: 1, 46: 2}
LAMPS = (48, 54, 35)
ALL = 0x07
TIMED = (5000, 0x25c, 139)
RELIT = (10000, 0x25d, 141)
# the targets' lamps: the switch handlers' argument (task +0x34, switches.csv handler_arg): sw 2, 49, 46
LAMPS = (48, 54, 35)
LIT_POINTS, LIT_DEFF, LIT_LEFF, LIT_SOUND, LIT_SOUND2, LIT_SOUND2_TICKS = 75000, 124, 140, 0x25e, 0x25f, 62
LIT_SOUND2_FLAG = 0x47               # task 0x97 [0x01030984]: sleep 0x3e, speech_once(0x25f, flag 0x47) [0x01006ae0]
SET_DEFF, SET_LEFF, SET_SOUND = 125, 142, 0x260
LIT_DEFF_TICKS, SET_DEFF_TICKS = 156, 142       # the op lists' end_tick (deff_124 [0x01030b94], deff_125 [0x01031038])
SET_BASE, SET_STEP, SET_CAP = 250000, 25000, 750000
DEBOUNCE_TASK, DEBOUNCE_TICKS = 0xb0, 10
SOUND_TASK = 0x97


class Energon(Feature):
    name = "energon"
    HOOKS = ("player_first_ball", "sw_2", "sw_49", "sw_46")

    def __init__(self, os_):
        super().__init__(os_)
        from tf.os_layer import TICK                     # noqa: PLC0415
        os_.display.set_media(LIT_DEFF, LIT_DEFF_TICKS * TICK, (), ())                   # deff_124.json end_tick
        os_.display.set_media(SET_DEFF, SET_DEFF_TICKS * TICK, (), ((0.0, 0x13e), (70 * TICK, 0x13f)))   # deff_125.json
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
            self._award(*TIMED, lamp=LAMPS[index])
            return
        if os_.task_running(DEBOUNCE_TASK):
            return
        bit = 1 << index
        lit = pd.get("energon_lit", 0)
        if lit & bit and lit != ALL:
            self._award(*RELIT, lamp=LAMPS[index])
            return
        if (lit | bit) != ALL:
            pd.energon_lit = lit | bit
            os_.deff_start(LIT_DEFF, values=[lit, bit])     # arg0: the set before the new bit [0x010309a4] (QA P18)
            os_.leff_start(LIT_LEFF)
            os_.sound(LIT_SOUND)
            os_.task_start(SOUND_TASK, LIT_SOUND2_TICKS, lambda: os_.speech_once(LIT_SOUND2, LIT_SOUND2_FLAG))
            os_.score_add(LIT_POINTS)
            os_.request_refresh()
            return
        sets = pd.get("energon_sets", 0)
        os_.deff_start(SET_DEFF)
        os_.leff_start(SET_LEFF)
        os_.sound(SET_SOUND)
        os_.score_add(min(SET_BASE + SET_STEP * sets, SET_CAP))
        os_.hook("lock_completion")                 # [0x01030b34] -> [0x0100af0c] (tf/features/megatron.py)
        os_.task_start(DEBOUNCE_TASK, DEBOUNCE_TICKS)
        pd.energon_sets = min(sets + 1, 255)
        pd.energon_lit = 0
        os_.hook("allspark_bank")
        os_.request_refresh()

    def _award(self, points, sound, leff, lamp=None):
        os_ = self.os
        os_.sound(sound)
        os_.leff_start(leff, lamp=lamp)     # leff 139 lights / 141 darkens the target's lamp (+0x30) [0x010309a4]
        os_.score_add(points)

    def draw(self):
        """Lamp rule [0x01030f80]: in a multiball all three off; else lit solid (0x00007858), not lit flashing
        (QA L-R06, L-G13)."""
        lamps = self.os.lamps
        lit = self.pd.get("energon_lit", 0)
        multiball = self.os.any_multiball()
        for i, lamp in enumerate(LAMPS):
            if multiball:
                lamps.lamp_off_all(lamp)
            elif lit & (1 << i):
                lamps.lamp_on_solid(lamp)
            else:
                lamps.lamp_flash(lamp)


def feature(os_):
    return Energon(os_)
