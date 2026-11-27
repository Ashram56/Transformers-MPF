"""Lamp matrix model: the ROM's game lamp image, flash mask, lamp-matrix effects (leffs) and flashers.

The SAM OS keeps (read in Tron Legacy's decompile, re-cited to tf_180; the same OS here):
- the game image (RAM 0x36374, cleared by FUN_0000731c) that the rules write with lamp_on / lamp_off / lamp_on_solid / lamp_off_all /
  lamp_toggle, plus the flash mask (RAM 0x36388, lamp_bit_set): a lamp in the mask blinks while it is on;
- lamp override layers (lamp_layer_create(group, priority)): a mask of lamps and their own image,
  composited over the game image in priority order. The lamp-matrix effects (leff_start, tf_180 table
  0x040cfe00) draw through such layers while their task runs;
- lamp groups (tf_180 table 0x040d1510, 148 entries, not read yet).

Here a running leff is a layer at its ROM priority that plays the leff's captured show
(rom/mpf_package/config/shows/lampfx_NNN.yaml, listed in rom/rom_data/io/lamp_effects.csv; a leff without a
show, the ROM drawing it from game state, draws nothing until a feature draws it with leff_code). The composite drives the MPF lights (key "tf") and is logged as `lamp` events (1-80)
exactly like the ROM reference traces; flasher pulses are logged as `coil` on/off events.

The list-5 lamp rules (rule_obj_init(obj, 5, fn, 0x20)) that redraw inserts from game state on every
rules refresh are registered by the features with os.lamp_update(fn, priority).
"""
import csv
import os
import re

from tf.hw_numbers import rom_numbers
from tf.os_layer import TICK

LAMP_COUNT = 80
FLASH_TICKS = 10            # lamp_compositor_tick [0x000073cc] inverts the flash phase every 10 passes (1/tick, QA L-G02)
# The reference traces log the lamp outputs as libpinmame reports them: a lamp reads on while it was on
# at any time in about the last 65 ms (a flashing insert: on ~146 ms, off ~16 ms; leff 14 blinking every
# 10 ticks: on ~225 ms, off ~97 ms; anything toggled every 2 ticks reads solid). The trace applies that
# filter; the MPF lights get the unfiltered output.
OFF_DELAY = 0.065
MPF_KEY = "tf"
# The tf_180 reference traces log the drivers raw (rom/rules/traces/basic.jsonl 4.70 s: the Optimus flasher of
# leff 96 as 3-17 ms on / off slices), unlike Tron's, which held a pulsed coil on ~0.24 s: no hold here.
COIL_OFF_DELAY = 0.0
WHITE, BLACK = "ffffff", "000000"
# the lamp strobe [0x000113fc] shows plane 0 one pass and plane 1 two: a lamp lit in one plane only is at 1/3 (plane
# 0) or 2/3 (plane 1) (QA L-G03; rom/tools/leff_package.py writes them 555555 / aaaaaa)
PLANE_COLOR = {"555555": 1, "aaaaaa": 2}
LEVEL_COLOR = {1: "555555", 2: "aaaaaa", 3: WHITE}


