"""Sample directory, stream scripts and IMA ADPCM streams of tf_180 (format as AGENTS.md section 6)."""
import struct
from rom import ROM, banked
DIR = 0x120048           # file offset; 20 B per sample = 5 language script pointers (all equal in 1.80)
STEP=[7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767]
IDX=[-1,-1,-1,-1,2,4,6,8]*2
def directory():
    out=[]; n=0
    while True:
        w=struct.unpack_from('<5I',ROM,DIR+20*n)
        if not all((x>>24)==3 for x in w): break
        out.append(w); n+=1
    return out
def is_hdr(o):
    if o+8>len(ROM): return False
    c,one,d1,d2=struct.unpack_from('<IHBB',ROM,o)
    return one==1 and d1==d2 and d1 in (1,2) and 0<c<24000*900
def script_info(i, ents, ends):
    o=banked(ents[i][0]); e=ends[o]
    b=ROM[o:e]
    mask,n,len32=b[1],b[2],struct.unpack_from('<I',b,3)[0]
    streams=[]; k=0
    while True:
        k=b.find(b'\x0a\x00',k)
        if k<0 or k+6>len(b): break
        p=struct.unpack_from('<I',b,k+2)[0]; t=banked(p)
        if p>>24<4 and is_hdr(t): streams.append(t); k+=6
        else: k+=1
    return dict(off=o,mask=mask,n=n,len32=len32,streams=streams,raw=b)
def script_ends(ents):
    starts=sorted(set(banked(w[0]) for w in ents)); ends={}
    for a,b in zip(starts,starts[1:]+[len(ROM)]): ends[a]=b
    return ends
def decode(o):
    import numpy as np
    cnt,_,div,_=struct.unpack_from('<IHBB',ROM,o)
    data=ROM[o+8:o+8+(cnt+1)//2]
    out=np.zeros(cnt,np.int16); pred=0; idx=0
    for i in range(cnt):
        b=data[i>>1]; nib=(b&15) if (i&1)==0 else (b>>4)
        st=STEP[idx]; d=st>>3
        if nib&1: d+=st>>2
        if nib&2: d+=st>>1
        if nib&4: d+=st
        pred = pred-d if nib&8 else pred+d
        pred=max(-32768,min(32767,pred)); idx=max(0,min(88,idx+IDX[nib])); out[i]=pred
    return out, 24000//div, cnt
