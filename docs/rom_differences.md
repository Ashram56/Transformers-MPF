# Departures from the ROM

Every place the game differs from tf_180, why, and what replaces it. Interim rows go away when the ROM
extraction delivers the data.

| Area | ROM | Here | Kind |
|---|---|---|---|
| Score display (deff 19) | 0x0102fb8c | drawn live from the captured draw calls; the dim level of players not up and the font for scores wider than 87 dots are inferred (tf/score_screen.py) | inferred details |
| Display effects with values | the ROM prints live values (scores, counts, credits, high scores) | the printf texts of 59 effects are cleared from the captured frames and drawn live from their ROM format (scripts/gen_media.py value_texts), with the values the rules pass (pop: 3,170; bonus: count value and total; which RAM value each text prints is inferred); a slot with no value keeps the capture's string, and texts in moving frames or drawn with fit fonts (bonus 1X) stay as captured; the status panel is live | interim, until A gives each text's argument source |
| Deffs without frames (39) | they draw live state or nothing in the capture window | nothing drawn (the previous screen stays) | interim |
| Scoring and rules | switch handlers and the features they call | as the ROM for the handlers, slings, pops, lanes, spinner, Bumblebee, 2-bank, combos, shot multipliers, skill shots, Energon, the Allspark award, mode-start shots and the eight battles (rom/rules/modes/*.md; tf/features/). Missing until their specs: Optimus, the Megatron lock, the wizard modes, super pops / super spinner play; the roving 3X and the combo arrows (leff 34) are not drawn. Inferred: double scoring's end split, the right orbit ignore windows (3 s after a left orbit pass, the center lane, a plunge or the back door), the battle hit deffs' lengths | interim, until the specs |
| Battle and Energon deffs without frames | deffs 94, 96, 111, 118, 119, 124, 125 have no capture | lengths, leffs and sounds from the traces (tf/features/battles.py UNCAPTURED, energon.py); nothing drawn | inferred |
| Battle hit deff sounds | each hit deff picks its callouts by hit index and chains follow-ups (e.g. Blackout 0x1c3 then 0x1c4, [0x0101db34]) | the hit sound with its index; the chained follow-ups are not played | interim |
| Ball search at a drain | a search that starts just after a drain is cut short when the trough sees the ball | the search runs its full length, so the bonus can start up to 0.6 s later (battle_blackout) | timing |
| Bonus | (670 x count + held) x multiplier | as the ROM (combos_and_multipliers.md 7), checked against every trace's bonus | |
| Lamp effects | leff shows | the 111 captured shows play at the ROM priority with their flasher pulses; the 67 leffs the ROM draws from game state (tag `code` in rom/rom_data/io/lamp_effects.csv, e.g. 14 ball save, 97 / 100 lanes) draw nothing until their features draw them | interim, until each feature draws its leff |
| Side choice (task 200) | each player's choice, starting side by adj 65 | runs on each player's first ball; adj 65 RANDOM uses the game's random generator (the ROM's source is not identified) | inferred |
| Custom pricing | SET CUSTOM PRICING edits a coin door and a ladder of up to 100 steps (NVRAM 0x2110808) | one units-per-coin and one units-per-credit value; the 68 presets are the ROM's (pricing.json) | interim |
| Service menu in a game | suspends the game task | asks END GAME? (Tron recreation, MPF timers cannot be suspended) | MPF limit |
