"""The center lane's Optimus access, the Optimus Prime battle and the Optimus multiball, Autobot (A) and
Decepticon (D) rules (rom/rules/modes/optimus_multiball.md; code [0x01025de4] [0x0102628c] [0x010262f0]
[0x01027994] [0x01027b74] [0x01029a08] [0x01029bf4], confirmed by traces/optimus_autobot.jsonl,
optimus_decepticon.jsonl).

Access (center lane sw 11, after the battles' shot and before the combo): blocked while a Megatron, Optimus, side
mode or wizard multiball runs or the battle runs: 1,000, leff 169, sound 0x2a1. Else hits 1-3: 2,500, flag 0x48,
deff 141 "n MORE TO ACCESS OPTIMUS", leff 170, sound 0x2a3; hit 4 starts the battle: flag 0x46, Optimus hits
left = 2L + 1 (L = adj 67 at game start, + 1 per battle won, max 8), audit 0x6b, 200,000, deff 142 (leff 174,
sound 0x2ab), music 0x34 (D) / 0x31 (A) and rule leffs 20, 176, 175 while it can progress.
Battle (Optimus target sw 51, 5 ticks after the switch; ignored for 1 s after a hit, task 0x54): deff 144 with
n = left + 1, leff 178, sound 0x2aa (leff 177 when none is left); the last hit 2,000,000, level + 1, the side's
multiball with the center lane's multiplier.
Multiball: multiball_start(3 if no ball is in play else in play + 2, save 625, grace 187); adj 87 restores the
saved phase / remaining / lit shots, NO resets them (and the super base); 250,000 x the center multiplier; flag 0x14
cleared (no other multiball); flag 0x1f (A) / 0x22 (D), 0x49; audit 0x6c / 0x70; wizard requirement 5 collected; the
intro (A deff 57 + leff 45, D deff 63 + leff 53) by show task 0x71 / 0x72 once the display is free, then
the background (A deff 58 + music 0x32 + leff 46, D deff 64 + music 0x35 + leff 54).
J = min(150,000 + 100,000 x supers, 500,000), DJ = min(2 J, 1,000,000), both x the shot's multiplier; super =
max(1,000,000, [100, 100, 75, 50]% (by the multiballs since the last super) of the jackpots since then).
A: a lit shot J (deff 59, leff 48, sound 0x7f, audit 0x6d) and only it stays lit; again DJ (deff 60, leff 49, sound
0x84, audit 0x6e), removed; none left: the super at the Megatron lock (hook mb_shot_6; leff 47; deff 61, leff 50,
audit 0x6f).
D: a lit shot J (deff 65, leff 56, sound 0xa5, audit 0x71), removed, Optimus lit; Optimus DJ (deff 66, leff 57,
sound 0xaa, audit 0x72); the center lane in that phase scores J again (the ROM's quirk); none left: the super at
Optimus (leff 55; deff 67, leff 58, sound 0xab, audit 0x73). A super: requirement 5 completed, all shots relit.
End: down to one ball the running flag goes, 218 ticks later the total (A deff 62 + leff 51, D deff 68 + leff 59).
The figure's motor and hit kicker are tf/features/optimus_mech.py. Not modelled: the chained speech of deff 144.
"""
import random

from tf.features import Feature
from tf.lamps import shot_blink
from tf.display import deff_variant

# the display effects' random animation picks: their own generator, so the rules' picks stay as they were
VARIANTS = random.Random()

ORDER = 41
AUTOBOT, DECEPTICON = 1, 2
CENTER = 3
TICK = 0.016

HINT_FRAME_TICKS = 30      # deff 141 [0x01025f18]: hint_speech_start at frame 10, 3 ticks a frame
ACCESS_POINTS, ACCESS_FLAG, ACCESS_DEFF, ACCESS_LEFF, ACCESS_SOUND = 2500, 0x48, 141, 170, 0x2a3
BLOCKED_POINTS, BLOCKED_LEFF, BLOCKED_SOUND = 1000, 169, 0x2a1
NEEDED = 4

