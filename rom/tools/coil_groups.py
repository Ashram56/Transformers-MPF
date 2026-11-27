"""Coil groups of tf_180: table 0x040cf65c (group -> pointer to a zero-terminated list of ROM coil numbers), read by
coilgroup_pulse [0x00005fd4] and the leff conflict test leff_name_check_611c [0x0000611c]; groups 1..0x3d.
Writes rom/rom_data/io/coil_groups.json. Usage: TF_ROM=tf_180.bin python rom/tools/coil_groups.py"""
import json
import os

import rom

TABLE, GROUPS = 0x040cf65c, 0x3e


def coil_group(g):
    p, out = rom.u32(TABLE + 4 * g), []
    while rom.u8(p):
        out.append(rom.u8(p))
        p += 1
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "rom_data", "io", "coil_groups.json")
    json.dump({str(g): coil_group(g) for g in range(GROUPS)}, open(path, "w"), indent=0)
    print(path)
