# Reference traces

Scenarios (`*.txt`) and the traces `tools/trace/tf_ref` wrote for them on the real ROM (`*.jsonl`). Format
and commands: `tools/trace/README.md`.

| Scenario | What it covers |
|---|---|
| `basic` | one player: start, plunge, slings, pops, a target, flippers, three drains |
| `coils` | every switch-driven coil, flipper hold, then 45 s with no switch activity (ball search) |
| `sounds` | attract, coin, start, 12 s in the shooter lane, plunge, playfield hits, two tilt warnings and a tilt, ball save, drains, bonus (run with `TF_EVENTS=1`) |
