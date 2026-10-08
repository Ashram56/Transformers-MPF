"""The Megatron lock and the Megatron multiball, Autobot (A) and Decepticon (D) rules
(rom/rules/modes/megatron_multiball.md; code [0x0100a31c] [0x0100acb4] [0x0100af0c] [0x0100b130] [0x0100c200]
[0x0100c430] [0x0100e0bc] [0x0100e29c] + observed in traces/megatron_autobot.jsonl, megatron_decepticon.jsonl).

Lock (per player): level = adj 68 at game start, +1 at each Megatron multiball; completions needed per lock:
level 0 -> 0 (all four lit at once), 1 -> 1, n -> min(n - 1, 5). An Energon set completion (hook
lock_completion, [0x0100af0c]) counts when no Megatron / Optimus / side mode / wizard multiball runs, no lock is lit
and lit + locked < 4: 5,000, or on the last one the lock is lit (level < 2: all four; else one, the counter re-armed;
per player here, the ROM's re-arm copies every player's counter), audit 0x74, deff 139, leff 167, sound 0x293,
10,000.

Lock entry (switches 38-41, the ball device bd_megatron; its handler runs 46 ticks after the switch, observed
0.75 s): the shot-6 rules of the running mode, else a lit lock: BALL n LOCKED (25,000, audit 0x75, deff 140,
leff 168, sound 0x29a / 0x29c / 0x29f); the 4th ball starts the multiball of the player's side. Then the handler's
5,120. A locked ball stays (ball hold hold_megatron) and a new ball is served and launched 155 ticks later
(observed 2.51 s to the trough coil, adj 89 AUTOFIRE AFTER LOCK); any other ball is kicked out (0x13b + leff 23,
0x13b, 0x13c + leff 24, coil 3 0.62 s after the handler, observed). A ball within the back-door task (sw 13,
187 ticks) is kicked out with no shot rules.

Multiball: multiball_start(4 if no ball is in play else in play + 3, ball save 625, grace 187); level + 1 and the
lock state re-derived; wizard requirement 0 collected; the locked balls are released when the intro ends.
A: 250,000, flag 0x25, intro deff 69 (task 0x74), leff 61, audit 0x76. Megatron lights the jackpot
J = min(100,000 x (supers + 1) + 25,000 x M, 500,000) (deff 71, leff 64, sound 0xca, audit 0x77), then the six shots
light for double jackpots DJ = min(2 J, 1,000,000) x the shot's multiplier (deff 72, leff 65, sound 0xd2, audit
0x78; 312 ticks without one: back to the jackpot, M = 1); M + 1 per award (max 6); after 10 awards or all six
doubles the super is lit at Megatron (leff 63): max(1,000,000, [100, 100, 75, 50]% of the awards since the last
super) (deff 73, leff 66, sound 0xd9, audit 0x79, requirement 0 completed). Adj 88 keeps phase, lit shots and
award count per player.
D: 100,000, flag 0x29, intro deff 75 (task 0x75), leff 69, audit 0x7a. All six shots and Megatron lit: a lit shot
min(100,000 + 25,000 x jackpots, 250,000) x its multiplier and unlit, Megatron 100,000 and relights all (deff 77,
leff 72, sound 0xe4, audit 0x7b); after 10 the center lane scores 3 double jackpots of 500,000 x its multiplier
(deff 78, leff 73, sound 0xf7, audit 0x7c), then Optimus (sw 51) the 1,000,000 super (deff 79, leff 74, sound 0xf9,
audit 0x7d, requirement 0 completed) and the jackpots start over.
End: down to one ball the running flag goes (music back), 218 ticks later the total (A deff 74 + leff 67, D deff
80 + leff 75) when the display is free; an ADD-A-BALL before then revives it.
Not modelled: task 0x57, adj 69 virtual lock. The rule leff (62 / 70) flashes the lit shots from the side's mask.
"""
from tf.features import Feature
from tf.lamps import shot_blink

