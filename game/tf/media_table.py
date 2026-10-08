"""What each ROM display effect (deff) starts, read from the ROM extraction's package (rom/mpf_package).

- media/dmd/deffs/deff_NNN/timing.json: run length (ended_ms: when the deff ended in the capture; none for a
  deff that ran past the capture window), the sounds and lamp effects the deff's code started, with their
  offsets (observed in emulation). Values are written as hex digits, sometimes as JSON numbers ("5e", 20).
- lamp_effects.csv "started_by": lamp-matrix effects a deff starts ("effect N (deff_N_...)").
"""
import csv
import glob
import json
import os
import re


class DeffInfo:
    __slots__ = ("id", "name", "seconds", "sounds", "tubes", "leffs")

    def __init__(self, deff_id, name):
        self.id, self.name = deff_id, name
        self.seconds = 0.0
        self.sounds = []        # (offset s, call)
        self.tubes = []         # (offset s, tube show)
        self.leffs = []         # lamp-matrix effects started with the deff


def load(pkg):
    """pkg: the ROM extraction's MPF package (rom/mpf_package). Nothing is known before its captures exist."""
    table = {}
    for path in glob.glob(os.path.join(pkg, "media", "dmd", "deffs", "deff_*", "timing.json")):
        folder = os.path.basename(os.path.dirname(path))
        deff_id = int(folder.split("_")[1])
        info = table.setdefault(deff_id, DeffInfo(deff_id, folder))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        info.seconds = float(data.get("ended_ms") or 0) / 1000
        info.sounds = [(s["t_ms"] / 1000, int(str(s["call"]), 16)) for s in data.get("sounds") or []
                       if int(str(s.get("deff", deff_id))) == deff_id]
        info.leffs = [int(e["leff"]) for e in data.get("leffs") or []]
    path = os.path.join(pkg, "lamp_effects.csv")
    if not os.path.exists(path):        # Tron's package table; tf_180's deffs list their leffs in timing.json
        return table
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for m in re.finditer(r"effect (\d+) \(deff_", row["started_by"]):
                deff_id = int(m.group(1))
                table.setdefault(deff_id, DeffInfo(deff_id, "deff_%03d" % deff_id)).leffs.append(int(row["leff"]))
    return table
