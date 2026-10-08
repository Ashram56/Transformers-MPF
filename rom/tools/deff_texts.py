"""Static list of the text each display effect draws, read from the decompile: calls to the text helpers with
a literal message id (the ROM message, often a printf format) or a literal string. Covers the effect function
and the game-code functions it calls directly or starts as a task (function pointer argument).

Extra columns:
  call_site     return address of the helper call (BL address + 4), the same value as `call_site` / `lr` in the
                effect captures (timing.json, tracer TXTSRC lines). Found by disassembling the function (capstone)
                and matching each BL to a helper with the decompiled call by (helper, message id) in order.
  args          for printf helpers, one entry per vararg (paired with the % conversions of the format), with the
                value's source as read at the call site: RAM address (+ name when known), a function call with
                its address (small getters inlined as `= expr`), a constant, or the deff task argument.
  args_observed distinct vararg values the printf helper received in emulator captures for this deff and call
                site (tracer TXTSRC ... args=), '|' between values, ';' between args.
  font_list     for a font operand that is a pointer (the *_fit helpers), the font ids (fonts.json index) of the
                0-terminated u32 list at that address, in the order text_draw_str_fit (0x21b90) tries them.

Usage: deff_texts.py DECOMP OUT_CSV [TRACER_LOG ...]"""
import sys, re, csv, glob
import tables
from rom import u32, foff, ROM, isstr, cstr

HELP = {'text_printf_msg': 'msg', 'text_draw_msg_page': 'msg', 'text_printf_msg_fit_page': 'msg', 'text_draw_msg_fit': 'msg',
        'text_draw_str_page': 'str', 'text_printf_page': 'str', 'text_draw_str_fit_page': 'str'}
HADDR = {'text_printf_msg': 0x21660, 'text_draw_msg_page': 0x215ac, 'text_printf_msg_fit_page': 0x217b4,
         'text_draw_msg_fit': 0x2174c, 'text_draw_str_page': 0x21838, 'text_printf_page': 0x21a78,
         'text_draw_str_fit_page': 0x21b4c}
NFIXED = {'text_printf_msg': 7, 'text_printf_msg_fit_page': 8, 'text_printf_page': 7}   # varargs follow these
RAM = {  # known RAM (address: name); [p] = indexed by player number
    0x32438: 'current player', 0x3243c: 'playfield multiplier', 0x21109e4: 'player score [p-1] (u32)',
    0x34b3c: 'bonus count [p-1] (u16)', 0x2111ce0: 'held bonus [p-1] (u32)', 0x2111cef: 'bonus multiplier [p] (u8)',
    0x2112107: 'side [p]', 0x353d4: 'pop burst total (sum of pop awards since the burst started)',
    0x353d0: 'last pop award', 0x2112044: 'pop value [p-1] (+1000 per pop, max 20000)',
    0x2112054: 'pop base value [p-1]',
}
LOCAL = re.compile(r'\b(?:[a-z]{1,2}Var\d+|[a-z]{1,2}Stack_\w+|local_\w+|param_\d+|arg(?:_\w+)?)\b')

def split_args(s, i):
    """Arguments of the call whose '(' ends just before s[i]; returns (args, index after ')')."""
    d = 0; a = []; cur = ''; q = None
    while i < len(s):
        ch = s[i]; i += 1
        if q:
            cur += ch
            if ch == '\\': cur += s[i]; i += 1
            elif ch == q: q = None
            continue
        if ch in '"\'': q = ch; cur += ch; continue
        if ch in '([': d += 1
        elif ch in ')]':
            if d == 0: a.append(cur.strip()); return a, i
            d -= 1
        elif ch == ',' and d == 0: a.append(cur.strip()); cur = ''; continue
        cur += ch
    return a, i

