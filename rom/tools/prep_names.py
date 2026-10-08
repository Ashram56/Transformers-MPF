"""Build Ghidra v2 inputs for tf_180: seeds with names and signatures (from the Tron match plus manual IDs).
Usage: python3 prep_names.py MATCH.tsv TRON_SIGS.tsv OUTDIR"""
import sys, csv, collections
match, tsigs, out = sys.argv[1], sys.argv[2], sys.argv[3]
MANUAL = {  # address: (name, signature or '') -- identified on tf_180 (code + emulator)
 0xacfc: ('task_sleep', 'void task_sleep(int ticks)'),
 0xaa04: ('task_create', 'void * task_create(ushort id, void *fn, ushort flags, ushort stack)'),
 0x209b4: ('deff_start', 'int deff_start(ushort id, uchar queue, uchar force)'),
 0x20498: ('deff_start_core', 'int deff_start_core(ushort id, uchar queue, uchar force, uchar d)'),
 0x20134: ('dmd_show_pages', 'int dmd_show_pages(uint fg_page, uint bg_page)'),
 0x20220: ('deff_frame_sleep', 'int deff_frame_sleep(int ticks)'),
 0x201bc: ('dmd_flip', ''),
 0x200a0: ('dmd_page_alloc_pair', ''), 0x1ffd4: ('dmd_page_alloc', ''),
 0x23d28: ('bitmap_draw', 'void bitmap_draw(uint img, int page, int x, int y, int a, uchar b)'),
 0x23c7c: ('bitmap_draw2', ''),
 0x23ba4: ('bitmap_blit', ''), 0x23a98: ('bitmap_blit_masked', ''),
 0x21878: ('text_draw_str', 'void text_draw_str(char *str, void *dmd_buf, uint font, uint flags, int x, int y, int color)'),
 0x21b90: ('text_draw_str_fit', 'int text_draw_str_fit(char *str, void *dmd_buf, uint font, uint flags, int x, int y, int color, int max_width)'),
 0x21660: ('text_printf_msg', 'void text_printf_msg(ushort msg_id, int page, uint font, uchar flags, int x, int y, int color, ...)'),
 0x2174c: ('text_draw_msg_fit', 'int text_draw_msg_fit(ushort msg_id, int page, uint font, uchar flags, int x, int y, int color, int max_width)'),
 0x21378: ('text_width', ''), 0x21244: ('font_height', ''),
 0x99f0: ('msg_get', 'char * msg_get(ushort msg_id)'),
 0x251f4: ('snd_play', 'void snd_play(ushort call)'),
 0x25044: ('snd_resolve_call', 'int snd_resolve_call(ushort call, int handle, uint *idx, uchar fixed)'),
 0x24ae4: ('snd_start_sample', ''), 0x25284: ('snd_play_after', ''), 0x25924: ('snd_call_sample_count', 'int snd_call_sample_count(ushort call)'),
 0x7c10: ('leff_start', ''), 0x6e50: ('event_post', ''), 0x6da8: ('event_hook_add', ''),
 0x340: ('adj_get', ''), 0xafc: ('audit_get', ''), 0xc3c: ('audit_add', ''),
 0x5e20: ('coil_pulse', ''), 0x5e70: ('coil_pulse_fn', ''), 0x5fd4: ('coilgroup_pulse', ''),
 0x4f78: ('error_log', 'void error_log(int code)'), 0x4f58: ('fatal_halt', 'void fatal_halt(int code)'),
 0xba94: ('random_below', 'uint random_below(uint n)'),
 0x2fd80: ('memset', ''), 0x2fd48: ('memcpy', ''), 0x2fd08: ('memcmp', ''), 0x2fef0: ('vsprintf', ''), 0x2fe4c: ('strlen', ''),
 0x2fe30: ('strcpy', ''), 0x2fe00: ('strcmp', ''), 0x2fa24: ('atoi', ''), 0x2b4dc: ('malloc', ''),
}
tsig = {}
for l in open(tsigs):
    if l.strip() and not l.startswith('#'):
        a, s = l.rstrip('\n').split('\t')[:2]; tsig[int(a, 16)] = s
names = {}; sigs = {}
rows = list(csv.DictReader(open(match), delimiter='\t'))
cnt = collections.Counter(r['target'] for r in rows)
for r in rows:
    t = int(r['target'], 16); sc = float(r['score'])
    if cnt[r['target']] > 1 or sc < 0.9 or t < 0x200: continue
    names[t] = r['name']
    s = tsig.get(int(r['ref'], 16))
    if s: sigs[t] = s
for a, (n, s) in MANUAL.items():
    names[a] = n
    if s: sigs[a] = s
    elif a in sigs and not sigs[a].split('(')[0].endswith(n): del sigs[a]
seeds = [l.split('\t')[0] for l in open(out + '/seeds.tsv')]
allseeds = set(int(x, 16) for x in seeds) | set(names)
open(out + '/seeds_named.tsv', 'w').write(''.join('%x\t%s\n' % (a, names.get(a, '')) for a in sorted(allseeds)))
open(out + '/sigs.tsv', 'w').write(''.join('%08x\t%s\n' % (a, s) for a, s in sorted(sigs.items())))
print('named', len(names), 'sigs', len(sigs))
