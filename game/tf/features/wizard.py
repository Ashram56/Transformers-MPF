"""Wizard requirements, All Hail Megatron / Autobots Roll Out (the side mode) and the Wizard Multiball
(rom/rules/modes/wizard_modes.md; code [0x01035af0] [0x01035ad0] [0x0100fff0] [0x01010174] [0x010363ec]
[0x010365c4] + observed in traces/wizard_all_hail_megatron.jsonl, wizard_multiball.jsonl).

Requirements (per player, hook wizard_req(r, what)): 0 Megatron multiball, 1-4 the Decepticon battles, 5 Optimus
multiball, 6-9 the Autobot battles, 10 the side mode; what 1 = collected (started, audit 0x81 + r), 2 = completed
(audit 0x8c + r). When the count of collected requirements reaches adj 83 (and flag 0x15 is clear) the extra ball
is lit.

The left eject (hook eject_modes, before its other rules) tries the wizard multiball's hit, the side mode's hit,
the side mode's start, the wizard multiball's start [0x0100a788]:
- Side mode: own side's five completed (Decepticon 0-4, Autobot 5-9), flag 0x3d clear, no multiball or timed
  mode. 1,000,000 x the Allspark multiplier, flags 0x3c / 0x3d, audit 0x7e, requirement 10 collected and
  completed, intro deff 81 (task 0x79, leff 78, sound 0x11a Decepticon / 0x119 Autobot), rule leff 79, background
  deff 82 + music 0x3c. Each main shot twice: (500,000 + 50,000 x shots made) x multiplier (deff 83, leff 81, sound
  0x11b, audit 0x7f); with all twelve made (leff 80) the Allspark scores the super = the shots' sum x multiplier
  (audit 0x80; deff 84, leff 82; total deff 85, leff 83) and the mode ends. A drain ends it with the total.
- Wizard multiball: all 11 completed, side mode not running. multiball_start(4 / in play + 3, save 937, grace
  312), flag 0x3e, wizard reset (requirements, battles, saved Megatron / Optimus progress), flag 0x3d cleared,
  audit 0x97, 1,000,000 x the Allspark multiplier, intro deff 86 (task 0x7c, leff 86), background deff 87 + music
  0x3d (rule leff 87). Each main shot three times: (500,000 + 50,000 x shots this round) x multiplier (deff 88, leff
  89, sound 0x131, audit 0x98); all eighteen made: the Allspark scores the SUPER WIZARD JACKPOT = the sum x
  multiplier (deff 89, audit 0x99) and the round starts over. Down to one ball: flag 0x3e off, 312 ticks of grace,
  then the total deff 90 (leff 91).
Wizard shot numbering: 0 Allspark, 1 left orbit, 2 left ramp, 3 center lane, 4 right orbit, 5 right ramp.
"""
from tf.display import deff_variant
from tf.features import Feature
from tf.lamps import hit_count_blink

ORDER = 37
AUTOBOT, DECEPTICON = 1, 2
REQS = 11
COLLECTED_AUDIT, COMPLETED_AUDIT = 0x81, 0x8c
EB_FLAG = 0x15
SIDE_FLAG, SIDE_PLAYED_FLAG, WMB_FLAG, ADD_BALL_FLAG = 0x3c, 0x3d, 0x3e, 0x14
SIDE_REQ = 10
# battle shot ids (tf/features/battles.py) -> wizard shot index
WIZ_SHOT = {0: 0, 1: 1, 2: 2, 3: 3, 4: 5, 5: 4}

