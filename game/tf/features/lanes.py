"""The Megatron (left, purple) and Optimus (right, red) lanes (rom/rules/modes/combos_and_multipliers.md
section 5; code [0x0102db28] [0x0102e208] + observed in traces/scoring.jsonl).

- Lamp group 76 (Megatron): 50 PURPLE/BOT, 51 PURPLE/TOP, 8 LEFT OUTLANE, 9 LEFT RETURN LANE; group 77
  (Optimus): 52 RED/TOP, 49 RED/BOT, 10 RIGHT RETURN LANE, 11 RIGHT OUTLANE.
- Switch 8 lights 51 (50 when 51 is lit), 24 lights 8, 25 lights 9; switch 7 lights 52 (49 when 52 is lit),
  28 lights 10, 29 lights 11.
- Lamp already lit: 1,000, leff 98 / 101, sound 0x168 / 0x16c. Lamp lit now: 2,500, leff 97 / 100, sound
  0x169 / 0x16d. The 4th lamp completes the group: lamps cleared, completions + 1, 10,000, leff 99 / 102,
  sound 0x16a / 0x16e; the player's own side (Decepticon left, Autobot right) lights the shot multipliers
  (deff 44, tf/features/combos.py), the other side adds 1 to the bonus multiplier (deff 45 "%dX BONUS").
- Each flipper press (not during the side choice, bonus, tilt or attract) moves the lit lamps of one group
  one position: left flipper 50 -> 51 -> 8 -> 9 -> 50, right flipper 52 -> 49 -> 10 -> 11 -> 52 (code; the
  direction was not traced).
Inferred: the lamps are per player and kept from ball to ball (the spec has them as lamp state).
"""
from tf.features import Feature

ORDER = 30
AUTOBOT, DECEPTICON = 1, 2
GROUPS = {"left": (50, 51, 8, 9), "right": (52, 49, 10, 11)}
SIDE_OF = {"left": DECEPTICON, "right": AUTOBOT}
LAMP = {8: ("left", (51, 50)), 24: ("left", (8,)), 25: ("left", (9,)),
        7: ("right", (52, 49)), 28: ("right", (10,)), 29: ("right", (11,))}
LIT = {"left": (1000, 0x168, 98), "right": (1000, 0x16c, 101)}
NEW = {"left": (2500, 0x169, 97), "right": (2500, 0x16d, 100)}
DONE = {"left": (10000, 0x16a, 99), "right": (10000, 0x16e, 102)}
SHOT_MULT_DEFF, BONUS_X_DEFF = 44, 45


class Lanes(Feature):
    name = "lanes"
    HOOKS = ("player_first_ball", "ball_start", "lane_award") + tuple("sw_{}".format(n) for n in LAMP)

    def __init__(self, os_):
        for num in LAMP:
            setattr(self, "sw_{}".format(num), (lambda n: lambda: self.lane_award(n))(num))
        super().__init__(os_)
        sc = self.machine.switch_controller
        for name, group in (("s_l_flipper_button", "left"), ("s_r_flipper_button", "right")):
            if name in self.machine.switches:
                sc.add_switch_handler(name, (lambda g: lambda: self._flipper(g))(group))
        os_.lamp_update(self.draw)

    def lit(self, group):
        return self.pd.get("lanes_" + group, set())

    def player_first_ball(self):
        self.pd.lanes_left, self.pd.lanes_right = set(), set()
        self.pd.lanes_left_done = self.pd.lanes_right_done = 0

    def ball_start(self):
        self.draw()

    def draw(self):
        if not self.os.game:
            return
        for group, lamps in GROUPS.items():
            for n in lamps:
                if n in self.lit(group):
                    self.os.lamps.lamp_on(n)
                else:
                    self.os.lamps.lamp_off(n)

    def lane_award(self, num):
        """The lane function of switch `num` (a made top-lane skill shot calls it twice)."""
        os_ = self.os
        if os_.tilted:
            return
        group, choices = LAMP[num]
        lit = self.lit(group)
        lamp = next((n for n in choices if n not in lit), None)
        if lamp is None:
            points, sound, leff = LIT[group]
        else:
            lit.add(lamp)
            points, sound, leff = NEW[group]
            if len(lit) == len(GROUPS[group]):
                lit.clear()
                self.pd["lanes_{}_done".format(group)] += 1
                points, sound, leff = DONE[group]
        os_.score_add(points)
        os_.sound(sound)
        os_.leff_start(leff)
        self.draw()
        if leff == DONE[group][2]:
            if SIDE_OF[group] == self.pd.get("side", DECEPTICON):
                os_.hook("shot_mult_light")
            else:
                os_.hook("bonus_x_add")
                os_.deff_start(BONUS_X_DEFF, values=[self.pd.get("bonus_x", 1)])

    def _flipper(self, group):
        os_ = self.os
        if not os_.game or not os_.in_play or os_.state & 0x205 or os_.hook("side_choosing"):
            return
        order = GROUPS[group]
        key = "lanes_" + group
        self.pd[key] = {order[(order.index(n) + 1) % len(order)] for n in self.lit(group)}
        self.draw()


def feature(os_):
    return Lanes(os_)
