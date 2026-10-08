# Departures from the ROM

Every place the game differs from tf_180, why, and what replaces it. Interim rows go away when the ROM
extraction delivers the data.

| Area | ROM | Here | Kind |
|---|---|---|---|
| Score display (deff 19) | 0x0102fb8c: scores by FUN_0102f200, status panel by FUN_0102fa40 (not decoded) | ROM fonts in a plain layout: current score large, others small, ball and credits on the bottom row (tf/score_screen.py) | interim, until captured |
| Attract (deff 1) | 0x0103c584, the attract show | GAME OVER and the credits in ROM fonts | interim, until captured |
| Other display effects | frames, timing and text per deff | nothing drawn (the previous screen stays) | interim, until captured |
| Scoring and rules | switch handlers per the rules specs | no points; outlanes start the ball save only | interim, until the specs |
| Lamp effects | leff shows | none (leff ids and priorities are tracked) | interim |
| Coil drive times | per coil | MPF defaults | interim, until decoded |
| Pricing | the ROM's pricing tables | Tron's USA 25c pricing | interim (inferred) |
| Service menu in a game | suspends the game task | asks END GAME? (Tron recreation, MPF timers cannot be suspended) | MPF limit |