def leff_rows(rom):
    """The ROM's leff table (rom/rom_data/io/lamp_effects.csv: leff, priority, coils_pulsed, run_ms, loops
    "yes" for a leff that runs until stopped, show), [] without the extraction."""
    path = os.path.join(rom, "rom_data", "io", "lamp_effects.csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_show(path):
    """Minimal reader for the package's generated show files (no YAML library in the venv):
    -> [(seconds, {light: on(bool) or hex color}, {flasher: ms})]."""
    steps = []
    section = coil = None
    for line in open(path, encoding="utf-8"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"- duration: (\d+)ms", line)
        if m:
            steps.append([int(m.group(1)) / 1000.0, {}, {}])
            section = None
            continue
        m = re.match(r"\s+(lights|flashers|coils):\s*$", line)
        if m:
            section = m.group(1)
            continue
        m = re.match(r"\s+pulse_ms:\s*(\d+)\s*$", line)
        if m and steps and section == "coils" and coil:
            steps[-1][2][coil] = int(m.group(1))
            continue
        m = re.match(r"\s+action:", line)
        if m:
            continue
        m = re.match(r"\s+(\S+):\s*$", line)
        if m and section == "coils":
            coil = m.group(1)
            continue
        m = re.match(r"""\s+(\S+):\s*['"]?([0-9a-fA-F]+)(ms)?['"]?\s*$""", line)   # agent A writes "ffffff" (QA L-G01)
        if m and steps and section:
            name, value = m.group(1), m.group(2)
            if section == "flashers":
                steps[-1][2][name] = int(value)
            else:
                steps[-1][1][name] = value.lower()
    return [tuple(s) for s in steps]


class Layer:
    """A lamp override layer (lamp_layer_create): owns `mask`, draws `image` (lamps on) over lower ones."""
    __slots__ = ("prio", "mask", "image", "seq", "name", "planes")

    def __init__(self, prio, mask=(), name=None):
        self.prio = prio
        self.mask = set(mask)
        self.image = set()
        self.seq = 0
        self.name = name
        self.planes = {}            # lamp -> 1 or 2: lit in one bit plane only (PLANE_COLOR)


class ShowPlayer:
    """Plays a parsed show on a layer (lamps), MPF RGB lights (tubes) and flashers."""

    def __init__(self, lamps, steps, layer=None, loops=0, tokens=None, on_end=None, rgb=False, owner=None,
                 loop_step=0):
        self.lamps = lamps
        self.loop_step = loop_step  # a looping leff's cycle starts here, after its lead-in (QA L-G11)
        self.owner = owner          # the leff id whose show this is (flasher arbitration)
        self.steps = steps
        self.layer = layer
        self.loops = loops
        self.tokens = tokens or {}
        self.on_end = on_end
        self.rgb = rgb
        self.index = 0
        self.handle = None
        self.done = False
        self._step()

    def _resolve(self, name):
        if name.startswith("("):
            return self.tokens.get(name.strip("()"), ())
        return (name,)

    def _step(self):
        self.handle = None
        if self.index >= len(self.steps):
            if self.loops == -1 and self.steps:
                self.index = self.loop_step if self.loop_step < len(self.steps) else 0
            else:
                self.done = True
                if self.on_end:
                    self.on_end()
                return
        seconds, lights, flashers = self.steps[self.index]
        self.index += 1
        lm = self.lamps
        for name, value in lights.items():
            for target in self._resolve(name):
                if self.rgb:
                    lm.rgb(target, value)
                    continue
                plane = PLANE_COLOR.get(str(value).lower())
                for n in lm.lamp_numbers(target):
                    if value != BLACK:
                        self.layer.image.add(n)
                    else:
                        self.layer.image.discard(n)
                    if plane:
                        self.layer.planes[n] = plane
                    else:
                        self.layer.planes.pop(n, None)
        for name, ms in flashers.items():
            lm.flasher(name, ms, owner=self.owner)
        if lights and not self.rgb:
            lm.changed()
        self.handle = lm.clock.schedule_once(self._step, max(seconds, 0.001))

    def stop(self):
        if self.handle:
            self.lamps.clock.unschedule(self.handle)
            self.handle = None
        self.done = True


class LeffTask:
    """A lamp-matrix effect drawn by code (the leffs whose show is "state display" or that follow live
    state): the ROM leff function as a task with its own layer. fn(task) draws on task.layer and
    continues with task.sleep(ticks, next_fn); task.end() ends the leff (its layer is released)."""

    def __init__(self, lamps, leff_id, layer):
        self.lamps = lamps
        self.leff_id = leff_id
        self.layer = layer
        self.handle = None
        self.data = {}
        self.children = []

    def spawn(self, fn, priority):
        """task_spawn_child: a child task with its own layer (freed with the leff)."""
        child = LeffTask(self.lamps, self.leff_id, self.lamps.layer_create(priority, name=self.layer.name))
        self.children.append(child)
        fn(child)
        return child

    def sleep(self, ticks, fn):
        def run():
            self.handle = None
            fn(self)
        self.handle = self.lamps.clock.schedule_once(run, max(ticks, 1) * TICK)

    def release(self, lamp):
        """lampgroup_bit_clear(group, layer mask): the lamp shows what is underneath again."""
        if lamp in self.layer.mask:
            self.layer.mask.discard(lamp)
            self.layer.image.discard(lamp)
            self.lamps.changed()

    def set(self, lamp, on):
        self.layer.mask.add(lamp)
        if on:
            self.layer.image.add(lamp)
        else:
            self.layer.image.discard(lamp)
        self.lamps.changed()

    def toggle(self, lamp):
        self.set(lamp, lamp not in self.layer.image)

    def end(self):
        """The leff function returned: its task ends (display.Leffs frees its outputs); an earlier copy of a leff
        started again (QA L-G05) frees only its own layer."""
        current = self.lamps.leff_players.get(self.leff_id)
        self.lamps._leff_show_done(self.leff_id, self)
        if current is not None and current[0] is self:
            self.lamps.os.leffs._ended(self.leff_id)

    def stop(self):
        if self.handle:
            self.lamps.clock.unschedule(self.handle)
            self.handle = None
        for child in self.children:
            child.stop()
            self.lamps.layer_free(child.layer)
        self.children = []


def shot_blink(rows, mask_fn, blink=3):
    """The mode rule leffs that flash the lit shots (leff_046 / 054 / 062 / 070 [0x010285e8 ...]): `rows` the
    mode's shot table [(mask bit, lamps)], each lit shot's lamps claimed and all on / all off every `blink`
    ticks, the others released to the rules. -> fn(LeffTask) for Lamps.leff_code."""
    def run(task, on=True):
        mask = mask_fn() or 0
        for bit, lamps in rows:
            for lamp in lamps:
                if mask & bit:
                    task.set(lamp, on)
                else:
                    task.release(lamp)
        task.sleep(blink, lambda t: run(t, not on))
    return run


def _coil_groups():
    """The coil group table 0x040cf65c (rom/rom_data/io/coil_groups.json, rom/tools/coil_groups.py): group -> ROM
    coil numbers, as coilgroup_pulse [0x00005fd4] and coil_group_pulse_fn_6044 [0x00006044] walk it."""
    import json                         # noqa: PLC0415
    path = os.path.join(os.path.dirname(__file__), "..", "..", "rom", "rom_data", "io", "coil_groups.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {int(k): tuple(v) for k, v in json.load(f).items()}


COIL_GROUPS = _coil_groups()
# leff -> coil group (rom/rom_data/io/lamp_effects.csv coil_group, read by task_leff_field8_81f4 [0x000081f4]): the
# leffs that loop coilgroup_pulse(group, 0x20) every 8 ticks: leff_047 [0x010286f8], leff_055 [0x0102a83c], leff_063
# [0x0100d038], leff_071 [0x0100ef64], leff_085 [0x0103692c] (QA L-085), leff_177 [0x01027024] (QA L-I59), and
# leff_077 [0x010104c4], leff_080 [0x01010b4c], leff_088 [0x0103720c], leff_124 [0x01015510]
SUPER_LIT_LEFF_GROUPS = {47: 18, 55: 22, 63: 26, 71: 31, 85: 36, 177: 57, 77: 34, 80: 35, 88: 37, 124: 46}


def _pf_ok(os_):
    """byte_314d8_d8ac [0x0000d8ac] and no ball search (task 0x2b): the test every flasher leff makes."""
    return os_.pf_valid and not os_.task_running(0x2b)


def _pulse_group(task, group, time, power=None):
    lamps = task.lamps
    names = {num: name for name, num in lamps.coil_numbers.items()}
    for num in COIL_GROUPS.get(group, ()):
        if num in names:
            lamps.flasher(names[num], time, owner=task.leff_id, power=power)


def flasher_group_pulse(group, every=8, time=0x20):
    """The super-lit leffs (QA M6): forever, every `every` ticks, coilgroup_pulse(group, 0x20) [0x00005fd4] while
    the playfield is valid (DAT_000314d8, FUN_0000d8ac; os.pf_valid) and ball search (task 0x2b) is not
    running. The group is the leff table's coil group, read by FUN_000081f4. -> fn(LeffTask)."""
    def run(task):
        if _pf_ok(task.lamps.os):
            _pulse_group(task, group, time)
        task.sleep(every, run)
    return run


# The brightness ramp of the flasher leffs: the 14 patterns of 0x040c7680 (leff_154), the same values at 0x040c6ff4
# (leff_040), 0x040c72f4 (044), 0x040c7458 (052), 0x040c643c (060), 0x040c663c (068), 0x040c5d5c (157), 0x040c5db8
# (160), 0x040c7110 (176), 0x040c751c (032)
RAMP_PATTERNS = (0x80008000, 0x80808080, 0x88808880, 0x88888888, 0xa888a888, 0xa8a8a8a8, 0xaaa8aaa8, 0xaaaaaaaa,
                 0xaaa8aaa8, 0xa8a8a8a8, 0xa888a888, 0x88888888, 0x88808880, 0x80808080)
# leff_148 [0x0102ef90]: the 11 patterns of 0x040c7590 (no top three)
RAMP_PATTERNS_11 = (0x80008000, 0x80808080, 0x88808880, 0x88888888, 0xa888a888, 0xa8a8a8a8, 0xa8a8a8a8, 0xa888a888,
                    0x88888888, 0x88808880, 0x80808080)


def _duty(pattern):
    return bin(pattern).count("1") / 32


def flasher_group_ramp(group, time=0x96, every=4, ready=_pf_ok):
    """leff_154 [0x010327bc] (super spinner lit), leff_032 [0x0102d520], leff_160 [0x01004b34], leff_176
    [0x01026fb0]: forever, while `ready` fails wait 4 ticks, then pulse the group with each of the 14 patterns,
    `every` ticks apart, a whole cycle without a new test (coil_group_pulse_fn_6044). leff_157 [0x01003f20] tests
    eject_warning_needed_3eec [0x01003eec] instead and steps 6 ticks. The pattern's duty is MPF's pulse_power.
    -> fn(LeffTask)."""
    def run(task, i=0):
        if i == 0 and not ready(task.lamps.os):
            return task.sleep(every, run)
        _pulse_group(task, group, time, _duty(RAMP_PATTERNS[i]))
        task.sleep(every, lambda t: run(t, (i + 1) % len(RAMP_PATTERNS)))
    return run


def _no_eject_warning(os_):
    """Not eject_warning_needed_3eec [0x01003eec]: the playfield is valid and no task 0x5d-0x7e runs."""
    return os_.pf_valid and not any(os_.task_running(t) for t in range(0x5d, 0x7f))


def flasher_coil_ramp(coil, time=100, every=4, group=None, patterns=RAMP_PATTERNS, toggle=None):
    """leff_040 [0x01024328] (Allspark banked, QA R-F7), leff_044 [0x01027ffc], leff_052 [0x0102a10c] (coil 0x1f),
    leff_060 [0x0100c914], leff_068 [0x0100e7d0] (coil 0x12): forever, every `every` ticks, when the playfield is
    valid and ball search (task 0x2b) does not run, coil_pulse_fn(coil, time, pattern) with the next pattern;
    otherwise the index goes back to 0. leff_148 [0x0102ef90] pulses its coil group (`group`) through the 11
    patterns of 0x040c7590 instead. `toggle` (060 and 068): coil_pulse(0x17, 0x20) on every other pass while
    valid, the first one included (a flag flipped every pass). The pattern's duty is MPF's pulse_power.
    -> fn(LeffTask)."""
    def run(task, i=0, odd=False):
        lamps = task.lamps
        if not _pf_ok(lamps.os):
            i = 0
        else:
            names = {num: name for name, num in lamps.coil_numbers.items()}
            if toggle and not odd and toggle[0] in names:
                lamps.flasher(names[toggle[0]], toggle[1], owner=task.leff_id)
            if group is not None:
                _pulse_group(task, group, time, _duty(patterns[i]))
            elif coil in names:
                lamps.flasher(names[coil], time, owner=task.leff_id, power=_duty(patterns[i]))
            i = (i + 1) % len(patterns)
        task.sleep(every, lambda t: run(t, i, not odd))
    return run


def _task_lamp(task):
    lamp = task.data.get("lamp")
    return lamp if isinstance(lamp, int) else None


def lamp_blink(toggles, every=2):
    """leff_097 [0x0102dda4], leff_100 [0x0102e4a0] (10 toggles), leff_098 [0x0102de08], leff_101 [0x0102e504]
    (5): the lamp of the task's +0x30 in the leff's own layer (lamp_bit_set_7814 on its mask), its image bit
    toggled (lamp_bit_flash_78dc) every 2 ticks from off, then the leff returns. -> fn(LeffTask)."""
    def run(task, n=0):
        lamp = _task_lamp(task)
        if lamp is None or n == toggles:
            return task.end()
        task.toggle(lamp)
        task.sleep(every, lambda t: run(t, n + 1))
    return run


def lamp_hold(on, ticks=8):
    """The lamp of the task's +0x30 forced on (leff_169 [0x0100999c], lamp_bit_toggle_set_77a0: leffs 139, 143,
    169) or off (leff_171 [0x01009a58], lamp_bit_write_765c: leffs 141, 145) in the leff's own layer for 8 ticks
    (the task's inline sleep 7 + 1), then the leff returns. -> fn(LeffTask)."""
    def run(task):
        lamp = _task_lamp(task)
        if lamp is None:
            return task.end()
        task.set(lamp, on)
        task.sleep(ticks, lambda t: t.end())
    return run


def gi_lamp_flash(gi_passes=12, toggles=0x50, every=2):
    """leff_038 [0x01023df8] (a shot goes to 2X): the GI taken (io_owner_take_bdbc) and switched off
    (io_owner_bit_set_bed8), back on after 12 passes (io_owner_bit_clear_bf04, tick 24); the lamp of the shot's
    record (+0x30 -> +0x12) toggled 80 times, 2 ticks apart, from off; then the leff returns. -> fn(LeffTask)."""
    def run(task, n=0):
        lamps = task.lamps
        lamp = _task_lamp(task)
        if n == 0:
            if lamp is None:
                return task.end()
            lamps._gi_cancel()
            lamps.gi_owner = task.leff_id
            lamps.gi_set(0, task.leff_id)
        if n == gi_passes:
            lamps.gi_set(1, task.leff_id)
        if n == toggles:
            return task.end()
        task.toggle(lamp)
        task.sleep(every, lambda t: run(t, n + 1))
    return run


def music_gi_beat(table):
    """leff_020 [0x01006f1c] (Optimus battle): the GI blinks on the beat of the battle music. table: [(music call,
    (ticks...))], the records of 0x040c5edc (+0 times, +4 count, +0xc call). Each tick, snd_chan_25854 [0x00025854]
    on the record's call: not playing, the index goes back to 0 and the time base to now; playing, when the ticks
    since the base reach times[index] the index steps and, while it stays below the count, io_owner_hold_6ef4
    [0x01006ef4] blinks the GI (claimed if free, off 2 ticks). The record is the one whose call plays
    (snd_call_playing); the first pass blinks once. -> fn(LeffTask)."""
    def blink(task):
        lamps = task.lamps
        if lamps.gi_owner not in (None, task.leff_id):
            return
        lamps._gi_cancel()
        lamps.gi_owner = task.leff_id
        lamps.gi_set(0, task.leff_id)

        def back(dt=0):
            lamps.gi_set(1, task.leff_id)
            if lamps.gi_owner == task.leff_id:
                lamps.gi_owner = None
        lamps._gi_handles.append(lamps.clock.schedule_once(back, 2 * TICK))

    def run(task, rec=0, idx=0, base=None, first=True):
        os_ = task.lamps.os
        call, times = table[rec]
        if base is None or not os_.sound_playing(call):
            idx, base = 0, os_.now
            rec = next((r for r, (c, _) in enumerate(table) if os_.sound_playing(c)), 0)
            if first:
                blink(task)
                first = False
        elif times[idx] * TICK <= os_.now - base:
            idx += 1
            if idx < len(times):
                blink(task)
            idx = min(idx, len(times) - 1)
        task.sleep(1, lambda t: run(t, rec, idx, base, first))
    return run


def hit_count_blink(rows, counts_fn, super_fn, super_lamps, all_lamps, blink=3, chase=8):
    """The side mode / wizard multiball rule leffs (leff_079 [0x010109a0], leff_087 [0x01037060]): per shot its
    lamps, the first `count` (hits made) solid and the others flashing every `blink` ticks; while the super is
    lit the shot lamps go back to the rules and `super_lamps` light one by one, then go out one by one, a step
    every `chase` ticks, in the order of lamp group 0x3d (12, 13, 14, 15): lamp_group_9164 [0x00009164] lights the
    group's first unlit lamp, lamp_group_941c [0x0000941c] puts out its first lit one."""
    def shots(task, on=True):
        if super_fn():
            for lamp in all_lamps:
                task.release(lamp)
            return sweep(task, 0, True)
        counts = counts_fn()
        for lamp in super_lamps:                # claimed (off) from the start, drawn only by the sweep
            if not any(lamp in lamps for lamps in rows):
                task.set(lamp, False)
        for i, lamps in enumerate(rows):
            made = counts[i] if i < len(counts) else 0
            for u, lamp in enumerate(lamps):
                task.set(lamp, on or u < made)
        task.sleep(blink, lambda t: shots(t, not on))

    def sweep(task, step, lighting):
        if step < len(super_lamps):
            task.set(super_lamps[step], lighting)
            task.sleep(chase, lambda t: sweep(t, step + 1, lighting))
        elif lighting:
            sweep(task, 0, False)
        else:
            shots(task)
    return shots


class Lamps:
    """The lamp matrix as the ROM keeps it. `in` / add / discard keep the old set interface
    (os.lamps: inserts the rules read back) as lamp_test / lamp_on_solid / lamp_off_all."""

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        self.clock = os_.machine.clock
        self.image = set()          # game image 0x36374: lamps on
        self.flash = set()          # flash mask 0x36388
        self.layers = []            # override layers, composited in (priority, creation) order
        self._seq = 0
        self.out = [0] * (LAMP_COUNT + 1)       # last output logged (filtered as libpinmame reports it)
        self.raw = [0] * (LAMP_COUNT + 1)       # composite output (MPF lights)
        self._off_pending = {}
        self._off_since = [0.0] * (LAMP_COUNT + 1)
        self.flash_off = False      # flash phase: True while flashing lamps are blanked
        self._flash_handle = None
        self._dirty = False
        self.leff_players = {}      # leff id -> ShowPlayer
        self.leff_copies = {}       # leff id -> [(ShowPlayer, layer)]: earlier copies still running (keep=True)
        self.gi = 1                 # the GI (owner 0x000314c4): on at power up, switched by 30 leffs (QA L-G07)
        self.gi_owner = None        # the leff that switched it last
        self.gi_by_code = set()     # code leffs that switch the GI themselves (leff_code gi=True)
        self._gi_handles = []
        self.tube_players = {}      # tube show id -> ShowPlayer
        self.code_leffs = {}        # leff id -> (layer priority, fn(LeffTask)): leffs drawn by code
        self.rules = []             # list-5 lamp rules: (priority, seq, fn)
        rom = os.path.join(self.machine.machine_path, "..", "rom")
        self.show_dir = os.path.join(rom, "mpf_package", "config", "shows")
        self._shows = {}
        self.leff_info = {}         # leff id -> (show name, loops (-1 = until stopped), priority)
        self.leff_loop_step = {}    # leff id -> the step its cycle starts at, after the lead-in (QA L-G11)
        for row in leff_rows(rom):
            self.leff_info[int(row["leff"])] = (row["show"], -1 if row["loops"] == "yes" else 0,
                                                int(row["priority"] or 0))
            self.leff_loop_step[int(row["leff"])] = int(row.get("loop_step") or 0)
        self.names = {}             # MPF light name -> lamp number (lamp matrix only)
        self.lights = {}            # lamp number -> MPF light
        self.groups = {}            # light tag (rom_group_N) -> lamp numbers
        rom_lamps = rom_numbers(self.machine, "lights")      # the ROM's lamp numbers, on any platform or machine
        for light in getattr(self.machine, "lights", {}).values():
            num = rom_lamps.get(light.name)
            if num is not None:
                self.names[light.name] = num
                self.lights[num] = light
                for tag in light.tags:
                    self.groups.setdefault(tag, []).append(num)
        self.coil_numbers = {}
        self._coil_until = {}       # flasher coil -> end of its current pulse
        rom_coils = rom_numbers(self.machine, "coils")
        for coil in getattr(self.machine, "coils", {}).values():
            if coil.name in rom_coils:
                self.coil_numbers[coil.name] = rom_coils[coil.name]
        self._start_flash()

    # ------------------------------------------------------------------ game image (ROM names)

    def lamp_on(self, n):
        """lamp_on(n, 0x36374, 0xff): on; a lamp in the flash mask keeps flashing."""
        self.image.add(n)
        self.changed()

    def lamp_off(self, n):
        """lamp_off(n, 0x36374, 0xff): off (the flash bit stays)."""
        self.image.discard(n)
        self.changed()

    def lamp_on_solid(self, n):
        """0x00007858: on, flash bit cleared (the lamp rules' solid write)."""
        self.image.add(n)
        self.flash.discard(n)
        self.changed()

    def lamp_off_all(self, n):
        """0x00007714: off, flash bit cleared (the lamp rules' off write)."""
        self.image.discard(n)
        self.flash.discard(n)
        self.changed()

    def lamp_flash(self, n):
        """lamp_on + the lamp's bit in the flash bitmap DAT_00036388 (as ball_start_sub_1801c [0x0001801c] sets it)."""
        self.image.add(n)
        self.flash.add(n)
        self.changed()

    def lamp_toggle(self, n):
        if n in self.image:
            self.image.discard(n)
        else:
            self.image.add(n)
        self.changed()

    def lamp_test(self, n):
        return n in self.image

    def lamp_flashing(self, n):
        return n in self.image and n in self.flash

    def lamp_set(self, n, state):
        """state: 0 off, 1 solid on, 2 flashing (the three states the lamp rules draw)."""
        if state == 2:
            self.lamp_flash(n)
        elif state:
            self.lamp_on_solid(n)
        else:
            self.lamp_off_all(n)

    def lamp_state(self, n):
        return 0 if n not in self.image else 2 if n in self.flash else 1

    def clear(self):
        """FUN_0000731c: game image, flash mask and leff images cleared (game start / end)."""
        self.image.clear()
        self.flash.clear()
        self.changed()

    # old set interface (os.lamps)
    def __contains__(self, n):
        return self.lamp_test(n)

    def add(self, n):
        self.lamp_on_solid(n)

    def discard(self, n):
        self.lamp_off_all(n)

    # ------------------------------------------------------------------ groups, layers

    def group(self, name):
        """Lamps of a ROM lamp group (lights.yaml tag rom_group_N) or of a light/lamp list."""
        if isinstance(name, int):
            return list(self.groups.get("rom_group_{}".format(name), ()))
        return list(self.groups.get(name, ()))

    def lamp_numbers(self, target):
        if isinstance(target, int):
            return (target,)
        if target in self.names:
            return (self.names[target],)
        return tuple(self.groups.get(target, ()))

    def layer_create(self, prio, mask=(), name=None):
        """lamp_layer_create(group, priority): a new layer on top of the ones with the same priority."""
        layer = Layer(prio, mask, name)
        self._seq += 1
        layer.seq = self._seq
        self.layers.append(layer)
        self.layers.sort(key=lambda la: (la.prio, la.seq))
        self.changed()
        return layer

    def layer_free(self, layer):
        if layer in self.layers:
            self.layers.remove(layer)
            self.changed()

    # ------------------------------------------------------------------ lamp-matrix effects

    def show(self, name):
        if name not in self._shows:
            path = os.path.join(self.show_dir, name + ".yaml")
            self._shows[name] = parse_show(path) if os.path.exists(path) else []
        return self._shows[name]

    def leff_code(self, leff_id, fn, priority=None, gi=False):
        """Draw leff `leff_id` with code instead of its captured show (fn(LeffTask), layer `priority`,
        default the leff's ROM priority). gi: fn switches the GI itself (its op list's GI frames are not played)."""
        self.code_leffs[leff_id] = (priority, fn)
        if gi:
            self.gi_by_code.add(leff_id)

    def leff_play(self, leff_id, lamp=None, keep=False):
        """A leff task started (display.Leffs accepted it): play its captured show on a layer at the ROM
        priority. `lamp` is the lamp (or lamp list / light tag) a caller passes to the token effects.
        keep: the running copy goes on beside the new one (leff_start [0x00007c10] creates a second task when
        the leff claims no lamp or coil group, QA L-G05)."""
        old = self.leff_players.get(leff_id)
        if keep and old is not None:
            self.leff_players.pop(leff_id)
            self.leff_copies.setdefault(leff_id, []).append(old)
        else:
            self.leff_end(leff_id)
        if leff_id not in self.gi_by_code:
            self._gi_play(leff_id)
        name, loops, prio = self.leff_info.get(leff_id, ("", 0, 0))
        if leff_id in self.code_leffs:
            layer_prio, fn = self.code_leffs[leff_id]
            layer = self.layer_create(prio if layer_prio is None else layer_prio, self._group_lamps(leff_id),
                                      name="leff_{}".format(leff_id))
            task = LeffTask(self, leff_id, layer)
            task.data["lamp"] = lamp
            self.leff_players[leff_id] = (task, layer)
            fn(task)
            return
        steps = self.show(name) if name else []
        if not steps:
            return
        tokens = {}
        mask = set()
        if lamp is not None:
            targets = lamp if isinstance(lamp, (list, tuple, set)) else (lamp,)
            tokens["lamp"] = tokens["lamps"] = [t for t in targets]
        for _, lights, _ in steps:
            for light in lights:
                for target in (tokens.get(light.strip("()"), ()) if light.startswith("(") else (light,)):
                    mask.update(self.lamp_numbers(target))
        mask |= self._group_lamps(leff_id)
        layer = self.layer_create(prio, mask, name="leff_{}".format(leff_id))
        player = ShowPlayer(self, steps, layer, loops, tokens, owner=leff_id,
                            loop_step=self.leff_loop_step.get(leff_id, 0))
        player.on_end = lambda: self._leff_show_done(leff_id, player)
        self.leff_players[leff_id] = (player, layer)

    def _group_lamps(self, leff_id):
        """leff_start [0x00007c10]: a leff with a lamp group (+6) clears the group's lamps in the leff image and flash
        mask (lamp_group_84cc / lamp_group_86d4 on 0x00036394 / 0x000363a8), so the leff owns them, off, from its
        start (QA L-G08)."""
        leffs = getattr(self.os, "leffs", None)
        claims = getattr(leffs, "claims", {}) if leffs is not None else {}
        return set(claims.get(leff_id, (frozenset(),))[0])

    def _leff_show_done(self, leff_id, player=None):
        # a show that plays once ends with its task: the layer is released (display.Leffs keeps the
        # leff's own length for the priority bookkeeping); an earlier copy frees only its own layer
        for entry in self.leff_copies.get(leff_id, ()):
            if player is not None and entry[0] is player:
                self.leff_copies[leff_id].remove(entry)
                self.layer_free(entry[1])
                return
        entry = self.leff_players.get(leff_id)
        if entry and (player is None or entry[0] is player):
            self.leff_players.pop(leff_id)
            if isinstance(entry[0], LeffTask):
                entry[0].stop()
            self.layer_free(entry[1])

    # ------------------------------------------------------------------ GI

    def _gi_steps(self, leff_id):
        """[(tick, 0 / 1)]: when the leff's code switches the GI (agent A's leff op lists, frames "gi"; the GI
        owner 0x000314c4, e.g. leff_081 ram_000314c4_user_bdbc(0) [0x010119d8])."""
        if not hasattr(self, "_gi_table"):
            import json                                  # noqa: PLC0415
            self._gi_table = {}
            folder = os.path.join(os.path.dirname(__file__), "..", "..", "rom", "rom_data", "io", "leff_ops")
            if os.path.isdir(folder):
                for name in os.listdir(folder):
                    if name.startswith("leff_") and name.endswith(".json"):
                        with open(os.path.join(folder, name), encoding="utf-8") as f:
                            d = json.load(f)
                        steps, last = [], None
                        for frame in d.get("frames") or ():
                            gi = frame.get("gi") if isinstance(frame, dict) else None
                            if gi is not None and gi != last:
                                steps.append((frame["t"], int(gi)))
                                last = gi
                        if any(v == 0 for _, v in steps):
                            self._gi_table[int(d["leff"])] = steps
        return self._gi_table.get(leff_id, ())

    def _gi_play(self, leff_id):
        steps = self._gi_steps(leff_id)
        if not steps:
            return
        self._gi_cancel()
        self.gi_owner = leff_id
        for tick, value in steps:
            fire = (lambda v: lambda: self.gi_set(v, leff_id))(value)
            if tick <= 0:
                fire()
            else:
                self._gi_handles.append(self.clock.schedule_once(lambda dt=0, f=fire: f(), tick * TICK))

    def _gi_cancel(self):
        for handle in self._gi_handles:
            self.clock.unschedule(handle)
        self._gi_handles = []

    def gi_set(self, value, owner=None):
        if owner is not None and owner != self.gi_owner:
            return
        if value != self.gi:
            self.gi = value
            self.os.trace.log("gi", on=value)
            self.machine.events.post("tf_gi", on=value)

    def leff_end(self, leff_id):
        if leff_id == self.gi_owner:             # the leff's end gives the GI back (on)
            self._gi_cancel()
            self.gi_set(1, leff_id)
            self.gi_owner = None
        entry = self.leff_players.pop(leff_id, None)
        if entry:
            entry[0].stop()
            self.layer_free(entry[1])
        for player, layer in self.leff_copies.pop(leff_id, ()):     # leff_stop kills every task of the leff
            player.stop()
            self.layer_free(layer)

    def leff_lamps_end(self):
        for leff_id in list(self.leff_players):
            self.leff_end(leff_id)

    # ------------------------------------------------------------------ tubes and flashers

    def tube_play(self, show_id):
        """Ramp tube show (display.Tubes accepted it): its show on the two RGB tube lights."""
        self.tube_end(show_id)
        steps = self.show("leff_{:03d}".format(show_id))
        if steps:
            loops = -1 if self.os.tubes.info.get(show_id, (0, 0, "loop", 0))[2] != "once" else 0
            self.tube_players[show_id] = ShowPlayer(self, steps, loops=loops, rgb=True,
                                                    on_end=lambda: self.tube_players.pop(show_id, None))

    def tube_end(self, show_id):
        player = self.tube_players.pop(show_id, None)
        if player:
            player.stop()

    def rgb(self, light_name, value):
        light = getattr(self.machine, "lights", {}).get(light_name)
        if light is not None:
            light.color(value.lstrip("#"), key=MPF_KEY)

    def flasher(self, name, ms=30, owner=None, power=None):
        """coil_pulse(coil, time) for a flasher: pulse the MPF coil, log coil on/off like the ROM traces.
        owner: the leff pulsing it. While a running leff with a higher priority uses the same flasher,
        a lower leff's pulses do not reach it (the ROM's flasher ownership: the leff's coil group, +8 of its
        table entry, claimed by leff_start's conflict test [0x00007c10], tf/display.py Leffs). power: the duty of a patterned pulse
        (coil_pulse_fn's 32-bit on/off pattern, bits set / 32) as MPF's pulse_power."""
        if owner is not None and self.os.leffs.flasher_outranked(owner, name):
            return
        coil = getattr(self.machine, "coils", {}).get(name)
        num = self.coil_numbers.get(name)
        if coil is not None:
            try:
                coil.pulse(int(ms), pulse_power=power) if power is not None else coil.pulse(int(ms))
            except Exception:       # noqa: BLE001 (a disabled driver in a test machine)
                pass
        if num is not None:
            self.coil_log(num, ms)

    def coil_log(self, num, ms):
        """Log a `coil` on/off pair for a driver on for `ms`, through the reference traces' output hold."""
        # the driver stays on through back-to-back pulses: one on/off pair, as the traces log the driver
        now = self.clock.get_time()
        until = now + ms / 1000.0 + COIL_OFF_DELAY
        if self._coil_until.get(num, 0) <= now:
            self.os.trace.log("coil", coil=num, on=1)
            self._coil_until[num] = until
            self.clock.schedule_once(lambda: self._coil_off(num), until - now)
        else:
            self._coil_until[num] = max(self._coil_until[num], until)

    def _coil_off(self, num):
        left = self._coil_until.get(num, 0) - self.clock.get_time()
        if left > 0.0005:
            self.clock.schedule_once(lambda: self._coil_off(num), left)
            return
        self.os.trace.log("coil", coil=num, on=0)

    # ------------------------------------------------------------------ list-5 lamp rules

    def add_rule(self, fn, priority=0):
        self._seq += 1
        self.rules.append((-priority, -self._seq, fn))       # equal priority: newest first
        self.rules.sort(key=lambda r: (r[0], r[1]))

    def run_rules(self):
        for _, _, fn in self.rules:
            fn()

    # ------------------------------------------------------------------ output

    def _start_flash(self):
        """Flash phase: flashing lamps are blanked every other FLASH_TICKS ticks."""
        def phase():
            self.flash_off = not self.flash_off
            self._start_flash()
            if self.flash & self.image:
                self._flush()
        self._flash_handle = self.clock.schedule_once(phase, FLASH_TICKS * TICK)

    def changed(self):
        if not self._dirty:
            self._dirty = True
            self.clock.schedule_once(self._flush, 0)

    def composite(self, n):
        return self.level(n) > 0

    def level(self, n):
        """The lamp's strobe level: 0 off, 1 / 2 one bit plane (1/3, 2/3), 3 both [0x000113fc]."""
        level = 3 if n in self.image and not (self.flash_off and n in self.flash) else 0
        for layer in self.layers:
            if n in layer.mask:
                level = layer.planes.get(n, 3) if n in layer.image else 0
        return level

    def _flush(self):
        self._dirty = False
        for n in range(1, LAMP_COUNT + 1):
            level = self.level(n)
            state = 1 if level else 0
            if level == self.raw[n]:
                continue
            was = self.raw[n]
            self.raw[n] = level
            light = self.lights.get(n)
            if light is not None:
                light.color(LEVEL_COLOR.get(level, BLACK), key=MPF_KEY)
            if bool(was) == bool(state):
                continue
            if state:
                if not self.out[n]:
                    self.out[n] = 1
                    self.os.trace.log("lamp", lamp=n, state=1)
            else:
                self._off_since[n] = self.clock.get_time()
                if self.out[n] and n not in self._off_pending:
                    self._off_pending[n] = self.clock.schedule_once(lambda n=n: self._off(n), OFF_DELAY)

    def _off(self, n):
        """The filtered output goes off once the lamp has stayed off for OFF_DELAY."""
        self._off_pending.pop(n, None)
        if self.raw[n] or not self.out[n]:
            return
        wait = self._off_since[n] + OFF_DELAY - self.clock.get_time()
        if wait > 0.001:
            self._off_pending[n] = self.clock.schedule_once(lambda: self._off(n), wait)
            return
        self.out[n] = 0
        self.os.trace.log("lamp", lamp=n, state=0)
