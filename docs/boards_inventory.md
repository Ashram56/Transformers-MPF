# Boards inventory: Transformers Pro 1.80 (STRICT RULE: DECOMPILE EVERYTHING, step zero)

One row per board with its own CPU, MCU, ROM or firmware (template: Stern-SAM-Decryption
`knowledge/templates/boards_inventory.md`). States: `complet` (every routine decompiled, named where used,
every datum it sends or receives traced), `partiel`, `absent`. `tools/check_strict_rule.py` fails while any row
is not `complet`. Written 2026-11-25 by the QA pass ([docs/qa/README.md](qa/README.md)); agent A owns it.

| Board | CPU / MCU | ROM file(s) | Decompile state | Where (decompile, notes) | Open |
|---|---|---|---|---|---|
| SAM CPU/sound board (520-5246-02), game program | Atmel AT91R40008 (ARM7TDMI) | `tf_180.bin` (30,560,052 bytes, SHA1 `62e1328e…7e904`) | partiel | `rom/code/tf_decompiled.c`: Ghidra 11.4.2, all 3,003 functions decompiled, about 466 named (OS by matching Tron, deff/leff functions from this ROM's tables); 2,526 still `FUN_`. Scores, inserts and sounds of the rules: specs in `rom/rules/modes/` with addresses, many lines still tagged observed | (1) deff (display effect) scripts: 117 of 153 decoded from their code (`rom/tools/deff_lift.py`, 2026-11-25), 38 that depend on game state still replay captures; (2) leff (lamp effect) scripts: all decoded from their code (`rom/tools/leff_lift.py`); (3) coil pulse times: 33 of 35 from the code (`rom/tools/coil_pulses.py`), the flipper drive open (its measured times kept, owner waiver 2026-11-25); (4) sound call fields +0x0c..+0x13 not decoded; (5) aux strobe outputs (CSTB/DSTB) not traced; (6) naming of the 2,526 unnamed functions used by the rules |
| SAM CPU board, Xilinx logic (DMD scan, audio playback, switch/IO glue) | two Xilinx XC95144XL CPLDs (flash, non-volatile; no program, a fuse map) | not in the PinMAME set and not in tf_180.bin (no Xilinx signature, no loader); written at the factory through the 1x6 JTAG header J8 (XTCK/XTDI/XTMS/XTDO), which is not wired to the ARM, so the CPU cannot load or read it (CPU/Sound board schematic) | absent | Fixed function, no game logic; behaviour documented in Stern-SAM-Decryption `knowledge/sam_hardware/CPU_BOARD_IO.md` (DMD 128x32 at 62.67 Hz, 16 shades; about 4 kHz sound FIQ). Only a JTAG read of a real board through J8 can give the fuse map, if Stern did not set read protection | Owner decision: whether it counts under rule 1 (it carries no rule); reading it through J8 would also check the Stern-SAM-CPU-PPUC assumptions (Q18) |

Boards without their own CPU, MCU, ROM or firmware, listed so nobody looks for one (not checked by the tool):

| Board | Why it has no firmware |
|---|---|
| SAM IO power driver board (520-5249-00) | decoders and edge-triggered latches; every pulse width is what the CPU writes (`knowledge/sam_hardware/README.md`) |
| 12-transistor aux driver board (PinMAME `SAM_GAME_AUXSOL12`, CSTB/DSTB) | latches on its strobe |
| 128x32 DMD panel | scanned by the CPU board's CPLDs |
| Shaker motor kit (optional), speakers and amplifier | no logic |

Last updated 2026-11-25.
