"""Turn tracer captures (caps/*.log + caps/*.dmd) into one folder per display effect (deff).
Usage: deff_export.py CAPS_DIR OUT_DIR CSV_OUT
Per deff: frames/NNNN.png (grey, level*17), reference_capture.gif and _x4.gif (orange), timing.json.
timing.json: frames (t_ms from the force, dur_ms), pages (one per dmd_show_pages call by the deff, with the image
draws and text draws composed into it), sounds, leffs, events, all with t_ms relative to the force."""
import sys, os, re, json, glob, csv, struct
import numpy as np
from PIL import Image
import dmdview, tables
from rom import u32, u16, u8

KV = re.compile(r'(\w+)=("([^"]*)"|\S+)')
def parse(line):
    p = line.split(' ', 2)
    t, kind = float(p[0]), p[1]
    rest = p[2] if len(p) > 2 else ''
    d = {}
    for m in KV.finditer(rest):
        v = m.group(3) if m.group(3) is not None else m.group(2)
        d[m.group(1)] = v if m.group(3) is not None else (int(v) if re.fullmatch(r'-?\d+', v) else v)
    if kind in ('FORCE', 'EVENT', 'AUDIT') or kind == 'FORCE_END':
        d['id'] = int(rest.split()[0])
    if kind in ('DRAW', 'TEXT'):
        d['fn_addr'] = rest.split()[0]
    return t, kind, d

def deff_table():
    out = {}
    for i in range(156):
        a = tables.rec('deffs', i); out[i] = dict(fn=u32(a), flags=u16(a + 4), prio=u8(a + 6))
    return out

PAL = np.array([[int(255 * k / 15), int(88 * k / 15), int(32 * k / 15)] for k in range(16)], np.uint8)
def orange(a, scale):
    im = Image.fromarray(PAL[np.clip(a, 0, 15)])
    return im.resize((128 * scale, 32 * scale), Image.NEAREST) if scale > 1 else im

