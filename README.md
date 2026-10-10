# Transformers MPF

Stern's **Transformers Pro** (code v1.80, ROM `tf_180`) rebuilt in the Mission Pinball Framework (MPF 0.80.1)
with a Godot DMD (GMC 1.0.0 on Godot 4.6.3), from the rules, sounds, display effects and lamp shows reverse
engineered out of the ROM in [rom/](rom/README.md). The goal is the ROM's game exactly; every departure is
listed in [docs/rom_differences.md](docs/rom_differences.md). It runs on Windows, macOS and Linux, on a desktop
or in Visual Pinball X instead of PinMAME, and can play TerryRed's PuP Pack on extra screens.

**Working with Claude, or rebuilding another Stern SAM game this way?** Start at the
[master plan](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/README.md) in Stern-SAM-Decryption: what to
provide (ROM, VPX table) and the agents that do the work. This game's map of which agent owns which files is
[CLAUDE.md](CLAUDE.md).

## Install

Run the line for your OS in a terminal. It installs what is missing (Git, Python 3.11, the libraries), clones
this repository into a `Transformers-MPF` folder in your home folder, and runs `scripts/setup.py`, which
downloads Godot, MPF and GMC, builds the media from the ROM extraction and sets up the PuP Pack. The first run
takes a while.

**Windows 10/11** (PowerShell or cmd):

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Ashram56/Transformers-MPF/main/scripts/install/install_prereqs_windows.ps1 | iex"
```

**Windows with Visual Pinball X** (put your table's path after `-Table`; [docs/vpx.md](docs/vpx.md)):

```powershell
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ashram56/Transformers-MPF/main/scripts/install/install_prereqs_windows.ps1))) -Vpx -Table 'C:\Visual Pinball\Tables\Transformers Pro (Stern 2011) v.2.4.vpx'"
```

**macOS 12+:**

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Ashram56/Transformers-MPF/main/scripts/install/install_prereqs_macos.sh)
```

**Linux** (Debian/Ubuntu, Fedora, Arch):

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Ashram56/Transformers-MPF/main/scripts/install/install_prereqs_linux.sh)
```

You can change where the files go, and what is installed:

- **Folder:** set `TF_DIR` before running the line. Windows: `$env:TF_DIR = "D:\Transformers"` first.
  macOS / Linux: `TF_DIR=~/games/transformers bash <(curl ...)`. The default is `%USERPROFILE%\Transformers-MPF`
  on Windows, `~/Transformers-MPF` elsewhere.
- **Branch / repository:** `TF_BRANCH` (default `main`) and `TF_REPO`, the same way. A folder that already holds
  a clone is updated with `git pull --ff-only`; a clone of a branch since deleted on GitHub moves to `main`.
- **The PuP Pack:** the pack is TerryRed's work. Download TerryRed's Transformers (Stern) PuP-Pack from the
  author's page and give its zip with `TF_PUP_ZIP` (a file or an https URL): Windows
  `$env:TF_PUP_ZIP = "C:\Downloads\Transformers PuP-Pack.zip"` first, macOS / Linux
  `TF_PUP_ZIP=~/Downloads/<the zip> bash <(curl ...)`. `TF_PUP=0` leaves the PuP out (the strict ROM game,
  ROM music). Without either, setup takes the pack from the private `pup_pack` submodule (the owner's copy);
  without access to it, the game installs without the PuP.
- **Private repositories:** when a repository the install needs is private (the `pup_pack` submodule), the
  installer asks for a GitHub token that can read it (github.com > Settings > Developer settings > Personal
  access tokens; a fine-grained token with Contents: read-only), instead of a password. On macOS and Linux,
  press Enter at that prompt to install without the PuP. On Windows, paste the token with a right-click:
  Ctrl+V does not paste into the hidden prompt. Or give it before the line so nothing is asked: Windows
  `$env:TF_GITHUB_TOKEN = "github_pat_..."` first, macOS / Linux `TF_GITHUB_TOKEN=github_pat_... bash <(curl ...)`.
- **Options:** on macOS and Linux they go after the line, for example `bash <(curl ...) --no-monitor` to leave
  MPF Monitor out, `--dry-run` to see the plan first, `--yes` for no questions. On Windows:
  `powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm <the URL above>))) -NoMonitor"`
  (also `-DryRun`, `-Yes`, `-Vpx`, `-Table`). `--proc` / `-Proc` installs the P-ROC driver only: the game has
  no P-ROC run yet ([docs/hardware.md](docs/hardware.md)).

On Windows, keep the folder out of OneDrive (the default, your home folder, is): OneDrive locks and
read-protects files while it syncs them. Requirements per OS: [docs/requirements.md](docs/requirements.md).

**Clone first** (if the lines above cannot fetch the script). Install Git, then:

```sh
git clone https://github.com/Ashram56/Transformers-MPF.git
cd Transformers-MPF
scripts/install/install_prereqs_linux.sh          # or install_prereqs_macos.sh
```