BATTLE_FLAG, BATTLE_AUDIT, BATTLE_POINTS = 0x46, 0x6b, 200000
BATTLE_DEFF, BATTLE_LEFF, BATTLE_SOUND = 142, 174, 0x2ab
BATTLE_MUSIC = {DECEPTICON: 0x34, AUTOBOT: 0x31}
BATTLE_RULE_LEFFS = (20, 176, 175)
# leff_020 [0x01006f1c]: the GI beat of the battle music, table 0x040c5edc (call, ticks since the music started)
MUSIC_BEATS = ((0x31, (36, 43, 50, 219, 261, 268, 275, 445, 487, 494, 501, 557, 614, 670, 712, 720, 727, 783, 811,
                       839, 868, 896, 938, 945, 952, 980, 1009, 1023, 1037, 1051, 1065, 1079, 1093, 1107, 10000)),
               (0x34, (21, 35, 105, 132, 146, 216, 244, 258, 285, 299, 327, 549, 605, 661, 716, 772, 786, 800, 813,
                       841, 855, 869, 883, 911, 925, 938, 966, 980, 994, 1008, 1022, 1036, 1077, 1091, 1105, 1119,
                       1161, 1175, 1189, 1203, 10000)))
BATTLE_DONE_LEFF = 177
HIT_DEFF, HIT_LEFF, HIT_SOUND = 144, 178, 0x2aa
MAX_LEFT = 8
START_AWARD = 2000000

MB_BALLS, SAVE_TICKS, GRACE_TICKS = 3, 625, 187
MB_FLAG, ADD_BALL_FLAG = 0x49, 0x14
WIZARD_REQ = 5
END_TICKS = 218
END_OFFER_TICKS = 0x9c     # the end task's first sleep before it renames itself [0x0100c7e8] (QA M7)
PCT = (100, 100, 75, 50)
ALL = 0x3f
# shot tables {mask bit, lamp group} [0x040c729c A, 0x040c7400 D]: the orange arrows, then the lock (A) / Optimus (D)
ARROWS = ((0x01, (15,)), (0x02, (19,)), (0x04, (44,)), (0x08, (40,)), (0x10, (34,)), (0x20, (39,)))
SHOT_LAMPS = {46: ARROWS + ((0x40, (29,)),), 54: ARROWS + ((0x40, (59,)),)}
OPTIMUS_BIT = 0x40


