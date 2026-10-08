import sys, json, difflib
sys.path.insert(0, 'tools')
from fmatch_c import load, norm
ref = load(sys.argv[1]); tgt = load(sys.argv[2]); api = json.load(open(sys.argv[3]))
tn = {a: norm(b) for a, (n, b) in tgt.items() if a < 0x34058}
for e in api:
    a = int(e['addr'], 16)
    if a not in ref: print('%-24s %6x  (not in ref C)' % (e['name'], a)); continue
    s = norm(ref[a][1]); sc = []
    for b, t in tn.items():
        if abs(len(t) - len(s)) > 0.5 * len(s) + 40: continue
        sm = difflib.SequenceMatcher(None, s, t, autojunk=False)
        if sm.quick_ratio() < 0.6: continue
        sc.append((sm.ratio(), b))
    sc.sort(reverse=True)
    print('%-24s %6x  len %5d  ' % (e['name'], a, len(s)) + '  '.join('%x:%.2f' % (b, r) for r, b in sc[:3]))
