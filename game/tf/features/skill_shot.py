"""Skill shot and super skill shot (rom/rules/modes/game_flow.md 5.1; code [0x01031928] [0x01031518]
[0x0103177c] [0x01031630] [0x01031848] + observed in traces/game_flow.jsonl t 18.79, 55.12, 80.86).

Armed on every serve of type 3 or 4 (a new ball) by the event 0x0f hook; a ball-save serve (type 1)
cancels both.
- Top-lane skill shot (task 0xb2): the player's own lane, Autobot the right top lane (sw7), Decepticon the
  left one (sw8). After the side choice a flipper press moves it to the other lane and sets game flag 0x11
  (not hands free). The lit lane: hands free 350,000 + 25,000 x hands-free skill shots made this game, else
  250,000 + 25,000 x regular ones (cap 500,000); deff 42, leff 93, sound 0x165; the lane lights both of its
  lamps (one more lane award, tf/features/lanes.py). The unlit lane cancels it. It ends on a force switch
  other than 7, 8, 12 or after 3 different valid switches other than those.
- Super skill shot (task 0xb4): the Megatron back door (sw13): 500,000 + 100,000 x super skill shots made
  (cap 1,000,000); deff 43 queued (show task 0x65), leff 94, sound 0x167. It ends on a force switch other
  than 12, 13 or 3 different valid switches other than those. Slings and pops end neither.
"""
from tf.features import Feature

ORDER = 20
AUTOBOT = 1
LANE = {AUTOBOT: 7}                 # own lane by side (Decepticon: 8)
NOT_HANDS_FREE = 0x11
SKILL_DEFF = 42
SUPER_DEFF, SUPER_TASK = 43, 0x65
# the skill shots' own count of valid switches (obj 0x31400 / 0x3140c): slings and pops do not end them
SKILL_COUNTING = {1, 2, 4, 5, 6, 13, 35, 37, 46, 49, 50}


class SkillShot(Feature):
    name = "skill_shot"
    HOOKS = ("player_first_ball", "ball_served", "switch", "ball_end", "tilt")

    def __init__(self, os_):
        super().__init__(os_)
        self.top = self.super = False
        self.lane = 8
        self.seen_top, self.seen_super = set(), set()
        self.value = 0
        sc = self.machine.switch_controller
        for name in ("s_l_flipper_button", "s_r_flipper_button"):
            if name in self.machine.switches:
                sc.add_switch_handler(name, self._flipper)
        os_.deff_live((SKILL_DEFF, SUPER_DEFF), lambda: {"values": [self.value]})

    def player_first_ball(self):
        self.pd.skill_hands_free = self.pd.skill_regular = self.pd.super_skill = 0

    def ball_served(self, serve_type):
        if serve_type in (3, 4):
            self.top = self.super = True
            self.seen_top, self.seen_super = set(), set()
            self.lane = LANE.get(self.pd.get("side", 2), 8)
            self.os.flag_clear(NOT_HANDS_FREE)
        elif serve_type == 1:
            self.cancel()

    def _flipper(self):
        os_ = self.os
        if not self.top or not os_.game or os_.tilted:
            return
        if os_.hook("side_choosing"):
            self.lane = 8 if self.lane == 7 else 7    # side and lane toggle together
            return
        self.lane = 8 if self.lane == 7 else 7
        os_.flag_set(NOT_HANDS_FREE)

    def switch(self, num):
        os_ = self.os
        if os_.tilted:
            return
        if self.top:
            if num == self.lane:
                self._award_top(num)
            elif num in (7, 8):
                self.top = False
            elif self._ends(num, (7, 8, 12), self.seen_top):
                self.top = False
        if self.super:
            if num == 13:
                self._award_super()
            elif self._ends(num, (12, 13), self.seen_super):
                self.super = False

    def _ends(self, num, exempt, seen):
        from tf.os_layer import FORCE_SWITCHES
        if num in exempt:
            return False
        if num in FORCE_SWITCHES:
            return True
        if num in SKILL_COUNTING:
            seen.add(num)
            return len(seen) >= 3
        return False

    def _award_top(self, num):
        os_ = self.os
        pd = self.pd
        if os_.flag(NOT_HANDS_FREE):
            self.value = min(250000 + 25000 * pd.skill_regular, 500000)
            pd.skill_regular += 1
        else:
            self.value = min(350000 + 25000 * pd.skill_hands_free, 500000)
            pd.skill_hands_free += 1
        self.cancel()
        os_.score_add(self.value)
        os_.deff_start(SKILL_DEFF, values=[self.value])     # its sound 0x165 and leff 93 come with it
        os_.hook("lane_award", num)

    def _award_super(self):
        os_ = self.os
        pd = self.pd
        self.value = min(500000 + 100000 * pd.super_skill, 1000000)
        pd.super_skill += 1
        self.cancel()
        os_.score_add(self.value)
        os_.show(SUPER_TASK, SUPER_DEFF, values=[self.value])   # sound 0x167 and leff 94 with the deff

    def cancel(self):
        self.top = self.super = False

    def ball_end(self):
        self.cancel()

    tilt = ball_end


def feature(os_):
    return SkillShot(os_)
