"""The functional diagram (docs/functional_diagram.md, strict rule item 5) cites real routines.

Every 0x address in a mermaid chart is a function start in rom/code/tf_decompiled.c, a ROM table (0x04xxxxxx),
or a call site inside a game function (within 0x1000 of the function start before it): a call site the specs cite."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_diagram_addresses_exist_in_decompile():
    heads, text = set(), open(os.path.join(ROOT, "rom", "code", "tf_decompiled.c"), encoding="utf-8").read()
    for m in re.finditer(r"^// ==== ([0-9a-f]+) ", text, re.M):
        heads.add(int(m.group(1), 16))
    diagram = open(os.path.join(ROOT, "docs", "functional_diagram.md"), encoding="utf-8").read()
    charts = "".join(re.findall(r"```mermaid(.*?)```", diagram, re.S))
    addrs = {int(a, 16) for a in re.findall(r"0x([0-9a-fA-F]{5,8})\b", charts)}
    assert len(addrs) > 60

    def inside(a):
        before = [h for h in heads if h < a]
        return a >= 0x01000000 and before and a - max(before) < 0x1000

    missing = sorted(hex(a) for a in addrs if a not in heads and not 0x04000000 <= a < 0x05000000 and not inside(a))
    assert not missing, missing
