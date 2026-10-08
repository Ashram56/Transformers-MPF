# Departures from the ROM

Every place the game differs from tf_180, why, and what replaces it. Interim rows go away when the ROM
extraction delivers the data.

| Area | ROM | Here | Kind |
|---|---|---|---|
| Score display (deff 19) | 0x0102fb8c | drawn live from the captured draw calls; the dim level of players not up and the font for scores wider than 87 dots are inferred (tf/score_screen.py) | inferred details |
| Display effects with values | the ROM prints live values (scores, counts, credits, high scores) | the capture's frames, so the values are those of the capture run (CREDITS 1/3, high score table, 00); the status panel is live | interim, until each deff's text is drawn live |
| Deffs without frames (39) | they draw live state or nothing in the capture window | nothing drawn (the previous screen stays) | interim |
| Scoring and rules | switch handlers per the rules specs | no points; outlanes start the ball save only | interim, until the specs |
| Lamp effects | leff shows | none (leff ids and priorities are tracked) | interim |
| Side choice (task 200) | the choice at game start, deff 40 / 41 | runs on each player's first ball, a flipper switches the side, Decepticon kept when nobody chooses; ends 37 ticks after the launch (tf/features/side.py) | inferred, until the rules spec |
| Pricing | the ROM's pricing tables | Tron's USA 25c pricing | interim (inferred) |
| Service menu in a game | suspends the game task | asks END GAME? (Tron recreation, MPF timers cannot be suspended) | MPF limit |
