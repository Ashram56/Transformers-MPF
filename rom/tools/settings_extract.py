"""Build rom_data/settings/* (pricing, audits, adjustments, presets, service texts, runtime menus) and the
MPF package service files (mpf_package/service_menu.json, service_menu.md, config/settings.yaml) from the
Stern Transformers Pro 1.80 ROM (tf_180). Port of Tron's rom_data/tools/settings_extract.py.

Inputs:  the ROM (rom.py; set TF_ROM to the image), code/tf_decompiled.c (function names, text calls),
         rom_data/settings/emu/t*.log (runs of tools/settings_emu.cpp, for `observed` facts).
Run:     TF_ROM=/path/tf_180.bin python3 tools/settings_extract.py            (writes the outputs)
         TF_ROM=/path/tf_180.bin python3 tools/settings_extract.py --scripts  (writes emu/t1..t5.txt)
Every fact carries `tag` = code (read from tables/disassembly), observed (seen in the emulator logs) or inferred.
"""
import bisect, collections, csv, json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rom import ROM, foff, u8, u16, u32, s32, cstr, disasm, bl_callers, func_start  # noqa: E402
from tables import msg  # noqa: E402

BASE = os.path.dirname(HERE)                       # rom/
OUT = os.path.join(BASE, 'rom_data', 'settings')
EMU = os.path.join(OUT, 'emu')
PKG = os.path.join(BASE, 'mpf_package')
DECOMP = os.path.join(BASE, 'code', 'tf_decompiled.c')


def hx(v):
    return '0x%x' % v


# ---------------------------------------------------------------- OS / table addresses (code)
# table-of-tables at 0x30b00 (RAM copy of the ROM; triples {addr, count, size})
ADJ_TAB, ADJ_N = 0x040cb20c, 98           # 32 B; count 99 incl. entry 0 (0x30b0c)
ADJ_FMT = 0x040ca7a4                      # 8 B {fn, u16 msg list ptr}; 36 entries (0x30b00)
CNT_TAB = 0x040cbe6c                      # 12 B counters {nvram rec ptr, ?, flags}; 159 entries (0x30b18)
AUD_FMT = 0x040cc5e0                      # 7 display-type formatters (0x30b24)
AUD_TAB, AUD_N = 0x040cd5a4, 166          # 16 B; 167 entries incl. 0 (0x30b30)
CREDSYS_TAB = 0x040ce024                  # 2 x 0x28 (0x30b3c); credit system #1 = +0x28
CREDSYS = CREDSYS_TAB + 0x28
PRICE_PTRS, NPRESET = 0x32324, 68         # RAM u32[69] pricing record pointers, index = adj 28 value (68 = CUSTOM)
COUNTRY_TAB, NCOUNTRY = 0x040ceca4, 29    # 32 B (0x30b60)
ITEMS, NITEMS = 0x040e3c40, 131           # 20 B menu items (0x30cf8)
MENUS, NMENUS = 0x040e4794, 18            # 12 B menus (0x30d04)
STD_ORDER = 0x338ac                       # u16 list: STANDARD ADJUSTMENTS order (0x10464bc -> 0x1045c08)
FEAT_ADJ = (65, 98)                       # FEATURE ADJUSTMENTS: 0x1005d18 -> 0x1045c08(0, 0x41, 0x62)
EARN_LIST, STDAUD_LIST = 0x3392e, 0x3394a  # EARNINGS / STANDARD AUDITS (0x1046508 / 0x1046990 -> 0x1046598)
FEAT_AUD = (73, 166)                      # FEATURE AUDITS: 0x1005ce4 -> 0x1046598(0, 0x49, 0xa6)
OVR_LIST = 0x33790                        # override list between country game list and country OS list (empty)
F = dict(adj_get=0x340, adj_default=0x3d8, adj_set=0x43c, adj_reset=0x530, adj_apply_list=0x598,
         adj_list_installed=0x5c8, adj_factory_all=0x728, country_override=0x53dc, adj_visible=0x2be10,
         counter_get=0xafc, audit_add=0xc3c, audit_value=0x1074, msg_get=0x99f0, msglist_fmt=0x76c,
         adj_menu=0x1045c08, audit_menu=0x1046598, install_screen=0x1049910, menu_build=0xeb3c)
ACT = {0x10459d8: 'submenu', 0x1045a78: 'back', 0x1045ac0: 'exit', 0x1045a74: 'help'}
MENU_NAMES = {1: 'MAIN MENU', 2: 'DIAGNOSTICS', 3: 'SWITCH MENU', 4: 'COIL MENU', 5: 'LAMP MENU', 6: 'FLASH LAMPS MENU',
              7: 'DR. PINBALL', 8: 'AUDITS', 9: 'ADJUSTMENTS', 10: 'UTILITIES', 11: 'INSTALLS', 12: 'RESETS', 13: 'SERIAL',
              14: 'USB', 15: 'TOURNAMENT', 16: 'REDEMPTION', 17: 'GAME-SPECIFIC TESTS'}
SHOWN_IF = {14: '0x2b270: game flag 7 set and 0x4fb8() != 0 (software errors were logged)',
            37: '0x2b29c: RAM 0x31316 != 0', 98: '0x10088ac: the game function always returns 1, so always shown',
            99: '0x283c8: 0x54a0() != 0 (tournament support, valid country record)',
            110: '0x28480: tournament type not 3/4 (no tournament running)', 111: '0x28464: tournament type 3 or 4 (running)',
            112: '0x2843c: tournament record +0x31 != 0 (data exists)',
            117: '0x2840c: 0x1b348() == 0 (no redemption system installed)', 118: '0x283f4: 0x1b348() != 0 (installed)',
            119: '0x28424: 0x1b348() != 0 (installed)', 120: '0x283dc: 0x1b348() != 0 (installed)'}


def msglist(a):
    out = []
    while u16(a):
        out.append(u16(a)); a += 2
    return out


def namep(p):
    try:
        return cstr(u32(p))
    except Exception:
        return None


def wcsv(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in cols})
    print('wrote', name, len(rows))


def plist(a):
    out = []
    while a and foff(a) is not None and u32(a) & 0xffff:
        out.append((u32(a) & 0xffff, s32(a + 4))); a += 8
    return out


# ---------------------------------------------------------------- decompile index
SRC = open(DECOMP).read().split('\n') if os.path.exists(DECOMP) else []
HEADS = []
for _i, _l in enumerate(SRC):
    _m = re.match(r'// ==== ([0-9a-f]{8}) (\S+)', _l)
    if _m:
        HEADS.append((_i, int(_m.group(1), 16), _m.group(2)))
H_NAME = {a: n for _, a, n in HEADS}
H_LINE = {a: i for i, a, _ in HEADS}
H_BYNAME = {n: a for _, a, n in HEADS}
_lines = [i for i, _, _ in HEADS]


H_START = sorted(H_NAME)


def func_of(a):
    """Function start: the nearest decompile header, or the nearest push {.., lr} when that is closer (the
    decompile lacks functions that are only reached through tables)."""
    k = bisect.bisect_right(H_START, a) - 1
    h = H_START[k] if k >= 0 else None
    f = func_start(a)
    if f is None or (h is not None and h <= f <= h + 0x10):
        return h if h is not None else a
    return max(f, h) if h is not None else f


def body(fa):
    i = H_LINE[fa]
    k = bisect.bisect_right(_lines, i)
    return SRC[i:_lines[k] if k < len(_lines) else len(SRC)]


def fname(a):
    return H_NAME.get(a, 'FUN_%08x' % a)


def emu_lines(name):
    p = os.path.join(EMU, name)
    return open(p).read().split('\n') if os.path.exists(p) else []


def r0_const(site):
    """Constant in r0 before a BL (None when computed)."""
    ins = [i for i in disasm(site - 64, size=64) if i.address < site]
    add = 0
    for i in reversed(ins):
        ops, mn = i.op_str, i.mnemonic
        if not ops.startswith('r0,'):
            continue
        if mn == 'mov' and '#' in ops:
            return int(ops.split('#')[1], 0) + add
        if mn == 'add' and ops.startswith('r0, r0, #'):
            add += int(ops.split('#')[1], 0); continue
        if mn == 'ldr' and '[pc, #' in ops:
            return u32(i.address + 8 + int(ops.split('#')[1].rstrip(']'), 0)) + add
        return None
    return None


