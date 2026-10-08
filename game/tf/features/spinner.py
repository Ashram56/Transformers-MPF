"""Right orbit spinner (rom/rules/modes/scoring_features.md 4.2; code [0x01033a08 -> 0x01032294 -> 0x010320a4]
+ observed: 5 spins -> 5 x (2,500 + 90), traces/scoring.jsonl t 33.71).

- spin_value (0x21120dc + 4(p-1)): 2,500 at ball start (event 0x11 hook 0x01032484) unless game flag 0x1c.
  NOTE: flag 0x1c is also set by the valid playfield (event 0x6a) in this OS model, so the reset is applied
  at every ball start here (what sets the spinner's keep flag was not found).
- Each spin (the handler adds 90, tf/switches.py) is queued like the pops (task 0x49, one per tick, 93-tick
  idle end): spin_value, leff 152, sound 0x26d stepping through its samples.
- Super spinner (left-eject award "SUPER SPINNER LIT") [0x010325bc]: value 50,000 + 10,000 x times lit before
  (cap 100,000), spins 50 + 5 x times lit (cap 75), flag 0x4c, show task 0x63 with deff 146, counter 0x9c
  (SUPER SPINNER LIT, NVRAM 0x2102cd8, written directly). While lit a spin [0x010320a4] scores the super value, sound
  0x270, leff 155, spins - 1: deff 147 "n HITS REMAINING / burst total" unless it is showing; the last one deff 148
  (its arg the award) and the flag goes. Code only (not traced); flag and count reset at the player's first
  ball [0x010324dc].
"""
from tf.features import Feature

VALUE = 2500
TASK = 0x49
SOUND, LEFF = 0x26d, 152
SUPER_TASK, SUPER_LIT_DEFF, SUPER_DEFF, SUPER_DONE_DEFF = 0x63, 146, 147, 148
SUPER_SOUND, SUPER_LEFF, SUPER_AUDIT = 0x270, 155, 0x9c


class Spinner(Feature):
    name = "spinner"
    HOOKS = ("player_first_ball", "ball_start", "sw_34", "ball_end")

    def __init__(self, os_):
        super().__init__(os_)
        self.queue = 0
        self.sample = 0
        self.super_total = 0
        os_.deff_live((SUPER_DEFF,), lambda: {"values": [self.pd.get("super_spin_left", 0), self.super_total]})

    def player_first_ball(self):
        self.pd.super_spin_count = 0
        self.pd.super_spinner = False

    def ball_start(self):
        self.pd.spin_value = VALUE

    def sw_34(self):
        if self.os.tilted:
            return
        self.queue += 1
        if not self.os.task_running(TASK):
            self._pay()
        elif self.queue == 1:
            self._pay()

    def _pay(self):
        os_ = self.os
        if not self.queue or not os_.game or os_.tilted:
            self.queue = 0
            return
        self.queue -= 1
        if self.pd.get("super_spinner"):
            self._super_spin()
            os_.task_start(TASK, 1 if self.queue else 93, self._pay)
            return
        os_.score_add(self.pd.get("spin_value", VALUE))
        os_.leff_start(LEFF)
        count = len(os_.sample_lengths(SOUND) or ())
        os_.sound(SOUND, index=self.sample if count else None)
        self.sample = (self.sample + 1) % count if count else 0
        os_.task_start(TASK, 1 if self.queue else 93, self._pay)

    def light_super(self):
        """[0x010325bc] SUPER SPINNER LIT (the left eject's award)."""
        os_ = self.os
        pd = self.pd
        n = pd.get("super_spin_count", 0)
        pd.super_spin_value = min(50000 + 10000 * n, 100000)
        pd.super_spin_left = min(50 + 5 * n, 75)
        pd.super_spinner = True
        os_.show(SUPER_TASK, SUPER_LIT_DEFF)
        pd.super_spin_count = n + 1
        os_.audits.add(SUPER_AUDIT)             # written to NVRAM directly, not through audit_add
        os_.request_refresh()

    def _super_spin(self):
        os_ = self.os
        pd = self.pd
        points = pd.get("super_spin_value", 50000)
        os_.score_add(points)
        if not os_.display.running(SUPER_DEFF):
            self.super_total = 0
        self.super_total += points
        pd.super_spin_left = max(pd.get("super_spin_left", 1) - 1, 0)
        if pd.super_spin_left == 0:
            os_.deff_start(SUPER_DONE_DEFF, values=[points])
            pd.super_spinner = False
            os_.request_refresh()
        elif not os_.display.running(SUPER_DEFF):
            os_.deff_start(SUPER_DEFF)
        os_.leff_start(SUPER_LEFF)
        os_.sound(SUPER_SOUND)

    def ball_end(self):
        self.queue = 0
        self.os.task_kill(TASK)


def feature(os_):
    return Spinner(os_)
