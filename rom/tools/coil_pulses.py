"""The pulse times the code gives each coil, from the code only: the MPF default pulse of coils.csv.

Sources, all code:
- every call of the pulse routines with a constant coil and time (backward scan of r0 / r1 before the BL):
  coil_pulse [0x00005e20] (coil, ms), coil_pulse_fn [0x00005e70] (coil, ms, 32-bit on/off pattern),
  FUN_00002078 [0x00002078] and FUN_00002160 [0x00002160] (the pulse routines under them), FUN_00002010 [0x00002010],
  coilgroup_pulse [0x00005fd4] / FUN_00006044 [0x00006044] (a coil group of table 0x040cf65c, ms);
- the effects' pulses as their code runs them (rom/rom_data/io/leff_ops/, leff_lift.py);
- the OS pop bumper and slingshot tables read by the 1 ms pass of the IO interrupt [0x000114b0] (every 4 interrupts
  of 250 us): pops 0x040ddfb0 (12-byte records 1..3: u16 on ms, u16 dead ms, u8 debounce, switch +6, coil +7; set up
  by FUN_00002c3c), slings 0x040ddfe0 (8-byte records 1..2: u16 on ms, u16 dead ms, switch +4, coil +5; FUN_00003148):
  the coil is on for `on` ms, then held off `dead` ms and until the switch opens;
- on / off devices (FUN_000024e4 on, FUN_0000246c off): enabled for a time, never pulsed.

Usage: TF_ROM=tf_180.bin coil_pulses.py   (rewrites the mpf_* columns of rom/rom_data/io/coils.csv and writes
rom/rom_data/io/coil_pulses.csv, one row per call site)
"""
import collections
import csv
import glob
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, foff, u32, disasm, bl_callers  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
IO = os.path.join(HERE, "..", "rom_data", "io")
COIL_GROUPS = 0x040cf65c
POPS, SLINGS = 0x040ddfb0, 0x040ddfe0
ROUTINES = {0x5e20: "coil_pulse", 0x5e70: "coil_pulse_fn", 0x2078: "FUN_00002078", 0x2160: "FUN_00002160",
            0x2010: "FUN_00002010", 0x5fd4: "coilgroup_pulse", 0x6044: "FUN_00006044"}
GROUPS = ("coilgroup_pulse", "FUN_00006044")
ON_OFF = {0x24e4: "on", 0x246c: "off"}


def reg_const(site, reg):
    """Constant in reg before the BL at site, or None when it is computed."""
    ins = []
    for a in range(site - 64, site, 4):      # word by word: capstone stops at the first word it cannot decode
        ins += disasm(a, size=4)
    add = 0
    for i in reversed(ins):
        ops, mn = i.op_str, i.mnemonic
        if i.mnemonic in ("bl", "b", "bx", "pop", "ldm") or mn.startswith("ldm") and reg in ops:
            return None
        if not ops.startswith(reg + ","):
            continue
        if mn == "mov" and "#" in ops:
            return int(ops.split("#")[1], 0) + add
        if mn == "mov" and ops.split(", ")[1] in ("r4", "r5", "r6", "r7", "r8"):
            v = reg_const(i.address + 4, ops.split(", ")[1]) if i.address > site - 60 else None
            return None if v is None else v + add
        if mn == "add" and ops.startswith("%s, %s, #" % (reg, reg)):
            add += int(ops.split("#")[1], 0)
            continue
        if mn == "ldr" and "[pc, #" in ops:
            return u32(i.address + 8 + int(ops.split("#")[1].rstrip("]"), 0)) + add
        return None
    return None


def _shaker(c):
    lv = [struct.unpack_from("<H", ROM, foff(SHAKER + 4 * i))[0] for i in range(1, 4)]
    return "", "", ("motor: shaker run %s ms by level 1-3 (FUN_0103070c [0x0103070c], FUN_00002078(8, ms), table "
                    "0x040c7620), not pulsed" % "/".join(map(str, lv)))


def _kept(ms, hold, why):
    return lambda c: (ms, hold, "code open: %s; %s ms%s kept from the emulator measurement until the owner decides "
                      "(docs/pinmame_waivers.md, open)" % (why, ms, " and hold %s" % hold if hold else ""))


SHAKER = 0x040c7620
SPECIAL = {
    5: lambda c: ("", "", "motor/gate: enabled for a time, not pulsed (code open: its drive routine is not found yet)"),
    8: _shaker,
    15: _kept("40.5", "0.083", "no flipper drive found in the CPU code (no flipper device: the OS device list "
              "0x0003143c, table 0x040ddfa4, has count 1 at 0x040c4604, so none; the FPGA is not decoded)"),
    16: _kept("40.6", "0.084", "as the left flipper"),
    24: _kept("81", "", "the time comes from the device record +0xc of FUN_0102c074 [0x0102c074] (method table "
              "0x00033bc0), a run-time record not decoded yet"),
    30: lambda c: ("", "", "motor: enabled for a time, not pulsed (code open: its drive routine is not found yet)"),
}


