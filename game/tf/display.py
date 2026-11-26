"""Display effect (deff) manager: priorities, the background score display and the show queue.

Model of the SAM OS deff system, rebuilt for Tron Legacy first (github.com/Ashram56/Tron-Legacy-MPF,
game/tron/display.py, where the trace references below come from) and the same OS here:
- Background deffs (the deff table's flag 0x0001, e.g. 19 score display, 21 tilt) loop until replaced.
- Foreground deffs run for their recorded length (timing.json run_seconds) unless started with
  hold=True (the caller stops them, e.g. the bonus). A deff with a lower priority than the running
  foreground deff is not shown.
- What a deff starts by itself comes from the asset package (media_table): its lamp-matrix effects
  at once, its sounds at their offsets (logged with in_deff = the deff).
- A foreground deff spends its last 10 ticks in a hold at priority 0x20 (deff_hold_frames): any deff
  can replace it then.
- Show queue, deff_start_user_6350 [0x01006350] (Tron's queue_fullscreen_deff): "show" tasks first run once their
  caller has finished, wait until the running deff's priority is below their threshold (0x9f for every
  caller) and they are the oldest show task waiting (leaf_b698(0x5d, 0x7e): tf_180's show tasks are 0x5d-0x7e;
  the game numbers them 0x81-0xa7, internal ids only), then play their deff until its hold (priority <= 0x20,
  leaf_20e48). While a show task runs, mode clocks pause.
- Mode TOTAL tasks (when_idle, deff_start_user_664c [0x0100664c]) wait for no show task (0x5d-0x7e,
  [0x01006634]) and no foreground deff.
- After an effect ends, and after a show ends, the deff rules re-assert the background deff (deff rule
  0x000178b0): deff 19, or the deff of the true mode rule, restarts in the background during normal play.
- Mode deff rules (lamp_rule_init list 2, os.deff_rule -> add_rule): on each rules refresh the true rule
  with the highest priority starts its background deff (even behind a show) when it changed, and its
  music call when that music is not already playing. With no mode rule true the score display rule runs
  with os.base_music() (inferred from the traces; tf_180's music rule routine is not identified yet). Every
  start of a rule's deff is traced with rule=1 (tf_180's caller 0x0001794c).
- Each decoded deff holds for its own tail (HOLD_TICKS_BY_DEFF: 1, 2 or 10 ticks, the ticks after its
  deff_hold_frames priority 0x20 in agent A's op list, rom/rom_data/dmd/deff_ops/; QA F7); 10 for the others.

Data: the deff priorities and background flags come from the ROM extraction's event_map.csv when it exists,
else game/config/interim/deffs.csv (scripts/interim_tables.py, read from tf_180's deff table); the run lengths,
sounds and lamp effects of each deff from the package's captures (media_table), none delivered yet.
"""
import csv
import os

from tf import media_table

SHOW_THRESHOLD = 0x9f
SHOW_TIMEOUT = 0xea6
HOLD_TICKS = 10             # deffs end with deff_hold_frames(10, 0x20): priority 0x20 for the last 10 ticks
HOLD_PRIORITY = 0x20
# a few deffs hold for fewer ticks (read from their code: deff_hold_frames(1, 0x20))
# A show task whose end the deferred rules refresh waits for (Tron: the Flynn's Arcade show 0x97); none here yet
RULES_HOLD_SHOW = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROM = os.path.join(ROOT, "rom")
PKG = os.path.join(ROM, "mpf_package")
INTERIM = os.path.join(ROOT, "game", "config", "interim")


