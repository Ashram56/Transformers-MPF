"""The score display (deff 19) and the status panel, drawn as ROM draw lists (tf/rom_draw.py).

From the ROM extraction's capture of deff 19 (rom/mpf_package/media/dmd/deffs/deff_019/timing.json: every text
draw with its font, position and flags, observed) and the code of deff 19 (0x0102fb8c) and of its score drawing
FUN_0102f200 (code):
- the status panel, left of a separator at column 40: each player's score in font 0, right edge at x 38, on rows
  8p - 3 (player 2 of a 2-player game on row 21); the players not up are drawn with a dimmer palette (code: the
  palette at sp+0x24 unless the player is up: level 3, 0x0102f200);
- the current player's score centred on x 84, font and baseline by value from table 0x040c75d0 (code, SCORE_TABLE);
- the bottom row (baseline 30): BALL n left at x 42 and the credits right at x 127, alternating with
  REPLAY AT <level> centred on x 84: 156 ticks of BALL / credits, then 312 ticks of REPLAY, then 1250 ticks of
  BALL / credits, and so on (code: 0x9c, 0x138, 0x4e2 at 0x0102fb90-0x0102fbe8; observed 2.49 s and 7.50 s).
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


def score_text(score):
    return "{:,}".format(score) if score else "00"


def panel_draw(scores, current, level=15):
    """The status panel: the scores (player order) and the separator. level: the deff's palette level."""
    n = len(scores) or 1
    draw = []
    for p, score in enumerate(scores or [0], 1):
        y = 21 if (p == 2 and n == 2) else 8 * p - 3
        draw.append(rd.text(score_text(score), PANEL_FONT, PANEL_X, y, 4,
                            level if p == current or n == 1 else min(level, OTHER_LEVEL)))
    draw.append(rd.box(SEPARATOR_X, 0, 1, 32, level))
    return draw


def replay_phase(ticks):
    """True while the bottom row shows REPLAY AT, `ticks` ROM ticks after deff 19 started."""
    if ticks < FIRST_BALL_TICKS:
        return False
    return (ticks - FIRST_BALL_TICKS) % (REPLAY_TICKS + BALL_TICKS) < REPLAY_TICKS


def score_draw(scores, current, ball, credits, replay="", ticks=0):
    """deff 19: panel, the current player's score, and the bottom row (replay: "REPLAY AT ..." or "")."""
    score = scores[current - 1] if scores and 0 < current <= len(scores) else 0
    draw = panel_draw(scores, current)
    _, font, y = next(e for e in SCORE_TABLE if score >= e[0])
    draw.append(rd.text(score_text(score), font, MAIN_X, y, 2))
    if replay and replay_phase(ticks):
        draw.append(rd.text(replay, 0, MAIN_X, ROW, 2))
    else:
        draw += [rd.text("BALL {}".format(ball), 0, 42, ROW, 1), rd.text(credits, 0, 127, ROW, 4)]
    return draw
