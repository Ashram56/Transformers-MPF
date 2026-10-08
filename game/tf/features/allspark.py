"""The Allspark: the left eject (sw 3, coil 22) and its mystery award (rom/rules/modes/allspark_and_energon.md
5.2-5.3; code [0x0100a754] [0x0100a788] [0x010243b4] [table 0x040dde30] + observed in
traces/allspark_energon.jsonl and the battle traces).

The eject holds its ball (ball hold hold_left_eject). The device settles 47 ticks (observed 0.76 s), then the
rule runs (not when tilted): audit 0x45; every battle with shot 0 (tf/features/battles.py); the mystery award if
an Allspark is banked; mode-start shot 0; combo shot 0; the handler's bonus count and 5,070. The kickout waits
while a show runs (the award, a battle intro), then sound 0x157 + leff 21, 54 ticks later 0x158 + leff 22 and
coil 22 (observed: 36.27 / 37.15 s with nothing showing; after deff 52 with the award).

Mystery award (one banked Allspark spent): a weighted pick over 12 items (each item's weight is 0 when it was
the last award; ADD-A-BALL only in a multiball and once, ADD MORE TIME only in a timed mode and once per mode,
each +1000 when offered: they win), show task 0x5e with deff 52 (0x140, the item's 0x143 / 0x142 / 0x144,
0x141), the item's audit 74 + item. Competition mode (adj 42) forces a fixed sequence (step 9 at game start:
POPS first). Leff 40 pulses the Allspark flasher while one is banked.
Not modelled yet: the wizard / Megatron / Optimus calls in the rule, and super spinner / super pops play
(their "lit" states are kept: pd.super_spinner, pd.super_pops with leff 32).
"""
from tf.features import Feature

ORDER = 30
SWITCH = "s_left_eject"
SETTLE_TICKS = 47
POLL_TICKS = 6
EJECT_TICKS = 54
WARN_SOUND, WARN_LEFF = 0x157, 21
EJECT_SOUND, EJECT_LEFF = 0x158, 22
RELEASE_EVENT = "tf_hold_release"
ENTER_AUDIT = 0x45
POINTS = 5070
BANKED_LEFF = 40
AWARD_TASK, AWARD_DEFF = 0x5e, 52
AWARD_SOUNDS = (0x140, 0x141)
ITEM_SOUND = {5: 0x143, 6: 0x142}
ITEM_SOUND_OTHER = 0x144
ITEM_SOUND_AT, END_SOUND_AT = 0.2, 1.63
BASE_WEIGHT = {1: 1, 2: 5, 3: 200, 4: 150, 5: 300, 6: 250, 7: 150, 8: 100, 9: 100, 10: 100, 11: 100, 12: 100}
COMPETITION_ITEM = {0: 1, 1: 2, 2: 3, 3: 12, 4: 11, 5: 10, 6: 9, 7: 8, 8: 4, 9: 7}
ITEM_AUDIT = 74                         # + item: MYSTERY: LIGHT SPECIAL (75) .. SUPER POPS LIT (86)
ADD_BALL_FLAG, ADD_TIME_FLAG = 0x14, 0x13
BONUS_HOLD, BONUS_X_HOLD = 0x4b, 0x4a
SUPER_POPS_DEFF, SUPER_POPS_TASK, SUPER_POPS_LEFF, SUPER_POPS_AUDIT = 149, 0x5f, 32, 157


