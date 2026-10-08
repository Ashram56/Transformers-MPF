"""Character battles and the mode-start shots (rom/rules/modes/battles.md; code [0x01020074] [0x01022e08]
[0x010229ec] [0x01022cf8] and the eight battles' start / hit / end functions; observed in traces/battle_*.jsonl).

Mode start (4.2): five shots (Allspark, left orbit, left ramp, right ramp, right orbit) carry the side's arrows;
adj 66 MODE START DIFFICULTY lights N of them at reset (game start, each battle start) and keeps at least a
minimum lit. A lit one scores min(10,000 + 10,000 x battles started + 5,000 x hits, 75,000) x the shot's
multiplier, deff 91 "N MORE FOR MODE START" with leff 103 (0x170 Decepticon / 0x174 Autobot); the 4th hit
starts the lit battle. Qualifying needs no multiball ([0x01006704], the decompile's any_timed_mode_running), no battle running and
no flag 0x3c (clu_start_allowed [0x01022ca8]).

The lit battle (battle_lit, one bit per record of table 0x040c6e08) moves to the next one of the side's ring of
four on every pop bumper and Bumblebee target hit while qualifying is allowed; the next one is the first not
started, else the first started but not completed [0x010229ec]. Leff 104 flashes its insert meanwhile.

A battle start [0x01022e08]: 100,000 (the run total), its timer, the intro show (deff "NAME BATTLE", task
0x68-0x6f), its background deff + music rule and rule leff; battle_started bit, mode-start reset, audits
(started, 0x58 MODES STARTED, wizard item played 0x81 + item), battle_lit = the next battle.
Running: lit shots score the battle's value x the shot multiplier (hit deff with the value, the hit sound),
unlit main shots 25,000; the shot count to finish is kept per player across balls. The timer counts 66-tick
seconds once the intro is over, holding while timers are paused (no valid playfield, a show, a ball held in a
device, pause task 0x59: 156 ticks after the intro and after pop bumpers, top lanes, Bumblebee phase-1 hits);
at 0 one more count, then the run ends (music back), lit shots still score for 125 ticks, then the total deff.
The last shot completes it (completed bit, audits, wizard item completed 0x8c + item): run killed at once, the
hit deff runs its COMPLETED page, then the total. Drain and tilt end every battle (no total on a tilt).

Observed, not in the spec text:
- the shot audits 65 left orbit, 66 right orbit, 67 left ramp, 68 right ramp come first in the shot handlers,
  lit or not, then the battles, then the mode-start rule (traces: audit, battle score, 25,000 / deff 91);
- the completed hit deff runs until the total (Shockwave 8.67 s, Blackout 9.0, Devastator 8.76, Bumblebee 7.99,
  Ironhide 7.02 after the hit); Starscream and Ratchet were not traced, 8.5 s is assumed;
- Starscream's lit pair did not move with the seconds once 5 shots were left (battle_starscream 41-82 s): only
  lit hits move it here (the spec's per-second move depends on switch tokens 0xc / 0xd, not traced);
- deffs without a capture get their length, lamp effects and sounds from the traces (UNCAPTURED).
"""
from tf.features import Feature

ORDER = 40
AUTOBOT, DECEPTICON = 1, 2

# battle shot ids [table 0x040c69f8]
ALLSPARK, LEFT_ORBIT, LEFT_RAMP, CENTER, RIGHT_RAMP, RIGHT_ORBIT, BEE = range(7)
SHOT_SWITCHES = {5: LEFT_ORBIT, 6: LEFT_ORBIT, 10: LEFT_RAMP, 11: CENTER, 51: CENTER, 14: RIGHT_RAMP,
                 12: RIGHT_ORBIT, 1: BEE}
SHOT_AUDIT = {LEFT_ORBIT: 65, RIGHT_ORBIT: 66, LEFT_RAMP: 67, RIGHT_RAMP: 68}
ORANGE = {ALLSPARK: 15, LEFT_ORBIT: 19, LEFT_RAMP: 44, CENTER: 40, RIGHT_RAMP: 34, RIGHT_ORBIT: 39, BEE: 30}
# Left orbit, switch-timeout token 7 (187 units) [0x01033354 sw 5, 0x010332e4 sw 6]: with the token down, sw 5 or
# sw 6 counts the shot and sets it; with it up, sw 5 clears it and sw 6 sets it again, neither counts; sw 12 clears
# it [0x01033530]. Its length is observed between 2.18 s (switches.jsonl: sw 5 and sw 6 again 2.17-2.18 s later,
# not counted) and 2.35 s (combos.jsonl: sw 6 every 2.35-2.37 s, each counted), so about 12 ms per unit (inferred).
ORBIT_TOKEN_S = 2.26
# A left orbit that counts holds the orbit control gate (coil 5) open 91 ticks (1.48-1.52 s), so the ball goes round
# (observed: every counted sw 5 / sw 6 in the traces, 0.02-0.05 s after the switch, e.g. switches.jsonl 24.7 / 29.1 s;
# the ignored repeats leave it shut)
GATE_TICKS = 91
CENTER_LOCK_S = 1.0         # center lane / Optimus: one of them per pass (task 0x54, inferred time)
# sw 12 is ignored while task 0x47 runs (a ball that just came round): after a left orbit pass, the center lane,
# a plunge or the Megatron back door (sw 13) (traces/game_flow.jsonl 30.57 s, 1.0 s after a plunge, and 56.29 s,
# 2.18 s after a plunge, 1.17 s after sw 13; switches.jsonl 58.86 s, 2.18 s after the center lane; counted 4.36 s
# after it: no audit, no mode start, no combo); the 3 s are inferred. Within 187 ticks of the previous right orbit
# shot it is ignored too (timer 9 [0x01033530], combos_and_multipliers.md 4.1).
RIGHT_IGNORE_S = 3.0
RIGHT_REPEAT_S = 187 * 0.01626

