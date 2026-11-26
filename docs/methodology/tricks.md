# The tricks that needed reasoning (Transformers Pro 1.80, tf_180)

Internal draft, 2026-11-26. Part 1 lists the tricks; part 2 gives a step-by-step method per trick, written for an
agent that has never seen this project. Addresses are tf_180's (the worked example); the method is game agnostic.
"Upstream" says where the method already is: **SSD** = Stern-SAM-Decryption, **MGP** = MPF-Godot-Packaging,
**new** = nowhere yet (to propose after the owner's green light), **part** = the fact is there, the recipe or a
step is missing.

## Part 1. The list

| # | Trick | Agent | What went wrong or took time without it | Upstream |
|---|---|---|---|---|
| T01 | Run the ROM's own functions in Unicorn (no machine emulator), OS services answered in Python | A | effects, lamp shows and coil times came from PinMAME captures (forbidden since 2026-11-24): 268 strict-check failures | SSD `rom_extraction.md` 3.3 (part: the bring-up checklist and the pilot step are missing) |
| T02 | An effect is an op list (one op per OS call, with the call's return address), drawn afterwards from primitives re-implemented from their routines | A | captures are frames without causes: no address, no state, no sounds | SSD 3.3 |
| T03 | Effects that draw game state: one run per state the caller sets in the effect's task | A | 38 of 153 deffs (battle shots left, tournament, high score, jackpot videos) | SSD 3.3 (part: the attribution trap of T04 is missing) |
| T04 | Attribute the caller's task writes to the right `deff_start`, and remember `task_create` zeroes the task | A | deff 65 got 5 jackpot variants that belong to deff 66; wrong arguments for deffs 31, 44, 60, 79, 125 | new |
| T05 | Table-driven animations: one op list per animation of the table, plus how the index is chosen | A, C | 9 deffs exported only their first animation, so the game missed sounds 0x085-0x099 and 0x0cb-0x0f2 | new |
| T06 | Random draws are inputs: a policy per run, declared in each scenario | A | the side drawn at game start decides half the rules; runs did not reproduce | SSD 3.3 |
| T07 | The tick: 16.0 ms in the code, 16.15-16.26 ms in a PinMAME trace; replay traces in reference time | A, C | 12 score / deff / audit comparisons broke when the game moved to 16.0 ms; deff 92 looked 29 ticks too long | SSD (code tick), MGP? (part: the replay time scale is new) |
| T08 | Measure an effect's length on the DMD task's function change, not on the next `deff_start` in the trace | A, C | a background rule re-requested deff 93 while deff 92 still held the DMD; C cut 92 short | new (SSD `dmd_animation_durations.md` has the code side) |
| T09 | Effects that lower their own priority near their end (to 0x20): the waiting effect takes the DMD while the task runs on | A, C | REPLAY, BALL LOCKED, wizard deffs held the screen too long; leff starts late | SSD 3.3 |
| T10 | Rule records (background deffs, rule leffs) are built in RAM by constructors and evaluated on request, in the list's order | A, C | rules missing from a static read; order made up (`order=` keys) | SSD 3.3 (part: the list order recipe is new) |
| T11 | Play whole reference scenarios in the ROM's code | A | 89 spec lines and 58 switch rows were "observed" only | SSD 3.3 |
| T12 | Sound FIQ, flash banks as MMIO, coil slots and motors inside the runner | A | chained sounds and eject warnings missing; 8 MB copies per bank switch too slow | SSD 3.3 |
| T13 | "Restarts" in a trace that are refused `leff_start` calls of the running leff | A, C | a departure row for something the ROM does not do | SSD PR #87 (open) |
| T14 | Name every function from its code, rule by rule, each name with its evidence | A | 2,555 `FUN_` left; Tron names ported by address were wrong (ground rule 20) | part (SSD ground rule 20 says what not to do, not how) |
| T15 | Run formatters and other pure routines to their return with nothing stubbed | A | adjustment value texts copied from captures | SSD 3.3 (one line) |
| T16 | Coil times from the code: scan the constants before each pulse call; OS device tables for pops, slings, flippers | A | pops 34 ms and slings 67 ms measured, 32 and 64 in the tables | SSD 8.1 (pops, slings, flipper table) |
| T17 | Ball feed, serve and ball search from their tasks; the ball's travel time is not in the code | A, C | four constants were Tron trace values; "decode" them without saying what is physics | part |
| T18 | Lamp effect arbitration: lamp group and coil group conflict in `leff_start`; a leff owns its group's lamps from its start | A, C | wrong leffs on top; lamps left lit under a leff | new |
| T19 | Sound arbitration: the call record's no-repeat ring, priority and take-over flag; the sample script's voice mask and count | A, C | "missing" sounds in the traces explained one by one | new for SAM (MGP has the WPC version) |
| T20 | Walk the service menu in code; port each test screen as the ROM's loop, pass by pass | A, C | static service screens, wrong items | SSD 3.3 (walk), new (port the loops) |
| T21 | Prove dead code: no `BL`, no literal, no PC-relative `ADD` anywhere in the image | A | leff 149 and sound 0x267 chased as missing | part (SSD ground rule 5 lacks PC-relative `ADD`) |
| T22 | A capture of a forced effect may be what was under it | A | wrong frames packaged for effects forced without arguments | SSD 3.3 |
| T23 | Declare every capture where the strict check reads it | A | 153 deffs, 111 leffs and coil times captured without any `source` column | SSD ground rule 0 |
| T24 | What an effect's code plays (sounds, leffs), the game must not play again | C | every battle hit sound twice; leff 150 started twice | new |
| T25 | Count what a parser read; zero of N is a failure, not an empty result | C | `parse_show` read 0 of 113 shows (double-quoted colours): no leff lit a lamp, and every test passed | new for MGP (SSD ground rule 9 is the A version) |
| T26 | Re-cite an OS layer copied from the previous game | C | Tron 1.74 addresses landed inside unrelated tf_180 functions | MGP `recreation.md` 5b |
| T27 | Independent read-only reviews with probes, then a matrix of the conversion against the code | C | 53 differences (then 330 "differs" and 633 "missing" rows) in a game that passed its 24 traces | MGP 5b (part: the 5-scope matrix and its verdicts are new) |
| T28 | The final table "MPF against decoded code" (element, MPF, ROM, state, correction, test) | C | no proof that the MPF code matches the decompile beyond the traces | new |
| T29 | A multiball's rules outlive its flag | C | jackpots after the drain | MGP 5b |
| T30 | Two agents on stacked branches: batched requests, who owns which file, merge the other's branch | A, C | conflicts on `boards_inventory.md` and `docs/qa/README.md`; piecemeal questions | new (global, see global_method.md) |

## Part 2. The method, trick by trick

Each entry: **When** (the symptom that tells you to use it), **Steps**, **Check** (a number you must reach before
moving on), **Traps**, **Example** (tf_180), **Escalate if** (see global_method.md, "Escalation").

### T01. Run the ROM's own functions in Unicorn

**When.** Any value (an effect, a lamp show, a text, a coil time, a rule outcome) still comes from an emulator
capture, or the decompile is too tangled to read the value by hand.

**Steps.**
1. Load the whole ROM image into Unicorn (ARM, little endian) at its run address; map RAM and initialise it from
   the ROM's copy loop data (SAM: the OS copies its data block at boot; tf_180 copy loop at `0x84`).
2. Find and write down, before any run, these addresses from the decompile: `task_current`, the task list head,
   `task_sleep`, `task_create`, `task_exit`, the bank-switch routine and its register, `snd_play`,
   `deff_start`, `leff_start`, `random_below`. tf_180: `task_sleep` `0xacfc`, task list head `0x314a0`,
   `deff_start` `0x000209b4`, `leff_start` `0x00007c10`, `random_below` `0x0000ba94`, bank register
   `0x02580000`.
3. Hook those routines in Python (a code hook at their first instruction): record the call with its arguments and
   the return address (`lr`), do what the OS would (sleep = save context, advance the tick; create = new context),
   and return. Let everything else run as ROM code: text helpers, `msg_get`, `vsprintf`, the lamp library.
4. Write the runner once as a library (tf_180: `rom/tools/coderun.py`), then a thin lift per kind of thing
   (`deff_lift.py`, `leff_lift.py`, `adj_format.py`, `switch_lift.py`, `scenario_lift.py`).
5. **Pilot first.** Run one effect that has a good old capture. Only scale to all effects when the pilot
   reproduces every captured frame (tf_180: deffs 53, 54, 65 matched pixel for pixel).

**Check.** On the pilot: same frame count, same frames, same length to one tick. Then on all: the share that
runs to its end (tf_180: 152 of 155 on the first pass) and the share that matches old captures (84).

**Traps.** In the order they cost time on tf_180: a wrong `task_current` gives garbage task structs; without the
bank switch, fonts and images in banked flash read as unmapped; task structs and stacks must not overlap the OS's;
a sound routine retries until it returns 1 (return 1); the lamp layer pool is filled by a boot init routine you
must call first; a primitive you did not model writes the DMD pages directly (add a memory hook on the pages to
catch it). Never `mem_unmap` inside a Unicorn hook (segfault).

**Escalate if** the pilot does not reproduce its capture after the traps above are checked: building the runner is
the one step a weaker model should not improvise.

### T02. Effects as op lists, drawn from re-implemented primitives

**Steps.** Record every display primitive call (fill, rect, copy, bitmap, text, show/flip, remap, dissolve), each
with the tick and `at` = the return address in the effect's code. Re-implement each primitive from its routine in
the decompile (not from what frames look like). Draw the op list with the ROM's own images and fonts.
Package: frames, `timing.json` (end tick, `ran_ticks` when it never ends, the sounds and leffs it starts, priority
changes), and keep the op list (`rom/rom_data/dmd/deff_ops/deff_NNN.json`) for the game to read.

**Check.** Every op has an `at`; every primitive used by any op list has a renderer (count the op kinds).

### T03. Effects drawn from game state: one run per caller state

**When.** A lifted effect shows zeros, empty names or the wrong side; or its capture differs from the run only in
values.

**Steps.**
1. List the caller writes: grep the decompile, after each `deff_start(id, ..)`, for stores into the returned task
   (`*(T *)(task + 0x30) = ...`, then `+0x34`, `+0x38` ...). Tool: `rom/tools/deff_args.py` (CSV per call site:
   deff, caller, offset, type, value expression). Apply T04 before trusting it.
2. List the RAM the effect reads (a counter, a per-player array, a record with a checksum). For a record with a
   checksum, recompute it with the OS's own sum routine, run as ROM code.
3. One run per distinct state, each state cited to the routine that sets it. Package the first run; keep the
   others as `deff_NNN__<name>.json`.

**Traps.** An effect started from inside another draws on that one's work pages: set the work page variables to a
real pair, or fg and bg are the same page. The OS edit cursor writes the page directly (tf_180 `0x0002b808`,
invert a box): catch it with the page hook and model it as a primitive.

### T04. Attribute caller writes to the right effect

**When.** A variant list looks too rich (an effect that never reads an index has 6 variants), or two effects
started close together share arguments.

**Steps.**
1. A write belongs to the **last** `deff_start` before it in the same function, and only until the **next**
   `deff_start` in that function. When the code reuses one variable for both tasks, read the assignment of that
   variable, not its name.
2. `task_create` clears the task block (tf_180: `memset` of 0x68 bytes in `task_create` `0x0000aa04`): an
   offset no caller writes is 0, never "whatever the last effect left".
3. Before packaging a variant, show that the effect's own code reads the offset (a load from `task_current +
   off` in its body). An index nobody reads is not a variant.

**Example.** The popcount stored at `+0x38` after `deff_start(0x42)` is deff 66's argument; deff 65 always plays
entry 0 of `0x040c7490`. The fix removed 5 false variants and false rows for deffs 31, 44, 60, 79, 125.

**Check.** For every packaged variant: the writing caller, its address, and the reading load in the effect.

### T05. Table-driven animations

**When.** An effect's code picks a function pointer from a table by an index, and a capture (or the first run)
shows only one of its animations; or the traces have sounds that no op list plays.

**Steps.**
1. Find each table and its entries (function pointers into the effect's module). tf_180: jackpot and super
   deffs, tables such as `0x040c6494`; battle hit deffs, tables `0x040c6a60` (94), `0x040c6c34` (102).
2. Find how the index is chosen: an argument in the task (`+0x34`, `+0x38`), a counter, a random pick with a
   no-repeat mask, a popcount, a cap (tf_180 deff 102: `+0x34` = 12 - shots left, capped at 11; the last shot
   takes entry 1 through `+0x3c`).
3. Run each entry as its own variant (`deff_NNN__shotsK`, `__final`, `__videoK`). The animation players take a
   sound table: an entry plays at its frame; a special entry (tf_180 0x1f, `snd_play_after_if` `0x00025364`)
   chains a sample after the running one ends: record it as its own op (`sound_after`).
4. Write one row per effect: table, index source with its address, variants with length and sounds
   (tf_180: `rom/rom_data/dmd/deff_anim_tables.csv`, 18 deffs).
5. Close the loop: every sound id of the range those players use is either in an op list or proven never called
   (T21). tf_180: all of 0x085-0x099 and 0x0cb-0x0f2 but 0x092 and 0x0df-0x0e1.

**Quirks to keep.** At index 6 deff 59 reads the first entry of deff 60's table; the ROM does it, so the game does.

### T06. Random draws as inputs

**Steps.** Answer `random_below` from a policy: 0 by default, `--rng all` for one run per value when the range is
small. In a whole-scenario run (T11) each draw is an input: write it in the scenario file as a comment line the
tracer ignores. Never let a draw float: two runs of the same scenario must give the same marks.

### T07. The tick, and replaying traces against a 16 ms game

**Steps.**
1. Read the tick from the code: the IO interrupt period times the divider of the OS loop (tf_180: 64 interrupts of
   250 us = 16.0 ms, `io_isr` `0x000114b0`). That is the game's tick.
2. A PinMAME pass runs late. Measure a trace's own tick only on spans the code counts in ticks (an effect of
   known length, a task sleep): tf_180 16.15 ms (Tron 16.26).
3. In the game's trace replay, wait each reference second for `16.0 / REF_TICK` of game time and write the game's
   trace back in reference seconds (tf_180 `tests/scenario.py`: `REF_TICK = 0.01615`, `TIME_SCALE`).
4. Never put the measured value in the game or the package (it is a capture).

**Check.** After the switch to the code tick, the same trace comparisons as before (tf_180: 12 broke without step
3, none with it).

### T08. Measuring an effect's length in a trace

**When.** The code's length and the trace disagree by tens of ticks.

**Steps.** Sum the code's sleeps along the path (T01 gives it: tf_180 deff 92 = 74 frames x 3 + 40 x 3 + 1 = 343
ticks). In the trace, look for the tick the DMD task's function changes, not for the next `deff_start`: a
background rule may request the next effect while the current one still holds the display with a higher
priority. Convert with the trace's tick (T07).

**Example.** Deff 93's request at 30.24 s was the background loop (`0x1794c`); the DMD task changed function at
30.67 s, 343 ticks at 16.15 ms. Six other battle intros agreed within 3 ticks.

### T09. Priority drops

Package every priority change with its tick (`priority_changes`, or the first 0x20 op of the final run), not only
the end of the run. In the game, from that tick the waiting effect or the score effect takes the display while the
effect's task (and any leff it stops on exit) runs on. tf_180: deff 140 drops at tick 105, deff 84 at 162, deff 47
raises itself to 0x80 at tick 44.

### T10. Rule records and their order

1. Run the module constructors (the global constructor table) before anything else; read the rule lists from RAM
   after a game start.
2. The rules are evaluated when a request flag is set (tf_180 `0x00017650`), not each tick; a RAM poke in a test
   makes no request.
3. Order: read the insert routine. tf_180 inserts before the first record whose priority is not above its own;
   all leff rules have priority 0, so each goes to the head; the constructors run from the last entry down. The
   list therefore runs the modules in ascending address order, and inside a module last registered first
   (`rom/tools/rule_order.py`, `rom/rom_data/rules/leff_rule_order.json`). Never invent `order=` keys.

### T11. Whole scenarios in the ROM's code

Order of bring-up (each step fixed a class of wrong marks on tf_180): constructors; `game_init`; clear the
"starting" game-state bit; each tick the OS work routine, the due tasks, the end-of-tick hooks; switch edges
through the dispatcher's rules; **dedicated switches** (flippers, tilt, coins) from their own record table
(tf_180 `0x040e3740`, found in the record lookup `0x0000d2d4`); coins before START for a second player; the
tracer's ball model (trough, shooter, ejects, locks); task exits with their exit calls (`+0x48`); never answer
current player, side or buttons in Python. **Check:** marks equal to the trace (tf_180: points on 260 of 262 marks,
then 58/58 switch rows).

### T12. Sound FIQ, banks, coil slots, motors

See SSD 3.3 for the full text. The one-line version: run the mixer 64 times per tick while a channel is active;
hook direct writes to the bank register and map the banked window as MMIO only during the FIQ batch; let the
coil pulse routines fill their slots and end each slot n // 16 + 1 ticks later through its callback; a motor gives
up after its timeout method's limit (tf_180 468 ticks), which a tracer shows as "run time".

### T13. Phantom restarts

When a trace shows the same leff started twice while it runs, check whether `leff_start` refuses a start of the
current task (tf_180 `0x7c10`: `task == task_current`). The rule leffs run in the context of the last task that
slept; when that is the rule's own leff, the restart is refused. Do not model it.

### T14. Naming every function

Apply rules in a fixed order, each name with its evidence (tf_180 `rom/tools/name_functions.py`,
`refine_names.py`, `purpose_names.py`, `read_names.py`):
1. semantic from tables: switch handler (switch table), task entry (`task_create` argument), event hook
   (`event_hook_add`), effect / sound / adjustment / audit / message when it is the function's one clear purpose;
2. wrapper (a body that calls one named function), getter, setter;
3. purpose: the effects the body shows through calls with constant arguments, resolved in the ROM's tables
   (message text, audit name, adjustment name);
4. by hand for the rest, one row each (address, name, evidence), in a CSV the tool applies.
Every name ends with the low address bits so it stays unique; an OS and a game function with the same low address
get separate names. Never port a name from another game by address or by matching signature (SSD ground rule 20);
a carried name is a hypothesis until its body is read.
**Check:** zero `FUN_` left; a sample of 20 names reread against their bodies.

### T15. Pure routines to their return

A formatter, a checksum, a price table lookup: call it with Unicorn and nothing stubbed, read the result buffer.
tf_180: the 15 adjustment formatters (`adj_format.py`); `0x0002aebc` is a plain `sprintf("%d")`.

### T16. Coil times from the code

1. Scan backwards from each `BL` to the pulse routines for the constants last moved into r0 / r1 (coil, ms),
   conditional moves included (`rom/tools/coil_pulses.py`).
2. Pops and slings are OS device tables read by the 1 ms pass of the IO interrupt (tf_180 pops `0x040ddfb0`).
3. Flippers: find the driver records from the flipper driver init (tf_180 table `0x040cf590`, built by
   `0x00006194`, run each 1 ms by `io_isr`; `rom/tools/flipper_drive.py`).
4. Effects' pulses come from the leff op lists (T01).

### T17. Ball feed: code plus physics

Decode the serve, multiball feed and ball search tasks and the device table's settle times (tf_180
`rom/rules/modes/ball_feed.md`, device table `0x040d17fc`: trough 31 ticks, shooter 31 / 46). Then write each game
constant as a composition: code part (cited) + ball travel or MPF device timing (not in the code, say so). A
constant that is "travel" stays measured, with that label; do not pretend it is decoded.

### T18. Lamp effect arbitration

`leff_start` refuses a new leff when a running one shares a lamp of its lamp group or a coil of its coil group and
is higher (or equal without flag bit 2); otherwise it kills the running one, and a killed rule leff restarts when
it can. From its start, a leff owns its lamp group's lamps (cleared in the override planes). Export the lamp and
coil group tables (tf_180 `0x040d1510`, `0x040cf65c`; `rom/tools/coil_groups.py`) so the game can run the same test.

### T19. Sound arbitration

From the sound call record (tf_180 0x14 bytes at `0x040dee08`, `rom/tools/sound_fields.py`): `+0x0e` the
no-repeat ring, `+0x10` priority, `+0x11` take-over flag; from each sample's stream script: byte 1 the voice mask,
byte 2 the voices taken (`sample_voices.py`). The start routine takes free voices first, then the slot playing
longest at a lower priority; else the sample does not start. Implement that in the game instead of special cases.

### T20. Service menu

Walk it in the scenario runner (PLUS until the first item comes back, SELECT, BACK; resync after BACK): every screen
text (`service_walk.py`, 858 screens, about 15 minutes). Then port each test screen as the ROM's loop, pass by pass
(grid, wire colours, coil firing), not as a static picture; check one menu against a code run.

### T21. Dead code

Dead only if there is no `BL`, no literal word with the address, and no PC-relative `ADD` that builds it, anywhere
in the image (pointer tables live in data banks). tf_180: leff 149 and the 0x267 call.

### T24. Do not play twice what an effect plays

Read each effect's op list (or `timing.json`) for the sounds and leffs it starts. A feature that also starts them
by hand plays them twice. Route the start through one helper that knows the op list (tf_180 `os_.deff_media`,
`display.own_sounds` for the calls a feature plays itself with an argument).

### T25. Count what a parser read

Every loader of generated data asserts a count: shows read, lamps per show, frames per effect. tf_180:
`parse_show` read 0 of 113 shows because the colours were double-quoted; no test noticed because "no lamp" is a
valid state.

### T27, T28. Reviews, matrix and the final table

1. Review pass (MGP 5b): read-only reviewers, one scope each, every finding proved by an address and, when
   possible, a probe that prints the game's value next to the ROM's. Reviewers fix nothing.
2. Conversion matrix: one row per element of the MPF conversion (configs, generated config, shows, Python,
   GDScript), verdict `match` / `differs` / `missing` / `extra` / `unverifiable`, each matrix rebuilt by its probe
   (tf_180: 5 scopes, 3,095 rows, `docs/qa/2026-11-26/`).
3. Fix high first, one regression test per fix (`tests/test_qa_2026_11_26.py`).
4. Final table once everything is decoded (`docs/qa/final/mpf_vs_code.csv`): `id, element, mpf, rom,
   state_before, state, correction, test`; `fixed`, `match` (now cites the code instead of a trace), or
   `open (MPF limit)` with its `rom_differences.md` row.
**Check.** pytest, strict check at 0, and the trace floor never goes down.
