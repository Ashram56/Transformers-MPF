"""DMD image table of tf_180. The OS resource block (file 0x30e78: images end, font count, font table,
image count, image table, sample count, sample directory) gives 10,212 images at file 0x123694: u32 banked
pointers, indexed by image number (the number the code draws). Each image's header carries its own id
(rid), which is not the table index; delta frames apply on top of the image whose rid is one less. 13-byte header u16 rid, u16 group, u32 flags, s16 w, s16 h, u8 format
(AGENTS.md section 7). Flags: 1 delta, 2 last frame of an animation, 4 cache."""
import struct
import numpy as np
from rom import ROM, banked
TABLE = 0x123694
NMAX = 10212
def valid_ids():
    out=[]
    for i in range(NMAX):
        p=struct.unpack_from('<I',ROM,TABLE+4*i)[0]
        if p==0xffffffff: continue
        o=banked(p)
        if o+13<len(ROM): out.append(i)
    return out
def header(i):
    o=banked(struct.unpack_from('<I',ROM,TABLE+4*i)[0])
    rid,grp,flags,w,h,t=struct.unpack_from('<HHIhhB',ROM,o)
    return dict(rid=rid,group=grp,flags=flags,w=w,h=h,format=t,addr=o)
def _rle(p,out,col,w,h):
    k=0; n=w*h
    def put(v):
        nonlocal k
        if k<n:
            if col: out[(k%h)*w+k//h]=v
            else: out[k]=v
        k+=1
    b=ROM[p]; p+=1
    while b:
        c=b>>2; op=b&3
        if op==1:
            for _ in range(c): put(0)
        elif op==2:
            for _ in range(c): put(15)
        elif op==0:
            for _ in range(c): put(ROM[p]); p+=1
        else:
            v=ROM[p]; p+=1
            for _ in range(c): put(v)
        b=ROM[p]; p+=1
    return k
def _delta(p,out,col,w,h):
    k=0; n=w*h
    b=ROM[p]; p+=1
    while b:
        c=b-256 if b>127 else b
        if c<0: k+=-c
        else:
            for _ in range(c):
                if k<n:
                    if col: out[(k%h)*w+k//h]=ROM[p]
                    else: out[k]=ROM[p]
                p+=1; k+=1
        b=ROM[p]; p+=1
    return k
def decode(i, prev=None):
    H=header(i); w,h,t=H['w'],H['h'],H['format']; a=H['addr']+13; n=w*h
    out=bytearray(prev) if t in (3,9) and prev is not None and len(prev)==n else bytearray(b'\xff'*n if t in (3,9) else n)
    if t==0: out[:]=ROM[a:a+n]
    elif t==1: _rle(a,out,True,w,h)
    elif t==7: _rle(a,out,False,w,h)
    elif t==12:
        for j in range(n):
            bt=ROM[a+j//2]; out[j]=(bt&0xf) if j%2==0 else (bt>>4)
    elif t==3: _delta(a,out,True,w,h)
    elif t==9: _delta(a,out,False,w,h)
    else: raise ValueError('format %d'%t)
    return np.frombuffer(bytes(out),dtype=np.uint8).reshape(h,w)