SIDE_POINTS, SIDE_STEP, SIDE_HITS = 500000, 50000, 2
SIDE_START_AUDIT, SIDE_AWARD_AUDIT, SIDE_DONE_AUDIT = 0x7e, 0x7f, 0x80
SIDE_INTRO, SIDE_INTRO_TASK, SIDE_INTRO_LEFF = 81, 0x79, 78
SIDE_INTRO_SOUND = {DECEPTICON: 0x11a, AUTOBOT: 0x119}
SIDE_BG, SIDE_MUSIC, SIDE_RULE_LEFF, SIDE_LIT_LEFF = 82, 0x3c, 79, 80
SIDE_HIT_DEFF, SIDE_HIT_LEFF, SIDE_HIT_SOUND = 83, 81, 0x11b
SIDE_AFTER_SOUND = 0x119        # queued after the Autobot routines 6-11's speech [0x00025364]
SIDE_DONE_DEFF, SIDE_DONE_LEFF, SIDE_DONE_TASK = 84, 82, 0x7a       # task 0x7a [0x01010174] (QA M14)
SIDE_DONE_SOUNDS = {DECEPTICON: (0x128, 0x12a), AUTOBOT: (0x128, 0x12b)}
SIDE_TOTAL_DEFF, SIDE_TOTAL_LEFF = 85, 83
# mode_task_8f_7b_resume_10330 [0x01010330]: completed, task 0x7b plays deff 85 as a show (0x01010304); otherwise
# (event 0x1d, the end of ball) task 0x8f waits for the display (deff_sequence_wait_664c(0x55, 0x753) [0x010102f4])
SIDE_TOTAL_TASK, SIDE_TOTAL_WAIT_TASK, SIDE_TOTAL_WAIT = 0x7b, 0x8f, 0x753
# zuse_qualify_enabled [0x0100ff80] (rule leffs 77, 76 [0x01011ed4]): no multiball, no timed mode, flag 0x3d clear
# [0x0100ff58] and the side's five requirements done; the side only picks the range (0x01035db4: 0-4 Decepticon,
# 5-9 Autobot), so both sides (QA M8, wizard_modes.md 1)
QUALIFY_LEFFS = (77, 76)

WMB_POINTS, WMB_STEP, WMB_HITS = 500000, 50000, 3
WMB_BALLS, WMB_SAVE, WMB_GRACE = 4, 937, 312
WMB_START_AUDIT, WMB_AWARD_AUDIT, WMB_SUPER_AUDIT = 0x97, 0x98, 0x99
WMB_INTRO, WMB_INTRO_TASK, WMB_INTRO_LEFF = 86, 0x7c, 86
WMB_BG, WMB_MUSIC, WMB_RULE_LEFF = 87, 0x3d, 87
# per shot its inserts (lamp groups 0x37-0x3c side mode, 0x41-0x46 wizard multiball; tables 0x040c66e4 /
# 0x040c7ac8), the super's sweep (group 0x3d / 0x47)
SIDE_LAMPS = ((13, 14), (17, 18), (46, 45), (42, 41), (37, 38), (32, 33))
WMB_LAMPS = ((13, 14, 15), (17, 18, 19), (46, 45, 44), (42, 41, 40), (37, 38, 39), (32, 33, 34))
SUPER_SWEEP = (12, 13, 14, 15)
WMB_HIT_DEFF, WMB_HIT_LEFF, WMB_HIT_SOUND = 88, 89, 0x131
WMB_SUPER_DEFF = 89
WMB_TOTAL_DEFF, WMB_TOTAL_LEFF, WMB_TOTAL_TASK = 90, 91, 0x90
WMB_SUPER_LIT_LEFF = 88


REQ_LAMPS = (27, 7, 6, 5, 4, 22, 23, 24, 25, 26, 28)   # table 0x040c7a14 (stride 0x10), byte 0


