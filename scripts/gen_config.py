#!/usr/bin/env python3
"""Generate game/config/rom/*.yaml from the ROM extraction's MPF package (rom/mpf_package/config).

These files are generated, not edited: re-run after every change under rom/ (scripts/setup.py and the tests do it).

- switches.yaml, coils.yaml, lights.yaml: the package's devices. Dedicated switches, which the package numbers
  129-160 (the ROM's switch numbers), become SAM's "D<n>" (n = 1-32, PinMAME sam.c numbering, the form the
  hardware overlays and docs/hardware.md use).
- settings.yaml: the operator adjustments as MPF settings, from the package's settings.yaml when the ROM
  extraction has delivered it, else game/config/interim/settings.yaml (scripts/interim_settings.py).
- coil_times.yaml: the ROM's drive times per coil from rom/rom_data/io/coils.csv's mpf_* columns, for a package
  whose coils.yaml lacks them (tf_180's carries them: measured in the emulator, coil_timing.csv).
- proc_numbers.yaml: the P-ROC addresses of every switch, coil and light for a hardware overlay, in the strings
  libpinproc's decode() takes for driverboards sternSAM (PRDecode in libpinproc src/pinproc.cpp): matrix switch n
  -> "Snn", dedicated "D<n>" (1-24) -> "SD<n>", coil n (1-32) -> "Cnn", lamp n (1-80) -> "Lnn". Coils 33-35 are
  aux bus outputs (ticket dispenser), not P-ROC drivers: they stay on the virtual platform.

Transformers Pro is the only model the ROM extraction covers (tf_180), so there is no other model's overlay.
"""
import csv
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "rom", "mpf_package", "config")
DST = os.path.join(ROOT, "game", "config", "rom")
CONFIG = os.path.join(ROOT, "game", "config")
INTERIM_SETTINGS = os.path.join(CONFIG, "interim", "settings.yaml")
DEVICE_FILES = ["switches.yaml", "coils.yaml", "lights.yaml"]
PROC_SOURCES = ["rom/switches.yaml", "rom/coils.yaml", "rom/lights.yaml", "hardware.yaml"]
COIL_TIMES = os.path.join(ROOT, "rom", "rom_data", "io", "coils.csv")
DEDICATED_BASE = 128            # the ROM numbers dedicated switch D<n> as 128 + n


def _write(path, out):
    if not os.path.exists(path) or open(path, encoding="utf-8").read() != out:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)


def settings_source():
    pkg = os.path.join(PKG, "settings.yaml")
    return pkg if os.path.exists(pkg) else INTERIM_SETTINGS


def _dedicated(m):
    n = int(m.group(2))
    if n > DEDICATED_BASE:
        return "{}D{}{}".format(m.group(1), n - DEDICATED_BASE, m.group(3))
    return m.group(0)


def convert(name, body):
    lines = [line for line in body.splitlines() if not line.startswith("#config_version")]
    body = "\n".join(lines) + "\n"
    if name == "switches.yaml":
        body = re.sub(r"(?m)^(    number: )(\d+)(.*)$", _dedicated, body)
    if name == "settings.yaml":
        # the package writes the setting group as "setting_type"; MPF 0.80's settings spec calls it "settingType"
        body = body.replace("    setting_type: ", "    settingType: ")
    # MPF 0.80 has no "flashers:" section; flashers are plain coils there
    body = body.replace("\nflashers:\n", "\n# (flashers, as coils for MPF 0.80)\n")
    return body


def proc_number(section, number):
    """SAM number -> (libpinproc number string, None) or (None, reason it stays virtual)."""
    text = str(number).strip()
    if section == "switches":
        m = re.fullmatch(r"D(\d+)", text)
        if m and 1 <= int(m.group(1)) <= 24:
            return "SD{}".format(int(m.group(1))), None
        if m:
            return None, "DIP switch, not a P-ROC input"
        if text.isdigit() and 1 <= int(text) <= 64:
            return "S{:02d}".format(int(text)), None
    elif section == "coils":
        if text.isdigit() and 1 <= int(text) <= 32:
            return "C{:02d}".format(int(text)), None
        if text.isdigit() and 33 <= int(text) <= 40:
            return None, "aux bus output, not a P-ROC driver"
    elif section == "lights":
        if text.isdigit() and 1 <= int(text) <= 80:
            return "L{:02d}".format(int(text)), None
    raise ValueError("{} number {!r} is not a SAM number".format(section, number))


