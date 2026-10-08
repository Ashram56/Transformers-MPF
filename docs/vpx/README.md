# VPX extraction: Transformers Pro (Stern 2011)

Agent B of the master plan ([vpx_extraction.md](https://github.com/Ashram56/Tron-Legacy-MPF/blob/main/docs/agents/vpx_extraction.md)),
run 2026-10-08 on `Transformers Pro (Stern 2011) v.2.4.vpx` (VR-Hybrid mod by RobbyKingPin et al., based on
JPSalas' VPX table; simulates the Pro, PinMAME set `tf_180`).

```
python scripts/vpx_extract.py "Transformers Pro (Stern 2011) v.2.4.vpx" out
python scripts/vpx_map.py out --mech 43:opr,44:opr
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

**Names are placeholders** (`s_NN_<vpx>`, `l_NN_<vpx>`, `f_NN_<vpx>`) carrying the SAM number: the ROM
extraction's MPF config was not available yet. Rerun `vpx_map.py out --names switches.yaml lights.yaml coils.yaml
--mech 43:opr,44:opr` when it is, or rename by number.

## Run values (to check a rerun)

- Bounds 0, 0, 952, 2164; playfield `pf` 3608x8192 (GameData IMAG); 386 images (no legacy BITS); 1,106 items;
  31 collections; `switches_all.csv` 529 rows, `lights_all.csv` 251.
- Switches (42): 1-8, 10-14, 18-32, 34, 35, 37-41, 43-46, 49-51.
  - Trough 18-21 (cvpmTrough) stacked at `BallRelease`; 22 is its own `sw22` trigger.
  - 38-41 Megatron lock (`bsKickerMegaTron`), stacked at `KickerMegaTron`. 3 is the left saucer `sw3`.
  - 43, 44: Optimus Prime ramp position switches, set by a motor timer (no object): placed at `opr` with
    `--mech` (inferred: 44 at the top of the motor travel, 43 at the bottom).
  - 23 is the shooter lane, 15/16 the flipper buttons (cabinet, not placed), -7 the tilt.
- Lamps (61): 1-62 without 56 (no object in the table). Lamps 1 and 2 (`li1`, `li2`) sit **below the
  playfield** (y 1.03, apron or cabinet buttons): MPF Monitor puts them off the picture.
- Flashers (12, solenoid numbers): 17, 18, 19, 20, 21, 23, 25, 26, 27, 28, 31, 32. Six are Flupper domes
  (`Flasherlight1-6`). The script comments call 26 "Slingshot (Left)" and 27 "Slingshot (Right)", but sub 26
  flashes dome 1, which sits on the right, and 27 dome 2 on the left: the positions follow the objects.
- Overlay checked by eye: lamp and switch markers sit on their inserts, rollovers and targets.

## For the owner

1. Lamp 56 has no object in the table, and lamps 1-2 are below the playfield: keep, move or drop them in MPF
   Monitor.
2. Flippers, autofires (slings, pops), ball devices and plain coils have no VPX object and are not in
   `monitor.yaml` yet: the recreation agent adds them near their parts once the config names exist.
