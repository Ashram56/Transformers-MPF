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
| Display | ROM fonts (all 27); one slide per captured display effect (113, the ROM's frames and timing) with the live status panel; score display drawn from its captured draw calls. Values inside other effects are still the capture's |
| Sound | every ROM sample, one pool per sound call; music intros play once and the body loops; base music by side (Autobot / Decepticon), coin, tilt, launch, ball save and drain sounds as traced; each deff plays its captured sounds |
| Coils | the pulse and hold times measured in the emulator (rom/mpf_package/config/coils.yaml) |
| Rules, scoring, lamp shows | waiting on the ROM extraction's specs; `scripts/trace_check.py basic` matches the reference up to the first scoring switch |
| Hardware | virtual (desktop + MPF Monitor) by default; P-ROC numbers generated (game/config/rom/proc_numbers.yaml); VPX bridge is agent D's |

Interim tables read from the ROM until the package carries them: `game/config/interim/` (scripts/interim_tables.py,
scripts/interim_fonts.py; both need `TF_ROM=<path to tf_180.bin>`).
