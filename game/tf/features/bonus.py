"""End-of-ball bonus, display effect 25 (rom/rules/switches_and_shots.md "End-of-ball bonus"; code + observed).

- Base = 670 x bonus count (u16 per player, RAM 0x34b3c, +1 from 11 shot functions through 0x1000dfc) + the
  held bonus (u32 per player, NVRAM 0x02111ce0, saved by 0x1000f68 while game flag 0x4b is set).
- Multiplier: u8 per player (0x02111cef), +1 per call of 0x1000e44, capped at 25. Total = base x multiplier.
- Deff 25 starts at the end of ball (caller 0x19fb8) and plays its own sounds (the capture's: 0x20 Decepticon
  at the start, 0x77 0x78 0x79 0x7a); the total is added 338 ticks later, as the next ball starts (observed:
  traces/sounds.jsonl deff 25 at 114.471 s, bonus 119.967 s).
Open: which shots add to the count and the multiplier (the 11 callers of 0x1000dfc, the callers of 0x1000e44)
and when the held bonus is kept; the sounds.jsonl bonus (127,680) is not a multiple of 670 with multiplier 1.
Until then no shot adds bonus (hooks bonus_add / bonus_x_add are ready for the features).
"""
from tf.features import Feature

UNIT = 670
MAX_X = 25
BONUS_TICKS = 338
SIDE_SOUND = {1: 0x21, 2: 0x20}       # the deff's first sound by side (Autobot / Decepticon)


class Bonus(Feature):
    name = "bonus"
    HOOKS = ("player_first_ball", "bonus_add", "bonus_x_add")

    def player_first_ball(self):
        self.pd.bonus_count = 0
        self.pd.bonus_x = 1
        self.pd.bonus_held = 0

    def bonus_add(self, n=1):
        """0x1000dfc: +1 bonus count."""
        self.pd.bonus_count = self.pd.get("bonus_count", 0) + n

    def bonus_x_add(self):
        """0x1000e44: +1 multiplier, capped at 25."""
        self.pd.bonus_x = min(self.pd.get("bonus_x", 1) + 1, MAX_X)

    def total(self):
        pd = self.pd
        return (UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", 0)) * pd.get("bonus_x", 1)

    def run(self, done):
        os_ = self.os
        total = self.total()
        side = self.pd.get("side", 2)
        captured = os_.display.media.get(25)
        sounds = [(t, (lambda c: lambda: os_.sound(c, in_deff=25))(SIDE_SOUND.get(side, c) if c in (0x20, 0x21)
                                                                    else c))
                  for t, c in (captured.sounds if captured else [])]
        pd = self.pd
        subtotal = UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", 0)
        # deff 25 prints the value under the multiplier, then the total (which values: inferred)
        os_.deff_start(25, sounds=sounds, total=total, values=[subtotal, total])
        os_.after(BONUS_TICKS, lambda: done(total))


def feature(os_):
    return Bonus(os_)
