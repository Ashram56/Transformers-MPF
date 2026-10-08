"""Summarize coil_pulse events of tf_ref traces into coil_timing.csv and add mpf_* columns to coils.csv.
Usage: coil_timing.py COILS_CSV OUT_CSV trace.jsonl..."""
import sys, json, csv, statistics, collections
coils_csv, out = sys.argv[1:3]
ev = collections.defaultdict(lambda: collections.defaultdict(list))
for p in sys.argv[3:]:
    mk = None
    for l in open(p):
        e = json.loads(l)
        if e['ev'] == 'mark': mk = e['text']
        if e['ev'] == 'coil_pulse':
            ev[e['coil']]['ball_search' if mk == 'ball_search' else 'game'].append(e)
rows = list(csv.DictReader(open(coils_csv)))
def med(xs): return round(statistics.median(xs), 1) if xs else ''
T = []
for r in rows:
    c = int(r['coil']); g = ev[c]['game']; b = ev[c]['ball_search']
    held = [e for e in g if e['segments'] > 3 and e['hold_duty'] > 0]
    solid = [e for e in g if e['segments'] == 1]
    kind = r['flags_decoded']
    t = dict(coil=c, name=r['name'], game_pulses=len(g), game_pulse_ms=med([e['first_ms'] for e in solid]),
             ballsearch_pulses=len(b), ballsearch_on_ms=med([e['total_ms'] for e in b]),
             held_activations=len(held), hold_first_ms=med([e['first_ms'] for e in held]),
             hold_duty=round(statistics.median([e['hold_duty'] for e in held]), 3) if held else '', test_pulse_ms=r['test_pulse_ms'])
    # MPF: pulse = what the game fires; flippers pulse then hold at the measured duty
    if 'flipper' in kind and held: mp, mh, note = t['hold_first_ms'], t['hold_duty'], 'flipper: pulse then hold PWM 1 ms on / 12 ms (observed)'
    elif t['game_pulse_ms'] != '': mp, mh, note = round(t['game_pulse_ms']), '', 'observed in play'
    elif 'motor' in kind or t['ballsearch_on_ms'] and float(t['ballsearch_on_ms']) > 300: mp, mh, note = '', '', 'motor/gate: enabled for a time, not pulsed (ball search held it %s ms)' % t['ballsearch_on_ms']
    elif t['ballsearch_on_ms'] != '': mp, mh, note = round(t['ballsearch_on_ms']), '', 'observed in ball search only'
    else: mp, mh, note = r['test_pulse_ms'], '', 'not fired in traces; ROM coil test time'
    r.update(mpf_default_pulse_ms=mp, mpf_default_hold_power=mh, mpf_source=note)
    T.append(t)
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, list(T[0]), lineterminator='\n'); w.writeheader(); w.writerows(T)
with open(coils_csv, 'w', newline='') as f:
    w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
for t, r in zip(T, rows): print(t['coil'], t['name'][:24], t['game_pulse_ms'], t['ballsearch_on_ms'], t['hold_duty'], '->', r['mpf_default_pulse_ms'], r['mpf_default_hold_power'], r['mpf_source'][:40])
