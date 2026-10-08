"""Combos and shot multipliers (rom/rules/modes/combos_and_multipliers.md sections 4 and 6; code [0x01002f0c]
[0x01002be4] [0x01002b5c] [0x010236e8] [0x01023538] + observed in traces/combos.jsonl).

Major shots (index / mask bit): 0 left eject (the Allspark rule, tf/features/allspark.py), 1 left orbit (sw5
or sw6 as tf/features/battles.py decides a pass, hook combo_shot), 2 left ramp exit
(sw10), 3 center lane (sw11), 4 right ramp exit (sw14), 5 right orbit (sw12: not when the ball just came
round the left orbit, switch timer 7, and not within 187 ticks of the previous right orbit shot).

Combos, on a major shot:
1. no window running: combo_way = 1, no award;
2. the shot's bit in combo_mask: way + 1, award M x (100,000 + 25,000 x way) with M the shot's multiplier,
   leff 35, audit 154 (observed 150,000 ... 250,000 for 2- to 6-way);
3. else the way count stays.
Then the window ends, and unless a multiball runs ([0x01002afc] -> [0x01006704], the multiball flags, named
any_timed_mode_running in the decompile) mask = all six minus the shot when it is the eject or the left ramp and
the window restarts: 312 ticks (task 0x92, not counting while the
left eject holds a ball) + 124 grace ticks (task 0x93). During a battle it restarts (observed:
traces/battle_starscream.jsonl, no award at 32.29 s 7.2 s after the last shot, 2-way 150,000 at 34.47 s, then a
combo on every shot). The arrows of the allowed shots (leff 34 [0x01003104]) are not drawn: 1.80 never runs
that leff (no start in the code or the traces; the arrow lamps stay as the modes set them during a window).
deff 48 (n-WAY COMBO) is never started in 1.80 (no starter; the status panel shows combos).

Shot multipliers (per ball, 1X unless the shot's hold flag 0x16 + s is set):
- lighting (own lanes complete, left-eject award): if a shot is below 2X, mult_lit and leff 37 run, deff 44;
- the next major shot below 2X goes to 2X: deff 50, sound 0x05b, leff 38 (inferred: after its combo award).
- lighting with all six at 2X starts the roving 3X [0x010236e8] (task 0xb6, until the ball ends) [0x01023650]:
  index 6 (the right orbit) moving to 2 and back every 92 ticks; the shot at the index is 3X, and for the
  first 46 ticks after a move the shot it left too [0x01023538]. Leff 39 (rule while task 0xb6 runs) blinks
  that shot's X lamp every 3 ticks [0x010239bc]. Code only (not traced).
shot_mult(shot) is the multiplier every award uses (os_layer.shot_mult).
The orbits are decided with the battle shots (tf/features/battles.py: left orbit sw5 / sw6 tokens, right orbit
sw12 ignored after a left orbit pass, the center lane, a plunge or the back door, and within 187 ticks of the
previous right orbit) and come here through hook combo_shot.
"""
from tf.features import Feature

ORDER = 45
SHOTS = {10: 2, 11: 3, 14: 4}      # switch -> shot index (eject 0, the orbits 1 and 5: hook combo_shot)
EJECT, LEFT_RAMP, RIGHT_ORBIT = 0, 2, 5
ALL = 0x3f
WINDOW_TICKS, GRACE_TICKS, STEP_TICKS = 312, 124, 7
WINDOW_TASK = 0x92
AWARD_LEFF, AWARD_AUDIT, WINDOW_LEFF = 35, 154, 34
MULT_LIT_LEFF, MULT_LIT_DEFF = 37, 44
MULT_DEFF, MULT_SOUND, MULT_LEFF = 50, 0x05b, 38
HOLD_FLAG = 0x16
ROVE_TASK, ROVE_TICKS, ROVE_LEFF, ROVE_BLINK = 0xb6, 46, 39, 3
X_LAMPS = (12, 16, 47, 43, 31, 36)  # shot index -> its X lamp (table 0x040c6f58 + 0x12, entries 1-6)


