"""End-of-ball bonus, display effect 25 (rom/rules/modes/combos_and_multipliers.md section 7; code).

bonus = (670 x bonus_count + held_bonus) x bonus_mult, added with playfield multiplier 1 [0x01000ffc]:
- bonus_count (RAM 0x34b3c + 2(p-1)): 0 at ball start (event 0x13 hook 0x01000d58), +1 for every playfield
  switch handler through 0x1032d2c -> 0x01000dfc (tf/switches.py calls hook bonus_add);
- held_bonus (0x2111ce0 + 4(p-1)): 125,000 at ball start unless BONUS HOLD (game flag 0x4b); with it, the end
  of that ball stores 670 x count + held as the next ball's held bonus, not when tilted (0x01000f68, state & 0x200);
- bonus_mult (0x2111cf0 + (p-1)): 1 at ball start unless BONUS X HOLD (flag 0x4a); +1 per call of 0x01000e44
  (hook bonus_x_add: the other side's lanes, the "%iX BONUS MULTIPLIER" award), cap 25;
- both hold flags last one ball: the ball start hook clears them after use (game_flag_clear(0x4a) at
  0x01000d8c, (0x4b) at 0x01000dc4). QA 2026-11-25 P1.
Checked against every reference trace's bonus (127,680 / 130,360 / 128,350 / 333,080 at 2X / 135,050).
Deff 25 starts at the end of ball (caller 0x19fb8) and plays its own sounds (the capture's: 0x20 Decepticon /
0x21 Autobot at the start, 0x77 0x78 0x79 0x7a); the total is added when it ends, 338 ticks later at 1X (deff_025 [0x010014b8] run as ROM code:
rom/rom_data/dmd/deff_ops/deff_025.json end_tick; traces/sounds.jsonl confirms, deff 25 at 114.471 s, bonus 119.967 s). A multiplier above 1 adds its counting pages and
sound 0x76 [0x01000ffc] (x_extra_ticks; QA SC9): the deff runs as its variant "xN", the deff's code run with that
multiplier (rom/rom_data/dmd/deff_ops/deff_025__xN.json), whose pages print the count u and u x subtotal live.
"""
from tf.features import Feature

UNIT = 670
HELD = 125000
MAX_X = 25
BONUS_X_HOLD, BONUS_HOLD = 0x4a, 0x4b
BONUS_TICKS = 338
SIDE_SOUND = {1: 0x21, 2: 0x20}       # the deff's first sound by side (Autobot / Decepticon)
# a multiplier above 1 [0x01000ffc]: task_sleep(4), then one counting page per multiplier 2..x of 8 frames (4 from
# 6X), then snd_play(0x76) just before 0x79; everything from 0x79 on (tick 67 of the capture, at 1X) comes later
COUNT_START_TICKS, X_PAGE_TICKS, X_PAGE_TICKS_FAST, X_FAST_FROM = 4, 8, 4, 6
X_SOUND, X_SOUND_AT = 0x76, 67


def x_extra_ticks(x):
    """Ticks a bonus multiplier x adds to deff 25 [0x01000ffc]: 0 at 1X."""
    if x <= 1:
        return 0
    return COUNT_START_TICKS + sum(X_PAGE_TICKS if u < X_FAST_FROM else X_PAGE_TICKS_FAST for u in range(2, x + 1))


class Bonus(Feature):
    name = "bonus"
    HOOKS = ("player_first_ball", "ball_start", "ball_end", "bonus_add", "bonus_x_add")

    def player_first_ball(self):
        self.pd.bonus_x = 1
        self.pd.bonus_held = HELD

    def ball_end(self):
        """0x01000f68: with BONUS HOLD and not tilted, store 670 x count + held as the next ball's held bonus."""
        pd = self.pd
        if self.os.flag(BONUS_HOLD) and not self.os.tilted:
            pd.bonus_held = UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", HELD)

    def ball_start(self):
        """0x01000d58: count 0; held bonus and multiplier back unless held (flags 0x4b / 0x4a), then both flags
        cleared: a hold lasts one ball."""
        pd = self.pd
        if not self.os.flag(BONUS_HOLD):
            pd.bonus_held = HELD
        if not self.os.flag(BONUS_X_HOLD):
            pd.bonus_x = 1
        self.os.flag_clear(BONUS_X_HOLD)
        self.os.flag_clear(BONUS_HOLD)
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
        from tf.display import deff_variant  # noqa: PLC0415
        from tf.os_layer import TICK        # noqa: PLC0415
        pd = self.pd
        x = pd.get("bonus_x", 1)
        extra = x_extra_ticks(x)
        # at 2X and up, deff 25's run with that multiplier [0x01000ffc] (rom/tools/deff_variants.py: RAM 0x02111cf0
        # set to x): its counting pages, length and sounds (0x76 [0x01000ffc]); at 1X, the run at factory state
        variant = "x%d" % min(x, MAX_X) if x > 1 else None
        own = deff_variant(25, variant) if variant else None
        captured = own or os_.display.media.get(25)
        timeline = [(t, SIDE_SOUND.get(side, c) if c in (0x20, 0x21) else c) for t, c in (captured.sounds if captured else [])]
        if extra and not own:               # no op list of that run: the 1X run with the pages' length added
            timeline = [(t + extra * TICK if t >= (X_SOUND_AT - 0.5) * TICK else t, c) for t, c in timeline]
            timeline.append(((X_SOUND_AT + extra - 0.01) * TICK, X_SOUND))
        # the code's order at one tick (0x76 then 0x79 [0x01000ffc]): a hair apart, as MPF's clock may swap equal times
        timeline = [(t + i * 1e-4, c) for i, (t, c) in enumerate(sorted(timeline, key=lambda e: e[0]))]
        sounds = [(t, (lambda c: lambda: os_.sound(c, in_deff=25))(c)) for t, c in timeline]
        subtotal = UNIT * pd.get("bonus_count", 0) + pd.get("bonus_held", HELD)
        kwargs = {"run_seconds": captured.seconds + extra * TICK} if extra and captured and not own else {}

        def site_values(u=x):
            """deff 25's printf texts by call site [0x01000ffc]: the 1X page's constant 1 [0x01001170] over the
            subtotal [0x010011a4], counting page u [0x01001258] over u x subtotal [0x01001290], the multiplier
            [0x01001358] over x x subtotal [0x01001388], the total (player_product_f38) [0x01001484] [0x0100161c]."""
            return {"1001170": 1, "10011a4": subtotal, "1001258": u, "1001290": u * subtotal,
                    "1001358": x, "1001388": x * subtotal, "1001484": total, "100161c": total}
        if own:
            kwargs["variant"] = variant
            started = os_.machine.clock.get_time()

            def live():
                """The counting page on screen: page u (2..x) from tick 71 (0x77 at 47, os_hook_call_203d0(10),
                task_sleep(4)), 8 ticks each, 4 from 6X [0x01000ffc]."""
                ticks = (os_.machine.clock.get_time() - started) / TICK
                u, at = 2, X_SOUND_AT + COUNT_START_TICKS
                while u < x and ticks >= at + (X_PAGE_TICKS if u < X_FAST_FROM else X_PAGE_TICKS_FAST):
                    at += X_PAGE_TICKS if u < X_FAST_FROM else X_PAGE_TICKS_FAST
                    u += 1
                return {"site_values": site_values(u)}
            os_.deff_live([25], live)
        else:
            os_.deff_values.pop(25, None)
        os_.deff_start(25, sounds=sounds, total=total, site_values=site_values(), **kwargs)
        os_.after(BONUS_TICKS + extra, lambda: done(total))

def feature(os_):
    return Bonus(os_)
