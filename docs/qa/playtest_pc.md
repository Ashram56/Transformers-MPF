# Play test on the owner's PC: what this cloud session could not check

Since 2026-11-26 the cloud session runs Godot 4.6.3 itself (Xvfb, OpenGL renderer: `scripts/render_check.py`), so
the DMD is checked there: the live op replay of the bonus (QA final F069) was captured on the `basic` scenario
(BONUS, then 1X 130,360, then TOTAL BONUS 130,360, with the status panel going 238,420 to 368,780), and the trough
test's inverted switch boxes (F064) were checked in Godot pixel by pixel. What needs a real machine:

| # | What | How to check | Why not here |
|---|---|---|---|
| 1 | Smoothness of the deffs replayed live (F069, F074: 151 of 155 since 2026-11-27, a background and a foreground one at a time): one Python replay per 16 ms tick and a 128x32 frame per change sent to Godot | play a game to the end of a ball with a bonus multiplier (2X or more), a battle with shots, a pops burst; the pages must move without stutter and the values must stay right during the moves | the container's CPU and Xvfb are not a PC; the frame rate under load matters on Windows and macOS |
| 2 | Sounds of those deffs | same game: the bonus count sounds (0x76, 0x77, 0x79), the battle shot sounds | no audio device in the container |
| 3 | PuP Pack videos at those deffs | `run.py` with the PuP on: the videos the pack plays at the bonus, combos and battle shots still come (the `tf_deff_<id>` events are unchanged) | GoZen video decoding on the GPU, three screens |
| 4 | Lamp levels 1/3 and 2/3 (F067) | MPF Monitor and VPX: the lamps of leffs 1, 37, 95, 147, 151 at their dim steps | MPF Monitor and VPX are not run here |
| 5 | LOCATING PINBALLS (F071) | in VPX, leave a ball stuck (or remove one) with another in the shooter lane, press START in attract: deff 11, the search coils, no game; START again plays | VPX only (the virtual hardware always has its balls) |
| 6 | Installer bundle | a fresh install on Windows: `rom/mpf_package/media/rom_images_mask.zip` and `game/media/live_ops/` must be there (scripts/package/game_package.json, scripts/gen_media.py) | the bundle is built and installed on the PC |
