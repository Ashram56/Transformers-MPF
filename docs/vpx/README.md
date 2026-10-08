# VPX extraction: Transformers Pro (Stern 2011)

Agent B of the master plan ([vpx_extraction.md](https://github.com/Ashram56/Tron-Legacy-MPF/blob/main/docs/agents/vpx_extraction.md)),
run 2026-10-08 on `Transformers Pro (Stern 2011) v.2.4.vpx` (VR-Hybrid mod by RobbyKingPin et al., based on
JPSalas' VPX table; simulates the Pro, PinMAME set `tf_180`).

```
python scripts/vpx_extract.py "Transformers Pro (Stern 2011) v.2.4.vpx" out
python scripts/vpx_map.py out --names rom/mpf_package/config/{switches,lights,coils}.yaml --mech 43:opr,44:opr
```

(scripts from Ashram56/Tron-Legacy-MPF; this table needed the cvpmTrough, InitSaucer, VPW StandupTarget,
SolModCallback flasher and collection-aware vpmMapLights patterns added there.)

## What is here

| File | What |
|---|---|
| `game/monitor/playfield.jpg` | The table's playfield image `pf` (3608x8192), scaled to 1000x2271 |
| `game/monitor/monitor.yaml` | MPF Monitor layout: 42 switches, 61 lamps, 12 flashers (under `coil:`) |
| `docs/vpx/switches.csv`, `lights.csv` | Numbered devices with VPX object, table units and fractions |
| `docs/vpx/switches_all.csv`, `lights_all.csv` | Every candidate object, numbered or not |
| `docs/vpx/overlay.jpg` | Markers on the playfield (S = switch, L = lamp, F = flasher) |

The table script (`script.vbs`, 4,891 lines) and `items.json` are in the project's files
(`/mnt/project-files/vpx_extraction/`), not here: the script is the table authors' work.

**Names are the ROM extraction's MPF config names** (`rom/mpf_package/config/` on branch
`claude/rom-extraction-uayj13`), joined by number: every placed device has one, no placeholders left.

## Run values (to check a rerun)

- Bounds 0, 0, 952, 2164; playfield `pf` 3608x8192 (GameData IMAG); 386 images (no legacy BITS); 1,106 items;
  31 collections; `switches_all.csv` 529 rows, `lights_all.csv` 251.
- Switches (42): 1-8, 10-14, 18-32, 34, 35, 37-41, 43-46, 49-51.
  - Trough 18-21 (cvpmTrough) stacked at `BallRelease`; 22 is its own `sw22` trigger.
  - 38-41 Megatron lock (`bsKickerMegaTron`), stacked at `KickerMegaTron`. 3 is the left saucer `sw3`.
  - 43, 44: Optimus Prime up/down (`s_optimus_prime_up`, `s_optimus_prime_down`), set by a motor timer
    (no object): placed at `opr` with `--mech`.
  - 23 is the shooter lane; 15/16 the tournament and start buttons (cabinet, not placed); -7 the tilt.
- Lamps (61): 1-62 without 56, which the ROM's lamp list doesn't use either. Lamps 1 and 2 (start and
  tournament buttons) sit **below the playfield** (y 1.03): MPF Monitor puts them off the picture.
- Flashers (12, solenoid numbers): 17, 18, 19, 20, 21, 23, 25, 26, 27, 28, 31, 32. Six are Flupper domes
  (`Flasherlight1-6`). The ROM names 26 "Flash: Slingshot (Left)" and 27 "(Right)", but the table's sub for
  26 flashes dome 1, which sits on the right, and 27 dome 2 on the left: the positions follow the table.
- Overlay checked by eye: lamp and switch markers sit on their inserts, rollovers and targets.

## For the owner

1. Lamps 1-2 (start and tournament buttons) are below the playfield: keep, move or drop them in MPF Monitor.
2. Flashers 26 and 27 (slingshot domes) are on the opposite sides from their ROM names: swap them in
   MPF Monitor if the real machine has them the other way round.
3. Flippers, autofires (slings, pops), ball devices and plain coils have no VPX object and are not in
   `monitor.yaml` yet: the recreation agent adds them near their parts.
