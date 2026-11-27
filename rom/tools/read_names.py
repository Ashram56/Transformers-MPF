"""Give the structural functions left by purpose_names.py the names read from their bodies one by one.

rom/code/function_names_read.csv holds one row per function (address, name, evidence): each was read in
rom/code/tf_decompiled.c, its name says what the code does (the tables, RAM, messages, tasks and calls it uses,
named in the evidence), and ends with the address suffix (address & 0xfffff) so it stays unique. A row is
applied only to a function whose rule is still structural (uses, leaf, ram, table, wrapper, sub).

Two functions can share one old name:
  - two thunks of one routine (0x00026584 / 0x000265d8): the rows give both the same new name;
  - an OS and a game function with the same low address (task_find_in_range_b698 at 0x0000b698 and 0x0100b698, flash_word_write_checked_10cd8):
    each header gets its own name, and the calls by the old name get the lowest address's name (the calls of
    task_find_in_range_b698(0x5d, 0x7e) in 0x01006350 / 0x01006480 are the OS task search 0x0000b698; flash_word_write_checked_10cd8 has no call).
A shared name without a row for every function (score_histogram_add_1bbb0, two thunks) is left as it is.

Writes rom/code/function_names.csv (rule "read", the evidence) and renames in the decompile and in the files of
rom/, docs/ and game/tf/ that name the old names (refine_names.py's rename()).

Usage: python3 read_names.py [--dry]
"""
import csv
import os
import re
import sys

import refine_names as rn

STRUCTURAL = {"uses", "leaf", "ram", "table", "wrapper", "sub"}
READ = os.path.join(rn.ROMDIR, "code", "function_names_read.csv")


def main():
    dry = "--dry" in sys.argv
    funcs = rn.load_funcs(open(rn.DECOMP, encoding="utf-8").read())
    count = {}
    for n, _ in funcs.values():
        count[n] = count.get(n, 0) + 1
    taken = set(count)
    rows = list(csv.DictReader(open(rn.NAMES, encoding="utf-8")))
    by_addr = {int(r["address"], 16): r for r in rows}
    read = {int(h["address"], 16): h for h in csv.DictReader(open(READ, encoding="utf-8"))}
    groups = {}
    for a, (n, _) in funcs.items():
        groups.setdefault(n, []).append(a)
    ren, heads, skipped = {}, {}, []
    for a, h in sorted(read.items()):
        r = by_addr.get(a)
        if r is None or a not in funcs or r["rule"] not in STRUCTURAL:
            skipped.append((h["address"], "not structural"))
            continue
        old = funcs[a][0]
        group = sorted(groups[old])
        if len(group) > 1:
            if any(g not in read for g in group):
                skipped.append((h["address"], "shared name without a row for each"))
                continue
            heads[a] = h["name"]                # the header of each, by its address
            new = read[group[0]]["name"]        # the calls: the lowest address's name
        else:
            new = h["name"]
        if new != old and old not in ren:
            if new in taken:
                raise SystemExit("name %s taken" % new)
            ren[old] = new
            taken.add(new)
        r.update(name=h["name"], rule="read", evidence=h["evidence"])
    left = sum(1 for r in rows if r["rule"] in STRUCTURAL)
    print(len(ren), "renamed;", len(skipped), "skipped;", left, "structural left")
    for s in skipped[:20]:
        print(" skipped", *s)
    if dry:
        return
    with open(rn.NAMES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    rn.rename(ren)
    src = open(rn.DECOMP, encoding="utf-8").read()
    for a, name in heads.items():
        src = re.sub(r"^(// ==== %08x )\S+\n((?://[^\n]*\n|\n)*)(.*?)\b\S+(\()" % a,
                     lambda m: m.group(1) + name + "\n" + m.group(2) + m.group(3) + name + m.group(4),
                     src, count=1, flags=re.M | re.S)
    with open(rn.DECOMP, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)


if __name__ == "__main__":
    main()
