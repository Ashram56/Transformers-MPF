"""The Megatron lock and the Megatron multiball, Autobot (A) and Decepticon (D) rules
(rom/rules/modes/megatron_multiball.md; code [0x0100a31c] [0x0100acb4] [0x0100af0c] [0x0100b130] [0x0100c200]
[0x0100c430] [0x0100e0bc] [0x0100e29c], confirmed by traces/megatron_autobot.jsonl, megatron_decepticon.jsonl).

Lock (per player): level = adj 68 at game start, +1 at each Megatron multiball; completions needed per lock:
level 0 -> 0 (all four lit at once), 1 -> 1, n -> min(n - 1, 5). An Energon set completion (hook
lock_completion, [0x0100af0c]) counts when no Megatron / Optimus / side mode / wizard multiball runs, no lock is lit
and lit + locked < 4: 5,000, or on the last one the lock is lit (level < 2: all four; else one, the counter re-armed;
the ROM's re-arm copies every player's counter, as here), audit 0x74, deff 139, leff 167, sound 0x293,
10,000.

Lock entry (switches 38-41, the ball device bd_megatron; its handler runs after device 4's +0x10 settle of
46 ticks, table 0x040d17fc; the traces show 0.75 s): the shot-6 rules of the running mode, else a lit lock: BALL n LOCKED (25,000, audit 0x75, deff 140,
leff 168, sound 0x29a / 0x29c / 0x29f); the 4th ball starts the multiball of the player's side. Then the handler's
5,120. A locked ball stays (ball hold hold_megatron) and a new ball is served once the lock and intro shows (tasks
0x73-0x75, list 0x040c61f8) are over, polled every 6 ticks (device 4 case 2 [0x0100a3b8]; adj 89 AUTOFIRE AFTER LOCK); any other ball is kicked out by device 4's callback
[0x0100a3b8]: 0x13b + leff 23, 0x13b at tick 15, 0x13c + leff 24 and coil 3 at tick 31. A ball within the back-door task (sw 13,
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
Not modelled: task 0x57. Adj 69 virtual lock: the device keeps no ball [0x0100a278]. The rule leff (62 / 70) flashes the lit shots from the side's mask.
"""

from tf.features import Feature
from tf.lamps import shot_blink
from tf.display import deff_variant
from tf.os_layer import TICK

# the display effects' random animation picks: their own generator, so the rules' picks stay as they were

ORDER = 38
AUTOBOT, DECEPTICON = 1, 2
SWITCHES = ("s_m_tron_lock_1_back", "s_megatron_lock_2", "s_megatron_lock_3", "s_megatron_lock_4")
# [0x0100a3b8 case 2], a ball entered in play (state & 0x316 == 0): while the jam switch 42 is closed or the count
# of the device's switches (list 0x000313ac: 42, 41, 40, 39, 38) differs from the first, up to 3 pulses of coil 3
# for 4 ms, 0x5d ticks apart
JAM_SWITCH, NUDGE_MS, NUDGE_TICKS, NUDGES = "s_megatron_jam", 4, 0x5d, 3
SWITCH_NUMS = (41, 40, 39, 38)
RELEASE_EVENT = "tf_megatron_release"
# shot tables {mask bit, lamp group} [0x040c63e4 A, 0x040c65dc D]: the orange arrows, Megatron, Optimus (D)
LOCK_LAMPS = (29, 57, 58)     # [0x0100b228]: 0x1d, 0x39, 0x3a
ARROWS = ((0x01, (15,)), (0x02, (19,)), (0x04, (44,)), (0x08, (40,)), (0x10, (34,)), (0x20, (39,)), (0x40, (29,)))
SHOT_LAMPS = {62: ARROWS, 70: ARROWS + ((0x80, (59,)),)}
SETTLE_TICKS = 46
EJECT_SETTLE_TICKS, RETRY_SLEEP_TICKS = 62, 31   # device record 0x040d188c +0x14 / +0x18 (ball_feed.md)
# device 4's case 2 [0x0100a3b8]: after the handler it waits, 6 ticks a try, while a task of list 0x040c61f8 runs
# (the lock and intro shows 0x73, 0x74, 0x75), then adj_megatron_m_b_virtual [0x0100a1f8] and the trough's serve
SERVE_WAIT_TASKS, SERVE_POLL_TICKS = (0x73, 0x74, 0x75), 6
ENTRY_POINTS = 5120
BACK_DOOR_S = 187 * 0.016
SHOT = 6
POLL_TICKS = 6
KICK_WAIT_DEFF = 61

