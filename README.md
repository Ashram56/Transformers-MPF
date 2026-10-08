# Transformers Pro 1.80 in MPF

The Stern Transformers Pro game (ROM `tf_180`, v1.80) rebuilt on the [Mission Pinball Framework](https://missionpinball.org)
0.80 with the Godot media controller (GMC), from the ROM extraction in [rom/](rom/README.md). The goal is the ROM's
game exactly; departures are listed in [docs/rom_differences.md](docs/rom_differences.md).

## Run it

```
python scripts/setup.py          # venv with MPF, Godot 4.5.2, GMC, generated config and media
python scripts/run.py            # the DMD window and MPF on virtual hardware (free play)
python scripts/run.py --monitor  # plus MPF Monitor with the playfield picture
```

Keys in the DMD window: `5` coin, `1` start, `z` / `/` flippers, `space` plunge, `t` tilt, `d` coin door,
`7 8 9 0` BACK MINUS PLUS SELECT. Tests: `.venv/bin/python -m pytest -q tests`. Display check:
`.venv/bin/python scripts/render_check.py` (captures/dmd_latest_x8.png).

## Status

| Area | State |
|---|---|
| OS (ball handling, validation, ball save, tilt, end of ball, match, credits, adjustments, audits) | Ported from the Tron recreation; tf_180's deff, leff, sound call, adjustment and audit tables match Tron's numbering (code) |
| Devices | ROM names and numbers (rom/mpf_package); trough, shooter lane, left eject, Megatron lock |
| Display | ROM fonts (all 27); one slide per captured display effect (128, the ROM's frames and timing) with the live status panel (100 effects); score display drawn from its captured draw calls; printf texts in 59 effects drawn live from their ROM formats (tf/deff_values.gd) |
| Sound | every ROM sample, one pool per sound call; music intros play once and the body loops; base music by side (Autobot / Decepticon), coin, tilt, launch, ball save and drain sounds as traced; each deff plays its captured sounds |
| Coils | the pulse and hold times measured in the emulator (rom/mpf_package/config/coils.yaml) |
| Lamp shows | every captured leff (111 shows in rom/mpf_package/config/shows) plays at its ROM priority with its flasher pulses; leffs the ROM draws from game state (67, no show) draw nothing yet. `trace_check.py basic`: lamps 46/47 samples, flashers 3/7 bursts |
| Rules, scoring | switch handlers, slings, pops, side choice and bonus as traced; feature rules wait on the ROM extraction's specs; `scripts/trace_check.py basic` matches up to the second pop hit |
| Hardware | virtual (desktop + MPF Monitor) by default; P-ROC numbers generated (game/config/rom/proc_numbers.yaml); VPX bridge is agent D's |

Interim tables read from the ROM until the package carries them: `game/config/interim/` (scripts/interim_tables.py,
scripts/interim_fonts.py; both need `TF_ROM=<path to tf_180.bin>`).
