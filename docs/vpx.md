# Visual Pinball X: the Transformers Pro table played by MPF

The "Transformers Pro (Stern 2011) v.2.4" table (VR-Hybrid mod of JPSalas' table, ROM `tf_180`) was written for
PinMAME running the ROM. With the `hw_vpx` overlay, Visual Pinball X keeps doing what it does well (the ball, the
playfield, the mechanical sounds) and **this MPF game replaces PinMAME**: MPF runs the rules, Godot draws the DMD
and plays the ROM's speech, music and effects. The table file is not modified.

```
VPX table script --COM--> TransformersMPF.Controller --BCP 5051--> MPF (hw_vpx, virtual_pinball) --BCP 5050--> Godot
 (core.vbs, sam.vbs)       scripts/vpx_bridge.py                    game/tf/vpx_hardware.py                  (DMD, sound)
```

| Piece | What it does |
|---|---|
| `scripts/vpx_table.py` | Reads the script out of the `.vpx` and writes `<table name>.vbs` next to it. VPX (10.7 and later) loads a `.vbs` with the table's name instead of the script inside the table, so the table plays with MPF while the `.vbs` is there and with PinMAME once it is deleted or renamed. The changes: `LoadVPM ... "SAM.VBS"` becomes `LoadMPF "SAM.VBS"`, which loads the same VPinMAME helper scripts and creates `TransformersMPF.Controller` instead of `VPinMAME.Controller`, and one line in the table's KeyDown makes `End` open and close the coin door. Rewriting the `.vpx` itself is not an option: VPX refuses a table whose script changed without its MAC hash being recomputed. |
| `scripts/vpx_bridge.py` | The `TransformersMPF.Controller` COM server (pywin32, out of process). Each controller call becomes an MPF `vpcom_bridge` BCP command, the protocol of MPF's `virtual_pinball` platform and of [mpf-vpcom-bridge](https://github.com/missionpinball/mpf-vpcom-bridge). `Run` starts the game when it is not running yet. `Stop` (the table closing) quits the game it started. |
| `game/config/hw_vpx.yaml` | The overlay: platform `virtual_pinball`, PinMAME's numbers for the SAM dedicated switches, the flippers, the sling and pop bumper autofires. |
| `game/tf/vpx_hardware.py` | Makes MPF answer as VPinMAME does (see "Device map"). |

## Set-up (Windows, once)

**One line** (PowerShell or cmd; put your table's path after `-Table`). It installs what is missing (Git,
Python 3.11), clones this repository into `%USERPROFILE%\Transformers-MPF`, runs `scripts\setup.py --vpx`
(Godot, MPF, GMC, the media, olefile and pywin32), registers the bridge (Windows asks once for administrator
rights) and writes the table's MPF script next to the table:

```powershell
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ashram56/Transformers-MPF/main/scripts/install/install_prereqs_windows.ps1))) -Vpx -Table 'C:\Visual Pinball\Tables\Transformers Pro (Stern 2011) v.2.4.vpx'"
```

Run again, it updates the clone (`git pull`) and redoes only what changed. `$env:TF_DIR` / `$env:TF_BRANCH` set
before the line change the folder and branch (default `main`). Without `-Table`, step 3 below writes the table's script later.

By hand, the same steps:

1. The workspace as usual (`python scripts\setup.py`), plus the bridge's packages:
   `python scripts\setup.py --vpx` (olefile and pywin32).
2. Register the COM server, in a terminal opened **as Administrator**, in the repo folder:
   `.venv\Scripts\python scripts\vpx_bridge.py --register`
   (`--unregister` removes it). It is registered with this repo's path and venv: register again after moving
   the repo. If the table then says it cannot load TransformersMPF.Controller with a DLL error, run pywin32's
   post-install once, also as Administrator: `.venv\Scripts\python .venv\Scripts\pywin32_postinstall.py -install`.
   It has its own name and class id, so the Tron Legacy bridge can stay registered next to it.
3. Write the table's MPF script next to the table:
   `.venv\Scripts\python scripts\vpx_table.py "C:\Visual Pinball\Tables\Transformers Pro (Stern 2011) v.2.4.vpx"`
4. `controller.vbs`, `core.vbs` and `sam.vbs` come from VPX's own `Scripts` folder, as before. VPinMAME is not
   needed while the `.vbs` is there.

## Playing

Start the game first, then the table:

```
python scripts\run.py --hw vpx
```

Godot opens the DMD window, MPF starts and waits for the table ("MPF waits for the Visual Pinball X table").
Then start the table in VPX. If the table is started first, the bridge starts `run.py --hw vpx` itself in a new
console and waits for it (VPX looks frozen during that time; the first start after a pull also regenerates the
media). Closing the table quits a game the bridge started.

Keys are VPX's own (the table script and `sam.vbs` turn them into switches): coin `5` (`4`, `3` the other slots),
START `1`, tournament start `2`, flippers, plunger, tilt (nudge) keys, slam tilt `Home`, service buttons `7` `8`
`9` `0`, and `End` opens and closes the coin door (as in PinMAME: "50V / 20V DISABLED" on the DMD and no coils
until it is closed again). Free play is on by default, as with `--hw virtual`; `--no-free-play` brings back the
factory pricing. The DMD window is Godot's: place it where the table's DMD goes (`--dmd-size 1280x320` sets its
size). The table's own DMD and a B2S backglass stay empty (B2S needs PinMAME behind it). Other run.py options
work as usual (`--monitor` for MPF Monitor next to the table).

Settings, as environment variables for the bridge: `TF_VPX_RUN_ARGS` (extra run.py arguments when the bridge
starts the game, for example `--dmd-size 1280x320`), `TF_VPX_LAUNCH=0` (never start it, only connect),
`TF_MPF_HOST` / `TF_MPF_PORT` (MPF on another computer: also give MPF's BCP server an outside address, see
mpf-vpcom-bridge's README). Logs: `game\logs\vpx_bridge.log` (bridge), MPF's console, `game\logs\godot.log`.

## Device map

The table uses PinMAME's numbering for Stern SAM, which for the matrix switches, coils and lamps is the ROM's
own numbering, the numbers `game/config` already uses. So every device keeps its MPF name; only these differ:

| Table (PinMAME) | MPF | Notes |
|---|---|---|
| switch 84 / 82 (`swLLFlip` / `swLRFlip`) | `s_l_flipper_button` / `s_r_flipper_button` | SAM dedicated D9 / D11. 83 and 81 are the EOS switches (D10, D12), which the table never sends. |
| switch -7 (`swTilt`, the table's nudge tilt) | `s_tilt_pendulum` | D17 |
| switch -6 (`swSlamTilt`) | `s_slam_tilt` | D18 |
| switches 65, 66, 67 (`swCoin1-3`) | `s_left_coin_slot`, `s_center_coin_slot`, `s_right_coin_slot` | D1-D3; 68, 69 are D4, D5 (no key) |
| switches -3, -2, -1, 0 | `s_back`, `s_minus`, `s_plus`, `s_select` | D21-D24 |
| switch -5 | `s_ticket_notch` | D19 |
| switch -4 | `s_coin_door_open` | D20. The table script's `End` key toggles it (`scripts/vpx_table.py` adds that line to the table's KeyDown; sam.vbs has no coin door switch). While it is on, every solenoid but 24 reads 0 and solenoid 33 is off, as the door interlock cuts the coil power. |
| switches 86, 88 (`swURFlip`, `swULFlip`) | none | Ignored, like any switch MPF does not have. |
| solenoids 1-32 | the coils and flashers of the same number | 0 or 255 (the table sets `UseVPMModSol = 2`, core.vbs scales by 1/255); a pulse is always reported at least once. |
| solenoid 33 | flippers enabled | On while MPF has the flipper rules on. `sam.vbs`'s fast flips then move the flippers straight from the keys; when MPF turns the flippers off (tilt, ball end, game over, service menu) solenoid 33 goes off and the flippers drop. The ticket outputs (MPF 33-35) are renumbered out of the way. |
| solenoids 15, 16 | `c_left_flipper`, `c_right_flipper` | Follow the flipper buttons while the rules are on, as the SAM CPU does. |
| solenoids 13, 14, 9-11 | slings, pop bumpers | Pulsed by MPF autofire rules on switches 26, 27, 30-32 while a ball is in play: the table's sling arms and sounds move on 13 and 14 (its sling and bumper objects kick the ball by themselves). |
| lamps 1-80 | the lights of the same number | 0-255 (MPF's brightness, so fades show), as the table's physical outputs expect. |
| GI string 0 | none | Always 255: MPF does not switch the GI, so the table's GI comes on with the game and stays on. |

The ball devices count the table's own switches: trough 18-21 (`bsTrough` starts with 4 balls; the table also
pulses the trough jam switch 22 on every eject, which MPF takes in its stride), shooter lane 23 (MPF's auto
launch, solenoid 2, fires the table's impulse plunger), left eject 3 (solenoid 22) and the Megatron lock 38-41
(solenoid 3). The Optimus Prime motor (solenoid 30) turns the table's ramp, which reports switches 43 and 44.

## Checked here, and what to check on Windows

Checked in the Linux workspace (VPX itself only runs on Windows):
- `tests/test_vpx.py`: the overlay's numbers, a game started through the bridge's calls (trough, START, trough
  kicker, flippers enabled, flipper coils following the button, lamps 0-255, GI, unknown switches), a ball served,
  plunged and drained the way the table reports it, sling and bumper coils, the coin door, tilt, the script rewrite,
  and the bridge's lamp and GI values for both output modes.
- `python scripts/vpx_bridge.py --check`, the bridge's own client without COM, with nothing running: it started
  `run.py --hw vpx` (Godot and MPF), saw the GI on, loaded the trough, pressed START, saw the trough kicker, the
  flippers enabled and the left flipper coil held with its button, and quit the game on Stop.
- `scripts/vpx_table.py` on the v2.4 table: the loader and the End key line changed, the rest byte for byte.

To check on Windows, in this order (from `%USERPROFILE%\Transformers-MPF` after the one-line set-up):
1. `.venv\Scripts\python scripts\vpx_bridge.py --check` with nothing running: it starts `run.py --hw vpx` and
   prints the same lines as above.
2. `.venv\Scripts\python scripts\run.py --hw vpx`, then start the table in VPX: no message box; MPF's console shows
   the switches as VPX sets them; the trough holds 4 balls (MPF Monitor: `--monitor`); the GI is on.
3. Coin `5`, START `1`: the DMD and sound start a game, the trough kicks a ball to the shooter lane, the plunger
   launches it (or the auto launch when the game serves the ball), the flippers work, and stop when the ball
   drains (ball end) or on a tilt.
4. Lamps and flashers follow the game; the slings animate when hit; the left eject (22) and the Megatron lock (3)
   kick out; the orbit gates (4, 5) and the Optimus Prime motor (30) move.
5. `End`: the DMD warns, the flippers drop; `End` again brings them back.
6. Close the table: a game the bridge started quits too.