# mode-start shots [table 0x040c6d00]: battle shot -> mode-start index (mask bit 1 << index)
MS_SHOT = {ALLSPARK: 0, LEFT_ORBIT: 1, LEFT_RAMP: 2, RIGHT_RAMP: 3, RIGHT_ORBIT: 4}
MS_BATTLE_SHOT = {v: k for k, v in MS_SHOT.items()}
MS_LAMPS = {0: (14, 13), 1: (18, 17), 2: (45, 46), 3: (33, 32), 4: (38, 37)}    # (red Autobot, purple)
MS_DIFFICULTY = {0: (5, 5), 1: (5, 4), 2: (4, 4), 3: (4, 3), 4: (4, 2)}       # adj 66: lit at reset, minimum
MS_WALK = (1, 2, 3, 4, 0)
MS_NEEDED = 4
MS_DEFF, MS_LEFF = 91, 103
MS_SOUND = {AUTOBOT: 0x174, DECEPTICON: 0x170}
LIT_LEFF = 104
SIDE_DONE_FLAG = 0x3d
ADD_TIME_FLAG = 0x13

START_POINTS = 100000
UNLIT_POINTS = 25000
PAUSE_TASK, PAUSE_TICKS = 0x59, 156
STEP_TICKS, STEPS = 6, 11             # one battle second: 11 steps of 6 ticks
INTRO_WAIT_TICKS = 93
GRACE_TICKS = 125
MODES_STARTED_AUDIT = 0x58
WIZARD_PLAYED_AUDIT, WIZARD_DONE_AUDIT = 0x81, 0x8c
ADD_TIME, MAX_TIME = 15, 90
RULE_PRIORITY = 0x40                  # below double / fast scoring (music table entries 7-8 before 9-16)
TOTAL_TICKS = 120                     # a total started at the drain holds the bonus (battle_ratchet: 1.94 s)

# deffs the package has no capture (or no end) of: (seconds, leffs, sounds), from the reference traces
UNCAPTURED = {
    94: (2.2, (107,), ((2.02, 0x18e),)),                    # Starscream hit (0x18e 2.02 s after each hit)
    96: (4.93, (109,), ((0.0, 0x193), (3.70, 0x194))),      # Shockwave intro (deff 97 again 4.93 s later)
    111: (1.92, (126,), ((0.0, 0x1fe),)),                   # Bumblebee total
    118: (4.4, (133,), ()),                                 # Mudflap & Skids hit (length as deff 114)
    119: (1.92, (134,), ((0.0, 0x232),)),                   # Mudflap & Skids total
}


