# Performance probe

Ported from Tron Legacy MPF (`docs/performance.md` there has the full method and how to read the report).

- `game/tools/perf_probe.gd` (autoload `PerfProbe`) records only when `MPF_PERF_DIR` is set (`TRON_PERF_DIR` is read too):
  `frames.csv`, `video.csv`, `av.csv`, `events.csv`, `memory.csv`. It reads and changes nothing.
- `bash scripts/perf/run.sh SCENARIO [SECONDS]` plays a trace scenario with the probe on (`--suite` runs
  `scripts/perf/clips.txt`: `basic`, `battle_bumblebee`, `megatron_autobot`), samples threads and writes `summary.md`
  under `perf/` (git-ignored). `python3 scripts/perf/summary.py <run folder>` summarises a folder.
- On a bundle installed by a platform image, start the game with `MPF_PERF_DIR=<folder>` in its environment.

Measured on the Nipogi AK2PLUS (x86 image, bundle 3e7142e, 2026-10-28): attract 212 s at 60.0 FPS, worst second 59, p99
16.7 ms, 4 video frames skipped of 44,396; one game of 56 s at 60 FPS with 1 skipped frame. See
`platforms/x86.md` in MPF-Godot-Packaging.
