"""Match functions between two Ghidra pseudo-C exports by normalized body text.
Usage: python3 fmatch_c.py REF.c TARGET.c OUT.tsv   (REF names are carried to TARGET)"""
import re, sys, collections, difflib
def load(p):
    fs = {}; cur = None; buf = []
    for l in open(p, errors='replace'):
        m = re.match(r'// ==== ([0-9a-f]{8}) (\S+)', l)
        if m:
            if cur: fs[cur[0]] = (cur[1], ''.join(buf))
            cur = (int(m.group(1), 16), m.group(2)); buf = []
        else: buf.append(l)
    if cur: fs[cur[0]] = (cur[1], ''.join(buf))
    return fs
def norm(body):
    s = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'\b(FUN|DAT|PTR_DAT|PTR_FUN|LAB|switchD|caseD|code|uRam|iRam|puRam|piRam|pcRam|cRam|bRam|sRam|usRam|pbRam|ppuRam|ram|PTR|UNK|s)_[0-9a-fA-F_]+\w*', 'X', s)
    s = re.sub(r'\b[A-Za-z_]\w*(?=\s*\()', lambda m: m.group(0) if m.group(0) in ('if','while','for','switch','return','sizeof') else 'F', s)
    s = re.sub(r'0x[0-9a-fA-F]+', 'N', s); s = re.sub(r'\b\d+\b', 'N', s)
    s = re.sub(r'\b(local|uVar|iVar|pcVar|puVar|piVar|bVar|cVar|sVar|uStack|iStack|auStack|in_|unaff_|extraout_|param_|pbVar|psVar|ppuVar|pvVar|lVar|uVar|ushort|undefined\d?|uint|int|char|byte|short|bool|code|void)\w*', 'V', s)
    s = re.sub(r'\s+', ' ', s)
    head = s.find('{')
    return s[head:] if head >= 0 else s
if __name__ == '__main__':
    ref, tgt = load(sys.argv[1]), load(sys.argv[2])
    rn = {a: (n, norm(b)) for a, (n, b) in ref.items() if not n.startswith('FUN_')}
    tn = {a: norm(b) for a, (n, b) in tgt.items()}
    byt = collections.defaultdict(list)
    for a, s in tn.items(): byt[s].append(a)
    out = []; used = set()
    for a, (n, s) in rn.items():
        if len(s) < 60: continue
        c = byt.get(s, [])
        if len(c) == 1: out.append((c[0], n, a, 1.0, 'exact')); used.add(c[0])
    done = {x[2] for x in out}
    tl = [(a, s) for a, s in tn.items() if a not in used]
    for a, (n, s) in rn.items():
        if a in done or len(s) < 80: continue
        best = (0, None)
        for b, t in tl:
            if abs(len(t) - len(s)) > 0.3 * len(s): continue
            r = difflib.SequenceMatcher(None, s, t, autojunk=False).quick_ratio()
            if r < best[0] or r < 0.85: continue
            r = difflib.SequenceMatcher(None, s, t, autojunk=False).ratio()
            if r > best[0]: best = (r, b)
        if best[1] is not None and best[0] >= 0.85: out.append((best[1], n, a, round(best[0], 3), 'fuzzy'))
    with open(sys.argv[3], 'w') as f:
        f.write('target\tname\tref\tscore\thow\n')
        for t, n, a, sc, how in sorted(out): f.write('%x\t%s\t%x\t%s\t%s\n' % (t, n, a, sc, how))
    print('ref named', len(rn), 'matched', len(out), 'exact', sum(1 for x in out if x[4] == 'exact'))
