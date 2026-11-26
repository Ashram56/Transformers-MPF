"""The score display (deff 19) and the status panel, drawn as ROM draw lists (tf/rom_draw.py).

From the code of deff 19 (0x0102fb8c) and of its score drawing FUN_0102f200 [0x0102f200] (the positions are the
code's: text_printf_msg(0x502, ..., x 0x26, row) with row 8p - 3, 0x15 for player 2 of 2, the award line at
8p + 13; the deff's code run, rom/rom_data/dmd/deff_ops/deff_019.json, gives the same draws):
- the status panel, left of a separator at column 40: each player's score in font 0, right edge at x 38, on rows
  8p - 3 (player 2 of a 2-player game on row 21); the players not up are drawn with a dimmer palette (code: the
  palette at sp+0x24 unless the player is up: level 3, 0x0102f200);
- the current player's score centred on x 84, font and baseline by value from table 0x040c75d0 (code, SCORE_TABLE);
- the bottom row (baseline 30): BALL n left at x 42 and the credits right at x 127, alternating with
  REPLAY AT <level> centred on x 84: 156 ticks of BALL / credits, then 312 ticks of REPLAY, then 1250 ticks of
  BALL / credits, and so on (code: 0x9c, 0x138, 0x4e2 at 0x0102fb90-0x0102fbe8; the traces confirm 2.49 s and 7.50 s).

The status counters (QA V-SC2, V-SC7, V-SC8, V-SC9; StatusCounters below): RAM 0x021120b0 (ticks since the last
score), 0x021120b8 (ticks since the last award value) and 0x021120a8 (ticks since the last combo) count up by one
every tick: 0x0102f9ec on event 0x21, posted once per tick at the end of the OS loop [0x0002bdb4] (agent A,
rom/rules/event_hooks.csv 0x21,2). Event 0x13, posted at the end of ball_start [0x00019e40], clears them
[0x0102f958]; event 0x4d, posted by score_add [0x0001caf0] with the points, takes a new award value [0x0102f998];
a combo award sets the way count and the player's combo count [0x01002f0c -> 0x0102f1c0, 0x0102f1f0].
"""
from tf import rom_draw as rd

PANEL_X, PANEL_FONT, SEPARATOR_X = 38, 0, 40
# table_75d0_find_2f11c [0x0102f11c]: the current player's score font and baseline by value, table 0x040c75d0
# (threshold, font, y; last entry 0x040c760c), drawn at x 0x54 with flags 2 [0x0102fa40] (QA V-SC1)
SCORE_TABLE = ((100000000, 22, 18), (1000000, 17, 18), (100000, 24, 21), (0, 26, 21))
MAIN_X = 84
ROW = 30
OTHER_LEVEL = 3                       # the players not up: palette entry 15 -> 3 (0x0102f200 local_21 = 3; QA V-SC6)
FIRST_BALL_TICKS, REPLAY_TICKS, BALL_TICKS = 0x9c, 0x138, 0x4e2
MAIN_BOX_X0, MAIN_BOX_X1 = 0x29, 0x7f  # the main score's box [0x0102fa40]; its rows are the table's +0xc .. +0x10
SCORE_ROWS = ((100000000, 4, 20), (1000000, 4, 20), (100000, 2, 23), (0, 2, 23))   # table 0x040c75d0 +0xc, +0x10
IDLE_TICKS, BLINK_PERIOD, BLINK_ON = 0x3e, 0xe, 7   # 0x021120b0 > 0x3e: blank 7 of every 14 ticks
AWARD_FADE, AWARD_KEEP = 0x1a, 0x10     # 0x021120b8: award text level (0x1a - n) >> 1; a smaller award within 0x10
COMBO_TICKS = 0x5e                       # 0x021120a8 < 0x5e: the combo texts slide
ST_PANEL_OFF = 0x11                      # gf_state bits bonus (0x01) and attract (0x10)
FAR = 1 << 30                            # a counter never cleared since power on


class StatusCounters:
    """The score display's counters (module docstring), kept as the time of their last clear: a counter reads
    the ticks since then, as the ROM's +1 per tick."""

    def __init__(self, tick):
        self.tick = tick
        self.score_at = self.award_at = self.combo_at = None
        self.award = self.way = self.count = 0

    def ticks(self, since, now):
        return FAR if since is None else max(0, int((now - since) / self.tick + 1e-6))

    def clear(self, now):
        """Event 0x13 [0x0102f958]: all counters 0, no award value, no combo."""
        self.score_at = self.award_at = self.combo_at = now
        self.award = self.way = self.count = 0

    def scored(self, points, now):
        """Event 0x4d [0x0102f998]: a score restarts the idle count; it becomes the award value unless a larger one
        came within 0x10 ticks."""
        if self.ticks(self.award_at, now) < AWARD_KEEP and points < self.award:
            self.score_at = now
            return
        self.award, self.award_at, self.score_at = points, now, now

    def combo(self, way, count, now):
        """A combo award [0x01002f0c]: way count (0x021120ac, its counter 0x021120a8 cleared [0x0102f1c0]) and the
        player's combo count (0x021120ae [0x0102f1f0])."""
        self.way, self.count, self.combo_at = way, count, now

    def values(self, now):
        """(idle, award ticks, combo ticks) at `now`: RAM 0x021120b0, 0x021120b8, 0x021120a8."""
        return self.ticks(self.score_at, now), self.ticks(self.award_at, now), self.ticks(self.combo_at, now)


def blank_on(idle):
    """[0x0102f200] / [0x0102fa40] with the playfield not valid: blank 7 of every 14 ticks after 0x3e idle ticks."""
    return idle > IDLE_TICKS and (idle - IDLE_TICKS) % BLINK_PERIOD < BLINK_ON


