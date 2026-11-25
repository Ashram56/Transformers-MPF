"""Which arguments each deff gets, read from its callers in the decompile.

A deff's arguments are words its caller stores into the task that `deff_start` [0x000209b4] returns
(`iVar = deff_start(id, ..); *(T *)(iVar + 0x30) = value;`); the deff reads them at task_current + offset.
For each call site: the deff id, the function and address, each stored offset with its C type and value
expression (a constant when the caller passes one). Usage: deff_args.py OUT_CSV"""
import csv
import re
import sys

import os
DECOMP = os.path.join(os.path.dirname(__file__), "..", "code", "tf_decompiled.c")


def main():
    src = open(DECOMP, encoding="utf-8").read()
    rows = []
    for fm in re.finditer(r"^// ==== ([0-9a-f]{8}) (\S+)\n(.*?)(?=^// ==== |\Z)", src, re.M | re.S):
        addr, name, body = fm.groups()
        lines = body.split("\n")
        for i, line in enumerate(lines):
            m = re.search(r"(\w+) = deff_start\((0x[0-9a-f]+|\d+),", line)
            if not m:
                if re.search(r"deff_start\((0x[0-9a-f]+|\d+),", line):
                    d = re.search(r"deff_start\((0x[0-9a-f]+|\d+),", line).group(1)
                    rows.append([int(d, 0), "0x" + addr, name, "", "", "", ""])
                continue
            var, d = m.group(1), int(m.group(2), 0)
            stores = []
            for nxt in lines[i + 1:i + 25]:
                for sm in re.finditer(r"\*\((\w+) \*\)\(" + var + r" \+ (0x[0-9a-f]+)\) = ([^;]+);", nxt):
                    stores.append(sm.groups())
                if re.search(r"\b" + var + r" = ", nxt) and "deff_start" not in nxt:
                    break
            if not stores:
                rows.append([d, "0x" + addr, name, var, "", "", ""])
            for t, off, expr in stores:
                rows.append([d, "0x" + addr, name, var, off, t, expr.strip()])
    rows.sort(key=lambda r: (r[0], r[1], r[4]))
    with open(sys.argv[1], "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["deff", "caller", "caller_name", "var", "offset", "type", "value"])
        w.writerows(rows)
    print(len(rows), "rows,", len({r[0] for r in rows}), "deffs started by the code")


if __name__ == "__main__":
    main()
