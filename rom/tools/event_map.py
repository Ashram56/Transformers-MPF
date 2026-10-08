"""Build event_map.csv (one row per display effect, Tron column layout where it applies) from the deff table,
the deff captures (deff_export.py output) and the Ghidra decompile, and rename deff/leff functions in the
decompile after this ROM's own tables. Usage: event_map.py DEFFS_DIR DECOMP_IN DECOMP_OUT LIB_INDEX CSV_OUT"""
import sys, os, re, json, csv
import tables
from rom import u32, u16, u8

def slug(s):
    return re.sub(r'_+', '_', re.sub(r'[^a-z0-9]+', '_', s.lower())).strip('_')[:32]

NOISE = re.compile(r'^[\d,.%/ -]*$|^(CREDITS|FREE PLAY|PLAYER|BALL \d)')
def name_for(did, texts):
    good = [t for t in texts if not NOISE.match(t) and len(t) > 2]
    return 'deff_%03d' % did + ('_' + slug(good[0]) if good else '')

def funcs(c):
    """split the decompile into (addr, name, body) by its '// ==== ADDR NAME' headers"""
    parts = re.split(r'^// ==== ([0-9a-f]{8}) (\S+)\n', c, flags=re.M)
    return [(int(parts[i], 16), parts[i + 1], parts[i + 2]) for i in range(1, len(parts), 3)]

def lit(x):
    return int(x, 16) if x.startswith('0x') else int(x)

def main(ddir, din, dout, libidx, csvp):
    c = open(din).read(); F = funcs(c)
    deff_fn = {u32(tables.rec('deffs', i)): i for i in range(1, 156)}
    leff_fn = {u32(tables.rec('leffs', i)): i for i in range(1, 179)}
    lib = json.load(open(libidx))
    def anims(imgs):
        return sorted({a['name'] for a in lib for i in imgs if a['first_image'] <= i <= a['last_image']})
    cap = {}
    for i in range(156):
        p = os.path.join(ddir, 'deff_%03d' % i, 'timing.json')
        if os.path.exists(p): cap[i] = json.load(open(p))
    names = {}
    for i in range(156):
        texts = []
        for pg in cap.get(i, {}).get('pages', []):
            for t in pg['texts']:
                if t['str'] not in texts: texts.append(t['str'])
        names[i] = (name_for(i, texts), texts)
    started_by = {}; snd_in = {}; leff_in = {}
    for a, n, body in F:
        for m in re.finditer(r'\bdeff_start\((0x[0-9a-f]+|\d+),', body): started_by.setdefault(lit(m.group(1)), []).append(a)
        if a in deff_fn:
            d = deff_fn[a]
            snd_in[d] = sorted({lit(m.group(1)) for m in re.finditer(r'\bsnd_play\((0x[0-9a-f]+|\d+)\)', body)})
            leff_in[d] = sorted({lit(m.group(1)) for m in re.finditer(r'\bleff_start\((0x[0-9a-f]+|\d+)\)', body)})
    # rename: table functions get this ROM's ids; names carried over from Tron for other addresses are dropped
    ren = {}
    OS_NAMES = {0x215ac: 'text_draw_msg_page', 0x217b4: 'text_printf_msg_fit_page', 0x21838: 'text_draw_str_page',
                0x21a78: 'text_printf_page', 0x21b4c: 'text_draw_str_fit_page', 0x1caf0: 'score_add', 0x1cb0c: 'score_add_player',
                0x1aa40: 'current_player', 0x1a94c: 'num_players', 0x103aec0: 'multiball_start', 0x20be4: 'deff_stop',
                0x178b0: 'bg_entry_eval', 0x73cc: 'lamp_compositor_tick', 0x1033e30: 'player_side', 0x1033e84: 'side_choice_running',
                0x1006704: 'any_multiball_running', 0x10067bc: 'any_timed_mode_running'}
    for a, n, _ in F:
        if a in OS_NAMES and n != OS_NAMES[a]: ren[n] = OS_NAMES[a]
        if a in OS_NAMES: continue
        if a in deff_fn: ren[n] = names[deff_fn[a]][0]
        elif a in leff_fn: ren[n] = 'leff_%03d' % leff_fn[a]
        elif re.match(r'(deff|leff)_\d', n): ren[n] = 'FUN_%08x' % a
    ren = {k: v for k, v in ren.items() if k != v}
    if ren:
        rx = re.compile(r'\b(' + '|'.join(map(re.escape, sorted(ren, key=len, reverse=True))) + r')\b')
        c = rx.sub(lambda m: ren[m.group(1)], c)
    open(dout, 'w').write(c)
    cols = ['deff', 'name', 'priority', 'background_loop', 'flags', 'rom_text', 'animation_frames', 'run_ms', 'rendered_in_emulation',
            'sounds_heard', 'sounds_in_code', 'lamp_effects_heard', 'lamp_effects_in_code', 'images_drawn', 'library_animations',
            'started_by_code', 'rom_function', 'capture']
    with open(csvp, 'w', newline='') as f:
        w = csv.DictWriter(f, cols, lineterminator='\n'); w.writeheader()
        for i in range(1, 156):
            a = tables.rec('deffs', i); fl = u16(a + 4); k = cap.get(i)
            imgs = sorted({x['img'] for pg in (k or {}).get('pages', []) for x in pg['images'] if x.get('img') is not None})
            run = (k.get('ended_ms') if k.get('ended_ms') is not None else k.get('window_ms')) if k else ''
            w.writerow(dict(deff=i, name=names[i][0], priority=u8(a + 6), background_loop='yes' if fl & 1 else '', flags='0x%x' % fl,
                            rom_text=' / '.join(names[i][1][:10]), animation_frames=len(k['frames']) if k else 0, run_ms=run,
                            rendered_in_emulation='yes' if k and len(k['pages']) else 'no',
                            sounds_heard=' '.join('%s@%dms' % (s['call'], s['t_ms']) for s in (k or {}).get('sounds', [])[:12] if s.get('deff') == i),
                            sounds_in_code=' '.join('0x%03x' % s for s in snd_in.get(i, [])),
                            lamp_effects_heard=' '.join(str(l['leff']) for l in (k or {}).get('leffs', [])[:12]),
                            lamp_effects_in_code=' '.join(map(str, leff_in.get(i, []))),
                            images_drawn=' '.join(map(str, imgs[:60])), library_animations=' '.join(anims(imgs)),
                            started_by_code=' '.join('0x%x' % x for x in started_by.get(i, [])), rom_function='0x%x' % u32(a),
                            capture=k['capture'] if k else ''))
    print(len(ren), 'functions renamed;', sum(1 for i in range(1, 156) if i in started_by), 'deffs with a literal deff_start caller')

if __name__ == '__main__':
    main(*sys.argv[1:6])
