"""MPF shows for the ROM's lamp effects (leffs, table 0x040cfe00) from emu/lfx.cpp captures, plus
lamp_effects.csv and lamp_groups.json. Port of Tron's build_lampfx.py (simplified: no parameter tokens).
Usage: lamp_shows.py LFX_LOGS_DIR PKG_DIR DATA_DIR DECOMP"""
import sys, os, re, json, glob, csv, struct, collections
import tables
from rom import ROM, foff, u32, u16, u8

def leff_entry(i):
    fn, flags, grp, cgrp, pr = struct.unpack_from('<IHHHH', ROM, foff(tables.rec('leffs', i)))
    return dict(fn=fn, flags=flags, group=grp, coil_group=cgrp, prio=pr & 0xff)

def lamp_group(g):
    p = u32(tables.rec('lamp_groups', g))
    if not p or foff(p) is None: return []
    o = foff(p); out = []
    while ROM[o] and len(out) < 100: out.append(ROM[o]); o += 1
    return out

def parse_logs(d):
    caps = {}
    for p in sorted(glob.glob(os.path.join(d, '*.log'))):
        cur = None
        for l in open(p):
            f = l.split()
            if len(f) < 2: continue
            try: t = float(f[0])
            except ValueError: continue
            k = f[1]
            if k == 'BEGIN': cur = dict(id=int(f[2]), t0=t, frames=[], coils=[], sounds=[], deffs=[], leffs=[], status=None, created=None); caps[cur['id']] = cur
            elif cur is None: continue
            elif k == 'RET': cur['created'] = f[3] == 'created'
            elif k == 'F' and int(f[2]) == cur['id']: cur['frames'].append((t - cur['t0'], f[3]))
            elif k == 'COIL': cur['coils'].append((t - cur['t0'], int(f[3].split('=')[1]), int(f[4].split('=')[1])))
            elif k == 'SND': cur['sounds'].append((t - cur['t0'], f[3].split('=')[1]))
            elif k == 'DEFF': cur['deffs'].append((t - cur['t0'], int(f[2])))
            elif k == 'LEFFSTART': cur['leffs'].append((t - cur['t0'], int(f[2])))
            elif k == 'END': cur['status'] = f[3]; cur['dur'] = t - cur['t0']; cur = None
    return caps

def names(pkg):
    lights = {}; flash = {}
    for m in re.finditer(r'\n  (l_\w+):\n    number: (\d+)', open(os.path.join(pkg, 'config/lights.yaml')).read()): lights[int(m.group(2))] = m.group(1)
    for m in re.finditer(r'\n  (c_\w+):\n    number: (\d+)', open(os.path.join(pkg, 'config/coils.yaml')).read()): flash[int(m.group(2))] = m.group(1)
    return lights, flash

def timeline(c, lights, coilnames):
    ev = collections.defaultdict(lambda: {'lights': {}, 'coils': {}}); prev = {}
    for t, h in c['frames']:
        mask = int(h[:20], 16); a = int(h[20:40], 16); b = int(h[40:60], 16)
        for n in range(1, 81):
            bit = 1 << (80 - n)
            if not mask & bit or n not in lights: continue
            on = bool(a & bit) + bool(b & bit)
            col = 'ffffff' if on == 2 else ('7f7f7f' if on == 1 else '000000')
            if prev.get(n) != col: ev[int(round(t * 1000))]['lights'][lights[n]] = col; prev[n] = col
    for t, coil, ms in c['coils']:
        if coil in coilnames: ev[int(round(t * 1000))]['coils'][coilnames[coil]] = '%dms' % ms
    return sorted(ev.items())

