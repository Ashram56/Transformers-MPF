"""The score display (deff 19) and the status panel, drawn as ROM draw lists (tf/rom_draw.py).

From the ROM extraction's capture of deff 19 (rom/mpf_package/media/dmd/deffs/deff_019/timing.json: every text
draw with its font, position and flags, observed) and the code of deff 19 (0x0102fb8c) and of its score drawing
FUN_0102f200 (code):
- the status panel, left of a separator at column 40: each player's score in font 0, right edge at x 38, on rows
  8p - 3 (player 2 of a 2-player game on row 21); the players not up are drawn with a dimmer palette (code: the
  palette at sp+0x24 unless the player is up; its level is inferred);
- the current player's score in font 26 centred on x 84, baseline 21 (observed with the score 00; the font used
  for scores too wide for 87 dots is inferred: the next smaller digit fonts);
- the bottom row (baseline 30): BALL n left at x 42 and the credits right at x 127, alternating with
  REPLAY AT <level> centred on x 84: 156 ticks of BALL / credits, then 312 ticks of REPLAY, then 1250 ticks of
  BALL / credits, and so on (code: 0x9c, 0x138, 0x4e2 at 0x0102fb90-0x0102fbe8; observed 2.49 s and 7.50 s).
"""
from tf import rom_draw as rd

PANEL_X, PANEL_FONT, SEPARATOR_X = 38, 0, 40
SCORE_FONTS = (26, 24, 22, 20)        # 18-dot digits first (observed), then smaller digit sets (inferred)
MAIN_X, MAIN_Y, MAIN_WIDTH = 84, 21, 87
ROW = 30
OTHER_LEVEL = 6                       # the players not up (inferred)
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
    draw.append(rd.fit(score_text(score), MAIN_X, MAIN_Y, SCORE_FONTS, width=MAIN_WIDTH))
    if replay and replay_phase(ticks):
        draw.append(rd.text(replay, 0, MAIN_X, ROW, 2))
    else:
        draw += [rd.text("BALL {}".format(ball), 0, 42, ROW, 1), rd.text(credits, 0, 127, ROW, 4)]
    return draw
