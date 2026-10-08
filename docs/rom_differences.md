# Departures from the ROM

Every place the game differs from tf_180, why, and what replaces it. Interim rows go away when the ROM
extraction delivers the data.

| Area | ROM | Here | Kind |
|---|---|---|---|
| Score display (deff 19) | 0x0102fb8c | drawn live from the captured draw calls; the dim level of players not up and the font for scores wider than 87 dots are inferred (tf/score_screen.py) | inferred details |
| Display effects with values | the ROM prints live values (scores, counts, credits, high scores) | the printf texts of 59 effects are cleared from the captured frames and drawn live from their ROM format (scripts/gen_media.py value_texts), with the values the rules pass (pop: 3,170; bonus: count value and total; which RAM value each text prints is inferred); a slot with no value keeps the capture's string, and texts in moving frames or drawn with fit fonts (bonus 1X) stay as captured; the status panel is live | interim, until A gives each text's argument source |
| Deffs without frames (39) | they draw live state or nothing in the capture window | nothing drawn (the previous screen stays) | interim |
| Scoring and rules | switch handlers and the features they call | handler points, slingshots and pop bumpers as traced (tf/switches.py); the lanes award their most frequent result (2500, 0x169 / 0x16d); pop values do not rise on quick repeat hits (traces/basic: 3170, 4170, 5170); no feature rules yet (Bumblebee, Energon, shots, 2-bank, spinner, Optimus, Megatron) | interim, until the specs |
| Bonus | 670 x count + held, x multiplier | the formula and the deff's timing; no shot adds count or multiplier yet | interim |
| Lamp effects | leff shows | the 111 captured shows play at the ROM priority with their flasher pulses; the 67 leffs the ROM draws from game state (tag `code` in rom/rom_data/io/lamp_effects.csv, e.g. 14 ball save, 97 / 100 lanes) draw nothing until their features draw them | interim, until each feature draws its leff |
| Side choice (task 200) | each player's choice? | runs on each player's first ball (one-player traces only) | inferred |
| Pricing | the ROM's pricing tables | Tron's USA 25c pricing | interim (inferred) |
| Service menu in a game | suspends the game task | asks END GAME? (Tron recreation, MPF timers cannot be suspended) | MPF limit |