On Windows: `powershell -ExecutionPolicy Bypass -File scripts\install\install_prereqs_windows.ps1` (add
`-Vpx -Table '<your .vpx>'` for Visual Pinball X).

## Play

From the install folder:

| | Windows | macOS / Linux |
|---|---|---|
| Start the game | `.venv\Scripts\python scripts\run.py` | `.venv/bin/python scripts/run.py` |
| ... with MPF Monitor (the playfield picture, click the switches) | `... run.py --monitor` | `... run.py --monitor` |
| ... in Visual Pinball X | `... run.py --hw vpx`, then start the table ([docs/vpx.md](docs/vpx.md)) | (VPX runs on Windows only) |

The game starts in **free play**: START begins a game without a coin. `--no-free-play` keeps the factory
pricing (insert coins with key `5`). `Ctrl+C` in the terminal (or `Esc` in MPF's text UI) quits; Godot's log is
`game/logs/godot.log`. With the PuP on, `run.py` prints `PuP on: ...` (or what is missing) before it starts the
windows.

With the DMD window focused, keys close the machine's switches (`game/gmc.cfg`, `[keyboard]`); in MPF Monitor,
click a switch instead.

| Key | Switch |
|---|---|
| `5` | coin (right coin slot) |
| `1` | START |
| `Space` | plunge: the ball leaves the shooter lane |
| `Z` / `/` (or `←` / `→`) | left / right flipper |
| `T` | tilt (plumb bob) |
| `D` | coin door open / closed |
| `7` `8` `9` `0` | service buttons BACK, MINUS, PLUS, SELECT |

## Settings

`scripts/run.py` takes the options; `python scripts/run.py --help` lists them all:

- `--monitor`: also MPF Monitor, with the VPX table's playfield picture and every switch, lamp and flasher on it.
- `--hw vpx`: the Visual Pinball X table, with MPF instead of PinMAME (Windows; the `-Vpx` install first,
  [docs/vpx.md](docs/vpx.md)).
- `--no-free-play`: coins as on the factory settings (the 98 adjustments and the service menu are the ROM's).
- `--dmd-size 1024x256`: the DMD window's size.
- `--scenario NAME`: plays a rule trace from `rom/rules/traces/` in real time; `--seconds N` stops after N
  seconds; `--trace FILE` writes MPF's trace.

The PuP Pack's settings (screens, topper, the pack's music or the ROM's) go in `game/pup.local.cfg`; the
environment overrides them for one run: `TF_PUP=0` (PuP off), `TF_VIDEO_PLAYER=native` (Windows' other video
player). [docs/pup.md](docs/pup.md) has them all.

## PuP Pack (optional): videos and music on three screens

The game can play **TerryRed's Transformers (Stern) PuP-Pack**, the videos and music PinUP Player shows around
the Visual Pinball table, at the same moments: a backglass window (with the pack's crests, faces and text
panel), the DMD in the pack's panel art and an optional topper; the pack's music replaces the ROM music. The
pack is TerryRed's work, credited to the author: get it from TerryRed's download page and install it with
`TF_PUP_ZIP` (above). The videos play as they are, decoded on the GPU (GoZen on Windows and Linux,
AVFoundation on macOS). Screens, settings and how it works: [docs/pup.md](docs/pup.md).

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

## Update

From the install folder: `git pull`, then `python3 scripts/setup.py` (Windows: `py -3.11 scripts\setup.py`).
You can also run the install line again. Both are safe to repeat; setup only redoes what changed.

## Tests

`.venv/bin/python -m pytest -q tests` (Windows: `.venv\Scripts\python -m pytest -q tests`). The display check:
`.venv/bin/python scripts/render_check.py` (writes `captures/dmd_latest_x8.png`); the rules against the ROM's
reference traces: `.venv/bin/python scripts/trace_check.py basic` (any trace in `rom/rules/traces/`). CI runs the
tests on Windows, macOS and Linux, and the render check on Linux, for every push to `main`.

## More

- [docs/requirements.md](docs/requirements.md): what a computer needs, per OS.
- [docs/vpx.md](docs/vpx.md): Visual Pinball X played by MPF.
- [docs/pup.md](docs/pup.md): the PuP Pack on three screens.
- [docs/hardware.md](docs/hardware.md): virtual hardware and the P-ROC numbers.
- [docs/rom_differences.md](docs/rom_differences.md): where the game differs from the ROM, and ROM quirks that are not bugs.
- [rom/README.md](rom/README.md): the ROM extraction (tables, sounds, display effects, MPF package, tools). The
  ROM itself is never in this repository.
- [CLAUDE.md](CLAUDE.md): which AI agent owns which files; the agents and the master plan are in
  [Stern-SAM-Decryption](https://github.com/Ashram56/Stern-SAM-Decryption).

## Credits

The game, its rules, sounds and display are Stern Pinball's (Transformers, 2011). The PuP Pack is TerryRed's.
The Visual Pinball X table used for the playfield picture and the VPX bridge is Transformers Pro (Stern 2011)
v.2.4 by its authors. MPF and GMC are the Mission Pinball Framework project's; Godot is the Godot Engine's.