def deff_table():
    """({deff: priority}, {background deffs}) from event_map.csv, else the interim table."""
    prio, background = {}, set()
    path = os.path.join(PKG, "event_map.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                deff_id = int(row["deff"])
                prio[deff_id] = int(row["priority"] or 0)
                if row["background_loop"] == "yes":
                    background.add(deff_id)
        return prio, background
    with open(os.path.join(INTERIM, "deffs.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            deff_id = int(row["deff"])
            prio[deff_id] = int(row["priority"])
            if row["background"] == "yes":
                background.add(deff_id)
    return prio, background
def deff_holds():
    """Each decoded deff's hold tail [FUN_0103058c / FUN_0002108c(n, 0x20)]: the ticks from its last priority-0x20
    op to its end (rom/rom_data/dmd/deff_ops/deff_NNN.json, agent A's op lists; QA F7). {} without them."""
    holds = {}
    folder = os.path.join(ROM, "rom_data", "dmd", "deff_ops")
    if os.path.isdir(folder):
        import json                         # noqa: PLC0415
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json") or "__" in name:     # a variant's own: deff_variant
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                d = json.load(f)
            prio = [o for o in d.get("ops", ()) if o.get("op") == "prio" and o.get("prio") == HOLD_PRIORITY]
            if prio and d.get("end_tick") is not None:
                holds[d["deff"]] = d["end_tick"] - prio[-1]["t"]
            elif d.get("end_tick") is not None:
                holds[d["deff"]] = 0          # no priority drop in its code: it keeps its priority to the end
    return holds


HOLD_TICKS_BY_DEFF = deff_holds()


def deff_drops():
    """The deffs whose priority drops to 0x20 long before their end (more than HOLD_TICKS): tick of the drop from
    the deff's start, the same in every variant (deff 140: tick 105, 0x0100b90c). {} without the op lists."""
    drops = {}
    folder = os.path.join(ROM, "rom_data", "dmd", "deff_ops")
    if os.path.isdir(folder):
        import json                         # noqa: PLC0415
        for name in sorted(os.listdir(folder)):
            if name.endswith(".json") and "__" not in name:
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    d = json.load(f)
                prio = [o["t"] for o in d.get("ops", ()) if o.get("op") == "prio" and o.get("prio") == HOLD_PRIORITY]
                if prio and d.get("end_tick") is not None and d["end_tick"] - prio[-1] > HOLD_TICKS:
                    drops[d["deff"]] = prio[-1]
    return drops


HOLD_AT_BY_DEFF = deff_drops()
_VARIANTS = {}
VARIANT_TIMING = {}     # (deff, variant) -> (hold ticks, drop tick or None): the variant's own priority 0x20 ops


def deff_variant(deff_id, name):
    """A deff's run for one set of arguments, from the ROM extraction's op list
    rom/rom_data/dmd/deff_ops/deff_NNN__<name>.json (the deff's code run with those arguments): its length
    (end_tick), the sounds and lamp effects its code starts. None without that op list. Deff 94 picks its
    animation by the shots left (+0x34, table 0x040c6a60 [0x010189a8]): shots1..8, and final on completion."""
    key = (deff_id, name)
    if key not in _VARIANTS:
        path = os.path.join(ROM, "rom_data", "dmd", "deff_ops", "deff_%03d__%s.json" % (deff_id, name))
        info = None
        if name and os.path.exists(path):
            import json                     # noqa: PLC0415
            from tf.os_layer import TICK    # noqa: PLC0415
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            info = media_table.DeffInfo(deff_id, "deff_%03d__%s" % (deff_id, name))
            info.seconds = (d.get("end_tick") or 0) * TICK
            ops = d.get("ops", ())
            info.sounds = [(o["t"] * TICK, int(o["call"])) for o in ops if o.get("op") == "sound"]
            info.leffs = [int(o["leff"]) for o in ops if o.get("op") == "leff" and not o.get("t")]
            prio = [o["t"] for o in ops if o.get("op") == "prio" and o.get("prio") == HOLD_PRIORITY]
            end = d.get("end_tick")
            if prio and end is not None:
                early = [t for t in prio if end - t > HOLD_TICKS]
                VARIANT_TIMING[key] = (end - prio[-1], early[0] if early else None)
        _VARIANTS[key] = info
    return _VARIANTS[key]
# the drop's own condition: deff 140 drops only with adj 69 MEGATRON M.B. VIRTUAL LOCK = NO (adj_get(0x45) == 0
# [0x0100b8f8]); the op lists were run at factory settings
HOLD_AT_IF = {140: lambda os_: not os_.adj[69]}


def deff_flags():
    """Each deff's flags word from tf_180's deff table 0x040ce7c4 (rom/rom_data/dmd/deffs.csv)."""
    flags = {}
    path = os.path.join(ROM, "rom_data", "dmd", "deffs.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                flags[int(row["deff"])] = int(row["flags"] or "0", 16)
    return flags


PREVALID_PRIO = 0x10        # priority of the score display rule that runs until the playfield is valid


class Show:
    __slots__ = ("task_id", "deff_id", "threshold", "timeout", "on_start", "on_end", "queued_at", "deff_args")

    def __init__(self, task_id, deff_id, threshold, timeout, on_start, on_end, queued_at, deff_args):
        self.task_id, self.deff_id, self.threshold, self.timeout = task_id, deff_id, threshold, timeout
        self.on_start, self.on_end, self.queued_at, self.deff_args = on_start, on_end, queued_at, deff_args


# the show deffs started by task_sleep_user_6480 [0x01006480] (battle and multiball intros, 140, 149, 146, 43):
# one flipper button held and the other pressed ends the deff (deff_stop) while its priority is above 0x20 (QA V-ENG4)
SKIPPABLE = frozenset((0x8c, 0x45, 0x4b, 0x51, 0x54, 0x55, 0x78, 0x6c, 0x68, 0x5c, 0x74, 0x70, 100, 0x60, 0x39, 0x3f,
                       0x95, 0x2b, 0x92))
FLIPPER_BUTTONS = ("s_l_flipper_button", "s_r_flipper_button")


class Display:

    def __init__(self, os_):
        self.os = os_
        sc = os_.machine.switch_controller
        for i, name in enumerate(FLIPPER_BUTTONS):
            if name in os_.machine.switches:
                sc.add_switch_handler(name, (lambda other: lambda: self._flipper_skip(other))(FLIPPER_BUTTONS[1 - i]))
        self.media = media_table.load(PKG)
        self.prio, self.background = deff_table()
        self.flags = deff_flags()
        self.own_sounds = set()     # (deff, call) a feature plays itself, with its argument: not again from the op list
        self.fg = None              # running foreground deff id
        self.show_held = False      # a show ended in this deff's hold: its rules refresh is due at its exit
        self.arcade_held = False    # ... the RULES_HOLD_SHOW show: the score display comes back at its exit
        self.fg_prio = 0            # its priority (HOLD_PRIORITY in its last 10 ticks)
        self.fg_handle = None
        self.bg = None              # running background deff id
        self.shows = []             # waiting Show entries
        self.show = None            # Show playing now
        self._sound_handles = []
        self._pump_handle = None
        self.idle_waits = []        # [task_id, deff_id, deadline, on_end, deff_args] (when_idle)
        # Background deff rules (lamp_rule_init list 2, os.deff_rule): (priority, cond, deff, music, on_start).
        # The true rule with the highest priority owns the background deff and the music; without one, the
        # score display (deff 19) runs with the OS base music (os.base_music()).
        self.rules = []
        self.fg_info = None         # the running foreground deff's DeffInfo (its variant's, deff_variant)
        self.hold_tail = {}         # deff id -> seconds of its hold when not HOLD_TICKS (set_hold_tail)
        self.music = None           # music call the background rules last played

    # ------------------------------------------------------------------ start / stop

    def start(self, deff_id, hold=False, refresh=True, run_seconds=None, sounds=None, media=False, variant=None,
              **args):
        """run_seconds: the run length when this call's variant differs from the recorded one.
        variant: the op list of this call's arguments (deff_variant), which gives the length, sounds and leffs.
        media: a held deff still plays its own sounds and lamp effects (deff 4, which runs until stopped).
        sounds: [(offset s, fn)] the deff's own sound calls when the rules make them (snd_play2 with an
        argument, a counter), played instead of the capture's sounds once the deff gets the display."""
        os_ = self.os
        os_.shaker_deff(deff_id)        # the deffs that run the shaker (shaker_run in the deff function)
        if deff_id in self.background:
            if self.bg not in (None, deff_id):
                os_.media.deff_stop(self.bg)
            self.bg = deff_id
            if self.is_rule_deff(deff_id):
                os_.trace.log("deff_start", id=deff_id, rule=1)   # a deff rule's deff (ROM caller 0x19944)
            else:
                os_.trace.log("deff_start", id=deff_id)
            os_.machine.events.post("tf_deff_{}".format(deff_id), **args)
            os_.media.deff_start(deff_id, self.prio.get(deff_id, 0), **args)
            return True
        os_.trace.log("deff_start", id=deff_id)    # the ROM trace logs every start call
        new_prio = self.prio.get(deff_id, 0)
        # deff_start_core [0x00020498]: an equal priority replaces the running deff only when its flags & 3
        if self.fg is not None and (self.fg_prio > new_prio or (
                self.fg_prio == new_prio and not self.flags.get(self.fg, 0) & 3)):
            # a higher priority deff keeps the display; the deff rules still run and restart a mode's
            # background deff (traces/disc_multiball.jsonl: deff 48 refused behind deff 50, deff 47 again)
            if refresh and not self.show and self.mode_bg():
                os_.after(1, lambda: self.mode_bg() and self.start(self.mode_bg(), refresh=False))
            return False
        # the show task waits for its own deff [0x01006350]: another effect replacing it ends the show
        # (traces/optimus_decepticon.jsonl: the jackpots replace intro deff 63, the Allspark ejects at once)
        replaced = self.show if self.show is not None and self.fg == self.show.deff_id != deff_id else None
        self._end_fg(stopped=True)
        if self.bg is not None:
            os_.media.deff_stop(self.bg)
        self.fg = deff_id
        self.fg_prio = self.prio.get(deff_id, 0)
        self.bg = None
        os_.machine.events.post("tf_deff_{}".format(deff_id), **args)
        os_.media.deff_start(deff_id, self.prio.get(deff_id, 0), variant=variant, **args)
        info = deff_variant(deff_id, variant) or self.media.get(deff_id)
        self.fg_info = info
        if info:
            seconds = run_seconds or info.seconds
            forced = os_.forced.get("deff_{}_seconds".format(deff_id))
            if forced:
                seconds = forced.pop(0) or seconds   # random length (e.g. the arcade reel), from a test
            if not hold or media:
                # the deff's own code starts its media once it runs: nothing if it is replaced at once
                self._sound_handles.append(os_.machine.clock.schedule_once(
                    lambda: self._media(deff_id, seconds, sounds), 0))
            if not hold and seconds:
                self.fg_handle = os_.machine.clock.schedule_once(lambda: self._ended(deff_id), seconds)
                from tf.os_layer import TICK
                hold_ticks = HOLD_TICKS_BY_DEFF.get(deff_id, HOLD_TICKS)
                drop = HOLD_AT_BY_DEFF.get(deff_id)
                if variant and (deff_id, variant) in VARIANT_TIMING:
                    hold_ticks, drop = VARIANT_TIMING[(deff_id, variant)]
                hold_at = seconds - self.hold_tail.get(deff_id, hold_ticks * TICK)
                if drop is not None and deff_id not in self.hold_tail \
                        and HOLD_AT_IF.get(deff_id, lambda o: True)(os_):
                    hold_at = drop * TICK     # a drop counted from the start (deff 140; deff 83 animations 7, 8, 10)
                self._sound_handles.append(os_.machine.clock.schedule_once(
                    lambda: self._hold(deff_id), max(0.0, hold_at)))
        if replaced is not None and self.show is replaced:
            self.show = None
            self.os.ball_search_reload()            # the show task's end (below, _end_show)
            if replaced.on_end:
                replaced.on_end()
            self._pump()
        if refresh and not self.show:
            os_.after(1, self.refresh)
        return True

    def _media(self, deff_id, seconds=None, sounds=None):
        """The deff's lamp effects, sounds and tube shows at their offsets. A capture can hold more than
        one run of the effect (deff 115 recorded two skipped stages back to back: 0x109 at 0 and 3.1 s);
        only what falls inside this run's length plays."""
        if self.fg != deff_id:
            return
        os_ = self.os
        info = self.fg_info or self.media[deff_id]
        for leff in info.leffs:
            os_.leff_start(leff)
        if sounds is not None:
            events = [(t, "call", fn) for t, fn in sounds]
        else:
            events = [(t, "sound", c) for t, c in info.sounds
                      if (not seconds or t < seconds) and (deff_id, c) not in self.own_sounds]
        events += [(t, "tube", n) for t, n in info.tubes if not seconds or t < seconds]
        for offset, kind, value in sorted(events, key=lambda e: e[0]):
            fire = (lambda k, v: lambda: self.fg == deff_id and (
                self._deff_sound(v, deff_id) if k == "sound" else v() if k == "call" else os_.tube_start(v)))(
                kind, value)
            if offset <= 0:
                fire()
            else:
                self._sound_handles.append(os_.machine.clock.schedule_once(fire, offset))

    def _hold(self, deff_id):
        """Last 10 ticks of deff_id (cancelled with it when it is replaced): its priority drops to 0x20,
        so any deff can replace it, and a show task (waiting for priority < 0x21) ends here
        [deff_start_user_6350 0x01006350]; its rules pass restarts a mode's background deff behind the
        held deff (traces/end_of_line_multiball.jsonl: deff 57 at the hold of deff 56 and at its end)."""
        self.fg_prio = HOLD_PRIORITY
        if not self.show and deff_id in self.hold_tail:
            # a measured hold (set_hold_tail): its rules pass restarts the mode's background deff behind
            # it (traces/quorra_multiball: deff 65 again 2.78 s into deff 68)
            if self.os.in_play and self.bg not in (None, 19):
                self.start(self.bg, refresh=False)
            self.os.request_refresh()
        if self.show:
            # the show's rules refresh request is served once the deff exits (traces/gem_hurryup.jsonl:
            # one tube 18 start as deff 76 ends; disc_multiball.jsonl 40.03 s: one tube 43 as deff 48
            # ends), except for the RULES_HOLD_SHOW show, whose end the deferred rules wait for (inherited
            # from the Tron model, Tron traces; not read in tf_180's code)
            if self.show.task_id == RULES_HOLD_SHOW:
                self.os.request_refresh()
                self.arcade_held = True
            else:
                self.show_held = True
            show, self.show = self.show, None
            self.os.ball_search_reload()
            if show.on_end:
                show.on_end()
            deff_id, _, on_start = self.select()
            # from the priority drop to 0x20 the waiting effect or the score deff 19 takes the DMD (agent A,
            # timing.json priority_changes; deff 140 at tick 105, megatron_autobot 18.71 -> 20.44 s)
            if self.os.in_play:
                self._start_rule(deff_id, on_start)
            self._pump()

    def _flipper_skip(self, other):
        """[0x01006480] loop: a button pressed while the other is held stops the show's deff (0x00006860 /
        0x00006878 read the buttons, 0x00006894 held, 0x000068b4 newly pressed)."""
        sw = self.os.machine.switches.get(other) if hasattr(self.os.machine.switches, "get") else None
        if sw is None or not sw.state or self.fg is None:
            return
        if self.show and self.show.deff_id == self.fg and self.fg in SKIPPABLE and self.fg_prio > HOLD_PRIORITY:
            self.os.deff_stop(self.fg)

    def redraw(self, deff_id, **args):
        """A running deff draws new state (deff 40 after a side change): the ROM's deff function keeps running and
        draws the other screen, so there is no new start in the trace; the slide for the new state plays again
        (tf/media_bridge.py deff_slide) and tf_deff_<id> is posted again, as the PuP Pack sees a new screen."""
        if deff_id not in (self.bg, self.fg):
            return
        self.os.machine.events.post("tf_deff_{}".format(deff_id), **args)
        self.os.media.deff_start(deff_id, self.prio.get(deff_id, 0), **args)

    def stop(self, deff_id):
        os_ = self.os
        os_.trace.log("deff_stop", id=deff_id)
        os_.machine.events.post("tf_deff_{}_stop".format(deff_id))
        if self.fg == deff_id:
            self._end_fg(stopped=True)
            self._after_fg()
        elif self.bg == deff_id:
            self.bg = None
            if self.fg is None:
                self.refresh()                     # the rules' background deff comes back (deff 19)

    def set_media(self, deff_id, seconds, leffs=(), sounds=()):
        """What the rules know of a deff the package has no capture of (no timing.json, or one without an
        end): its run length, the lamp effects and sounds its code starts (read from the reference traces
        by the feature that calls this). A capture with a length wins."""
        info = self.media.get(deff_id)
        if info and info.seconds:
            return
        info = media_table.DeffInfo(deff_id, "deff_%03d" % deff_id)
        info.seconds, info.leffs, info.sounds = seconds, list(leffs), list(sounds)
        self.media[deff_id] = info

    def set_hold_tail(self, deff_id, seconds):
        """deff_hold_frames(n, 0x20) (FUN_0002108c(n, 0x20) [0x0002108c]) when a deff's hold is not the usual 10 ticks: for its last
        `seconds` the deff runs at priority 0x20, so any other deff may replace it (measured per deff)."""
        self.hold_tail[deff_id] = seconds

    def _deff_sound(self, call, deff_id):
        """A deff's own sound. When it is a mode rule's music call (intro deff 64 plays the Quorra music
        0x066), that music is playing, so the rule does not start it again (traces/quorra_multiball)."""
        self.os.sound(call, in_deff=deff_id)
        if any((r[3]() if callable(r[3]) else r[3]) == call for r in self.rules):
            self.music = call
        return True

    def queued(self, task_id):
        """Show task task_id is waiting in the queue (not playing yet)."""
        return any(s.task_id == task_id for s in self.shows)

    def extend(self, deff_id):
        """A running deff that takes new values (e.g. deff 43 on every pop hit) shows its full length again."""
        info = self.media.get(deff_id)
        if self.fg != deff_id or not self.fg_handle or not info or not info.seconds:
            return False
        self.os.machine.clock.unschedule(self.fg_handle)
        self.fg_handle = self.os.machine.clock.schedule_once(lambda: self._ended(deff_id), info.seconds)
        return True

    def running(self, deff_id):
        return deff_id in (self.fg, self.bg)

    def _end_fg(self, stopped=False, exit_handler=True):
        info = (self.fg_info or self.media.get(self.fg)) if self.fg is not None else None
        self.fg_info = None
        if info:
            for leff in info.leffs:                # the deff's exit handler stops its lamp effects
                if self.os.leffs.is_running(leff):
                    self.os.leff_stop(leff)
        if self.fg_handle:
            self.os.machine.clock.unschedule(self.fg_handle)
            self.fg_handle = None
        for handle in self._sound_handles:
            self.os.machine.clock.unschedule(handle)
        self._sound_handles = []
        if self.fg is not None:
            self.os.media.deff_stop(self.fg)
        if self.show_held:
            self.show_held = False
            self.os.request_refresh()
        if exit_handler and info:
            # the deff's exit handler stops the lamp show it started (Tron model; no tf_180 case read); no rules
            # refresh follows (traces/find_flynn_and_items.jsonl 18.15 s: tube 13 stops, no tube 14)
            for _, tube in info.tubes:
                if self.os.tubes.is_running(tube):
                    self.os.tubes.stop(tube)
        self.fg = None
        self.arcade_held = False

    def _ended(self, deff_id):
        self.fg_handle = None
        if self.fg != deff_id:
            return
        arcade_end = self.arcade_held
        self._end_fg()
        # the deff rules restart a mode's background deff when the effect in front of it ends
        # (traces/disc_multiball.jsonl: deff 47 again as deff 48/50 end)
        if self.mode_bg():
            self.start(self.mode_bg(), refresh=False)
            self.os.request_refresh()              # the same rules pass restarts the mode's tube show
        elif arcade_end:
            # the rules pass deferred during the Flynn's Arcade show 0x97 runs at its deff's exit and puts
            # the score display back (traces/flynns_arcade.jsonl 19.36 s: deff 19 as deff 105 ends); without
            # it the screen stayed empty until the next effect
            self.refresh()
        self._after_fg()

    def _after_fg(self):
        if self.show:
            self._end_show()
        self._pump()
        if self.fg is None and self.bg is None:
            # nothing left on the display: the deff rules [0x000178b0] put the background deff back (the
            # score display, or the mode's), as after every effect (traces/flynns_arcade.jsonl 19.36 s,
            # end_of_line_multiball.jsonl 38.60 s: deff 19 as the effect in front ends)
            self.refresh()

    def _end_show(self):
        """The show task [0x01006480] reloads the ball-search countdown when it runs, when its deff starts and
        when the deff is over (observed: game_flow.jsonl, super skill shot deff 43 49.21-51.73 s, no search
        before the drain at 60.47 s)."""
        show, self.show = self.show, None
        self.os.ball_search_reload()
        if show.on_end:
            show.on_end()
        self.refresh()
        self.os.request_refresh()                  # queue_fullscreen_deff: rules_refresh_request at the end

    def add_rule(self, cond, deff_id, music=None, priority=0, on_start=None):
        """lamp_rule_init(list 2): while cond() is true the background deff deff_id runs, with music
        (None/0 = keep; a callable gives the call, e.g. music by mode level). on_start() is called when
        the rule (re)starts the deff (the deff's own code)."""
        self.rules.append((priority, cond, deff_id, music, on_start))
        self.rules.sort(key=lambda r: -r[0])

    def raise_rule(self, deff_id):
        """A mode start re-inserts its rule before the others of its priority (Tron model, inferred), so
        the mode started last shows its deff when several are true (stacked Light Cycle + Quorra)."""
        rule = next(r for r in self.rules if r[2] == deff_id)
        self.rules.remove(rule)
        i = next((k for k, r in enumerate(self.rules) if r[0] <= rule[0]), len(self.rules))
        self.rules.insert(i, rule)

    def is_rule_deff(self, deff_id):
        return any(r[2] == deff_id for r in self.rules)

    def select(self):
        """The true rule with the highest priority: (deff, music, on_start), else the score display."""
        valid = self.os.pf_valid
        for prio, cond, deff_id, music, on_start in self.rules:
            if prio < PREVALID_PRIO and not valid:
                break                              # only the score display rule before validation (inferred)
            if cond():
                return deff_id, music() if callable(music) else music, on_start
        return 19, self.os.base_music(), None

    def _start_rule(self, deff_id, on_start):
        self.start(deff_id, refresh=False)
        if on_start:
            on_start()

    def refresh(self):
        """Deff rules [0x000178b0] after an effect ends: restart the background deff (deff 19 or a mode's)
        behind whatever runs, in normal play."""
        if self.os.in_play and self.bg is None and not self.show:
            deff_id, _, on_start = self.select()
            self._start_rule(deff_id, on_start)

    def mode_bg(self):
        """The mode background deff the rules select now (None: the score display)."""
        deff_id = self.select()[0] if self.os.in_play else 19
        return None if deff_id == 19 else deff_id

    def rules_refresh(self):
        """Rules refresh: a change of the selected rule starts its background deff and its music."""
        os_ = self.os
        if not os_.in_play:
            return
        deff_id, music, on_start = self.select()
        changed = deff_id != self.bg and (self.bg is not None or deff_id != 19)
        if changed:
            self._start_rule(deff_id, on_start)
        if music and music != self.music:
            if not changed and deff_id == 19:
                self.start(19, refresh=False)       # the ROM restarts the score display with new music
            self.music = music
            os_.sound(music)

    def clear(self):
        """Ball end / game end: drop the queue and the foreground deff (no trace event)."""
        self.shows = []
        self.show = None
        self.music = None
        self.idle_waits = []
        self._end_fg(exit_handler=False)
        if self._pump_handle:
            self.os.machine.clock.unschedule(self._pump_handle)
            self._pump_handle = None

    # ------------------------------------------------------------------ mode totals (tasks 0x4d-0x58)

    def when_idle(self, task_id, deff_id, timeout=SHOW_TIMEOUT, on_end=None, on_start=None, **deff_args):
        """FUN_0100fd88, used by the mode TOTAL tasks 0x4d-0x58: wait until no show task runs, no
        foreground deff is on screen and this is the oldest such task waiting, then play deff_id;
        on_end() runs when it is over (or when the wait times out). tf_180 [0x0100664c] reloads the ball-search
        countdown when it is called and again when its deff starts (observed: battle_blackout, total deff 103 at
        66.04 s, ball search 10.1 s later)."""
        from tf.os_layer import TICK
        self.os.ball_search_reload()
        self.idle_waits = [w for w in self.idle_waits if w[0] != task_id]
        if on_start:
            deff_args["_on_start"] = on_start
        self.idle_waits.append([task_id, deff_id, self.os.now + timeout * TICK, on_end, deff_args])
        if len(self.idle_waits) == 1:
            self._idle_tick()

    def _idle_tick(self):
        from tf.os_layer import TICK
        now = self.os.now
        for w in [w for w in self.idle_waits if now > w[2]]:
            self.idle_waits.remove(w)
            if w[3]:
                w[3]()
        if not self.idle_waits:
            return
        if self.fg is None and not self.show_running():
            task_id, deff_id, _, on_end, args = self.idle_waits.pop(0)
            args = dict(args)
            on_start = args.pop("_on_start", None)
            self.start(deff_id, **args)
            if on_start:
                on_start()
            self.os.ball_search_reload()
            info = self.media.get(deff_id)
            if on_end:
                self.os.machine.clock.schedule_once(lambda: on_end(), info.seconds if info else 0)
        if self.idle_waits:
            self.os.machine.clock.schedule_once(self._idle_tick, TICK)

    # ------------------------------------------------------------------ show queue

    def queue(self, task_id, deff_id, timeout=SHOW_TIMEOUT, threshold=SHOW_THRESHOLD, on_start=None,
              on_end=None, **deff_args):
        self.shows = [s for s in self.shows if s.task_id != task_id]
        if self.show is not None and self.show.task_id == task_id:
            # task_start kills the running show task of that id and its effect: the new one plays at once
            # (traces/megatron_decepticon.jsonl: each BALL n LOCKED replaces the previous one, task 0x73)
            old, self.show = self.show, None
            if self.fg == old.deff_id:
                self._end_fg(stopped=True)
        self.shows.append(Show(task_id, deff_id, threshold, timeout, on_start, on_end, self.os.now, deff_args))
        self.os.ball_search_reload()
        # FUN_0000b698 takes the first show task in the OS task list, i.e. the oldest one waiting
        # (traces/end_of_line_multiball.jsonl: task 0x87 deff 139, then 0x83 deff 133, then 0x97).
        # The show task first runs once its caller has finished (a deff the caller starts right after
        # queueing, e.g. deff 55 after the extra ball show 0x82, is on screen first).
        if self._pump_handle is None and (not self.show or threshold != SHOW_THRESHOLD):
            self._pump_handle = self.os.machine.clock.schedule_once(self._pump_tick, 0)

    def cancel(self, task_id):
        self.shows = [s for s in self.shows if s.task_id != task_id]

    def task_running(self, task_id):
        """task_running(id) for a show task: waiting in the queue or playing."""
        return bool(self.show and self.show.task_id == task_id) or any(s.task_id == task_id for s in self.shows)

    def show_running(self):
        """task_running_range(0x81, 0xa7): a show task is waiting or playing."""
        return bool(self.show or self.shows)

    def _pump(self):
        if self._pump_handle:
            self.os.machine.clock.unschedule(self._pump_handle)
            self._pump_handle = None
        if self.show and self.shows and self.shows[0].threshold != SHOW_THRESHOLD and self.fg is not None \
                and self.fg_prio < self.shows[0].threshold:
            # a show waiting on its own priority (a multiball intro) does not wait for the show playing below it
            # (traces/megatron_decepticon.jsonl 29.65 s: intro deff 75 over the lock show's deff 140)
            old, self.show = self.show, None
            if old.on_end:
                old.on_end()
        if self.show or not self.shows:
            return
        from tf.os_layer import TICK
        now = self.os.now
        self.shows = [s for s in self.shows if now - s.queued_at <= s.timeout * TICK]
        if not self.shows:
            return
        first = self.shows[0]
        if self.fg is None or self.fg_prio < first.threshold:
            self.shows.pop(0)
            self.show = first
            self.start(first.deff_id, refresh=False, **first.deff_args)
            self.os.ball_search_reload()
            if first.on_start:
                first.on_start()
            self.os.request_refresh()            # rules that wait for this show's deff (e.g. a mode intro)
            if self.fg is None:                  # deff without a recorded length
                self._after_fg()
            return
        self._pump_handle = self.os.machine.clock.schedule_once(self._pump_tick, TICK)

    def _pump_tick(self):
        self._pump_handle = None
        self._pump()


class Tubes:
    """Tron's ramp light tube shows; Transformers has none, so every show is refused (kept for the OS calls)."""

    def __init__(self, os_):
        self.os = os_

    def is_running(self, show_id):
        return False

    def start(self, show_id):
        return False

    def stop(self, show_id, log=True):
        pass

    def clear(self):
        pass


UNCLAIMED = set()    # leffs that pulse a flasher themselves without owning it (Tron: leff 76)


class Leffs:
    """Flasher ownership of lamp-matrix effects (rom/rom_data/io/lamp_effects.csv: coils pulsed, priority, length;
    without it, the priorities of game/config/interim/leffs.csv and no flashers).

    Lamps are drawn in priority layers, so they never conflict (leff 99 starts under leff 52), but a
    leff start is refused while a running leff with a higher priority uses one of its flashers (a
    running lower one keeps running). When an effect ends or stops, the lamp rules start a refused rule
    leff that can run now (logged again; traces/recognizer_and_disc_battle.jsonl: leff 107 behind leff
    108; disc_multiball_restart.jsonl: leff 54 behind leff 52). Rule leffs run until the rule stops them.
    """

    def __init__(self, os_):
        self.os = os_
        self.info = {}
        from tf.lamps import leff_rows     # noqa: PLC0415 (lamps imports the OS layer)
        rows = leff_rows(ROM)
        for row in rows:
            leff_id = int(row["leff"])
            outputs = frozenset(row["coils_pulsed"].split()) if leff_id not in UNCLAIMED else frozenset()
            length = float(row["run_ms"]) / 1000 if row["loops"] != "yes" and row["run_ms"] else None
            self.info[leff_id] = (outputs, int(row["priority"] or 0), length)
        if not rows:
            with open(os.path.join(INTERIM, "leffs.csv"), encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.info[int(row["leff"])] = (frozenset(), int(row["priority"]), None)
        self.running = {}           # leff id -> end handle (or None)
        self.pending = []           # refused lamp-rule leffs, started when an effect ends
        # leff_start's conflict test [0x00007c10] (QA L-G04): the leff table's lamp group (+6, lamp_group_9570
        # [0x00009570] over table 0x040d1510) and coil group (+8, leff_start_sub_611c [0x0000611c] over table
        # 0x040cf65c) and flags (+4, bit 2: an equal-priority leff may replace it)
        import json                         # noqa: PLC0415
        groups = {}
        for name in ("lamp_groups", "coil_groups"):
            path = os.path.join(ROM, "rom_data", "io", name + ".json")
            groups[name] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        self.claims = {}
        for row in rows:
            lamps_ = frozenset(groups["lamp_groups"].get(str(int(row["lamp_group"] or 0)), ()))
            coils_ = frozenset(groups["coil_groups"].get(str(int(row["coil_group"] or 0)), ()))
            self.claims[int(row["leff"])] = (lamps_, coils_, int(row["flags"] or "0", 16))

    def is_running(self, leff_id):
        return leff_id in self.running

    def _conflicts(self, leff_id):
        """The running leffs sharing a lamp of its lamp group or a coil of its coil group [0x00007c10]."""
        lamps_, coils_, _ = self.claims.get(leff_id, (frozenset(), frozenset(), 0))
        if not lamps_ and not coils_:
            return []
        out = []
        for other in self.running:
            if other == leff_id:
                continue        # the same leff restarts (the game stops it first, as leaf_b780 / b7e4 callers do)
            o_lamps, o_coils, _ = self.claims.get(other, (frozenset(), frozenset(), 0))
            if o_lamps & lamps_ or o_coils & coils_:
                out.append(other)
        return out

    def _refused_by(self, leff_id, other):
        """[0x00007c10]: refused by a conflicting running leff of a higher priority, or of the same priority
        whose flags lack bit 2 (may be replaced)."""
        prio = self.info.get(leff_id, (frozenset(), 0, None))[1]
        o_prio = self.info.get(other, (frozenset(), 0, None))[1]
        return prio < o_prio or (prio == o_prio and not self.claims.get(other, (0, 0, 0))[2] & 2)

    def blocked(self, leff_id):
        outputs, prio, _ = self.info.get(leff_id, (frozenset(), 0, None))
        if any(self._refused_by(leff_id, other) for other in self._conflicts(leff_id)):
            return True
        return any(other != leff_id and o_out & outputs and o_prio > prio
                   for other in self.running for o_out, o_prio, _ in (self.info.get(other, (frozenset(), 0, None)),))

    def flasher_outranked(self, leff_id, flasher):
        """A running leff with a higher priority than `leff_id` uses `flasher` (lamp_effects.csv)."""
        prio = self.info.get(leff_id, (frozenset(), 0, None))[1]
        return any(other != leff_id and flasher in self.info.get(other, (frozenset(), 0, None))[0]
                   and self.info[other][1] > prio for other in self.running)

    def start(self, leff_id, loop=False, lamp=None):
        """lamp: the lamp(s) a token effect draws (tf.lamps: the show's "(lamp)" token)."""
        if self.blocked(leff_id):
            if loop and leff_id not in self.pending:
                self.pending.append(leff_id)
            return False
        for other in self._conflicts(leff_id):       # the conflicting lower (or replaceable) leffs are killed
            self.os.leff_stop(other)
            if any(r[1] == other and r[3] for r in self.os.rules) and other not in self.pending:
                self.pending.append(other)          # its rule starts it again once it can run (game_flow.md 5.8)
        self.stop(leff_id)
        length = self.info.get(leff_id, (None, None, None))[2]
        handle = None
        if length and not loop and leff_id not in self.os.lamps.code_leffs:   # a code leff ends itself
            handle = self.os.machine.clock.schedule_once(lambda: self._ended(leff_id), length)
        self.running[leff_id] = handle
        self.os.lamps.leff_play(leff_id, lamp)      # its captured lamp show, on a layer at its priority
        return True

    def _ended(self, leff_id):
        self.running.pop(leff_id, None)
        self.os.lamps.leff_end(leff_id)
        self._retry()

    def _retry(self):
        """Outputs were freed: the lamp rules run again and start a refused rule leff that can run now."""
        if any(not self.blocked(p) for p in self.pending):
            from tf.os_layer import TICK
            self.os.machine.clock.schedule_once(lambda: self.os.rules_refresh(leffs_only=True), TICK / 2)

    def kill_all(self):
        """Every leff task killed with the other tasks (game start): no leff_stop is logged."""
        for handle in self.running.values():
            if handle:
                self.os.machine.clock.unschedule(handle)
        self.running.clear()
        self.pending = []
        self.os.lamps.leff_lamps_end()

    def retry_due(self, leff_id):
        return leff_id in self.pending and not self.blocked(leff_id)

    def stop(self, leff_id):
        if leff_id in self.pending:
            self.pending.remove(leff_id)
        if leff_id not in self.running:
            return
        handle = self.running.pop(leff_id)
        if handle:
            self.os.machine.clock.unschedule(handle)
        self.os.lamps.leff_end(leff_id)
        self._retry()
