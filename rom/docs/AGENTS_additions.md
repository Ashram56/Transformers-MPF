# Additions for AGENTS.md (Tron-Legacy-LE-ROM-Decryption), learned on Transformers Pro 1.80 (tf_180)

The second SAM ROM run through the AGENTS.md method. Each item names the AGENTS.md section it belongs to. Fact
tags: **code**, **observed**, **inferred**. TF addresses are in `rom/README.md` and `rom/tools/trace/README.md`.

## §0 Ground rules

- **Find the OS table registry first (code).** The OS keeps a table of tables, `(address, count, record size)`
  triples, at file 0x30b00-0x30d10 on tf_180 (43 tables: adjustments, audits, coils, deffs, leffs, lamps, lamp
  groups, messages, sound calls, switches, ...). Finding it gave every table at once; per-table searches are not
  needed after that. Look for a run of triples whose addresses fall in 0x04000000-0x04800000.
- **Never trust names carried over from another game's decompile.** Function names copied from Tron's Ghidra
  project landed on TF functions at the same address with different meaning (e.g. `deff_093_zuse...`). Rename
  deff/leff functions from this ROM's own tables (`tools/event_map.py`) and treat other carried names as
  unreliable.
- **Re-run captures in small batches and compare with the previous run before replacing it.** A full re-capture
  of the display effects (33 effects per emulator run) came back empty for 25 effects that had rendered before;
  re-running them 4 per run recovered 21. Always diff page/frame counts per effect against the last capture and
  merge per effect instead of replacing the folder.

## §2 Memory map

- tf_180: OS 0x0-0x34057 (copied to SRAM by the reset code at 0x84), RAM from 0x34058, game code at 0x01000000 =
  file 0x40000 (0x6f090 bytes, copied at 0x160), data at 0x04000000 = the first 8 MB of the file. The OS code end
  moves between games; read it from the reset copy loop, not from Tron's value.
- RAM 0x39400-0x3fc00 is unused on tf_180 and works as scratch for injected calls (stack 0x3f400, buffer 0x3ee80).

## §3.2 PinMAME with an ARM hook

- **Tron's `pinmame_arm_hook.patch` is incomplete.** Its `src/cpu/arm7/*` hunks are what actually call the hook;
  without them the hook is never called. `rom/tools/trace/pinmame_hooks.patch` has the full patch.
- **Add a bus hook** `PinmameSetBusHook(addr, data, mask, write)` on the SAM bus. It sees every solenoid register
  write (SOL_B 0x02400021 = coils 1-8, SOL_A 0x02400020 = 9-16, SOL_C 0x02400022 = 17-24, FLSH_LMP 0x02400023 =
  25-32, written every 250 us), which gives exact coil pulse and hold times. `PinmameGetSolenoid` polling cannot.
- `PINMAME_NOJIT=1` is required (the hook needs the interpreter).

## §5 OS API and tables

- **The image table index is not the image's own id (code).** The image table (resource block, 0x123694 on
  tf_180, 10,212 images) is indexed by image number, and each image header carries an id that is *not* the
  index. Delta frames apply on top of the image whose *header id* is one less.
- **Doubled score events (observed pitfall).** `score_add` (0x1caf0) tail-calls `score_add_player` (0x1cb0c).
  Hooking both logs every award twice; hook only the inner one. Agent C's first trace mismatch came from this.
- **Pointer arithmetic in Ghidra output.** Ghidra rendered some per-completion terms as pointer arithmetic
  (`(int *)x + n` = x + 4n), so a literal read gave values 4x too small (6,250 instead of 25,000). Check any
  scaled value from the decompile against a trace before writing it in a spec.
- **Text helpers (code).** Seven helpers draw effect text: 0x21660 text_printf_msg, 0x215ac text_draw_msg_page,
  0x217b4 text_printf_msg_fit_page, 0x2174c text_draw_msg_fit (message id in r0), and 0x21838 text_draw_str_page,
  0x21a78 text_printf_page, 0x21b4c text_draw_str_fit_page (string or format in r0). Printf varargs start at
  entry sp+12 for 0x21660/0x21a78 (7 fixed arguments) and sp+16 for 0x217b4 (8). Hooking these, not only the
  low-level `text_draw_str`, gives the format and arguments behind every drawn string.
- **Fit fonts (code).** A font operand that is a pointer names a 0-terminated u32 list of font ids;
  `text_draw_str_fit` (0x21b90) uses the first whose width fits (the width argument, or the 128-px screen for
  the alignment when the width is 0). Font 0 is the last resort.
- **Music / background table (code).** Walked by 0x178b0. Entry: mask +4, condition fn +0xc, deff +0x10, sound
  +0x12, chooser fn +0x14. It picks both the background display effect and the music for the game state.
- **Settings code is Tron's, shifted (code).** Every adjustment, audit, pricing and menu function exists with the
  same body at a new address (list in `rom/rom_data/settings/README.md`); `tools/settings_extract.py` is the
  port. Country overrides can be tested through NVRAM (0x21100d8 + checksum 0x1c50 + factory reset 0x728)
  instead of DIP switches.

## §6 Sound

- **Stream scripts can sit at the very end of the file (code).** On tf_180 they are in bank 3 (0x1d1a664); a
  search of the first 12 MB for stream pointers found nothing. Search the whole image.
- **Parse `call=` from the tracer as hex.** The tracer prints sound calls with `%x`; parsing them as decimal
  silently mapped calls to the wrong sounds. Store calls as hex strings everywhere.
- Hook `snd_play` (0x251f4) and save its caller; inside `snd_resolve` (0x25044) lr always points back into
  `snd_play`.

## §7 Display effects

- Background effects (deff flag bit 0, not bit 1) never get a forced end; close their capture window at the end
  of the log or they are lost.
- Background effects need a capture window of at least 14 s per run (10 s ended before some rendered).
- About 35 effects end within 0.3 s when forced because they read game state; they need live play or RAM pokes
  (tracer env `POKE=addr=value[:size],...`).

## §8 Lights, coils and IO

- **Lamp effects (code + observed).** Leff table 0x040cfe00, 12-byte records `{fn, u16 flags, u16 lamp group,
  u16 coil group, u16 prio}`. The lamp compositor tick (0x73cc) merges the base image, the shared leff layer
  (image 0x36394, mask 0x363a8) and a layer list at 0x31480 (image +0..0x13, mask +0x14, owner task +0x20,
  next +0x24). Capturing only lamps whose layer owner is the leff task (`tools/emu/lfx.cpp`, Tron's lfx port)
  gives clean shows: 178 leffs, 119 end by themselves, 59 loop until stopped.
- Coil 24 fires 81 ms on each coin: the coin meter (inferred).

## §9 Rules extraction

- Task struct on tf_180: deff id +0x24, flags u16 +2 (0x20 = leff task), leff id +0x28, prio +0x2a, task arg
  +0x30, next +0x1c; list head 0x314a0, current task 0x314b0. Call injection by hijacking `task_sleep` (0xacfc)
  works as on Tron.
- The ball save blocks drains in scenarios; scenarios that test end of ball must wait it out or disable it.
- Side byte (Autobot/Decepticon) is at 0x02112107 + player (not player - 1): per-player arrays are not all
  indexed the same way, check each one.
