"""Game flags of tf_180: the attribute table [0x040cf458], 4 bytes per flag (flags 1..0x4d).

    python rom/tools/game_flags.py > rom/rom_data/io/game_flags.csv        (TF_ROM set)

Record: u16 attributes, u8 default value, u8 unused. Attribute bits, from the OS code that reads them:
- 0x1 global: the flag is not part of a player's saved set. Without it the flag is per player: the end of a ball
  that changes the player saves the current flags to the leaving player's copy [0x00005bb0] and loads the next
  player's, keeping the global ones [0x00005bf4] (both from the player change, near 0x0001ac64);
- 0x2 reset to the default at game start (game_init -> FUN_00005870(2); per-player flags in all four copies);
- 0x4 reset at every ball start (ball_start -> FUN_00005870(4));
- 0x8 reset at a tilt (FUN_00005870(8)).
"""
import rom

TABLE, FLAGS = 0x040cf458, 0x4e

print("flag,hex,attr,default,per_player,reset_game,reset_ball,reset_tilt")
for flag in range(1, FLAGS):
    attr, default = rom.u16(TABLE + 4 * flag), rom.u8(TABLE + 4 * flag + 2)
    print("{},0x{:02x},{},{},{},{},{},{}".format(flag, flag, attr, default, int(not attr & 1), int(bool(attr & 2)),
                                                 int(bool(attr & 4)), int(bool(attr & 8))))