class Allspark(Feature):
    name = "allspark"
    HOOKS = ("player_first_ball", "allspark_bank")

    def __init__(self, os_):
        super().__init__(os_)
        self.machine.switch_controller.add_switch_handler(SWITCH, self._entered)
        self.machine.events.add_handler("balldevice_bd_left_eject_ball_eject_success", self._eject_success)
        os_.lamp_rule(lambda: bool(os_.game) and self.pd.get("allspark_lit", 0) > 0, leff=BANKED_LEFF,
                      order=0x01024f24)
        os_.lamp_rule(lambda: bool(os_.game) and bool(self.pd.get("super_pops")), leff=SUPER_POPS_LEFF,
                      order=0x0102d520)

    def player_first_ball(self):
        pd = self.pd
        pd.allspark_lit = 0
        pd.allspark_last = 0
        pd.allspark_step = 9
        pd.super_pops = pd.super_spinner = False

    def allspark_bank(self):
        self.pd.allspark_lit = self.pd.get("allspark_lit", 0) + 1

    # ------------------------------------------------------------------ the eject

    def _entered(self):
        os_ = self.os
        if not os_.game:
            return
        if os_.in_play:
            os_.playfield_switch(3)
        os_.ball_held = True
        os_.after(SETTLE_TICKS, self._settled)

    def _settled(self):
        os_ = self.os
        if os_.game and os_.in_play and not os_.tilted:
            self.rule()
        self._kickout()

    def rule(self):
        """[0x0100a788] event 2, ball entered."""
        os_ = self.os
        os_.audit(ENTER_AUDIT)
        os_.hook("battle_shot", 0)
        if self.pd.get("allspark_lit", 0) > 0:
            self.award()
        os_.hook("mode_start_shot", 0)
        os_.hook("combo_shot", 0)
        os_.hook("bonus_add")
        os_.base_score(POINTS)
        os_.request_refresh()

    def _kickout(self):
        """Event 7: wait for the show tasks, then the warning (0x157, leff 21) and the eject."""
        os_ = self.os
        if not self.machine.switches[SWITCH].state:
            os_.ball_held = False
            return
        if os_.show_running():
            os_.after(POLL_TICKS, self._kickout)
            return
        if os_.game and not os_.state & 0x310:
            os_.sound(WARN_SOUND)
            os_.leff_start(WARN_LEFF)
            os_.after(EJECT_TICKS, self._eject)
        else:
            self._eject()

    def _eject(self):
        os_ = self.os
        if os_.game and not os_.state & 0x312:
            os_.sound(EJECT_SOUND)
            os_.leff_start(EJECT_LEFF)
        os_.ball_held = False
        os_.device_released_at = os_.now
        os_.device_ejecting = True
        os_.ball_search_reload()
        self.machine.events.post(RELEASE_EVENT)

    def _eject_success(self, **kwargs):
        """MPF confirms the eject (a playfield switch or the 2 s timeout): ball search may run again (observed:
        battle_blackout, a search 10.9 s after the eject with no switch in between)."""
        self.os._device_eject_confirmed()
        self.os.device_ejecting = False

    # ------------------------------------------------------------------ the mystery award

    def weights(self):
        os_ = self.os
        pd = self.pd
        last = pd.get("allspark_last", 0)
        w = dict(BASE_WEIGHT)
        if not os_.any_multiball() or os_.flag(ADD_BALL_FLAG):
            w[5] = 0
        else:
            w[5] += 1000
        if not os_.timed_mode_running() or os_.flag(ADD_TIME_FLAG):
            w[6] = 0
        else:
            w[6] += 1000
        if pd.get("super_pops"):
            w[7] = w[12] = 0
        if os_.flag(BONUS_HOLD):
            w[8] = 0
        if os_.flag(BONUS_X_HOLD):
            w[9] = 0
        if all(m >= 2 for m in pd.get("shot_mult", [1] * 6)):
            w[10] = 0
        if pd.get("super_spinner"):
            w[11] = 0
        if last in w and last not in (5, 6):
            w[last] = 0
        if os_.adj[42] or os_.flag(0x0f):
            forced = COMPETITION_ITEM.get(pd.get("allspark_step", 9))
            if forced and w.get(forced, 0) < 1000:
                w[forced] = (w[forced] or 0) + 1000
        return [w[i] for i in range(1, 13)]

    def award(self):
        """[0x010243b4]."""
        os_ = self.os
        pd = self.pd
        os_.display.cancel(AWARD_TASK)
        pick = os_.pick("allspark", self.weights())
        if pick is None:
            return
        item = pick + 1
        sound = ITEM_SOUND.get(item, ITEM_SOUND_OTHER)
        os_.show(AWARD_TASK, AWARD_DEFF, values=[pd.get("bonus_x", 1) + (1 if item == 4 else 0)], sounds=[
            (0.0, lambda: os_.sound(AWARD_SOUNDS[0], in_deff=AWARD_DEFF)),
            (ITEM_SOUND_AT, lambda: os_.sound(sound, in_deff=AWARD_DEFF)),
            (END_SOUND_AT, lambda: os_.sound(AWARD_SOUNDS[1], in_deff=AWARD_DEFF))])
        self.run(item)
        os_.audit(ITEM_AUDIT + item)
        pd.allspark_last = item
        pd.allspark_lit = pd.get("allspark_lit", 0) - 1
        step = pd.get("allspark_step", 9)
        pd.allspark_step = (10 if step == 0 else step) - 1

    def run(self, item):
        os_ = self.os
        pd = self.pd
        if item == 1:
            os_.specials_lit[os_.player_num - 1] += 1
            os_.special_lamp_update()
        elif item == 2:
            os_.light_extra_ball()
        elif item == 3:
            os_.score_add(200000)
        elif item == 4:
            os_.hook("bonus_x_add")
        elif item == 5:
            os_.flag_set(ADD_BALL_FLAG)
            os_.multiball_start(os_.rom_balls_in_play() + 1)
            os_.hook("add_ball")
        elif item == 6:
            os_.hook("add_time")
            os_.flag_set(ADD_TIME_FLAG)
        elif item == 7:
            pops = os_.features_by_name.get("pops")
            if pops:
                pops.grow()
        elif item == 8:
            os_.flag_set(BONUS_HOLD)
        elif item == 9:
            os_.flag_set(BONUS_X_HOLD)
        elif item == 10:
            os_.hook("shot_mult_light")
        elif item == 11:
            pd.super_spinner = True
        elif item == 12:
            pd.super_pops = True
            os_.audit(SUPER_POPS_AUDIT)
            os_.show(SUPER_POPS_TASK, SUPER_POPS_DEFF)
        os_.request_refresh()


def feature(os_):
    return Allspark(os_)