class Dec:
    def __init__(self, path):
        c = open(path).read()
        parts = re.split(r'^// ==== ([0-9a-f]{8}) (\S+)\n', c, flags=re.M)
        self.F = {int(parts[i], 16): (parts[i + 1], parts[i + 2]) for i in range(1, len(parts), 3)}
        self.byname = {n: a for a, (n, _) in self.F.items()}
        self.addrs = sorted(self.F)

    def fend(self, a):
        i = self.addrs.index(a)
        return self.addrs[i + 1] if i + 1 < len(self.addrs) else a + 0x400

    def getter(self, name):
        """Return expression of a small function (one return, few statements), else None."""
        a = self.byname.get(name)
        if a is None: return None
        body = self.F[a][1]
        b = body[body.find('{'):]
        st = [l.strip() for l in b.split('\n') if l.strip() and l.strip() not in '{}' and not re.match(
            r'^(?:uint|int|char|undefined\d?|bool|short|byte|ushort|void)\s*\**\s*\w+(\s*\[\d+\])?;$', l.strip())]
        rets = [l for l in st if l.startswith('return ')]
        if len(rets) != 1 or len(st) > 6 or any(k in b for k in ('while', 'if (', 'goto')): return None
        return a, body, body.find(rets[0]), rets[0][7:].rstrip(';').strip()

    def resolve(self, a, body, pos, expr, depth=0, callers=None, targs=None):
        """Replace locals in expr by their last assignment before pos (recursively) and inline small getters,
        in one pass so substituted text is not rewritten again. callers: [(addr, body, pos, args, callers)] of the
        calls into this function (resolves param_N); targs: {offset: text} task arguments set by the spawner."""
        if depth > 12: return expr
        def sub_local(v):
            if v.startswith('param_'):
                if callers:
                    k = int(v[6:]) - 1
                    vals = [self.resolve(pa, pbody, ppos, pargs[k], depth + 1, pcallers)
                            for (pa, pbody, ppos, pargs, pcallers) in callers if k < len(pargs)]
                    vals = list(dict.fromkeys(vals))
                    if vals: return '(' + ' | '.join(vals) + ')' if len(vals) > 1 else vals[0]
                return '%s of 0x%x' % (v, a)
            asg = [(m2.start(), m2.group(1).strip()) for m2 in re.finditer(
                r'(?:^|[\s(,])' + re.escape(v) + r' = ((?:[^;,()]|\([^()]*(?:\([^()]*\)[^()]*)*\))+)[;,)]', body, re.M)]
            self_mask = re.compile(r'^' + re.escape(v) + r' & 0x[0-9a-f]+$')
            asg = [x for x in asg if not self_mask.match(x[1])]            # v = v & 0xff: same value
            if not asg: return v
            before = [x for x in asg if x[0] < pos] or asg
            p0, rhs = before[-1]
            selfref = [r for (q, r) in asg if re.search(r'\b' + re.escape(v) + r'\b', r)]
            if selfref:   # loop counter / accumulator (stepped somewhere in the function)
                rhs = selfref[0]
                inits = [(q, r) for (q, r) in before if not re.search(r'\b' + re.escape(v) + r'\b', r)][-1:] or \
                        [(q, r) for (q, r) in asg if not re.search(r'\b' + re.escape(v) + r'\b', r)]
                init = ' / '.join(dict.fromkeys(self.resolve(a, body, q, r, depth + 1, callers, targs) for (q, r) in inits)) or '?'
                return '[loop counter: from %s, then %s]' % (init, re.sub(r'\b' + re.escape(v) + r'\b', 'self', rhs))
            r = self.resolve(a, body, p0, rhs, depth + 1, callers, targs)
            return '(' + r + ')' if re.search(r'[-+*/|&]', r) and not r.startswith(('(', '[')) else r
        def sub_call(name):
            g = self.getter(name); ca = self.byname.get(name)
            tag = '%s()@0x%x' % (name, ca) if ca is not None else name + '()'
            if name in ('current_player', 'num_players', 'player_side'): return name + '()'
            if g and depth < 10:
                ga, gbody, gpos, gexpr = g
                return '%s{= %s}' % (tag, self.resolve(ga, gbody, gpos, gexpr, depth + 1))
            return tag
        def sub_targ(m):
            off = int(m.group(1), 16)
            if targs and off in targs: return '{task arg +0x%x = %s}' % (off, targs[off])
            return m.group(0)
        def one(m):
            if m.group(1): return sub_call(m.group(1))
            if m.group(2): return sub_targ(re.match(r'.*\+ (0x[0-9a-f]+)\)', m.group(2)))
            return sub_local(m.group(0))
        return re.sub(r'\b(\w+)\(\)|(\*\(\w+ \*\)\(task_current \+ 0x[0-9a-f]+\))|' + LOCAL.pattern, one, expr)