class Battle:
    """One record of the battle table; the subclasses hold the per-battle rules (battles.md 5.1-5.8)."""
    key = ""
    index = 0
    side = DECEPTICON
    timer_adj = None
    timer_task = run_task = intro_task = total_task = 0
    item = 0
    audit_started = audit_completed = 0
    insert = 0
    intro = bg = hit_deff = total_deff = 0
    music = 0
    rule_leff = 0
    hit_sound = 0
    shots = 10
    completed_seconds = 8.5
    multiball = False

    def __init__(self, mgr):
        self.mgr = mgr
        self.os = mgr.os
        self.active = False         # the run task: rule, music, timed mode
        self.scoring = False        # the timer task: lit shots score (also in the 125-tick grace)
        self.hits = 0
        self.total = 0
        self.seconds = 0
        self.steps = 0
        self.waiting_intro = False
        self.lit = 0

    @property
    def bit(self):
        return 1 << self.index

    @property
    def pd(self):
        return self.os.pd

    @property
    def left_key(self):
        return "left_" + self.key

    def done(self):
        """C: completions of this battle by this player this game."""
        return self.pd.get("done_" + self.key, 0)

    def reset(self):
        """The player's game start (and a wizard reset)."""
        self.pd[self.left_key] = self.shots

    # ------------------------------------------------------------------ start

    def start(self):
        os_ = self.os
        self.kill()
        self.hits = 0
        self.total = START_POINTS
        self.steps = 0
        os_.score_add(START_POINTS)
        os_.flag_clear(ADD_TIME_FLAG)
        self.setup()
        self.active = self.scoring = True
        if self.timer_adj is not None:
            self.seconds = os_.adj[self.timer_adj]
        self.start_timer()
        os_.show(self.intro_task, self.intro, on_end=self.mgr.pause)
        return True

    def setup(self):
        """Per-run state (lit shots)."""

    def start_timer(self):
        self.waiting_intro = True
        self.os.task_start(self.timer_task, STEP_TICKS, self._timer)

    def _timer(self):
        os_ = self.os
        if not self.scoring:
            return
        if self.waiting_intro:
            if os_.display.task_running(self.intro_task):
                os_.task_start(self.timer_task, STEP_TICKS, self._timer)
                return
            self.waiting_intro = False
            self.steps = 0
            os_.task_start(self.timer_task, INTRO_WAIT_TICKS, self._timer)
            return
        if self.mgr.paused():
            self.steps = 0
        else:
            self.steps += 1
        if self.steps < STEPS:
            os_.task_start(self.timer_task, STEP_TICKS, self._timer)
            return
        self.steps = 0
        if self.seconds <= 0:
            self.time_up()
            return
        self.seconds -= 1
        os_.task_start(self.timer_task, STEP_TICKS, self._timer)

    def restart_timer(self, at_least):
        """A new level / rover hit: the timer back to at least `at_least` seconds, the count restarted."""
        self.seconds = max(self.seconds, at_least)
        self.steps = 0
        if self.active and not self.waiting_intro:
            self.os.task_start(self.timer_task, STEP_TICKS, self._timer)

    def add_time(self):
        """ADD MORE TIME [0x01024b14]: +15 s, capped at 90."""
        if self.active:
            self.seconds = min(self.seconds + ADD_TIME, MAX_TIME)
            self.steps = 0

    def time_up(self):
        """The timer reached 0: the run ends (music back), lit shots still score for 125 ticks, then the total."""
        os_ = self.os
        self.active = False
        os_.request_refresh()
        os_.task_start(self.timer_task, GRACE_TICKS, self._grace_end)

    def _grace_end(self):
        self.scoring = False
        self.show_total()

    def show_total(self):
        os_ = self.os
        if os_.tilted or not os_.game:
            return
        os_.display.when_idle(self.total_task, self.total_deff, values=[self.total])

    # ------------------------------------------------------------------ hits

    def multiplier(self, shot):
        return self.os.shot_mult(shot)

    def is_lit(self, shot):
        return bool(self.lit & (1 << shot))

    def hit(self, shot):
        if not self.scoring:
            return
        m = self.multiplier(shot)
        if self.is_lit(shot):
            self.lit_hit(shot, m)
        elif shot != BEE:
            self.unlit_hit(shot, m)
        self.os.request_refresh()

    def unlit_hit(self, shot, m):
        self.os.score_add(UNLIT_POINTS)
        self.total += UNLIT_POINTS

    def value(self, shot):
        raise NotImplementedError

    def lit_hit(self, shot, m):
        os_ = self.os
        points = m * self.value(shot)
        os_.score_add(points)
        self.total += points
        self.advance(shot)
        self.hits += 1
        left = self.pd.get(self.left_key, self.shots) - 1
        self.pd[self.left_key] = max(left, 0)
        self.hit_media(points, completed=left <= 0)
        if left <= 0:
            self.complete()

    def advance(self, shot):
        """The lit shots after a lit hit."""
        self.lit &= ~(1 << shot)

    def hit_media(self, points, completed=False):
        os_ = self.os
        kwargs = {"run_seconds": self.completed_seconds} if completed else {}
        os_.deff_start(self.hit_deff, values=[points], **kwargs)
        lengths = os_.sample_lengths(self.hit_sound)
        os_.sound(self.hit_sound, in_deff=self.hit_deff,
                  index=(self.hits - 1) % len(lengths) if lengths else None)

    def complete(self):
        os_ = self.os
        pd = self.pd
        pd["done_" + self.key] = self.done() + 1
        self.mgr.wizard(self.item, 2)
        os_.audit(self.audit_completed)
        pd.battle_completed = pd.get("battle_completed", 0) | self.bit
        self.kill()
        self.show_total()

    # ------------------------------------------------------------------ end

    def kill(self):
        os_ = self.os
        os_.task_kill(self.timer_task)
        os_.task_kill(self.run_task)
        self.active = self.scoring = False
        self.waiting_intro = False
        self.lit = 0

    def end(self, show_total=True):
        """End fn (drain, tilt): kill the run, then the total (not when tilted)."""
        if not self.scoring:
            return False
        self.kill()
        if show_total:
            self.show_total()
        return True

    def rule(self):
        return self.active

    def pop(self):
        """A pop bumper hit while it runs."""

    def background_values(self):
        return {"values": [self.seconds, self.pd.get(self.left_key, self.shots) if self.os.game else self.shots]}


class Starscream(Battle):
    key, index, side, timer_adj = "ss", 0, DECEPTICON, 72
    timer_task, run_task, intro_task = 0x9c, 0x9d, 0x68
    item, audit_started, audit_completed, insert = 1, 0x59, 0x5a, 7
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 92, 93, 94, 95, 0x28, 106, 0x181
    total_task = 0x80
    shots = 10
    PAIRS = (0x03, 0x06, 0x0c, 0x18, 0x30, 0x18, 0x0c, 0x06)       # table 0x040c6a40

    def setup(self):
        self.pair = 0
        self.lit = self.PAIRS[0]

    def value(self, shot):
        return min(100000 + 12500 * self.done(), 500000) + 12500 * self.hits

    def advance(self, shot):
        self.pair = (self.pair + 1) % len(self.PAIRS)
        self.lit = self.PAIRS[self.pair]


class Shockwave(Battle):
    key, index, side, timer_adj = "sw", 1, DECEPTICON, 73
    timer_task, run_task, intro_task, total_task = 0x9e, 0x9f, 0x69, 0x81
    item, audit_started, audit_completed, insert = 2, 0x5b, 0x5c, 6
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 96, 97, 98, 99, 0x29, 110, 0x195
    shots = 11
    completed_seconds = 8.67

    def setup(self):
        self.phase = 1
        self.lit = 0x01

    def value(self, shot):
        return min(200000 + 25000 * self.done(), 500000) + 25000 * self.hits

    def advance(self, shot):
        if self.phase == 1:
            self.phase, self.lit = 2, 0x10
        elif self.phase == 2:
            self.phase, self.lit = 3, 0x3f
        else:
            self.lit = 0x3f & ~(1 << shot)


