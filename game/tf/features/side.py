"""Autobot or Decepticon: the side each player plays, which picks the base music (rom/rules/switches_and_shots.md
"Side choice", rom/rom_data/sound/music_table.csv).

- Game start (code + observed): the player's side byte (0x02112107 + player) comes from adj 65 (random by
  default: Decepticon in traces/sounds and basic, Autobot for both players in game_flow); task 200 runs
  and the music table gives deff 40 with music 0x1a (Autobot) / 0x1b (Decepticon), with leffs 104, 92, 95.
- Either flipper toggles the side (1 = Autobot, 2 = Decepticon), plays 0x257 and re-evaluates the music
  (deff 40 function 0x1034198), which then draws the chosen side's logo (image 0x2232 Autobot / 0x2234
  Decepticon); deff 41 names it (message 0x682 AUTOBOT / 0x683 DECEPTICON). The captures are the Decepticon
  side: scripts/gen_media.py makes the Autobot slides (SIDE_VARIANTS), tf/media_bridge.py picks them.
- The shooter lane opening starts task 0xc9 (0x1033f18): 31 ticks later 0x1033f54 shows deff 41 with sound
  0x57 (Autobot) / 0x58 (Decepticon) and kills task 200. A playfield switch other than 12 (right orbit) ends the
  choice earlier (event hooks 0x6b/0x6c; the same ending is inferred).
- After it: deff 19 with 0x1c / 0x1d until the playfield is valid, 0x1e / 0x1f in play.
Inferred: the choice runs on each player's first ball (one-player traces only).
"""
from tf.features import Feature

ORDER = 10
AUTOBOT, DECEPTICON = 1, 2
MUSIC = {"choose": {AUTOBOT: 0x1a, DECEPTICON: 0x1b},
         "ball_start": {AUTOBOT: 0x1c, DECEPTICON: 0x1d},
         "play": {AUTOBOT: 0x1e, DECEPTICON: 0x1f}}
CHOICE_DEFF, CHOSEN_DEFF = 40, 41
CHOICE_END_TICKS = 31              # task 0xc9's sleep before deff 41 (code)
TOGGLE_SOUND = 0x257
CHOSEN_SOUND = {AUTOBOT: 0x57, DECEPTICON: 0x58}
BALL_START_LEFFS = (92,)         # leff 104 (lit battle) is the battles rule (tf/features/battles.py)
CHOICE_LEFF = 95


class Side(Feature):
    name = "side"
    HOOKS = ("player_first_ball", "base_music", "ball_start_media", "ball_end", "switch", "side_choosing")

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
        """The starting side by adj 65 TRANSFORMERS SELECT: 0 random, 1 Autobot, 2 Decepticon (game_flow.md 2;
        the ROM's random source was not identified)."""
        select = self.os.adj[65]
        if select in (AUTOBOT, DECEPTICON):
            self.pd["side"] = select
        else:
            self.pd["side"] = AUTOBOT if self.os.pick("side", [1, 1]) == 0 else DECEPTICON
        self.choosing = True

    def ball_end(self):
        self.choosing = False

    def side_choosing(self):
        return self.choosing or None

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
            self.os.hook("side_changed")             # the side's first battle is lit [0x01022d7c]
            self.os.sound(TOGGLE_SOUND, in_deff=CHOICE_DEFF)
            self.os.display.rules_refresh()
            self.os.display.redraw(CHOICE_DEFF)      # the chosen side's logo, and the PuP Pack's D10 / D11

    def switch(self, num):
        if self.choosing and num != 12:
            self._chosen()

    def _launched(self):
        if self.choosing and self.os.game:
            self.os.after(CHOICE_END_TICKS, self._chosen)

    def _chosen(self):
        if not self.choosing or not self.os.game:
            return
        self.choosing = False
        side = self.side()
        self.os.deff_start(CHOSEN_DEFF, sounds=[(0, lambda: self.os.sound(CHOSEN_SOUND[side], in_deff=CHOSEN_DEFF))])
        self.os.request_refresh()                    # deff 19 and its music right after deff 41's sound


def feature(os_):
    return Side(os_)
