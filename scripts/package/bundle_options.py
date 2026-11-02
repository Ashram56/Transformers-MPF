#!/usr/bin/env python3
"""Read and change the settings of an installed Transformers bundle (docs/package.md). Standard library only.

    python scripts/package/bundle_options.py list                  # the schema (options.json) as JSON
    python scripts/package/bundle_options.py get [ID ...]          # the values that were set, as JSON
    python scripts/package/bundle_options.py set ID VALUE [ID VALUE ...]   # validate them all, then write
    python scripts/package/bundle_options.py unset ID [ID ...]     # back to the game's own default
    python scripts/package/bundle_options.py run-args              # the scripts/run.py flags the values make

This is the `options.tool` of the bundle: the platform's setup page (MPF-Godot-Packaging common/games/README.md) builds
its settings form from `list` and writes with `set`/`unset`; it never writes the game's files itself. Values go where
options.json says: scripts/run.py flags are kept in game/options.json (scripts/package/start.py adds them to the
command), cfg keys are written into game/pup.local.cfg, the git-ignored file the PuP runtime reads after game/pup.cfg.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
GAME = os.path.join(ROOT, "game")
SCHEMA = os.path.join(HERE, "options.json")
STORE = "options.json"            # in game/: the values that become run.py flags (kept on update, never packed)


class OptionError(ValueError):
    pass


def load_schema(path=SCHEMA):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def by_id(schema):
    return {o["id"]: o for o in schema["options"]}


# ---------------------------------------------------------------------- values

def convert(opt, value):
    """The value as the option's type, or OptionError saying what is wrong. Strings come from a command line or a form."""
    kind, label = opt["type"], opt["id"]
    try:
        if kind == "bool":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in ("1", "true", "yes", "on"):
                return True
            if text in ("0", "false", "no", "off"):
                return False
            raise ValueError
        if kind == "integer":
            number = int(str(value).strip())
            if "min" in opt and number < opt["min"] or "max" in opt and number > opt["max"]:
                raise OptionError("{}: {} to {}, not {}".format(label, opt.get("min", ""), opt.get("max", ""), value))
            return number
        if kind == "choice":
            text = str(value).strip().lower()
            if text not in opt["choices"]:
                raise OptionError("{}: one of {}, not {!r}".format(label, ", ".join(opt["choices"]), value))
            return text
        if kind == "size":
            text = str(value).strip().lower()
            if not re.fullmatch(r"\d{2,5}x\d{2,5}", text):
                raise ValueError
            return text
        raise OptionError("{}: unknown type {}".format(label, kind))
    except (ValueError, TypeError) as e:
        if isinstance(e, OptionError):
            raise
        raise OptionError("{}: not a valid {}: {!r}".format(label, kind, value))


# ---------------------------------------------------------------------- game/pup.local.cfg (INI with JSON values)

def cfg_path(target, game=GAME):
    name = target["cfg"]
    if os.path.basename(name) != name or not name.endswith(".local.cfg"):
        raise OptionError("bad cfg file name " + name)
    return os.path.join(game, name)


def cfg_read(path, section, key):
    """The raw text of key in [section] of a cfg file, or None."""
    if not os.path.exists(path):
        return None
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                current = s[1:-1].strip()
            elif current == section and "=" in s and s[0] not in ";#" and s.split("=", 1)[0].strip() == key:
                return s.split("=", 1)[1].strip()
    return None


def cfg_write(path, section, key, text):
    """Set key=text in [section], keeping every other line and comment; text None removes the key."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
    out, current, done, section_at = [], None, False, None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if current == section and not done and text is not None:
                out.append("{}={}".format(key, text))
                done = True
            current = s[1:-1].strip()
            if current == section:
                section_at = len(out)
        elif current == section and "=" in s and s[0] not in ";#" and s.split("=", 1)[0].strip() == key:
            if text is not None and not done:
                out.append("{}={}".format(key, text))
                done = True
            continue
        out.append(line)
    if text is not None and not done:
        if section_at is None:
            if out and out[-1].strip():
                out.append("")
            out.append("[{}]".format(section))
        out.append("{}={}".format(key, text))
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)


def decode(text):
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text.strip('"')


# ---------------------------------------------------------------------- store of the run.py flags

def store_read(game=GAME):
    path = os.path.join(game, STORE)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def store_write(values, game=GAME):
    path = os.path.join(game, STORE)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------- public

def get_values(ids=None, game=GAME, schema=None):
    """{id: value} for the options that were set (default values are not listed)."""
    opts = by_id(schema or load_schema())
    stored = store_read(game)
    out = {}
    for oid in ids or opts:
        opt = opts.get(oid)
        if opt is None:
            raise OptionError("unknown option " + oid)
        t = opt["target"]
        if "cfg" in t:
            value = decode(cfg_read(cfg_path(t, game), t["section"], t["key"]))
            if value is not None and value != "":
                out[oid] = value
        elif oid in stored:
            out[oid] = stored[oid]
    return out


def set_values(changes, game=GAME, schema=None):
    """Validate every {id: value} first, then write them all. Returns the ids that changed."""
    opts = by_id(schema or load_schema())
    clean = {}
    for oid, value in changes.items():
        if oid not in opts:
            raise OptionError("unknown option " + oid)
        clean[oid] = convert(opts[oid], value)
    stored = store_read(game)
    for oid, value in clean.items():
        t = opts[oid]["target"]
        if "cfg" in t:
            cfg_write(cfg_path(t, game), t["section"], t["key"], json.dumps(value))
        else:
            stored[oid] = value
    store_write(stored, game)
    return sorted(clean)


def unset_values(ids, game=GAME, schema=None):
    opts = by_id(schema or load_schema())
    stored = store_read(game)
    for oid in ids:
        if oid not in opts:
            raise OptionError("unknown option " + oid)
        t = opts[oid]["target"]
        if "cfg" in t:
            path = cfg_path(t, game)
            if os.path.exists(path):
                cfg_write(path, t["section"], t["key"], None)
        else:
            stored.pop(oid, None)
    store_write(stored, game)
    return sorted(ids)


def run_args(game=GAME, schema=None):
    """The scripts/run.py flags made by the stored values, in schema order."""
    stored = store_read(game)
    args = []
    for opt in (schema or load_schema())["options"]:
        t = opt["target"]
        if opt["id"] not in stored or "cfg" in t:
            continue
        value = stored[opt["id"]]
        if "arg" in t:
            args += [t["arg"], str(value)]
        elif "flag" in t:
            if value:
                args.append(t["flag"])
            elif "flag_off" in t:
                args.append(t["flag_off"])
    return args


# ---------------------------------------------------------------------- command line

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else "list"
    try:
        if cmd == "list":
            print(json.dumps(load_schema(), indent=2))
        elif cmd == "get":
            print(json.dumps(get_values(argv or None), indent=2, sort_keys=True))
        elif cmd == "set":
            if not argv or len(argv) % 2:
                raise OptionError("set ID VALUE [ID VALUE ...]")
            print("set: " + ", ".join(set_values(dict(zip(argv[::2], argv[1::2])))))
        elif cmd == "unset":
            print("unset: " + ", ".join(unset_values(argv)))
        elif cmd == "run-args":
            print(" ".join(run_args()))
        else:
            raise OptionError("commands: list, get, set, unset, run-args")
    except OptionError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