LIGHT_POINTS, COUNT_POINTS = 10000, 5000
LIGHT_AUDIT, LIGHT_DEFF, LIGHT_LEFF, LIGHT_SOUND = 0x74, 139, 167, 0x293
LOCK_POINTS, LOCK_AUDIT, LOCK_DEFF, LOCK_LEFF, LOCK_TASK = 25000, 0x75, 140, 168, 0x73
LOCK_SOUNDS = (0x29a, 0x29c, 0x29f)
# the lock music [0x0100b7f0]: the side's per-player call (Autobot 0x294-0x296, Decepticon 0x297-0x299), set at the
# player's first ball [0x0100ab5c] and moved to the next at every Megatron multiball [0x0100ad70]
# (megatron_decepticon.jsonl: 0x297 at the first three locks, 0x298 after the multiball, 94.66 s)
LOCK_MUSIC = {AUTOBOT: (0x294, 0x297), DECEPTICON: (0x297, 0x29a)}   # first call, end of the cycle
LOCK_SPEECH_AT = 0x15 * 5 * 0.016     # deff_140_locked [0x0100b7f0]: 21 frames of deff_status_frames(5), 1 tick each
WIZARD_REQ = 0
MB_BALLS, SAVE_TICKS, GRACE_TICKS = 4, 625, 187
END_TICKS = 218
END_OFFER_TICKS = 0x9c     # the end task's first sleep before it renames itself [0x0100c7e8] (QA M7)

# device 4's callback run_leff_23_pulse_megatron_lockup_a3b8 [0x0100a3b8] (ticks, sound, leff): case 7 plays 0x13b +
# leff 23, again 0x13b at its 16th pass (tick 15), returns after 31 passes; the device loop [0x010391a0] then calls
# case 8 (nothing) and case 9: 0x13c + leff 24, falling into case 3: coil_pulse_now(3, 0x40) the same tick
KICK_ONE = ((0, 0x13b, 23), (15, 0x13b, None), (31, 0x13c, 24))
KICK_ONE_COIL = 31
# multiball release: the case 7 task as above beside case 4 -> 9 one tick later (0x13c + leff 24), then case 3 with
# task 0x57: per ball 0x13d + leff 25 and coil_pulse_now_wait(3, 64 ms) (64 // 16 + 1 = 5 ticks) + task_sleep(0x14):
# 25 ticks per ball
RELEASE_KICK = ((0, 0x13b, 23), (15, 0x13b, None), (31, 0x13c, 24))
RELEASE_FIRST, RELEASE_STEP = 1, 5 + 0x14
# a kick's eject is over: device 4's task 0x1c [0x01039db4] settles its count +0x14 = 62 ticks after the ball
# leaves, then runs the trough's case 0xe (the multiball end that waited) the tick after: optimus_autobot run as
# ROM code (scenario_lift): coil 3 at tick 4324, flag 0x1f cleared at 4387
EJECT_OVER_TICKS = 63


JACKPOT_DEFF, JACKPOT_RETRY_SOUND, JACKPOT_RETRY_TICKS = 77, 0x0f4, 0x2e     # [0x0100f3b4]
JACKPOT_SPEECH, JACKPOT_SPEECH_AFTER = 0x0f5, 0x0f6                         # [0x0100f360]


