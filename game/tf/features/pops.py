"""Pop bumpers: the growing pop value (rom/rules/modes/scoring_features.md 4.1; code + observed in
traces/scoring.jsonl).

- pop_base (0x2112054 + 4(p-1)): 3,000 at ball start (event 0x11 hook 0x0102d1ec) unless game flag 0x40.
- Each pop hit (handler 0x01032f8c, tf/switches.py: +170, audit 73) queues one award; task 0x51 pays one
  queued award per tick [0x0102ca98] and ends 93 ticks after the last one, setting pop_value back to
  pop_base [0x0102ca30] (observed: back to 3,000 1.53 s after the last hit).
- An award [0x0102c8c8]: score pop_value, then pop_value + 1,000 up to 20,000; sound 0x15b Autobot / 0x15c
  Decepticon (0x15d during double or fast scoring); deff 46 (the burst total pop_total, 0x353d4) unless it is
  showing; leff 26 + leff 27 / 28 / 29 (top / right / bottom). The step and deff 46 are skipped during a multiball
  or with flag 0x3c ([0x0102c878] -> [0x01006704], the multiball flags, which the decompile names
  any_timed_mode_running); during a battle both happen (observed: traces/battle_devastator 43.86 / 45.04 s:
  3,000 then 4,000, deff 46 each time).
- POPS GROW (left-eject award "POPS SCORE", deff 47): grow().
- Super pop bumpers (left-eject award "SUPER POP BUMPERS LIT") [0x0102d31c]: value 50,000 + 10,000 x times lit
  before (cap 100,000), hits 50 + 5 x times lit (cap 75), flag 0x4d, show task 0x64 with deff 149, audit 0x9d.
  While lit an award [0x0102c8c8] scores the super value instead (no step), sound 0x163, leff 33, hits - 1:
  deff 150 "n HITS REMAINING / burst total" unless it is showing; the last hit deff 151 (its arg the award) and
  the flag goes. Code only (not traced); the count resets at the player's first ball [0x0102d244].
"""
from tf.features import Feature

BASE, STEP, CAP = 3000, 1000, 20000
IDLE_TICKS = 93
TASK = 0x51
SOUND = {1: 0x15b, 2: 0x15c}
FAST_SOUND = 0x15d
DEFF = 46
LEFF = 26
OWN_LEFF = {30: 27, 31: 28, 32: 29}
KEEP_BASE = 0x40
SUPER_TASK, SUPER_LIT_DEFF, SUPER_DEFF, SUPER_DONE_DEFF = 0x64, 149, 150, 151
SUPER_SOUND, SUPER_LEFF, SUPER_AUDIT = 0x163, 33, 0x9d


class Pops(Feature):
    name = "pops"
    HOOKS = ("player_first_ball", "ball_start", "pop", "ball_end", "tilt")

    def __init__(self, os_):
        super().__init__(os_)
        self.queue = []
        self.total = 0
        self.super_total = 0
        os_.deff_live((DEFF,), lambda: {"values": [self.total]})
        os_.deff_live((SUPER_DEFF,), lambda: {"values": [self.pd.get("super_pop_left", 0), self.super_total]})

    def player_first_ball(self):
        self.pd.super_pop_count = 0

    def ball_start(self):
        pd = self.pd
        if not self.os.flag(KEEP_BASE) or "pop_base" not in pd:
            pd.pop_base = BASE
        pd.pop_value = pd.pop_base

    def pop(self, num):
        self.queue.append(num)
        if not self.os.task_running(TASK):
            self._pay()
        elif len(self.queue) == 1:                   # the task was idling: it pays in the same tick
            self._pay()

    def _pay(self):
        os_ = self.os
        if not self.queue:
            for player in os_.players:              # every player's value back to the base [0x0102ca30]
                if "pop_base" in player:
                    player.pop_value = player.pop_base
            return
        if not os_.game or os_.tilted:
            self.queue = []
            return
        num = self.queue.pop(0)
        pd = self.pd
        if pd.get("super_pops"):
            self._super_award()
            os_.task_start(TASK, 1 if self.queue else IDLE_TICKS, self._pay)
            return
        busy = os_.any_multiball() or os_.flag(0x3c)       # [0x0102c878]
        os_.score_add(pd.pop_value)
        if not os_.display.running(DEFF):
            self.total = 0
        self.total += pd.pop_value
        if not busy:
            pd.pop_value = min(pd.pop_value + STEP, CAP)
        fast = bool(os_.hook("scoring_boost"))       # double or fast scoring runs
        os_.sound(FAST_SOUND if fast else SOUND.get(pd.get("side", 2), SOUND[2]))
        if not busy:
            if os_.display.running(DEFF):
                os_.display.extend(DEFF)             # it shows the burst total until the burst ends (observed)
            else:
                os_.deff_start(DEFF)
        os_.leff_start(LEFF)
        os_.leff_start(OWN_LEFF[num])
        os_.task_start(TASK, 1 if self.queue else IDLE_TICKS, self._pay)

    def grow(self):
        """[0x0102c624] POPS GROW: pop_base + 1,000 (cap 20,000), pop_value = pop_base, score it, audit 0x4a,
        deff 47 with sound 0x15e and leff 30 (the left eject's award)."""
        os_ = self.os
        pd = self.pd
        pd.pop_base = min(pd.get("pop_base", BASE) + STEP, CAP)
        pd.pop_value = pd.pop_base
        os_.score_add(pd.pop_value)
        os_.audit(0x4a)
        os_.deff_start(47, values=[pd.pop_value])       # sound 0x15e and leff 30 come with the deff

    def light_super(self):
        """[0x0102d31c] SUPER POP BUMPERS LIT (the left eject's award)."""
        os_ = self.os
        pd = self.pd
        n = pd.get("super_pop_count", 0)
        pd.super_pop_value = min(50000 + 10000 * n, 100000)
        pd.super_pop_left = min(50 + 5 * n, 75)
        pd.super_pops = True
        os_.show(SUPER_TASK, SUPER_LIT_DEFF)
        pd.super_pop_count = n + 1
        os_.audit(SUPER_AUDIT)
        os_.request_refresh()

    def _super_award(self):
        os_ = self.os
        pd = self.pd
        points = pd.get("super_pop_value", 50000)
        os_.score_add(points)
        if not os_.display.running(SUPER_DEFF):
            self.super_total = 0
        self.super_total += points
        pd.super_pop_left = max(pd.get("super_pop_left", 1) - 1, 0)
        if pd.super_pop_left == 0:
            os_.deff_start(SUPER_DONE_DEFF, values=[points])
            pd.super_pops = False
            os_.request_refresh()
        elif not os_.display.running(SUPER_DEFF):
            os_.deff_start(SUPER_DEFF)
        os_.leff_start(SUPER_LEFF)
        os_.sound(SUPER_SOUND)

    def ball_end(self):
        self.queue = []
        self.os.task_kill(TASK)

    tilt = ball_end


def feature(os_):
    return Pops(os_)