def _yaml():
    from ruamel.yaml import YAML        # MPF's YAML library
    return YAML(typ="safe")


def machine_numbers():
    """{section: [(name, SAM number)]} of rom/*.yaml and hardware.yaml."""
    yaml = _yaml()
    out = {}
    for section in ("switches", "coils", "lights"):
        entries = out.setdefault(section, [])
        for source in PROC_SOURCES:
            path = os.path.join(CONFIG, source)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                data = yaml.load(f) or {}
            for name, cfg in (data.get(section) or {}).items():
                if cfg and "number" in cfg:
                    entries.append((name, cfg["number"]))
    return out


def gen_proc_numbers(numbers):
    lines = ["#config_version=6",
             "# GENERATED by scripts/gen_config.py from {}:".format(", ".join(PROC_SOURCES)),
             "# P-ROC (driverboards sternSAM) numbers for every switch, coil and light of Transformers Pro."]
    for section in ("switches", "coils", "lights"):
        lines.append("{}:".format(section))
        for name, number in numbers[section]:
            lines.append("  {}:".format(name))
            proc, reason = proc_number(section, number)
            if proc:
                lines.append("    number: {}   # SAM {}".format(proc, number))
            else:
                lines.append("    platform: virtual   # SAM {}: {}".format(number, reason))
    _write(os.path.join(DST, "proc_numbers.yaml"), "\n".join(lines) + "\n")


def gen_coil_times(numbers):
    """rom/coil_times.yaml: the drive times the ROM gives each coil (rom/rom_data/io/coils.csv, mpf_* columns)."""
    names = {int(number): name for name, number in numbers["coils"] if str(number).isdigit()}
    with open(os.path.join(PKG, "coils.yaml"), encoding="utf-8") as f:
        if "default_pulse_ms" in f.read():           # the package's coils carry the measured times already
            names = {}
    lines = ["#config_version=6",
             "# GENERATED by scripts/gen_config.py from rom/rom_data/io/coils.csv: the ROM's drive time for each coil.",
             "# Empty when rom/mpf_package/config/coils.yaml carries the times itself (rom/coils.yaml then has them)."]
    entries = []
    with open(COIL_TIMES, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            number = int(row["coil"])
            if number not in names or "mpf_default_pulse_ms" not in row:
                continue
            values = [("default_pulse_ms", row.get("mpf_default_pulse_ms", ""), lambda t: int(round(float(t)))),
                      ("default_hold_power", row.get("mpf_default_hold_power", ""), float),
                      ("default_pulse_power", row.get("mpf_pulse_power", ""), float)]
            values = [(key, cast(text)) for key, text, cast in values if text and text.strip()]
            if not values:
                continue
            entries.append("  {}:   # {} {}: {}".format(names[number], number, row["name"], row.get("mpf_note", "")))
            entries += ["    {}: {}".format(key, value) for key, value in values]
    lines += ["coils:"] + entries if entries else ["coils: {}"]
    _write(os.path.join(DST, "coil_times.yaml"), "\n".join(lines) + "\n")


def main():
    os.makedirs(DST, exist_ok=True)
    sources = [(name, os.path.join(PKG, name)) for name in DEVICE_FILES] + [("settings.yaml", settings_source())]
    for name, path in sources:
        with open(path, encoding="utf-8") as f:
            body = convert(name, f.read())
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        _write(os.path.join(DST, name), "#config_version=6\n# GENERATED from {} by scripts/gen_config.py\n{}".format(
            rel, body))
    numbers = machine_numbers()
    gen_proc_numbers(numbers)
    gen_coil_times(numbers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
