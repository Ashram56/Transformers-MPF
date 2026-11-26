"""Right 2-bank targets and fast scoring (rom/rules/modes/scoring_features.md 4.4; code [0x0102e9c0]
[0x01004394] [0x010047b8] [0x01004220] + observed in traces/scoring.jsonl t 104.88-161.46).

- Switches 50 (top) and 37 (bottom), handler 30 points + audit 70 (tf/switches.py BASE_SCORE / here).
- During a multiball or a timed mode ([0x0102e994]: [0x01006704] multiball flags, [0x010067bc] battle timers,
  double and fast scoring): 5,000, sound 0x261, leff 143.
- Else twobank_left > 0: - 1, 75,000, sound 0x263, leff 144, deff 126 "n MORE FOR FAST SCORING"; reaching 0
  shows deff 131 "FAST SCORING READY" instead and leffs 147 / 148 run while it is ready.
- twobank_left = 0: fast scoring starts [0x01004394]: 100,000, starts + 1, twobank_left = 5 + 2 x fs_level (cap
  12): fs_level is adj 82 at the player's first ball [0x0102e8f8] and + 1 at each start [0x0102e9c0], audit 106.
- Fast scoring: fast_value = 10,000 + 5,000 x starts before (cap 50,000); deff 132 0.9 s later (sound 0x289,
  leff 158), background deff 133 "ALL TARGETS = n" with music 0x027, leffs 159 / 160. The countdown, adj 81
  counts of 66 ticks, holds while a show or deff 132 is up (observed: first count 5.1 s after the start).
  Every playfield switch scores fast_value (one award per tick, task 0x5b); unless deff 132 is up or about to
  show (task 0x70): sound 0x28d, leff 164, a 200 ms shake (MAXIMAL), and deff 134 when it is not up and no
  multiball runs [0x01004644]. Switches 50 / 37 [0x010047b8]: the first target of a cycle adds 1,000 to
  fast_value only during the countdown (task 0xac; cap 50,000, deff 135 when it changed) [0x01004520] and starts
  leff 144; a target already hit this cycle starts leff 145; the completing hit adds 10 counts (cap 90) with
  deff 136 [0x0100457c] and resets the cycle (QA P8). Each count is 11 steps of 6 ticks; a step that finds the
  timers held (0x0100683c: pops and top lanes start the 156-tick hold task 0x59) restarts the count [0x01004220]
  (QA P7). The 250-tick tail (task 0xae) is not a timed mode (any_timed_mode_running [0x010067bc] tests task
  0xac only: the 2-bank scores 75,000 and counts down again); 0x0100457c in the tail kills 0xae and restarts the
  countdown (QA P9), for the completing hit and ADD MORE TIME alike (deff 136 both times, QA P16).
  One count after 0 the switches keep scoring 250 ticks, then the total task 0x88 [0x01004950] (a ball-end-wait
  task) shows deff 137 "FAST SCORING TOTAL" (2.65 s, sound 0x290 and leff 165 from its code) when the display is
  free. Task 0xad, started with the mode, is still running after that (observed: scoring.jsonl, task 0x88 again at
  the drain, 155.11 s), so the end of that ball [0x010049a8] shows the total once more, after the first one, and the
  bonus waits for it (deff 137 at 153.46 and 156.10 s, bonus 158.76 s). What else task 0xad keeps running after the
  total (the awards [0x010047b8] test the same tasks) is not traced: here only the ball-end total. ADD MORE TIME adds adj 81 counts (cap 90).
"""
from tf.features import Feature

