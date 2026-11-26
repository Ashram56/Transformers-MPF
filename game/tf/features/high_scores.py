"""High-score table and initials entry (game_flow.md 5.5; OS code, not a rules mode).

Table [0x0001855c / 0x000185c8]: in each list GRAND CHAMPION then HIGH SCORE #1-#4 (below); an entry is a
name and a score, kept in MPF's data file "tf_high_scores" like the ROM's NVRAM records.
- Reset of an entry [0x00018730]: the default name (3 initials, or the 10-letter name on adj 60) and the
  score of its adjustment (adj 49 GRAND CHAMPION SCORE, adj 50-53 HIGH SCORE #1-#4). RESET GRAND CHAMPION
  resets entry 0 (flag 1), RESET HIGH SCORES entries 1-4 (flag 2) [0x000189fc], RESET FACTORY SETTINGS
  all [0x00018b20].
- adj 61 HSTD RESET COUNT [0x000184f8], at every game start while adj 48 = YES: a counter (reloaded from
  adj 61) counts the games down; at 0 the high scores (not the grand champion) are reset. 0 = OFF.
Entry at game over, before match [high_score_entry 0x00018d54], only on adj 48 ALLOW HIGH SCORES = YES; gf_state
0x40 is set meanwhile (START cannot start a game). For each entry in order, the best player of the game not
yet placed whose score beats the entry's [0x00018b70, ties go to the earlier player]:
1. the player's initials (once per player and table; this game has one table): event 0x33, deff 31 "PLAYER n / ENTER INITIALS", events 0x34 / 0x35, deff 32 initials
   entry (below), event 0x36;
2. [0x00018c04] the entry and the ones below move down one place and the player's name and score go in
   [0x000188cc]; the entry's award (adj 55-59 count, adj 54 kind: 0 credit with knocker, 1 ticket,
   2 token) and audit 0x10 HIGH SCORE AWARDS by the count; event 0x37, deff 33 (the entry, name and score,
   with the award), event 0x38.
Initials entry, deff 32 [0x0103c840], one frame per tick: the left / right flipper button picks the previous /
next letter (auto-repeat after 31 frames, then every 7; both buttons together do nothing), START takes it.
After the letters come three specials: BACK (deletes a letter), END and SPACE; once the name is full only
BACK and END can be picked, END at first. 3 initials (adj 60 = 0) or 10 letters. A 30 s countdown (63
frames a second) restarts on every button; at its end 15 more seconds are shown, then the entry ends with
what is entered (plus the letter under the cursor).
This is Tron 1.74's OS model (the same SAM OS), re-cited to tf_180's routines (QA F13). tf_180 has 17 entries in five
lists (tables 0x040cf948 / 0x040cfc48, QA D-HS-COMBO): HIGHEST SCORES, AUTOBOT and DECEPTICON HIGHEST SCORES (the
player's side), COMBO CHAMPION (combos made) and BEST COMBO CHAMPION (way and multiplier), each list placing its
players apart; the initials are asked once per player. Not read yet for tf_180: the letter set.
"""
from tf.features import Feature

ORDER = 7
# The 17 entries of table 0x040cf948 (0x20 bytes each; QA D-HS-COMBO): title (+0x14), default name with 3 initials
# (+4) and with 10 letters on adj 60 (+8), reset groups (+0x18: 1 grand champion, 2 high scores), score adj (+0x1a),
# award kind adj (+0x1c) and award count adj (+0x1e)
_HS = ("HIGH SCORE #1", "HIGH SCORE #2", "HIGH SCORE #3", "HIGH SCORE #4")
TITLES = ("GRAND CHAMPION",) + _HS + ("GRAND CHAMPION",) + _HS + ("GRAND CHAMPION",) + _HS + (
    "COMBO CHAMPION", "BEST COMBO CHAMPION")
NAMES = (("G S", "STERN"), ("L R", "ROPP"), ("J R", "ROTHARMEL"), ("D T", "THORNE"), ("P P", "POWERS"),
         ("OPT", "OPTIMUS"), ("JAZ", "JAZZ"), ("PWL", "PROWL"), ("IRN", "IRONHIDE"), ("BEE", "BUMBLEBEE"),
         ("MEG", "MEGATRON"), ("STR", "STARSCREAM"), ("SND", "SOUNDWAVE"), ("SHK", "SHOCKWAVE"), ("BLK", "BLACKOUT"),
         ("LON", "ROPP"), ("LON", "ROPP"))