class Wizard(Feature):
    name = "wizard"
    HOOKS = ("player_first_ball", "add_ball_open", "wizard_req", "eject_modes", "mb_shot", "wizard_shot", "multiball_end", "add_ball", "ball_end",
             "tilt", "side_mode_running")

    def __init__(self, os_):
        super().__init__(os_)
        self.side_running = False
        self.wmb_running = False        # flag 0x3e
        self.wmb_alive = False          # until the total (grace)
        self.side_total = self.side_sum = 0
        self.side_counts = [0] * 6
        self.wmb_total = self.wmb_sum = 0
        self.wmb_counts = [0] * 6
        os_.deff_rule(lambda: self.side_running, SIDE_BG, music=SIDE_MUSIC, priority=0x77)   # QA V-ENG5
        os_.deff_rule(lambda: self.wmb_running, WMB_BG, music=WMB_MUSIC, priority=0x75)   # QA V-ENG5
        # NEXT SHOT = 500,000 + 50,000 x shots made [0x01010100 / 0x01036534]; SUPER = the super's base
        # (RAM 0x34eac) [deff 82 0x010107e8, deff 87 0x01036d50]
        os_.deff_live((SIDE_BG,), lambda: {"values": [SIDE_POINTS + SIDE_STEP * sum(self.side_counts),
                                                      self.side_sum]})
        os_.deff_live((WMB_BG,), lambda: {"values": [WMB_POINTS + WMB_STEP * sum(self.wmb_counts)]})
        os_.lamp_rule(lambda: self.side_running, leff=SIDE_RULE_LEFF)
        # leff_079 / leff_087 [0x010109a0 / 0x01037060]: made hits solid, the rest flashing; the super's sweep
        os_.lamps.leff_code(SIDE_RULE_LEFF, hit_count_blink(
            SIDE_LAMPS, lambda: self.side_counts, self.side_super_lit, SUPER_SWEEP, sum(SIDE_LAMPS, ())))
        os_.lamps.leff_code(WMB_RULE_LEFF, hit_count_blink(
            WMB_LAMPS, lambda: self.wmb_counts, lambda: all(c >= WMB_HITS for c in self.wmb_counts), SUPER_SWEEP,
            sum(WMB_LAMPS, ())))
        os_.lamp_rule(lambda: self.side_running and self.side_super_lit(), leff=SIDE_LIT_LEFF)
        os_.lamp_rule(lambda: self.wmb_running, leff=WMB_RULE_LEFF)
        os_.lamp_rule(lambda: self.wmb_running and all(c >= WMB_HITS for c in self.wmb_counts), leff=WMB_SUPER_LIT_LEFF)
        for i, leff in enumerate(QUALIFY_LEFFS):
            os_.lamp_rule(lambda: bool(os_.game) and self.side_qualifies(),
                          leff=leff)
        os_.lamp_update(self.draw, priority=1)
        # leffs 84 and 85 while every requirement is completed, no multiball runs and flag 0x3c is clear: rule
        # items_all_collected_idle_363b4 [0x010363b4] (items_all_collected [0x01035d50]) (QA L-084, L-085)
        for i, leff in enumerate((84, 85)):
            os_.lamp_rule(lambda: bool(os_.game) and self.all_done() and not os_.any_multiball() and not os_.flag(0x3c),
                          leff=leff)
        for r in range(REQS):
            os_.register_poke(0x0211210c + 16 * r, self._poke_req(r), stride=4)
        os_.register_poke(0x34eb4, self._poke_side_count, players=6, stride=4)

    def _poke_req(self, r):
        def setter(p, v):
            players = self.os.players
            if p < len(players):
                req = players[p].get("wiz_req") or [[0, 0] for _ in range(REQS)]
                req[r] = [v & 0xff, (v >> 8) & 0xff]
                players[p]["wiz_req"] = req
            # an NVRAM poke requests no rules evaluation: the rule leffs change at the next request
            # (set_dat_000315fc [0x00017650], wizard_modes.md 1)
        return setter

    def _poke_side_count(self, i, v):
        self.side_counts[i] = v
        self.os.request_refresh()

    # ------------------------------------------------------------------ requirements

    def player_first_ball(self):
        self.pd.wiz_req = [[0, 0] for _ in range(REQS)]
        self.pd.wmb_count = 0

    def reqs(self):
        req = self.pd.get("wiz_req")
        if not req:
            req = self.pd.wiz_req = [[0, 0] for _ in range(REQS)]
        return req

    def wizard_req(self, r, what):
        """[0x01035af0(r, what)]."""
        os_ = self.os
        req = self.reqs()
        if what == 1:
            req[r][0] = min(req[r][0] + 1, 255)
            os_.audit(COLLECTED_AUDIT + r)
            started = sum(1 for x in req if x[0])
            if started == os_.adj[83] and not os_.flag(EB_FLAG):
                os_.flag_set(EB_FLAG)
                os_.light_extra_ball()
        else:
            req[r][1] = min(req[r][1] + 1, 255)
            os_.audit(COMPLETED_AUDIT + r)
        os_.request_refresh()

    def draw(self):
        """Lamp rule current_player_user_35ea8 [0x01035ea8] (registered with priority 1): the 11 requirement inserts
        (table 0x040c7a14, byte 0: 27 Megatron, 7 6 5 4 the Decepticon battles, 22 Optimus, 23 24 25 26 the Autobot
        battles, 28 Sentinel) are solid (0x00007858) once completed, flash (0x000077a0 + 0x00007814) once
        collected, else off (0x00007714) (QA L-R07)."""
        lamps = self.os.lamps
        for (collected, completed), lamp in zip(self.reqs(), REQ_LAMPS):
            if completed:
                lamps.lamp_on_solid(lamp)
            elif collected:
                lamps.lamp_flash(lamp)
            else:
                lamps.lamp_off_all(lamp)

    def reset(self):
        """Wizard reset [0x01035ad0]: requirements, battles, saved Megatron / Optimus progress."""
        pd = self.pd
        pd.wiz_req = [[0, 0] for _ in range(REQS)]
        self.os.hook("wizard_reset")

    def own_done(self):
        req = self.reqs()
        rs = range(0, 5) if self.pd.get("side", DECEPTICON) == DECEPTICON else range(5, 10)
        return all(req[r][1] for r in rs)

    def all_done(self):
        return all(r[1] for r in self.reqs())

    def quiet(self):
        """No multiball, no timed mode (battle timer, double / fast scoring)."""
        os_ = self.os
        return not os_.any_multiball() and not os_.timed_mode_running() and not os_.hook("battle_running")

    def side_qualifies(self):
        os_ = self.os
        return (not self.side_running and not os_.flag(SIDE_PLAYED_FLAG) and self.own_done() and self.quiet())

    def wmb_qualifies(self):
        return not self.side_running and not self.wmb_running and self.all_done() and self.quiet()

    def side_mode_running(self):
        return self.side_running or None

    def side_super_lit(self):
        return all(c >= SIDE_HITS for c in self.side_counts)

    def mult(self, shot):
        return self.os.shot_mult(shot)

    # ------------------------------------------------------------------ the left eject

    def eject_modes(self):
        """[0x0100a788]: the wizard modes' part of the Allspark rule."""
        os_ = self.os
        if os_.tilted or not os_.game:
            return
        if self.wmb_running or self.wmb_alive:     # flag or end task 0xc5 (gate [0x01036590]): QA M1
            if all(c >= WMB_HITS for c in self.wmb_counts):
                self.wmb_super()
            else:
                self.wmb_hit(0)
            return
        if self.side_running:
            if self.side_super_lit():
                self.side_super()
            else:
                self.side_hit(0)
            return
        if self.side_qualifies():
            self.side_start()
        elif self.wmb_qualifies():
            self.wmb_start()

    def mb_shot(self, shot):
        if shot == 0 or self.os.tilted:
            return                              # the Allspark: eject_modes
        if self.wmb_running or self.wmb_alive:
            self.wmb_hit(WIZ_SHOT[shot])
        elif self.side_running:
            self.side_hit(WIZ_SHOT[shot])

    def wizard_shot(self, i):
        """A wizard shot by its wizard index: the Megatron lock counts as shot 2 ([0x0100a31c] calls
        0x010365c4(2) and 0x01010174(2) before its own rules)."""
        if self.os.tilted:
            return
        if self.wmb_running or self.wmb_alive:
            self.wmb_hit(i)
        elif self.side_running:
            self.side_hit(i)

    # ------------------------------------------------------------------ side mode

    def side_start(self):
        """[0x0100fff0]."""
        os_ = self.os
        side = self.pd.get("side", DECEPTICON)
        self.side_counts = [0] * 6
        self.side_sum = 0
        points = 1000000 * self.mult(0)
        os_.score_add(points)
        self.side_total = points
        os_.flag_set(SIDE_FLAG)
        os_.flag_set(SIDE_PLAYED_FLAG)
        self.side_running = True
        os_.audit(SIDE_START_AUDIT)
        self.wizard_req(SIDE_REQ, 1)
        self.wizard_req(SIDE_REQ, 2)
        os_.hook("hint_set", 1)                     # hint_speech_set(1) [0x0100fff0] (QA SC4)
        sound = SIDE_INTRO_SOUND.get(side, 0x11a)
        os_.show(SIDE_INTRO_TASK, SIDE_INTRO, sounds=[(0, lambda: os_.sound(sound, in_deff=SIDE_INTRO))],
                 on_start=lambda: os_.deff_media(SIDE_INTRO, SIDE_INTRO_LEFF))
        os_.request_refresh()

    def side_hit(self, i):
        os_ = self.os
        if self.side_counts[i] >= SIDE_HITS:
            return
        made = sum(self.side_counts)
        points = (SIDE_POINTS + SIDE_STEP * made) * self.mult(i)
        self.side_counts[i] += 1
        os_.score_add(points)
        self.side_sum += points
        self.side_total += points
        # anim: the ROM's animation, the shot on its first hit, shot + 6 (the character's name) on the one
        # that completes it [0x01010174]; the PuP map reads it
        anim = i + 6 if self.side_counts[i] >= SIDE_HITS else i
        # deff_083_soundwave [0x01011750] runs routine +0x34 of table 0x040c6770 (Decepticon) / 0x040c67a0
        # (Autobot): its speech, 0x11c-0x121 / 0x11a and 0x122-0x127, at tick 63 through the task snd_play_delayed_6a9c
        # [0x01006a9c] or after the animation; Autobot routines 6-11 queue 0x119 after it (snd_play_after_wrap
        # [0x00025364], e.g. 0x01011530). Its length and sounds from the op list of that routine (QA SC10)
        side = self.pd.get("side", DECEPTICON)
        variant = "%s_anim%d" % ("autobot" if side == AUTOBOT else "decepticon", anim)
        info = deff_variant(SIDE_HIT_DEFF, variant)
        kwargs = {}
        if info:
            after = side == AUTOBOT and anim >= 6
            kwargs = {"variant": variant, "sounds": [(t, self._side_speech(c, after and c != SIDE_HIT_SOUND))
                                                     for t, c in info.sounds]}
        os_.deff_start(SIDE_HIT_DEFF, values=[points, i], anim=anim, **kwargs)
        os_.audit(SIDE_AWARD_AUDIT)
        os_.deff_media(SIDE_HIT_DEFF, SIDE_HIT_LEFF, SIDE_HIT_SOUND)
        os_.request_refresh()

    def _side_speech(self, call, then_119):
        os_ = self.os

        def play():
            end = os_.sound(call, in_deff=SIDE_HIT_DEFF)
            if then_119:
                if end is None or end <= os_.now:
                    os_.sound(SIDE_AFTER_SOUND)
                else:
                    os_.machine.clock.schedule_once(lambda dt=0: os_.sound(SIDE_AFTER_SOUND), end - os_.now)
        return play

    def side_super(self):
        os_ = self.os
        side = self.pd.get("side", DECEPTICON)
        points = self.side_sum * self.mult(0)
        os_.score_add(points)
        self.side_total += points
        os_.audit(SIDE_DONE_AUDIT)
        sounds = SIDE_DONE_SOUNDS.get(side, SIDE_DONE_SOUNDS[DECEPTICON])
        os_.show(SIDE_DONE_TASK, SIDE_DONE_DEFF, values=[points], sounds=[(0, (lambda c: lambda: os_.sound(c, in_deff=SIDE_DONE_DEFF))(c))
                                                         for c in sounds],
                 on_start=lambda: os_.deff_media(SIDE_DONE_DEFF, SIDE_DONE_LEFF))
        self.side_end(show_total="completed")

    def side_end(self, show_total):
        """[0x01010330]: the mode ends; its total follows (not when tilted)."""
        os_ = self.os
        if not self.side_running:
            return
        self.side_running = False
        os_.flag_clear(SIDE_FLAG)
        os_.request_refresh()
        total = self.side_total
        if show_total and not os_.tilted and total:          # none with no total (DAT_00034ecc == 0)
            media = (lambda: os_.deff_media(SIDE_TOTAL_DEFF, SIDE_TOTAL_LEFF))
            if show_total == "completed":
                os_.show(SIDE_TOTAL_TASK, SIDE_TOTAL_DEFF, values=[total], on_start=media)
            else:
                os_.display.when_idle(SIDE_TOTAL_WAIT_TASK, SIDE_TOTAL_DEFF, timeout=SIDE_TOTAL_WAIT, values=[total],
                                      on_start=media)

    # ------------------------------------------------------------------ wizard multiball

    def wmb_start(self):
        """[0x010363ec]."""
        os_ = self.os
        pd = self.pd
        in_play = max(os_.rom_balls_in_play(), 0)
        os_.multiball_start(WMB_BALLS if not in_play else in_play + 3, save_ticks=WMB_SAVE, grace_ticks=WMB_GRACE)
        if not os_.any_multiball():
            os_.flag_clear(ADD_BALL_FLAG)
        self.wmb_counts = [0] * 6
        self.wmb_sum = 0
        os_.flag_set(WMB_FLAG)
        self.wmb_running = self.wmb_alive = True
        pd.wmb_count = pd.get("wmb_count", 0) + 1
        self.reset()
        os_.flag_clear(SIDE_PLAYED_FLAG)
        os_.audit(WMB_START_AUDIT)
        points = 1000000 * self.mult(0)
        os_.score_add(points)
        self.wmb_total = points
        os_.show(WMB_INTRO_TASK, WMB_INTRO, on_start=lambda: os_.deff_media(WMB_INTRO, WMB_INTRO_LEFF))
        os_.request_refresh()

    def wmb_hit(self, i):
        os_ = self.os
        if self.wmb_counts[i] >= WMB_HITS:
            return
        made = sum(self.wmb_counts)
        points = (WMB_POINTS + WMB_STEP * made) * self.mult(i)
        self.wmb_counts[i] += 1
        os_.score_add(points)
        self.wmb_sum += points
        self.wmb_total += points
        os_.deff_start(WMB_HIT_DEFF, values=[points, i])
        os_.audit(WMB_AWARD_AUDIT)
        os_.deff_media(WMB_HIT_DEFF, WMB_HIT_LEFF, WMB_HIT_SOUND)
        os_.request_refresh()

    def wmb_super(self):
        os_ = self.os
        points = self.wmb_sum * self.mult(0)
        os_.score_add(points)
        self.wmb_total += points
        self.wmb_counts = [0] * 6
        self.wmb_sum = 0
        os_.audit(WMB_SUPER_AUDIT)
        os_.deff_start(WMB_SUPER_DEFF, values=[points])
        os_.request_refresh()

    def multiball_end(self):
        os_ = self.os
        if not self.wmb_running:
            return
        self.wmb_running = False
        os_.flag_clear(WMB_FLAG)
        os_.request_refresh()
        os_.task_start(WMB_TOTAL_TASK, WMB_GRACE, self._wmb_total)

    def _wmb_total(self):
        os_ = self.os
        self.wmb_alive = False
        if os_.tilted or not os_.game or os_.state & 0x310:
            return
        os_.display.when_idle(WMB_TOTAL_TASK, WMB_TOTAL_DEFF, values=[self.wmb_total],
                              on_start=lambda: os_.deff_media(WMB_TOTAL_DEFF, WMB_TOTAL_LEFF))

    def add_ball_open(self):
        """End task 0xc5 [0x01036590]: its whole 312-tick sleep [0x01036768] (QA M7; WMB_TOTAL_TASK here)."""
        return self.wmb_alive and not self.wmb_running and self.os.task_running(WMB_TOTAL_TASK)

    def add_ball(self):
        if self.wmb_alive and not self.wmb_running:
            self.os.task_kill(WMB_TOTAL_TASK)
            self.os.flag_set(WMB_FLAG)
            self.wmb_running = True
            self.os.request_refresh()

    def ball_end(self):
        self.side_end(show_total=not self.os.tilted)
        if self.wmb_running or self.wmb_alive:
            self.os.task_kill(WMB_TOTAL_TASK)
            self.os.flag_clear(WMB_FLAG)
            self.wmb_running = self.wmb_alive = False

    def tilt(self):
        self.side_end(show_total=False)
        self.ball_end()


def feature(os_):
    return Wizard(os_)