def callers(target):
    return [(s, bool(u32(s) & (1 << 24))) for s in bl_callers(target)]


# ================================================================ adjustments
def adj_record(i):
    a = ADJ_TAB + 32 * i
    nv, d, mn, mx, step, f14, np_, ty = struct.unpack_from('<IiiiiIIi', ROM, foff(a))
    return dict(id=i, rec=a, nvram=nv, default=d, min=mn, max=mx, step=step, f14=f14, name=namep(np_),
                display_type=ty & 0xffff, nowrap=(ty >> 16) & 1)


def fmt_of(r):
    return struct.unpack_from('<II', ROM, foff(ADJ_FMT + 8 * r['display_type']))


def sample_values(r):
    n = (r['max'] - r['min']) // r['step'] + 1
    if n <= 1100:
        return [r['min'] + k * r['step'] for k in range(n)]
    ks = set(range(26)) | set(range(0, n, max(1, n // 80))) | {n - 3, n - 2, n - 1}
    return sorted(set([r['min'] + k * r['step'] for k in ks] + [r['default']]))


def formatter_labels():
    fnout = collections.defaultdict(dict)
    for l in emu_lines('t5.log'):
        m = re.match(r'[\d.]+ fmt 0x([0-9a-f]+) (-?\d+) = -?\d+ "(.*)"$', l)
        if m:
            fnout[int(m.group(1), 16)][int(m.group(2))] = m.group(3).replace('|', '\n')
    out = {}
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        fn, arg = fmt_of(r)
        vals = list(range(r['min'], r['max'] + 1, r['step']))
        labels, tag = {}, 'code'
        if fn == 0 and arg:
            lst = msglist(arg)
            for v in vals:
                labels[v] = msg(lst[v]) if 0 <= v < len(lst) else str(v)
            src = 'msg list %s (%s), drawn by 0x76c' % (hx(arg), ','.join(hx(x) for x in lst))
        else:
            got = fnout.get(fn, {})
            for v in vals:
                if v in got:
                    labels[v] = got[v]
            tag = 'observed' if got else 'missing'
            src = 'formatter fn %s run in the emulator (emu/t5.log)%s' % (
                hx(fn), '' if len(labels) == len(vals) else '; %d of %d values sampled' % (len(labels), len(vals)))
        out[i] = dict(fn=fn, arg=arg, labels=labels, src=src, tag=tag)
    return out


def countries():
    rows = []
    for c in range(NCOUNTRY):
        a = COUNTRY_TAB + 32 * c
        w = struct.unpack_from('<IIIIIHHHHI', ROM, foff(a))
        cec = []
        q = w[3]
        while q and u32(q) and len(cec) < 16:
            cec.append(cstr(u32(q))); q += 4
        rows.append(dict(code=c, rec=a, name=msg(w[5]), name_msg=w[5], os_list=w[1], game_list=w[2], cec_list=w[3],
                         redemption_defaults=w[4], msgs=(w[6], w[7], w[8]), os=plist(w[1]), game=plist(w[2]), cec_msgs=cec))
    return rows


# visibility rules of adj_visible 0x2be10 (jump table at 0x2be2c, ids 12..61; all others always visible)
VISIBLE = {12: 'REPLAY TYPE (11) is DYNAMIC or AUTO', 13: 'REPLAY TYPE (11) is FIXED or AUTO (case 13 falls through into case 14 at 0x2bf28)',
           14: 'REPLAY TYPE (11) is FIXED or AUTO', 15: 'REPLAY TYPE (11) is AUTO', 16: 'REPLAY TYPE (11) is DYNAMIC',
           17: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 1', 18: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 2',
           19: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 3', 20: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 4',
           21: 'REPLAY TYPE (11) is FIXED or AUTO', 23: 'SPECIAL LIMIT (22) != 0', 24: 'SPECIAL LIMIT (22) != 0',
           27: 'EXTRA BALL LIMIT (26) != 0', 29: 'MATCH PERCENTAGE (30) != OFF (11)'}
for _k in range(49, 62):
    VISIBLE[_k] = 'ALLOW HIGH SCORES (48) != 0'

# adj_get sites whose id comes from a data structure (code; ids marked observed were seen in emu/t2.log or t6)
STRUCT_SITES = {
    0x3d78: ([33], 'credits_add 0x3d40: credit system +0x1e = adj 33; caps credits at CREDIT LIMIT'),
    0x3e5c: ([28], 'pricing_current 0x3e3c: credit system +0x18 = adj 28; selects the pricing record'),
    0x3f68: ([62], 'coin task 0x3f00: credit system +0x1a = adj 62; wait N ticks re-checking the lockout, 61 = OFF'),
    0x448c: ([34], 'free_play 0x4464: credit system +0x1c = adj 34'),
    0x9ba8: ([44], 'meter_add 0x9b54: meter table 0x40cf768 +0 = adj 44; meter 1 counts only when Q24 OPTION = COIN METER (0)'),
    0x17134: ([85], 'device disable predicate 0x17120 (struct +0x1a); observed id 85 DISABLE OPTIMUS PRIME MOTOR'),
    0x18788: ([49, 50, 51, 52, 53, 90, 93], 'HS entry save 0x18730: HS table 0x40cf948 +0x1a, stored with the entry as its reset score'),
    0x18c54: ([55, 56, 57, 58, 59, 92, 95], 'HS award 0x18c04: HS table +0x1e = number of awards for that place'),
    0x18c64: ([54, 91, 94], 'HS award 0x18c04: HS table +0x1c = award type (0 credit, 1 ticket)'),
    0x1c13c: ([17, 18, 19, 20], 'replay score 0x1c07c (FIXED): adj 16+level = REPLAY LEVEL #n'),
    0x102c0e0: ([84], 'device predicate 0x102c0cc (struct +2); observed id 84 DISABLE ORBIT CONTROL GATE'),
}


def adj_get_observed():
    obs = collections.Counter()
    for l in emu_lines('t2.log'):
        m = re.search(r'adj_get id=(\d+) lr=0x([0-9a-f]+)', l)
        if m:
            obs[(int(m.group(1)), int(m.group(2), 16) - 4)] += 1
    for l in emu_lines('t6_adj_get_counts.txt'):
        m = re.match(r'\s*(\d+) adj_get id=(\d+) lr=0x([0-9a-f]+)', l)
        if m:
            obs[(int(m.group(2)), int(m.group(3), 16) - 4)] += int(m.group(1))
    return obs


def adj_readers():
    obs = adj_get_observed()
    rd = collections.defaultdict(list)
    for site, isbl in callers(F['adj_get']):
        fa = func_of(site)
        c = r0_const(site)
        ids = [c] if c is not None and 1 <= c <= ADJ_N else STRUCT_SITES.get(site, ([], ''))[0]
        for i in ids:
            rd[i].append('%s %s%s' % (hx(site), fname(fa), ' (observed)' if obs.get((i, site)) else ''))
    return rd


# ================================================================ pricing
def preset(i):
    p = u32(PRICE_PTRS + 4 * i)
    s, k, lad, n = [u32(p + 4 * j) for j in range(4)]
    m = [u16(p + 16 + 2 * j) for j in range(4)]
    return p, s, k, lad, n, m


def pricing(ctry):
    cs = struct.unpack_from('<6I8H', ROM, foff(CREDSYS))
    credsys = dict(address=hx(CREDSYS), table=hx(CREDSYS_TAB), id=1, state_nvram=hx(cs[0]), pricing_table_ram=hx(cs[1]),
                   custom_record_nvram=hx(cs[2]), custom_coin_door_nvram=hx(cs[3]), custom_ladder_nvram=hx(cs[4]),
                   slot_audit_list=hx(cs[5]), adj_pricing=cs[6], adj_coin_input_delay=cs[7], adj_free_play=cs[8],
                   adj_credit_limit=cs[9], meter_id=cs[10], units_counter=cs[11], credits_counter=cs[12], lockout_id=cs[13] & 0xff,
                   note='credit system #0 (0x40ce024) has only a state record (NVRAM 0x2111000) and no pricing; '
                        'the game uses #1 (RAM 0x30e9e = 1)', tag='code')
    slot_counters = msglist(cs[5])
    aud_by_counter = {}
    for a in range(1, AUD_N + 1):
        w = struct.unpack_from('<4I', ROM, foff(AUD_TAB + 16 * a))
        if not w[0]:
            aud_by_counter.setdefault(w[2] >> 16, (a, namep(w[1])))
    obs_slot = {}
    for l in emu_lines('t2.log'):
        m = re.search(r'coin_task_create task=0x13 r1=(\d+) slot=(\d+)', l)
        if m:
            obs_slot[int(m.group(2))] = int(m.group(1)) - 128
    keys = {0: 'PinMAME key 3', 1: 'key 4', 2: 'key 5', 3: 'key 6', 4: None}
    slots = []
    for s, c in enumerate(slot_counters):
        a, nm = aud_by_counter.get(c, (None, None))
        slots.append(dict(slot=s, audit_counter=c, audit=a, audit_name=nm, pinmame_input=keys.get(s),
                          tag='observed' if s in obs_slot else 'code'))
    summ, names_obs = {}, {}
    for l in emu_lines('t3.log'):
        m = re.search(r'callstr 0xa438\(\d+,(\d+),', l)
        if m:
            summ[int(m.group(1))] = l[l.index('"') + 1:l.rindex('"')]
        m = re.search(r'callstr 0x26a4c\(\d+,(\d+),', l)
        if m:
            names_obs[int(m.group(1))] = l[l.index('"') + 1:l.rindex('"')]
    default_for = collections.defaultdict(list)
    for c in ctry:
        if not any(a == 28 for a, _ in c['os'] + c['game']):
            default_for[adj_record(28)['default']].append('%s (table default)' % c['name'])
        for adj, v in c['os'] + c['game']:
            if adj == 28:
                default_for[v].append(c['name'])
    presets = []
    for i in range(NPRESET):
        p, s, k, lad, n, m = preset(i)
        units = []
        q = s
        while u32(q) and len(units) < 10:
            units.append(dict(unit_value=u32(q), slot_units=[u8(q + 4 + j) for j in range(5)], address=hx(q)))
            q += 12
        sel = units[k]
        uv = sel['unit_value']
        ladder = [u8(lad + j) for j in range(n)]
        cum, tot = [], 0
        for j, c in enumerate(ladder):
            tot += c
            if c:
                cum.append(dict(units=j + 1, money=(j + 1) * uv, credits=tot))
        first = cum[0]['units'] if cum else None
        fmt_money = msg(m[2])

        def money(x, f=fmt_money):
            try:
                return f.replace('%,d', '%d') % ((x // 100, x % 100) if f.count('%') >= 2 else (x // 100,))
            except Exception:
                return str(x)
        presets.append(dict(
            adj_value=i, name=msg(m[0]), name_msg=hx(m[0]), record=hx(p), coin_door=hx(s), unit_table=units, unit_index=k,
            unit_value_minor=uv, money_formats=dict(plain=msg(m[1]), short=msg(m[2]), long=msg(m[3]), msg_ids=[hx(x) for x in m[1:]]),
            slot_units=sel['slot_units'], slot_money=[money(x * uv) for x in sel['slot_units']],
            ladder=ladder, ladder_address=hx(lad), ladder_length=n, cycle_money=money(n * uv), cycle_credits=tot,
            awards=[dict(units=c['units'], money=money(c['money']), credits_total=c['credits']) for c in cum],
            first_credit_units=first, first_credit_money=money(first * uv) if first else None,
            service_summary=summ.get(p), service_summary_tag='observed' if p in summ else None,
            name_observed=names_obs.get(i), factory_default_for=default_for.get(i, []), tag='code'))
    custom = dict(adj_value=NPRESET, name=msg(0x287), name_msg=hx(0x287), name_observed=names_obs.get(NPRESET),
                  record='NVRAM %s (0x1a bytes + ~checksum16): {coin-door ptr -> %s (10 x 12 B unit table), unit index, ladder ptr -> %s '
                         '(<= 100 B), ladder length, u16 name msg 0x287, u16 money formats x3, u8 valid}' % (hx(cs[2]), hx(cs[3]), hx(cs[4])),
                  editor='SET CUSTOM PRICING (item 107, 0x10457c4)',
                  how='0x4764 copies the factory-default preset (unit table, unit index, money formats) with an empty ladder; the operator '
                      'sets the credits given at each unit step, up to 100 steps; INSTALL saves it with 0x48a8 (trailing zero steps are '
                      'trimmed, valid byte set) and the preset is selected with adj 28 = 68',
                  factory='empty (0x4694 clears it): no unit table, no ladder', tag='code')
    algo = r'''credit system #1 = 0x040ce04c (table 0x040ce024 + id*0x28, id = RAM 0x30e9e = 1)
  state  NVRAM 0x2111008: s32 pos (-1 = start), u8 credits, u8 ~checksum8(5)   [0x3cdc validates, 0x3ca8 resets]
coin switch -> 0x4164 task_create(0x13, coin_task 0x3f00); task+0x38 = slot 0-4, +0x30 = credit system  [observed]
  coin_task 0x3f00:
    if slot >= 5: error_log(100); return
    if coin lockout (0x3ea8): return                                                      # coin ignored
    d = adj_get(62 COIN INPUT DELAY); if d != 61 (OFF): repeat d times { task_sleep(1); if lockout: return }   # ~0.49 s at 30 (observed)
    audit_add(slot_counter[slot] = 2,3,4,5,6 (LEFT,CENTER,RIGHT,FOURTH,FIFTH), 1)
    P = pricing[adj_get(28 GAME PRICING)]       # 0x3e3c; RAM table 0x32324, 68 presets + CUSTOM (NVRAM 0x2110808)
    units = P.coin_door[P.unit_index].slot_units[slot]
    if units == 0: return
    meter_add(1, units) 0x9b54                  # coin meter
    audit_add(7 units counter = METER CLICKS / TOTAL EARNINGS, units)
    0x26588(...)                                 # game hook (coin accepted)
    repeat units times:
        pos = pos + 1; if pos >= P.ladder_len: pos = 0      # the ladder repeats
        c = P.ladder[pos]
        if c: n = credits_add(c) 0x3d40         # capped: credits + c <= adj_get(33 CREDIT LIMIT)
              audit_add(1 TOTAL PAID CREDITS, c)    # counts c, not the capped n (observed)
              event_post(0x19, {cs, n})
        deff_start(10)                           # coin/credit display effect
    if no credit was added: event_post(0x1a, {cs})
display: 0x44a4 -> "FREE PLAY" (msg 0x283) when adj 34 = YES (0x4464), else "CREDITS %d" / "CREDITS %d/%d" / "CREDITS %d %d/%d" (0x284-0x286)
         fraction (0x41f8) = units since the last ladder award / units between that award and the next.
pricing change (event 5 hook 0x45a4 on adj 28): pos = -1 (credits kept)       [observed]
0x43c8: keep only the units after the last award.
reset credits 0x4338: pos = -1, credits = 0.
replay/special/match/high-score credits use 0x41a0 (same cap); FREE GAME LIMIT (adj 25) is not checked by replay_award 0x1c410 (observed).'''
    verif = []
    for l in emu_lines('t2.log'):
        if re.search(r' (credits|callstr 0x44a4|callstr 0x26a4c|mark|adjset|adjpoke|call 0x1c410|key )', l):
            verif.append(l.strip())
    return dict(credit_system=credsys, coin_slots=slots, presets=presets, custom=custom, algorithm=algo,
                countries=[dict(code=c['code'], name=c['name'], name_msg=hx(c['name_msg']), record=hx(c['rec']),
                                os_overrides=c['os'], game_overrides=c['game'], os_list=hx(c['os_list']), game_list=hx(c['game_list']),
                                custom_message_list=hx(c['cec_list']) if c['cec_list'] else None, custom_messages=c['cec_msgs'],
                                redemption_defaults=hx(c['redemption_defaults']))
                           for c in ctry],
                related_adjustments={28: 'GAME PRICING: 0-67 presets below, 68 = CUSTOM', 33: 'CREDIT LIMIT 4-50', 34: 'FREE PLAY',
                                     62: 'COIN INPUT DELAY 30-60 ticks, 61 = OFF', 44: 'Q24 OPTION (coin meter / token / knocker)',
                                     37: 'BILL VALIDATOR'},
                verification_log=verif)


# ================================================================ audits
AUD_FORMULA = {
    2: ('0x26c94', 'c17 ? audit28 * 100 / c17 : 0', 'FREE GAME PERCENTAGE = TOTAL FREE PLAYS x 100 / paid plays (counter 17)'),
    3: ('0x26bbc', 'c8 ? c63 / c8 : 0', 'AVERAGE BALL TIME (s) = ball time counter 63 / TOTAL BALLS PLAYED (counter 8)'),
    4: ('0x26bfc', 'audit29 ? c60 / audit29 : 0', 'AVERAGE GAME TIME (s) = game time counter 60 / TOTAL PLAYS'),
    10: ('0x26e10', 'c2 + c3 + c4 + c5 + c6', 'TOTAL COINS = sum of the five slot counters'),
    11: ('0x26e7c', 'c7  (shown as money: c7 x unit value of the CURRENT pricing, /100 and %100, money format record +0x16)',
         'TOTAL EARNINGS = units counter 7 converted with the pricing selected now (formatter 0x26f74)'),
    13: ('0x2af18', '0  (function is "mov r0,#0; mov pc,lr")', 'SOFTWARE METER: always 0 in v1.80'),
    16: ('0x26c48', 'c17 ? c9 * 100 / c17 : 0', 'EXTRA BALL PERCENTAGE = extra balls (counter 9) x 100 / paid plays'),
    21: ('0x26f1c', 'c10 + c11 + c12 + c13', 'TOTAL REPLAYS = replay 1-4 awards'),
    22: ('0x26d34', 'c17 ? audit21 * 100 / c17 : 0', 'REPLAY PERCENTAGE'),
    24: ('0x26d80', 'c17 ? c14 * 100 / c17 : 0', 'SPECIAL PERCENTAGE'),
    27: ('0x26ce0', 'c17 ? c16 * 100 / c17 : 0', 'HIGH SCORE PERCENT'),
    28: ('0x26e94', 'audit21 + c14 + c15 + c16', 'TOTAL FREE PLAYS = replays + specials + matches + high score awards'),
    29: ('0x26eec', 'c17 + c18', 'TOTAL PLAYS = counter 17 (paid starts) + counter 18 (free starts)'),
    47: ('0x26c3c -> 0x1cd60', '(score_sum_u64 / score_count) / 10 * 10; 0 when the record at NVRAM 0x21109d4 fails 0x1cd2c or count = 0',
         'AVERAGE SCORES from NVRAM 0x21109d4 {u64 sum, u32 count}'),
    53: ('0x26dcc', 'c8 - c40 - c41', 'CENTER DRAINS = balls played - left drains - right drains'),
    72: ('0x26d2c', '0  (function is "mov r0,#0; mov pc,lr")', 'RECENT REPLAY PERCENT: always 0% in v1.80'),
}
TYPE_FMT = {1: ('0x2af20', '"%d"'), 2: ('0x2af30', '"%d%%"'), 3: ('0x2af40', '"%2d:%02d" of value/60, value%60 (seconds)'),
            4: ('0x26f74', 'money: value x unit_value(current pricing) -> fmt msg at pricing record +0x16 (e.g. "USD %,d.%02d")'),
            5: ('0x270bc', 'score: fmt msg RAM 0x30e96 (0x502 "%,02lu")'),
            6: ('0x2700c', 'count + share of TOTAL PLAYS p: p=0 -> msg 0x500 "%u\\n%u%% OF GAMES"(v,0); v/p=0 -> 0x500 (v, v*100/p); '
                           'else 0x501 "%u\\n%u%u%% OF GAMES" (v, v/p, (v%p)*100/p)')}


def audit_menu(a):
    earn, std = msglist(EARN_LIST), msglist(STDAUD_LIST)
    if a in earn:
        return 'EARNINGS AUDITS', 'EARNINGS AUDIT #%d' % (earn.index(a) + 1)
    if a in std:
        return 'STANDARD AUDITS', 'STANDARD AUDIT #%d' % (std.index(a) + 1)
    if FEAT_AUD[0] <= a <= FEAT_AUD[1]:
        return 'FEATURE AUDITS', 'FEATURE AUDIT #%d' % (a - FEAT_AUD[0] + 1)
    return '', ''


def audits():
    obs = {}
    phase = 'zero'
    for l in emu_lines('t1.log'):
        if 'mark POKE' in l:
            phase = 'poked'
        m = re.match(r'[\d.]+ audit (\d+) sel=0x(\w+) type=\d+ value=(-?\d+) text="(.*)"', l)
        if m:
            obs.setdefault((int(m.group(1)), m.group(2), phase), (m.group(3), m.group(4).replace('|', '\\n')))
    inc = collections.defaultdict(set)
    for site, isbl in callers(F['audit_add']):
        c = r0_const(site)
        if c is not None:
            inc[c].add(fname(func_of(site)))
    rows = []
    for a in range(1, AUD_N + 1):
        ea = AUD_TAB + 16 * a
        fn, np_, cw, fl = struct.unpack_from('<4I', ROM, foff(ea))
        cnt, ty = cw >> 16, cw & 0xffff
        menu, num = audit_menu(a)
        rec = struct.unpack_from('<3I', ROM, foff(CNT_TAB + 12 * cnt)) if not fn else None
        f = AUD_FORMULA.get(a)
        zero, pok, life = obs.get((a, 'c0', 'zero')), obs.get((a, 'c0', 'poked')), obs.get((a, '90', 'zero'))
        rows.append(dict(
            audit=a, name=namep(np_) if np_ else '', formula_fn=hx(fn) if fn else '', w_0x08='0x%08x' % cw, w_0x0c='0x%08x' % fl,
            desc_addr=hx(ea), menu=menu, menu_label=num,
            counter=cnt if not fn else '', counter_nvram=hx(rec[0]) if rec else '', counter_flags=hx(rec[2]) if rec else '',
            display_type=ty, display_format=TYPE_FMT.get(ty, ('', ''))[1], formatter=TYPE_FMT.get(ty, ('', ''))[0],
            lifetime_line='yes ([LIFETIME: x], sel 0x90)' if fl & 1 else '',
            formula=f[1] if f else ('counter %d' % cnt), meaning=f[2] if f else '',
            div_by_zero='0' if f and '?' in f[1] else '', rounding='integer division, truncated' if f and '/' in f[1] else '',
            incremented_by=';'.join(sorted(inc.get(cnt, [])))[:200] if not fn else '',
            observed_zero=('%s -> "%s"' % zero) if zero else '', observed_poked=('%s -> "%s"' % pok) if pok else '',
            observed_lifetime=('%s -> "%s"' % life) if life else '',
            tag='observed' if pok else 'code'))
    return rows


# ================================================================ menus / service texts
def menu_items():
    items = {}
    for k in range(1, NITEMS):
        vis, act, scr, m, icon, sub = struct.unpack_from('<IIIHHI', ROM, foff(ITEMS + 20 * k))
        kind = ACT.get(act, 'screen' if scr else ('action' if act else 'none'))
        if kind == 'submenu' and not sub:
            kind = 'page'
        items[k] = dict(vis=vis, act=act, scr=scr, msg=m, icon=icon, sub=sub, kind=kind)
    menus = {}
    for k in range(NMENUS):
        _, _, p = struct.unpack_from('<3I', ROM, foff(MENUS + 12 * k))
        menus[k] = msglist(p) if p and foff(p) is not None else []
    return items, menus


def runtime_menus():
    out = {}
    for l in emu_lines('t1.log'):
        m = re.search(r' menu (\d+) count=(\d+) items=([\d,]*)', l)
        if m:
            out[int(m.group(1))] = [int(x) for x in m.group(3).split(',') if x]
    return out


# text APIs and service helpers by address (names come from the current decompile)
TEXT_API_ADDR = {0x99f0: 'msg_get', 0x215ac: 'text_draw_msg', 0x21660: 'text_printf_msg', 0x2174c: 'text_draw_msg_fit',
                 0x217b4: 'text_printf_msg_fit'}
HELPER_ADDR = {0x1046598: ([6], 'audit screen title: msg passed to 0x1046598 (arg 6, y=5)'),
               0x1045c08: ([6], 'adjustment screen title: msg passed to 0x1045c08 (arg 6, y=5)'),
               0x1049910: ([3, 4, 5, 6], 'install screen text: msg passed to 0x1049910 (args 3-6, drawn at y=9/10/0x12 and status line)')}
TEXT_API = {fname(a): n for a, n in TEXT_API_ADDR.items()}
MSG_HELPERS = {fname(a): v[0] for a, v in HELPER_ADDR.items()}
HELPER_ROLE = {fname(a): v[1] for a, v in HELPER_ADDR.items()}


def split_args(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth == 0:
                break
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''
        else:
            cur += ch
    out.append(cur.strip())
    return out


def lit(s):
    s = re.sub(r'^\((ushort|uint|short|int|undefined2|undefined4)\)', '', s.strip())
    return int(s, 0) if re.fullmatch(r'0x[0-9a-fA-F]+|\d+', s) else None


def texts_in(fa):
    out = []
    for l in body(fa)[1:]:
        for api in tuple(TEXT_API) + tuple(MSG_HELPERS):
            for m in re.finditer(r'\b%s\(' % api, l):
                args = split_args(l[m.end():])
                if api in MSG_HELPERS:
                    for k in MSG_HELPERS[api]:
                        if len(args) >= k and lit(args[k - 1]) is not None:
                            out.append((lit(args[k - 1]), api, args, args[k - 1]))
                    continue
                out.append((lit(args[0]), TEXT_API[api], args, args[0]))
    return out


def callees(fa):
    out = set()
    for l in body(fa)[1:]:
        for m in re.finditer(r'\b(FUN_[0-9a-f]{8}|[a-z_][a-z0-9_]*)\(', l):
            a = H_BYNAME.get(m.group(1))
            if a is not None and a != fa:
                out.add(a)
    return out


def service_texts(items, obs_menus, labels, ctry):
    parent = {}
    for mk, lst in obs_menus.items():
        for it in lst:
            parent.setdefault(it, mk)
    menu_name = dict(MENU_NAMES)

    def path(k):
        p, seen = [], set()
        mk = parent.get(k)
        while mk and mk not in seen:
            seen.add(mk); p.append(menu_name.get(mk, 'menu %d' % mk))
            owner = [i for i, x in items.items() if x['kind'] == 'submenu' and x['sub'] == mk]
            mk = parent.get(owner[0]) if owner else None
        return ' > '.join(reversed(p))
    rows = []
    for k, it in items.items():
        rows.append(dict(msg=hx(it['msg']), text=msg(it['msg']), role='menu item name', menu=path(k) or '(not in any runtime menu)',
                         item=k, item_text=msg(it['msg']), screen_fn=hx(it['scr'] or it['act']),
                         drawn_by='service menu renderer (item table 0x40e3c40 +0xc)',
                         notes='%s; icon image %d%s' % (it['kind'], it['icon'], '; shown only if %s' % SHOWN_IF.get(k, hx(it['vis'])) if it['vis'] else ''),
                         tag='observed' if k in parent else 'code'))
    ncall = collections.Counter()
    for fa in H_NAME:
        for c in callees(fa):
            ncall[c] += 1
    seen_rows = set()
    roots = [(k, it['scr'] or it['act']) for k, it in items.items() if (it['scr'] or it['act']) and (it['scr'] or it['act']) not in ACT]
    roots += [(None, 0x103f960), (None, 0x1045c08), (None, 0x1046598), (None, 0x1049910)]
    for k, root in roots:
        if root not in H_LINE:
            continue
        frontier, depth, visited = [root], 0, {root}
        while frontier and depth <= 3:
            nxt = []
            for fa in frontier:
                for v, api, args, expr in texts_in(fa):
                    key = (v if v is not None else expr, fa)
                    if key in seen_rows:
                        continue
                    seen_rows.add(key)
                    y = args[5] if api.startswith('text_') and len(args) > 5 else ''
                    role = HELPER_ROLE.get(api) or (('dynamic: %s' % expr[:80]) if v is None else api)
                    rows.append(dict(msg=hx(v) if v is not None else '', text=msg(v) if v is not None else '', role=role,
                                     menu=path(k) if k else 'service menu shell', item=k or '', item_text=msg(items[k]['msg']) if k else '',
                                     screen_fn=hx(root), drawn_by='%s %s%s' % (hx(fa), fname(fa), (' y=%s' % y) if y else ''),
                                     notes='', tag='code'))
                for c in callees(fa):
                    if c in visited or ncall[c] > 12:
                        continue
                    if not fname(c).startswith('FUN_') and not (0x1040000 <= c < 0x1050000):
                        continue
                    visited.add(c); nxt.append(c)
            frontier, depth = nxt, depth + 1
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        fn, arg = fmt_of(r)
        if fn == 0 and arg:
            std = i not in range(FEAT_ADJ[0], FEAT_ADJ[1] + 1)
            for v, mid in enumerate(msglist(arg)):
                rows.append(dict(msg=hx(mid), text=msg(mid), role='adjustment value label', menu='ADJUSTMENTS',
                                 item=58 if std else 125, item_text='STANDARD ADJUSTMENTS' if std else 'FEATURE ADJUSTMENTS',
                                 screen_fn='0x1045c08', drawn_by='0x76c msg-list formatter (via 0x1045c08, y=0x16)',
                                 notes='adj %d %s value %d' % (i, r['name'], v), tag='code'))
    for c in ctry:
        rows.append(dict(msg=hx(c['name_msg']), text=c['name'], role='country name (country record +0x14)', menu='boot / country check',
                         item='', item_text='', screen_fn='', drawn_by='country table 0x040ceca4 +0x14', notes='country %d' % c['code'], tag='code'))
    for i in range(NPRESET + 1):
        mid = preset(i)[5][0] if i < NPRESET else 0x287
        rows.append(dict(msg=hx(mid), text=msg(mid), role='pricing preset name', menu='ADJUSTMENTS', item=58, item_text='STANDARD ADJUSTMENTS',
                         screen_fn='0x1045c08', drawn_by='0x26a4c (adj 28 formatter: pricing record +0x10)', notes='GAME PRICING = %d' % i,
                         tag='observed'))
    return rows


# ================================================================ package (mpf_package)
def setting_key(a, used):
    k = re.sub(r'[^a-z0-9]+', '_', a['name'].lower()).strip('_')
    if a['id'] in (97, 98):
        k += '_trim'
    if k in used:
        k += '_%d' % a['id']
    used.add(k)
    return k


def thin(vals, d):
    """MPF settings need a list of values; keep the ROM's step up to 150 values, else a coarser ladder."""
    if len(vals) <= 150:
        return vals
    keep = set(vals[:20]) | {d, vals[-1]}
    keep |= set(vals[::max(1, len(vals) // 120)])
    return sorted(keep)


def package(adjrows, labels, A, items, obs_menus, inst, static_menus):
    os.makedirs(os.path.join(PKG, 'config'), exist_ok=True)
    std_order = msglist(STD_ORDER)
    adjs = []
    for r in adjrows:
        i = r['adj']
        rec = adj_record(i)
        grp = 'standard' if i in std_order else 'feature'
        adjs.append(dict(id=i, name=rec['name'], default=rec['default'], factory_default_usa=r['factory_default_usa'],
                         min=rec['min'], max=rec['max'], step=rec['step'], display_type=rec['display_type'], group=grp,
                         menu_label=r['menu_label'], visible_if=r['visible_if'], wraps=r['wraps'],
                         labels={str(k): v for k, v in sorted(labels[i]['labels'].items())},
                         menu_order=std_order.index(i) if i in std_order else 1000 + i))
    auds = [dict(id=a['audit'], name=a['name'], menu=a['menu'].split()[0].lower() if a['menu'] else '', menu_label=a['menu_label'],
                 counter=a['counter'] if a['counter'] != '' else 0, computed=bool(a['formula_fn']), display_type=a['display_type'])
            for a in A]

    def it_json(i):
        it = items[i]
        return dict(item=i, text=msg(it['msg']), kind=it['kind'], submenu=it['sub'] if it['kind'] == 'submenu' else None,
                    shown_only_if=hx(it['vis']) if it['vis'] else None, screen_fn=hx(it['scr']) if it['scr'] else None)
    menus_json = {MENU_NAMES.get(k, str(k)): [it_json(i) for i in v] for k, v in sorted(obs_menus.items()) if v}
    hidden_json = {MENU_NAMES.get(k, str(k)): [it_json(i) for i in static_menus.get(k, []) if i not in v]
                   for k, v in sorted(obs_menus.items()) if [i for i in static_menus.get(k, []) if i not in v]}
    presets = collections.OrderedDict()
    for p in inst:
        presets.setdefault(p['preset'], [])
        if p['adj'] == 'all':
            presets[p['preset']].append(dict(adj='all', name='every adjustment', value='factory default', label='factory default', list=''))
        elif p['adj'] != '':
            presets[p['preset']].append(dict(adj=p['adj'], name=p['name'], value=p['value'], label=p['label'], list=p['list']))
    json.dump(dict(rom='Transformers Pro v1.80 (tf_180)', menus=menus_json, adjustments=adjs, audits=auds,
                   install_presets=presets, hidden_with_factory_settings=hidden_json, conditional_items={str(k): v for k, v in SHOWN_IF.items()},
                   note='Menus are the runtime lists built by 0xeb3c with factory settings (observed, rom_data/settings/menus_runtime.json).'),
              open(os.path.join(PKG, 'service_menu.json'), 'w'), indent=1)
    # ---- settings.yaml
    used = set()
    out = ['#config_version=6\n'
           '# Generated from the Stern Transformers Pro v1.80 ROM (tf_180) by rom/tools/settings_extract.py. See ../service_menu.md.\n'
           '# All %d operator adjustments, as MPF machine settings. Keys are the ROM names in snake case.\n' % len(adjs) +
           '# setting_type: standard = the ROM\'s STANDARD ADJUSTMENTS menu, feature = FEATURE ADJUSTMENTS (Transformers).\n'
           '# sort is the ROM menu order. Labels are what the ROM shows for each value (English).\n'
           '# default is the U.S.A. factory default (after INSTALL FACTORY); the table default is in the comment when it differs.\n'
           '# Settings with very long ranges (scores, IDs) list a coarser ladder; the ROM range is in the comment.\n'
           'settings:\n']
    for a in sorted(adjs, key=lambda x: x['menu_order']):
        labs = labels[a['id']]['labels']
        d = a['factory_default_usa'] if a['factory_default_usa'] != '' else a['default']
        vals = thin(sorted(labs), d)
        if d not in vals and d in labs:
            vals = sorted(set(vals) | {d})
        k = setting_key(a, used)
        a['setting'] = k
        out.append('  %s:   # adj %d (%s), ROM range %s..%s step %s%s\n' % (
            k, a['id'], a['menu_label'], a['min'], a['max'], a['step'], '; table default %d' % a['default'] if d != a['default'] else ''))
        out.append('    label: %s\n    values:\n' % json.dumps(a['name']))
        for v in vals:
            out.append('      %d: %s\n' % (v, json.dumps(labs[v])))
        out.append('    default: %d\n    key_type: int\n    sort: %d\n    setting_type: %s\n' % (
            d, (a['menu_order'] + 1) * 10 if a['group'] == 'standard' else 1000 + a['id'] * 10, a['group']))
    open(os.path.join(PKG, 'config', 'settings.yaml'), 'w').write(''.join(out))
    # ---- service_menu.md
    def esc(s):
        return (s or '').replace('|', '/').replace('\n', ' ')
    md = ['# Transformers Pro v1.80: service menu, adjustments and audits\n\n',
          'Read from the ROM (`tf_180`) by `rom/tools/settings_extract.py`. The menu tree is the one the ROM builds at run time '
          '(0xeb3c, factory settings, observed in the emulator); item texts, the adjustment table (98 entries), value labels '
          'and audit names come from the ROM\'s own tables, and function-formatted value labels were produced by running the '
          'ROM\'s own formatter code in the emulator. `config/settings.yaml` has every adjustment as an MPF setting. '
          'Details and evidence tags are in `rom/rom_data/settings/`.\n',
          '\n## Buttons\n\nThe coin door has four service buttons: BACK, MINUS, PLUS and SELECT (SAM dedicated switches).\n'
          'SELECT enters the menu from attract mode and opens an item, MINUS/PLUS move or change a value, BACK leaves.\n'
          'Every menu ends with a return item, EXIT SERVICE MENU and DISPLAY HELP SCREEN.\n',
          '\n## Menu tree\n\nItems marked *(Transformers)* are added by the game code through event 0x5d; the rest are the '
          'Stern SAM operating system. Items marked *(only when ...)* have a shown-only-if function.\n\n']
    adj_std = [a for a in adjs if a['group'] == 'standard']
    adj_feat = [a for a in adjs if a['group'] == 'feature']

    def walk(k, depth, seen):
        hidden = [i for i in static_menus.get(k, []) if i not in obs_menus.get(k, []) and items[i]['kind'] not in ('back', 'exit', 'help')]
        for i in obs_menus.get(k, []) + hidden:
            it = items[i]
            if it['kind'] in ('back', 'exit', 'help'):
                continue
            tag = ' *(Transformers)*' if i >= 124 else ''
            if it['vis']:
                tag += ' *(only when %s)*' % SHOWN_IF.get(i, hx(it['vis'])).split(': ', 1)[-1]
            if i in hidden:
                tag += ' *(hidden with factory settings)*'
            md.append('%s- %s%s\n' % ('  ' * depth, msg(it['msg']), tag))
            if it['kind'] == 'submenu' and it['sub'] and it['sub'] not in seen:
                walk(it['sub'], depth + 1, seen | {it['sub']})
            sub = {58: 'STANDARD ADJUSTMENT #1-#%d (%d adjustments, listed below)' % (len(adj_std), len(adj_std)),
                   125: 'FEATURE ADJUSTMENT #1-#%d = adj %d-%d' % (len(adj_feat), FEAT_ADJ[0], FEAT_ADJ[1]),
                   52: 'EARNINGS AUDIT #1-#13 = audits 1-13', 53: 'STANDARD AUDIT #1-#59 = audits 14-72',
                   124: 'FEATURE AUDIT #1-#%d = audits %d-%d' % (FEAT_AUD[1] - FEAT_AUD[0] + 1, FEAT_AUD[0], FEAT_AUD[1])}.get(i)
            if sub:
                md.append('%s  - %s\n' % ('  ' * depth, sub))
    walk(1, 0, {1})
    md.append('\nNotes:\n'
              '- GO TO FUSE TABLE, SINGLE SWITCH TEST and the three FLOW CHART items (DR. PINBALL menu) open help pages.\n'
              '- ORDERED LAMP TEST (item 37) and TICKET DISPENSER TEST (item 17) exist in the ROM but are not in the factory menus. '
              'The game inserts item 17 before RETURN in the diagnostics menu only when ticket dispenser 1 is configured (0xf644(1)).\n'
              '- GO TO SERIAL MENU (item 66, menu 13 with UPDATE GAME CODE) is in no menu list, so it cannot be reached in v1.80.\n'
              '- GAME-SPECIFIC TESTS has one test: OPTIMUS PRIME MOTOR TEST (screen 0x1025844).\n'
              '- Hidden adjustments: the adjustment menu skips ids for which adj_visible 0x2be10 returns 0 (column visible_if).\n')
    md.append('\n## Adjustments\n\n`#` is the ROM table id; `Menu label` is what the machine shows. `Default` is the U.S.A. factory '
              'default. `setting` is the key in `config/settings.yaml`.\n\n'
              '| # | Menu label | Name | Default | Values | Shown when | Setting |\n|---|---|---|---|---|---|---|\n')
    for a in sorted(adjs, key=lambda x: (x['group'] != 'standard', x['menu_order'])):
        labs = labels[a['id']]['labels']; ks = sorted(labs)
        plain = all(labs[v] == str(v) or labs[v] == '{:,}'.format(v) for v in ks)
        if plain or len(ks) > 12:
            vs = '%s..%s step %s' % (labs[ks[0]], labs[ks[-1]], '{:,}'.format(a['step'])) if len(ks) > 1 else labs[ks[0]]
            if not plain:
                vs += ' (e.g. %s)' % ', '.join(labs[v] for v in ks[:4])
        else:
            vs = ', '.join('%d=%s' % (v, labs[v]) for v in ks)
        d = a['factory_default_usa'] if a['factory_default_usa'] != '' else a['default']
        md.append('| %d | %s | %s | %s | %s | %s | `%s` |\n' % (a['id'], a['menu_label'], esc(a['name']), esc(labs.get(d, str(d))),
                                                             esc(vs), a['visible_if'] if a['visible_if'] != 'always' else '', a['setting']))
    md.append('\n## Install presets\n\nINSTALL items (UTILITIES > GO TO INSTALLS MENU) apply an OS list and a game list with '
              '0x598 (screen 0x1049910). INSTALL FACTORY (0x1049774) resets every adjustment with 0x728.\n\n')
    for k, v in presets.items():
        md.append('- **%s**: %s\n' % (k, ', '.join('%s = %s' % (x['name'], x['label'] or x['value']) for x in v) if v else 'no changes'))
    md.append('\n## Audits\n\n| # | Menu label | Name | Kind |\n|---|---|---|---|\n')
    for a in A:
        md.append('| %d | %s | %s | %s |\n' % (a['audit'], a['menu_label'], esc(a['name']),
                                              ('computed ' + a['formula_fn']) if a['formula_fn'] else 'counter %s' % a['counter']))
    open(os.path.join(PKG, 'service_menu.md'), 'w').write(''.join(md))
    print('package: %d adjustments, %d audits, %d menus' % (len(adjs), len(auds), len(menus_json)))


# ================================================================ emulator scripts
def write_scripts():
    os.makedirs(EMU, exist_ok=True)

    def w(name, lines):
        open(os.path.join(EMU, name), 'w').write('\n'.join(lines) + '\n')
    aud = lambda: ['audit %d' % a for a in range(1, AUD_N + 1)] + \
        ['audit %d 0x90' % a for a in range(1, AUD_N + 1) if u32(AUD_TAB + 16 * a + 12) & 1]
    L = ['dumpram ram_usa.bin', 'peek 3379e 8', 'credits', 'callstr 44a4 1 B'] + ['menu %d' % m for m in range(1, NMENUS)]
    for i in range(1, ADJ_N + 1):
        L += ['call 340 %d' % i, 'call 3d8 %d' % i]
    L += aud() + ['mark POKE'] + ['call c3c %d %d' % cv for cv in [
        (17, 40), (18, 10), (14, 2), (15, 4), (16, 5), (10, 3), (11, 2), (12, 1), (13, 1), (9, 7), (8, 120), (40, 30), (41, 25),
        (63, 9000), (60, 10000), (2, 5), (3, 2), (4, 1), (5, 1), (6, 1), (7, 13), (1, 6), (19, 3), (36, 2), (65, 17), (66, 77),
        (87, 4), (154, 9)]] + aud() + ['mark END']
    w('t1.txt', L)
    L = ['mark PRICING_USA10', 'credits', 'key 3', 'key 3', 'key 3', 'wait 1', 'credits', 'callstr 44a4 1 B', 'key 4', 'wait 1', 'credits',
         'callstr 44a4 1 B', 'key 5', 'wait 1', 'credits', 'callstr 44a4 1 B', 'key 6', 'wait 1', 'credits', 'callstr 44a4 1 B',
         'mark GERMANY2', 'adjset 28 24', 'credits', 'callstr 26a4c B 24', 'key 4', 'wait 1', 'credits', 'callstr 44a4 1 B', 'key 5', 'wait 1',
         'credits', 'callstr 44a4 1 B', 'key 3', 'wait 1', 'credits', 'callstr 44a4 1 B',
         'mark EURO3', 'adjset 28 13', 'credits', 'key 3', 'wait 1', 'credits', 'callstr 44a4 1 B', 'key 3', 'wait 1', 'credits',
         'callstr 44a4 1 B', 'key 4', 'wait 1', 'credits', 'callstr 44a4 1 B',
         'mark FREEPLAY', 'adjset 34 1', 'callstr 44a4 1 B', 'adjset 34 0',
         'mark CREDITLIMIT', 'call 4338 1', 'credits', 'adjset 28 66', 'adjset 33 4', 'key 4', 'wait 1', 'key 4', 'wait 1', 'credits', 'key 4',
         'wait 1', 'credits', 'callstr 44a4 1 B', 'key 4', 'wait 1', 'credits', 'callstr 44a4 1 B', 'adjset 33 30',
         'mark COINDELAY_OFF', 'adjset 62 61', 'key 3', 'wait 1', 'credits', 'adjset 62 30',
         'mark ADJ25', 'call 4338 1', 'key 4', 'wait 1', 'key 4', 'wait 1', 'credits', 'key 1', 'wait 4', 'adjpoke 25 0', 'credits',
         'adjlog 1', 'call 1c410 1 1', 'adjlog 0', 'wait 2', 'credits', 'call 1c410 1 2', 'wait 2', 'credits', 'mark END']
    w('t2.txt', L)
    L = []
    for i in range(NPRESET):
        L += ['stack 0xffffffff', 'callstr a438 B %d 0 128' % preset(i)[0], 'callstr 26a4c B %d' % i]
    w('t3.txt', L + ['callstr 26a4c B %d' % NPRESET])
    L = []
    for c in range(NCOUNTRY):
        L += ['country %d' % c] + ['call 340 %d' % i for i in range(1, ADJ_N + 1)]
    w('t4.txt', L + ['country 0', 'call 340 28', 'call 340 10'])
    vals = collections.defaultdict(set)
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        fn, arg = fmt_of(r)
        if fn:
            vals[fn] |= set(sample_values(r))
    L = []
    for fn in sorted(vals):
        vs = sorted(vals[fn])
        L += ['fmt %x %s' % (fn, ' '.join(map(str, vs[k:k + 20]))) for k in range(0, len(vs), 20)]
    w('t5.txt', L)
    # t6: adj_get call sites during boot settling, coins, a game start and three drains (counts: t6_adj_get_counts.txt)
    w('t6.txt', ['adjlog 1', 'mark boot_done', 'key 4', 'key 4', 'wait 1', 'credits', 'mark press_start', 'key 1', 'wait 8', 'mark ball1',
                 'sw 7', 'sw 8', 'sw 26', 'sw 30', 'wait 20', 'drain', 'wait 8', 'mark ball2', 'drain', 'wait 8', 'mark ball3', 'drain',
                 'wait 12', 'mark after_game', 'wait 4'])
    print('scripts written to', EMU)


# ================================================================ main
def main():
    os.makedirs(OUT, exist_ok=True)
    ctry = countries()
    labels = formatter_labels()
    # ---- pricing
    P = pricing(ctry)
    json.dump(P, open(os.path.join(OUT, 'pricing.json'), 'w'), indent=1)
    prow = []
    for p in P['presets']:
        prow.append(dict(adj_value=p['adj_value'], name=p['name'], record=p['record'], coin_door=p['coin_door'], unit_index=p['unit_index'],
                         unit_value_minor=p['unit_value_minor'], currency_format=p['money_formats']['long'],
                         slot1_units=p['slot_units'][0], slot2_units=p['slot_units'][1], slot3_units=p['slot_units'][2],
                         slot4_units=p['slot_units'][3], slot5_units=p['slot_units'][4],
                         slot_money='|'.join(p['slot_money']), ladder=' '.join(map(str, p['ladder'])), ladder_len=p['ladder_length'],
                         first_credit=p['first_credit_money'], awards='|'.join('%s=%d' % (a['money'], a['credits_total']) for a in p['awards']),
                         service_summary=p['service_summary'], factory_default_for='|'.join(p['factory_default_for']),
                         tag='observed' if p['service_summary_tag'] else 'code'))
    prow.append(dict(adj_value=NPRESET, name=P['custom']['name'], record=P['custom']['record'], tag='code'))
    wcsv('pricing.csv', prow, ['adj_value', 'name', 'record', 'coin_door', 'unit_index', 'unit_value_minor', 'currency_format',
                               'slot1_units', 'slot2_units', 'slot3_units', 'slot4_units', 'slot5_units', 'slot_money', 'ladder',
                               'ladder_len', 'first_credit', 'awards', 'service_summary', 'factory_default_for', 'tag'])
    # ---- audits (existing columns first)
    A = audits()
    wcsv('audits.csv', A, ['audit', 'name', 'formula_fn', 'w_0x08', 'w_0x0c', 'desc_addr', 'menu', 'menu_label', 'counter',
                           'counter_nvram', 'counter_flags', 'display_type', 'display_format', 'formatter', 'lifetime_line', 'formula',
                           'meaning', 'div_by_zero', 'rounding', 'incremented_by', 'observed_zero', 'observed_poked',
                           'observed_lifetime', 'tag'])
    # ---- adjustments (existing columns first)
    over = collections.defaultdict(list)
    obs_country = collections.defaultdict(dict)
    cur = None
    for l in emu_lines('t4.log'):
        m = re.search(r' country (\d+) ->', l)
        if m:
            cur = int(m.group(1)); continue
        m = re.search(r'call 0x340\((\d+),0,0,0\) = (-?\d+)', l)
        if m and cur is not None:
            obs_country[cur].setdefault(int(m.group(1)), int(m.group(2)))
    for c in ctry:
        for which, lst in (('', c['os']), (' (game list)', c['game'])):
            for a, v in lst:
                seen = obs_country.get(c['code'], {}).get(a)
                over[a].append('%s=%d%s%s' % (c['name'], v, which, ' [observed]' if seen == v else ''))
    std_order = msglist(STD_ORDER)
    rd = adj_readers()
    obs_def, obs_get = {}, {}
    for l in emu_lines('t1.log'):
        m = re.search(r'call 0x3d8\((\d+),0,0,0\) = (-?\d+)', l)
        if m:
            obs_def[int(m.group(1))] = int(m.group(2))
        m = re.search(r'call 0x340\((\d+),0,0,0\) = (-?\d+)', l)
        if m:
            obs_get[int(m.group(1))] = int(m.group(2))
    rows = []
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        lb = labels[i]
        if i in std_order:
            menu, num = 'STANDARD ADJUSTMENTS', 'STANDARD ADJUSTMENT #%d' % (std_order.index(i) + 1)
        else:
            menu, num = 'FEATURE ADJUSTMENTS', 'FEATURE ADJUSTMENT #%d' % (i - FEAT_ADJ[0] + 1)
        fdu = obs_get.get(i, obs_def.get(i, ''))
        rows.append(dict(adj=i, name=r['name'], default_table=r['default'], min=r['min'], max=r['max'], step=r['step'],
                         field_0x14=r['f14'], display_type=r['display_type'], nvram=hx(r['nvram']), desc_addr=hx(r['rec']),
                         tag='observed' if i in obs_get else 'code',
                         menu=menu, menu_label=num, default_label=lb['labels'].get(r['default'], ''),
                         factory_default_usa=fdu, factory_default_usa_label=lb['labels'].get(fdu, '') if fdu != '' else '',
                         wraps='no' if r['nowrap'] else 'yes', formatter=hx(lb['fn']) if lb['fn'] else 'msg list %s' % hx(lb['arg']),
                         labels=json.dumps({str(k): v for k, v in sorted(lb['labels'].items())}, ensure_ascii=False),
                         labels_source=lb['src'], visible_if=VISIBLE.get(i, 'always'), country_overrides='; '.join(over.get(i, [])),
                         readers='; '.join(rd.get(i, [])) or 'none (no adj_get call site with this id)'))
    wcsv('adjustments.csv', rows, ['adj', 'name', 'default_table', 'min', 'max', 'step', 'field_0x14', 'display_type', 'nvram', 'desc_addr',
                                   'tag', 'menu', 'menu_label', 'default_label', 'factory_default_usa',
                                   'factory_default_usa_label', 'wraps', 'formatter', 'labels', 'labels_source', 'visible_if',
                                   'country_overrides', 'readers'])
    # ---- presets
    items, menus = menu_items()
    INST = [(71, 0x337b8, 0x30eb4), (72, 0x337b0, 0x30f3c), (73, 0x337e0, 0x30fc4), (74, 0x337c8, 0x3104c), (75, 0x337c0, 0x310d4),
            (102, 0x33550, 0x311e4), (103, 0x33560, 0x3126c), (104, 0x335d0, 0x33618), (76, 0x337a8, 0x3115c), (77, 0x337d0, 0x337d8),
            (105, 0x33620, 0x33678), (106, 0x33570, 0x335c8)]
    name_of = {i: adj_record(i)['name'] for i in range(1, ADJ_N + 1)}
    pr = []
    for item, l1, l2 in INST:
        nm = msg(items[item]['msg'])
        entries = [('os', l1, a, v) for a, v in plist(l1)] + [('game', l2, a, v) for a, v in plist(l2)]
        if not entries:
            pr.append(dict(kind='install', preset=nm, item=item, list='os+game', list_address='%s / %s' % (hx(l1), hx(l2)), adj='',
                           name='(both lists empty: changes nothing)', value='', label='',
                           applied_by='%s -> 0x1049910 -> adj_apply_list 0x598' % hx(items[item]['scr']), tag='code'))
        for which, la, a, v in entries:
            pr.append(dict(kind='install', preset=nm, item=item, list=which, list_address=hx(la), adj=a, name=name_of.get(a),
                           value=v, label=labels[a]['labels'].get(v, '') if a in labels else '',
                           applied_by='%s -> 0x1049910 -> 0x598' % hx(items[item]['scr']), tag='code'))
    pr.append(dict(kind='install', preset=msg(items[78]['msg']), item=78, list='', adj='all', name='every adjustment',
                   value='factory default', label='', applied_by='0x1049774 -> 0x728 (0x530 for ids 1-98: 0x3d8 default)', tag='code'))
    for c in ctry:
        for which, lst, la in (('os', c['os'], c['os_list']), ('game', c['game'], c['game_list'])):
            for a, v in lst:
                seen = obs_country.get(c['code'], {}).get(a)
                pr.append(dict(kind='country', preset=c['name'], item='country %d' % c['code'], list=which, list_address=hx(la), adj=a,
                               name=name_of.get(a), value=v, label=labels[a]['labels'].get(v, '') if a in labels else '',
                               applied_by='factory default 0x3d8 -> 0x53dc (country NVRAM 0x21100d8, set from the DIP at boot by 0x550c)',
                               tag='observed' if seen == v else ('code' if seen is None else 'code (observed value %d)' % seen)))
    wcsv('presets.csv', pr, ['kind', 'preset', 'item', 'list', 'list_address', 'adj', 'name', 'value', 'label', 'applied_by', 'tag'])
    # ---- menus and service texts
    obs_menus = runtime_menus()
    json.dump({str(k): v for k, v in sorted(obs_menus.items())}, open(os.path.join(OUT, 'menus_runtime.json'), 'w'), indent=1)
    T = service_texts(items, obs_menus, labels, ctry)
    T = list({tuple(r.get(k) for k in sorted(r)): r for r in T}.values())
    T.sort(key=lambda r: (str(r['item']).zfill(4) if r['item'] != '' else 'zzzz', r['msg'], r['drawn_by'], r['role']))
    wcsv('service_texts.csv', T, ['msg', 'text', 'role', 'menu', 'item', 'item_text', 'screen_fn', 'drawn_by', 'notes', 'tag'])
    # ---- package
    package(rows, labels, A, items, obs_menus, [p for p in pr if p['kind'] == 'install'], menus)


if __name__ == '__main__':
    if '--scripts' in sys.argv:
        write_scripts()
    else:
        main()