ORDER = 40
TWO_BANK_LAMPS = (21, 20)            # table 0x040c7568 +5: sw 50 -> lamp 21, sw 37 -> lamp 20
SWITCHES = {50: 2, 37: 4}           # switch -> fast_groups bit
HIT_TICKS = 10                       # task 0xb1: one hit per 10 ticks
LOCKED = (5000, 0x261, 143)
HIT = (75000, 0x263, 144)
LEFT_DEFF, READY_DEFF = 126, 131
# deff 126 frame 15 (tick 75) [0x0102eaec]: speech_once(0x265, flag 0x30) [0x01006ae0], else 0x264
LEFT_SOUND_TICKS, LEFT_SPEECH, LEFT_FLAG, LEFT_SOUND = 75, 0x265, 0x30, 0x264
READY_LEFFS = (148, 147)
START_POINTS, START_AUDIT = 100000, 106
FIRST_LEVEL = 1                      # adj 82 factory EASY: twobank_left 7 before the first ball sets it
FIRST_LEFT = 5 + 2 * FIRST_LEVEL
COUNT_TICKS, TAIL_TICKS, SHOW_TICKS = 66, 250, 55
STEP_TICKS, STEPS = 6, 11            # a count: 11 x task_sleep(6) [0x01004220]
NEW_LEFF, REPEAT_LEFF = 0x90, 0x91   # 144 a new target this cycle, 145 a repeat [0x010047b8]
FS_DEFF_S, TICK_S = 3.97, 0.016     # deff 132's length (the capture), one tick
FS_DEFF, FS_BG_DEFF, FS_AWARD_DEFF, FS_VALUE_DEFF, FS_TIME_DEFF, FS_TOTAL_DEFF = 132, 133, 134, 135, 136, 137
FS_LEFF, FS_RULE_LEFFS, FS_AWARD_LEFF, FS_TOTAL_LEFF = 158, (160, 159), 164, 165
FS_MUSIC, FS_AWARD_SOUND, FS_TOTAL_SOUND = 0x027, 0x28d, 0x290
TASK, AWARD_TASK, TOTAL_TASK = "fast_scoring", 0x5b, 0x88
TOTAL_SECONDS = 2.65                 # deff 137 (no capture; scoring.jsonl 153.46 -> 156.10 -> 158.76 s)
AWARD_SHAKER = (1, 3)                # 200 ms, adj 96 MAXIMAL [0x01004644] (rom_data/io/shaker.csv)


