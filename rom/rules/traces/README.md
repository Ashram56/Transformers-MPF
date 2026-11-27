# Reference traces

Scenarios (`*.txt`) and the traces `tools/trace/tf_ref` wrote for them on the real ROM (`*.jsonl`). Format
and commands: `tools/trace/README.md`.

| Scenario | What it covers |
|---|---|
| `basic` | one player: start, plunge, slings, pops, a target, flippers, three drains |
| `coils` | every switch-driven coil, flipper hold, then 45 s with no switch activity (ball search) |
| `sounds` | attract, coin, start, 12 s in the shooter lane, plunge, playfield hits, two tilt warnings and a tilt, ball save, drains, bonus (run with `TF_EVENTS=1`) |
| `tilt_ball_save` | QA F15 (capture approved by the owner 2026-11-25): validate, three tilt presses, drain inside the ball save, next ball |
| `switches` | every playfield switch hit twice, one at a time, then the left eject (`rules/switch_handlers.csv`) |
| `side_left`, `side_right` | side choice with one press of the left / right flipper; watches the side byte (`watch_side.tsv`) |

Traces made before the score fix logged each award twice; all traces here were re-run with the fixed tracer
(`score_add` is logged once, from 0x1cb0c, with the real caller).

## Code runs: the same scenarios in the ROM's code

`tools/scenario_lift.py` plays every scenario (but `basic`, which has no marks) in tf_180's own code under Unicorn,
with the tracer's ball model and inputs (`tools/switch_lift.py` runner: OS tick loop [0x0002bd48], module
constructors [0x0002c0f4], switch dispatcher rules [0x0000dc44]; commands before the first `start` are not run).
The random draws are inputs too: the `#! random FN V ...` comment lines (the tracer ignores comments) give the
answers of `random_below` [0x0000ba94] when FN draws: the side at game start (on_event_26_33f94 [0x01033f94]) and
the Allspark mystery award (`bag_weighted_pick` [0x0000bae8], `allspark_energon`); every other draw answers 0.
Since 2026-11-26 the OS's own coil and sound code runs too: the coil pulses and the queued-pulse list
(`coil_pulse_queue_serve` [0x00003758], 1 ms slot ends as `io_isr` [0x000114b0] does) and the sound FIQ
(`snd_fiq_mix` [0x000261fc], 64 calls a tick while a channel plays, flash banks switched by the sound code itself),
so chained sounds and the eject warning step (0x157 + leff 21) come from the code.

`code_runs.csv` has one row per mark: the code run's points, awards (value and the ROM function that scored it),
sounds, deffs and leffs, and `trace` = `same` or the columns where the trace differs (confirmation only, never
the source). On 2026-11-26: **points equal on 260 of 262 marks**, every column equal on 232 (205 before the FIQ and
coil code ran). The two point differences are an end-of-ball bonus that lands after the mark's window
(`battle_mudflap` after_end, `allspark_energon` allspark_collect_3: 405,150 and 132,370 from `start_deff_25`
[0x00019e44] in the trace). The other column differences are timing (a deff or sound a few ticks across a mark) and
random picks (speech variants).

Rebuild: `TF_ROM=tf_180.bin python3 tools/scenario_lift.py OUT_DIR [SCENARIO ...]` (about 3 minutes a scenario;
`OUT_DIR/<scenario>.json` holds the op lists, `OUT_DIR/summary.csv` the rows of `code_runs.csv`).
