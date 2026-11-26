"""Bumblebee target letters and double scoring (rom/rules/modes/scoring_features.md 4.3; code [0x01033adc ->
0x01001a70] [0x010039a0] [0x010038dc], confirmed by traces/scoring.jsonl t 49.87-105.91).

- bb_letters (0x2111cf4 + (p-1)): at the player's first ball 2 / 1 / 0 by adj 70 BUMBLEBEE LETTER
  DIFFICULTY (EASY / MEDIUM / HARD); bb_completions starts at the adj 70 value [0x01001880].
- Switch 1 with L < 9 letters: 10,000 + 5,000 x L [table 0x040c5c18], L + 1, deff 128, sound 0x26b,
  leff 150 (the handler's 30 follows, tf/switches.py).
- The 9th letter starts double scoring; completions + 1; the letters restart at 1 after the first word, at 0
  after that [0x010017fc].
- Double scoring [0x010039a0]: playfield multiplier 2, deff 129 ("FOR n SECONDS"), leff 156, audit 105;
  background deff 130 ("n / ALL SCORES X 2") with music 0x026 and leff 157 while it runs. Every scoring switch
  plays 0x27c + 0x27d [0x01003a64]. Countdown [0x010038dc] (task 0xc3): adj 80 counts of 11 x 6 ticks that never
  pause (the 0x0100683c result is thrown away; QA P6); 0x284 .. 0x280 at 5 .. 1 (table 0x040c5d18), and 0x285
  once per run of the task at the first count in 5 .. 10 (QA P12); one count after 0 the end sound 0x286, then
  the tail task 0xc4 sets the multiplier back to 1 125 ticks later [0x0100396c-0x0100398c]. The tail is not a
  timed mode (any_timed_mode_running [0x010067bc] tests task 0xc3 only; QA P9). ADD MORE TIME adds adj 80 counts
  (cap 90) [0x01003a8c]; in the tail it kills 0xc4 and restarts the countdown (QA P16).
- The end of ball stops it: start_deff_25 [0x00019e44] kills the tasks without flag 0x100 (0xc3 / 0xc4 have
  none) and sets the multiplier back to 1 (ball_number_set_1cce0(1)); the tilt ends the ball the same way.
"""
from tf.features import Feature
from tf.os_layer import TICK

LETTERS = 9
START_LETTERS = {0: 2, 1: 1, 2: 0}
LETTER_DEFF, LETTER_SOUND, LETTER_LEFF = 128, 0x26b, 150
DS_DEFF, DS_BG_DEFF, DS_SOUND, DS_LEFF, DS_BG_LEFF, DS_MUSIC, DS_AUDIT = 129, 130, 0x27a, 156, 157, 0x026, 105
# deff_129_double [0x01003c5c] (QA V129): snd_play(0x27a), then at tick 20 snd_play_arg_25250(0x27b, 0) and its
# samples 1, 2 and 0 each queued after the previous one (snd_play_after_handle_2539c [0x0002539c]; the OS plays
# them, in_deff 0)
DS_TICK_SOUND = 20
DS_TICK_CHAIN = (1, 2, 0)
SWITCH_SOUNDS = (0x27c, 0x27d)
COUNT_TICKS = 66                     # 11 x task_sleep(6)
END_TICKS = 125                      # sleep 0x7d [0x0100396c]
TASK = "double_scoring"
COUNT_SOUNDS = {5: 0x284, 4: 0x283, 3: 0x282, 2: 0x281, 1: 0x280}
WARN_SOUND = 0x285
END_SOUND = 0x286
MAX_COUNT = 90