class Blackout(Battle):
    key, index, side, timer_adj = "bo", 2, DECEPTICON, 74
    timer_task, run_task, intro_task, total_task = 0xa0, 0xa1, 0x6a, 0x82
    item, audit_started, audit_completed, insert = 3, 0x5d, 0x5e, 5
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 100, 101, 102, 103, 0x2a, 114, 0x1ab
    shots = 11
    completed_seconds = 9.0
    GROUPS = ((0x01, 0x02, 0x04), (0x08, 0x10, 0x20))

    def setup(self):
        self.used = [0, 0]
        self._light(0)

    def _light(self, group):
        """Add a random not yet used shot of the group to its used set and light that set [0x0101c910]."""
        shots = self.GROUPS[group]
        free = [b for b in shots if not self.used[group] & b]
        if free:
            pick = self.os.pick("blackout", [0 if self.used[group] & b else 1 for b in shots])
            self.used[group] |= shots[pick] if pick is not None else free[0]
        else:
            self.used[group] = sum(shots)
        self.lit = self.used[group]

    def value(self, shot):
        return min(200000 + 50000 * self.done(), 500000) + 50000 * self.hits

    def advance(self, shot):
        self._light(1 if self.hits % 2 == 0 else 0)     # hits counts this hit after advance


class Devastator(Battle):
    key, index, side, timer_adj = "dv", 3, DECEPTICON, 75
    timer_task, run_task, intro_task, total_task = 0xa2, 0xa3, 0x6b, 0x83
    item, audit_started, audit_completed, insert = 4, 0x5f, 0x60, 4
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 104, 105, 106, 107, 0x2b, 118, 0x1d1
    shots = 10
    completed_seconds = 8.76
    ROVER = (0, 1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 0)       # table 0x040c6964
    ROVER_LEFF, ROVER_POINTS = 120, 10000

    def setup(self):
        self.state = 1
        self.rover = 0
        self.lit = 1 << RIGHT_ORBIT

    def value(self, shot):
        return min(100000 + 100000 * self.done(), 500000) + 100000 * self.hits

    def advance(self, shot):
        if self.state == 1:
            self.state, self.rover = 2, 0
            self.lit = 1 << self.ROVER[0]
        else:
            self.state = 1
            self.lit = 1 << RIGHT_ORBIT
            self.restart_timer(self.os.adj[self.timer_adj])

    def pop(self):
        if self.state == 2 and self.scoring:
            os_ = self.os
            self.rover = (self.rover + 1) % len(self.ROVER)
            self.lit = 1 << self.ROVER[self.rover]
            os_.leff_start(self.ROVER_LEFF)
            os_.score_add(self.ROVER_POINTS)
            os_.request_refresh()

    def background_values(self):
        return {"values": [self.seconds, self.pd.get(self.left_key, self.shots) if self.os.game else self.shots]}


class Bumblebee(Battle):
    """Phase 1: the six main shots at a decaying value (no timer); phase 2: the Bumblebee target on a timer."""
    key, index, side, timer_adj = "bb", 4, AUTOBOT, 76
    timer_task, run_task, intro_task, total_task = 0xa4, 0xa5, 0x6c, 0x84
    item, audit_started, audit_completed, insert = 6, 0x61, 0x62, 23
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 108, 109, 110, 111, 0x2c, 123, 0x1ee
    PHASE2_LEFF = 124
    completed_seconds = 7.99
    DECAY_TICKS, END_TICKS, FLOOR = 3, 46, 100000
    DIRECT_JACKPOT = 200000

    def reset(self):
        self.pd.bb_phase = 1
        self.pd.bb_mask = 0x3f

    def setup(self):
        pd = self.pd
        self.start_value = min(750000 + 50000 * self.done(), 1000000)
        self.current = self.start_value
        self.decay = (self.start_value - self.FLOOR) // 3000 * 10 - 10
        self.jackpot = 0
        self.direct = pd.get("bb_phase", 1) == 2
        self.lit = pd.get("bb_mask", 0x3f) if not self.direct else 0x40
        if self.direct:
            self.seconds = self.os.adj[self.timer_adj]

    def start(self):
        Battle.start(self)
        if self.direct:
            self.seconds = self.os.adj[self.timer_adj]
        return True

    def start_timer(self):
        self.waiting_intro = True
        self.os.task_start(self.timer_task, STEP_TICKS, self._timer)

    def _timer(self):
        if self.pd.get("bb_phase", 1) == 2:
            Battle._timer(self)
            return
        os_ = self.os
        if not self.scoring:
            return
        if self.waiting_intro:
            if os_.display.task_running(self.intro_task):
                os_.task_start(self.timer_task, STEP_TICKS, self._timer)
                return
            self.waiting_intro = False
            os_.task_start(self.timer_task, INTRO_WAIT_TICKS, self._timer)
            return
        if not self.mgr.paused():
            self.current = max(self.current - self.decay, self.FLOOR)
        if self.current <= self.FLOOR:
            os_.task_start(self.timer_task, self.END_TICKS, self.time_up)
            return
        os_.task_start(self.timer_task, self.DECAY_TICKS, self._timer)

    def value(self, shot):
        if shot == BEE:
            return self.jackpot if not self.direct else self.DIRECT_JACKPOT
        return self.current

    def unlit_hit(self, shot, m):
        points = UNLIT_POINTS * (m if self.pd.get("bb_phase", 1) == 1 else 1)
        self.os.score_add(points)
        self.total += points

    def lit_hit(self, shot, m):
        os_ = self.os
        pd = self.pd
        if shot == BEE:
            points = self.value(shot)
            os_.score_add(points)
            self.total += points
            self.hits += 1
            self.hit_media(points, completed=True)
            self.complete()
            return
        points = m * self.current
        os_.score_add(points)
        self.total += points
        self.jackpot += points
        pd.bb_mask = pd.get("bb_mask", 0x3f) & ~(1 << shot)
        self.hits += 1
        self.mgr.pause()
        if pd.bb_mask:
            self.lit = pd.bb_mask
            self.hit_media(points)
            return
        pd.bb_phase = 2
        pd.bb_mask = self.lit = 0x40
        self.hit_media(points)
        self.seconds = os_.adj[self.timer_adj]
        self.steps = 0
        self.waiting_intro = False
        os_.task_start(self.timer_task, STEP_TICKS, self._timer)
        os_.request_refresh()

    def add_time(self):
        if not self.active:
            return
        if self.pd.get("bb_phase", 1) == 1:
            self.current = self.start_value
        else:
            self.seconds = min(self.seconds + 5, 15)

    def phase2(self):
        return self.active and self.pd.get("bb_phase", 1) == 2

    def background_values(self):
        """Deff 109's captured page is phase 2's: "%,02lu" the timer (RAM 0x34f7c) over "SHOOT CAMARO / FOR %,02lu"
        the award (0x34f74). Phase 1's page (value 0x34f70, "BEE = " award) is not in the capture: its value and
        award go in the same two slots."""
        award = self.DIRECT_JACKPOT if getattr(self, "direct", False) else getattr(self, "jackpot", 0)
        if self.os.game and self.pd.get("bb_phase", 1) == 2:
            return {"values": [self.seconds, award]}
        return {"values": [getattr(self, "current", 0), award]}


