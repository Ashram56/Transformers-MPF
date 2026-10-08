# Reference traces

Scenarios (`*.txt`) and the traces `tools/trace/tf_ref` wrote for them on the real ROM (`*.jsonl`). Format
and commands: `tools/trace/README.md`.

| Scenario | What it covers |
|---|---|
| `basic` | one player: start, plunge, slings, pops, a target, flippers, three drains |
| `coils` | every switch-driven coil, flipper hold, then 45 s with no switch activity (ball search) |
| `sounds` | attract, coin, start, 12 s in the shooter lane, plunge, playfield hits, two tilt warnings and a tilt, ball save, drains, bonus (run with `TF_EVENTS=1`) |
| `switches` | every playfield switch hit twice, one at a time, then the left eject (`rules/switch_handlers.csv`) |
| `side_left`, `side_right` | side choice with one press of the left / right flipper; watches the side byte (`watch_side.tsv`) |

Traces made before the score fix logged each award twice; all traces here were re-run with the fixed tracer
(`score_add` is logged once, from 0x1cb0c, with the real caller).
