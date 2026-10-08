"""Adjustments (99 x 32 B) and audits (167 x 16 B) as CSV. Usage: python3 extract_settings.py OUTDIR
Adjustment record (Tron layout, matches here): nvram addr, default, min, max, step, ?, name record ptr, display type.
The table default is not always the factory default: per-country install lists can override it (Tron mistake log)."""
import sys, os, csv, struct
sys.path.insert(0, os.path.dirname(__file__))
from rom import *
from tables import rec
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
def w(fn, rows):
    with open(os.path.join(OUT, fn), 'w', newline='') as f:
        d = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); d.writeheader(); d.writerows(rows)
rows = []
for i in range(1, 99):
    a = rec('adjustments', i); nv, df, mn, mx, st, f5, np, dt = struct.unpack_from('<IiiiiiII', ROM, foff(a))
    rows.append(dict(adj=i, name=cstr(u32(np)), default_table=df, min=mn, max=mx, step=st, field_0x14=f5, display_type=dt,
                     nvram='0x%x' % nv, desc_addr='0x%x' % a, tag='code (table); default may be overridden by country install lists'))
w('adjustments.csv', rows)
rows = []
for i in range(1, 167):
    a = rec('audits', i); fn, np, w2, w3 = struct.unpack_from('<4I', ROM, foff(a))
    rows.append(dict(audit=i, name=cstr(u32(np)) if np else '', formula_fn='0x%x' % fn if fn else '', w_0x08='0x%08x' % w2,
                     w_0x0c='0x%08x' % w3, desc_addr='0x%x' % a))
w('audits.csv', rows)
print('adjustments', 98, 'audits', len(rows))
