# Transformers Pro 1.80: ROM extraction

Agent A (ROM extraction) of the master plan in
[Tron-Legacy-MPF `docs/agents/README.md`](https://github.com/Ashram56/Tron-Legacy-MPF/blob/main/docs/agents/README.md),
following [AGENTS.md](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption/blob/main/AGENTS.md) of the Tron
extraction. Everything here was read from the ROM image; the image itself is copyrighted and is never committed.

## The ROM

| | |
|---|---|
| File | `tf_180.bin`, 30,560,052 bytes, SHA1 `62e1328e8462680694157aca266055d57347e904`, CRC32 `0b6e3a4f` |
| PinMAME set | **`tf_180`**, "Transformers (V1.8)", 2013 (clone of `tf_180h`) |
| Model | **Pro**. The LE 1.80 is a separate image (`tf_180h`); nothing here covers it |
| Stern README | V1.8, March 14, 2013 (redemption system, Autobot/Decepticon high score tables, MB progression) |
| PinMAME driver | `SAM_GAME_AUXSOL12` (12-transistor aux driver board on CSTB/DSTB), lamp 58 and 60-62 as strobed LEDs |

## Layout

| Path | What it is |
|---|---|
| `rom_data/rom_map.json` | Memory map, the OS resource block, and the OS **table registry** (43 tables: address, count, record size, name) |
| `rom_data/io/` | `switches.csv` (64 matrix), `dedicated_switches.csv` (D1-D32 with PinMAME numbers), `coils.csv` (35, flags decoded, test/ball-search times, wire colours), `lamps.csv` (80) |
| `rom_data/sound/` | `samples.csv` (668 directory entries: kind, rate, duration, ROM length check, loop point, stream offsets), `sound_calls.csv` (705 calls: sample list, raw fields) |
| `rom_data/dmd/images.csv` | All 10,212 images: header fields and file offset |
| `rom_data/dmd/deffs.csv` | The 155 display effects (deffs): function, flags, priority, background flag, capture summary |
| `rom_data/io/coil_timing.csv` | Every coil's pulse, ball-search and hold times measured from the solenoid register writes in the emulator; `coils.csv` carries the `mpf_default_pulse_ms`, `mpf_default_hold_power` and `mpf_source` this gives, and `coils.yaml` uses them |
| `rom_data/sound/sound_call_uses.csv` | Per sound call: role where identified (coin, credit, tilt, ball save, drain, launch, music), how it was identified, scenarios it was heard in, deffs that play it, code call sites |
| `rom_data/sound/music_table.csv` | The ROM's background table: 18 prioritized entries, each a condition plus a background deff and its music call (base music per side, mode music) |
| `rom_data/io/lamp_effects.csv`, `lamp_groups.json` | The 178 lamp effects (leffs): function, flags, lamp group, coil group, priority, how the capture ended, loop, show file, lamps and flashers used, who starts it; the 148 lamp groups |
| `mpf_package/config/shows/lampfx_NNN.yaml` | 111 lamp effects as MPF shows, captured in the emulator (`tools/emu/lfx.cpp`); looping ones cut to one period |
| `rules/switches_and_shots.md`, `rules/switch_handlers.csv` | Every playfield switch hit twice on a fresh ball: points and who awarded them, sounds, display and lamp effects, coils; the side choice; the end-of-ball bonus |
| `rules/traces/` | Scenarios and reference traces from the real ROM (`tools/trace/tf_ref`, a port of Tron's `tron_ref`) |
| `rom_data/fonts.json` | The 27 fonts, Tron `fonts.json` layout (ranges, glyph to image number, height, spacing) |
| `rom_data/settings/` | `adjustments.csv` (99: NVRAM slot, default, min, max, step, name, display type), `audits.csv` (167) |
| `code/tf_decompiled.c` | Ghidra 11.4.2 decompile of OS and game code, 3,000+ functions, OS API and deff/leff functions named |
| `mpf_package/event_map.csv` | One row per deff: name, priority, background loop, ROM text, frames, run time, sounds and lamp effects heard and in code, images drawn, library animations, callers |
| `mpf_package/media/dmd/deffs/deff_NNN/` | Per effect captured in the emulator: `frames/NNNN.png` (grey, level x 17), `reference_capture.gif` and `_x4.gif`, `timing.json` (frame times, every image and text draw per shown page, sounds, lamp effects, events) |
| `mpf_package/config/` | MPF v6 config: `switches.yaml`, `coils.yaml`, `lights.yaml`, `sounds.yaml` (659 sounds, 694 pools, one per sound call) |
| `mpf_package/mpf_names.json` | SAM number to MPF device name, for the VPX extraction agent and the recreation |
| `mpf_package/media/sounds/{speech,sfx,music}/XXXX.wav` | Every sample, file name = ROM sample id |
| `mpf_package/media/rom_images_all.zip` | Every ROM image as PNG (`img_NNNNN.png`, NNNNN = image number the code draws) |
| `mpf_package/media/dmd_library/` | 274 full-height animations: `frames/*.png`, `animation.gif`, `animation_128x32.gif`, `index.json` |
| `tools/` | The readers and exporters (Python), emulator probes (C++, libpinmame with the ARM hook), Ghidra scripts |

Fact tags as in AGENTS.md: **code** (read from the ROM or its tables), **observed** (emulator), **inferred**.

## What was found (and how, for the next ROM)

- **Memory map (code).** OS 0x0-0x34057 (copied to SRAM by the reset code at 0x84), RAM from 0x34058, game code
  0x01000000 = file 0x40000 (0x6f090 bytes, copied at 0x160), data at 0x04000000 = the first 8 MB of the file.
- **Table registry (code).** The OS keeps a table of tables at file 0x30b00-0x30d10: `(address, count, record size)`
  triples for adjustments, audits, coils, deffs, leffs, lamps, lamp groups, messages, sound calls, switches,
  dedicated switches and more. Finding it gave every table at once (see `rom_map.json`).
- **Resource block (code).** File 0x30e74: font table 0x123478 (27 fonts), image table 0x123694 (10,212), sample
  directory 0x120048 (668). The image table is indexed by image number; each image header carries its own id,
  which is *not* the table index (delta frames apply on top of the image whose header id is one less).
- **Sound (code, checked against the ROM).** Same format as Tron. The stream scripts sit at the very end of the
  file (bank 3, 0x1d1a664), which is why a search of the first 12 MB for stream pointers found nothing. Every one
  of the 664 ADPCM streams is referenced and exported; 658 of 659 decoded samples match the ROM's own duration
  field; sample 0x02e plays a fade-out envelope (opcode 09) and its script length differs from the stream
  (stream exported whole). Channel mask 0x02 = speech (397, mostly 12 kHz, 18 at 24 kHz), 0x01 = music (25),
  others sfx. 18 music scripts are an intro plus a body that loops (`07 00` label, `03 00` jump): exported as one
  WAV with `loop_start_at`.
- **Images (code).** Formats 0, 1, 3, 7, 9, 12 as on Tron. Most animations are 87x32 (drawn at x = 41 on Tron;
  assumed here until display effects are captured), 693 images are full 128x32.
- **Display effects (code + observed).** Deff table record `{u32 fn, u16 flags, u8 priority}`. Flag bit 0 marks
  the 21 background effects (attract, status panel 40, mode backgrounds), bit 1 most foreground effects. The deff
  id is the u16 at task+0x24 of the deff task. Effects were captured by calling `deff_start(id)` from the
  `task_sleep` hook in a started game (`tools/emu/tracer.cpp`). 153 of 155 rendered; 8 and 22 are stubs. About 35
  end within 0.3 s when forced because they read game state (mode scores, shots lit) and need live play to show.
  Every image the effects draw goes through `bitmap_draw` and every glyph through `text_draw_str`, so
  `timing.json` lists those two and leaves out the blits under them.
- **Animations (observed).** 87-wide animations are drawn at x = 41 (3,447 draws seen), right of the 41-column
  status panel. 49 library animations have a measured frame time (median step), now in `index.json` and their
  GIFs; the other 225 were not drawn in the captures and keep the 50 ms placeholder.
- **Coils (observed).** Timed from the 250 us solenoid register writes. Flippers: 40.5 ms then hold at 1 ms on
  every 12 ms (duty 0.083). Pops 34 ms in play (64 ms in ball search and coil test), slings 67-68 ms, trough,
  launch, eject and Optimus target 64-65 ms. The orbit gate (5) and the motors (8, 30) are held, not pulsed.
  Coil 24 ("OPTIONAL COIL") fires 81 ms on every coin: it is the coin meter output (inferred).
- **Music (code + observed).** Background deff and music come from an 18-entry priority table walked by
  0x178b0 (entry: state mask, condition function, deff, sound call, optional chooser function). The side the
  player picks (u8 at 0x02112107 + player) selects between paired calls: 0x1a/0x1b choose-side screen,
  0x1c/0x1d ball start, 0x1e/0x1f main play, 0x31/0x34 battle ready; modes and multiballs have their own
  entries. Which value is Autobot is inferred (1 = Autobot).
- **Lamp effects (observed).** Captured by injecting `leff_start(id)` with a ball in the shooter lane and reading,
  on every lamp compositor tick (0x73cc), only the lamps the effect's own task owns (shared leff layer 0x36394 /
  mask 0x363a8 and the layer list at 0x31480). 119 end by themselves, 59 run until stopped. 111 produce lamps or
  flasher pulses; the other 67 draw from game state, need a lamp parameter from their caller, or were refused.
- **Side choice (code + observed).** Side byte 0x02112107 + player: 1 = Autobot, 2 = Decepticon (default).
  Either flipper toggles it on the choose-side screen; the plunge confirms it 31 ticks later (deff 41).
- **Names in the decompile.** OS functions were named by matching Tron's decompile (same OS). Game-code
  functions that matched a Tron game function keep Tron's name (for example `dbattle_can_progress`): the code
  is alike but the meaning on Transformers can differ. Deff and leff functions are named from this ROM's tables.
- **IO (code).** Name tables use the Tron 24-byte, five-language records. Coil descriptor layout is the Tron one
  (flags, test fn, ball-search fn, name, test ms, ball-search ms, two wire colour message ids). Coil register map
  (1-8 SOL_B, 9-16 SOL_A, 17-24 SOL_C, 25-32 FLSH_LMP, 33-35 aux) is the SAM standard and not yet confirmed from
  this ROM's IO pointer block.

## Status

Delivered: IO tables, all sounds with one pool per sound call, all images and the animation library, fonts,
adjustments and audits, the decompile, the display effect captures and the event map.

Also delivered: coil timing, sound call roles and the music table, the reference tracer with six traces, the
lamp effects as shows, the switch handler spec with the side choice and the bonus.

Next, in this order: settings in package format with pricing, the format string behind each text draw, rules
specs per mode with traces, switch flags.

Open items:
1. The aux strobe outputs (PinMAME maps CSTB/DSTB to solenoids 51-56 and 59-64) were not seen firing yet. The
   coil register map is PinMAME's SAM map, and the measured pulses match each coil's role.
2. 225 library animations keep a 50 ms placeholder frame time; about 35 effects need live play to capture.
3. Meaning of the sound call fields at +0x0c..+0x13 (`flags_0x10` holds values like 0x1b0, 0x1ff) is not decoded.
4. 60 samples are in no sound call; they may be played directly or be unused.