class Bumblebee(Feature):
    name = "bumblebee"
    HOOKS = ("player_first_ball", "sw_1", "scoring_switch", "ball_end", "tilt", "scoring_boost", "timed_mode", "add_time")

    def __init__(self, os_):
        super().__init__(os_)
        self.running = False                     # double scoring: countdown (task 0xc3) or its tail (0xc4)
        self.counting = False                    # task 0xc3
        self.warned = False                      # 0x285 played in this run of task 0xc3
        self.count = 0
        os_.deff_rule(lambda: self.running, DS_BG_DEFF, music=DS_MUSIC, priority=0x58)   # QA V-ENG5 (os_layer deff_rule)
        os_.lamp_rule(lambda: self.running, leff=DS_BG_LEFF)
        # leff 151 while every BUMBLEBEE letter is lit (more than 8): rule player_count_above_8_18bc [0x010018bc]
        # (0x02111cf4 + (p-1) > 8, registered by [0x010026cc], mask 0x20) (QA L-151)
        os_.lamp_rule(lambda: bool(os_.game) and self.pd.get("bb_letters", 0) > 8, leff=151)
        os_.deff_live((DS_BG_DEFF, DS_DEFF), lambda: {"values": [self.count]})
        # arcade_lamp_rule [0x010024dc] (list 4, mask 0x20, registered by [0x010026cc]): return_one_18b4
        # [0x010018b4] is 1 in 1.80, so lamp 30 BUMBLEBEE (CAPTIVE BALL) flashes all game (QA L-R01, L-I30)
        os_.lamp_update(lambda: os_.lamps.lamp_flash(30))

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
        if pd.bb_letters < LETTERS:                  # the 9th letter shows deff 129 instead [0x01001a70]
            os_.deff_start(LETTER_DEFF)
            # deff 128's code starts its leff and sound [0x01002410, 0x0100241c]: the package's timing.json
            # carries them now; deff_media starts only what it does not
            os_.deff_media(LETTER_DEFF, LETTER_LEFF, LETTER_SOUND)
        else:
            pd.bb_completions = pd.get("bb_completions", 0) + 1
            pd.bb_letters = 1 if pd.bb_completions == 1 else 0
            self.start()

    def start(self, count=None):
        os_ = self.os
        os_.task_kill(TASK)
        self.started_at = os_.now                    # the starting hit plays no doubled-switch sounds
        self.running = self.counting = True
        self.warned = False
        self.count = count or os_.adj[80]
        os_.flag_clear(0x13)                         # ADD MORE TIME offered again [0x010039a0] (QA P5)
        os_.pf_mult = 2
        os_.deff_start(DS_DEFF, values=[self.count], sounds=[
            (0.0, lambda: os_.sound(DS_SOUND, in_deff=DS_DEFF)),
            (DS_TICK_SOUND * TICK, lambda: self._tick_sounds(os_.sound(0x27b, in_deff=DS_DEFF, index=0)))])
        os_.leff_start(DS_LEFF)
        os_.audit(DS_AUDIT)
        os_.request_refresh()
        os_.task_start(TASK, COUNT_TICKS, self._tick)

    def _tick_sounds(self, end, chain=DS_TICK_CHAIN):
        """The 0x27b samples queued one after the other [0x0002539c]."""
        if end is None or not chain:
            return
        os_ = self.os
        os_.machine.clock.schedule_once(
            lambda _dt=None: self._tick_sounds(os_.sound(0x27b, index=chain[0]), chain[1:]), max(0.0, end - os_.now))

    def add_time(self):
        """ADD MORE TIME [0x01003a8c]: counts added; in the tail the countdown restarts (multiplier 2)."""
        if self.running:
            self.count = min(self.count + self.os.adj[80], MAX_COUNT)
            if not self.counting:
                self.counting, self.warned = True, False
                self.os.pf_mult = 2
                self.os.task_start(TASK, COUNT_TICKS, self._tick)
                self.os.request_refresh()

    def _tick(self):
        os_ = self.os
        if not self.running:
            return
        if self.count == 0:
            os_.sound(END_SOUND)
            self.counting = False                    # task 0xc4: the tail
            os_.request_refresh()
            os_.task_start(TASK, END_TICKS, self.stop)
            return
        self.count -= 1
        if self.count in COUNT_SOUNDS:
            os_.sound(COUNT_SOUNDS[self.count])
        if not self.warned and 5 <= self.count <= 10:
            self.warned = True
            os_.sound(WARN_SOUND)
        os_.task_start(TASK, COUNT_TICKS, self._tick)

    def stop(self):
        os_ = self.os
        os_.task_kill(TASK)
        if self.running:
            self.running = self.counting = False
            os_.pf_mult = 1
            os_.request_refresh()

    def scoring_switch(self, num):
        if self.running and not self.os.tilted and getattr(self, "started_at", None) != self.os.now:
            for call in SWITCH_SOUNDS:
                self.os.sound(call)

    def scoring_boost(self):
        """Task 0xc3 runs: the countdown, not its tail ([0x010038b0], QA P9)."""
        return (self.running and self.counting) or None

    timed_mode = scoring_boost          # a timed mode ([0x010067bc], task 0xac / 0xc3)

    ball_end = stop
    tilt = stop


def feature(os_):
    return Bumblebee(os_)
