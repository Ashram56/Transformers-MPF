"""The score display (deff 19) and the attract screen (deff 1), drawn as ROM draw lists (tf/rom_draw.py).

INTERIM, inferred layouts. The ROM's own screens are not captured yet: deff 19 (0x0102fb8c) draws the scores
with FUN_0102f200 and a status panel with FUN_0102fa40 (code, not decoded), and deff 1 (0x0103c584) plays the
attract show. Until the ROM extraction's display captures land, these screens use the ROM's fonts (exact, from
the font table) in a plain SAM-style layout: the current player's score large, the others small, the ball and
credits on the bottom row; attract shows GAME OVER / the credits. Listed in docs/rom_differences.md.
"""
from tf import rom_draw as rd

BIG, MEDIUM, SMALL, LINE = 23, 21, 19, 0          # ROM fonts: 18-dot digits, 12-dot digits, 7-dot digits, 5-dot text
CORNERS = {1: (1, 12, 1), 2: (126, 12, 4), 3: (1, 25, 1), 4: (126, 25, 4)}   # player -> x, baseline, flags


def score_text(score):
    return "{:,}".format(score) if score else "00"


def score_draw(players, current, ball, credits):
    """players: the scores in player order; current: 1-based; credits: the bottom-right text."""
    if len(players) <= 1:
        draw = [rd.fit(score_text(players[0] if players else 0), 64, 22, (BIG, MEDIUM))]
    else:
        draw = []
        for p, score in enumerate(players, 1):
            x, y, flags = CORNERS[p]
            draw.append(rd.text(score_text(score), MEDIUM if p == current else SMALL, x, y, flags))
    draw += [rd.text("BALL {}".format(ball), LINE, 1, 31, 1), rd.text(credits, LINE, 126, 31, 4)]
    return draw


def attract_draw(credits):
    return [rd.text("GAME OVER", 9, 64, 14, 2), rd.text(credits, 4, 64, 26, 2)]
