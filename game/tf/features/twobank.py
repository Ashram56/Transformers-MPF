"""Right 2-bank targets and fast scoring (rom/rules/modes/scoring_features.md 4.4; code [0x0102e9c0]
[0x01004394] [0x010047b8] [0x01004220] + observed in traces/scoring.jsonl t 104.88-161.46).

- Switches 50 (top) and 37 (bottom), handler 30 points + audit 70 (tf/switches.py BASE_SCORE / here).
- During a multiball or a timed mode ([0x0102e994]: [0x01006704] multiball flags, [0x010067bc] battle timers,
  double and fast scoring): 5,000, sound 0x261, leff 143.
- Else twobank_left > 0: - 1, 75,000, sound 0x263, leff 144, deff 126 "n MORE FOR FAST SCORING"; reaching 0
  shows deff 131 "FAST SCORING READY" instead and leffs 147 / 148 run while it is ready.
- twobank_left = 0: fast scoring starts [0x01004394]: 100,000, starts + 1, twobank_left = 5 + 2 x starts (cap
  12; observed 7 at the first ball, 9 after the first start), audit 106.
- Fast scoring: fast_value = 10,000 + 5,000 x starts before (cap 50,000); deff 132 0.9 s later (sound 0x289,
  leff 158), background deff 133 "ALL TARGETS = n" with music 0x027, leffs 159 / 160. The countdown, adj 81
  counts of 66 ticks, holds while a show or deff 132 is up (observed: first count 5.1 s after the start).
  Every playfield switch scores fast_value (one award per tick, task 0x5b); unless deff 132 is up or about to
  show (task 0x70): sound 0x28d, leff 164, a 200 ms shake (MAXIMAL), and deff 134 when it is not up and no
  multiball runs [0x01004644]. Switches 50 / 37: the first hit of each this cycle adds
  1,000 to fast_value (cap 50,000, deff 135); both hit: +10 counts (cap 90), deff 136, cycle reset.
  One count after 0 the switches keep scoring 250 ticks, then deff 137 "FAST SCORING TOTAL" (sound 0x290, leff 165); also
  at the end of a ball while it runs. ADD MORE TIME adds adj 81 counts (cap 90).
"""
from tf.features import Feature

ORDER = 40
SWITCHES = {50: 2, 37: 4}           # switch -> fast_groups bit
HIT_TICKS = 10                       # task 0xb1: one hit per 10 ticks
LOCKED = (5000, 0x261, 143)
HIT = (75000, 0x263, 144)
LEFT_DEFF, READY_DEFF = 126, 131
READY_LEFFS = (148, 147)
START_POINTS, START_AUDIT = 100000, 106
FIRST_LEFT = 7
COUNT_TICKS, TAIL_TICKS, SHOW_TICKS = 66, 250, 55
FS_DEFF, FS_BG_DEFF, FS_AWARD_DEFF, FS_VALUE_DEFF, FS_TIME_DEFF, FS_TOTAL_DEFF = 132, 133, 134, 135, 136, 137
FS_LEFF, FS_RULE_LEFFS, FS_AWARD_LEFF, FS_TOTAL_LEFF = 158, (160, 159), 164, 165
FS_MUSIC, FS_AWARD_SOUND, FS_TOTAL_SOUND = 0x027, 0x28d, 0x290
TASK, AWARD_TASK = "fast_scoring", 0x5b
AWARD_SHAKER = (1, 3)                # 200 ms, adj 96 MAXIMAL [0x01004644] (rom_data/io/shaker.csv)


