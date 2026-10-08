"""MPF config (v6) from the extracted tables. Usage: python3 build_mpf.py DATA_DIR PKG_DIR
DATA_DIR holds switches.csv, dedicated_switches.csv, coils.csv, lamps.csv, samples.csv, sound_calls.csv;
PKG_DIR gets config/*.yaml (media paths are relative to PKG_DIR/config)."""
import sys, os, csv, re, json
DATA, PKG = sys.argv[1], sys.argv[2]
CFG = os.path.join(PKG, 'config'); os.makedirs(CFG, exist_ok=True)
HDR = '#config_version=6\n# Generated from the Stern Transformers Pro v1.80 ROM (PinMAME set tf_180). See ../README.md.\n'
def rd(fn): return list(csv.DictReader(open(os.path.join(DATA, fn))))
def slug(s):
    s = re.sub(r'[^a-z0-9]+', '_', s.lower().replace('#', ' ')).strip('_')
    return s
def names(rows, key, prefix):
    out = {}; seen = {}
    for r in rows:
        nm = r['name']
        if not nm or nm == 'NOT USED' or re.match(r'^(LAMP|COIL) #\d+$', nm): continue
        base = prefix + slug(nm); seen.setdefault(base, []).append(r)
    for base, rs in seen.items():
        for r in rs: out[int(r[key])] = base if len(rs) == 1 else '%s_%s' % (base, r[key])
    return out
names_out = {}
# ---- switches
sw = rd('switches.csv'); ded = rd('dedicated_switches.csv')
sn = names(sw, 'number', 's_')
L = [HDR, '# number: the SAM switch number (Stern numbering, matrix 1-64, dedicated 129-160). Replace with your\n',
     '# platform\'s address. PinMAME numbers are the same for the matrix; dedicated ones are in the comment.\nswitches:\n']
for r in sw:
    n = int(r['number'])
    if n in sn: L.append('  %s:\n    number: %d   # %s\n' % (sn[n], n, r['name']))
dn = {}
for r in ded:
    if r['name'] in ('NOT USED',) or r['name'].startswith('DIP SW'): continue
    nm = 's_' + slug(r['name']); dn[int(r['rom_switch_number'])] = nm
    L.append('  %s:\n    number: %s   # %s %s, PinMAME %s\n' % (nm, r['rom_switch_number'], r['dedicated'], r['name'], r['pinmame_switch']))
open(os.path.join(CFG, 'switches.yaml'), 'w').write(''.join(L))
names_out['switches'] = {**{str(k): v for k, v in sn.items()}, **{str(k): v for k, v in dn.items()}}
# ---- coils
co = rd('coils.csv'); cn = names(co, 'coil', 'c_')
L = [HDR, '# number: the SAM driver number (1-32 on the IO board, 33-35 aux bus ticket outputs). FLASH: entries are\n',
     '# flashers. Motors and the orbit gate (5, 8, 30) are held outputs. Pulse and hold times were measured from the\n',
     '# solenoid register writes in the emulator (rom_data/io/coil_timing.csv, mpf_source column of coils.csv).\ncoils:\n']
for r in co:
    n = int(r['coil'])
    if n not in cn: continue
    L.append('  %s:\n    number: %d   # %s\n' % (cn[n], n, r['name']))
    src = r.get('mpf_source', '')
    if 'motor_or_long' in r['flags_decoded'] or src.startswith('motor'):
        L.append('    default_hold_power: 1.0   # held on, not pulsed\n')
        if r.get('mpf_default_pulse_ms'): L.append('    # the game ran it %s ms at a time\n' % r['mpf_default_pulse_ms'])
        continue
    if r.get('mpf_default_pulse_ms'): L.append('    default_pulse_ms: %s   # %s\n' % (int(round(float(r['mpf_default_pulse_ms']))), src))
    if r.get('mpf_default_hold_power'): L.append('    default_hold_power: %s\n' % r['mpf_default_hold_power'])
open(os.path.join(CFG, 'coils.yaml'), 'w').write(''.join(L))
names_out['coils'] = {str(k): v for k, v in cn.items()}
# ---- lights
la = rd('lamps.csv'); ln = names(la, 'lamp', 'l_')
L = [HDR, '# Lamp matrix: numbers as in the ROM\'s lamp test (1-80; unnamed "LAMP #n" entries are not used).\n',
     '# PinMAME drives lamp 58 (Megatron) and 60-62 (bumpers) as strobed LEDs.\nlights:\n']
for r in la:
    n = int(r['lamp'])
    if n in ln: L.append('  %s:\n    number: %d   # %s\n' % (ln[n], n, r['name']))
open(os.path.join(CFG, 'lights.yaml'), 'w').write(''.join(L))
names_out['lights'] = {str(k): v for k, v in ln.items()}
# ---- sounds and pools
sa = rd('samples.csv'); calls = rd('sound_calls.csv')
TRACK = {'speech': 'voice', 'sfx': 'sfx', 'music': 'music'}
L = [HDR, '# One entry per decoded ROM sample (mono WAV, the file header carries its rate: most speech 12 kHz,\n',
     '# everything else 24 kHz). Music with an intro and a looped body has loop_start_at and loops: -1, from the\n',
     '# ROM\'s stream script (label before the body, jump back after it).\nsounds:\n']
have = set()
for r in sa:
    if r['kind'] == 'stub': continue
    sid = int(r['sample'], 16); have.add(sid)
    L.append('  snd_%04x:\n    file: %s\n    track: %s\n' % (sid, os.path.basename(r['file']), TRACK[r['kind']]))
    if r['loop_start_s']: L.append('    loops: -1\n    loop_start_at: %ss\n' % r['loop_start_s'])
L.append('sound_pools:\n')
np = 0
for c in calls:
    ss = [int(x, 16) for x in c['samples'].split() if int(x, 16) in have]
    if not ss: continue
    L.append('  call_%s:\n    type: random_force_all\n    sounds: %s\n' % (c['call'][2:], ', '.join('snd_%04x' % s for s in ss))); np += 1
open(os.path.join(CFG, 'sounds.yaml'), 'w').write(''.join(L))
json.dump(names_out, open(os.path.join(DATA, 'mpf_names.json'), 'w'), indent=1)
print('switches', len(sn) + len(dn), 'coils', len(cn), 'lights', len(ln), 'sounds', len(have), 'pools', np)