class Combos(Feature):
    name = "combos"
    HOOKS = ("player_first_ball", "ball_start", "switch", "shot_mult_light", "ball_end", "tilt", "combo_shot")

    def __init__(self, os_):
        super().__init__(os_)
        self.way = 0
        self.ticks = 0
        self.mask = ALL
        os_.lamp_rule(lambda: bool(os_.game) and bool(self.pd.get("mult_lit")), leff=MULT_LIT_LEFF,
                      order=0x01023928)
        self.rove = self.rove_prev = 0          # roving 3X index (1-6 = shot + 1) and the one it just left
        self.rove_dir = -1
        os_.lamp_rule(lambda: bool(os_.game) and os_.task_running(ROVE_TASK), leff=ROVE_LEFF, order=0x01023a70)
        os_.lamps.leff_code(ROVE_LEFF, self._rove_leff)

    def shot_mult(self, shot):
        """[0x01023538]: the shot's multiplier, 3 while the roving 3X is on it."""
        if self.os.task_running(ROVE_TASK) and shot + 1 in (self.rove, self.rove_prev):
            return 3
        mult = self.pd.get("shot_mult")
        return mult[shot] if mult and shot < len(mult) else 1

    def _rove_start(self):
        self.rove, self.rove_prev, self.rove_dir = 6, 0, -1
        self.os.task_start(ROVE_TASK, ROVE_TICKS, self._rove_half)

    def _rove_half(self):
        """[0x01023650]: 46 ticks with the left shot still 3X, then 46 more before the next move."""
        self.rove_prev = 0
        self.os.task_start(ROVE_TASK, ROVE_TICKS, self._rove_move)

    def _rove_move(self):
        self.rove_prev = self.rove
        if self.rove_dir < 1:
            if self.rove < 2:
                self.rove_dir, self.rove = 1, 2
            else:
                self.rove -= 1
        elif self.rove < 6:
            self.rove += 1
        else:
            self.rove_dir, self.rove = -1, 5
        self.os.task_start(ROVE_TASK, ROVE_TICKS, self._rove_half)
        self.os.request_refresh()

    def _rove_leff(self, task):
        """leff_039 [0x010239bc]: the X lamp of the roving index blinks (toggled every 3 ticks), the others are
        left to the rules."""
        lamp = X_LAMPS[self.rove - 1] if 1 <= self.rove <= 6 else None
        for x in X_LAMPS:
            if x != lamp:
                task.release(x)
        if lamp is not None:
            task.toggle(lamp)
        task.sleep(ROVE_BLINK, self._rove_leff)

    def combo_shot(self, index):
        self.shot(index)

    def player_first_ball(self):
        self.pd.combo_total = 0
        self.pd.combo_best = 1

    def ball_start(self):
        pd = self.pd
        old = pd.get("shot_mult", [1] * 6)
        pd.shot_mult = [old[s] if self.os.flag(HOLD_FLAG + s) else 1 for s in range(6)]
        pd.mult_lit = False

    def switch(self, num):
        if num in SHOTS and not self.os.tilted:
            self.shot(SHOTS[num])

    def shot(self, index):
        os_ = self.os
        if not os_.game or not os_.in_play or os_.tilted:
            return
        pd = self.pd
        bit = 1 << index
        if not os_.task_running(WINDOW_TASK):
            self.way = 1
        elif self.mask & bit:
            self.way += 1
            pd.combo_total = pd.get("combo_total", 0) + 1
            mult = self.shot_mult(index)
            pd.combo_best = max(pd.get("combo_best", 1), (self.way << 16) | mult)
            os_.score_add(mult * (100000 + 25000 * self.way))
            os_.leff_start(AWARD_LEFF)
            os_.audit(AWARD_AUDIT)
        if pd.get("mult_lit") and pd.shot_mult[index] < 2:
            pd.shot_mult[index] = 2
            pd.mult_lit = False
            os_.deff_start(MULT_DEFF)                   # its sound 0x05b comes with it
            os_.leff_start(MULT_LEFF)
            os_.request_refresh()
        restart = not os_.task_running(WINDOW_TASK)
        os_.task_kill(WINDOW_TASK)
        if os_.any_multiball():
            os_.request_refresh()
            return
        self.mask = ALL & ~(bit if index in (EJECT, LEFT_RAMP) else 0)
        self.ticks = WINDOW_TICKS
        os_.task_start(WINDOW_TASK, STEP_TICKS, self._step)
        if restart:
            os_.request_refresh()

    def _step(self):
        """[0x01002b5c]: combo_ticks - 7 every 7 ticks, not while the left eject's device task runs (a held
        ball, [0x0103a4f0(3)]; traces/wizard_multiball.jsonl: the eject's window still open 7.4 s on), then
        124 ticks of grace."""
        os_ = self.os
        if not os_.ball_held:
            self.ticks = max(self.ticks - STEP_TICKS, 0)
        if self.ticks:
            os_.task_start(WINDOW_TASK, STEP_TICKS, self._step)
        else:
            os_.task_start(WINDOW_TASK, GRACE_TICKS, self._window_end)

    def _window_end(self):
        self.os.request_refresh()

    def shot_mult_light(self):
        """[0x010236e8]: shot multipliers lit when a shot is below 2X, else the roving 3X starts (deff 44 shows
        which, from the lanes' caller)."""
        os_ = self.os
        pd = self.pd
        below = sum(1 for m in pd.get("shot_mult", [1] * 6) if m < 2)
        if below:
            pd.mult_lit = True
        elif not os_.task_running(ROVE_TASK):
            self._rove_start()
        else:
            return
        os_.deff_start(MULT_LIT_DEFF)
        os_.request_refresh()

    def ball_end(self):
        self.os.task_kill(WINDOW_TASK)
        self.os.task_kill(ROVE_TASK)
        self.rove = self.rove_prev = 0
        self.way = 0

    tilt = ball_end


def feature(os_):
    return Combos(os_)
