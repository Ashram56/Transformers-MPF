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

The build stops on stale or missing generated media, on any `*.bin` or `*.local.cfg` under `game/`. Without the
platform builder installed it prints the command to run by hand: `python -m mpf_godot bundle bundle_spec.json --target all`.

## What is in it, what is not

| In | Out (never) |
|---|---|
| `game/` (tracked files plus the generated config, sounds, media, fonts, deffs, Godot import), `scripts/`, the trace scenarios | the ROM and every `*.bin` / `tf_*.zip`, `game/data`, audits, logs, `*.local.cfg`, `.venv`, `tools/`, `captures/` |
| GDE GoZen: from the platform (`platform_addons`), no binary in this repository | the PuP Pack (`pup_pack`, `pup_media`) and `native_video` |

## The PuP Pack

TerryRed's pack is not in the bundle. `bundle.json` `pup.install` runs
`python scripts/pup_setup.py --pup-zip <the author's zip or https URL>` on the target (ffmpeg is needed even when
the videos are not converted). The private `pup_pack` submodule is only the owner's copy; none of its files go into
this repository or a bundle. `keep_on_update` protects cabinet data, the installed pack and its media.

## Not verified yet

`bundle_spec.json` was written from `agents/packaging.md` section 5c without access to the platform's example or
schema: field names must be checked against `examples/bundle/bundle_spec.json` in MPF-Godot-Packaging. No real
bundle was built (it needs Godot, the platform builder and a full `setup.py`), and `rom/` is assumed not to be read at
run time except `rom/rules/traces` for `--scenario` (check with `strace -f -e trace=openat,stat`, as 5c advises).