class Ironhide(Battle):
    key, index, side, timer_adj = "ih", 5, AUTOBOT, 77
    timer_task, run_task, intro_task, total_task = 0xa6, 0xa7, 0x6d, 0x85
    item, audit_started, audit_completed, insert = 7, 0x63, 0x64, 24
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 112, 113, 114, 115, 0x2d, 128, 0x201
    shots = 10
    completed_seconds = 7.02
    PATTERNS = {1: 0x08, 2: 0x14, 3: 0x2a, 4: 0x36}    # table 0x040c6b3c

    def reset(self):
        Battle.reset(self)
        self.pd.ih_level = 1
        self.pd.ih_lit = self.PATTERNS[1]

    def setup(self):
        self.lit = self.pd.get("ih_lit", self.PATTERNS[1])

    def value(self, shot):
        return min(200000 + 50000 * self.done(), 500000) + 50000 * self.hits

    def advance(self, shot):
        pd = self.pd
        pd.ih_lit = pd.get("ih_lit", 0) & ~(1 << shot)
        if not pd.ih_lit:
            pd.ih_level = min(pd.get("ih_level", 1) + 1, 4)
            pd.ih_lit = self.PATTERNS[pd.ih_level]
            self.restart_timer(self.os.adj[self.timer_adj])
        self.lit = pd.ih_lit


class Mudflap(Battle):
    """Mudflap & Skids: a 2-ball multiball instead of a timer [0x01019150]."""
    key, index, side, timer_adj = "mf", 6, AUTOBOT, 78
    timer_task, run_task, intro_task, total_task = 0xa8, 0xa9, 0x6e, 0x86
    item, audit_started, audit_completed, insert = 8, 0x65, 0x66, 25
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 116, 117, 118, 119, 0x2e, 132, 0x21c
    shots = 11
    multiball = True
    RUNNING_FLAG, COMPLETED_FLAG, ADD_BALL_FLAG = 0x1e, 0x1d, 0x14
    SAVE_TICKS_PER_S, GRACE = 62, 187
    END_SOUND_TICKS, END_SOUND, TOTAL_AFTER_TICKS = 142, 0x231, 53

    def start(self):
        os_ = self.os
        self.kill()
        self.hits = 0
        self.total = START_POINTS
        balls = os_.rom_balls_in_play()
        os_.multiball_start(balls + 1 if balls else 2, save_ticks=os_.adj[self.timer_adj] * self.SAVE_TICKS_PER_S,
                            grace_ticks=self.GRACE)
        os_.score_add(START_POINTS)
        os_.flag_set(self.RUNNING_FLAG)
        os_.flag_clear(self.COMPLETED_FLAG)
        if not os_.any_multiball():               # [0x01019150] tests after setting 0x1e: never clears
            os_.flag_clear(self.ADD_BALL_FLAG)
        self.lit = 0x3f
        self.active = self.scoring = True
        os_.show(self.intro_task, self.intro, on_end=self.mgr.pause)
        return True

    def value(self, shot):
        return min(200000 + 50000 * (self.hits + 1 + self.done()), 500000)

    def advance(self, shot):
        self.lit &= ~(1 << shot)
        if not self.lit:
            self.lit = 0x3f

    def lit_hit(self, shot, m):
        os_ = self.os
        points = m * self.value(shot)
        os_.score_add(points)
        self.total += points
        self.advance(shot)
        self.hits += 1
        left = self.pd.get(self.left_key, self.shots) - 1
        first = left <= 0 and not os_.flag(self.COMPLETED_FLAG)
        if left <= 0:
            left = self.shots
        self.pd[self.left_key] = left
        self.hit_media(points, completed=first)
        if first:
            os_.flag_set(self.COMPLETED_FLAG)
            pd = self.pd
            pd["done_" + self.key] = self.done() + 1
            self.mgr.wizard(self.item, 2)
            os_.audit(self.audit_completed)
            pd.battle_completed = pd.get("battle_completed", 0) | self.bit

    def hit_media(self, points, completed=False):
        Battle.hit_media(self, points)

    def multiball_end(self):
        """Down to one ball [0x01019550]: flag 0x1e off (music back), grace task 0xa9, then the total."""
        os_ = self.os
        if not self.active:
            return
        self.active = False
        os_.flag_clear(self.RUNNING_FLAG)
        os_.request_refresh()
        os_.task_start(self.run_task, self.END_SOUND_TICKS, self._end_sound)

    def _end_sound(self):
        self.os.sound(self.END_SOUND)
        self.os.task_start(self.run_task, self.TOTAL_AFTER_TICKS, self._grace_end)

    def add_ball(self):
        """ADD-A-BALL during the grace revives it [0x01019594]."""
        if self.scoring and not self.active:
            self.os.task_kill(self.run_task)
            self.os.flag_set(self.RUNNING_FLAG)
            self.active = True
            self.os.request_refresh()

    def kill(self):
        Battle.kill(self)
        self.os.flag_clear(self.RUNNING_FLAG)

    def background_values(self):
        return {"values": [self.pd.get(self.left_key, self.shots) if self.os.game else self.shots]}


