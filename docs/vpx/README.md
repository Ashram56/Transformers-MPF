# VPX extraction: Transformers Pro (Stern 2011)

Agent B of the master plan ([vpx_extraction.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/vpx_extraction.md)),
run 2026-10-08 on `Transformers Pro (Stern 2011) v.2.4.vpx` (VR-Hybrid mod by RobbyKingPin et al., based on
JPSalas' VPX table; simulates the Pro, PinMAME set `tf_180`).

```
python tools/vpx/vpx_extract.py "Transformers Pro (Stern 2011) v.2.4.vpx" out
python tools/vpx/vpx_map.py out --names rom/mpf_package/config/{switches,lights,coils}.yaml game/config/hardware.yaml \
    --mech 43:opr,44:opr,42:kickermegatron --cabinet
```

(tools in Ashram56/Stern-SAM-Decryption; this table needed the cvpmTrough, InitSaucer, VPW StandupTarget,
SolModCallback flasher and collection-aware vpmMapLights patterns, and `--cabinet`, added there.)

## What is here

| File | What |
|---|---|
| `game/monitor/playfield.jpg` | The table's playfield image `pf` (3608x8192), scaled to 1000x2271 |
| `game/monitor/monitor.yaml` | MPF Monitor layout: 62 switches (19 on the cabinet strip), 61 lamps, 12 flashers (under `coil:`) |
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
- Switches on the playfield (43): 1-8, 10-14, 18-32, 34, 35, 37-46, 49-51.
  - Trough 18-21 (cvpmTrough) stacked at `BallRelease`; 22 is its own `sw22` trigger.
  - 38-41 Megatron lock (`bsKickerMegaTron`), stacked at `KickerMegaTron`. 3 is the left saucer `sw3`.
  - 43, 44: Optimus Prime up/down (`s_optimus_prime_up`, `s_optimus_prime_down`), set by a motor timer
    (no object): placed at `opr` with `--mech`; 42 (Megatron jam, no object either) after the lock slots.
  - 23 is the shooter lane.
- **Cabinet strip** (`--cabinet`, the bottom edge of the picture, by number): the 19 config switches with no
  playfield object: tournament and start buttons (15, 16), coin slots (D1-D5), flipper buttons and EOS
  (D9-D12), tilt, slam tilt, ticket notch (D17-D19), coin door open (D20, from `game/config/hardware.yaml`),
  BACK, MINUS, PLUS, SELECT (D21-D24). Lamps 1 and 2 (start and tournament buttons, below the playfield in
  the table) sit just above the strip.
- Lamps (61): 1-62 without 56, which the ROM's lamp list doesn't use either.
- Flashers (12, solenoid numbers): 17, 18, 19, 20, 21, 23, 25, 26, 27, 28, 31, 32. Six are Flupper domes
  (`Flasherlight1-6`). The ROM names 26 "Flash: Slingshot (Left)" and 27 "(Right)", but the table's sub for
  26 flashes dome 1, which sits on the right, and 27 dome 2 on the left: the positions follow the table.
- Overlay checked by eye: lamp and switch markers sit on their inserts, rollovers and targets.

## For the owner

1. Flashers 26 and 27 (slingshot domes) are on the opposite sides from their ROM names: swap them in
   MPF Monitor if the real machine has them the other way round.
2. Flippers, autofires (slings, pops), ball devices and plain coils have no VPX object and are not in
   `monitor.yaml` yet: the recreation agent adds them near their parts.
