"""Static list of the text each display effect draws, read from the decompile: calls to the text helpers with
a literal message id (the ROM message, often a printf format) or a literal string. Covers the effect function
and the game-code functions it calls directly. Usage: deff_texts.py DECOMP OUT_CSV"""
import sys, re, csv
import tables
from rom import u32
HELP = {'text_printf_msg': 'msg', 'text_draw_msg_page': 'msg', 'text_printf_msg_fit_page': 'msg', 'text_draw_msg_fit': 'msg',
        'text_draw_str_page': 'str', 'text_printf_page': 'str', 'text_draw_str_fit_page': 'str'}
def main(dec, out):
    c = open(dec).read()
    parts = re.split(r'^// ==== ([0-9a-f]{8}) (\S+)\n', c, flags=re.M)
    F = {int(parts[i], 16): (parts[i + 1], parts[i + 2]) for i in range(1, len(parts), 3)}
    byname = {n: a for a, (n, _) in F.items()}
    rx = re.compile(r'\b(' + '|'.join(HELP) + r')\(([^,]+),[^,]+,([^,]+),([^,]+),([^,]+),([^,)]+)')
    rows = []
    for d in range(1, 156):
        fa = u32(tables.rec('deffs', d))
        if fa not in F: continue
        todo = [(fa, 0)]; seen = set()
        while todo:
            a, depth = todo.pop()
            if a in seen or a not in F: continue
            seen.add(a); n, body = F[a]
            for m in rx.finditer(body):
                h, arg, font, flags, x, y = [g.strip() for g in m.groups()]
                r = dict(deff=d, function='0x%x %s' % (a, n), helper=h, font=font, flags=flags, x=x, y=y, msg_id='', text='')
                if HELP[h] == 'msg':
                    if re.fullmatch(r'0x[0-9a-f]+|\d+', arg):
                        i = int(arg, 0); r['msg_id'] = i; r['text'] = (tables.msg(i) or '').replace('\n', '|')
                    else: r['msg_id'] = arg; r['text'] = '(message id computed at run time)'
                else:
                    sm = re.fullmatch(r'"(.*)"', arg); r['text'] = sm.group(1) if sm else '(%s)' % arg
                rows.append(r)
            if depth < 1:
                for m in re.finditer(r'\b(FUN_01[0-9a-f]{6})\(', body): todo.append((int(m.group(1)[4:], 16), depth + 1))
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    print(len(rows), 'text calls for', len({r['deff'] for r in rows}), 'deffs')
if __name__ == '__main__':
    main(*sys.argv[1:3])