def pretty(e):
    e = re.sub(r'\((?:uint|int|ushort|short|byte|char|undefined\d?)\)', '', e)
    e = re.sub(r'\*\((?:undefined\d|uint|int|ushort|short|byte|char) \*\)\(task_current \+ (0x[0-9a-f]+)\)',
               r'deff task arg (task+\1)', e)
    def ram(m):
        a = int(m.group(1), 16); n = RAM.get(a)
        return 'RAM 0x%x%s' % (a, ' ' + n if n else '')
    e = re.sub(r'&?DAT_([0-9a-f]{8})', ram, e)
    e = re.sub(r'\(current_player\(\)(?:@0x[0-9a-f]+)? & 0xff\)', 'current_player()', e)
    e = e.replace('current_player() & 0xff', 'current_player()')
    e = re.sub(r'\*\(\w+ \*\)\((RAM 0x[0-9a-f]+[^+]*?) \+ \(\(?current_player\(\)(?: & 0xff)?\)? - 1\) \* \d\)', r'\1{current_player()-1}', e)
    e = re.sub(r'\((RAM 0x[0-9a-f]+[^)]*\)?)\)\[current_player\(\)(?: & 0xff)?\]', r'\1{current_player()}', e)
    e = re.sub(r'\s+', ' ', e).strip()
    return e

# printf conversions; %P<n>/<forms>/% is the ROM's plural/ordinal form chooser and also takes one argument
CONV = re.compile(r'%P\d*/[^%]*%|%(?:%|[-+ #0,]*\d*(?:\.\d+)?(?:ll|l|h)?[a-zA-Z])')
def conversions(fmt):
    return [c[:2] if c.startswith('%P') else c for c in CONV.findall(fmt or '') if c != '%%']

def font_list(font):
    m = re.fullmatch(r'&?(?:DAT_)?(0x)?([0-9a-f]+)', font)
    if not m: return ''
    try: a = int(m.group(2), 16) if (m.group(1) or font.startswith(('&', 'DAT'))) else int(m.group(2))
    except ValueError: return ''
    if a < 0x1000 or foff(a) is None: return ''
    out = []
    for i in range(16):
        f = u32(a + 4 * i); out.append(f)
        if f == 0: break
    return ' '.join(map(str, out))

