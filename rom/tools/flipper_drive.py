"""The flipper drive of tf_180, read from the code and run as ROM code.

The flippers are driven by the CPU, in the 1 ms pass of the IO interrupt io_isr [0x000114b0] (every 4th
250 us interrupt, counter 0x0003156c), from one 0x40-byte driver record per flipper (array 0x00031458, count
0x0003145c). The records are built by coil_init_6194 [0x00006194] from the table 0x00030b9c ->
0x040cf590 (2 entries of 12 bytes), called by the event 0x27 hook 0x01005fb8 (start-up). Entry bytes:

  +0 id   +1 button switch   +2 alternate switch (used when +1 is disabled)   +3 coil   +5 EOS switch
  +6 pulse (ms)   +7 EOS cut (ms)   +8 hold on (ms)   +9 hold off (ms)

The 1 ms pass, per record (decompile lines of io_isr after `DAT_0003156c = 4`):
  - hold phase: +0x3b counts the on time (+8) down, then +0x3d the off time (+9); the first record starts at
    phase 0, the second at udiv(i * (on + off), n) = 6 ms, so the two holds do not fire together;
  - only while the record is enabled (+0x3e): the button closed for +0x24 passes (its switch record +0x1b)
    starts a pulse of +6 ms (+0x28) and samples the EOS switch (+0x30); while the pulse runs the coil is on;
    if the EOS was closed at the start and opens (debounced +0x37) the pulse is cut to 1 ms when at most +7 ms
    are left, and marked (+0x38); a marked pulse that ends with the EOS closed again (debounced +0x35) pulses
    once more, at most 2 times (+0x39 = 2); after the pulse the coil follows the hold phase; the button open
    for +0x26 passes (switch record +0x1c) turns the coil off.
  - enable: post_event_28_65c4 [0x000065c4] for each record, from hooks_28_all_6668 [0x00006668] (tilt
    [0x0001db40], and the game state changes): off (coil_slot_64ac [0x000064ac]) while gf_state & 0x214 (tilt,
    end of ball, attract) or in the service menu, on (coil_slot_6540 [0x00006540]) in play and in service item
    0x15; an event 0x28 hook may refuse.

This tool reads the table and runs io_isr itself (Unicorn, the ROM image only) on a started game with the
button and EOS switches set in the dedicated switch register (pointer 0x000314c8, read inverted by io_isr
[0x00011c30]), and prints the coil output (0x00035b00 + record +8, mask +0xc) per ms.

Usage: TF_ROM=tf_180.bin python3 flipper_drive.py [OUT.json]   (default rom_data/io/flipper_drive.json)
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, foff, u32  # noqa: E402

TABLE_PTR = 0x00030b9c          # {entries, count, stride}, the argument of coil_init_6194 at 0x01005fb8
FIELDS = ("id", "switch", "switch_alt", "coil", "unused_4", "eos_switch", "pulse_ms", "eos_cut_ms",
          "hold_on_ms", "hold_off_ms")
HERE = os.path.dirname(os.path.abspath(__file__))


def table():
    p, n, stride = struct.unpack_from("<III", ROM, foff(TABLE_PTR))
    out = []
    for i in range(n):
        b = ROM[foff(p) + i * stride: foff(p) + i * stride + stride]
        e = dict(zip(FIELDS, b[:10]))
        e["entry"] = "0x%08x" % (p + i * stride)
        out.append(e)
    return out


def run(cases):
    """Each case: a list of (ms, switch, closed). Returns the ms where the left flipper coil turns on / off."""
    import switch_lift
    import deff_lift
    from switch_lift import rd32
    deff_lift.work_pages()
    res = {}
    for name, events in cases.items():
        r = switch_lift.SwitchRunner()
        switch_lift.start_game(r)
        m = r.m
        base = rd32(m, 0x00031458)
        hw = rd32(m, 0x000314c8)                  # the dedicated switch register (switches 129..144)
        m.mem_write(hw, struct.pack("<H", 0xffff))
        m.mem_write(0x02800000, struct.pack("<I", 0x02800100))   # io_isr's argument: its timer's status

        def switch(sw, closed):
            w = struct.unpack("<H", bytes(m.mem_read(hw, 2)))[0]
            bit = 1 << ((sw - 1) & 15)
            m.mem_write(hw, struct.pack("<H", w & ~bit if closed else w | bit))

        rec = bytes(m.mem_read(base, 0x40))
        idx, mask = struct.unpack_from("<I", rec, 8)[0], rec[0xc]
        edges, prev = [], 0
        for ms in range(260):
            for t, sw, closed in events:
                if t == ms:
                    switch(sw, closed)
            for _ in range(4):                    # four 250 us interrupts: one 1 ms pass
                r.call(0x000114b0, 0x02800000)
            on = int(bool(m.mem_read(0x00035b00 + idx, 1)[0] & mask))
            if on != prev:
                edges.append([ms, on])
                prev = on
        res[name] = edges
    return res


CASES = {
    "press_5_release_205": [(5, 137, True), (205, 137, False)],
    "eos_closed_at_press_opens_20_closes_30": [(0, 138, True), (5, 137, True), (20, 138, False),
                                               (30, 138, True), (205, 137, False), (205, 138, False)],
    "eos_falls_after_the_pulse_60_75": [(5, 137, True), (25, 138, True), (60, 138, False), (75, 138, True),
                                        (205, 137, False), (205, 138, False)],
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "rom_data", "io", "flipper_drive.json")
    t = table()
    runs = run(CASES)
    doc = {"source": "code: table 0x040cf590 via 0x00030b9c, coil_init_6194 [0x00006194] from the event 0x27 hook "
                     "0x01005fb8; driven each 1 ms by io_isr [0x000114b0]; runs: io_isr run as ROM code",
           "entries": t, "runs_left_flipper_coil_edges_ms": runs}
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    for e in t:
        print(e)
    for k, v in runs.items():
        print(k, v[:8], "...", v[-2:])


if __name__ == "__main__":
    main()
