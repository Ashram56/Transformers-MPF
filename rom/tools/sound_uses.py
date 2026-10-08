"""What each sound call is for. Joins the sound call table, the tf_ref traces (sound events with the scenario
mark they fell under), the deff captures (sounds a display effect plays) and the decompile (snd_play(literal)
call sites), plus the music table read in the emulator (bg_entry events).
Usage: sound_uses.py ROMDIR DEFFS_DIR OUT_CSV MUSIC_CSV trace.jsonl..."""
import sys, os, re, csv, json, glob, bisect, collections

ROLES = {  # identified from the traces and the music table; tag says how. Side = u8 at 0x02112107+player, 1 = Autobot (inferred: the default side plays the Decepticon calls and shows deff 41 DECEPTICON)
    0x042: ('coin inserted', 'observed: every coin'),
    0x043: ('credit added', 'observed: on the coin that completes a credit'),
    0x01a: ('music: choose your side, Autobot selected', 'code: music table entry 0x34cd4 (deff 40)'),
    0x01b: ('music: choose your side, Decepticon selected', 'code: music table entry 0x34cd4 (deff 40); observed at game start'),
    0x01c: ('music: ball start, Autobot', 'code: music table entry 0x34cd4 (deff 19)'),
    0x01d: ('music: ball start, Decepticon', 'code: music table entry 0x34cd4 (deff 19); observed at each ball start'),
    0x01e: ('music: main play, Autobot', 'code: music table fallback entry 0x34cec (deff 19)'),
    0x01f: ('music: main play, Decepticon', 'code: music table fallback entry 0x34cec; observed after the first award or ball save'),
    0x031: ('music: battle ready, Autobot', 'code: music table, replaces 0x1c/0x1e when the battle can progress'),
    0x034: ('music: battle ready, Decepticon', 'code: music table, replaces 0x1d/0x1f when the battle can progress'),
    0x020: ('music: end of ball bonus', 'observed in deff 25 (bonus)'),
    0x056: ('ball launched from the shooter lane', 'observed on every plunge and auto launch'),
    0x016: ('tilt warning sound', 'observed: tilt bob, warning'),
    0x052: ('tilt warning, second sound', 'observed: 0.5 s after 0x016'),
    0x017: ('tilt sound', 'observed: tilt'),
    0x053: ('tilt speech', 'observed: 1 s after 0x017'),
    0x169: ('ball saved sound', 'observed: drain under ball save'),
    0x05e: ('ball saved, first sound', 'observed in deff 20 (ball saved)'),
    0x05f: ('ball saved speech', 'observed in deff 20 (ball saved)'),
    0x16d: ('drain (ball lost)', 'observed: drain with no ball save'),
}

def main(romdir, ddir, out, music_out, *traces):
    calls = {int(r['call'], 16): r for r in csv.DictReader(open(os.path.join(romdir, 'rom_data/sound/sound_calls.csv')))}
    samples = {r['sample']: r for r in csv.DictReader(open(os.path.join(romdir, 'rom_data/sound/samples.csv')))}
    c = open(os.path.join(romdir, 'code/tf_decompiled.c')).read()
    hdr = [(int(m.group(1), 16), m.group(2), m.start()) for m in re.finditer(r'^// ==== ([0-9a-f]{8}) (\S+)', c, re.M)]
    starts = [h[0] for h in hdr]
    def fn_at(a):
        i = bisect.bisect_right(starts, a) - 1
        return '0x%x %s' % (hdr[i][0], hdr[i][1]) if i >= 0 else '0x%x' % a
    code = collections.defaultdict(set)
    for i, (a, n, pos) in enumerate(hdr):
        body = c[pos:hdr[i + 1][2] if i + 1 < len(hdr) else len(c)]
        for m in re.finditer(r'\bsnd_play\((0x[0-9a-f]+|\d+)\)', body):
            v = m.group(1); code[int(v, 16) if v.startswith('0x') else int(v)].add('0x%x %s' % (a, n))
    heard = collections.defaultdict(collections.Counter); callers = collections.defaultdict(set); in_deff = collections.defaultdict(set)
    music = {}
    for p in traces:
        mk = None
        for l in open(p):
            e = json.loads(l)
            if e['ev'] == 'mark': mk = e['text']
            elif e['ev'] == 'sound':
                k = int(e['call'], 16); heard[k][mk or 'unmarked'] += 1
                f = fn_at(int(e['caller'], 16))
                if 'snd_play' not in f and int(e['caller'], 16) != 0x2521c: callers[k].add(f)
                if e['in_deff']: in_deff[k].add(e['in_deff'])
            elif e['ev'] == 'bg_entry': music[e['rec']] = e
    for p in glob.glob(os.path.join(ddir, 'deff_*/timing.json')):
        d = json.load(open(p))
        for s in d['sounds']:
            if isinstance(s['call'], int) and s.get('deff') == d['deff']: in_deff[s['call']].add(d['deff'])
    cols = ['call', 'role', 'role_tag', 'kinds', 'samples', 'durations_s', 'heard_in_scenarios', 'in_deffs', 'code_call_sites', 'trace_callers']
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, cols, lineterminator='\n'); w.writeheader()
        for k in sorted(calls):
            r = calls[k]; sl = [s for s in r['samples'].split() if s]
            role, tag = ROLES.get(k, ('', ''))
            w.writerow(dict(call='0x%03x' % k, role=role, role_tag=tag, kinds=r['kinds'], samples=' '.join(sl),
                            durations_s=' '.join(samples.get(s, {}).get('duration_s', '') or '-' for s in sl),
                            heard_in_scenarios=' '.join('%s:%d' % kv for kv in heard[k].items()),
                            in_deffs=' '.join(map(str, sorted(in_deff[k]))), code_call_sites=' | '.join(sorted(code[k])),
                            trace_callers=' | '.join(sorted(callers[k]))))
    with open(music_out, 'w', newline='') as f:
        w = csv.DictWriter(f, ['priority', 'entry_ram', 'state_mask', 'condition_fn', 'deff', 'sound', 'chooser_fn', 'meaning'], lineterminator='\n'); w.writeheader()
        for i, e in enumerate(music.values()):
            w.writerow(dict(priority=i, entry_ram=e['rec'], state_mask=e['mask'], condition_fn=e['cond_fn'], deff=e['deff'], sound=e['sound'],
                            chooser_fn=e['adjust_fn'], meaning=MUSIC_NOTES.get(e['rec'], '')))
    print(sum(1 for k in calls if heard[k] or in_deff[k] or code[k]), 'of', len(calls), 'calls placed;', len(music), 'music entries')

MUSIC_NOTES = {
    '0x34cd4': 'no game flag 0x10 and nothing queued: deff 40 + 0x1a/0x1b while the side choice runs (task 200), else deff 19 + 0x1c/0x1d; 0x31/0x34 when the battle can progress',
    '0x34cec': 'fallback, always true: deff 19 + 0x1e (Autobot) / 0x1f (Decepticon); 0x31/0x34 when the battle can progress',
    '0x34bb4': 'task 0xc3 running: deff 130 + music 0x26',
}

if __name__ == '__main__':
    main(*sys.argv[1:])
