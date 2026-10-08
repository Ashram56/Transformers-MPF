"""Switches, dedicated switches, coils and lamps of tf_180 as CSV. Usage: python3 extract_io.py OUTDIR"""
import sys, os, csv, struct
sys.path.insert(0, os.path.dirname(__file__))
from rom import *
from tables import TABLES, rec, msg
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
def hx(v, w=0): return ('0x%0' + str(w) + 'x') % v if w else '0x%x' % v
def wcsv(fn, rows):
    with open(os.path.join(OUT, fn), 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
# ---- switches: 32 B records, index = switch number (record 0 unused)
def sw_row(a, num, ded=None):
    h, p4, nm, f0c = struct.unpack_from('<4I', ROM, foff(a))
    w10, w12, w14, w16, m18 = struct.unpack_from('<5H', ROM, foff(a) + 0x10)
    b1a, b1b, b1c = ROM[foff(a) + 0x1a], ROM[foff(a) + 0x1b], ROM[foff(a) + 0x1c]
    return dict(number=num, name=cstr(u32(nm)) if nm else '', handler=hx(h) if h else '', handler_arg=p4,
                flags_0x0c=hx(f0c, 8), w_0x10=w10, w_0x12=w12, w_0x14=w14, w_0x16=w16,
                msg_0x18=m18, msg_0x18_text=msg(m18) or '', id_0x1a=b1a, b_0x1b=b1b, b_0x1c=b1c, desc_addr=hx(a))
rows = []
for i in range(1, 65):
    r = sw_row(rec('switches', i), i)
    col, row = (i - 1) // 16, (i - 1) % 16
    r2 = dict(number=i, name=r['name'], matrix_column=col, matrix_row=row, pinmame_switch=i)
    r2.update({k: v for k, v in r.items() if k not in ('number', 'name')}); rows.append(r2)
wcsv('switches.csv', rows)
# PinMAME numbers of the SAM dedicated switches (external: PinMAME src/wpc/sam.c and sam.vbs, same as Tron)
PINMAME_DED = {1: 65, 2: 66, 3: 67, 4: 68, 5: 69, 6: 70, 7: 71, 8: 72, 9: 84, 10: 83, 11: 82, 12: 81, 13: 88, 14: 87, 15: 86, 16: 85,
               17: -7, 18: -6, 19: -5, 20: -4, 21: -3, 22: -2, 23: -1, 24: 0}
ded = []
for i in range(0, 32):   # record i = dedicated switch D(i+1) = SAM switch 129+i (no INVALID record here)
    a = rec('dedicated_switches', i); r = sw_row(a, 129 + i)
    if not r['name']: continue
    r2 = dict(dedicated='D%d' % (i + 1), rom_switch_number=129 + i, name=r['name'], pinmame_switch=PINMAME_DED.get(i + 1, ''))
    r2.update({k: v for k, v in r.items() if k not in ('number', 'name')}); ded.append(r2)
wcsv('dedicated_switches.csv', ded)
# ---- coils: 28 B records; register map is the SAM standard one (Tron io_registers.csv)
FLAG_BITS = [(0x1,'aux'),(0x2,'power_exempt'),(0x4,'flasher'),(0x8,'flipper'),(0x40,'ball_device_kicker'),(0x80,'optional'),
             (0x100,'motor_or_long'),(0x400,'no_cycle_test'),(0x800,'hidden_in_tests'),(0x2000,'bumper'),(0x4000,'relay'),(0x10000,'solenoid')]
REGS = [('SOL_B', 0x02400021), ('SOL_A', 0x02400020), ('SOL_C', 0x02400022), ('FLSH_LMP', 0x02400023)]
crows = []
for i in range(1, 36):
    a = rec('coils', i)
    fl, tfn, bfn, nm = struct.unpack_from('<4I', ROM, foff(a)); tms, bms, w1, w2 = struct.unpack_from('<4H', ROM, foff(a) + 0x10)
    num = ROM[foff(a) + 0x18]
    if i <= 32: reg, addr = REGS[(i - 1) // 8]; bit = (i - 1) % 8; addr = hx(addr)
    else: reg, addr, bit = 'AUX_DRV (aux bus)', '0x02400026 + strobe on 0x0240002B', i - 33
    known = sum(b for b, _ in FLAG_BITS)
    crows.append(dict(coil=i, name=cstr(u32(nm)), register=reg, reg_address=addr, bit=bit, desc_addr=hx(a), flags_hex=hx(fl, 8),
                      flags_decoded=' '.join(n for b, n in FLAG_BITS if fl & b) + (' unknown_%s' % hx(fl & ~known) if fl & ~known else ''),
                      test_pulse_ms=tms, test_fn=hx(tfn) if tfn else '', ballsearch_ms=bms, ballsearch_fn=hx(bfn) if bfn else '',
                      wire_color_1=msg(w1), wire_color_1_msg=hx(w1), wire_color_2=msg(w2), wire_color_2_msg=hx(w2), id_0x18=num,
                      tag='code (descriptor); register map SAM standard, flag names from Tron (same OS), not re-verified on tf_180'))
wcsv('coils.csv', crows)
# ---- lamps: 12 B records {name ptr, ?, ?, u8 number}
lrows = []
for i in range(1, 81):
    a = rec('lamps', i); nm, w4, w8 = struct.unpack_from('<3I', ROM, foff(a))
    line, bit = (i - 1) // 8, 7 - ((i - 1) % 8)
    lrows.append(dict(lamp=i, name=cstr(u32(nm)) if nm else '', strobe_line=line, drive_bit=bit, pinmame_lamp=i,
                      w_0x04=hx(w4), id_0x08=ROM[foff(a) + 8], b_0x09=ROM[foff(a) + 9], desc_addr=hx(a)))
wcsv('lamps.csv', lrows)
print(len(rows), len(ded), len(crows), len(lrows))
