"""Bumblebee target letters and double scoring (rom/rules/modes/scoring_features.md 4.3; code [0x01033adc ->
0x01001a70] [0x010039a0] [0x010038dc] + observed in traces/scoring.jsonl t 49.87-105.91).

- bb_letters (0x2111cf4 + (p-1)): at the player's first ball 2 / 1 / 0 by adj 70 BUMBLEBEE LETTER
  DIFFICULTY (EASY / MEDIUM / HARD); bb_completions starts at the adj 70 value [0x01001880].
- Switch 1 with L < 9 letters: 10,000 + 5,000 x L [table 0x040c5c18], L + 1, deff 128, sound 0x26b,
  leff 150 (the handler's 30 follows, tf/switches.py).
- The 9th letter starts double scoring; completions + 1; the letters restart at 1 after the first word, at 0
  after that [0x010017fc].
- Double scoring [0x010039a0]: playfield multiplier 2, deff 129 ("FOR n SECONDS"), leff 156, audit 105;
  background deff 130 ("n / ALL SCORES X 2") with music 0x026 and leff 157 while it runs. Every scoring switch
  plays 0x27c + 0x27d [0x01003a64]. Countdown [0x010038dc]: adj 80 counts of 66 ticks (observed 1.07 s),
  holding while the playfield is not valid; sound 0x285 at 10, 0x284 .. 0x280 at 5 .. 1; one count after 0
  the end sound 0x286, the multiplier back to 1 124 ticks later (observed 103.89 / 105.91 s; the tail's
  split is inferred). ADD MORE TIME adds adj 80 counts (cap 90) [0x01003a8c].
- Inferred: the end of ball and the tilt stop it (the OS resets the multiplier there).
"""
from tf.features import Feature

LETTERS = 9
START_LETTERS = {0: 2, 1: 1, 2: 0}
LETTER_DEFF, LETTER_SOUND, LETTER_LEFF = 128, 0x26b, 150
DS_DEFF, DS_BG_DEFF, DS_SOUND, DS_LEFF, DS_BG_LEFF, DS_MUSIC, DS_AUDIT = 129, 130, 0x27a, 156, 157, 0x026, 105
# deff 129's sounds (observed, scoring.jsonl 51.98-55.41 s): 0x27a, then the 0x27b ticks, the later ones
# logged outside the deff (OS caller 0x255b8)
DS_DEFF_SOUNDS = ((0.0, 0x27a, DS_DEFF), (0.33, 0x27b, DS_DEFF), (1.43, 0x27b, 0), (2.41, 0x27b, 0),
                  (3.43, 0x27b, 0))
SWITCH_SOUNDS = (0x27c, 0x27d)
COUNT_TICKS = 66
END_TICKS = 124
TASK = "double_scoring"
COUNT_SOUNDS = {10: 0x285, 5: 0x284, 4: 0x283, 3: 0x282, 2: 0x281, 1: 0x280}
END_SOUND = 0x286
MAX_COUNT = 90


class Bumblebee(Feature):
    name = "bumblebee"
    HOOKS = ("player_first_ball", "sw_1", "switch", "ball_end", "tilt", "scoring_boost")

    def __init__(self, os_):
        super().__init__(os_)
        self.running = False                     # double scoring counts down
        self.count = 0
        os_.deff_rule(lambda: self.running, DS_BG_DEFF, music=DS_MUSIC, priority=0x80)
        os_.lamp_rule(lambda: self.running, leff=DS_BG_LEFF, order=0x010039a0)
        os_.deff_live((DS_BG_DEFF, DS_DEFF), lambda: {"values": [self.count]})

    def player_first_ball(self):
        level = self.os.adj[70]
        self.pd.bb_letters = START_LETTERS.get(level, 2)
        self.pd.bb_completions = level

    def sw_1(self):
        os_ = self.os
        if os_.tilted:
            return
        pd = self.pd
        letters = pd.get("bb_letters", 0)
        if letters >= LETTERS:
            return
        os_.score_add(10000 + 5000 * letters)
        pd.bb_letters = letters + 1
        if pd.bb_letters < LETTERS:                  # the 9th letter shows deff 129 instead (observed)
            os_.deff_start(LETTER_DEFF)
            os_.leff_start(LETTER_LEFF)               # deff 128's code starts its leff and sound
            os_.sound(LETTER_SOUND, in_deff=LETTER_DEFF)
        else:
            pd.bb_completions = pd.get("bb_completions", 0) + 1
            pd.bb_letters = 1 if pd.bb_completions == 1 else 0
            self.start()

    def start(self, count=None):
        os_ = self.os
        os_.task_kill(TASK)
        self.started_at = os_.now                    # the starting hit plays no doubled-switch sounds
        self.running = True
        self.count = count or os_.adj[80]
        os_.pf_mult = 2
        os_.deff_start(DS_DEFF, values=[self.count], sounds=[
            (t, (lambda d: lambda: os_.sound(c, in_deff=d))(d)) for t, c, d in DS_DEFF_SOUNDS])
        os_.leff_start(DS_LEFF)
        os_.audit(DS_AUDIT)
        os_.request_refresh()
        os_.task_start(TASK, COUNT_TICKS, self._tick)

    def add_time(self):
        """ADD MORE TIME [0x01003a8c]."""
        if self.running:
            self.count = min(self.count + self.os.adj[80], MAX_COUNT)

    def _tick(self):
        os_ = self.os
        if not self.running:
            return
        if not os_.pf_valid:
            os_.task_start(TASK, COUNT_TICKS, self._tick)
            return
        if self.count == 0:
            os_.sound(END_SOUND)
            os_.task_start(TASK, END_TICKS, self.stop)
            return
        self.count -= 1
        if self.count in COUNT_SOUNDS:
            os_.sound(COUNT_SOUNDS[self.count])
        os_.task_start(TASK, COUNT_TICKS, self._tick)

    def stop(self):
        os_ = self.os
        os_.task_kill(TASK)
        if self.running:
            self.running = False
            os_.pf_mult = 1
            os_.request_refresh()

    def switch(self, num):
        if self.running and not self.os.tilted and getattr(self, "started_at", None) != self.os.now:
            for call in SWITCH_SOUNDS:
                self.os.sound(call)

    def scoring_boost(self):
        return self.running or None

    ball_end = stop
    tilt = stop


def feature(os_):
    return Bumblebee(os_)