def find_period(evs):
    if len(evs) < 4: return None
    sig = [json.dumps(e, sort_keys=True) for _, e in evs]; ts = [t for t, _ in evs]
    for s0 in range(0, max(1, min(len(evs) // 3, 40))):
        for k in range(1, (len(evs) - s0) // 2 + 1):
            per = ts[s0 + k] - ts[s0]
            if per < 50: continue
            if all(sig[i] == sig[i + k] and abs((ts[i + k] - ts[i]) - per) <= 25 for i in range(s0, len(evs) - k)): return s0, k, per
    return None

def to_steps(evs, end_ms):
    steps = []
    for i, (t, e) in enumerate(evs):
        nxt = evs[i + 1][0] if i + 1 < len(evs) else end_ms
        st = {'duration': '%dms' % max(1, nxt - t)}
        if e['lights']: st['lights'] = dict(sorted(e['lights'].items()))
        if e['coils']: st['coils'] = {k: {'action': 'pulse', 'pulse_ms': int(v[:-2])} for k, v in sorted(e['coils'].items())}
        steps.append(st)
    return steps

def dump_show(path, header, steps):
    L = ['#show_version=6\n'] + ['# %s\n' % h for h in header]
    for s in steps:
        L.append('- duration: %s\n' % s['duration'])
        if 'lights' in s:
            L.append('  lights:\n'); L += ['    %s: %s\n' % (k, '"%s"' % v) for k, v in s['lights'].items()]
        if 'coils' in s:
            L.append('  coils:\n')
            for k, v in s['coils'].items(): L.append('    %s:\n      action: pulse\n      pulse_ms: %d\n' % (k, v['pulse_ms']))
    open(path, 'w').write(''.join(L))

def main(ldir, pkg, data, dec):
    caps = parse_logs(ldir); lights, coilnames = names(pkg)
    src = open(dec).read(); sites = collections.defaultdict(list); cur = None
    for line in src.split('\n'):
        m = re.match(r'// ==== ([0-9a-f]{8}) (\S+)', line)
        if m: cur = '0x%x %s' % (int(m.group(1), 16), m.group(2)); continue
        for m2 in re.finditer(r'\bleff_start\((0x[0-9a-f]+|\d+)\)', line): sites[int(m2.group(1), 0)].append(cur)
    sd = os.path.join(pkg, 'config/shows'); os.makedirs(sd, exist_ok=True)
    rows = []; show_cfg = []
    for i in range(1, 179):
        e = leff_entry(i); c = caps.get(i)
        evs = timeline(c, lights, coilnames) if c else []
        if evs and evs[0][0] < 40: t0 = evs[0][0]; evs = [(t - t0, x) for t, x in evs]
        status = (c or {}).get('status'); dur = int(round((c or {}).get('dur', 0) * 1000))
        loop = status == 'cap'; note = ''; show = ''
        body = evs; end = dur
        if loop and evs:
            fp = find_period(evs)
            if fp:
                s0, k, per = fp; state = {}
                for _, x in evs[:s0 + 1]: state.update(x['lights'])
                first = {'lights': dict(state), 'coils': dict(evs[s0][1]['coils'])}
                body = [(0, first)] + [(t - evs[s0][0], x) for t, x in evs[s0 + 1:s0 + k]]; end = per
                note = 'loops in the ROM (period %d ms)%s' % (per, '; lead-in of %d ms left out' % evs[s0][0] if s0 else '')
            elif len(evs) == 1: note = 'sets this lamp state and holds it until stopped'
            else: note = 'runs until stopped; no exact repeat within the 12 s capture, show is the capture'
        elif evs: note = 'ends by itself after %d ms' % dur
        if body:
            used = sorted({k for _, x in body for k in x['lights']})
            show = 'lampfx_%03d' % i
            dump_show(os.path.join(sd, show + '.yaml'), ['ROM lamp effect (leff) %d, captured in the emulator (tools/emu/lfx.cpp). %s.' % (i, note),
                                                        'Colors: ffffff = on, 7f7f7f = second plane only (dim / blink phase), 000000 = off.'], to_steps(body, end))
            show_cfg.append((show, loop))
        why = '' if body else ('not created (refused or already running at higher priority)' if c and c['created'] is False else
                               'no lamps of its own in the capture (draws from game state, needs a parameter, or controls other outputs)' if c else 'not captured')
        rows.append(dict(leff=i, fn='0x%x' % e['fn'], flags='0x%04x' % e['flags'], lamp_group=e['group'], lamp_group_lamps=' '.join(map(str, lamp_group(e['group']))) if e['group'] else '',
                         coil_group=e['coil_group'], priority=e['prio'], capture=status or '', run_ms=dur if c else '', loops='yes' if loop else '',
                         show=show, steps=len(body), lamps_used=len({k for _, x in body for k in x['lights']}), coils_pulsed=' '.join(sorted({k for _, x in body for k in x['coils']})),
                         sounds=' '.join(sorted({s for _, s in (c or {}).get('sounds', [])})), deffs_started=' '.join(sorted({str(d) for _, d in (c or {}).get('deffs', [])})),
                         leffs_started=' '.join(sorted({str(x) for _, x in (c or {}).get('leffs', [])})), started_by_code=' | '.join(sorted(set(sites.get(i, [])))),
                         note=note or why, tag='observed' if body else 'code'))
    with open(os.path.join(data, 'io/lamp_effects.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    json.dump({str(g): lamp_group(g) for g in range(148)}, open(os.path.join(data, 'io/lamp_groups.json'), 'w'), indent=0)
    print(len(show_cfg), 'shows;', sum(1 for r in rows if r['capture']), 'captured of 178')

if __name__ == '__main__':
    main(*sys.argv[1:5])
