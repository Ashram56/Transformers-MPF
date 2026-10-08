"""Right orbit spinner (rom/rules/modes/scoring_features.md 4.2; code [0x01033a08 -> 0x01032294 -> 0x010320a4]
+ observed: 5 spins -> 5 x (2,500 + 90), traces/scoring.jsonl t 33.71).

- spin_value (0x21120dc + 4(p-1)): 2,500 at ball start (event 0x11 hook 0x01032484) unless game flag 0x1c.
  NOTE: flag 0x1c is also set by the valid playfield (event 0x6a) in this OS model, so the reset is applied
  at every ball start here (what sets the spinner's keep flag was not found).
- Each spin (the handler adds 90, tf/switches.py) is queued like the pops (task 0x49, one per tick, 93-tick
  idle end): spin_value, leff 152, sound 0x26d stepping through its samples.
- Super spinner (left-eject award "SUPER SPINNER LIT") comes with the award bag.
"""
from tf.features import Feature

VALUE = 2500
TASK = 0x49
SOUND, LEFF = 0x26d, 152


class Spinner(Feature):
    name = "spinner"
    HOOKS = ("ball_start", "sw_34", "ball_end")

    def __init__(self, os_):
        super().__init__(os_)
        self.queue = 0
        self.sample = 0

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
        os_.score_add(self.pd.get("spin_value", VALUE))
        os_.leff_start(LEFF)
        count = len(os_.sample_lengths(SOUND) or ())
        os_.sound(SOUND, index=self.sample if count else None)
        self.sample = (self.sample + 1) % count if count else 0
        os_.task_start(TASK, 1 if self.queue else 93, self._pay)

    def ball_end(self):
        self.queue = 0
        self.os.task_kill(TASK)


def feature(os_):
    return Spinner(os_)
