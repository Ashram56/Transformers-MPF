"""Sound call table (705 x 20 B at 0x040dee08): call -> sample list. Usage: python3 extract_sounds_calls.py OUTDIR SAMPLES_CSV"""
import sys, os, csv, struct
sys.path.insert(0, os.path.dirname(__file__))
from rom import *
from tables import rec
OUT, SAMP = sys.argv[1], sys.argv[2]
kinds = {int(r['sample'], 16): r['kind'] for r in csv.DictReader(open(SAMP))}
rows = []
for i in range(705):
    a = rec('sound_calls', i)
    r0, r1, lp, f12, f14, f16, f18 = struct.unpack_from('<IIIHHHH', ROM, foff(a))
    lst = []
    if lp:
        o = foff(lp)
        while True:
            v = struct.unpack_from('<H', ROM, o)[0]
            if v == 0: break
            lst.append(v); o += 2
    ks = sorted(set(kinds.get(v, '?') for v in lst))
    rows.append(dict(call='0x%03x' % i, samples=' '.join('0x%03x' % v for v in lst), n_samples=len(lst), kinds=' '.join(ks),
                     w_0x0c=f12, w_0x0e=f14, flags_0x10='0x%03x' % f16, w_0x12=f18, state_ram_0x00='0x%x' % r0,
                     state_ram_0x04='0x%x' % r1, list_addr='0x%x' % lp, desc_addr='0x%x' % a))
with open(os.path.join(OUT, 'sound_calls.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
used = set(int(x, 16) for r in rows for x in r['samples'].split())
print('calls', len(rows), 'with samples', sum(1 for r in rows if r['n_samples']), 'samples used', len(used), 'unused', sorted(set(kinds) - used)[:40])
