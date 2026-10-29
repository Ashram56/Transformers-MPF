# The game package (for the prebuilt bundle)

The platform ([MPF-Godot-Packaging](https://github.com/Ashram56/MPF-Godot-Packaging)) knows no game. It takes the **complete
package of the game**, made by this repository, and turns it into a bundle for a machine that already has the MPF engine
(MPF, Godot, GoZen, ffmpeg). The PuP Pack is never in it: it is installed separately from the author's zip (`pup.install`).

| Where | What |
|---|---|
| `scripts/package/game_package.json` | the contract: identity, `run`, `git_tracked` (tracked folders), `copy` (every other path the game needs, **generated and git-ignored ones included**), `never`, `platform_addons` (`gde_gozen`, `mpf-gmc`: the platform adds them), `requires`, `options`, `pup`, `keep_on_update`, `import_seed` |
| `scripts/package/build_package.py` | checks the package is complete (`--list` prints the paths); the package itself is made by `python scripts/setup.py` |
| `scripts/package/options.json`, `dmd_frame.import.template` | the settings schema and the Godot import template for the 2,367 effect frames (VRAM compressed in the bundle; lossy, so a row belongs in `rom_differences.md`) |
| `tests/test_package.py` | every listed path exists once the game is built; the generated files (`game/slides/deffs`, `game/tf/media_data.json`, ...) stay listed |

Why generated files are listed: the platform stages tracked files with `git ls-files`, so git-ignored files made by `setup.py`
are missing unless `copy` names them. Without `game/slides/deffs` and `game/tf/media_data.json` the bundle has no
animation for the 130 display effects and no sound pools; without `mpf-gmc` (platform add-on) Godot never connects to MPF
and the DMD stays empty.

The field names follow what the platform's builder reads today (`copy`, `git_tracked`, ...); the platform rejects keys it does not know
(no `format` key), so the contract follows its list.
