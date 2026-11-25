# Boards inventory: Transformers Pro 1.80 (STRICT RULE: DECOMPILE EVERYTHING, step zero)

One row per board with its own CPU, MCU, ROM or firmware (template: Stern-SAM-Decryption
`knowledge/templates/boards_inventory.md`). States: `complet` (every routine decompiled, named where used,
every datum it sends or receives traced), `partiel`, `absent`. `tools/check_strict_rule.py` fails while any row
is not `complet`. Written 2026-11-25 by the QA pass ([docs/qa/README.md](qa/README.md)); agent A owns it.

| Board | CPU / MCU | ROM file(s) | Decompile state | Where (decompile, notes) | Open |
|---|---|---|---|---|---|
| SAM CPU/sound board (520-5246-02), game program | Atmel AT91R40008 (ARM7TDMI) | `tf_180.bin` (30,560,052 bytes, SHA1 `62e1328e…7e904`) | partiel | `rom/code/tf_decompiled.c`: Ghidra 11.4.2, all 3,003 functions decompiled and all named: 466 by hand or by matching, 2,555 by `rom/tools/name_functions.py` (`rom/code/function_names.csv`, each name with its rule and evidence: about 1,000 say what the function does, from its switch, task, event hook, deff, leff, sound, adjustment, audit or message; about 1,560 are structural: the named routine or the table it uses). Scores, inserts and sounds of the rules: specs in `rom/rules/modes/` with addresses | (1) deffs, (2) leffs, (4) sound call fields (`rom/tools/sound_fields.py`), (5) aux outputs (only strobe bit 6, aux coils 33-35, `rom/README.md`) and (6) function names: done 2026-11-25. Still open: (3) the flipper drive (its measured times kept, owner waiver 2026-11-25); 89 spec lines in `rom/rules/modes/` and the 58 rows of `rom/rules/switch_handlers.csv` still tagged observed, to re-cite from the code; about 1,560 structural names to refine |

Boards without their own CPU, MCU, ROM or firmware, or with programmable logic the owner ruled out of rule 1, listed so nobody looks for one (not checked by the tool):

| Board | Why it has no firmware |
|---|---|
| SAM CPU board, Xilinx logic (two XC95144XL CPLDs: DMD scan, audio playback, switch/IO glue) | **not decoded, owner decision (Vincent, 2026-11-25: "On ne les décode pas")**. No program: a fuse map in flash, not in the PinMAME set nor in `tf_180.bin`, written at the factory through the JTAG header J8, which the ARM cannot read. Fixed function, no game logic; behaviour documented in Stern-SAM-Decryption `knowledge/sam_hardware/CPU_BOARD_IO.md` (DMD 128x32 at 62.67 Hz, 16 shades; sound FIQ about 4 kHz) |
| SAM IO power driver board (520-5249-00) | decoders and edge-triggered latches; every pulse width is what the CPU writes (`knowledge/sam_hardware/README.md`) |
| 12-transistor aux driver board (PinMAME `SAM_GAME_AUXSOL12`, CSTB/DSTB) | latches on its strobe |
| 128x32 DMD panel | scanned by the CPU board's CPLDs |
| Shaker motor kit (optional), speakers and amplifier | no logic |

Last updated 2026-11-25.