def call_sites(dec, a):
    """[(return address, helper name, r0 constant or None)] for BLs to text helpers in the function at a."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM); md.skipdata = True
    e = dec.fend(a); o = foff(a)
    if o is None: return []
    ins = list(md.disasm(ROM[o:o + (e - a)], a))
    inv = {v: k for k, v in HADDR.items()}
    out = []
    for k, i in enumerate(ins):
        if i.mnemonic != 'bl': continue
        try: t = int(i.op_str.lstrip('#'), 0)
        except ValueError: continue
        if t not in inv: continue
        r0 = None
        for j in ins[max(0, k - 16):k]:
            ops = [x.strip() for x in j.op_str.split(',')]
            if not ops or ops[0] != 'r0': continue
            mm = j.mnemonic
            try:
                if mm == 'mov' and ops[1].startswith('#'): r0 = int(ops[1][1:], 0)
                elif mm == 'mvn' and ops[1].startswith('#'): r0 = ~int(ops[1][1:], 0) & 0xffffffff
                elif mm == 'ldr' and ops[1] == '[pc' : r0 = u32(j.address + 8 + int(ops[2].strip('#]'), 0))
                elif mm in ('add', 'orr', 'sub') and ops[1] == 'r0' and ops[2].startswith('#') and r0 is not None:
                    v = int(ops[2][1:], 0); r0 = r0 + v if mm == 'add' else (r0 | v if mm == 'orr' else r0 - v)
                else: r0 = None
            except (ValueError, IndexError): r0 = None
        out.append((i.address + 4, inv[t], None if r0 is None else r0 & 0xffff))
    return out

def load_obs(logs):
    obs = {}
    rx = re.compile(r'TXTSRC fn=([0-9a-f]+) deff=(\d+) .*?lr=([0-9a-f]+) .*args=(\d+),(\d+),(\d+),(\d+)')
    for p in logs:
        for l in open(p, errors='replace'):
            m = rx.search(l)
            if m: obs.setdefault((int(m.group(2)), int(m.group(3), 16)), []).append(tuple(int(x) for x in m.groups()[3:]))
    return obs

def fmt_obs(vals, n, convs):
    out = []
    for k in range(n):
        vs = []
        for v in vals:
            x = v[k]; c = convs[k] if k < len(convs) else '%u'
            if c[-1] in 'di' and x >= 0x80000000: x -= 1 << 32
            s = ('0x%x' % x) if c[-1] in 'sxXp' else str(x)
            if s not in vs: vs.append(s)
        out.append('|'.join(vs[:8]) + ('|...' if len(vs) > 8 else ''))
    return ';'.join(out)

def main(dec_path, out, *logs):
    dec = Dec(dec_path); F = dec.F
    obs = load_obs([p for g in logs for p in sorted(glob.glob(g))])
    rows = []
    stats = [0, 0]
    # deff task arguments stored by direct starters: v = deff_start(N, ..); *(T *)(v + off) = expr;
    dargs = {}
    for fa_, (fn_, body_) in F.items():
        for sm in re.finditer(r'(\w+) = deff_start\((0x[0-9a-f]+|\d+),[^;()]*\)', body_):
            for am in re.finditer(r'\*\(\w+ \*\)\(' + sm.group(1) + r' \+ (0x[0-9a-f]+)\) = ([^;]+);', body_[sm.end():sm.end() + 400]):
                v = pretty(dec.resolve(fa_, body_, sm.end() + am.start(), am.group(2), 1))
                dargs.setdefault(int(sm.group(2), 0), {}).setdefault(int(am.group(1), 16), [])
                ent = '%s @0x%x' % (v, fa_)
                if ent not in dargs[int(sm.group(2), 0)][int(am.group(1), 16)]: dargs[int(sm.group(2), 0)][int(am.group(1), 16)].append(ent)
    for d in range(1, 156):
        fa = u32(tables.rec('deffs', d))
        if fa not in F: continue
        todo = [(fa, 0, None)]; seen = set(); callers = {}; targs = {}
        order = []
        while todo:
            a, depth, par = todo.pop()
            if par: callers.setdefault(a, []).append(par)
            if a in seen or a not in F: continue
            seen.add(a); order.append(a); n, body = F[a]
            if depth < 1:
                for m in re.finditer(r'\b(FUN_01[0-9a-f]{6})(\()?', body):
                    ca = int(m.group(1)[4:], 16)
                    if m.group(2):
                        args, _ = split_args(body, m.end())
                        todo.append((ca, depth + 1, (a, body, m.start(), args, None)))
                    else:
                        todo.append((ca, depth + 1, None))
                        # task started with this entry point: the starter stores its arguments at task+0x30..
                        for sm in re.finditer(r'(\w+) = \w+\([^;()]*?\b' + m.group(1) + r'\b[^;()]*\)', body):
                            for am in re.finditer(r'\*\(\w+ \*\)\(' + sm.group(1) + r' \+ (0x[0-9a-f]+)\) = ([^;]+);',
                                                  body[sm.end():sm.end() + 800]):
                                v = pretty(dec.resolve(a, body, sm.end() + am.start(), am.group(2), 1))
                                targs.setdefault(ca, {}).setdefault(int(am.group(1), 16), [])
                                if v not in targs[ca][int(am.group(1), 16)]: targs[ca][int(am.group(1), 16)].append(v)
        for a in order:
            n, body = F[a]
            sites = call_sites(dec, a); used = [False] * len(sites)
            for m in re.finditer(r'\b(' + '|'.join(HELP) + r')\(', body):
                h = m.group(1)
                args, _ = split_args(body, m.end())
                if len(args) < 6: continue
                arg, font, flags, x, y = args[0], args[2], args[3], args[4], args[5]
                r = dict(deff=d, function='0x%x %s' % (a, n), helper=h, font=font, flags=flags, x=x, y=y, msg_id='', text='',
                         call_site='', args='', args_observed='', font_list=font_list(font))
                lit = None
                if HELP[h] == 'msg':
                    if re.fullmatch(r'0x[0-9a-f]+|\d+', arg):
                        lit = int(arg, 0); r['msg_id'] = lit; r['text'] = (tables.msg(lit) or '').replace('\n', '|')
                    else: r['msg_id'] = arg; r['text'] = '(message id computed at run time)'
                else:
                    sm = re.fullmatch(r'"(.*)"', arg); r['text'] = sm.group(1) if sm else '(%s)' % arg
                    pm = re.fullmatch(r'&DAT_([0-9a-f]{8})', arg)
                    if pm and isstr(int(pm.group(1), 16)): r['text'] = cstr(int(pm.group(1), 16)).replace('\n', '|')
                # call site: first unused BL to this helper with the same r0 constant, else first unused BL to it
                k = next((i for i, s in enumerate(sites) if not used[i] and s[1] == h and lit is not None and s[2] == lit), None)
                if k is None:
                    k = next((i for i, s in enumerate(sites) if not used[i] and s[1] == h and (lit is None or s[2] is None)), None)
                if k is not None: used[k] = True; r['call_site'] = '%x' % sites[k][0]
                if h in NFIXED:
                    va = args[NFIXED[h]:]
                    convs = conversions(r['text'])
                    pa = callers.get(a)
                    pcs = [(p[0], p[1], p[2], p[3], None) for p in pa if p] if pa else None
                    ta = {o: ' | '.join(v) for o, v in targs.get(a, {}).items()}
                    res = [pretty(dec.resolve(a, body, m.start(), e, 0, pcs, ta)) for e in va]
                    def starter(mm):
                        st = dargs.get(d, {}).get(int(mm.group(1), 16))
                        return mm.group(0) + (' {set by starter: %s}' % ' | '.join(st) if st else '')
                    res = [re.sub(r'deff task arg \(task\+(0x[0-9a-f]+)\)', starter, x) for x in res]
                    ent = []
                    for i, s in enumerate(res):
                        c = convs[i] if i < len(convs) else '?'
                        ent.append('%s %s' % (c, s))
                        stats[1 if LOCAL.search(re.sub(r'task arg', '', s)) else 0] += 1
                    r['args'] = '; '.join(ent)
                    if r['call_site']:
                        vals = obs.get((d, int(r['call_site'], 16)))
                        if vals: r['args_observed'] = fmt_obs(vals, len(va), convs)
                rows.append(r)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    print(len(rows), 'text calls for', len({r['deff'] for r in rows}), 'deffs;', stats[0], 'printf args resolved,',
          stats[1], 'with an unresolved local;', sum(1 for r in rows if r['args_observed']), 'rows with observed values')
if __name__ == '__main__':
    main(*sys.argv[1:])
