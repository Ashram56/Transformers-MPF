# Reference traces: run the real ROM, compare with the rebuild

`tf_ref` runs the real Transformers Pro 1.80 ROM (`tf_180`) in libpinmame from a scenario script and logs
what the game rules do. It is a port of Tron's `tron_ref` (same scenario commands, same JSON lines), with
this ROM's addresses, a Transformers ball simulation, and coil timing read from the solenoid register
writes. Run the same scenario on the MPF rebuild, log the same events, and `trace_compare.py` reports the
first place they differ.

Runs are deterministic: each one starts from factory settings (fresh NVRAM in a temp folder) and the
emulator is paused at fixed emulated times while the script acts.

## Build (Linux)

```sh
git clone --depth 1 https://github.com/vpinball/pinmame && cd pinmame
# ARM per-instruction hook plus the SAM bus hook (PinmameSetBusHook(addr, data, mask, write)), RAM access
# and emulated time. Tron's pinmame_arm_hook.patch alone is not enough here: its src/cpu/arm7/* hunks are
# what call the hook, and the bus hook is new.
git apply /path/to/rom/tools/trace/pinmame_hooks.patch
cp cmake/libpinmame/CMakeLists.txt . && mkdir build && cd build
cmake -DPLATFORM=linux -DARCH=x64 -DBUILD_STATIC=OFF -DCMAKE_BUILD_TYPE=Release .. && make -j4
cd ../..
g++ -O2 -std=c++17 -Ipinmame/src/libpinmame tf_ref.cpp -Lpinmame/build -lpinmame -lpthread \
    -Wl,-rpath,$PWD/pinmame/build -o tf_ref
mkdir -p ~/.pinmame/roms && (cd /tmp && cp /path/to/tf_180.bin . && zip ~/.pinmame/roms/tf_180.zip tf_180.bin)
```

Run: `PINMAME_NOJIT=1 ./tf_ref scenario.txt out.jsonl [watch.tsv]`. `PINMAME_NOJIT=1` is required (the
hook needs the interpreter). `TF_ROMS=/dir` overrides the ROM folder; `TF_EVENTS=1` also logs every
`event_post` (busy: thousands per second in some states).

## Scenario commands

One command per line; `#` starts a comment. The machine boots for 8 s (emulated) before line 1.

| Command | Effect |
|---|---|
| `start N` | 4 coins per player, then press Start N times |
| `wait S` | let S seconds of emulated time pass |
| `hit SW [ms]` | pulse switch SW closed for ms (default 60), then 100 ms settle. Switch 3 (left eject) stays closed until coil 22 fires. 38-41 (Megatron lock) lock a ball in play instead |
| `hold SW` / `release SW` | close / open a switch |
| `plunge` | the ball in the shooter lane leaves it |
| `autoplunge S` | auto-plunge S seconds after a ball reaches the shooter lane (default 1, 0 = never) |
| `drain [left\|right]` | one ball in play drains, optionally through the left (24) / right (29) outlane first |
| `adj ID VALUE` | set operator adjustment ID (`rom_data/settings/adjustments.csv`) |
| `poke HEXADDR VALUE [1\|4]` | write RAM (to jump straight into a state; mark such scenarios) |
| `button B [ms]` | `left`/`right` flipper, `tilt` (plumb bob), `tournament`, `start`, `coin`; ms defaults to 100, `-1` holds, `0` releases |
| `mark TEXT` | write a marker event, useful to line up both traces |

Ball simulation: a 4-ball trough (switches 21 = #1 right .. 18 = #4), coil 1 ejects a ball to the shooter
lane (23), coil 2 auto-launches it, coil 22 kicks the left eject (3), coil 3 releases one ball from the
Megatron lock (41, 40, 39, 38 fill in that order; inferred), coil 30 moves Optimus Prime between up (43)
and down (44) after 1 s on (inferred). Balls only leave play through `drain`.

## Trace format (JSON lines)

Every line has `t` (emulated seconds since power-on) and `ev`. `caller` is the ROM address of the calling
code, for looking things up in `code/tf_decompiled.c`; the rebuild does not need it.

| ev | fields | meaning |
|---|---|---|
| `ready` | | boot finished, script starts (time 0 for comparisons) |
| `switch`, `switch_hold`, `switch_release` | `sw` | script input |
| `button` | `button`, `ms` | script input |
| `score` | `player`, `delta`, `total` | a player's score changed (scores at 0x021109e4) |
| `score_add` | `points`, `multiplier`, `player` | the rules awarded `points` before the playfield multiplier (0x1caf0, 0x1cb0c) |
| `deff_start` / `deff_stop` | `id` | display effect started / stopped (`mpf_package/event_map.csv`) |
| `sound` | `call`, `in_deff` | sound call (`rom_data/sound/sound_call_uses.csv`); `in_deff` = display effect that played it, 0 = rules code |
| `leff_start` / `leff_stop` | `id` | lamp effect (table 0x040cfe00) |
| `audit` | `id`, `n` | audit counter bumped (`rom_data/settings/audits.csv`) |
| `flag_set` / `flag_clear` | `flag` | game flag |
| `multiball_start` | `balls`, `save_ticks`, `grace_ticks` | multiball / ball save request (0x103aec0) |
| `task_start` | `task`, `fn` | ROM task started |
| `lamp` | `lamp`, `state` | lamp output changed (`rom_data/io/lamps.csv` numbers) |
| `coil` | `coil`, `on` | coil output on/off as libpinmame reports it |
| `coil_pulse` | `coil`, `first_ms`, `total_ms`, `hold_duty`, `segments` | one coil activation timed from the register writes (250 us steps): first solid on time, whole activation, duty after the first pulse |
| `bg_entry` | `rec`, `mask`, `cond_fn`, `deff`, `sound`, `adjust_fn` | an entry of the background display / music table, logged once (`rom_data/sound/music_table.csv`) |
| `event` | `id` | `event_post` (only with `TF_EVENTS=1`) |
| `var` | `name`, `value`, `old` | a watched RAM variable changed (watch.tsv: `name hexaddr size`) |
| `sim` | `what`, ... | ball simulation (eject, launch, drain, lock) |
| `mark`, `script`, `end` | | script markers |

## Comparing

`trace_compare.py reference.jsonl candidate.jsonl [--tol 0.25] [--events score,deff_start,sound]`, as on
Tron. Reference scenarios and traces are in `rules/traces/`.