ORDER = 38
AUTOBOT, DECEPTICON = 1, 2
SWITCHES = ("s_m_tron_lock_1_back", "s_megatron_lock_2", "s_megatron_lock_3", "s_megatron_lock_4")
SWITCH_NUMS = (41, 40, 39, 38)
RELEASE_EVENT = "tf_megatron_release"
# shot tables {mask bit, lamp group} [0x040c63e4 A, 0x040c65dc D]: the orange arrows, Megatron, Optimus (D)
ARROWS = ((0x01, (15,)), (0x02, (19,)), (0x04, (44,)), (0x08, (40,)), (0x10, (34,)), (0x20, (39,)), (0x40, (29,)))
SHOT_LAMPS = {62: ARROWS, 70: ARROWS + ((0x80, (59,)),)}
SETTLE_TICKS = 46
SERVE_TICKS = 155
ENTRY_POINTS = 5120
BACK_DOOR_S = 187 * 0.01626
SHOT = 6
POLL_TICKS = 6
KICK_WAIT_DEFF = 61

LIGHT_POINTS, COUNT_POINTS = 10000, 5000
LIGHT_AUDIT, LIGHT_DEFF, LIGHT_LEFF, LIGHT_SOUND = 0x74, 139, 167, 0x293
LOCK_POINTS, LOCK_AUDIT, LOCK_DEFF, LOCK_LEFF, LOCK_TASK = 25000, 0x75, 140, 168, 0x73
LOCK_SOUNDS = (0x29a, 0x29c, 0x29f)
LOCK_SPEECH, LOCK_SPEECH_AT = 0x297, 1.71
WIZARD_REQ = 0
MB_BALLS, SAVE_TICKS, GRACE_TICKS = 4, 625, 187
END_TICKS = 218

# kickout sounds and leffs (offset s, sound, leff), then the coil (observed: 82.19 s handler, 82.81 s coil 3)
KICK_ONE = ((0.0, 0x13b, 23), (0.243, 0x13b, None), (0.505, 0x13c, 24))
KICK_ONE_COIL = 0.61
# multiball release (megatron_decepticon.jsonl 35.86-37.19 s): per ball its media and coil offsets
RELEASE = (((0.0, 0x13b, 23), (0.016, 0x13c, 24), (0.017, 0x13d, 25)), ((0.242, 0x13b, None), (0.419, 0x13d, 25),
           (0.500, 0x13c, 24)), ((0.820, 0x13d, 25),), ((1.221, 0x13d, 25),))
RELEASE_COILS = (0.13, 0.61, 0.93, 1.33)
EJECT_OVER_TICKS = 66       # a kick's eject is over (the multiball end that waited for it: optimus_autobot.jsonl
                            # kick 72.45 s, end 73.53 s; inferred as the device's eject check)
RELEASE_AFTER_INTRO = 0.07
# deffs the package has no length for: (seconds, leffs, sounds) observed in traces/megatron_decepticon.jsonl
# (lengths inferred: the next effect comes several seconds later)
UNCAPTURED = {79: (3.0, (74,), ((0.0, 0xf9), (0.58, 0xfa), (1.57, 0xfb))), 139: (2.0, (167,), ((0.0, 0x293),))}


