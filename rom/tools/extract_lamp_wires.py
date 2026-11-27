"""The lamp wire tables of the lamp tests as CSV: rom/rom_data/io/lamp_wires.csv. Usage: TF_ROM=... python3
extract_lamp_wires.py OUTDIR

The lamp tests read two array descriptors in RAM {base, count, stride} (array_entry_e3a0 [0x0000e3a0]):
0x00030c14, the 10 lamp rows (start_leff_5 [0x0104aeac], lamp_column_of_75cc [0x000075cc]), base 0x040d11c8, and
0x00030c20, the 8 lamp columns (start_leff_6 [0x0104a0d0], lamp_row_mask_7604 [0x00007604]), base 0x040d1220;
stride 8: u16 messages wire colour, connector pin, driver, then the index (entry 0 empty). The descriptors are
the values the ROM's start-up leaves in RAM (read with switch_lift.SwitchRunner, a Unicorn run of the ROM's code).
"""
import csv, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, foff
from tables import msg

TABLES = (("row", 0x040d11c8, 11), ("column", 0x040d1220, 9))


def main(out):
    rows = []
    for name, base, count in TABLES:
        for i in range(1, count):
            wire, pin, driver, idx = struct.unpack_from('<4H', ROM, foff(base + 8 * i))
            rows.append(dict(table=name, index=idx, wire=msg(wire), pin=msg(pin), driver=msg(driver),
                             wire_msg='0x%x' % wire, pin_msg='0x%x' % pin, driver_msg='0x%x' % driver,
                             addr='0x%08x' % (base + 8 * i)))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'lamp_wires.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    print(len(rows))


if __name__ == '__main__':
    main(sys.argv[1])