SCORE_ADJ = (49, 50, 51, 52, 53) * 3 + (90, 93)
KIND_ADJ = (54,) * 15 + (91, 94)
AWARD_ADJ = (55, 56, 57, 58, 59) * 3 + (92, 95)
FLAGS = (1, 3, 3, 3, 3) * 3 + (3, 3)
# The five lists of table 0x040cfc48 (0x24 bytes each): title, entries (0-based here), the player's value (+4) and
# who may enter (+0x10); lists 1-3 skip a player with 0x021109f3[p] set (+0x20 = 1, not modelled: never set here)
LISTS = (("HIGHEST SCORES", range(0, 5), "score", None),                  # 0x0001cacc, 0x01007500
         ("AUTOBOT HIGHEST SCORES", range(5, 10), "score", 1),            # 0x01007508: player_side 1
         ("DECEPTICON HIGHEST SCORES", range(10, 15), "score", 2),        # 0x01007578: player_side 2
         ("COMBO CHAMPION", range(15, 16), "combo_total", None),          # 0x0100279c: 0x02111d08[p]
         ("BEST COMBO CHAMPION", range(16, 17), "combo_best", None))      # 0x010028f4: 0x02111d10[p]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SPECIALS = ("BACK", "END", "SPACE")
FRAME_TICKS = 1
SECOND_FRAMES = 63                       # 0x3e frames, then the second counts down
COUNTDOWN, LAST_COUNTDOWN = 30, 15
REPEAT_FIRST, REPEAT_NEXT = 31, 6        # held button: first repeat after 0x1f frames, then every 7
DEFF_SECONDS = {31: 1.841, 33: 2.353}    # run lengths (event_map.csv run_ms) when the media table has none
# deff 32 [0x0103c840] / deff 36 [0x0103e460]: the OS words 0x00030eac / 0x00030eae / 0x00030eb0 (0x04c, 0x04d,
# 0x04e in tf_180) on a step back, a step forward and an entered character (QA SC8)
SOUNDS = {"left": 0x04c, "right": 0x04d, "select": 0x04e, "countdown": None, "enter_initials": None}


class Entry:
    """Initials entry, deff 32 [0x0103c840]."""

    def __init__(self, hs, player, done):
        self.hs, self.os, self.machine = hs, hs.os, hs.machine
        self.player = player
        self.done = done
        self.size = 10 if self.os.adj[60] == 1 else 3
        self.name = ""
        self.cursor = 0
        self.seconds, self.counting = COUNTDOWN, False
        self.frame_left = SECOND_FRAMES - 1
        self.select = False
        self.buttons = {"s_l_flipper_button": [False, False, 0], "s_r_flipper_button": [False, False, 0]}  # was, holding, repeat
        self.handler = self.machine.switch_controller.add_switch_handler("s_start_button", self._start, state=1)
        self.os.deff_start(32, hold=True, player=player, seconds=self.seconds)
        self.show()
        self.handle = self.os.after(FRAME_TICKS, self.frame)

    def letter(self):
        return LETTERS[self.cursor] if self.cursor < len(LETTERS) else SPECIALS[self.cursor - len(LETTERS)]

    def show(self):
        self.machine.events.post("tf_initials", player=self.player, name=self.name, letter=self.letter(),
                                 seconds=self.seconds if self.counting else None)
        self.os.media.text_show("text_page", ["PLAYER {} - ENTER INITIALS".format(self.player),
                                              self.name + ("_" if self.cursor >= len(LETTERS) else self.letter()),
                                              str(self.seconds) if self.counting else ""], 244,
                                 screen=4)   # text_page.tscn: deff 32's rows (0x0103c840), ROM fonts 2 / 14 / 2

    def _start(self):
        self.select = True

    def _sound(self, key):
        if SOUNDS[key] is not None:
            self.os.sound(SOUNDS[key])

    def _step(self, name):
        """One frame of a button: (stepped, holding)."""
        state = self.buttons[name]
        down = bool(self.machine.switches[name].state)
        stepped = False
        if down and not state[0]:
            state[1], state[2], stepped = True, REPEAT_FIRST, True
        elif state[1] and down:
            state[2] -= 1
            if state[2] == -1:
                state[2], stepped = REPEAT_NEXT, True
        else:
            state[1] = False
        state[0] = down
        return stepped, state[1]

    def move(self, step):
        n = len(LETTERS)
        if len(self.name) < self.size:
            self.cursor = (self.cursor + step) % (n + 3)
        else:
            self.cursor = n + 1 if self.cursor == n else n      # a full name: BACK <-> END
        self._sound("left" if step < 0 else "right")
        self.show()

    def frame(self):
        left, hold_l = self._step("s_l_flipper_button")
        right, hold_r = self._step("s_r_flipper_button")
        if not (hold_l and hold_r):
            if left and not right:
                self.move(-1)
            elif right and not left:
                self.move(1)
        if hold_l or hold_r or self.select:
            self.seconds = LAST_COUNTDOWN if self.counting else COUNTDOWN
            self.frame_left = SECOND_FRAMES - 1
        elif self.frame_left == 0:
            self.frame_left = SECOND_FRAMES - 1
            if self.seconds == 0:
                if self.counting:
                    if self.cursor < len(LETTERS) and len(self.name) < self.size:
                        self.name += self.letter()       # the letter under the cursor is part of the name
                    return self.finish()
                self.counting, self.seconds = True, LAST_COUNTDOWN
                self._sound("countdown")
            else:
                self.seconds -= 1
            self.show()
        else:
            self.frame_left -= 1
        if self.select:
            self.select = False
            if self.take():
                return self.finish()
        self.handle = self.os.after(FRAME_TICKS, self.frame)

    def take(self):
        """START: the letter or special under the cursor. Returns True at END."""
        n = len(LETTERS)
        if self.cursor >= n:
            special = SPECIALS[self.cursor - n]
            self._sound("select")
            if special == "END":
                return True
            if special == "BACK":
                self.name = self.name[:-1]
            elif len(self.name) < self.size:
                self.name += " "
        elif len(self.name) < self.size:
            self.name += LETTERS[self.cursor]
            self._sound("select")
        if len(self.name) >= self.size:
            self.cursor = n + 1                         # END
        self.show()
        return False

    def finish(self):
        self.machine.switch_controller.remove_switch_handler_by_key(self.handler)
        self.os.deff_stop(32)
        self.os.media.text_hide("text_page")
        self.done(self.name)