class Side:
    """Shared parts of the two multiballs."""
    flag = grace_flag = 0
    intro = intro_task = start_leff = bg = music = rule_leff = 0
    total_deff = total_leff = total_task = show_task = 0
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
        self.seq = 0            # the jackpot speech sample counter (DAT_00034db8 A / DAT_00034e2c D), 0 at the start
        self.active = self.alive = True
        os_.audit(self.start_audit)
        os_.hook("wizard_req", WIZARD_REQ, 1)
        # the intro replaces the lock's deff 140 at once (megatron_decepticon.jsonl 29.65 s: 4.2 s into it)
        os_.show(self.intro_task, self.intro, on_start=lambda: os_.deff_media(self.intro, self.start_leff),
                 threshold=os_.display.prio.get(self.intro, 0))
        os_.request_refresh()

    def setup(self):
        pass

    def sample(self, call, advance=True):
        """The deff's +0x34, the sample of its first speech call: the side's counter, 0 past the call's sample
        count (snd_call_sample_count), then + 1 (QA M12: [0x0100c430] 0xca / 0xd2, [0x0100e29c] 0xe4 / 0xf7)."""
        seq = getattr(self, "seq", 0)
        if seq >= len(self.os.sample_lengths(call)):
            seq = 0
        self.seq = seq + 1 if advance else seq
        return seq

    def award(self, points, deff, leff, sound, audit, anim=None, index=None):
        """anim: which of the deff's animations the ROM shows (the PuP map reads it); its length and sounds come
        from its op list, the frames are still the recorded animation's (docs/rom_differences.md). index: the
        sample of `sound` the deff plays (snd_play_arg_25250(sound, +0x34))."""
        os_ = self.os
        os_.score_add(points)
        self.total += points
        kwargs = {} if anim is None else {"anim": anim}
        if anim is not None and deff_variant(deff, "video%d" % anim):
            # the picked video's own length, sounds and leffs (op lists deff_066 / 071 / 072__videoN; QA V066-V072)
            kwargs["variant"] = "video%d" % anim
        os_.deff_start(deff, values=[points], **kwargs)
        os_.audit(audit)
        if index is None:
            os_.deff_media(deff, leff, sound)
        else:
            os_.display.own_sounds.add((deff, sound))       # its op lists carry it too: played here with its sample
            os_.deff_media(deff, leff, None)
            # once the deff's code runs: nothing if it is replaced at once (megatron_autobot.jsonl 81.07 s, deff 70)
            os_.machine.clock.schedule_once(lambda: os_.display.fg == deff and os_.sound(sound, in_deff=deff,
                                                                                           index=index), 0)
        if deff == JACKPOT_DEFF:
            self._jackpot_sounds(anim or 0)
        os_.request_refresh()

    def _jackpot_sounds(self, anim):
        """deff_077_jackpot [0x0100f3b4] (QA SC7): animation 0 retries 0x0f4 up to 0x2e ticks (task 0x95,
        leaf_6a20); another starts task_sleep_user_f360 [0x0100f360]: after 0x8c ticks (0x4d for animation 3)
        sample `anim` of 0x0f5 (0 past its count) and, for animation 3, 0x0f6 when it ends."""
        os_ = self.os
        os_.display.own_sounds.update({(JACKPOT_DEFF, JACKPOT_RETRY_SOUND), (JACKPOT_DEFF, JACKPOT_SPEECH),
                                       (JACKPOT_DEFF, JACKPOT_SPEECH_AFTER)})   # the video op lists carry them too
        if not anim:
            os_.after(1, lambda: os_.display.running(JACKPOT_DEFF)
                      and os_.sound_retry(JACKPOT_RETRY_SOUND, JACKPOT_RETRY_TICKS, in_deff=JACKPOT_DEFF))
            return
        index = min(anim, 9)
        if index >= len(os_.sample_lengths(JACKPOT_SPEECH)):
            index = 0

        def speak():
            end = os_.sound(JACKPOT_SPEECH, in_deff=JACKPOT_DEFF, index=index)
            if anim == 3 and end:
                os_.sound_chain(JACKPOT_SPEECH_AFTER, end)
        os_.after(0x4d if anim == 3 else 0x8c, speak)

    def multiball_end(self):
        os_ = self.os
        if not self.active:
            return
        self.active = False
        os_.flag_clear(self.flag)
        os_.request_refresh()
        os_.task_start(self.total_task, END_TICKS, self._total)

    def _total(self):
        os_ = self.os
        self.alive = False
        os_.flag_clear(self.grace_flag)
        if os_.tilted or not os_.game or os_.state & 0x310:
            return
        os_.display.when_idle(self.show_task, self.total_deff, values=[self.total],
                              on_start=lambda: os_.deff_media(self.total_deff, self.total_leff))

    def add_ball_open(self):
        """The end task under its first id: its first 156 of END_TICKS (QA M7)."""
        return self.alive and self.os.task_running(self.total_task) and \
            self.os.task_ticks_left(self.total_task) > END_TICKS - END_OFFER_TICKS

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
    # end task 0xbb [0x0100c7e8], its total shown by task 0x8b [0x0100c790] (QA M14)
    total_deff, total_leff, total_task, show_task = 74, 67, 0xbb, 0x8b
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
        if not (self.active or self.alive):   # the rules run while the flag is set or the end task runs
            return                             # (gates [0x0100be84] A / [0x0100dec0] D). QA 2026-11-25 M1
        os_ = self.os
        pd = self.pd
        if shot == SHOT and self.phase == 1:
            points = self.j()
            self.award(points, *self.JP, anim=self.os.random.randrange(5),   # deff 71: random_below(5) [0x0100d214]
                       index=self.sample(self.JP[2]))
            pd.mt_sum = pd.get("mt_sum", 0) + points
            self.jp += 1
            if self.jp < 10:
                self.seq = 0                                  # [0x0100c430]: back to 0 below 10 jackpots
            self.m = min(self.m + 1, 6)
            self.phase, self.mask = 2, 0x3f
            self._arm_timeout()
            if self.jp >= 10:
                self._super_lit()
        elif shot < 6 and self.phase == 2 and self.mask & (1 << shot):
            points = min(2 * self.j(), 1000000) * self.mult(shot)
            self.award(points, *self.DJ, anim=self.os.random.randrange(4),   # deff 72: random_below(4) [0x0100d550]
                       index=self.sample(self.DJ[2]))
            pd.mt_sum = pd.get("mt_sum", 0) + points
            self.mask &= ~(1 << shot)
            self.jp += 1
            self.m = min(self.m + 1, 6)
            self._arm_timeout()
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
        self.phase, self.mask, self.m = 3, 0x40, 1      # leff 63 runs by its lamp rule [0x0100d004]
        self.os.request_refresh()

    def _arm_timeout(self):
        """The double-jackpot timeout task [0x0100c10c] (restarted by [0x0100c164] at each award) first waits
        while M < 3, then 250 + 62 ticks: after the first jackpot (M = 2) the doubles do not time out.
        QA 2026-11-25 M3."""
        if self.m < 3:
            self.os.task_kill(self.TIMEOUT_TASK)
        else:
            self.os.task_start(self.TIMEOUT_TASK, self.TIMEOUT_TICKS, self._timeout)

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
    # end task 0xbf [0x0100e6a0], its total shown by task 0x8c [0x0100e61c] (QA M14)
    total_deff, total_leff, total_task, show_task = 80, 75, 0xbf, 0x8c
    start_points, start_audit = 100000, 0x7a
    JP = (77, 72, 0xe4, 0x7b)
    DJ = (78, 73, 0xf7, 0x7c)
    SUPER = (79, 74, 0xf9, 0x7d)
    SUPER_LIT_LEFF = 71
    CENTER = 3

    def __init__(self, mgr):
        Side.__init__(self, mgr)
        self.phase, self.mask, self.jp, self.dj, self.supers = 1, 0x7f, 0, 0, 0
        self.bag = 1

    def setup(self):
        """[0x0100e0bc]: adj 88 SAVE MEGATRON PROGRESS = YES restores the player's jackpot count, double count,
        lit mask and phase (0x02111e04 / e0c / df4 / de4, written at every award); NO resets them
        (FUN_0100dcc0). QA 2026-11-25 M2."""
        pd = self.pd
        if self.os.adj[88] == 1:
            self.jp, self.dj = pd.get("mtd_jp", 0), pd.get("mtd_dj", 0)
            self.mask, self.phase = pd.get("mtd_mask", 0x7f), pd.get("mtd_phase", 1)
        else:
            self.phase, self.mask, self.jp, self.dj = 1, 0x7f, 0, 0
            self.save()
        self.supers = 0
        self.bag = 1                # deff 77's animations drawn this multiball [0x0100e0bc]

    def save(self):
        pd = self.pd
        pd.mtd_jp, pd.mtd_dj, pd.mtd_mask, pd.mtd_phase = self.jp, self.dj, self.mask, self.phase

    def draw(self):
        """[0x0100ddc8]: deff 77's animation for a lit shot, 1-9 drawn without repeats from a random start
        (the scan wraps over 1-8, so 9 comes only as the start; a full bag starts again)."""
        if self.bag == 0x3ff:
            self.bag = 1
        start = i = self.os.random.randrange(9) + 1
        while True:
            if not self.bag & (1 << i):
                self.bag |= 1 << i
                return i
            i = 1 if i + 1 > 8 else i + 1
            if i == start:
                return i

    def shot(self, shot):
        if not (self.active or self.alive):   # the rules run while the flag is set or the end task runs
            return                             # (gates [0x0100be84] A / [0x0100dec0] D). QA 2026-11-25 M1
        if self.phase == 1 and shot < 6 and self.mask & (1 << shot):
            self.award(min(100000 + 25000 * self.jp, 250000) * self.mult(shot), *self.JP, anim=self.draw(),
                       index=self.sample(self.JP[2]))
            self.mask &= ~(1 << shot)
            self._jackpot()
        elif self.phase == 1 and shot == SHOT:
            self.seq = 0                                  # the Megatron shot: counter 0, not advanced [0x0100e29c]
            self.award(100000, *self.JP, anim=0, index=self.sample(self.JP[2], advance=False))   # deff 77 index 0
            self.mask = 0x7f
            self._jackpot()
        elif self.phase == 2 and shot == self.CENTER:
            self.award(500000 * self.mult(self.CENTER), *self.DJ, index=self.sample(self.DJ[2]))
            self.dj += 1
            if self.dj >= 3:
                self.seq = 0                                # [0x0100e29c]: the third double jackpot
                self.phase, self.mask = 3, 0x80             # leff 71 runs by its lamp rule [0x0100ef30]
                self.os.request_refresh()
        else:
            return
        self.save()

    def _jackpot(self):
        self.jp += 1
        if self.jp >= 10:
            self.seq = 0                                    # [0x0100e29c]: the tenth jackpot
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
        self.seq = 0                                        # the super jackpot [0x0100e29c]
        self.phase, self.mask, self.jp, self.dj = 1, 0x7f, 0, 0
        self.save()
        os_.request_refresh()
        return True


