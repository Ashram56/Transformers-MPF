# Transformers Pro 1.80 in MPF

The Stern Transformers Pro game (ROM `tf_180`, v1.80) rebuilt on the [Mission Pinball Framework](https://missionpinball.org)
0.80 with the Godot media controller (GMC), from the ROM extraction in [rom/](rom/README.md). The goal is the ROM's
game exactly; departures are listed in [docs/rom_differences.md](docs/rom_differences.md).

## Install (Windows, one line)

PowerShell or cmd. It installs what is missing (Git, Python 3.11), clones this repository into
`%USERPROFILE%\Transformers-MPF` and runs `scripts\setup.py` (Godot, MPF, GMC, the media). With `-Vpx` (and
`-Table <your .vpx>`) it also sets up Visual Pinball X ([docs/vpx.md](docs/vpx.md)):

```powershell
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ashram56/Transformers-MPF/claude/pup-pack/scripts/install/install_prereqs_windows.ps1))) -Vpx -Table 'C:\Visual Pinball\Tables\Transformers Pro (Stern 2011) v.2.4.vpx'"
```

Without VPX: `powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Ashram56/Transformers-MPF/claude/pup-pack/scripts/install/install_prereqs_windows.ps1 | iex"`. Options:
`-NoMonitor`, `-DryRun` (the plan only), `-Yes` (no questions); `$env:TF_DIR` / `$env:TF_BRANCH` before the line
change the folder and branch. Safe to run again: it updates the clone and redoes only what changed.

## Run it

```
python scripts/setup.py          # venv with MPF, Godot 4.6.3, GMC, generated config and media
python scripts/run.py            # the DMD window and MPF on virtual hardware (free play)
python scripts/run.py --monitor  # plus MPF Monitor with the playfield picture
```

Keys in the DMD window: `5` coin, `1` start, `z` / `/` flippers, `space` plunge, `t` tilt, `d` coin door,
`7 8 9 0` BACK MINUS PLUS SELECT. Tests: `.venv/bin/python -m pytest -q tests`. Display check:
`.venv/bin/python scripts/render_check.py` (captures/dmd_latest_x8.png).

## PuP Pack (optional): videos and music on three screens

The game can play TerryRed's Transformers (Stern) PuP-Pack, the videos and music PinUP Player shows around the
Visual Pinball table, at the same moments, on a backglass window (with the pack's crests, faces and text panel),
the DMD in the pack's panel art and an optional topper; the pack's music replaces the ROM music. The pack is
TerryRed's work: download it from the author's page. `setup.py` installs it from the private `pup_pack`
submodule, or from the author's zip with `TF_PUP_ZIP=<zip>`; `TF_PUP=0` turns it off (the strict game).
Screens, settings and how it works: [docs/pup.md](docs/pup.md).

## Status

| Area | State |
|---|---|
| OS (ball handling, validation, ball save, tilt, end of ball, match, credits, adjustments, audits) | Ported from the Tron recreation; tf_180's deff, leff, sound call, adjustment and audit tables match Tron's numbering (code); the 98 adjustments, 166 audits and service menu from the ROM extraction's settings package; the 68 pricing presets (rom/rom_data/settings/pricing.json) |
| Devices | ROM names and numbers (rom/mpf_package); trough, shooter lane, left eject, Megatron lock |
| Display | ROM fonts (all 27); one slide per captured display effect (128, the ROM's frames and timing) with the live status panel (100 effects); score display drawn from its captured draw calls; printf texts in 71 effects drawn live from their ROM formats, fit-font numbers in the font the ROM picks (tf/deff_values.gd) |
| Sound | every ROM sample, one pool per sound call; music intros play once and the body loops; base music by side (Autobot / Decepticon), coin, tilt, launch, ball save and drain sounds as traced; each deff plays its captured sounds |
| Coils | the pulse and hold times measured in the emulator (rom/mpf_package/config/coils.yaml) |
| Lamp shows | every captured leff (111 shows in rom/mpf_package/config/shows) plays at its ROM priority with its flasher pulses; leffs the ROM draws from game state (67, no show) draw nothing yet. `trace_check.py basic`: lamps 46/47 samples, flashers 3/7 bursts |
| Rules, scoring | switch handlers, side choice, skill shots, pops, lanes, spinner, Bumblebee and double scoring, 2-bank and fast scoring, combos, shot multipliers, bonus, Energon targets, the Allspark (left eject) mystery award, mode-start shots, the eight character battles, the Megatron lock and multiball, the Optimus battle and multiball (Autobot and Decepticon rules), All Hail Megatron / Autobots Roll Out and the Wizard Multiball, the shaker motor by adj 96, the Optimus figure's motor and hit kicker, the orbit gate and the ball search's coil sweep (tf/features/, from rom/rules/modes/; shaker, Optimus and gate runs match every trace where the play matches). Scores, display effects and audits match the ROM, in order, in all 24 reference traces (`trace_check.py`; `combos` reads its mode-start relight picks from its mode-start scores); the timing differences left (0.3-0.9 s, speech-driven deff lengths, the Allspark warning, the bonus end in `allspark_energon`) are rows of docs/rom_differences.md. Every ball search and Optimus kicker run lands where the ROM's does |
| PuP Pack | optional, TerryRed's pack on backglass, DMD and topper windows with its music ([docs/pup.md](docs/pup.md)); 210 of the 213 DMD captures its active rows use are mapped to game events |
| Hardware | virtual (desktop + MPF Monitor) by default; P-ROC numbers generated (game/config/rom/proc_numbers.yaml); VPX bridge is agent D's |

Interim tables read from the ROM until the package carries them: `game/config/interim/` (scripts/interim_tables.py,
scripts/interim_fonts.py; both need `TF_ROM=<path to tf_180.bin>`).
