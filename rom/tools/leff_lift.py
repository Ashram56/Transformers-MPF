"""Decode each lamp effect (leff) of tf_180 from its code: the lamps it lights, tick by tick, its flasher
pulses, sounds and the effects it starts.

The leff table 0x040cfe00 (12-byte records: fn, flags u16, lamp group u16, coil group u16, priority u8) and
leff_start [0x00007c10]: the effect runs as task 3 (flags | 0x22, +0x28 leff id, +0x2a priority, +0x2c the
record's flags); if the record names a lamp group, the group's lamps are cleared in the override planes
0x00036394 and set in the override mask 0x000363a8 (FUN_000084cc, FUN_000086d4): they are off under the effect.

The effect's code runs as in deff_lift.py (coderun.Runner, its OS calls answered by Python for sleeping,
tasks, sound, coils, deffs, game state). The lamp library runs as ROM code: a leff draws into lamp layers it
allocates (FUN_00007200 [0x00007200], 0x28-byte records in the list at 0x00031480: two planes of 10 bytes at
+0 and +10, one bit per lamp, lamp n at bit 0x80 >> ((n - 1) & 7) of byte (n - 1) >> 3 (FUN_00007578), the
mask at +0x14, the owner task at +0x20, next at +0x24); the set / clear / toggle helpers 0x000077a0,
0x0000765c, 0x000078dc take a plane mask (bit 0 plane 0, bit 1 plane 1) and the lamp groups of table
0x040d1510 (FUN_00008664 and its siblings).

What the lamps show is lamp_compositor_tick [0x000073cc], re-done here at the end of every tick: per plane,
the rule lamps (0x00036374, blinking ones cleared on the off phase), then the override planes where the
override mask is set, then each layer in list order (`out = out & ~mask | mask & layer`). Only the lamps the
effect owns are written to the show: its group and its layers' masks. A lamp lit in both planes is "on",
in one plane only a half level (plane 1 only: the dim / blink phase of lamp_shows.py), in none "off".

Usage: TF_ROM=tf_180.bin leff_lift.py OUT_DIR [leff ...]  ->  OUT_DIR/leff_NNN.json
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import coderun  # noqa: E402
from coderun import rd32  # noqa: E402
import deff_lift  # noqa: E402
from deff_lift import S  # noqa: E402

LEFF_TABLE = 0x040cfe00
N_LEFFS = 0xb3                     # leff_start rejects 0 and ids above 0xb2
LAYERS = 0x00031480                # list head of the lamp layers (FUN_00007200 links into it)
OVR_PLANES, OVR_MASK = 0x00036394, 0x000363a8
GROUP_TABLE = 0x040d1510           # lamp groups (FUN_00008664 ...), 0-terminated lamp lists
GI_OWNER, GI_BITS = 0x000314c4, 0x000368c8


def lamp_group(m, g):
    if not g:
        return []
    p = rd32(m, GROUP_TABLE + 4 * g)
    out = []
    while len(out) < 80:
        b = bytes(m.mem_read(p + len(out), 1))[0]
        if not b:
            break
        out.append(b)
    return out


def bits(b10):
    v = int.from_bytes(b10, "big")
    return {n for n in range(1, 81) if v & (1 << (80 - n))}


class LeffRunner(deff_lift.DeffRunner):
    def __init__(self, rom_path=None, state=None):
        super().__init__(rom_path, state)
        a = self.arg
        st = self.stub

        def coil(kind, n, names):
            def f(r):
                r.op(kind, **dict(zip(names, [a(i) for i in range(n)])))
                return 0
            return f
        st(S("coil_pulse"), "coil_pulse", coil("coil", 2, ["coil", "ms"]))
        st(S("coil_pulse_fn"), "coil_pulse_fn", coil("coil_fn", 3, ["coil", "ms", "arg"]))
        st(S("coilgroup_pulse"), "coilgroup_pulse", coil("coil_group", 2, ["group", "ms"]))
        st(S("FUN_00006044"), "coilgroup_pulse_fn", coil("coil_group_fn", 3, ["group", "ms", "arg"]))
        self.on_tick = self._snapshot

    def reset(self):
        super().reset()
        self.call(S("FUN_00007144"))      # lamp layer pool: 32 records of 0x28 at 0x000363b4 (boot init)
        self.frames = []
        self.owned = set()
        self.group = []

    def _ours(self):
        return {t.struct for t in self.tasks if t.alive or t is self.main}

    def _snapshot(self, r):
        m = self.m
        ours = self._ours()
        p = [bytearray(10), bytearray(10)]
        mask_ovr = bytes(m.mem_read(OVR_MASK, 10))
        ovr = bytes(m.mem_read(OVR_PLANES, 20))
        for k in range(2):
            for i in range(10):
                p[k][i] = (p[k][i] & ~mask_ovr[i] | ovr[10 * k + i] & mask_ovr[i]) & 0xff
        lay = rd32(m, LAYERS)
        owned = set(self.group)
        guard = 0
        while lay and guard < 64:
            rec = bytes(m.mem_read(lay, 0x28))
            if struct.unpack_from("<I", rec, 0x20)[0] in ours:
                msk = rec[0x14:0x1e]
                owned |= bits(msk)
                for k in range(2):
                    for i in range(10):
                        p[k][i] = (p[k][i] & ~msk[i] | msk[i] & rec[10 * k + i]) & 0xff
            lay = struct.unpack_from("<I", rec, 0x24)[0]
            guard += 1
        b0, b1 = bits(p[0]), bits(p[1])
        state = {n: (n in b0) + (n in b1) * 2 for n in owned}
        gi = None
        if rd32(m, GI_OWNER) in ours:
            gi = bytes(m.mem_read(GI_BITS, 1))[0] & 1
        self.owned |= owned
        if not self.frames or self.frames[-1][1] != state or self.frames[-1][2] != gi:
            self.frames.append((self.now - 1 if self.now else 0, state, gi))


# Leffs that blink the lamps of what is lit in a game word (a bit per entry of their table): run with every bit
# set, the show is "all lit"; the game lights the entries that are lit (the table and the word are the inputs).
STATE_RAM = {
    46: [(0x00035300, 0xffffffff)],    # table 0x040c729c, 7 entries [0x010285e8]
    54: [(0x00035378, 0xffffffff)],    # table 0x040c7400, 7 entries [0x0102a72c]
    62: [(0x00034da8, 0xffffffff)],    # table 0x040c63e4, 7 entries [0x0100cf28]
    70: [(0x00034e1c, 0xffffffff)],    # table 0x040c65dc, 8 entries [0x0100ee54]
    104: [(0x02111ecc, 0xffffffff)],   # player 1's word, table 0x040c6e08, first lit of 8 [0x01023150]
}


def leff_table(m):
    out = {}
    for i in range(1, N_LEFFS):
        fn, flags, grp, cgrp, pr = struct.unpack_from("<IHHHH", bytes(m.mem_read(LEFF_TABLE + 12 * i, 12)))
        out[i] = {"fn": fn, "flags": flags, "group": grp, "coil_group": cgrp, "priority": pr & 0xff}
    return out


def lift(r, leff, info, max_ticks=9000):
    def setup(rr):
        for adr, val in STATE_RAM.get(leff, []):
            rr.m.mem_write(adr, struct.pack("<I", val))
        if info["group"]:
            rr.group = lamp_group(rr.m, info["group"])
            planes = bytearray(rr.m.mem_read(OVR_PLANES, 20))
            mask = bytearray(rr.m.mem_read(OVR_MASK, 10))
            for n in rr.group:
                i, b = (n - 1) >> 3, 0x80 >> ((n - 1) & 7)
                planes[i] &= ~b & 0xff
                planes[10 + i] &= ~b & 0xff
                mask[i] |= b
            rr.m.mem_write(OVR_PLANES, bytes(planes))
            rr.m.mem_write(OVR_MASK, bytes(mask))
    r.state.setdefault("rng", 0)
    ops = r.run(info["fn"], setup=lambda rr: setup(rr), max_ticks=max_ticks, main_tid=3,
                main_flags=0x22 | (0 if info["flags"] & 4 else (0x100 if info["flags"] & 1 else 0x2000)),
                init_main=lambda rr, t: rr.m.mem_write(t.struct + 0x28, struct.pack(
                    "<HBxH", leff, info["priority"], info["flags"])))
    m = r.m
    r._snapshot(r)
    return {"leff": leff, "fn": "0x%08x" % info["fn"], "flags": info["flags"], "group": info["group"],
            "group_lamps": r.group, "coil_group": info["coil_group"], "priority": info["priority"],
            "end_tick": r.ended_tick, "ran_ticks": r.now, "detached": r.detached,
            "lamps": sorted(r.owned), "frames": [{"t": t, "lamps": {str(k): v for k, v in sorted(s.items())}, "gi": g}
                                                 for t, s, g in r.frames],
            "ops": [o for o in ops if o["op"] not in ("sleep",)], "reads": r.reads,
            "state_ram": ["0x%08x = 0x%08x" % kv for kv in STATE_RAM.get(leff, [])]}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    deff_lift.work_pages()
    r = LeffRunner()
    table = leff_table(r.m)
    ids = [int(x) for x in sys.argv[2:]] or sorted(table)
    for i in ids:
        info = table[i]
        if not info["fn"]:
            continue
        try:
            res = lift(r, i, info)
        except Exception as e:      # noqa: BLE001
            res = {"leff": i, "fn": "0x%08x" % info["fn"], "error": str(e)}
        with open(os.path.join(out, "leff_%03d.json" % i), "w") as f:
            json.dump(res, f, indent=0)
        print(i, res.get("error") or "end %s frames %d lamps %d" % (res["end_tick"], len(res["frames"]),
                                                                     len(res["lamps"])))


if __name__ == "__main__":
    main()
