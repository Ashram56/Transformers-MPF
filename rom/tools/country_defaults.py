"""Read the factory default of every adjustment, per country, by running the ROM's own factory reset.

For each country N of the country table 0x00030b60 (0..0x1c): the country word 0x021100d8 = N with its inverted
sum16 (sum16_1c50 [0x00001c50]) in 0x021100da, as the DIP read 0x550c stores it at boot; then the factory reset
error_log_530_all_728 [0x00000728] (adj_reset_one_530 for 1..98: adj_default_get_3d8 [0x000003d8] ->
adj_default_lookup_53dc [0x000053dc]: country game list > list 0x33790 > country OS list > table default), then
adj_get [0x00000340] of every adjustment. All of it runs as ROM code in Unicorn (switch_lift.py's runner after
the module constructors and game_init).

Checks rom_data/settings/presets.csv (kind=country) and the factory_default_usa column of adjustments.csv
against the code run and retags them "code" when they agree; prints every disagreement.

Usage: TF_ROM=tf_180.bin python3 country_defaults.py [--dry]
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import deff_lift  # noqa: E402
import switch_lift  # noqa: E402
from deff_lift import S  # noqa: E402

SET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rom_data", "settings")
COUNTRY = 0x021100d8


def defaults(r, n):
    r.m.mem_write(COUNTRY, struct.pack("<H", n))
    s = r.call(0x00001c50, COUNTRY, 2) & 0xffff
    r.m.mem_write(COUNTRY + 2, struct.pack("<H", ~s & 0xffff))
    r.call(0x00000728)
    return {a: r.call(S("adj_get"), a) for a in range(1, 99)}


def main():
    dry = "--dry" in sys.argv
    deff_lift.work_pages()
    r = switch_lift.SwitchRunner()
    switch_lift.start_game(r)
    pre = list(csv.DictReader(open(os.path.join(SET, "presets.csv"), encoding="utf-8")))
    runs, bad = {}, []
    for row in pre:
        if row["kind"] != "country":
            continue
        n = int(row["item"].split()[1])
        if n not in runs:
            runs[n] = defaults(r, n)
        v = runs[n][int(row["adj"])]
        if v == int(row["value"]):
            row["tag"] = "code (country %d, 0x728 and adj_get run as ROM code, country_defaults.py)" % n
        else:
            bad.append(("preset", row["preset"], row["adj"], row["value"], v))
    usa = runs.get(0) or defaults(r, 0)
    adj = list(csv.DictReader(open(os.path.join(SET, "adjustments.csv"), encoding="utf-8")))
    ok = 0
    for row in adj:
        v = usa[int(row["adj"])]
        if str(v) == row["factory_default_usa"]:
            ok += 1
            row["country_overrides"] = row["country_overrides"].replace("[observed]", "[code]")
        else:
            bad.append(("usa", row["adj"], row["name"], row["factory_default_usa"], v))
    print("countries run", len(runs), "; preset rows", sum(1 for x in pre if x["kind"] == "country"),
          "; USA defaults equal", ok, "of", len(adj), "; disagreements", bad)
    if dry or bad:
        return
    for name, rows in (("presets.csv", pre), ("adjustments.csv", adj)):
        with open(os.path.join(SET, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