class Ratchet(Battle):
    key, index, side, timer_adj = "ra", 7, AUTOBOT, 79
    timer_task, run_task, intro_task, total_task = 0xaa, 0xab, 0x6f, 0x87
    item, audit_started, audit_completed, insert = 9, 0x67, 0x68, 26
    intro, bg, hit_deff, total_deff, music, rule_leff, hit_sound = 120, 121, 122, 123, 0x2f, 136, 0x236
    shots = 11

    def reset(self):
        Battle.reset(self)
        self.pd.ra_lit = 0x3f

    def setup(self):
        self.lit = self.pd.get("ra_lit", 0x3f)

    def double(self):
        return self.lit & -self.lit           # the lowest lit shot [0x01012178]

    def value(self, shot):
        base = min(100000 + 50000 * self.done(), 500000) + 50000 * self.hits
        return base * 2 if (1 << shot) == self.double() else base

    def advance(self, shot):
        pd = self.pd
        pd.ra_lit = pd.get("ra_lit", 0x3f) & ~(1 << shot)
        if not pd.ra_lit:
            pd.ra_lit = 0x3f
        self.lit = pd.ra_lit


BATTLES = (Starscream, Shockwave, Blackout, Devastator, Bumblebee, Ironhide, Mudflap, Ratchet)