class Side:
    """Shared parts of the two Optimus multiballs."""
    key = ""
    flag = intro = intro_leff = intro_task = bg = music = rule_leff = super_leff = 0
    start_audit = total_deff = total_leff = total_task = 0
    JP = DJ = SUPER = ()

    def __init__(self, mgr):
        self.mgr = mgr
        self.os = mgr.os
        self.active = False         # flag set: the rules run
        self.shown = False          # the intro has started: the background rule runs
        self.alive = False          # until the total (the grace window)
        self.total = 0
        self.phase, self.remaining, self.lit = 1, ALL, ALL

    @property
    def pd(self):
        return self.os.pd

    def get(self, name, default=0):
        return self.pd.get(self.key + name, default)

    def put(self, name, value):
        self.pd[self.key + name] = value

    def reset(self):
        """[0x01027510 / 0x01029558]: the saved progress back to the start."""
        self.put("phase", 1)
        self.put("remaining", ALL)
        self.put("lit", ALL)

    def save(self):
        self.put("phase", self.phase)
        self.put("remaining", self.remaining)
        self.put("lit", self.lit)

    def mult(self, shot):
        return self.os.shot_mult(shot)

    def j(self):
        return min(150000 + 100000 * self.get("supers"), 500000)

    def dj(self):
        return min(2 * self.j(), 1000000)

    def start(self, mult):
        os_ = self.os
        if os_.adj[87]:
            self.phase, self.remaining, self.lit = self.get("phase", 1), self.get("remaining", ALL), self.get("lit", ALL)
        else:
            self.phase, self.remaining, self.lit = 1, ALL, ALL
            self.put("since", 0)
            self.put("sum", 0)
        self.save()
        points = 250000 * mult
        os_.score_add(points)
        self.total = points
        if not os_.any_multiball():               # tested before this side's flag is set [0x01027994]
            os_.flag_clear(ADD_BALL_FLAG)
        os_.flag_set(self.flag)
        os_.flag_set(MB_FLAG)
        self.active = self.alive = True
        self.seq = 0            # deff 59's speech sample counter DAT_00035308, 0 at the start [0x01027994]
        self.shown = False
        self.put("since", self.get("since") + 1)
        os_.audit(self.start_audit)
        os_.hook("wizard_req", WIZARD_REQ, 1)
        self._intro()

    def _intro(self):
        os_ = self.os
        if not self.active:
            return

        def started():
            self.shown = True
            os_.deff_media(self.intro, self.intro_leff)
            os_.request_refresh()
        # task 0x71 / 0x72 created at the multiball start [0x01027994] [0x01029a08]: deff_sequence_flippers_6480
        # [0x01006480](57 / 63, 0xea6, 0x9f): waits while the deff priority is 0x9f or more (deff 144 0xa2 until
        # its hold tail) and an older show task waits, at most 0xea6 ticks
        os_.show(self.intro_task, self.intro, on_start=started)

    def award(self, points, media, anim=None, index=None):
        """anim: which of the deff's animations the ROM shows (the PuP map reads it); its length and sounds come
        from its op list, the frames are still the recorded animation's (docs/rom_differences.md). index: the
        sample of `sound` the deff plays (snd_play_arg_25250(sound, +0x34), QA M12)."""
        os_ = self.os
        deff, leff, sound, audit = media
        os_.score_add(points)
        self.total += points
        kwargs = {} if anim is None else {"anim": anim}
        if anim is not None and deff_variant(deff, "video%d" % anim):
            # the picked animation's own length, sounds and leffs (deff_NNN__videoK, rom/rom_data/dmd/deff_anim_tables.csv;
            # QA V066-V072, SC6: deffs 59, 60, 65, 77); index 0 is the base op list
            kwargs["variant"] = "video%d" % anim
        os_.deff_start(deff, values=[points], **kwargs)
        os_.audit(audit)
        if index is None:
            os_.deff_media(deff, leff, sound)
            return
        os_.display.own_sounds.add((deff, sound))           # its op lists carry it too: played here with its sample
        os_.deff_media(deff, leff, None)
        os_.machine.clock.schedule_once(lambda: os_.display.fg == deff and os_.sound(sound, in_deff=deff,
                                                                                       index=index), 0)

    def jackpot_index(self):
        """The jackpot deff's +0x34: deff 65 leaves it 0 (task_create clears the block; [0x01029bf4] sets none)."""
        return 0

    def jackpot(self, shot):
        points = self.j() * self.mult(shot)
        self.award(points, self.JP, self.jackpot_anim(shot), index=self.jackpot_index())
        self.put("sum", self.get("sum") + points)

    def double(self, shot):
        points = self.dj() * self.mult(shot)
        self.award(points, self.DJ, self.double_anim(shot))
        self.put("sum", self.get("sum") + points)

    def jackpot_anim(self, shot):
        return None

    def double_anim(self, shot):
        return None

    def super(self, mult=1):
        os_ = self.os
        points = max(1000000, self.get("sum") * PCT[min(self.get("since"), 3)] // 100) * mult
        self.award(points, self.SUPER)
        self.seq = 0                                        # the super [0x01027b74]
        os_.hook("wizard_req", WIZARD_REQ, 2)
        self.put("supers", self.get("supers") + 1)
        self.put("sum", 0)
        self.put("since", 0)
        self.phase, self.remaining, self.lit = 1, ALL, ALL

    def after_double(self):
        """Shots left: back to the jackpots; none: the super is lit."""
        if self.remaining:
            self.phase, self.lit = 1, self.remaining
        else:
            self.phase, self.lit = 3, OPTIMUS_BIT
        self.save()
        self.os.request_refresh()

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
        if os_.tilted or not os_.game or os_.state & 0x310:
            return
        os_.display.when_idle(self.total_task, self.total_deff, values=[self.total],
                              on_start=lambda: os_.deff_media(self.total_deff, self.total_leff))

    def add_ball_open(self):
        """The end task under its first id: its first 156 of END_TICKS (QA M7)."""
        return self.alive and self.os.task_running(self.total_task) and \
            self.os.task_ticks_left(self.total_task) > END_TICKS - END_OFFER_TICKS

    def add_ball(self):
        if self.alive and not self.active:
            self.os.task_kill(self.total_task)
            self.os.flag_set(self.flag)
            self.active = True
            self.os.request_refresh()

    def kill(self):
        os_ = self.os
        os_.task_kill(self.total_task)
        os_.flag_clear(self.flag)
        self.active = self.alive = self.shown = False


class Autobot(Side):
    key = "opa_"
    flag, intro, intro_leff, intro_task = 0x1f, 57, 45, 0x71
    bg, music, rule_leff, super_leff = 58, 0x32, 46, 47
    start_audit, total_deff, total_leff, total_task = 0x6c, 62, 51, 0x89
    JP = (59, 48, 0x7f, 0x6d)

    def jackpot_index(self):
        """Deff 59's +0x34 [0x01027b74]: the counter, 0 past 0x7f's sample count, then + 1."""
        seq = getattr(self, "seq", 0)
        if seq >= len(self.os.sample_lengths(self.JP[2])):
            seq = 0
        self.seq = seq + 1
        return seq
    DJ = (60, 49, 0x84, 0x6e)
    SUPER = (61, 50, 0x8f, 0x6f)

    def jackpot_anim(self, shot):
        return shot        # deff 59: one enemy per shot, table 0x040c732c[shot] [0x01028950], shot from [0x01027b74]

    def double_anim(self, shot):
        return shot        # deff 60: table 0x040c7344[shot] [0x01028da0]

    def shot(self, shot):
        """[0x01027b74]: shots 0-5, 6 the Megatron lock. The rules run while the flag is set or the end task
        runs (gate [0x010276e0]). QA 2026-11-25 M1."""
        if not (self.active or self.alive):
            return False
        bit = 1 << shot
        if self.phase == 1 and shot < 6 and self.lit & bit:
            self.jackpot(shot)
            self.phase, self.lit = 2, bit
        elif self.phase == 2 and shot < 6 and self.lit & bit:
            self.double(shot)
            self.remaining &= ~bit
            self.after_double()
            return True
        elif self.phase == 3 and shot == 6:
            self.super()
        else:
            return False
        self.save()
        self.os.request_refresh()
        return True


class Decepticon(Side):
    key = "opd_"
    flag, intro, intro_leff, intro_task = 0x22, 63, 53, 0x72   # task 0x72 [0x01029a08] (QA M14)
    bg, music, rule_leff, super_leff = 64, 0x35, 54, 55
    start_audit, total_deff, total_leff, total_task = 0x70, 68, 59, 0x8a
    JP = (65, 56, 0xa5, 0x71)
    DJ = (66, 57, 0xaa, 0x72)
    SUPER = (67, 58, 0xab, 0x73)

    def jackpot_anim(self, shot):
        return 0           # deff 65 indexes its table by task+0x38, which no caller sets [0x0102aa70]

    def double_anim(self, shot):
        return VARIANTS.randrange(3)   # deff 66: random_below(3), table 0x040c749c [0x0102ad30]

    def shot(self, shot):
        """[0x01029bf4]: shots 0-5 (the center lane from sw 11 only); flag or end task (gate [0x01029754])."""
        if not (self.active or self.alive) or shot >= 6:
            return False
        bit = 1 << shot
        if self.phase == 1 and self.lit & bit:
            self.jackpot(shot)
            self.remaining &= ~bit
            self.phase, self.lit = 2, OPTIMUS_BIT
        elif self.phase == 2 and shot == CENTER:
            self.jackpot(shot)                  # the quirk: no state change (caller 0x01029e14)
        else:
            return False
        self.save()
        self.os.request_refresh()
        return True

    def optimus(self):
        """The Optimus target (sw 51): the double, or the super in phase 3 (x the center lane's multiplier,
        table 0x040c7400 row 6 slot 4, [0x01029bf4]: QA 2026-11-25 M4)."""
        if not (self.active or self.alive):
            return False
        if self.phase == 2:
            self.double(CENTER)
            self.after_double()
        elif self.phase == 3:
            self.super(self.mult(CENTER))
            self.save()
            self.os.request_refresh()
        else:
            return False
        return True


class Optimus(Feature):
    name = "optimus"
    HOOKS = ("player_first_ball", "add_ball_open", "ball_start", "base_music", "sw_11", "sw_51", "mb_shot", "mb_shot_6",
             "multiball_end", "add_ball", "ball_end", "tilt", "wizard_reset", "optimus_running")

    def __init__(self, os_):
        super().__init__(os_)
        self.sides = {AUTOBOT: Autobot(self), DECEPTICON: Decepticon(self)}
        self.hit_at = -10.0
        for side in self.sides.values():
            os_.deff_rule((lambda s: lambda: s.active and s.shown)(side), side.bg, music=side.music, priority=0x76)   # QA V-ENG5
            os_.lamp_rule((lambda s: lambda: s.active and s.shown)(side), leff=side.rule_leff)
            # the rule leff flashes the lit shots (leff_046 / leff_054 [0x010285e8 / 0x0102a72c])
            os_.lamps.leff_code(side.rule_leff,
                                shot_blink(SHOT_LAMPS[side.rule_leff], (lambda s: lambda: s.lit)(side)))
            os_.lamp_rule((lambda s: lambda: s.active and s.phase == 3)(side), leff=side.super_leff)
        for i, leff in enumerate(BATTLE_RULE_LEFFS):
            os_.lamp_rule(self.battle_progress, leff=leff)
        from tf.lamps import music_gi_beat                    # noqa: PLC0415
        os_.lamps.leff_code(20, music_gi_beat(MUSIC_BEATS), gi=True)
        os_.lamp_rule(lambda: self.battle_progress() and self.pd.get("opt_left", 0) <= 0, leff=BATTLE_DONE_LEFF)

    def player_first_ball(self):
        pd = self.pd
        pd.opt_access = 0
        pd.opt_level = self.os.adj[67]
        pd.opt_battle = False
        pd.opt_left = 0
        for side in self.sides.values():
            side.reset()
            side.put("supers", 0)
            side.put("since", 0)
            side.put("sum", 0)

    def ball_start(self):
        if self.pd.get("opt_battle"):
            self.os.flag_set(BATTLE_FLAG)
        else:
            self.os.flag_clear(BATTLE_FLAG)

    def wizard_reset(self):
        for side in self.sides.values():
            side.reset()

    # ------------------------------------------------------------------ gates

    def running(self):
        return next((s for s in self.sides.values() if s.active), None)

    def optimus_running(self):
        return True if self.running() else None

    def mb_blocked(self):
        """A Megatron, Optimus, side mode or wizard multiball runs [0x01025d7c]."""
        os_ = self.os
        return any(os_.flag(f) for f in (0x25, 0x29, 0x1f, 0x22, 0x3c, 0x3e))

    def battle_progress(self):
        """[0x010260d8]: the battle runs and no multiball blocks it."""
        return bool(self.os.game) and bool(self.pd.get("opt_battle")) and not self.mb_blocked()

    def base_music(self):
        """Music table entry 0 side_choice_running_user [0x010068e4]: 0x31 / 0x34 whenever the battle can
        progress, before the playfield is valid too (QA SC15)."""
        if self.battle_progress():
            return BATTLE_MUSIC[self.pd.get("side", DECEPTICON)]
        return None

    # ------------------------------------------------------------------ access

    def sw_11(self):
        """[0x01025de4]."""
        os_ = self.os
        if os_.tilted or not os_.game:    # no time gate: the lockout is task 0x54 (tf/switches.py; QA R-F5)
            return
        pd = self.pd
        if self.mb_blocked() or pd.get("opt_battle"):
            os_.leff_start(BLOCKED_LEFF, lamp=0x28)    # leff 169 lights lamp 40 (+0x30) [0x01025de4]
            os_.sound(BLOCKED_SOUND)
            os_.score_add(BLOCKED_POINTS)
            return
        pd.opt_access = pd.get("opt_access", 0) + 1
        if pd.opt_access < NEEDED:
            os_.score_add(ACCESS_POINTS)
            os_.flag_set(ACCESS_FLAG)
            os_.deff_start(ACCESS_DEFF, values=[NEEDED - pd.opt_access])
            os_.after(HINT_FRAME_TICKS, lambda: os_.hook("hint_start"))   # deff 141 frame 10 [0x01025f18] (QA SC4)
            os_.leff_start(ACCESS_LEFF)
            os_.sound(ACCESS_SOUND)
            return
        self.battle_start()

    def battle_start(self):
        """[0x0102628c]."""
        os_ = self.os
        pd = self.pd
        os_.flag_set(BATTLE_FLAG)
        pd.opt_battle = True
        pd.opt_left = min(2 * pd.get("opt_level", 1) + 1, MAX_LEFT)
        self.hit_no = 1                   # dbattle_set_hits_needed [0x010261cc]: DAT_00035294 = 1
        os_.audit(BATTLE_AUDIT)
        os_.score_add(BATTLE_POINTS)
        os_.deff_start(BATTLE_DEFF)
        os_.deff_media(BATTLE_DEFF, BATTLE_LEFF, BATTLE_SOUND)
        pd.opt_access = 0
        os_.request_refresh()

    # ------------------------------------------------------------------ Optimus

    def sw_51(self):
        """[0x010262f0] (one tick after the switch opens, tf/switches.py OPENING_ONLY)."""
        os_ = self.os
        if os_.tilted or not os_.game:
            return
        side = self.sides[DECEPTICON]
        if side.active:
            side.optimus()
            return
        if not self.battle_progress():    # no time gate here either: task 0x54 / 0x4e (QA R-F5)
            return
        pd = self.pd
        self.hit_at = os_.now
        if pd.get("opt_left", 0) > 0:
            pd.opt_left -= 1
            # start_deff_144 [0x010262f0]: task +0x34 = DAT_00035294 (1 at the battle start, + 1 a hit) picks the
            # animation of the side's table, 0x040c70c4 (Decepticon, at most 6) or 0x040c70e0 (Autobot, at most 11)
            # (QA SC6, rom/rom_data/dmd/deff_anim_tables.csv)
            hit_no = getattr(self, "hit_no", 1)
            self.hit_no = hit_no + 1
            name = ("autobot_left%d" % min(hit_no, 11) if pd.get("side", DECEPTICON) == AUTOBOT
                    else "decepticon_left%d" % min(hit_no, 6))
            kwargs = {"variant": name} if deff_variant(HIT_DEFF, name) else {}
            os_.deff_start(HIT_DEFF, values=[pd.opt_left + 1], **kwargs)
            os_.leff_start(HIT_LEFF)
            os_.sound(HIT_SOUND)
            os_.request_refresh()
            return
        os_.score_add(START_AWARD)
        pd.opt_battle = False
        os_.flag_clear(BATTLE_FLAG)
        pd.opt_level = pd.get("opt_level", 1) + 1
        self.start_multiball()

    def start_multiball(self):
        os_ = self.os
        in_play = os_.rom_balls_in_play()
        os_.multiball_start(MB_BALLS if in_play <= 1 else in_play + 2, save_ticks=SAVE_TICKS,
                            grace_ticks=GRACE_TICKS)
        mult = self.sides[AUTOBOT].mult(CENTER)
        self.sides[self.pd.get("side", DECEPTICON)].start(mult)
        os_.request_refresh()

    # ------------------------------------------------------------------ shots

    def mb_shot(self, shot):
        side = self.running()
        if side:
            side.shot(shot)

    def mb_shot_6(self):
        side = self.sides[AUTOBOT]
        if side.active and side.shot(6):
            return True
        return None

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
        self.os.flag_clear(MB_FLAG)

    tilt = ball_end


def feature(os_):
    return Optimus(os_)
