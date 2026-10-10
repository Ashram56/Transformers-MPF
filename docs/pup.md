# PuP Pack: TerryRed's Transformers pack on three screens

The game can play **TerryRed's Transformers (Stern) PuP-Pack** (v1.0, PinUP Player set `tf_180`) the way
PinUP Player does in Visual Pinball: its videos on the backglass (with its crests, faces and text panel), the
game's DMD drawn large in the pack's DMD panel art, an optional topper, and the pack's music instead of the ROM
music. The pack is TerryRed's work: get it from the author's download page, where TerryRed is credited.
This project keeps a private copy for the owner's cabinets in
[Ashram56/Transformers-PuP](https://github.com/Ashram56/Transformers-PuP) (the `pup_pack` submodule); nothing
of the pack is in this repository.

With the PuP off (`TF_PUP=0`, or `[pup] enabled=false`) the game is the strict recreation, ROM music included.

The PuP runtime (`game/pup_runtime/`, `game/pup/`, `scripts/pup_setup.py`, `scripts/gen_pup.py`,
`scripts/pup_captures.py`, `scripts/pup_decode.py`) is a copy of the game-agnostic runtime in
[Ashram56/Stern-SAM-Decryption `tools/pup/runtime/`](https://github.com/Ashram56/Stern-SAM-Decryption/tree/main/tools/pup/runtime)
(the PuP Pack agent, `agents/pup_pack.md`): never edit the copies here, change them there and run its
`install.py` again. This game's own parts are `game/pup.cfg`, `game/tf_pup/trigger_map.yaml`,
`game/modes/pup/` and the hooks listed at the end.

## Setting it up

```
python scripts/setup.py               # the game + the PuP: the pack, its videos converted for Godot
python scripts/run.py                 # the game with the PuP windows
```

`run.py` prints `PuP on: ...` before it starts Godot, or what is missing. `setup.py` calls
`scripts/pup_setup.py`, which takes the pack from the `pup_pack` submodule (private: your git needs access to
Ashram56/Transformers-PuP) and installs the video add-on for the platform: the pack's MP4s play **as they are,
with hardware decoding**, nothing is converted.

| Platform | Video player |
|---|---|
| Windows x86_64 | GDE GoZen (FFmpeg), decoding on the GPU through Direct3D 11 Video, else DXVA2 (any GPU vendor, nothing to install); software when the GPU cannot. `native_video` (Media Foundation) is installed too as the fallback: `[pup] video_player="native"` or `TF_VIDEO_PLAYER=native` |
| macOS | `native_video` (AVFoundation; Godot 4.6+, hence the game's Godot 4.6.3). A build with a heap fix: never replace it with the upstream zip |
| Linux x86_64 / arm64 | GDE GoZen (a Jetson's hardware decoder once libnvmpi is installed) |
| Anything else, or `TF_GOZEN=0` and `TF_NATIVE_VIDEO=0` | fallback: `scripts/gen_pup.py` converts the videos to Theora in `pup_media/tf_180/` (slow the first time) |

The add-ons come from `pup_addons/` and are copied to `game/addons/` by setup. `python scripts/video_check.py`
decodes a few of the pack's videos with GoZen, on the GPU and then in software, and prints the decoder and speed
of each. The GoZen Windows build and why Windows uses it (the native player stuttered and drifted on Tron) are in
Stern-SAM-Decryption `agents/pup_pack.md` section 6.

`scripts/gen_pup.py --native` only lists the pack's files and their sizes in `pup_media/tf_180/manifest.json`
(it reads the sizes with ffmpeg, installing `imageio-ffmpeg` in the venv when none is on the PATH).

**From the author's zip.** `TF_PUP_ZIP=<the zip, or an https URL>` for `setup.py` (or
`python scripts/pup_setup.py --pup-zip <zip>`) takes the pack from the zip TerryRed publishes instead of the
submodule: the folder holding `triggers.pup` (`tf_180/`) is extracted into `pup_pack/tf_180/` and stamped with
the zip's SHA-256, so the same zip is not extracted twice. A pack already checked out by the submodule is left
alone (delete the folder to switch). The zip's muted ROM is not used: the game drops the ROM music itself.

## The three screens

| Window | Shows | PuP screens |
|---|---|---|
| `backglass` (16:9) | the background and mode videos, with the pack's overlays where its `screens.pup` places them: the text panel (bottom centre), the two crests (top corners), the Decepticon and Autobot faces (bottom corners) | 2, 11, 12, 13, 14, 15 |
| `dmd` | the game's 128x32 DMD in the pack's DMD panel art (`PuPAlphas/TF Backbox 4x3 or 5x4.png`) | the game's DMD |
| `topper` (optional) | the side's topper loop | 0 |
| (no window) | the pack's music | 4 |

This is the pack's "Option 1 - Backglass, Topper" set (its default), with the topper forced on as the pack's
ReadMe says to do when a topper display exists. By default (`[pup] layout="stack"`) the windows open one
under the other at the left of the main monitor; every window can be resized and its content follows.

Everything is set in `game/pup.cfg`. Do not edit it for your cabinet: put the keys you change in
`game/pup.local.cfg` (git-ignored, same sections), for example:

```ini
[pup]
layout="manual"           ; each window where its section says
third_screen=false        ; no topper window and no topper videos

[backglass]
screen=1                  ; monitor index
fullscreen=true
borderless=true

[dmd]
screen=2
fullscreen=true
borderless=true
```

- `[pup] ost_music=false` keeps the ROM music (the videos still play).
- `[pup] enabled=false`, or `TF_PUP=0` in the environment, turns the whole PuP off.
- `[backglass] fit`: `fit` (black bars), `fill` (crops) or `stretch`.
- `[dmd] frame_crop` / `dmd_rect` place the art and the DMD (pixels of the art image); `dots` draws round dots.
  The game's own 128x32 window is minimised (`hide_main_window`); it stays the source of the DMD picture.
  Keys pressed in any PuP window drive the game as in the DMD window.

## How it works

1. **Triggers.** The pack's `triggers.pup`, `playlists.pup` and `screens.pup` are read as they are. In Visual
   Pinball, `D<n>` fires when the DMD shows `PupCapture/<n>.bmp` (inside its purple rectangle, or the whole
   frame when it has none). Here the game posts `tf_deff_<id>` when display effect `<id>` takes the DMD, and
   `game/tf_pup/trigger_map.yaml` maps each `D<n>` to the effects whose frames contain that capture
   (`scripts/pup_captures.py` matches all 225 captures against every recorded frame and library animation;
   report in [pup_captures.md](pup_captures.md)).
2. **Shots, sides and locks.** The ROM shows a different animation per battle shot, per side and per lock, but
   the ROM extraction recorded one variant per effect, so those captures match a library animation no effect
   is credited with. The map tells them apart by the event's arguments: the battle hit's number and whether it
   completed the battle (`hit`, `completed`, posted by `tf/features/battles.py`), the lock number and the
   wizard shot (`values`), the player's side (`state.side`, from the player's rule state) and counts since a
   mode's intro (`counters:`). Which video goes with which shot follows the pack's row order (inferred).
3. **MPF side** (`game/pup_runtime/`, loaded as the never-started mode `pup`): fires the rows of each event,
   applies their `RestSeconds` and sends them as BCP `pup_play` to Godot.
4. **Godot side** (`game/pup/`, autoload `Pup`): the windows and the PinUP Player rules per screen
   (priorities, `Loop`, `SetBG`, `StopFile`, `StopPlayer`, `SkipSamePrty`, playlists).
5. **Music.** When Godot's PuP player is ready, MPF drops the ROM's music calls (the sound pools on the
   `music` track) and stops the running ROM music; speech and effects still play. The pack's music then plays
   on its screen 4. A departure from the ROM, row in [rom_differences.md](rom_differences.md).

Not mapped yet: the Decepticon side's second-round lock videos (rows 208-210, "Ball n Locked - 2nd": no game
event tells the rounds apart). `tests/test_pup.py` covers the map, the engine and the music hand-over.

## Hooks in the game's files

`game/config/config.yaml` (the `pup.yaml` include), `game/project.godot` (the `Pup` autoload), `.gitmodules`
(`pup_pack`), `.gitignore` (`pup_media/`, `game/pup.local.cfg`, video add-ons), one `pup_setup` call each in
`scripts/setup.py` and `scripts/run.py`, and the `hit` / `completed` arguments of the battle hit effect in
`game/tf/features/battles.py`. Everything else is in its own files.
