"""The evaluation order of the leff rule list (list 3) from the ROM's code (QA R-F9).

rule_record_init_a_17748 [0x00017748] registers a leff rule through rule_record_new_17500 [0x00017500], which
inserts it with rule_list_insert_by_prio_17580 [0x00017580]: before the first record whose priority byte (+7) is
not above its own. Every leff rule passes priority 0, so each new record goes to the head of the list: the list
runs in the reverse order of registration. The rules are registered by the game modules' static constructors
(register_rules_* (1, 0xffff)), which the start-up walker [0x0002c0c8] runs from the last entry of the
constructor table 0x00033e3c down to the first; the table lists the game modules in address order. So the list
runs the modules in ascending address order and, inside a module, its registrations last first.

Writes rom/rom_data/rules/leff_rule_order.json: {"list": 3, "order": [leff ids in evaluation order], "sites":
{leff: call site}}. Needs TF_ROM.
"""
import json
import os
import struct

import rom

INIT_A = 0x00017748
CTORS = 0x00033e3c          # -1, then the constructor stubs, 0
OUT = os.path.join(os.path.dirname(__file__), "..", "rom_data", "rules", "leff_rule_order.json")


def ctor_targets():
    """The register functions the constructor stubs branch to (mov r1, #0xff00; add; mov r0, #1; b target)."""
    out = []
    o = rom.foff(CTORS) + 4
    while True:
        stub = struct.unpack_from("<I", rom.ROM, o)[0]
        if stub in (0, 0xffffffff):
            break
        for ins in rom.disasm(stub, 0x10):
            if ins.mnemonic == "b":
                out.append(int(ins.op_str.lstrip("#"), 16))
                break
        o += 4
    return out


def registrations():
    """(call site, list, leff) of every call of rule_record_init_a_17748: r1 the list, r3 the leff id."""
    out = []
    for site in rom.bl_callers(INIT_A):
        regs = {}
        for ins in rom.disasm(site - 0x30, 0x30):     # mov rN, #imm / add rN, rN, #imm / mov rN, rM
            ops = [x.strip() for x in ins.op_str.split(",")]
            if ins.mnemonic == "mov" and ops[1].startswith("#"):
                regs[ops[0]] = int(ops[1][1:], 0)
            elif ins.mnemonic == "mov" and ops[1] in regs:
                regs[ops[0]] = regs[ops[1]]
            elif ins.mnemonic == "add" and len(ops) == 3 and ops[1] in regs and ops[2].startswith("#"):
                regs[ops[0]] = regs[ops[1]] + int(ops[2][1:], 0)
            elif ops and ops[0] in regs and ins.mnemonic in ("ldr", "add", "sub", "mov"):
                regs.pop(ops[0])
        if "r1" in regs and "r3" in regs:
            out.append((site, regs["r1"], regs["r3"]))
        else:
            raise SystemExit("unparsed call site 0x{:08x}".format(site))
    return out


def main():
    modules = sorted(set(ctor_targets()))
    def module_of(site):
        return max(m for m in modules if m <= site)
    regs = [r for r in registrations() if r[1] == 3]
    # modules ascending, then the registrations of a module last first
    regs.sort(key=lambda r: (module_of(r[0]), -r[0]))
    doc = {"list": 3, "source": "rom/tools/rule_order.py",
           "order": [leff for _, _, leff in regs],
           "sites": {str(leff): "0x{:08x}".format(site) for site, _, leff in regs}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(len(regs), "leff rules:", doc["order"])


if __name__ == "__main__":
    main()