class Battles(Feature):
    name = "battles"
    HOOKS = ("player_first_ball", "ball_start", "side_changed", "ball_end", "ball_end_wait", "tilt", "timed_mode",
             "timer_pause", "multiball_end", "battle_shot", "mode_start_shot", "add_time", "add_ball",
             "sw_1", "sw_5", "sw_6", "sw_13", "sw_10", "sw_11", "sw_12", "sw_14", "sw_51", "sw_7", "sw_8",
             "sw_30", "sw_31", "sw_32", "battle_running", "wizard_reset")

    def __init__(self, os_):
        super().__init__(os_)
        self.battles = [cls(self) for cls in BATTLES]
        self.left_orbit_at = {5: -10.0, 6: -10.0}
        self.orbit_token = 0.0          # token 7 runs until then
        self.center_at = self.lane_at = -10.0
        self.launched_at = self.back_door_at = self.right_at = -10.0
        self.machine.switch_controller.add_switch_handler("s_shooter_lane", self._launched, state=0)
        self.ended_at_drain = False
        for deff_id, (seconds, leffs, sounds) in UNCAPTURED.items():
            os_.display.set_media(deff_id, seconds, leffs, sounds)
        for b in self.battles:
            os_.deff_rule((lambda b_: lambda: b_.rule())(b), b.bg, music=b.music, priority=RULE_PRIORITY)
            os_.deff_live((b.bg,), b.background_values)
            if b.rule_leff:
                os_.lamp_rule((lambda b_: lambda: b_.active and not (isinstance(b_, Bumblebee) and b_.phase2()))(b),
                              leff=b.rule_leff, order=0x01012000 + b.index)
        bee = self.battles[4]
        os_.lamp_rule(lambda: bee.phase2(), leff=Bumblebee.PHASE2_LEFF, order=0x01012010)
        os_.lamp_rule(lambda: bool(os_.game) and self.qualify_allowed() and bool(self.pd.get("battle_lit")),
                      leff=LIT_LEFF, order=0x010232d4)
        os_.lamp_update(self.draw)
        os_.register_poke(0x2111ecc, self._poke("battle_lit"), stride=4)
        for b in self.battles:
            addr = {"ss": 0x2111e5c, "sw": 0x2111e9c, "bo": 0x2111e94, "dv": 0x2111e54, "ih": 0x2111e8c,
                    "mf": 0x2111e64, "ra": 0x2111e2c}.get(b.key)
            if addr:
                os_.register_poke(addr, self._poke(b.left_key), stride=2)

    def _poke(self, key):
        def setter(p, v):
            players = self.os.players
            if p < len(players):
                players[p][key] = v
        return setter

    # ------------------------------------------------------------------ state

    def player_first_ball(self):
        pd = self.pd
        pd.battle_started = pd.battle_completed = 0
        pd.battles_started_n = 0
        for b in self.battles:
            b.reset()
            pd["done_" + b.key] = 0
        self.ms_reset()
        self.side_changed()

    def wizard_reset(self):
        """[0x010359f4(2)]: 0x01022b88(0xff) and each battle's reset (the wizard multiball start)."""
        pd = self.pd
        pd.battle_started = pd.battle_completed = 0
        for b in self.battles:
            b.reset()
        self.os.request_refresh()

    def ball_start(self):
        """The lit-battle rule's leff 104 is the first effect of every ball start (all traces: 104, then 92):
        its rule is evaluated here, before the ball start effects, instead of at the next rules refresh."""
        os_ = self.os
        for rule in os_.rules:
            if rule[1] == LIT_LEFF:
                rule[3] = bool(rule[0]())
                if rule[3]:
                    os_.leff_start(LIT_LEFF, loop=True)

    def side_changed(self):
        """[0x01022d7c]: the side's first battle (Bumblebee whatever the side in competition mode at game start)."""
        pd = self.pd
        if self.os.adj[42] and not pd.get("battle_started"):
            pd.battle_lit = 0x10
            return
        pd.battle_lit = 0x10 if pd.get("side", DECEPTICON) == AUTOBOT else 0x01

    def wizard(self, item, what):
        """[0x01035af0(item, what)]: 1 collected, 2 completed (tf/features/wizard.py)."""
        self.os.hook("wizard_req", item, what)

    def running(self):
        return next((b for b in self.battles if b.scoring), None)

    def battle_running(self):
        return any(b.active for b in self.battles) or None

    def timed_mode(self):
        return any(b.active and not b.multiball for b in self.battles) or None

    def timer_pause(self):
        os_ = self.os
        return os_.task_running(PAUSE_TASK) or os_.ball_held or None

    def paused(self):
        return self.os.timed_mode_paused() or self.os.ball_held

    def pause(self, ticks=PAUSE_TICKS):
        """[0x010062f0(ticks)]: battle timers hold."""
        if self.os.task_ticks_left(PAUSE_TASK) < ticks:
            self.os.task_start(PAUSE_TASK, ticks)

    def qualify_allowed(self):
        """clu_start_allowed [0x01022ca8] and the side gates of [0x0101fdac]."""
        os_ = self.os
        if not os_.game or os_.any_multiball() or self.battle_running() or os_.flag(0x3c):
            return False
        pd = self.pd
        done = pd.get("battle_completed", 0)
        own = 0x0f if pd.get("side", DECEPTICON) == DECEPTICON else 0xf0
        other = 0xff & ~own
        if done & 0xff == 0xff:
            return False
        if done & own == own and not os_.flag(SIDE_DONE_FLAG):
            return False
        if done & own == own and done & other == other and os_.flag(SIDE_DONE_FLAG):
            return False
        return True

    def next_battle(self, index):
        """[0x010229ec]: from the record after `index`, the first battle of its ring not started, else the first
        started but not completed, else none."""
        pd = self.pd
        base = 0 if index < 4 else 4
        ring = [base + (index - base + k) % 4 for k in range(1, 5)]
        started, completed = pd.get("battle_started", 0), pd.get("battle_completed", 0)
        for i in ring:
            if not started & (1 << i):
                return 1 << i
        for i in ring:
            if not completed & (1 << i):
                return 1 << i
        return 0

    def lit_index(self):
        lit = self.pd.get("battle_lit", 0)
        return lit.bit_length() - 1 if lit else None

    def rotate(self):
        """[0x01022cf8]: pops and the Bumblebee target move the lit battle while qualifying is allowed."""
        if not self.qualify_allowed():
            return
        index = self.lit_index()
        if index is not None:
            self.pd.battle_lit = self.next_battle(index)
            self.os.request_refresh()

    # ------------------------------------------------------------------ mode-start shots

    def ms_reset(self):
        """[0x0101fe98]: light N shots walking from shot 1; hits 0; needed 4."""
        pd = self.pd
        n, _ = MS_DIFFICULTY.get(self.os.adj[66], MS_DIFFICULTY[3])
        pd.ms_lit = sum(1 << s for s in MS_WALK[:n])
        pd.ms_hits = 0
        pd.ms_needed = MS_NEEDED

    def mode_start_shot(self, ms):
        """[0x01020074]: a mode-start shot made."""
        os_ = self.os
        pd = self.pd
        if os_.tilted or not self.qualify_allowed() or not pd.get("ms_lit", 0) & (1 << ms):
            return
        side = pd.get("side", DECEPTICON)
        value = min(10000 + 10000 * pd.get("battles_started_n", 0) + 5000 * pd.get("ms_hits", 0), 75000)
        shot = MS_BATTLE_SHOT[ms]
        os_.score_add(value * os_.shot_mult(shot))
        pd.ms_hits = pd.get("ms_hits", 0) + 1
        if pd.ms_hits < pd.get("ms_needed", MS_NEEDED):
            difficulty = os_.adj[66]
            if difficulty != 0:
                pd.ms_lit &= ~(1 << ms)
            _, minimum = MS_DIFFICULTY.get(difficulty, MS_DIFFICULTY[3])
            if bin(pd.ms_lit).count("1") < minimum:
                weights = [0 if (pd.ms_lit & (1 << i) or i == ms) else 1 for i in range(5)]
                pick = os_.pick("mode_start", weights)
                if pick is not None:
                    pd.ms_lit |= 1 << pick
            left = pd.ms_needed - pd.ms_hits
            os_.deff_start(MS_DEFF, values=[left], sounds=[(0, lambda: os_.sound(MS_SOUND[side], in_deff=MS_DEFF))])
            os_.leff_start(MS_LEFF)
            os_.request_refresh()
            return
        self.start_lit()

    def start_lit(self):
        """[0x01022e08]: start the battle of battle_lit."""
        os_ = self.os
        pd = self.pd
        index = self.lit_index()
        if index is None:
            return False
        battle = self.battles[index]
        if not battle.start():
            return False
        pd.battle_started = pd.get("battle_started", 0) | battle.bit
        self.ms_reset()
        pd.battles_started_n = min(pd.get("battles_started_n", 0) + 1, 255)
        os_.audit(battle.audit_started)
        os_.audit(MODES_STARTED_AUDIT)
        self.wizard(battle.item, 1)
        pd.battle_lit = self.next_battle(index)
        os_.request_refresh()
        return True

    # ------------------------------------------------------------------ shots

    def shot(self, shot, mb=True):
        """A battle shot made (the shot handlers): its audit, every battle's hit fn, the mode-start rule (and
        the left orbit's combo, which the orbit tokens decide here)."""
        os_ = self.os
        if not os_.game or os_.tilted:
            return
        if shot in SHOT_AUDIT:
            os_.audit(SHOT_AUDIT[shot])
        if mb:
            os_.hook("mb_shot", shot)               # the multiball and wizard shot rules
        self.battle_shot(shot)
        if shot in MS_SHOT:
            self.mode_start_shot(MS_SHOT[shot])
        if shot in (LEFT_ORBIT, RIGHT_ORBIT):
            os_.hook("combo_shot", shot)

    def _launched(self):
        self.launched_at = self.os.now

    def sw_13(self):
        self.back_door_at = self.os.now

    def battle_shot(self, shot):
        for b in self.battles:
            if b.scoring:
                b.hit(shot)

    def _left_orbit(self, num):
        now = self.os.now
        self.left_orbit_at[num] = now
        if now < self.orbit_token:
            self.orbit_token = now + ORBIT_TOKEN_S if num == 6 else 0.0
            return
        self.orbit_token = now + ORBIT_TOKEN_S
        self.os.hold_coil("c_orbit_control_gate", 5, GATE_TICKS)
        self.shot(LEFT_ORBIT)

    def sw_5(self):
        self._left_orbit(5)

    def sw_6(self):
        self._left_orbit(6)

    def sw_10(self):
        self.shot(LEFT_RAMP)

    def _center(self, mb=True):
        now = self.os.now
        last, self.center_at = self.center_at, now
        if now - last < CENTER_LOCK_S:
            return
        self.shot(CENTER, mb)

    def sw_11(self):
        self.lane_at = self.os.now                  # the right orbit's debounce counts the lane only (optimus_* traces)
        self._center()

    def sw_51(self):
        self._center(mb=False)                      # Optimus has its own multiball rules (hook sw_51)

    def sw_12(self):
        now = self.os.now
        self.orbit_token = 0.0
        last = max(list(self.left_orbit_at.values()) + [self.back_door_at, self.lane_at, self.launched_at])
        if now - last < RIGHT_IGNORE_S or now - self.right_at < RIGHT_REPEAT_S:
            return
        self.right_at = now
        self.shot(RIGHT_ORBIT)

    def sw_14(self):
        self.shot(RIGHT_RAMP)

    def sw_1(self):
        """[0x01033adc]: the lit battle moves, then battle shot 6 (the Bumblebee letters follow)."""
        if self.os.tilted:
            return
        self.rotate()
        self.battle_shot(BEE)

    def _top_lane(self):
        if self.running():
            self.pause()

    sw_7 = sw_8 = _top_lane

    def _pop(self):
        """[0x01032f8c]: the lit battle moves, the Devastator rover moves, battle timers pause."""
        if self.os.tilted:
            return
        self.rotate()
        for b in self.battles:
            if b.scoring:
                b.pop()
        if self.running():
            self.pause()

    sw_30 = sw_31 = sw_32 = _pop

    def add_time(self):
        for b in self.battles:
            b.add_time()
        self.os.flag_set(ADD_TIME_FLAG)

    def add_ball(self):
        self.battles[6].add_ball()

    def multiball_end(self):
        self.battles[6].multiball_end()

    # ------------------------------------------------------------------ end

    def ball_end(self):
        """Event 0x1d: every battle ends; the totals show at once (the bonus waits for them)."""
        self.ended_at_drain = False
        for b in self.battles:
            if b.end(show_total=not self.os.tilted):
                self.ended_at_drain = True

    def ball_end_wait(self):
        return TOTAL_TICKS if self.ended_at_drain else None

    def tilt(self):
        for b in self.battles:
            b.end(show_total=False)

    # ------------------------------------------------------------------ lamps

    def draw(self):
        os_ = self.os
        lamps = os_.lamps
        pd = self.pd
        side = pd.get("side", DECEPTICON)
        allowed = self.qualify_allowed()
        for ms, (red, purple) in MS_LAMPS.items():
            on = allowed and pd.get("ms_lit", 0) & (1 << ms)
            mine, other = (red, purple) if side == AUTOBOT else (purple, red)
            if on:
                lamps.lamp_flash(mine)
            else:
                lamps.lamp_off(mine)
            lamps.lamp_off(other)
        lit = 0
        for b in self.battles:
            if b.scoring:
                lit |= b.lit
        for shot, lamp in ORANGE.items():
            if lit & (1 << shot):
                lamps.lamp_flash(lamp)
            else:
                lamps.lamp_off(lamp)
        started, completed = pd.get("battle_started", 0), pd.get("battle_completed", 0)
        for b in self.battles:
            if completed & b.bit:
                lamps.lamp_on(b.insert)
            elif started & b.bit:
                lamps.lamp_flash(b.insert)
            else:
                lamps.lamp_off(b.insert)


def feature(os_):
    return Battles(os_)
