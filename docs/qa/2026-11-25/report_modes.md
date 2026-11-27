# QA 2026-11-25: modes and multiballs against the tf_180 decompile

Independent read-only review (scope: `battles.py`, `megatron.py`, `optimus.py`, `optimus_mech.py`, `wizard.py`,
shaker). Probes: [probe_modes.py](probe_modes.py) (6). Labels: confirmed (code + probe), code-proven, doubtful.

## Findings

| id | feature | ROM address | ROM does | game does | game file:line | proof | label | sev |
|---|---|---|---|---|---|---|---|---|
| M1 | End window of every multiball | gates `0x0100be84` (Megatron A), `0x0100dec0` (D), `0x010276e0` (Optimus A), `0x01029754` (D), `0x01036590` (wizard); end routines `0x0100c814`, `0x0100e6a0`, `0x01027f44`, `0x0102a028`, `0x01036768` | shot rules run while the flag is set **or** the end task runs (0xbb→0xbc, 0xbf→0xc0, 0xb7→0xb8, 0xb9→0xba: 156 + 62 = 218 ticks; wizard 0xc5: 312 ticks): jackpots still score after the drop to one ball | shots score only while `active` / `wmb_running`, cleared at `multiball_end` | megatron.py:214, 309; optimus.py:248, 302; wizard.py:195, 215, 225 | PROBE1 | confirmed | high |
| M2 | Megatron D saved progress | `0x0100e0bc` | adj 88 = 1 (default YES) restores the player's jackpot count, double count, mask and phase (0x02111e04 / e0c / df4 / de4) | D always resets (adj 88 honoured for Autobot only) | megatron.py:290-291 | PROBE3 | confirmed | high |
| M3 | Megatron A double-jackpot timeout | `0x0100c10c` (started by `0x0100c164`) | the timeout task waits `while (M < 3)` first: after the first jackpot the six doubles stay lit with no timeout | 312-tick timeout restarted on every award | megatron.py:225, 235, 263-267 | PROBE2 | confirmed | high |
| M4 | Optimus D super | `0x01029bf4` phase 3; table 0x040c7400 row 6 (slot 4) | super x center-lane multiplier | not multiplied | optimus.py:184, 302-315 | PROBE4 | confirmed | medium |
| M5 | Center lane / Optimus lockout | sw 11 `0x01033b3c`, sw 51 `0x01033d3c`, task 0x54 `0x01033cfc` (62 ticks) | sw 11 blocked only while task 0x54 runs, which only sw 51 starts | any sw 11 or sw 51 within 1.0 s of a sw 11 / 51 dropped (`CENTER_LOCK_S`, inferred) | battles.py:55, 971-976 | PROBE5 | confirmed | medium |
| M6 | Super-lit flashers | leffs 47 `0x010286f8`, 55 `0x0102a83c`, 63 `0x0100d038`, 71 `0x0100ef64`; rules `0x0100d004` / `0x0100ef30` | endless leff pulsing coil groups 18 / 22 / 26 / 31 every 8 ticks while the super is lit | no show, nothing pulsed; a phase 3 restored by adj 88 gets none | megatron.py:261, 324; optimus.py:234, 271 | lamp_effects.csv rows 47/55/63/71 | code-proven | medium |
| M7 | Add-a-ball at the end of a multiball | `0x01024a20` (weight), `0x01024a60` (award), gate `0x01006760` | offered during the first 156 ticks of the end task; award `FUN_0103aff4(1, 0, 312, 187)` with ball save 312 and grace 187 | weight uses the flags only; award has no ball save or grace | allspark.py:161, 224 | decompile 70687-70715 | code-proven | medium |
| M8 | Wizard qualify lamps | `0x01011ed4` | leffs 76 / 77 whenever `zuse_qualify_enabled`, both sides | Autobot only (observed) | wizard.py:49, 102-104 | decompile 58379-58380 | code-proven | low |
| M9 | Starscream lit pair moves | timer task `0x01017824` | each second, while shots left < 6 and switch tokens 0xc and 0xd down, the lit pair moves on | never moves (dropped after a trace) | battles.py:31-32 | decompile 62066-62080 | code-proven | medium |
| M10 | Megatron lock re-arm (ROM bug) | `0x0100af0c` (`DAT_02111d4c = DAT_02111d48`) | re-arms every player's counter | current player only; no row in rom_differences.md | megatron.py:432 | decompile 53148 | code-proven | low |
| M11 | Adj 89 autofire after lock, adj 69 virtual lock | `0x0100a074`, `0x0100a1f8`, deff 140 `0x0100b7f0` | both change the lock | neither read; no row | megatron.py:36, 607-612 | grep | code-proven | low |
| M12 | Jackpot speech sample | deffs 71 `0x0100d214`, 72 `0x0100d550`, 77, 78, 59, 65 via `FUN_00025250(call, idx)` | sample from a sequential counter | random sample | megatron.py:136; optimus.py:139 | decompile 54888, 55076 | code-proven | low |
| M13 | Megatron grace flags | only `game_flag_clear(0x26 / 0x2a)` exists | never set | set at the multiball end | megatron.py:146 | grep | code-proven | low |
| M14 | Task and show ids | totals: show tasks 0x8b / 0x8c (`0x0100c790`, `0x0100e61c`); D end task 0xbf / 0xc0; Optimus D intro task 0x72 (`0x01029a08`); side mode deff 84 task 0x7a, deff 85 task 0x7b | | totals queued as 0xbb / 0xbc; Optimus D intro 0x71; side mode 0x7b / 0x8f | megatron.py:178, 277; optimus.py:270; wizard.py:44-45 | decompile | code-proven | low |
| M15 | Lock lit deff 139 value | `0x0100af0c` (deff 0x8b, +0x30 = locked count) | passes the locked count | no value | megatron.py:434 | decompile 53153-53157 | code-proven | low |