class TwoBank(Feature):
    name = "twobank"
    HOOKS = ("player_first_ball", "sw_50", "sw_37", "switch", "ball_end", "tilt", "scoring_boost", "timed_mode", "add_time")

    def __init__(self, os_):
        super().__init__(os_)
        self.running = False            # fast scoring (countdown or its 250-tick tail)
        self.counting = False
        self.intro_pending = False      # task 0x70: the start show not on yet
        self.value = self.count = self.total = 0
        self.groups = 0
        self.awards = 0
        self.last_hit = -1.0
        for leff in READY_LEFFS:
            os_.lamp_rule(lambda: self.ready() and not self.running, leff=leff, order=0x0102e9c0)
        os_.deff_rule(lambda: self.running, FS_BG_DEFF, music=FS_MUSIC, priority=0x80)
        for leff in FS_RULE_LEFFS:
            os_.lamp_rule(lambda: self.running, leff=leff, order=0x01004394)
        os_.deff_live((FS_DEFF, FS_AWARD_DEFF, FS_VALUE_DEFF), lambda: {"values": [self.value]})
        # deff 133: the countdown on both sides ("%u" at x 42 and 127), then "ALL TARGETS=%,02lu"
        os_.deff_live((FS_BG_DEFF,), lambda: {"values": [self.count, self.count, self.value]})
        os_.deff_live((FS_TOTAL_DEFF,), lambda: {"values": [self.total]})

    def ready(self):
        return bool(self.os.game) and self.pd.get("twobank_left", FIRST_LEFT) == 0

    def player_first_ball(self):
        self.pd.twobank_left = FIRST_LEFT
        self.pd.fs_starts = 0

    def sw_50(self):
        self._target(50)

    def sw_37(self):
        self._target(37)

    def _target(self, num):
        os_ = self.os
        if os_.tilted:
            return
        if self.running:
            self._fast_target(num)
        if os_.any_multiball() or os_.timed_mode_running() or self.running:     # [0x0102e994]
            points, sound, leff = LOCKED
            os_.score_add(points)
            os_.sound(sound)
            os_.leff_start(leff)
            return
        if os_.now - self.last_hit < HIT_TICKS * 0.01626:
            return
        self.last_hit = os_.now
        pd = self.pd
        left = pd.get("twobank_left", FIRST_LEFT)
        if left == 0:
            self.start()
            return
        pd.twobank_left = left - 1
        points, sound, leff = HIT
        os_.deff_start(READY_DEFF if pd.twobank_left == 0 else LEFT_DEFF, values=[pd.twobank_left])
        os_.leff_start(leff)
        os_.sound(sound)
        os_.score_add(points)
        if pd.twobank_left == 0:
            os_.request_refresh()

    # ------------------------------------------------------------------ fast scoring

    def start(self):
        os_ = self.os
        pd = self.pd
        os_.score_add(START_POINTS)
        self.value = min(10000 + 5000 * pd.get("fs_starts", 0), 50000)
        pd.fs_starts = pd.get("fs_starts", 0) + 1
        pd.twobank_left = min(5 + 2 * (pd.fs_starts + 1), 12)
        os_.audit(START_AUDIT)
        self.running = self.counting = True
        self.count = os_.adj[81]
        self.groups = 0
        self.total = START_POINTS
        self.started_now = True                 # the starting hit scores no all-targets award (observed)
        os_.request_refresh()
        self.intro_pending = True               # task 0x70 until deff 132 shows
        os_.after(SHOW_TICKS, self._show)
        os_.task_start(TASK, COUNT_TICKS, self._tick)

    def _show(self):
        self.intro_pending = False
        if self.running:
            self.os.deff_start(FS_DEFF, values=[self.value])    # sound 0x289 and leff 158 come with it

    def _tick(self):
        os_ = self.os
        if not self.running:
            return
        if os_.timed_mode_paused() or os_.display.running(FS_DEFF):
            os_.task_start(TASK, COUNT_TICKS, self._tick)
            return
        if self.count > 0:                      # one more count after 0 (observed 0 at 148.22 s, total 153.46 s)
            self.count -= 1
            os_.task_start(TASK, COUNT_TICKS, self._tick)
            return
        self.counting = False
        os_.task_start(TASK, TAIL_TICKS, self._end)

    def _end(self):
        os_ = self.os
        self.stop()
        os_.deff_start(FS_TOTAL_DEFF, values=[self.total])
        os_.sound(FS_TOTAL_SOUND, in_deff=FS_TOTAL_DEFF)
        os_.leff_start(FS_TOTAL_LEFF)

    def stop(self):
        self.os.task_kill(TASK)
        self.os.task_kill(AWARD_TASK)
        self.awards = 0
        if self.running:
            self.running = self.counting = False
            self.os.request_refresh()

    def add_time(self):
        if self.running:
            self.count = min(self.count + self.os.adj[81], 90)

    def _fast_target(self, num):
        os_ = self.os
        bit = SWITCHES[num]
        if not self.groups & bit:
            self.groups |= bit
            self.value = min(self.value + 1000, 50000)
            os_.deff_start(FS_VALUE_DEFF, values=[self.value])
        if self.groups & 6 == 6:
            self.count = min(self.count + 10, 90)
            self.groups = 0
            os_.deff_start(FS_TIME_DEFF)

    def switch(self, num):
        if getattr(self, "started_now", False):
            self.started_now = False
            return
        if self.running and not self.os.tilted:
            self.awards += 1
            if not self.os.task_running(AWARD_TASK):
                self._award()

    def _award(self):
        os_ = self.os
        if not self.awards or not self.running:
            self.awards = 0
            return
        self.awards -= 1
        os_.score_add(self.value)
        self.total += self.value
        if not os_.display.running(FS_DEFF) and not self.intro_pending:                       # task 0x70
            if not os_.display.running(FS_AWARD_DEFF) and not os_.any_multiball():
                os_.deff_start(FS_AWARD_DEFF, values=[self.value])
            os_.sound(FS_AWARD_SOUND)
            os_.leff_start(FS_AWARD_LEFF)
            os_.shaker_run(*AWARD_SHAKER)       # read from adj 96 directly: MAXIMAL only
        if self.awards:
            os_.task_start(AWARD_TASK, 1, self._award)

    def ball_end(self):
        if self.running:
            self.stop()
            self.os.deff_start(FS_TOTAL_DEFF, values=[self.total])
            self.os.sound(FS_TOTAL_SOUND, in_deff=FS_TOTAL_DEFF)
            self.os.leff_start(FS_TOTAL_LEFF)

    def tilt(self):
        self.stop()

    def scoring_boost(self):
        return self.running or None

    timed_mode = scoring_boost          # a timed mode ([0x010067bc], task 0xac / 0xc3)


def feature(os_):
    return TwoBank(os_)
