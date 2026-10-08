"""Set dmd_library frame_ms from the deff captures: median time between draws of consecutive images of one
animation by one deff. Usage: lib_timing.py DEFFS_DIR LIB_INDEX"""
import json, glob, sys, statistics, collections
ddir, idx = sys.argv[1:3]
lib = json.load(open(idx)); by = {}
for a in lib:
    for i in range(a['first_image'], a['last_image'] + 1): by[i] = a['name']
dt = collections.defaultdict(list); xs = collections.defaultdict(collections.Counter); who = collections.defaultdict(set)
for p in sorted(glob.glob(ddir + '/deff_*/timing.json')):
    d = json.load(open(p)); prev = None
    for pg in d['pages']:
        for x in pg['images']:
            i = x.get('img'); n = by.get(i)
            if n is None: continue
            xs[n][x['x']] += 1; who[n].add(d['deff'])
            if prev and prev[1] == n and i == prev[0] + 1: dt[n].append(x['t_ms'] - prev[2])
            prev = (i, n, x['t_ms'])
k = 0
for a in lib:
    n = a['name']
    if xs[n]:
        a['x_on_128'] = xs[n].most_common(1)[0][0] if a['w'] < 128 else 0
        a['x_tag'] = 'observed (deff captures)'; a['deffs'] = sorted(who[n])
    if len(dt[n]) >= 2:
        a['frame_ms'] = round(statistics.median(dt[n])); a['frame_ms_tag'] = 'observed (median of %d steps)' % len(dt[n]); k += 1
json.dump(lib, open(idx, 'w'), indent=1)
print(k, 'of', len(lib), 'animations timed;', sum(1 for a in lib if xs[a['name']]), 'seen drawn')
