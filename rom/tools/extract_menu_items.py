"""The service menu items' icons as CSV: rom/rom_data/settings/menu_items.csv. Usage: TF_ROM=... python3
extract_menu_items.py OUTDIR

The menu item table is the array descriptor 0x00030cf8 in RAM {base 0x040e3c40, count 131, stride 20}
(array_entry_e3a0 [0x0000e3a0]; the values the ROM's start-up leaves there, read with switch_lift.SwitchRunner).
post_event_5b_bitmap_draw2_3f47c [0x0103f47c] draws a menu: each item's icon, image +0xe when it is the current
item (with its text, message +0xc, font 2 centred at (64, 0x1e)) and image +0xe + 1 otherwise.
"""
import csv, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, foff
from tables import msg

BASE, COUNT, STRIDE = 0x040e3c40, 131, 20


def main(out):
    rows = []
    for i in range(1, COUNT):
        a = BASE + STRIDE * i
        m, img = struct.unpack_from('<HH', ROM, foff(a) + 0xc)
        rows.append(dict(item=i, text=msg(m) if m else '', msg='0x%x' % m, image=img, image_other=img + 1,
                         addr='0x%08x' % a))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'menu_items.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    print(len(rows))


if __name__ == '__main__':
    main(sys.argv[1])
