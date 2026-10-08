"""Render frames of a tracer .dmd capture (records: f64 time + 128x32 bytes). Usage: dmdview.py CAP OUT.png [t0 t1 maxframes]"""
import sys, struct
import numpy as np
from PIL import Image
def load(p):
    b = open(p, 'rb').read(); out = []
    for o in range(0, len(b) - 4103, 4104):
        t = struct.unpack_from('<d', b, o)[0]; a = np.frombuffer(b[o + 8:o + 4104], np.uint8).reshape(32, 128); out.append((t, a))
    return out
if __name__ == '__main__':
    fr = load(sys.argv[1]); t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0; t1 = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
    n = int(sys.argv[5]) if len(sys.argv) > 5 else 24
    sel = [f for f in fr if t0 <= f[0] <= t1]; step = max(1, len(sel) // n); sel = sel[::step][:n]
    mx = max(1, max(int(a.max()) for _, a in fr))
    sheet = Image.new('L', (2 * 256 + 4, (len(sel) + 1) // 2 * 68), 40)
    for k, (t, a) in enumerate(sel):
        im = Image.fromarray((a.astype(np.float32) * 255 / mx).astype(np.uint8)).resize((256, 64), Image.NEAREST)
        sheet.paste(im, ((k % 2) * 260, (k // 2) * 68))
    sheet.save(sys.argv[2]); print(len(fr), 'frames, max', mx, [round(t, 2) for t, _ in sel])