Checked and matching: Megatron A values and the percentage table [100, 100, 75, 50] (0x040c6438, 0x040c72f0,
0x040c7454); Megatron D phases, values and multiplier slots; Optimus A/D jackpots and doubles; the 25,000 counters
left out (their routines have no caller); Optimus access and battle; lock gates; battle qualify gates; Starscream
values and 125-tick grace; wizard and side-mode values and the 312-tick end; all 52 shaker call sites.

Every function cited by the five files has a caller. The synthetic lamp-rule order keys (0x01012000,
0x01026000/10, 0x01028000/100, 0x0100cee0 + flag, 0x01010959, 0x01037019) look like ROM addresses but are not
functions: misleading citations.

## Observed / inferred values, with their code

| value | code |
|---|---|
| `CENTER_LOCK_S` 1.0 s | task 0x54 `0x01033cfc`, 15 + 47 = 62 ticks, but scope wrong (M5) |
| `RIGHT_IGNORE_S` 3.0 s | task 0x47, `FUN_0000abe8(0x47, 0xbb)` in `0x01033b3c` (187 ticks); sw 13 task 0x4f 187 ticks (`0x01033c80`) |
| Optimus kicker 0.37 s | `0x01033cfc`: 15 ticks, 64 ms pulse, 47 ticks |
| Megatron D intro and release timing | `0x0100a3b8` cases 3/7; task 0x57 (434 ticks) selects release-all (0x13d + leff 25, coil 3 every 20 ticks) |
| Lock handler delay 46 ticks | not found; `0x0100a3b8` case 2 calls `0x0100a31c` directly |
| `SERVE_TICKS` 155 | not found; serve through `0x0100a074` (adj 89) |
| `KICK_ONE`, `KICK_ONE_COIL` | `0x0100a3b8` cases 7/9 |
| `EJECT_OVER_TICKS` 66 | not found |
| Uncaptured deff lengths (59, 60, 62, 79, 139, 94, 96, 111, 118, 119, 88) | the deff loops, e.g. deff 71 = 31 x `FUN_01030374(4)`, deff 72 = 41 x 4 ticks |
| Optimus intro delay 1.32 / 3.52 s | tasks 0x71 / 0x72 start at once (`0x01027994` / `0x01029a08`); the deff waits in `FUN_01006480` |
| Battle completed-deff lengths 8.5 s | the hit deff loops (Starscream deff 94) |
| `QUALIFY_LEFFS` | `0x01011ed4` (M8) |
| `MOVE_S` 7.65 s, `ORBIT_TOKEN_S` 2.26 s | not found / not checked |

## Spec errors

1. megatron_multiball.md §6 "D progress always starts fresh": `0x0100e0bc` restores it when adj 88 = 1.
2. megatron_multiball.md §5.1 omits the `while (M < 3)` wait in `0x0100c10c`.
3. megatron_multiball.md "0x26 A grace / 0x2a D grace": never set; the window is the end task, and the shot rules
   run during it.
4. megatron_multiball.md §6 add-a-ball: offered only in the first 156 ticks (`0x01006760`); the revive covers 218.
   The D total is show task 0x8c.
5. optimus_multiball.md §6 "grace 187 ticks": the end task is 218 ticks (`0x01027f18`); 187 is the
   multiball_start grace.
6. optimus_multiball.md §5.2: the D super is x the center multiplier.
7. wizard_modes.md: qualify leffs 76 / 77 are not side-specific (`0x01011ed4`).
