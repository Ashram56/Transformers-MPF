"""Decode every DMD image and split the image list into animations (flag 2 = last frame).
Usage: python3 export_images.py OUTDIR   (writes media/rom_images_all.zip, media/dmd_library/, images.csv)"""
import sys, os, io, json, csv, zipfile
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from images import *
OUT = sys.argv[1]
FRAME_MS = 50          # placeholder frame time until per-effect captures give the ROM's timing
ids = valid_ids(); H = {i: header(i) for i in ids}; r2i = {H[i]['rid']: i for i in ids}
frames = {}
def get(i):
    if i in frames: return frames[i]
    h = H[i]; prev = None
    if h['format'] in (3, 9): prev = get(r2i[h['rid'] - 1]).tobytes()
    frames[i] = decode(i, prev); return frames[i]
sys.setrecursionlimit(20000)
def rgba(a):
    g = np.where(a == 255, 0, np.minimum(a, 15) * 17).astype(np.uint8)
    al = np.where(a == 255, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([g, g, g, al]), 'RGBA')
def png(a):
    b = io.BytesIO(); rgba(a).save(b, 'PNG', optimize=True); return b.getvalue()
os.makedirs(os.path.join(OUT, 'media'), exist_ok=True)
rows = []
with zipfile.ZipFile(os.path.join(OUT, 'media', 'rom_images_all.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    for i in ids:
        a = get(i); z.writestr('img_%05d.png' % i, png(a))
        h = H[i]; rows.append(dict(image=i, rid=h['rid'], group=h['group'], flags=h['flags'], w=h['w'], h=h['h'],
                                    format=h['format'], file_offset='0x%x' % h['addr']))
with open(os.path.join(OUT, 'images.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
# animations: runs of consecutive images ending at a flag-2 image, all full height (32), 2+ frames
anims = []; cur = []
for i in ids:
    cur.append(i)
    if H[i]['flags'] & 2: anims.append(cur); cur = []
lib = []
def gif(frs, path, ms):
    ims = [rgba(a).convert('RGBA') for a in frs]
    pal = [Image.fromarray(np.dstack([np.where(np.array(im)[:, :, 3] == 0, 255, np.array(im)[:, :, 0])]*1)[:, :, 0], 'L') for im in ims]
    # grey GIF, 255 = transparent
    ps = []
    for im in ims:
        a = np.array(im); g = (a[:, :, 0] // 17).astype(np.uint8); g[a[:, :, 3] == 0] = 16
        p = Image.fromarray(g, 'P'); p.putpalette(sum([[v * 17] * 3 for v in range(16)], []) + [0, 0, 0] * 240); ps.append(p)
    ps[0].save(path, save_all=True, append_images=ps[1:], duration=ms, loop=0, transparency=16, disposal=2)
n = 0
for a in anims:
    big = [i for i in a if H[i]['h'] == 32 and H[i]['w'] >= 64]
    if len(a) < 2 or len(big) != len(a): continue
    name = 'anim_%03d_img%05d' % (n, a[0]); d = os.path.join(OUT, 'media', 'dmd_library', name); os.makedirs(os.path.join(d, 'frames'), exist_ok=True)
    frs = [get(i) for i in a]
    for k, f in enumerate(frs): open(os.path.join(d, 'frames', '%03d.png' % k), 'wb').write(png(f))
    gif(frs, os.path.join(d, 'animation.gif'), FRAME_MS)
    w = H[a[0]]['w']; x = 41 if w == 87 else 128 - w if w < 128 else 0
    canv = []
    for f in frs:
        c = np.full((32, 128), 255, np.uint8); fw = min(f.shape[1], 128 - x); c[:, x:x + fw] = f[:, :fw]; canv.append(c)
    gif(canv, os.path.join(d, 'animation_128x32.gif'), FRAME_MS)
    lib.append(dict(name=name, first_image=a[0], last_image=a[-1], frames=len(a), w=w, h=32, x_on_128=x,
                    x_tag='inferred (87-wide animations drawn at x=41 as on Tron; check against deff captures)',
                    frame_ms=FRAME_MS, frame_ms_tag='placeholder'))
    n += 1
json.dump(lib, open(os.path.join(OUT, 'media', 'dmd_library', 'index.json'), 'w'), indent=1)
print('images', len(ids), 'animations', len(anims), 'library', n)