class Megatron(Feature):
    name = "megatron"
    HOOKS = ("player_first_ball", "add_ball_open", "mb_shot", "sw_13", "sw_51", "lock_completion", "multiball_end", "add_ball",
             "ball_end", "tilt", "megatron_running", "lock_lit", "wizard_reset", "device_kicking")

    def __init__(self, os_):
        super().__init__(os_)
        self.sides = {AUTOBOT: Autobot(self), DECEPTICON: Decepticon(self)}
        self.back_door_at = -10.0
        self.in_device = 0          # balls the device holds (locked or waiting for their handler / kickout)
        self.pending = 0            # entered balls not handled yet (still counted in play)
        self.locked_held = 0        # locked balls (not in play)
        self.kicking = 0            # balls waiting for their kick (_kick)
        self.excess = 0             # further balls the device loop kicks after the first [0x010391a0]
        sc = self.machine.switch_controller
        for name in SWITCHES:
            if name in self.machine.switches:
                sc.add_switch_handler(name, self._switch)
                sc.add_switch_handler(name, self._switch, state=0)
        for side in self.sides.values():
            os_.deff_rule((lambda s: lambda: s.active)(side), side.bg, music=side.music, priority=0x78)   # QA V-ENG5
            os_.lamp_rule((lambda s: lambda: s.active)(side), leff=side.rule_leff)
            # the rule leff flashes the lit shots (leff_062 / leff_070 [0x0100cf28 / 0x0100ee54])
            os_.lamps.leff_code(side.rule_leff,
                                shot_blink(SHOT_LAMPS[side.rule_leff], (lambda s: lambda: s.mask)(side)))
            # the super-lit flasher leff while phase 3: rules FUN_0100d004 / FUN_0100ef30 (QA M6; a phase 3
            # restored by adj 88 gets it too)
            os_.lamp_rule((lambda s: lambda: s.active and s.phase == 3)(side), leff=side.SUPER_LIT_LEFF)
        self.machine.events.add_handler("tf_rules_refresh", self._keep_check)
        os_.lamp_update(self.draw_lock)

    def draw_lock(self):
        """Lamp rule error_log_user_b228 [0x0100b228] (registered by [0x0100bc0c], list 4, mask 0x20): lamps 29, 57
        and 58 flash (0x000077a0 + 0x00007814) while a lock is lit and no multiball or mode blocks it
        (no_mode_and_flag_b0b8 [0x0100b0b8]: 0x02111d50[player]), else off (0x00007714) (QA L-R02)."""
        lamps = self.os.lamps
        lit = self.lock_lit()
        for lamp in LOCK_LAMPS:
            if lit:
                lamps.lamp_flash(lamp)
            else:
                lamps.lamp_off_all(lamp)

    def player_first_ball(self):
        pd = self.pd
        pd.mtl_level = self.os.adj[68]
        pd.mtl_music_a, pd.mtl_music_d = LOCK_MUSIC[AUTOBOT][0], LOCK_MUSIC[DECEPTICON][0]
        pd.mtl_played_a = pd.mtl_played_d = 0      # [0x0100ab5c]
        self.derive()
        pd.mt_since_super = pd.mt_sum = 0
        pd.mta_phase, pd.mta_mask, pd.mta_jp = 1, 0x40, 0
        pd.mtd_jp, pd.mtd_dj, pd.mtd_mask, pd.mtd_phase = 0, 0, 0x7f, 1

    def wizard_reset(self):
        """[0x0100bd1c / 0x0100dcc0]: the saved multiball progress back to the start."""
        pd = self.pd
        pd.mta_phase, pd.mta_mask, pd.mta_jp = 1, 0x40, 0
        pd.mtd_jp, pd.mtd_dj, pd.mtd_mask, pd.mtd_phase = 0, 0, 0x7f, 1

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
            # DAT_02111d4c = DAT_02111d48: the ROM's re-arm copies every player's count from their need (QA M10,
            # a ROM quirk kept)
            for player in os_.players:
                player.mtl_count = player.get("mtl_need", 1)
        os_.audit(LIGHT_AUDIT)
        os_.deff_start(LIGHT_DEFF, values=[pd.get("mtl_locked", 0)])     # +0x30 = the locked count (QA M15)
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
        if os_.in_play and not os_.tilted and self._jam():
            self._nudge(0, self._jam_count())
        back_door = os_.now - self.back_door_at < BACK_DOOR_S
        os_.after(SETTLE_TICKS, lambda: self._handle(back_door))

    def _jam(self):
        return JAM_SWITCH in self.machine.switches and bool(self.machine.switches[JAM_SWITCH].state)

    def _jam_count(self):
        return self._count() + int(self._jam())

    def _nudge(self, n, first):
        """[0x0100a3b8 case 2]: coil 3 for 4 ms while jammed or moving, at most 3 times, 0x5d ticks apart."""
        if n >= NUDGES or not (self._jam() or self._jam_count() != first) or not self.os.game:
            return
        coil = self.machine.coils.get("c_megatron_lockup") if hasattr(self.machine.coils, "get") else None
        if coil is not None:
            coil.pulse(NUDGE_MS)
        self.os.lamps.coil_log(3, NUDGE_MS)
        self.os.after(NUDGE_TICKS, lambda: self._nudge(n + 1, first))

    def _keep_check(self, **kwargs):
        """[0x0100a1f8]: the device keeps no ball while a multiball (any_multiball_running 0x01006704) or the
        side mode (flag 0x3c) runs, so the locked balls go back into play; the lock count stays. Timed battles,
        double and fast scoring keep them. game_device_3a2c0 [0x0103a2c0] lowers the device's target and starts
        its task 0x1c, the device loop [0x010391a0] of record 0x040d188c: the count settled (+0x10, 46 ticks),
        callback 7 (0x13b + leff 23, [0x0100a3b8] case 7) and the kick (case 9: 0x13c + leff 24, coil 3) as
        for any kickout (_kick); while more balls than the target stay, after the count settles again (+0x14,
        62 ticks) and task_sleep(+0x18, 31 ticks), callbacks 8 and 9 again (0x13c + leff 24, coil 3)."""
        os_ = self.os
        if not self.locked_held or not os_.game or not (os_.any_multiball() or os_.flag(0x3c)):
            return
        held, self.locked_held = self.locked_held, 0
        os_.game.balls_in_play += held
        self.kicking += held
        self.excess += held - 1
        os_.after(SETTLE_TICKS, self._kick)

    def _retry(self):
        """The device loop's next try [0x010391a0]: callback 9 ([0x0100a3b8] case 9, sound and leff unless the
        game state has 0x310), then case 3's coil 3."""
        os_ = self.os
        if os_.game and not os_.tilted:
            os_.sound(0x13c)
            os_.leff_start(24)
        self._kicked()

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
            os_.hook("wizard_shot", 2)              # [0x0100a31c]: the wizard modes' shot 2 first
            os_.hook("scoring_switch", None)        # FUN_010047b8 and FUN_01003a64 [0x0100a31c] (QA P10)
            keep = self.rule()
        if not os_.tilted and os_.game:
            os_.base_score(ENTRY_POINTS)
            # the inline copy of 0x01032d2c in [0x0100a31c]: FUN_01000dfc(1), the bonus count, and
            # FUN_00017d60, the ball search reset (QA F11)
            os_.hook("bonus_add")
            if not os_.task_running(0x2b):
                os_.ball_search_count = 0
        if keep == "multiball":
            return
        if keep and os_.adj[69] == 1:
            # adj 69 MEGATRON M.B. VIRTUAL LOCK = YES: the device's target count is 0 (adj_get(0x45) == 1
            # [0x0100a278]), so the locked ball is kicked back into play; the lock still counts (QA D-ADJ-69-use)
            keep = False
        if keep:
            self.locked_held += 1
            self._serve_wait()
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
                (LOCK_SPEECH_AT, lambda: self.lock_call(n))],
                on_start=lambda: os_.deff_media(LOCK_DEFF, LOCK_LEFF))
            os_.request_refresh()
            return True
        self.start_multiball()
        return "multiball"

    def lock_music(self):
        """The lock music call of the player's side [0x0100b7f0]; the PuP map reads mtl_music_d too."""
        pd = self.pd
        if pd.get("side", DECEPTICON) == AUTOBOT:
            return pd.get("mtl_music_a", LOCK_MUSIC[AUTOBOT][0])
        return pd.get("mtl_music_d", LOCK_MUSIC[DECEPTICON][0])

    def lock_call(self, n):
        """Deff 140 after its 21 frames [0x0100b7f0]: the side's call plays its samples in order, one per lock,
        while the per-player count (RAM 0x02111d78 Autobot, 0x02111d88 Decepticon; reset at [0x0100ab5c] and
        [0x0100ad70]) is below the call's sample count (snd_call_sample_count [0x00025924]); snd_play2
        [0x00025250] picks sample `count`, and the count moves on when it started. At the third lock the call's
        last sample follows when that one ends (snd_play_after [0x00025284])."""
        os_ = self.os
        pd = self.pd
        call = self.lock_music()
        key = "mtl_played_a" if pd.get("side", DECEPTICON) == AUTOBOT else "mtl_played_d"
        played = pd.get(key, 0)
        count = len(os_.sample_lengths(call))
        if played >= count:
            return
        end = os_.sound(call, in_deff=LOCK_DEFF, index=played)
        if end is None:
            return
        pd[key] = played + 1
        if n == 3:
            os_.machine.clock.schedule_once(lambda: os_.sound(call, index=count - 1), max(end - os_.now, 0))

    def next_lock_music(self):
        """[0x0100ad70]: both sides' calls move to the next of their three, at every Megatron multiball."""
        pd = self.pd
        for key, side in (("mtl_music_a", AUTOBOT), ("mtl_music_d", DECEPTICON)):
            first, end = LOCK_MUSIC[side]
            call = pd.get(key, first) + 1
            pd[key] = call if call < end else first
        pd.mtl_played_a = pd.mtl_played_d = 0      # [0x0100ad70]

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
        self.next_lock_music()
        self.derive()
        side.start()
        held = self.locked_held + 1
        self.locked_held = 0
        # game_device_3a2c0(4, 0) [0x0100c200 caller]: the device releases its balls once its case 7 wait is over (the
        # intro show task 0x74 / 0x75 that the multiball start just created)
        os_.after(1, lambda: self._release_wait(held))

    def _release_wait(self, balls):
        if self._device_busy():
            self.os.after(POLL_TICKS, lambda: self._release_wait(balls))
            return
        self._release(balls)

    def _release(self, balls):
        """The multiball release: each ball's sounds and leffs, then coil 3."""
        os_ = self.os
        for at, sound, leff in RELEASE_KICK:
            self._media_at(at, sound, leff)
        for i in range(balls):
            at = RELEASE_FIRST + RELEASE_STEP * i
            self._media_at(at, ((0x13c, 24),) * (i == 0) + ((0x13d, 25),))     # case 9 then case 3, one task
            os_.machine.clock.schedule_once(lambda: self.machine.events.post(RELEASE_EVENT), at * TICK)

    def _media_at(self, at, sound, leff=None):
        """At tick `at`: sound + leff, or sound = ((sound, leff), ...) in that order."""
        os_ = self.os
        steps = sound if isinstance(sound, tuple) else ((sound, leff),)

        def run():
            if not os_.game:
                return
            for call, lf in steps:
                os_.sound(call)
                if lf is not None:
                    os_.leff_start(lf)
        if at <= 0:
            run()
        else:
            os_.machine.clock.schedule_once(lambda: run(), at * TICK)

    def _device_busy(self):
        """Device 4's case 7 [0x0100a3b8] waits, 6 ticks a try, while a task of list 0x040c61f8 (0x73-0x75, the lock
        and intro shows) or a deff of list 0x040c6200 (deff 61, the Optimus super) runs."""
        os_ = self.os
        return os_.game and (os_.display.running(KICK_WAIT_DEFF) or
                             any(os_.task_running(t) or os_.display.task_running(t) for t in SERVE_WAIT_TASKS))

    def _kick(self):
        """The eject waits while the device is busy (optimus_autobot.jsonl: the super's ball stays 5.3 s)."""
        os_ = self.os
        if self._device_busy():
            os_.after(POLL_TICKS, self._kick)
            return
        for at, sound, leff in KICK_ONE:
            self._media_at(at, sound, leff)
        os_.machine.clock.schedule_once(lambda: self._kicked(), KICK_ONE_COIL * TICK)

    def _kicked(self):
        self.machine.events.post(RELEASE_EVENT)
        self.kicking = max(self.kicking - 1, 0)
        if self.excess:
            self.excess -= 1
            self.os.after(EJECT_SETTLE_TICKS + RETRY_SLEEP_TICKS, self._retry)
            return
        if not self.kicking:
            self.os.after(EJECT_OVER_TICKS, self.os.device_ejected)

    def _serve_wait(self):
        os_ = self.os
        if any(os_.task_running(t) or os_.display.task_running(t) for t in SERVE_WAIT_TASKS):
            os_.after(SERVE_POLL_TICKS, self._serve_wait)
            return
        # the serve task [0x0103b128]: the trough's settle, then its kick through the coil queue (trough_callback
        # case 9 [0x0100a0a4], coil_pulse_queue_wait), as a later ball start (tf/os_layer.py)
        from tf.os_layer import SERVE_EJECT_TICKS, LATER_SERVE_EXTRA_TICKS     # noqa: PLC0415
        os_.after(SERVE_EJECT_TICKS + LATER_SERVE_EXTRA_TICKS, self._serve)

    def _serve(self):
        """AUTOFIRE AFTER LOCK (adj 89): a new ball from the trough, auto-launched only when adj 89 = 1
        ([0x0100a074] adj_get(0x59) == 1; else the player plunges it) (QA D-ADJ-89)."""
        os_ = self.os
        if not os_.game or os_.tilted:
            return
        self.machine.playfield.add_ball(balls=1, player_controlled=os_.adj[89] != 1)

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

    def add_ball_open(self):
        return any(side.add_ball_open() for side in self.sides.values())

    def ball_end(self):
        for side in self.sides.values():
            if side.alive:
                side.kill()
        self.pending = 0

    tilt = ball_end


def feature(os_):
    return Megatron(os_)
