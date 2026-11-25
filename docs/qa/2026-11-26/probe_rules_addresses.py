"""QA 2026-11-26 (scope R): every ROM address cited in game/ (Python and GDScript) against the tf_180 decompile.

Read-only. For each distinct address (0x0XXXXXXX, bracketed or not, and FUN_/DAT_/LAB_ names) it says where it
lands in rom/code/tf_decompiled.c: a function head (with its name from function_names.csv), inside a function
(name + offset), a ROM table / data symbol or RAM symbol named in the decompile, or nowhere; and whether it is a
function head of the Tron 1.74 decompile (TRON env var, default ../ashram56/tron-rom/code/tron_game_decompiled_v2.c)
but not of tf_180 (a Tron-derived citation). Prints CSV: address,class,tf_function,tron_head,files(lines),context.

Usage: .venv/bin/python docs/qa/2026-11-26/probe_rules_addresses.py > OUT.csv
"""
import bisect
import collections
import csv
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEC = os.path.join(ROOT, "rom", "code", "tf_decompiled.c")
TRON = os.environ.get("TRON", os.path.join(ROOT, "..", "ashram56", "tron-rom", "code", "tron_game_decompiled_v2.c"))
SKIP = ("game/pup_runtime", "game/pup/", "game/addons")
# 0x0XXXXXXX, the short game-code form 0x10XXXXX (= 0x010XXXXX, as in switches.py), and Ghidra names
PAT = re.compile(r"(?:\b0x(0[0-9a-fA-F]{7})\b|\b0x(10[0-3][0-9a-fA-F]{4})\b|\b(?:FUN|DAT|LAB|PTR_FUN|PTR)_([0-9a-fA-F]{8})\b)")


def heads(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    h = {int(m.group(1), 16): m.group(2) for m in re.finditer(r"^// ==== ([0-9a-f]{8}) (\S+)", src, re.M)}
    return src, h


def main():
    src, h = heads(DEC)
    starts = sorted(h)
    tron_heads = set()
    if os.path.exists(TRON):
        tron_heads = set(heads(TRON)[1])
    syms = set(int(x, 16) for x in re.findall(r"(?:DAT|LAB|PTR_FUN|PTR|PTR_DAT|FUN)_([0-9a-f]{8})", src))
    syms |= set(int(x, 16) for x in re.findall(r"0x([0-9a-f]{7,8})\b", src))
    cites = collections.defaultdict(list)
    for dp, dn, fn in os.walk(os.path.join(ROOT, "game")):
        rel = os.path.relpath(dp, ROOT) + "/"
        if any(rel.startswith(s) for s in SKIP):
            continue
        for f in fn:
            if not f.endswith((".py", ".gd")):
                continue
            p = os.path.join(dp, f)
            for i, ln in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                for m in PAT.finditer(ln):
                    a = int(m.group(1) or m.group(2) or m.group(3), 16)
                    cites[a].append((os.path.relpath(p, ROOT), i, ln.strip()[:160]))
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["address", "class", "tf_function", "tron_head", "where", "context"])
    for a in sorted(cites):
        cls, fn = "", ""
        if a in h:
            cls, fn = "function", h[a]
        elif 0x01000000 <= a < 0x01100000 or a < 0x00036000:
            i = bisect.bisect_right(starts, a) - 1
            if i >= 0 and a in syms:
                cls, fn = "symbol_in_code", "%s+0x%x" % (h[starts[i]], a - starts[i])
            elif i >= 0:
                cls, fn = "inside", "%s+0x%x" % (h[starts[i]], a - starts[i])
            if a < 0x00036000 and a >= 0x00030000 and a in syms:
                cls, fn = "data", "DAT"
        elif 0x04000000 <= a < 0x05000000:
            cls = "rom_table" if a in syms else "rom_table_not_in_decompile"
        elif 0x02000000 <= a < 0x03000000:
            cls = "ram" if a in syms else "ram_not_in_decompile"
        else:
            cls = "other"
        where = " ".join("%s:%d" % (p, i) for p, i, _ in cites[a][:4]) + (" +%d" % (len(cites[a]) - 4)
                                                                          if len(cites[a]) > 4 else "")
        w.writerow(["0x%08x" % a, cls, fn, "yes" if a in tron_heads and a not in h else "", where, cites[a][0][2]])


if __name__ == "__main__":
    main()