class HighScores(Feature):
    name = "high_scores"

    def __init__(self, os_):
        super().__init__(os_)
        self.store = self.machine.create_data_manager("tf_high_scores")
        data = self.store.get_data() or {}
        entries = data.get("entries") or []
        self.entries = [dict(e) for e in entries] if len(entries) == len(TITLES) else None
        self.count = data.get("reset_count")
        self.entry = None
        self._loaded()

    @property
    def adj(self):
        return self.os.adj

    def _loaded(self):
        if self.entries is None:                    # no valid record: every entry is reset [0x000190bc]
            self.entries = [None] * len(TITLES)
            self.reset(3)
        if self.count is None:
            self.count = self.adj[61]
            self.save()

    def save(self):
        self.store.save_all(data={"entries": [dict(e) for e in self.entries], "reset_count": self.count})

    def default_name(self, i):
        """[0x00018730]: +8 on adj 60 = 1 (10 letters), else +4."""
        return NAMES[i][1 if self.adj[60] == 1 else 0]

    def reset(self, mask):
        """FUN_000189fc: reset the entries of the flag mask (1 grand champion, 2 high scores)."""
        for i, flag in enumerate(FLAGS):
            if flag & mask:
                self.entries[i] = {"name": self.default_name(i), "score": self.adj[SCORE_ADJ[i]]}
        self.save()

    def reset_all(self):
        """FUN_00018b20: every entry and the reset counter."""
        self.reset(3)
        self.count = self.adj[61]
        self.save()

    def game_started(self):
        """FUN_000184f8: adj 61 HSTD RESET COUNT, counted down by every game while adj 48 = YES."""
        if not self.adj[61] or self.adj[48] != 1:
            return
        if self.count < 1:
            self.reset(2)
            self.count = self.adj[61]
        else:
            self.count -= 1
        self.save()

    def table(self):
        """(title, name, score) of each entry, or [] when high scores are off (FUN_000186d0)."""
        if self.adj[48] != 1:
            return []
        return [(TITLES[i], e["name"], self.score_text(i, e["score"])) for i, e in enumerate(self.entries)]

    @staticmethod
    def score_text(i, score):
        """The entry's score as the formatters print it: combos 0x010028c4 (msg 0x6e0 "%,02lu COMBO%P1//S/%"),
        best combo 0x01002a7c (msg 0x6e1 "%P1//DOUBLE /TRIPLE //%%u-WAY" with mult = low nibble, way = high word)."""
        if i == 15:
            return "{:,} COMBO{}".format(score, "" if score == 1 else "S")
        if i == 16:
            mult, way = score & 0xf, score >> 16
            return "{}{}-WAY".format({2: "DOUBLE ", 3: "TRIPLE "}.get(mult, ""), way)
        return score

    # ------------------------------------------------------------------ entry at game over

    def run(self, done):
        os_ = self.os
        if self.adj[48] != 1 or not os_.game:
            done()
            return
        os_.state |= 0x40
        self.players = self.machine.game.player_list
        self.names = [None] * len(self.players)
        self._done = done
        self._list(0)

    def value(self, lst, n):
        key = LISTS[lst][2]
        player = self.players[n - 1]
        if key == "score":
            return player.score
        return os_pd(self.os, n).get(key, 0)

    def _list(self, lst):
        """high_score_entry [0x00018d54]: the lists in order, each with its own placed players."""
        if lst >= len(LISTS):
            self.os.state &= ~0x40
            self.save()
            self._done()
            return
        self.lst = lst
        self.placed = [False] * len(self.players)
        self._next(LISTS[lst][1][0])

    def best(self, i):
        """FUN_00018b70: the best unplaced player of the list who may enter it, beating entry i (ties: the
        earlier player), or 0."""
        side = LISTS[self.lst][3]
        best = 0
        for n in range(1, len(self.players) + 1):
            if self.placed[n - 1] or (side is not None and os_pd(self.os, n).get("side") != side):
                continue
            v = self.value(self.lst, n)
            if v > self.entries[i]["score"] and (not best or v > self.value(self.lst, best)):
                best = n
        return best

    def _deff(self, deff_id, then, **args):
        info = self.os.display.media.get(deff_id)
        seconds = info.seconds if info and info.seconds else DEFF_SECONDS[deff_id]
        self.os.deff_start(deff_id, run_seconds=seconds, **args)
        self.machine.clock.schedule_once(lambda: then(), seconds)

    def _next(self, i):
        if i > LISTS[self.lst][1][-1]:
            self._list(self.lst + 1)
            return
        player = self.best(i)
        if not player:
            self._next(i + 1)
            return
        post = self.machine.events.post
        post("tf_high_score", stage=0x33, player=player, entry=i)

        def initials():
            post("tf_high_score", stage=0x34, player=player, entry=i)
            post("tf_high_score", stage=0x35, player=player, entry=i)
            self.entry = Entry(self, player, entered)
        if self.names[player - 1] is not None:      # the initials once per player [0x00018d54]
            self._place(i, player)
            return

        def entered(name):
            self.entry = None
            self.names[player - 1] = name
            post("tf_high_score", stage=0x36, player=player, entry=i)
            self._place(i, player)
        self._deff(31, initials, player=player)

    def _place(self, i, player):
        """FUN_00018c04: the entry and the ones below move down, the award, deff 33."""
        os_ = self.os
        last = LISTS[self.lst][1][-1]
        self.entries[i + 1:last + 1] = self.entries[i:last]
        self.entries[i] = {"name": self.names[player - 1], "score": self.value(self.lst, player)}
        self.save()
        count = self.adj[AWARD_ADJ[i]]
        kind = self.adj[KIND_ADJ[i]]
        if count:
            if kind == 0:
                os_.award_credit(count)
                for _ in range(count):
                    os_.knock()                     # FUN_00019378(1, n)
            elif kind == 1:
                for _ in range(count):
                    self.machine.events.post("tf_award_ticket")
            os_.audit(0x10, count)
        post = self.machine.events.post
        post("tf_high_score", stage=0x37, player=player, entry=i)
        self.placed[player - 1] = True

        def shown():
            post("tf_high_score", stage=0x38, player=player, entry=i)
            self._next(i + 1)
        self._deff(33, shown, player=player, title=TITLES[i], name=self.entries[i]["name"],
                   score=self.score_text(i, self.entries[i]["score"]), award=kind if count else None, count=count)


def os_pd(os_, n):
    """Rule state of player n (1-based)."""
    return os_.players[n - 1] if n - 1 < len(os_.players) else {}


feature = HighScores
