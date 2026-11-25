# Ball feed: serve, multiball feed, ball search (code)

Agent A, 2026-11-25, read from the tf_180 decompile (`rom/code/tf_decompiled.c`). Ticks are OS ticks (16.0 ms,
owner 2026-11-25). Fact tags: **code** unless said.

## Devices

The game's ball devices are the 0x24-byte records of table `0x040d17fc` (index 1..4), registered at start-up by
`0x01005fb8` (`FUN_00006194(device registry)` [0x00006194]). RAM after that init (run as ROM code,
`rom/tools/ball_search.py` `boot`): trough = device 1 (`DAT_00031624`), shooter lane = device 2 (`DAT_00031628`),
no second feeder (`DAT_00031626` = 0).

| device | record | +0x10 settle, first ball | +0x14 settle, next balls | +0x18 settle after the kick |
|---|---|---|---|---|
| 1 trough | `0x040d1820` | 31 | 31 | 31 |
| 2 shooter lane | `0x040d1844` | 31 | 46 | 31 |
| 3 | `0x040d1868` | 46 | 31 | 31 |
| 4 | `0x040d188c` | 46 | 62 | 31 |

A settle is `FUN_01037cf4(dev, &count, n)` [0x01037cf4]: count the device's switches
(`balldev_count_switches`) every tick until the count has not changed for n ticks.

## Serve

`serve_ball(type)` [0x0103b39c]: only with a trough and, unless type 8, none of the game-state bits 0x211; posts
event 0xf (a handler can refuse), type 3 arms the ball save (`ball_save_arm`), then starts the serve task
`FUN_0103b128` [0x0103b128] as task trough + 0x18 (+0x34 = the type, +0x30 = the auto-launch flag: types 1, 2, 6)
and the timed-plunger task (`FUN_0103a758` [0x0103a758]); posts event 0x10.

The serve task [0x0103b128]:
1. `FUN_0103801c` [0x0103801c]: how many balls to feed (the trough's count, at most what was asked).
2. Settle the trough count (`FUN_0103b048` [0x0103b048], polling every 2 ticks while the feeder task runs):
   types 2 and 8 without a settle, the others with +0x10 (31 ticks).
3. No ball in the trough: unless type 1, 2 or 8, start a device that holds a ball instead (`FUN_0103a3c0` /
   `FUN_0103a2c0`, the last device first).
4. Else per ball: unless type 8, `FUN_0000d8a0` and `FUN_00005ad8(0xd, ...)`; audits 7 (first ball), 8 and 9 of the
   trough (`FUN_01037bdc`); the trough kick (`FUN_0103a7d8` [0x0103a7d8]: bit 0x40 of the shooter record
   `DAT_00031454 + 1`); `FUN_0103a7fc` [0x0103a7fc]: when switch 0xe (shooter lane) is closed, task 0x16
   `FUN_0103a7a4` [0x0103a7a4] sleeps **125 ticks**, sets game flag 0xc and starts the shooter device's task;
   from the 16th try on, 312 ticks between tries; settle again with +0x14 (31 ticks).
5. `trough_drain_check(trough)`.

So the first serve waits the trough's 31-tick settle before its kick (the game's `SERVE_EJECT_TICKS` = 32: the
settle plus the tick the task starts on). Timed plunger (adj 39 TIMED PLUNGER, factory OFF): `task_17`
[0x0103a6d0] waits until trough and feeder are idle, sleeps adj 39 x **62 ticks**, then, if a ball sits in the
shooter lane (switch 0xc or the device count) and switch 0xd is open, kicks the shooter device (`FUN_01039de0`,
flags 8).

## Multiball feed

`multiball_start` [0x0103aec0] starts `FUN_0103aba4` [0x0103aba4] as task trough + 0x18. It starts leff 13 (its
+0x30 points at the feed's counters `0x000375e8`), waits until the trough is ready (`FUN_0103a4d0`, 1 tick a
try), then loops while balls are left to feed or the counters at `0x000375e8` / `0x000375ec` run:
- stops on game-state bits 0x214; while bit 0x100 is set or a ball sits in the shooter lane (`FUN_0103ab6c`,
  unless `DAT_00031470` bit 2), waits 6 ticks a try with the OS task priority 0x28;
- `FUN_0103aa5c` [0x0103aa5c]: settle the trough with +0x10 (31 ticks), then 6 ticks a try while the feeder,
  the shooter task or task 0x16 still run (so each ball waits the shooter's 125-tick task 0x16 of the ball
  before it);
- a ball to feed: audits 7, 8, 9, the trough kick and `FUN_0103a7fc` as in a serve; else 6 ticks;
- event 0x41 with the counters, which count down by the ticks spent (`DAT_00031550`); leff 13 ends when the
  first runs out (`FUN_0000b7e4(0xd)`); event 0x42.
At the end: audit 10, leff 13 off, a last settle with +0x18 (31), the counters cleared, `trough_drain_check`.

The game's `MB_EJECT_TICKS` (101) and `MB_FIRST_EJECT_TICKS` (51), `SAVE_SERVE_TICKS` (48) and
`DEVICE_BUSY_TICKS` (149) in `game/tf/os_layer.py` came from Tron traces. The tf_180 code gives instead: the
settles above, the shooter task's 125 ticks, and the 6-tick polls. The time between two balls also includes the
ball's travel (switch 0xe closing), which is physics, not code.

## Ball search

`FUN_0103b778` [0x0103b778] (task 0x2b), decoded by running it (`rom/tools/ball_search.py`,
`rom/rom_data/io/ball_search_ops.json`). Order of the 64 ms pulses, ticks from the task's first turn:

| tick | coil | from |
|---|---|---|
| 0 | 12 Optimus Prime | the coil registry's search routine 0x01033cb0 (`FUN_000025e8`, registry 0x00030b48 = ROM 0x040ce3d4) |
| 5 | 9 top pop | `FUN_00003018` [0x00003018] pops 1..3 |
| 6 | 22 left eject, 3 Megatron lockup | the game devices `FUN_0103be8c` [0x0103be8c]: device tasks `FUN_01039db4` |
| 6 | 2 auto launch (queued) | the trough's device task, queued pulse `FUN_00001f70` (served by `FUN_00003758`) |
| 10 | 10 right pop | |
| 15 | 11 bottom pop | |
| 20 | 13 left sling | `FUN_00003518` [0x00003518] slings 1..2 |
| 25 | 14 right sling | |

Each direct pulse (`FUN_00002160` [0x00002160]) holds the search until the 1 ms IO pass ends it: 64 // 16 + 1 =
5 ticks. The game's `BALL_SEARCH_SWEEP` is this table one tick later (the task runs the tick after its start).
Code open: when the queued auto-launch pulse really starts (the game uses 14, observed), the Optimus motor and
the orbit gate (from the event 0xd / 0xc handlers), and the search's own length (`task_running(0x2b)` loop).
