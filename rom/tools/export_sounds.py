"""Decode every sample in the directory to media/sounds/<kind>/<id>.wav and write samples.csv.
Usage: python3 export_sounds.py OUTDIR"""
import sys, os, struct, wave, csv, json
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sound import *
OUT = sys.argv[1]
ents = directory(); ends = script_ends(ents)
def kind(mask): return 'music' if mask == 1 else 'speech' if mask == 2 else 'sfx'
def job(i):
    s = script_info(i, ents, ends)
    if not s['streams']: return dict(sample=i, mask=s['mask'], kind='stub', streams=0)
    import numpy as np
    raw = s['raw']; parts = []; rates = set(); counts = []
    for t in s['streams']:
        a, r, c = decode(t); parts.append(a); rates.add(r); counts.append(c)
    assert len(rates) == 1
    rate = rates.pop()
    # music: "07 00" label before the 2nd stream and "03 00" goto after it = loop that stream
    loop_at = None
    if len(parts) == 2 and b'\x07\x00\x0a\x00' in raw and raw.rstrip(b'\xff').endswith(b'\x03\x00'):
        loop_at = len(parts[0]) / rate
    a = np.concatenate(parts)
    k = kind(s['mask']); d = os.path.join(OUT, 'media', 'sounds', k); os.makedirs(d, exist_ok=True)
    fn = '%04x.wav' % i
    with wave.open(os.path.join(d, fn), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes())
    dur = len(a) / rate
    rom_dur = s['len32'] / 4000
    return dict(sample=i, mask=s['mask'], kind=k, streams=len(parts), rate=rate, samples=len(a),
                duration_s=round(dur, 4), rom_len32=s['len32'], rom_duration_s=round(rom_dur, 4),
                length_check='ok' if abs(dur - rom_dur) < 0.01 or len(parts) > 1 else 'MISMATCH',
                loop_start_s=round(loop_at, 4) if loop_at else '', file='media/sounds/%s/%s' % (k, fn),
                script_file_offset='0x%x' % s['off'], stream_file_offsets=' '.join('0x%x' % t for t in s['streams']))
if __name__ == '__main__':
    with Pool(4) as p: rows = p.map(job, range(len(ents)))
    keys = ['sample','kind','mask','streams','rate','samples','duration_s','rom_len32','rom_duration_s','length_check','loop_start_s','file','script_file_offset','stream_file_offsets']
    with open(os.path.join(OUT, 'samples.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, keys, extrasaction='ignore', lineterminator='\n'); w.writeheader()
        for r in rows:
            r = dict(r); r['sample'] = '0x%03x' % r['sample']; r['mask'] = '0x%02x' % r['mask']; w.writerow(r)
    import collections
    print(collections.Counter(r['kind'] for r in rows), collections.Counter(r.get('length_check') for r in rows))