def sweep_period(score):
    """leaf_2f174 [0x0102f174]: twice the main score's box height (rows +0x10 - +0xc of table 0x040c75d0)."""
    _, y0, y1 = next(e for e in SCORE_ROWS if score >= e[0])
    return (y1 - y0) * 2


def score_text(score):
    return "{:,}".format(score) if score else "00"


def panel_draw(scores, current, level=15, status=None, state=0, valid=False):
    """The status panel [0x0102f200]: the last award value, the scores (player order), the current player's box,
    the separator and the combo texts. level: the deff's palette level; status: (StatusCounters, now); state:
    gf_state (0x31468); valid: the playfield is valid (0x000314d8)."""
    n = len(scores) or 1
    if state & 0x10:
        current = 0                                  # attract: no current player, every score at full level
    idle, award_ticks, combo_ticks = status[0].values(status[1]) if status else (0, FAR, FAR)
    counters = status[0] if status else None
    draw = []
    # the last award value, 1-2 players: under the current player's score, palette entry 15 = (0x1a - n) >> 1
    fade = (AWARD_FADE - award_ticks) >> 1 if award_ticks < AWARD_FADE else 0
    if counters and n < 3 and counters.award and not state & ST_PANEL_OFF and fade:
        y = 13 if current in (0, 1) else 8 * current + 13
        draw.append(rd.text(score_text(counters.award), PANEL_FONT, PANEL_X, y, 4, min(level, fade)))
    for p, score in enumerate(scores or [0], 1):
        y = 21 if (p == 2 and n == 2) else 8 * p - 3
        draw.append(rd.text(score_text(score), PANEL_FONT, PANEL_X, y, 4,
                            level if p == current or n == 1 or state & 0x10 else min(level, OTHER_LEVEL)))
    if status and not state & ST_PANEL_OFF and current:
        top, bottom = (17, 22) if (current == 2 and n == 2) else (8 * current - 7, 8 * current - 2)
        rows = None
        if not valid:
            if blank_on(idle):
                rows = (top, bottom)
        else:                                        # a sweep down the current player's row [0x0102f394]
            period = sweep_period(scores[current - 1] if 0 < current <= len(scores) else 0)
            u = idle % (period * 2 + IDLE_TICKS)
            if u > IDLE_TICKS:
                v = (u - IDLE_TICKS) * 12 // (period * 2)
                rows = (top, top + v) if v < 6 else (top + v - 6, bottom)
        if rows:
            draw.append(rd.box(0, rows[0], 0x27 + 1, rows[1] - rows[0] + 1, 0))
    draw.append(rd.box(SEPARATOR_X, 0, 1, 32, level))
    if counters and combo_ticks < COMBO_TICKS:
        # "%d-WAY" and "COMBO" (msgs 0x6d1, 0x6d2) slide up from rows 25 and 31 after a combo of 2 ways or more
        shown = counters.way > 1 and not state & ST_PANEL_OFF
        for msg, top in (("%d-WAY" % counters.way, 0x4b), ("COMBO", 0x5d)):
            if shown and combo_ticks <= top:
                draw.append(rd.text(msg, 1, 0x27, (top - combo_ticks) // 3, 4, level))
        if n < 3 and shown:
            # "%d COMBO%P1//S/%" (msg 0x6d3) at row 0x20, x 0x27 (0x28 from 100 combos)
            text = "%d COMBO%s" % (counters.count, "" if counters.count == 1 else "S")
            draw.append(rd.text(text, 1, 0x27 if counters.count < 100 else 0x28, 0x20, 4, level))
    return draw


def replay_phase(ticks):
    """True while the bottom row shows REPLAY AT, `ticks` ROM ticks after deff 19 started."""
    if ticks < FIRST_BALL_TICKS:
        return False
    return (ticks - FIRST_BALL_TICKS) % (REPLAY_TICKS + BALL_TICKS) < REPLAY_TICKS


def main_box(score, idle, valid):
    """[0x0102fa40]: the rows of the box blanked over the main score (x 0x29-0x7f), or None."""
    _, y0, y1 = next(e for e in SCORE_ROWS if score >= e[0])
    if not valid:
        return (y0, y1) if blank_on(idle) else None
    half = y1 - y0
    u = idle % (half * 4 + IDLE_TICKS)               # leaf_2f174 * 2 + 0x3e
    if u <= IDLE_TICKS:
        return None
    u = (u - IDLE_TICKS) >> 1
    return (y0 + u - half, y1) if u >= half else (y0, y0 + u)


def score_draw(scores, current, ball, credits, replay="", ticks=0, status=None, state=0, valid=False):
    """deff 19: panel, the current player's score, and the bottom row (replay: "REPLAY AT ..." or "")."""
    score = scores[current - 1] if scores and 0 < current <= len(scores) else 0
    draw = panel_draw(scores, current, status=status, state=state, valid=valid)
    _, font, y = next(e for e in SCORE_TABLE if score >= e[0])
    draw.append(rd.text(score_text(score), font, MAIN_X, y, 2))
    rows = main_box(score, status[0].values(status[1])[0], valid) if status else None
    if rows:
        draw.append(rd.box(MAIN_BOX_X0, rows[0], MAIN_BOX_X1 - MAIN_BOX_X0 + 1, rows[1] - rows[0] + 1, 0))
    if replay and replay_phase(ticks):
        draw.append(rd.text(replay, 0, MAIN_X, ROW, 2))
    else:
        draw += [rd.text("BALL {}".format(ball), 0, 42, ROW, 1), rd.text(credits, 0, 127, ROW, 4)]
    return draw