def export(caps, outdir):
    best = {}
    for log in sorted(glob.glob(os.path.join(caps, '*.log'))):
        name = os.path.basename(log)[:-4]
        ev = [parse(l.rstrip('\n')) for l in open(log) if l[:1].isdigit()]
        frames = dmdview.load(log[:-4] + '.dmd')
        wins = []; cur = None
        for t, k, d in ev:
            if k == 'FORCE': cur = (d['id'], t)
            elif k == 'FORCE_END' and cur: wins.append((cur[0], cur[1], t, d.get('active'))); cur = None
        if cur: wins.append((cur[0], cur[1], ev[-1][0], cur[0]))  # background deffs run until the capture stops
        for did, t0, t1, active_end in wins:
            w = [(t, k, d) for t, k, d in ev if t0 <= t <= t1]
            mine = [x for x in w if x[2].get('deff') == did]
            shows = [x for x in mine if x[1] == 'SHOW']
            ended = (shows[-1][0] if shows else t0) if active_end != did else None
            tend = ended if ended is not None else t1
            fr = [(t, a) for t, a in frames if t0 <= t <= tend + 0.02]
            score = (len(shows), len(fr))
            if did not in best or score > best[did][0]:
                best[did] = (score, dict(cap=name, t0=t0, t1=t1, ended=ended, w=w, mine=mine, fr=fr))
    tab = deff_table(); rows = []
    for did in sorted(best):
        b = best[did][1]; t0 = b['t0']; ms = lambda t: round((t - t0) * 1000, 1)
        d = os.path.join(outdir, 'deff_%03d' % did); os.makedirs(os.path.join(d, 'frames'), exist_ok=True)
        fr = b['fr']; durs = []
        for i, (t, a) in enumerate(fr):
            nxt = fr[i + 1][0] if i + 1 < len(fr) else max(t + 0.05, (b['ended'] or b['t1']))
            durs.append(max(10, round((nxt - t) * 1000)))
            Image.fromarray((np.clip(a, 0, 15) * 17).astype(np.uint8)).save(os.path.join(d, 'frames', '%04d.png' % i))
        if fr:
            for sc, fn in ((1, 'reference_capture.gif'), (4, 'reference_capture_x4.gif')):
                ims = [orange(a, sc) for _, a in fr]
                ims[0].save(os.path.join(d, fn), save_all=True, append_images=ims[1:], duration=durs, loop=0, optimize=False)
        pages = []; pend_img = []; pend_txt = []
        for t, k, e in b['mine']:
            if k == 'IMG': pend_img.append(dict(t_ms=ms(t), img=e.get('img'), page=e.get('page'), x=e.get('x'), y=e.get('y'), fn=e.get('fn'), lr=e.get('lr')))
            elif k == 'TEXT': pend_txt.append(dict(t_ms=ms(t), str=e.get('str'), font=e.get('font'), flags=e.get('flags'), x=e.get('x'), y=e.get('y'), color=e.get('color'), width=e.get('w'), page=e.get('page'), lr=e.get('lr')))
            elif k == 'SHOW':
                pages.append(dict(t_ms=ms(t), fg=e.get('fg'), bg=e.get('bg'), images=pend_img, texts=pend_txt)); pend_img = []; pend_txt = []
        # blits (DRAW lines) are left out: every one comes from text_draw (glyphs, lr 0x219e0/0x21a10) or
        # bitmap_draw (lr 0x23d0c/0x23dc0), which are already listed as texts and images
        snd = [dict(t_ms=ms(t), call=e.get('call'), via=k, deff=e.get('deff'), lr=e.get('lr')) for t, k, e in b['w'] if k in ('SNDPLAY',)]
        lef = [dict(t_ms=ms(t), leff=e.get('id'), lr=e.get('lr')) for t, k, e in b['w'] if k == 'LEFF']
        evs = [dict(t_ms=ms(t), event=e['id']) for t, k, e in b['w'] if k == 'EVENT']
        T = tab.get(did, {})
        meta = dict(deff=did, fn='0x%x' % T.get('fn', 0), flags=T.get('flags'), priority=T.get('prio'),
                    background=bool(T.get('flags', 0) & 1), capture=b['cap'], forced_at_s=round(t0, 4),
                    ended_ms=ms(b['ended']) if b['ended'] is not None else None, window_ms=ms(b['t1']),
                    note='frames are emulator DMD output (only changed frames recorded); the left 41 columns may '
                         'show the status panel drawn by deff 40 (background) rather than this effect',
                    frames=[dict(i=i, t_ms=ms(t), dur_ms=durs[i]) for i, (t, _) in enumerate(fr)],
                    pages=pages, sounds=snd, leffs=lef, events=evs)
        json.dump(meta, open(os.path.join(d, 'timing.json'), 'w'), indent=1)
        imgs = sorted({x['img'] for p in pages for x in p['images'] if x.get('img') is not None})
        texts = sorted({x['str'] for p in pages for x in p['texts']})
        rows.append(dict(deff=did, fn=meta['fn'], flags='0x%x' % (T.get('flags') or 0), priority=T.get('prio'), background=int(meta['background']),
                         capture=b['cap'], frames=len(fr), pages=len(pages), ended_ms=meta['ended_ms'], sounds=' '.join(str(s['call']) for s in snd),
                         images=' '.join(map(str, imgs[:40])), texts=' | '.join(texts[:12])))
    return rows, tab

if __name__ == '__main__':
    caps, outdir, csvp = sys.argv[1:4]
    rows, tab = export(caps, outdir)
    seen = {r['deff'] for r in rows}
    for i in range(156):
        if i not in seen:
            T = tab[i]; rows.append(dict(deff=i, fn='0x%x' % T['fn'], flags='0x%x' % T['flags'], priority=T['prio'], background=int(bool(T['flags'] & 1)), capture='', frames=0, pages=0))
    rows.sort(key=lambda r: r['deff'])
    cols = ['deff', 'fn', 'flags', 'priority', 'background', 'capture', 'frames', 'pages', 'ended_ms', 'sounds', 'images', 'texts']
    with open(csvp, 'w', newline='') as f:
        w = csv.DictWriter(f, cols, lineterminator='\n'); w.writeheader(); [w.writerow(r) for r in rows]
    print(len(seen), 'deffs exported;', sum(1 for r in rows if r.get('pages', 0) > 1), 'with >1 page')
