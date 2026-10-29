# Prebuilt bundle (universal, `--target all`)

A bundle is one archive of the game with everything `scripts/setup.py` computes already built: the generated
config (`game/config/rom/`), sounds, media, baked fonts and the Godot import (both texture formats, so it installs
on any GPU family). A machine with MPF, Godot and ffmpeg then needs no setup run. The method and the builder
belong to the platform ([MPF-Godot-Packaging `platforms/game-bundles.md`](https://github.com/Ashram56/MPF-Godot-Packaging/blob/main/platforms/game-bundles.md),
`python -m mpf_godot bundle`); this game supplies `bundle_spec.json`, `scripts/package/options.json` and
`scripts/package/build_bundle.py` (its own checks).

## Build

```sh
.venv/bin/python scripts/setup.py                         # a complete, imported build first
.venv/bin/python scripts/package/build_bundle.py          # checks, then the platform builder, --target all
.venv/bin/python scripts/package/build_bundle.py --check-only
```

The build stops on stale or missing generated media, on any `*.bin` (outside `game/.godot`) or `*.local.cfg` under `game/`. The platform builder
must be importable (`PYTHONPATH=<MPF-Godot-Packaging checkout>`, with `GODOT=` unless `mpf_godot setup` ran). The script adds the
128 `timing.json` paths to the spec for the build, because the builder copies named paths only.

## What is in it, what is not

| In | Out (never) |
|---|---|
| `game/` (tracked files plus the generated config, sounds, media, fonts, `slides/deffs`, `tf/media_data.json`, Godot import), `scripts/`, the `rom/` tables and package files the game reads at run time, the trace scenarios | the ROM and every `*.bin` / `tf_*.zip`, `game/data`, audits, logs, `*.local.cfg`, `.venv`, `tools/`, `captures/` |
| GDE GoZen: from the platform (`platform_addons`), no binary in this repository | the PuP Pack (`pup_pack`, `pup_media`) and `native_video` |

## The PuP Pack

TerryRed's pack is not in the bundle. `bundle.json` `pup.install` runs
`python scripts/pup_setup.py --pup-zip <the author's zip or https URL>` on the target (ffmpeg is needed even when
the videos are not converted). The private `pup_pack` submodule is only the owner's copy; none of its files go into
this repository or a bundle. `keep_on_update` protects cabinet data, the installed pack and its media.

## Checked, and not checked

Built on 2026-10-28 on Linux x86_64 with the platform at MPF-Godot-Packaging `main` (`GODOT=tools/godot/Godot_v4.6.3-stable_linux.x86_64
PYTHONPATH=<platform checkout> python scripts/package/build_bundle.py`): 3,703 files staged, `xz -t` and `bundle.json`
read back fine, 102 MB packed, no ROM, `.bin` (only Godot's own `game/.godot/uid_cache.bin`), `pup_pack`, `pup_media`,
cabinet data or add-on binary in the archive. The 2,367 effect frames the slides load (`game/media/dmd/**/f*.png`, untracked, so their `.import` files are not in the
bundle) are seeded with `scripts/package/dmd_frame.import.template` (`compress/mode=2`, spec key `import_seed`, 5c):
the archive holds 2,367 `.s3tc.ctex` and 2,367 `.etc2.ctex` (102 MB). Without the seed Godot's default import is lossless and
the bundle carries no VRAM variant (the platform builder warns). `setup.py` itself still imports them lossless.
VRAM compression is lossy: a DMD frame may show it (row in `docs/rom_differences.md`); the bundle was not played or compared by eye.

Not checked: installing the archive on a real machine (the platform's setup page) and playing from it; the
`rom/` files read at run time (`rom_data/io|sound|settings`, `mpf_package/config`, `event_map.csv`, `service_menu.json`,
`rom_images_all.zip`, the 128 `deff_*/timing.json`, the traces) come from reading the code, not from
`strace -f -e trace=openat,stat`; `options.schema` has no settings tool yet, so the web page cannot write the options.
