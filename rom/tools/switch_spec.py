"""Per-switch rules table from the tf_ref switches trace (each playfield switch hit twice in a fresh game,
ball in play, after one validating sling hit) joined with the switch table and the decompile.
Usage: switch_spec.py ROMDIR TRACE OUT_CSV"""
import sys, os, re, csv, json, bisect, collections

def main(romdir, trace, out):
    sw = {int(r['number']): r for r in csv.DictReader(open(os.path.join(romdir, 'rom_data/io/switches.csv')))}
    snd = {r['call']: r['role'] for r in csv.DictReader(open(os.path.join(romdir, 'rom_data/sound/sound_call_uses.csv')))}
    dname = {int(r['deff']): r['name'] for r in csv.DictReader(open(os.path.join(romdir, 'mpf_package/event_map.csv')))}
    aud = {int(r['audit']): r['name'] for r in csv.DictReader(open(os.path.join(romdir, 'rom_data/settings/audits.csv')))}
    c = open(os.path.join(romdir, 'code/tf_decompiled.c')).read()
    hdr = [(int(m.group(1), 16), m.group(2)) for m in re.finditer(r'^// ==== ([0-9a-f]{8}) (\S+)', c, re.M)]
    st = [h[0] for h in hdr]
    def fn(a):
        i = bisect.bisect_right(st, a) - 1
        return '0x%x' % hdr[i][0] if i >= 0 else '0x%x' % a
    segs = collections.OrderedDict(); cur = None
    for l in open(trace):
        e = json.loads(l)
        if e['ev'] == 'mark': cur = e['text']; segs[cur] = []; continue
        if cur: segs[cur].append(e)
    rows = []
    STATUS_AUDITS = {59, 60, 61, 62, 63, 64}   # bumped on every switch (switch activity counters)
    for k, v in segs.items():
        m = re.match(r'sw_(\d+)(_again)?$', k)
        if not m: continue
        n = int(m.group(1)); again = bool(m.group(2)); r = sw[n]
        pts = [(e['points'], 'handler' if int(e['caller'], 16) == 0x14f38 else fn(int(e['caller'], 16))) for e in v if e['ev'] == 'score_add']
        rows.append(dict(
            switch=n, name=r['name'], hit='repeat' if again else 'first', handler=r['handler'], handler_arg=r['handler_arg'], switch_flags=r['flags_0x0c'],
            score_total=sum(e['delta'] for e in v if e['ev'] == 'score'),
            awards=' + '.join('%d (%s)' % p for p in pts),
            sounds=' '.join('%s%s' % (e['call'], ' [%s]' % snd[e['call']] if snd.get(e['call']) else '') for e in v if e['ev'] == 'sound' and e['call'] not in ('0x14d',)),
            deffs=' '.join('%d %s' % (e['id'], dname.get(e['id'], '')) for e in v if e['ev'] == 'deff_start' and e['id'] != 19),
            leffs=' '.join(str(e['id']) for e in v if e['ev'] == 'leff_start'),
            coils=' '.join('%d:%dms%s' % (c, ms, ' x%d' % n if n > 1 else '') for (c, ms), n in collections.Counter((e['coil'], round(e['first_ms'])) for e in v if e['ev'] == 'coil_pulse').items()),
            audit_counters=' '.join(str(x) for x in sorted({e['id'] for e in v if e['ev'] == 'audit' and e['id'] not in STATUS_AUDITS})),
            flags=' '.join(['+%d' % e['flag'] for e in v if e['ev'] == 'flag_set'] + ['-%d' % e['flag'] for e in v if e['ev'] == 'flag_clear' and e['flag'] != 8]),
            tag='observed'))
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    print(len(rows), 'rows')

if __name__ == '__main__':
    main(*sys.argv[1:4])
