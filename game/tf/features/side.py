"""Autobot or Decepticon: the side each player plays, which picks the base music (rom/rom_data/sound/music_table.csv).

Music table entry 0x34cd4 (code): while the side choice runs (task 200) the background deff is 40 with music
0x1a (Autobot) / 0x1b (Decepticon); after it, deff 19 with 0x1c / 0x1d until the playfield is valid; the
fallback entry 0x34cec plays 0x1e / 0x1f in play. The ROM extraction notes that which side value is Autobot is
a guess; the sound call roles follow its labels.

Observed (rom/rules/traces/sounds.jsonl, one player, no flipper during the choice):
- game start 17.72 s: deff 19, deff 40 and music 0x1b, with leffs 104, 92, 95 (a later ball: 104, 92 and
  music 0x1d; leff 14 one tick later is the OS's ball save leff);
- plunge 30.58 s: deff 41 (its sound 0x58 and leff 96 come with the deff) 0.60 s later (37 ticks), then deff 19
  and music 0x1d; after the first award, 0x1f.
Inferred: the choice runs on each player's first ball, Decepticon is the side kept when nobody chooses, and a
flipper button during the choice switches the side (the music follows; the switching sound is not known).
"""
from tf.features import Feature

ORDER = 10
AUTOBOT, DECEPTICON = 1, 2
MUSIC = {"choose": {AUTOBOT: 0x1a, DECEPTICON: 0x1b},
         "ball_start": {AUTOBOT: 0x1c, DECEPTICON: 0x1d},
         "play": {AUTOBOT: 0x1e, DECEPTICON: 0x1f}}
CHOICE_DEFF, CHOSEN_DEFF = 40, 41
CHOICE_END_TICKS = 37              # deff 41 after the ball leaves the shooter lane (observed 0.604 s)
BALL_START_LEFFS = (104, 92)
CHOICE_LEFF = 95


class Side(Feature):
    name = "side"
    HOOKS = ("player_first_ball", "base_music", "ball_start_media", "ball_end")

    def __init__(self, os_):
        super().__init__(os_)
        self.choosing = False
        os_.display.add_rule(lambda: self.choosing, CHOICE_DEFF, music=lambda: MUSIC["choose"][self.side()],
                             priority=0xff)
        sc = self.machine.switch_controller
        sc.add_switch_handler("s_shooter_lane", self._launched, state=0)
        for name in ("s_l_flipper_button", "s_r_flipper_button"):
            sc.add_switch_handler(name, self._flipper)

    def side(self):
        return self.pd.get("side", DECEPTICON) if self.os.game else DECEPTICON

    def player_first_ball(self):
        self.pd["side"] = DECEPTICON
        self.choosing = True

    def ball_end(self):
        self.choosing = False

    def base_music(self):
        if not self.os.game:
            return None
        if self.choosing:
            return MUSIC["choose"][self.side()]
        return MUSIC["play" if self.os.ball_validated else "ball_start"][self.side()]

    def ball_start_media(self):
        os_ = self.os
        for leff in BALL_START_LEFFS + ((CHOICE_LEFF,) if self.choosing else ()):
            os_.leff_start(leff)
        if self.choosing:
            os_.request_refresh()

    def _flipper(self):
        if self.choosing and self.os.game and not self.os.tilted:
            self.pd["side"] = AUTOBOT if self.side() == DECEPTICON else DECEPTICON
            self.os.display.rules_refresh()

    def _launched(self):
        if self.choosing and self.os.game:
            self.os.after(CHOICE_END_TICKS, self._chosen)

    def _chosen(self):
        if not self.choosing or not self.os.game:
            return
        self.choosing = False
        self.os.deff_start(CHOSEN_DEFF)
        self.os.request_refresh()                    # deff 19 and its music right after deff 41's sound


def feature(os_):
    return Side(os_)