def coil_group(g):
    p = u32(COIL_GROUPS + 4 * g)
    o, out = foff(p), []
    while o is not None and ROM[o] and len(out) < 40:
        out.append(ROM[o])
        o += 1
    return out


def main():
    rows = []
    for adr, name in ROUTINES.items():
        for site in bl_callers(adr):
            c, ms = reg_const(site, "r0"), reg_const(site, "r1")
            if c is None or ms is None:
                continue
            coils = coil_group(c) if name in GROUPS else [c & 0xff]
            for k in coils:
                rows.append(dict(coil=k, ms=ms & 0xffff, how=name + (" group %d" % c if name in GROUPS else ""),
                                 site="0x%08x" % site, source="code: constant arguments at the call"))
    for adr, name in ON_OFF.items():
        for site in bl_callers(adr):
            c = reg_const(site, "r0")
            if c is not None:
                rows.append(dict(coil=c & 0xff, ms="", how="FUN_%08x (%s)" % (adr, name), site="0x%08x" % site,
                                 source="code: enabled / disabled, not pulsed"))
    seen = set()          # one row per (coil, time, call site): a looping leff pulses from the same site again
    for p in sorted(glob.glob(os.path.join(IO, "leff_ops", "leff_*.json"))):
        doc = json.load(open(p))
        for o in doc["ops"]:
            if o["op"] in ("coil", "coil_fn"):
                coils = [o["coil"] & 0xff]
            elif o["op"] in ("coil_group", "coil_group_fn"):
                coils = coil_group(o["group"] & 0xffff)
            else:
                continue
            for k in coils:
                key = (k, o["ms"] & 0xffff, o["at"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(dict(coil=k, ms=o["ms"] & 0xffff, how="leff %d %s" % (doc["leff"], o["op"]), site=o["at"],
                                 source="code: the leff's code run (leff_lift.py)"))
    for i in range(1, 4):
        on, dead, deb, _, sw, coil = struct.unpack_from("<HHBBBB", ROM, foff(POPS + 12 * i))
        rows.append(dict(coil=coil, ms=on, how="pop bumper %d: switch %d, dead %d ms, debounce %d" % (i, sw, dead, deb),
                         site="0x%08x" % (POPS + 12 * i), source="code: OS pop table, IO interrupt 0x000114b0"))
    for i in range(1, 3):
        on, dead, sw, coil = struct.unpack_from("<HHBB", ROM, foff(SLINGS + 8 * i))
        rows.append(dict(coil=coil, ms=on, how="slingshot %d: switch %d, dead %d ms" % (i, sw, dead),
                         site="0x%08x" % (SLINGS + 8 * i), source="code: OS slingshot table, IO interrupt 0x000114b0"))
    rows.sort(key=lambda r: (r["coil"], str(r["ms"]), r["site"]))
    with open(os.path.join(IO, "coil_pulses.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["coil", "ms", "how", "site", "source"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["coil"]].append(r)
    path = os.path.join(IO, "coils.csv")
    coils = list(csv.DictReader(open(path)))
    for c in coils:
        n = int(c["coil"])
        rs = by.get(n, [])
        timed = collections.Counter(r["ms"] for r in rs if r["ms"] != "")
        os_dev = [r for r in rs if r["source"].startswith("code: OS")]
        onoff = [r for r in rs if r["ms"] == ""]
        hold = ""
        if os_dev:
            ms, src = os_dev[0]["ms"], "code: %s (%s)" % (os_dev[0]["how"], os_dev[0]["site"])
        elif timed:
            ms = timed.most_common(1)[0][0]
            src = "code: %d ms at %d of %d pulse sites (%s); all: %s" % (
                ms, timed[ms], sum(timed.values()), ", ".join(r["site"] for r in rs if r["ms"] == ms)[:120],
                " ".join("%sx%d" % kv for kv in sorted(timed.items())))
        elif onoff:
            ms, src = "", "code: enabled for a time, not pulsed (%s)" % ", ".join(
                "%s at %s" % (r["how"], r["site"]) for r in onoff[:4])
        elif "flipper" in c["flags_decoded"]:
            ms = c["test_pulse_ms"]
            src = ("code open: no flipper drive in the CPU code (the flipper device 0x0003143c is empty and its IO "
                   "interrupt pass only resets its counter); coil test time %s ms (descriptor %s)" % (ms, c["desc_addr"]))
        else:
            ms = c["test_pulse_ms"]
            src = "code: no pulse in the game code; coil test time of the descriptor %s" % c["desc_addr"]
        if n in SPECIAL:
            ms, hold, src = SPECIAL[n](c)
        elif "motor" in c["flags_decoded"] and not timed:
            ms = ""
        c.update(mpf_default_pulse_ms=ms, mpf_default_hold_power=hold, mpf_source=src)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, list(coils[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(coils)
    for c in coils:
        print(c["coil"], c["name"][:22], c["mpf_default_pulse_ms"], "|", c["mpf_source"][:110])


if __name__ == "__main__":
    main()
