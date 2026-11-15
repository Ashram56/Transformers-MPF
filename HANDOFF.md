# Handoff: rules test bench and code review (work in progress)

Branch `claude/project-thread-8o5fcy`, one work-in-progress commit, **no pull request yet**. Delete this file
before opening the pull request. Owner's request (Vincent): an exhaustive review of the MPF rules code against
the rules read from the ROM, through a reusable test bench (per mode, then stress games), checking in particular
that the service menu's adjustments really change the game.

## What is done

- **The bench** `tests/bench/` with its runner `scripts/bench.py` and its page `docs/test_bench.md` (read it
  first: how to run, the files, the invariants, how to write a test).
  - per mode: `test_battles.py`, `test_megatron.py`, `test_optimus.py`, `test_wizard.py` (with the whole road
    to the wizard multiball, no shortcut), `test_features.py`;
  - game flow and players: `test_game_flow.py`, `test_multiplayer.py`;
  - `test_adjustments.py`: the register `COVERAGE` of the 98 adjustments (a bench test, or `ROM_UNUSED`,
    `NOT_MODELLED`, `MACHINE`);
  - `test_traces.py` + `trace_baseline.json`: the 24 reference traces must not match the ROM less than today;
  - `test_stress.py`: seeded random games, invariants checked after every action.
- **Game fixes** found by the bench (each cites its ROM address in the code): per-player game flags
  (`rom/rom_data/io/game_flags.csv`, `rom/tools/game_flags.py`, table [0x040cf458]); the Megatron lock over balls
  and players, adj 69 and 89 [0x0100a1f8] [0x0100a074]; extra ball and special collect (`game/tf/features/awards.py`,
  [0x01007b40] [0x01008528]); wizard reset and side mode [0x01035ad0] [0x0100fff0]; bonus hold; adj 82, 84, 85,
  86, 88; ADD-A-BALL [0x01024a60] / [0x0103aff4]; game restart (adj 36) deadlock; multiball launches capped to
  what the trough holds [0x0103a87c]; a kept ball kicked out by the ball search; lock keep check at a player
  change; tilt during a multiball re-serve or a lock serve.
- `docs/rom_differences.md`: 8 rows added (lock at game end, kept ball kicked by ball search, multiball launches,
  ADD-A-BALL, game restart, extra ball and special, adjustments not modelled 46 / 90-95, adjustments 84 / 85).

## State of the tests at the handoff

- Last full run of the per-mode files, game flow, players, adjustments and traces: all passed. **Not rerun
  since the last changes to `megatron.py`, `os_layer.py` and `driver.py`: rerun everything first.**
- Stress, `scripts/bench.py stress --stress 25 --seed 1000` (137 games): 135 passed, 2 failed, before the last
  edit below:
  - `two_players_seed_1104`: "balls in play 3 but census (0, 0, 0, 0, 4)";
  - `two_players_seed_1105`: "balls in play 2 but census (0, 0, 0, 1, 3) with 1 locked".
  Replay one with `scripts/bench.py --replay two_players_seed_1104 --seed 1000 --stress 25`.

## The Megatron edit to verify (written, never run)

`game/tf/features/megatron.py`, `_handle` / `_serve` / `_trough_empty`. Case of seed 1104: the lock holds 3
balls, the ball search kicks one out (2 kept, 2 in play), the player locks one (3 kept, the trough is empty so no
ball can be served), then locks the last one, which starts the Megatron multiball. The serve was scheduled at the
lock and gave MPF's count back one ball *after* `start_multiball` had counted the kept balls again: one ball
short. The edit decides at the lock: with an empty trough the locked ball leaves `game.balls_in_play` at once
and no serve is scheduled. To do: run the two seeds, then the 137 games, then the default bench; seed 1105 was
not analysed (probably the same family: a lock with the trough empty).

Two of the last failures were the bench's, not the game's, and are fixed in `tests/bench/driver.py`: `land()`
(a bench ball is not moved into a device before MPF has confirmed its kickout) and `plunge()` (only a ball MPF
has counted in the shooter lane).

## What is left

1. Verify the edit above, finish the stress analysis, rerun `scripts/bench.py` and `pytest -q tests`
   (`tests/test_package.py::test_tracked_paths_exist` fails only where setup ran with `--skip-media`), and the
   trace checks (the baseline must not regress).
2. Short regression tests in the mode files for the corner cases the stress found: game restart, launch with an
   empty trough, kept ball kicked by the ball search (and a lock after it), tilt during a re-serve, keep check
   at a player change, ADD-A-BALL at the eject.
3. Docs: `AGENTS.md` section 4 and the repository map (`tests/bench/`, `scripts/bench.py`), README "Tests",
   `rom/README.md` (`game_flags.csv` and its tool), the specs in `rom/rules/modes/` (adj 89 at [0x0100a074],
   adj 88 Autobot only [0x0100c200], game flags, ADD-A-BALL), check the `rom_differences.md` rows.
4. Pull request on Transformers-MPF; open questions for the owner: adj 46 and 90-95 not modelled; the locked
   balls go home at game end; a restart waits for the ball to drain; a player gets the balls the previous
   player's lock releases [0x0100a1f8]; `battle_blackout` audit difference.
5. Stern-SAM-Decryption, pull request `Knowledge: rules test bench (from Transformers)`: the bench method in
   `agents/recreation.md`, the SAM game-flag table, `balls_in_play` and the multiball task. MPF pitfalls
   (BallHold default reset events, `add_ball` queued until the next drain, `balls_in_play = 1` set after
   `ball_starting`, ball start waiting for an empty playfield) go to MPF-Godot-Packaging, game agnostic only.

## Running the bench

```sh
.venv/bin/python scripts/bench.py                  # everything (about 3 minutes)
.venv/bin/python scripts/bench.py --quick          # without the stress games and the traces
.venv/bin/python scripts/bench.py megatron wizard  # some files only
.venv/bin/python scripts/bench.py stress --stress 25 --seed 1000
```

Set-up without Godot: `python3.11 scripts/setup.py --skip-godot`.