class TwoBank(Feature):
    name = "twobank"
    HOOKS = ("player_first_ball", "sw_50", "sw_37", "scoring_switch", "ball_end", "ball_end_wait", "tilt", "scoring_boost",
             "timed_mode", "add_time")

    def __init__(self, os_):
        super().__init__(os_)
        self.running = False            # fast scoring (countdown or its 250-tick tail)
        self.counting = False
        self.intro_pending = False      # task 0x70: the start show not on yet
        self.value = self.count = self.total = 0
        self.groups = 0
        self.awards = 0
        self.last_hit = -1.0
        os_.lamp_update(self.draw)
        self.lingering = False          # task 0xad after the total (see above)
        self.total_at = None            # when deff 137 last started
        self.end_wait = 0.0
        os_.display.set_media(FS_TOTAL_DEFF, TOTAL_SECONDS, (FS_TOTAL_LEFF,), ((0.0, FS_TOTAL_SOUND),))
        for leff in READY_LEFFS:
            os_.lamp_rule(lambda: self.ready() and not self.running, leff=leff)
        os_.deff_rule(lambda: self.running, FS_BG_DEFF, music=FS_MUSIC, priority=0x57)   # QA V-ENG5 (os_layer deff_rule)
        for leff in FS_RULE_LEFFS:
            os_.lamp_rule(lambda: self.running, leff=leff)
        os_.display.own_sounds.add((LEFT_DEFF, LEFT_SOUND))
        self._left_token = 0
        os_.deff_live((FS_DEFF, FS_VALUE_DEFF), lambda: {"values": [self.value]})
        # deffs 133 / 134 / 136: the countdown on both sides (RAM 0x34c3c) ("%u" at x 42 and 127), then "ALL TARGETS=%,02lu"
        os_.deff_live((FS_BG_DEFF, FS_AWARD_DEFF, FS_TIME_DEFF),
                      lambda: {"values": [self.count, self.count, self.value]})
        os_.deff_live((FS_TOTAL_DEFF,), lambda: {"values": [self.total]})

    def ready(self):
        return bool(self.os.game) and self.pd.get("twobank_left", FIRST_LEFT) == 0

    def _left_sound(self, token):
        """Deff 126 frame 15 [0x0102eaec]: speech_once(0x265, 0x30) [0x01006ae0], else 0x264."""
        os_ = self.os
        if token != self._left_token or not os_.display.running(LEFT_DEFF):
            return
        if not os_.speech_once(LEFT_SPEECH, LEFT_FLAG, in_deff=LEFT_DEFF):
            os_.sound(LEFT_SOUND, in_deff=LEFT_DEFF)

    def player_first_ball(self):
        """Event 0x26 hook [0x0102e8f8]: fs_level (0x2112090) = adj 82 MUDFLAP/SKIDS TARGET DIFFICULTY, then
        twobank_left = min(5 + 2 x fs_level, 12) [0x0102e88c] (factory 1: 7)."""
        self.pd.fs_level = self.os.adj_value(82)
        self.pd.twobank_left = min(5 + 2 * self.pd.fs_level, 12)
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
        if os_.any_multiball() or os_.timed_mode_running():     # [0x0102e994] (the countdown, not its tail)
            points, sound, leff = LOCKED
            os_.score_add(points)
            os_.sound(sound)
            os_.leff_start(leff)
            return
        if os_.now - self.last_hit < HIT_TICKS * 0.016:
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
        if pd.twobank_left:
            self._left_token += 1
            token = self._left_token
            os_.after(LEFT_SOUND_TICKS, lambda: self._left_sound(token))
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
        os_.flag_clear(0x13)                         # ADD MORE TIME offered again [0x01004394] (QA P5)
        self.value = min(10000 + 5000 * pd.get("fs_starts", 0), 50000)
        pd.fs_starts = pd.get("fs_starts", 0) + 1
        pd.fs_level = min(pd.get("fs_level", FIRST_LEVEL) + 1, 255)      # [0x0102e9c0]
        pd.twobank_left = min(5 + 2 * pd.fs_level, 12)
        os_.audit(START_AUDIT)
        self.running = self.counting = True
        self.steps = 0
        self.lingering = False
        self.count = os_.adj[81]
        self.groups = 0
        self.total = START_POINTS
        self.started_now = True                 # the starting hit scores no all-targets award (observed)
        os_.request_refresh()
        self.intro_pending = True               # task 0x70 until deff 132 shows
        os_.ball_search_reload()                # FUN_01006350 reloads the search at call, show start and show end
        os_.after(SHOW_TICKS, self._show)
        os_.task_start(TASK, STEP_TICKS, self._tick)

    def _show(self):
        self.intro_pending = False
        if self.running:
            self.os.deff_start(FS_DEFF, values=[self.value])    # sound 0x289 and leff 158 come with it
            self.os.ball_search_reload()
            self.os.after(int(FS_DEFF_S / TICK_S), self.os.ball_search_reload)

    def _tick(self):
        os_ = self.os
        if not self.running:
            return
        if os_.timed_mode_paused() or os_.display.running(FS_DEFF):
            self.steps = 0                      # [0x01004220]: a held step restarts the count
        else:
            self.steps += 1
        if self.steps < STEPS:
            os_.task_start(TASK, STEP_TICKS, self._tick)
            return
        self.steps = 0
        if self.count > 0:                      # one more count after 0 (observed 0 at 148.22 s, total 153.46 s)
            self.count -= 1
            os_.task_start(TASK, STEP_TICKS, self._tick)
            return
        self.counting = False                   # task 0xae: the tail
        os_.request_refresh()
        os_.task_start(TASK, TAIL_TICKS, self._end)

    def _end(self):
        self.stop()
        self.lingering = True
        self._show_total()

    def _show_total(self):
        """Task 0x88 [0x01004950]: deff 137 with the total once the display is free."""
        if self.total and not self.os.state & 0x310:
            self.os.display.when_idle(TOTAL_TASK, FS_TOTAL_DEFF, values=[self.total],
                                      on_start=lambda: setattr(self, "total_at", self.os.now))

    def stop(self):
        self.os.task_kill(TASK)
        self.os.task_kill(AWARD_TASK)
        self.awards = 0
        if self.running:
            self.running = self.counting = False
            self.os.request_refresh()

    def add_time(self):
        """ADD MORE TIME: FUN_0100457c(0), adj 81 counts."""
        self._add_counts(self.os.adj[81])

    def _add_counts(self, n):
        """[0x0100457c]: while task 0xac or its tail 0xae runs, n counts (cap 90), the tail killed and the
        countdown (re)started, deff 136."""
        os_ = self.os
        if not self.running:
            return
        self.count = min(self.count + n, 90)
        if not self.counting:
            self.counting = True
            self.steps = 0
            os_.task_start(TASK, STEP_TICKS, self._tick)
            os_.request_refresh()
        os_.deff_start(FS_TIME_DEFF)

    def _fast_target(self, num):
        os_ = self.os
        bit = SWITCHES[num]
        if self.groups & bit:
            os_.leff_start(REPEAT_LEFF)
            return
        self.groups |= bit
        if self.groups & 6 == 6:                # the completing hit [0x010047b8]
            self.groups = 0
            self._add_counts(10)
            return
        if self.counting and self.value < 50000:          # [0x01004520]: task 0xac only
            self.value = min(self.value + 1000, 50000)
            os_.deff_start(FS_VALUE_DEFF, values=[self.value])
        os_.leff_start(NEW_LEFF)

    def scoring_switch(self, num):
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
        """[0x010049a8]: while the mode's tasks run, they stop and the total shows (again)."""
        self.end_wait = 0.0
        if self.running or self.lingering:
            self.stop()
            self.lingering = False
            if not self.os.tilted and self.total:
                # the ball end clears the display, but the ROM's deff 137 plays out first (scoring.jsonl 153.46 -> 156.10)
                showing = self.total_at is not None and self.os.now < self.total_at + TOTAL_SECONDS
                left = max(0.0, self.total_at + TOTAL_SECONDS - self.os.now) if showing else 0.0
                self.end_wait = left + TOTAL_SECONDS
                if left:
                    from tf.os_layer import TICK
                    self.os.after(round(left / TICK), self._show_total)
                else:
                    self._show_total()

    def ball_end_wait(self):
        from tf.os_layer import TICK
        return round(self.end_wait / TICK) if self.end_wait else None

    def tilt(self):
        self.stop()
        self.lingering = False

    def scoring_boost(self):
        """Task 0xac runs: the countdown, not its tail ([0x01004618], QA P9)."""
        return (self.running and self.counting) or None

    timed_mode = scoring_boost          # a timed mode ([0x010067bc], task 0xac / 0xc3)


    def draw(self):
        """Lamp layer lamp_layer_2ede0 [0x0102ede0]: outside multiballs and timed modes (0x0102e994) the 2-bank
        lamps 21 (sw 50, bit 1) and 20 (sw 37, bit 2) of table 0x040c7568 flash, solid when their bit of the
        player's mask 0x02112098 is set; else off. Nothing in the code sets that mask (only 0x0102e88c clears it:
        its two literals 0x0006e8f4 / 0x0006ee94 are that reset and this read), so they flash (QA L-R05)."""
        if not self.os.game:
            return
        lamps = self.os.lamps
        on = not self.os.any_multiball() and not self.os.timed_mode_running()
        for lamp in TWO_BANK_LAMPS:
            if on:
                lamps.lamp_flash(lamp)
            else:
                lamps.lamp_off_all(lamp)

def feature(os_):
    return TwoBank(os_)
