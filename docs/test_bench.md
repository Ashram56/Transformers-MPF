# The rules test bench

`tests/bench/` checks the game's rules code against the rules read from the ROM (`rom/rules/modes/*.md`,
`rom/code/tf_decompiled.c`), mode by mode, then in whole games played in any order. It is what a session runs to
validate a rules change. It needs no ROM, no Godot and no display: the real game code runs on MPF's
`smart_virtual` platform (coil pulses move the balls between the ball devices) and the bench plays the part of
the player and of the balls.

```sh
.venv/bin/python scripts/bench.py                  # everything (about 3 minutes)
.venv/bin/python scripts/bench.py --quick          # without the stress games and the reference traces (1 minute)
.venv/bin/python scripts/bench.py megatron wizard  # only tests/bench/test_megatron.py and test_wizard.py
.venv/bin/python scripts/bench.py --stress 50      # 50 stress games of each kind (--seed N for other games)
.venv/bin/python scripts/bench.py -- -x -k adj_68  # anything after -- goes to pytest
```

`pytest -q tests` runs the bench too (it is part of the test suite).

## What is in it

| File | What it checks |
|---|---|
| `driver.py` | `BenchCase`, the base of every bench test: the player (`start_game`, `plunge`, `shoot`, `eject`, `lock`, `drain`, `end_ball`, `end_game`), the shortcuts into the modes (`start_battle`, `complete_battle`, `start_megatron_multiball`, `start_optimus_multiball`, `complete_energon`, `poke_wizard`) and the invariants (`check`, `check_fresh_ball`) |
| `test_battles.py` | the mode-start shots (values, adj 66), each of the eight battles from its start to its completion with every hit value, the time-out, the drain, the tilt, the timer adjustments |
| `test_megatron.py` | locks, both Megatron multiballs up to the super jackpot, the lock's balls over balls and players, adj 68, 69, 89 |
| `test_optimus.py` | the access, the battle, both Optimus multiballs up to the super, adj 67, 85, 87 |
| `test_wizard.py` | the side mode, the wizard multiball, the wizard reset, adj 86, and **the whole road** played shot by shot from the first ball to the wizard multiball with no shortcut |
| `test_features.py` | Energon, the twelve Allspark awards, extra ball and special at the right orbit, pops, spinner, Bumblebee and double scoring, 2-bank and fast scoring, lanes, skill shots, combos, shot multipliers, bonus and its holds |
| `test_game_flow.py` | balls per game, ball save, timed plunger, flipper launch, tilt warnings and tilt, extra balls, special, side choice, competition mode, game over, game restart, players joining |
| `test_adjustments.py` | the register of the 98 operator adjustments (below) and the tests of those no other file covers |
| `test_multiplayer.py` | what one player earns or starts does not reach the others (game flags, battles, bonus hold, the extra ball's road), four players in turn |
| `test_stress.py` | seeded random games (below) |
| `test_traces.py`, `traces.py`, `trace_baseline.json` | the 24 reference traces of `rom/rules/traces/` must not match the ROM less than they do in the baseline |

Each test's docstring gives the spec section or the ROM address of what it checks. A test that fails means the
game differs from the spec: fix the game when the spec is right, fix the spec (and the test) when the ROM says
otherwise (AGENTS.md section 7).

## Invariants

`check()` is called all along the stress games and at the end of most tests. With the game settled (`settle()`:
no ball on its way) it verifies:

- the four balls are all somewhere: trough, shooter lane, left eject, Megatron lock or playfield;
- MPF's balls in play = 4 - the trough's balls - the balls the Megatron lock keeps, and at least one;
- the lock holds at least the balls the rules count as kept;
- no multiball flag (0x1e, 0x1f, 0x22, 0x25, 0x29, 0x3e) with a single ball in play;
- no player's score went down; the playfield multiplier is at least 1;
- after the game: every ball is home and no task is left running.

`check_fresh_ball()` verifies that a ball starts with nothing of the previous ball or player: no battle,
multiball, side mode, double or fast scoring, no mode flag, playfield multiplier 1, bonus count 0.

## Adjustments

`test_adjustments.py` holds `COVERAGE`: for each of the ROM's 98 adjustments, the bench test that shows it changes
the game, or why it has none: `ROM_UNUSED` (the ROM never reads it), `NOT_MODELLED` (the ROM reads it, the game
does not yet: a row in `rom_differences.md`), `MACHINE` (cabinet, pricing, sound, high-score tables: not rules,
not covered by the bench). `test_every_adjustment_is_accounted_for` fails when an adjustment is missing or a named
test does not exist. **A rule that starts reading an adjustment gets its test and its `COVERAGE` line in the same
change.** Tests set adjustments the way the service menu does (`set_adj(number, value)`, or the class attribute
`ADJ = {number: value}`).

## Stress

`test_stress.py` plays whole games with a seeded random player: any shot in any order, locks, the left eject,
mode starts, drains (also in the middle of a multiball), outlanes, long waits (ball search), tilts, flipper
presses, wizard requirements completed out of order, banked Allspark awards; one, two and four players; factory
settings, the hardest and the easiest ones. `check()` runs after every action. The game's own random picks follow
the seed, so a seed always replays the same game.

- `TF_BENCH_GAMES` (default 2): games of each kind; `TF_BENCH_SEED` (default 1): the first seed;
  `TF_BENCH_ACTIONS` (default 60): actions per ball at most. `scripts/bench.py --stress N --seed S` sets them.
- A failure prints the seed and the last 25 actions, each with the game state after it (state bits, ball census,
  balls in play, kept lock balls, running modes). Run it again alone with
  `scripts/bench.py --replay two_players_seed_1101 --seed 1000 --stress 25` (the test's name, and the `--seed`
  and `--stress` of the run that found it).
- A stress failure is a corner case: reduce it to a short test in the mode's file (the fix's regression test),
  then fix the game.

