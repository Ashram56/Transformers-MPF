"""End-of-ball bonus, display effect 25 (rom/rules/modes/combos_and_multipliers.md section 7; code + observed).

bonus = (670 x bonus_count + held_bonus) x bonus_mult, added with playfield multiplier 1 [0x01000ffc]:
- bonus_count (RAM 0x34b3c + 2(p-1)): 0 at ball start (event 0x13 hook 0x01000d58), +1 for every playfield
  switch handler through 0x1032d2c -> 0x01000dfc (tf/switches.py calls hook bonus_add);
- held_bonus (0x2111ce0 + 4(p-1)): 125,000 at ball start unless BONUS HOLD (game flag 0x4b); with it, the end
  of that ball stores 670 x count + held as the next ball's held bonus (0x01000f68; inferred end of ball);
- bonus_mult (0x2111cf0 + (p-1)): 1 at ball start unless BONUS X HOLD (flag 0x4a); +1 per call of 0x01000e44
  (hook bonus_x_add: the other side's lanes, the "%iX BONUS MULTIPLIER" award), cap 25.
Checked against every reference trace's bonus (127,680 / 130,360 / 128,350 / 333,080 at 2X / 135,050).
Deff 25 starts at the end of ball (caller 0x19fb8) and plays its own sounds (the capture's: 0x20 Decepticon /
0x21 Autobot at the start, 0x77 0x78 0x79 0x7a); the total is added 338 ticks later, as the next ball starts
(observed: traces/sounds.jsonl deff 25 at 114.471 s, bonus 119.967 s; it runs longer at higher multipliers).
"""
from tf.features import Feature

UNIT = 670
HELD = 125000
MAX_X = 25
BONUS_X_HOLD, BONUS_HOLD = 0x4a, 0x4b
BONUS_TICKS = 338
SIDE_SOUND = {1: 0x21, 2: 0x20}       # the deff's first sound by side (Autobot / Decepticon)


class Bonus(Feature):
    name = "bonus"
    HOOKS = ("player_first_ball", "ball_start", "bonus_add", "bonus_x_add")

    def player_first_ball(self):
        self.pd.bonus_x = 1
        self.pd.bonus_held = HELD

    def ball_start(self):
        """0x01000d58: count 0; held bonus and multiplier back unless held (flags 0x4b / 0x4a)."""
        pd = self.pd
        if self.os.flag(BONUS_HOLD) and pd.get("bonus_count") is not None:
            pd.bonus_held = UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", HELD)
        else:
            pd.bonus_held = HELD
        if not self.os.flag(BONUS_X_HOLD):
            pd.bonus_x = 1
        pd.bonus_count = 0

    def bonus_add(self, n=1):
        """0x1000dfc: +1 bonus count."""
        if self.os.game:
            self.pd.bonus_count = self.pd.get("bonus_count", 0) + n

    def bonus_x_add(self):
        """0x1000e44: +1 multiplier, capped at 25."""
        self.pd.bonus_x = min(self.pd.get("bonus_x", 1) + 1, MAX_X)

    def total(self):
        pd = self.pd
        return (UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", HELD)) * pd.get("bonus_x", 1)

    def run(self, done):
        os_ = self.os
        total = self.total()
        side = self.pd.get("side", 2)
        captured = os_.display.media.get(25)
        sounds = [(t, (lambda c: lambda: os_.sound(c, in_deff=25))(SIDE_SOUND.get(side, c) if c in (0x20, 0x21)
                                                                    else c))
                  for t, c in (captured.sounds if captured else [])]
        pd = self.pd
        subtotal = UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", HELD)
        # deff 25 prints "1X" (a constant 1, fit font [0x01001170]) over the value, then the total (which values:
        # inferred); the 2X.. pages of a higher multiplier are not in the capture
        os_.deff_start(25, sounds=sounds, total=total, values=[1, subtotal, total])
        os_.after(BONUS_TICKS, lambda: done(total))


def feature(os_):
    return Bonus(os_)
