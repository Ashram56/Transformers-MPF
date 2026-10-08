"""tf_180 table registry. The OS keeps a table of tables at file 0x30b00-0x30d10: triples
(u32 address, u32 count, u32 record size). Names below are what each table was identified as."""
import struct
from rom import ROM, u32, u16, cstr, foff
REGISTRY = 0x30b00
TABLES = {
    'adjustments': (0x040cb20c, 99, 32), 'audits': (0x040cd5a4, 167, 16), 'coils': (0x040ce3d4, 36, 28),
    'deffs': (0x040ce7c4, 156, 8), 'leffs': (0x040cfe00, 179, 12), 'lamps': (0x040d0dfc, 81, 12),
    'lamp_groups': (0x040d1510, 148, 4), 'messages': (0x040dc0f0, 1794, 4), 'sound_calls': (0x040dee08, 705, 20),
    'switches': (0x040e2c20, 65, 32), 'dedicated_switches': (0x040e3740, 32, 32),
}
def registry():
    out=[]; o=REGISTRY
    while o<0x30e60:
        a,n,s=struct.unpack_from('<3I',ROM,o)
        if 0x04000000<=a<0x04800000 and n<20000 and 0<s<256: out.append((o,a,n,s)); o+=12
        else: o+=4
    return out
NMSG = 1794
def msg(i):
    if i is None or i>=NMSG: return None
    p=u32(0x040dc0f0+4*i)
    if foff(p) is None: return None
    q=u32(p)
    return cstr(q) if foff(q) is not None else None
def rec(name, i):
    a,n,s=TABLES[name]; return a+s*i