Before a release, or after a change to the ball handling (`tf/os_layer.py`, the lock, the eject, the multiballs),
run a few hundred games: `scripts/bench.py stress --stress 50 --seed 2000`.

## Reference traces

`test_traces.py` replays every scenario of `rom/rules/traces/` and compares it with the ROM's trace
(`scripts/trace_check.py`). The game does not match every trace on every event kind yet (lamps, coils and sounds:
`rom_differences.md`), so the test compares with `trace_baseline.json`, the state of each scenario and kind today:
a kind that matched and no longer does, differs earlier, or matches fewer samples, is a regression. Scores, audits
and multiball starts must equal the ROM's in every scenario (two known exceptions are listed in the test). After
a change that matches the traces better: `scripts/bench.py --update-baseline`, and commit the file.

## Writing a bench test

```python
from tests.bench.driver import AUTOBOT, BenchCase

class TestSomething(BenchCase):
    SIDE = AUTOBOT              # the side every player starts on (default Decepticon)
    ADJ = {31: 5}               # operator adjustments, set as the service menu sets them

    def test_it(self):
        """The spec section and the ROM address of the rule."""
        self.start_game()                       # one player, the ball plunged
        battle = self.start_battle("ih")        # four lit mode-start shots, Ironhide lit first
        self.mark()                             # forget the trace so far
        self.shoot("left_ramp")                 # a shot the ROM counts (its debounces are waited out)
        self.assertIn(114, self.deffs())        # the display effects, audits and scores since mark()
        self.settle()
        self.check()
```

- `shoot(name)` knows the shots of `driver.SHOTS`; `eject()` and `lock()` put a ball in the left eject or the
  Megatron lock and wait for the game; `drain(n)` drops balls into the trough. A ball can only go somewhere when
  one is on the playfield (`rolling()`).
- Timers hold until the playfield is valid: call `validate()` (a spinner turn) when the test's own shots do not.
- `self.pd` is the player's rules state, `self.tf` the OS layer (`flag`, `adj`, `trace`), `self.feature(name)`
  a rules feature. Prefer what a player sees (scores, display effects, audits, balls) to internal fields.
- `self.tf.forced[name] = [...]` fixes the game's random picks (`"allspark"`: the award, `"side"`: the starting
  side), as the reference scenarios do.
