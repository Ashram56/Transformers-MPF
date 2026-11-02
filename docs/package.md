# The game package (for the prebuilt bundle)

The platform ([MPF-Godot-Packaging](https://github.com/Ashram56/MPF-Godot-Packaging), "MGP") knows no game: no recipe, no spec,
no file list, no name (its CONTRIBUTING.md, `tests/test_no_game_content.py`). It takes the **complete package of the game**,
made and described by this repository, and turns it into a bundle for a machine that already has the MPF engine (MPF, Godot,
GoZen, ffmpeg, the setup page). Everything below is this game's side of MGP's contract: `common/games/README.md` ("What the game
provides") and `platforms/game-bundles.md` ("Rules every prebuilt bundle follows") there.

## Build and publish

On Linux or WSL, from a clone of MGP, with the author's PuP Pack zip:

```sh
python3 common/games/build_game_package.py https://github.com/Ashram56/Transformers-MPF.git --pup-zip ~/Downloads/tf_180.zip --out dist
# dist/transformers-pro-<date>-<commit>-linux-all.tar.xz  and  .sha256
```

Add `--publish https://SERVER/FOLDER` (with `WEBDAV_USER` and `WEBDAV_PASS` in the environment) to upload it, and
`--skip-setup` to rebuild in a workspace a full run already prepared.

The tool clones `main` (it refuses another branch or an unpushed commit, rules 1 and 10), runs `scripts/setup.py --no-monitor`,
then this game's `scripts/package/build_bundle.py` (the Stern SAM convention), checks the archive (`.sha256`, `bundle.json`, no
binary, every import of the start chain present, `run.check`) and with `--publish` uploads it to `<URL>/transformers-pro/` and
updates `mpf-games.json`, which the page's *Updates* card reads. Then install it on a machine and watch it
(`sh common/games/check_installed.sh 60` there, rule 11): the build's checks do not prove it runs.

## What is where

| Where | What |
|---|---|
| `scripts/package/game_package.json` | the description MGP's `python -m mpf_godot bundle` reads (keys from MGP `schema/game_package.schema.json`, an unknown key is refused): identity, `git_tracked`, `copy` (every other path the game needs, **generated and git-ignored ones included**), `optional`, `never`, `platform_addons` (`gde_gozen`, `mpf-gmc`), `requires`, `run`, `options`, `pup`, `keep_on_update`, `monitor`, `import_seed` |
| `scripts/package/build_bundle.py` | what the game does around MGP's builder: checks the package is complete, makes the PuP media from `--pup-zip` on the builder, then calls `mpf_godot bundle` with `game_package.json`. `--no-pup`: a bundle without PuP support |
| `scripts/package/build_package.py` | the completeness check (`--list` prints the paths); the package itself is made by `python scripts/setup.py` |
| `scripts/package/start.py` | `run.start`: `scripts/run.py` with the saved settings; the board's Godot arguments (`MPF_GAME_ARGS`, `run.game_args`) go after `--` |
| `scripts/package/check.py` | `run.check`: can the unpacked bundle start (contract paths, settings, start scripts, MPF import, MPF config parses)? The builder and the page run it before installing |
| `scripts/package/bundle_options.py`, `options.json` | `options.tool` and its schema: the page's settings card (`list`, `get`, `set`, `unset`). `free_play`, `dmd_size` become `run.py` flags kept in `game/options.json`; the `pup.*` options are written into `game/pup.local.cfg` |
| `scripts/package/pup_install.py` | `pup.install`: only unpacks the author's zip into `pup_pack/tf_180` (the page does the same itself for a pack from its library, `pup.extract_only`) |
| `scripts/package/dmd_frame.import.template` | the Godot import of the 2,367 effect frames (VRAM compressed in the bundle; lossy, a row in `rom_differences.md`) |
| `tests/test_package.py` | the contract's paths and the platform's rules, the settings tool, the start merge, `check.py` on a built game |

## Rules this game follows (MGP `platforms/game-bundles.md`)

| Rule | Here |
|---|---|
| 2, 3: a bundle regenerates nothing at start | `toolchain.media_stale()` returns None when `bundle.json` is there; `run.py` then never calls the generators |
| 4, 5: GMC and GoZen are the platform's | `platform_addons: ["gde_gozen", "mpf-gmc"]`; `scripts/gmc_patch.py` takes the platform's `# mpf-godot fix` tag as patched; `pup_setup.py` keeps the platform's GoZen |
| 6: the venv and the Godot arguments | `toolchain.venv_dir()` reads `TF_VENV`, then `MPF_GAME_VENV`; `run.game_args: true`, `start.py` passes them to Godot |
| 7: the pack's videos are never converted | the mp4s play through the platform's GoZen; `build_bundle.py` refuses a manifest with Theora conversions |
| 8, 9: the start chain and its check | the start chain lives in `scripts/` and `game/` (both tracked, all packed); `run.check` is `check.py` |
| 12, 13: nothing is made on the target, extras ship in the bundle | `pup_media/tf_180` (the manifest, the pack's music and pictures, made by `pup_setup.py` on the builder from `--pup-zip`) is in the bundle and is not carried over by an update; the machine only unpacks the author's zip (`pup.extract_only`), no ffmpeg, pip or conversion there |

The PuP Pack itself is never in the bundle (`never: pup_pack`): the owner uploads the author's zip on the page (*Add a game or a
PuP Pack*). Why generated files are listed: the platform stages tracked files with `git ls-files`, so git-ignored files made by
`setup.py` are missing unless `copy` names them. Without `game/slides/deffs` and `game/tf/media_data.json` the bundle has no
animation for the 130 display effects and no sound pools; without `mpf-gmc` Godot never connects to MPF and the DMD stays empty.