class Side:
    """Shared parts of the two multiballs."""
    flag = grace_flag = 0
    intro = intro_task = start_leff = bg = music = rule_leff = 0
    total_deff = total_leff = total_task = 0
    start_points = start_audit = 0

    def __init__(self, mgr):
        self.mgr = mgr
        self.os = mgr.os
        self.active = False         # flag set: the rules run
        self.alive = False          # until the total (the grace window)
        self.total = 0

    @property
    def pd(self):
        return self.os.pd

    def mult(self, shot):
        return self.os.shot_mult(shot)

    def start(self):
        os_ = self.os
        self.setup()
        os_.score_add(self.start_points)
        self.total = self.start_points
        os_.flag_set(self.flag)
        os_.flag_clear(self.grace_flag)
        self.active = self.alive = True
        os_.audit(self.start_audit)
        os_.hook("wizard_req", WIZARD_REQ, 1)
        # the intro replaces the lock's deff 140 at once (megatron_decepticon.jsonl 29.65 s: 4.2 s into it)
        os_.show(self.intro_task, self.intro, on_start=lambda: os_.deff_media(self.intro, self.start_leff),
                 threshold=os_.display.prio.get(self.intro, 0))
        os_.request_refresh()

    def setup(self):
        pass

    def award(self, points, deff, leff, sound, audit):
        os_ = self.os
        os_.score_add(points)
        self.total += points
        os_.deff_start(deff, values=[points])
        os_.audit(audit)
        os_.deff_media(deff, leff, sound)
        os_.request_refresh()

    def multiball_end(self):
        os_ = self.os
        if not self.active:
            return
        self.active = False
        os_.flag_clear(self.flag)
        os_.flag_set(self.grace_flag)
        os_.request_refresh()
        os_.task_start(self.total_task, END_TICKS, self._total)

    def _total(self):
        os_ = self.os
        self.alive = False
        os_.flag_clear(self.grace_flag)
        if os_.tilted or not os_.game or os_.state & 0x310:
            return
        os_.display.when_idle(self.total_task, self.total_deff, values=[self.total],
                              on_start=lambda: os_.deff_media(self.total_deff, self.total_leff))

    def add_ball(self):
        if self.alive and not self.active:
            self.os.task_kill(self.total_task)
            self.os.flag_set(self.flag)
            self.os.flag_clear(self.grace_flag)
            self.active = True
            self.os.request_refresh()

    def kill(self):
        os_ = self.os
        os_.task_kill(self.total_task)
        os_.flag_clear(self.flag)
        os_.flag_clear(self.grace_flag)
        self.active = self.alive = False


class Autobot(Side):
    flag, grace_flag = 0x25, 0x26
    intro, intro_task, start_leff, bg, music, rule_leff = 69, 0x74, 61, 70, 0x38, 62
    total_deff, total_leff, total_task = 74, 67, 0xbb
    start_points, start_audit = 250000, 0x76
    JP = (71, 64, 0xca, 0x77)
    DJ = (72, 65, 0xd2, 0x78)
    SUPER = (73, 66, 0xd9, 0x79)
    SUPER_LIT_LEFF = 63
    TIMEOUT_TASK, TIMEOUT_TICKS = 0xbd, 312
    PCT = (100, 100, 75, 50)

    def __init__(self, mgr):
        Side.__init__(self, mgr)
        self.phase, self.mask, self.m, self.supers, self.jp = 1, 0x40, 1, 0, 0

    def setup(self):
        pd = self.pd
        if self.os.adj[88]:
            phase = pd.get("mta_phase", 1)
            self.phase = 1 if phase == 2 else phase
            self.mask = pd.get("mta_mask", 0x40) if self.phase != 1 else 0x40
            self.jp = pd.get("mta_jp", 0)
        else:
            self.phase, self.mask, self.jp = 1, 0x40, 0
            pd.mt_since_super = 0
            pd.mt_sum = 0
        self.supers, self.m = 0, 1
        pd.mt_since_super = pd.get("mt_since_super", 0) + 1
        self.save()

    def save(self):
        pd = self.pd
        pd.mta_phase, pd.mta_mask, pd.mta_jp = self.phase, self.mask, self.jp

    def j(self):
        return min(100000 * (self.supers + 1) + 25000 * self.m, 500000)

    def shot(self, shot):
        if not self.active:
            return
        os_ = self.os
        pd = self.pd
        if shot == SHOT and self.phase == 1:
            points = self.j()
            self.award(points, *self.JP)
            pd.mt_sum = pd.get("mt_sum", 0) + points
            self.jp += 1
            self.m = min(self.m + 1, 6)
            self.phase, self.mask = 2, 0x3f
            os_.task_start(self.TIMEOUT_TASK, self.TIMEOUT_TICKS, self._timeout)
            if self.jp >= 10:
                self._super_lit()
        elif shot < 6 and self.phase == 2 and self.mask & (1 << shot):
            points = min(2 * self.j(), 1000000) * self.mult(shot)
            self.award(points, *self.DJ)
            pd.mt_sum = pd.get("mt_sum", 0) + points
            self.mask &= ~(1 << shot)
            self.jp += 1
            self.m = min(self.m + 1, 6)
            os_.task_start(self.TIMEOUT_TASK, self.TIMEOUT_TICKS, self._timeout)
            if self.jp >= 10 or not self.mask:
                self._super_lit()
        elif shot == SHOT and self.phase == 3:
            since = pd.get("mt_since_super", 0)
            points = max(1000000, pd.get("mt_sum", 0) * self.PCT[min(since, 3)] // 100)
            os_.score_add(points)
            self.total += points
            deff, leff, sound, audit = self.SUPER
            os_.deff_start(deff, values=[points])
            os_.hook("wizard_req", WIZARD_REQ, 2)
            os_.audit(audit)
            os_.deff_media(deff, leff, sound)
            self.supers += 1
            self.jp = 0
            pd.mt_sum = 0
            pd.mt_since_super = 0
            self.phase, self.mask = 1, 0x40
            os_.request_refresh()
        else:
            return
        self.save()

    def _super_lit(self):
        self.os.task_kill(self.TIMEOUT_TASK)
        self.phase, self.mask, self.m = 3, 0x40, 1
        self.os.leff_start(self.SUPER_LIT_LEFF)

    def _timeout(self):
        if self.active and self.phase == 2:
            self.phase, self.mask, self.m = 1, 0x40, 1
            self.save()
            self.os.request_refresh()

    def kill(self):
        Side.kill(self)
        self.os.task_kill(self.TIMEOUT_TASK)


class Decepticon(Side):
    flag, grace_flag = 0x29, 0x2a
    intro, intro_task, start_leff, bg, music, rule_leff = 75, 0x75, 69, 76, 0x3b, 70
    total_deff, total_leff, total_task = 80, 75, 0xbc
    start_points, start_audit = 100000, 0x7a
    JP = (77, 72, 0xe4, 0x7b)
    DJ = (78, 73, 0xf7, 0x7c)
    SUPER = (79, 74, 0xf9, 0x7d)
    SUPER_LIT_LEFF = 71
    CENTER = 3

    def __init__(self, mgr):
        Side.__init__(self, mgr)
        self.phase, self.mask, self.jp, self.dj, self.supers = 1, 0x7f, 0, 0, 0

    def setup(self):
        self.phase, self.mask, self.jp, self.dj, self.supers = 1, 0x7f, 0, 0, 0

    def shot(self, shot):
        if not self.active:
            return
        if self.phase == 1 and shot < 6 and self.mask & (1 << shot):
            self.award(min(100000 + 25000 * self.jp, 250000) * self.mult(shot), *self.JP)
            self.mask &= ~(1 << shot)
            self._jackpot()
        elif self.phase == 1 and shot == SHOT:
            self.award(100000, *self.JP)
            self.mask = 0x7f
            self._jackpot()
        elif self.phase == 2 and shot == self.CENTER:
            self.award(500000 * self.mult(self.CENTER), *self.DJ)
            self.dj += 1
            if self.dj >= 3:
                self.phase, self.mask = 3, 0x80
                self.os.leff_start(self.SUPER_LIT_LEFF)

    def _jackpot(self):
        self.jp += 1
        if self.jp >= 10:
            self.phase, self.mask, self.dj = 2, 0x08, 0

    def optimus(self):
        """Optimus (sw 51): the super jackpot in phase 3."""
        os_ = self.os
        if not self.active or self.phase != 3:
            return False
        points = 1000000 * self.mult(self.CENTER)
        os_.score_add(points)
        self.total += points
        deff, leff, sound, audit = self.SUPER
        os_.deff_start(deff, values=[points])
        os_.hook("wizard_req", WIZARD_REQ, 2)
        os_.audit(audit)
        os_.deff_media(deff, leff, sound)
        self.supers += 1
        self.phase, self.mask, self.jp = 1, 0x7f, 0
        os_.request_refresh()
        return True


class Megatron(Feature):
    name = "megatron"
    HOOKS = ("player_first_ball", "mb_shot", "sw_13", "sw_51", "lock_completion", "multiball_end", "add_ball",
             "ball_end", "tilt", "megatron_running", "lock_lit", "wizard_reset", "device_kicking")

    def __init__(self, os_):
        super().__init__(os_)
        self.sides = {AUTOBOT: Autobot(self), DECEPTICON: Decepticon(self)}
        self.back_door_at = -10.0
        for deff_id, (seconds, leffs, sounds) in UNCAPTURED.items():
            os_.display.set_media(deff_id, seconds, leffs, sounds)
        self.in_device = 0          # balls the device holds (locked or waiting for their handler / kickout)
        self.pending = 0            # entered balls not handled yet (still counted in play)
        self.locked_held = 0        # locked balls (not in play)
        self.kicking = 0            # balls waiting for their kick (_kick)
        sc = self.machine.switch_controller
        for name in SWITCHES:
            if name in self.machine.switches:
                sc.add_switch_handler(name, self._switch)
                sc.add_switch_handler(name, self._switch, state=0)
        for side in self.sides.values():
            os_.deff_rule((lambda s: lambda: s.active)(side), side.bg, music=side.music, priority=0x60)
            os_.lamp_rule((lambda s: lambda: s.active)(side), leff=side.rule_leff, order=0x0100cee0 + side.flag)
            # the rule leff flashes the lit shots (leff_062 / leff_070 [0x0100cf28 / 0x0100ee54])
            os_.lamps.leff_code(side.rule_leff,
                                shot_blink(SHOT_LAMPS[side.rule_leff], (lambda s: lambda: s.mask)(side)))
        self.machine.events.add_handler("tf_rules_refresh", self._keep_check)

    def player_first_ball(self):
        pd = self.pd
        pd.mtl_level = self.os.adj[68]
        self.derive()
        pd.mt_since_super = pd.mt_sum = 0
        pd.mta_phase, pd.mta_mask, pd.mta_jp = 1, 0x40, 0

    def wizard_reset(self):
        """[0x0100bd1c / 0x0100dcc0]: the saved multiball progress back to the start."""
        pd = self.pd
        pd.mta_phase, pd.mta_mask, pd.mta_jp = 1, 0x40, 0

    def derive(self):
        """[0x0100acb4]: the lock state from the level."""
        pd = self.pd
        level = pd.get("mtl_level", 0)
        need = 0 if level == 0 else 1 if level == 1 else min(level - 1, 5)
        pd.mtl_need = pd.mtl_count = need
        pd.mtl_lit = 4 if need == 0 else 0
        pd.mtl_locked = 0

    # ------------------------------------------------------------------ gates

    def running(self):
        return next((s for s in self.sides.values() if s.active), None)

    def megatron_running(self):
        return any(s.active for s in self.sides.values()) or None

    def blocked(self):
        """[0x0100ae6c / 0x0100b0b8]: a Megatron, Optimus, side mode or wizard multiball runs."""
        os_ = self.os
        return any(os_.flag(f) for f in (0x25, 0x29, 0x1f, 0x22, 0x3c, 0x3e))

    def lock_lit(self):
        return (bool(self.os.game) and self.pd.get("mtl_lit", 0) > 0 and not self.blocked()) or None

    # ------------------------------------------------------------------ lighting

    def lock_completion(self):
        """[0x0100af0c]: an Energon set completed."""
        os_ = self.os
        pd = self.pd
        if self.blocked() or pd.get("mtl_lit", 0) or pd.get("mtl_lit", 0) + pd.get("mtl_locked", 0) >= 4:
            return
        if pd.get("mtl_count", 0) > 1:
            pd.mtl_count -= 1
            os_.score_add(COUNT_POINTS)
            return
        if pd.get("mtl_level", 0) < 2:
            pd.mtl_lit = 4
        else:
            pd.mtl_lit = pd.get("mtl_lit", 0) + 1
            pd.mtl_count = pd.get("mtl_need", 1)
        os_.audit(LIGHT_AUDIT)
        os_.deff_start(LIGHT_DEFF)
        os_.leff_start(LIGHT_LEFF)
        os_.sound(LIGHT_SOUND)
        os_.score_add(LIGHT_POINTS)
        os_.request_refresh()

    # ------------------------------------------------------------------ the device

    def _count(self):
        return sum(1 for name in SWITCHES if name in self.machine.switches and self.machine.switches[name].state)

    def _switch(self):
        count = self._count()
        if count > self.in_device:
            for _ in range(count - self.in_device):
                self._entered()
        self.in_device = max(count, self.locked_held + self.pending)

    def _entered(self):
        os_ = self.os
        if not os_.game:
            self.machine.events.post(RELEASE_EVENT)
            return
        if os_.in_play:
            os_.playfield_switch(38)
        self.pending += 1
        back_door = os_.now - self.back_door_at < BACK_DOOR_S
        os_.after(SETTLE_TICKS, lambda: self._handle(back_door))

    def _keep_check(self, **kwargs):
        """[0x0100a1f8]: the device keeps no ball while a multiball (any_multiball_running 0x01006704) or the
        side mode (flag 0x3c) runs, so the locked balls go back into play; the lock count stays. Timed battles,
        double and fast scoring keep them. The kicks use the multiball release spacing (inferred)."""
        os_ = self.os
        if not self.locked_held or not os_.game or not (os_.any_multiball() or os_.flag(0x3c)):
            return
        held, self.locked_held = self.locked_held, 0
        os_.game.balls_in_play += held
        for i in range(held):
            os_.machine.clock.schedule_once(lambda: self.machine.events.post(RELEASE_EVENT),
                                            RELEASE_COILS[min(i, len(RELEASE_COILS) - 1)])

    def sw_13(self):
        self.back_door_at = self.os.now

    def _handle(self, back_door):
        """Lock entry handler [0x0100a31c]. The spec's wait on tasks 0x73-0x75 [list 0x040c61f8] is not modelled:
        the traces handle a lock while the previous lock's show runs (megatron_decepticon.jsonl 13.31 s)."""
        os_ = self.os
        self.pending = max(self.pending - 1, 0)
        if not os_.game:
            return
        keep = False
        if not back_door and os_.in_play and not os_.tilted:
            keep = self.rule()
        if not os_.tilted and os_.game:
            os_.base_score(ENTRY_POINTS)
        if keep == "multiball":
            return
        if keep:
            self.locked_held += 1
            os_.after(SERVE_TICKS, self._serve)
        else:
            self.kicking += 1
            self._kick()

    def device_kicking(self):
        return self.kicking > 0 or None

    def rule(self):
        """The shot-6 rules (multiballs first), else the lock [0x0100b130]."""
        os_ = self.os
        pd = self.pd
        if os_.hook("mb_shot_6"):
            return False
        side = self.running()
        if side:
            side.shot(SHOT)
            return False
        if self.blocked() or pd.get("mtl_lit", 0) <= 0:
            return False
        pd.mtl_lit -= 1
        if pd.get("mtl_locked", 0) + 1 < MB_BALLS:
            pd.mtl_locked = pd.get("mtl_locked", 0) + 1
            n = pd.mtl_locked
            os_.audit(LOCK_AUDIT)
            os_.score_add(LOCK_POINTS)
            # show task 0x73: it waits for the ball launch deff 41 (megatron_autobot.jsonl 10.71 s, 0.33 s on)
            os_.show(LOCK_TASK, LOCK_DEFF, values=[n], sounds=[
                (0, lambda: os_.sound(LOCK_SOUNDS[min(n, 3) - 1], in_deff=LOCK_DEFF)),
                (LOCK_SPEECH_AT, lambda: os_.sound(LOCK_SPEECH, in_deff=LOCK_DEFF))],
                on_start=lambda: os_.deff_media(LOCK_DEFF, LOCK_LEFF))
            os_.request_refresh()
            return True
        self.start_multiball()
        return "multiball"

    def start_multiball(self):
        os_ = self.os
        pd = self.pd
        in_play = max(os_.balls_in_play() - self.pending - 1 - (1 if os_.ball_held else 0), 0)
        balls = MB_BALLS if not in_play else in_play + 3
        # the locked balls and this one come back into play: MPF counts them again
        os_.game.balls_in_play += self.locked_held
        os_.multiball_start(balls, save_ticks=SAVE_TICKS, grace_ticks=GRACE_TICKS)
        side = self.sides[pd.get("side", DECEPTICON)]
        pd.mtl_level = pd.get("mtl_level", 0) + 1
        self.derive()
        side.start()
        held = self.locked_held + 1
        self.locked_held = 0
        intro = os_.display.media.get(side.intro)
        at = (intro.seconds if intro else 6.2) + RELEASE_AFTER_INTRO
        os_.machine.clock.schedule_once(lambda: self._release(held), at)

    def _release(self, balls):
        """The multiball release: each ball's sounds and leffs, then coil 3."""
        os_ = self.os
        for i in range(balls):
            steps = RELEASE[min(i, len(RELEASE) - 1)]
            for at, sound, leff in steps:
                self._media_at(at, sound, leff)
            os_.machine.clock.schedule_once(lambda: self.machine.events.post(RELEASE_EVENT),
                                            RELEASE_COILS[min(i, len(RELEASE_COILS) - 1)])

    def _media_at(self, at, sound, leff):
        os_ = self.os

        def run():
            if not os_.game:
                return
            os_.sound(sound)
            if leff is not None:
                os_.leff_start(leff)
        if at <= 0:
            run()
        else:
            os_.machine.clock.schedule_once(lambda: run(), at)

    def _kick(self):
        """The eject waits while deff 61 (the Optimus super) runs [list 0x040c6200] (optimus_autobot.jsonl: the
        super's ball stays 5.3 s)."""
        os_ = self.os
        if os_.game and os_.display.running(KICK_WAIT_DEFF):
            os_.after(POLL_TICKS, self._kick)
            return
        for at, sound, leff in KICK_ONE:
            self._media_at(at, sound, leff)
        os_.machine.clock.schedule_once(lambda: self._kicked(), KICK_ONE_COIL)

    def _kicked(self):
        self.machine.events.post(RELEASE_EVENT)
        self.kicking = max(self.kicking - 1, 0)
        if not self.kicking:
            self.os.after(EJECT_OVER_TICKS, self.os.device_ejected)

    def _serve(self):
        """AUTOFIRE AFTER LOCK (adj 89): a new ball from the trough, launched."""
        os_ = self.os
        if not os_.game or os_.tilted:
            return
        self.machine.playfield.add_ball(balls=1, player_controlled=False)

    # ------------------------------------------------------------------ shots

    def mb_shot(self, shot):
        side = self.running()
        if side:
            side.shot(shot)

    def sw_51(self):
        side = self.sides[DECEPTICON]
        if side.active and not self.os.tilted:
            side.optimus()

    def multiball_end(self):
        for side in self.sides.values():
            side.multiball_end()

    def add_ball(self):
        for side in self.sides.values():
            side.add_ball()

    def ball_end(self):
        for side in self.sides.values():
            if side.alive:
                side.kill()
        self.pending = 0

    tilt = ball_end


def feature(os_):
    return Megatron(os_)
