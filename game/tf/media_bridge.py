"""Sends the rules' display effects and sound calls to the Godot media controller (GMC) over BCP.

The OS layer reports every deff start/stop and sound call here. Slides and sounds come from
scripts/gen_media.py (game/slides/deffs, game/sounds, game/tf/media_data.json). Without that data
or without a connected GMC (unit tests), nothing is sent.

- deff N -> slide "deff_NNN" at the deff's ROM priority; text lines with values are formatted from
  the deff's ROM text (event_map.csv rom_text) and its arguments.
- sound call N -> one sample of pool N (sounds.yaml), on the call's track (voice, sfx, music). Music
  calls replace the running music. Calls 0x01-0x08 are the ROM's channel stops.
"""
import json
import os
import re

CONTEXT = "tf_media"
SERVICE_PRIORITY = 1000         # the service slide covers every deff (ROM priorities are 0-255)
TICK = 0.01626                                     # seconds per ROM tick (os_layer.TICK)
SPEC = re.compile(r"%(P\d/[^%]*%|[-+ #0,]*\d*l?[dus])")
# The values of a deff's printf lines, in the ROM's argument order, for effects whose callers also pass
# arguments the text does not print (the others: every argument not in the deff's "args", in call order).
# Filled per deff as the rules are ported (Tron's table: game/tron/media_bridge.py).
TEXT_ARGS = {}


def format_rom_text(line, args):
    """printf as the ROM's text_printf_msg uses it: %d %u %s, %,02lu (score with commas),
    %P1/a/b/c/% (plural or ordinal pick by the previous number)."""
    args = list(args)
    last = [0]

    def sub(m):
        spec = m.group(1)
        if spec.startswith("P"):
            choices = spec[3:-1].split("/")
            n = last[0]
            if spec[1] == "1" and len(choices) > 2:     # ordinal list: 1-based
                return choices[n - 1] if 0 < n <= len(choices) else ""
            return choices[0] if n == 1 else (choices[2] if len(choices) > 2 else choices[-1])
        value = args.pop(0) if args else 0
        if value is None:
            return ""
        if spec.endswith("s"):
            return str(value)
        try:
            value = int(value)
        except (TypeError, ValueError):            # never print a name or a tuple where the ROM prints a number
            return ""
        last[0] = value
        text = "{:,}".format(value) if "," in spec else str(value)
        flags, width = re.match(r"([-+ #0,]*)(\d*)", spec).groups()
        if width:                                  # %,02lu: score 0 shows "00"; %06d zero-padded
            text = text.rjust(int(width), "0" if "0" in flags or width.startswith("0") else " ")
        return text
    return SPEC.sub(sub, line)


# Deffs drawn live as ROM draw lists from their captured draw calls (tf/score_screen.py)
DRAWN = (19,)


class MediaBridge:

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        path = os.path.join(os.path.dirname(__file__), "media_data.json")
        self.data = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.data = {"pools": {int(k): v for k, v in data["pools"].items()},
                         "deffs": {int(k): v for k, v in data["deffs"].items()}}
        self.music_key = None
        self.service_shown = False
        self.counters = {}
        self._refresh = None
        self.active = set()                        # deffs on screen that draw the status panel or live values
        self.started = {}                          # deff id -> the args of its last start
        # (deff, line, ROM text) of every printf line left blank because the rules gave no value for it
        # (tests/test_dmd_text.py: a value line drawn without its value shows a bare label, "RIGHT SPINNER =")
        self.missing = []
        # the DMD keeps its last frame while no effect draws (the ROM never clears it between effects): the
        # last deff / text slide stays up until the next one plays, never GMC's base slide below them all
        self.shown = set()                         # deff and text slides playing now
        self.kept = None                           # the last one, stopped but left up until the next plays
        self.drawn = set()                         # deffs shown by deff_draw (rom_screen) in place of their frames
        self.drawn_since = {}                      # deff in DRAWN -> when it started
        self.drawn_last = None
        self._drawn_timer = None

    # ------------------------------------------------------------------ transport

    def connected(self, need_data=True):
        bcp = getattr(self.machine, "bcp", None)
        if (need_data and not self.data) or not bcp or not getattr(bcp, "transport", None):
            return False
        return bool(bcp.transport.get_named_client("local_display"))

    def _send(self, name, settings, priority=0, need_data=True, **kwargs):
        """Send a slides_play / sounds_play trigger straight to GMC. MPF's bcp_trigger() only reaches clients
        that registered a handler for the name, and GMC registers none for sounds_play (MPF's own
        sound_player config would): sent that way, every sound was dropped."""
        if not self.connected(need_data):
            return
        bcp = self.machine.bcp
        client = bcp.transport.get_named_client("local_display") if getattr(bcp, "transport", None) else None
        args = dict(name=name, settings=settings, context=CONTEXT, calling_context=CONTEXT, priority=priority,
                    **kwargs)
        if client:
            bcp.interface.bcp_trigger_client(client=client, **args)
        else:                                      # unit tests: a mocked interface, no transport client
            bcp.interface.bcp_trigger(**args)

    # ------------------------------------------------------------------ display effects

    def deff_lines(self, deff_id, args):
        info = self.data["deffs"].get(deff_id) if self.data else None
        if not info:
            return {}
        live = getattr(self.os, "deff_values", {}).get(deff_id)
        if live:                                       # values the deff reads from RAM, now (over the passed ones)
            args = dict(args, **live())
        passed = {k: args[k] for k in info.get("args", []) if k in args}   # e.g. letters for letter_panel.gd
        if not info["text"]:
            return dict(self.panel_args(info), **passed)
        if deff_id in TEXT_ARGS:
            values = [args.get(k) for k in TEXT_ARGS[deff_id]]
        else:
            values = [v for k, v in args.items() if k not in info.get("args", [])]   # not lit/new/screen
        if deff_id == 19:                              # score display: ball number and score
            values = [self.machine.game.player.ball if self.os.game and self.os.game.player else 0,
                      self.os.game.player.score if self.os.game and self.os.game.player else 0]
        out = dict(self.panel_args(info), **passed)
        for i, line in enumerate(info["text"]):
            n = sum(1 for spec in SPEC.findall(line) if not spec.startswith("P"))   # %P picks by the last number
            if n and len(values) < n:              # value not reported by the rules: leave the line blank
                out["line{}".format(i)] = ""
                self.missing.append((deff_id, i, line))
                values = []
                continue
            out["line{}".format(i)] = format_rom_text(line, values[:n])
            values = values[n:]
        return out

    def deff_start(self, deff_id, priority, **args):
        info = self.data["deffs"].get(deff_id) if self.data else None
        if deff_id in DRAWN:                             # drawn live from its draw calls
            self.drawn.add(deff_id)
            self.drawn_since[deff_id] = self.machine.clock.get_time()
            self.drawn_last = self.drawn_screen(deff_id)
            self.text_show("rom_screen", [], priority, draw=self.drawn_last)
            if self._drawn_timer is None and self.connected(need_data=False):
                self._drawn_timer = self.machine.clock.schedule_interval(self.redraw, 0.1)
            return
        if not info:
            return
        slide = info["slide"]
        self.started[deff_id] = args
        if info.get("panel") is not None or deff_id in getattr(self.os, "deff_values", {}):
            self.active.add(deff_id)
            if self._refresh is None and self.connected():   # timer bars move between scores
                self._refresh = self.machine.clock.schedule_interval(self.score_changed, 0.25)
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}})
        self._send("slides_play", {slide: {"action": "play", "key": slide, "expire": None,
                                           "priority": priority}},
                   priority=priority, **self.deff_lines(deff_id, args))
        self._played(slide)

    def deff_stop(self, deff_id):
        info = self.data["deffs"].get(deff_id) if self.data else None
        self.active.discard(deff_id)
        if deff_id in self.drawn:
            self.drawn.discard(deff_id)
            if self._drawn_timer is not None and not self.drawn & set(DRAWN):
                self.machine.clock.unschedule(self._drawn_timer)
                self._drawn_timer = None
            self._remove("rom_screen")
        elif info:
            self._remove(info["slide"])

    def scores(self):
        game = self.os.game
        return [p.score for p in game.player_list] if game else []

    def panel_args(self, info):
        """The live status panel of a deff that draws it (tf/score_screen.py panel_draw, at the deff's level)."""
        if not info or info.get("panel") is None:
            return {}
        from tf import score_screen
        return {"draw": score_screen.panel_draw(self.scores(), self.os.player_num or 1, info["panel"])}

    def drawn_screen(self, deff_id):
        """The screen of a deff in DRAWN (tf/score_screen.py): the score display."""
        from tf import score_screen
        game = self.os.game
        ball = game.player.ball if game and game.player else 1
        ticks = int((self.machine.clock.get_time() - self.drawn_since.get(deff_id, 0)) / TICK)
        return score_screen.score_draw(self.scores(), self.os.player_num or 1, ball, self.credits_text(),
                                       self.replay_text() if game else "", ticks)

    def deff_draw(self, deff_id, priority, draw):
        """A running deff whose next screen its captured frames do not hold (deff 4 dims after 30 s): the ROM
        draw list `draw` (tf/rom_draw.py) on the rom_screen slide (tf/service_screen.gd), in place of the
        deff's frames, until the deff stops."""
        info = self.data["deffs"].get(deff_id) if self.data else None
        if not info:
            return
        self.drawn.add(deff_id)
        self.text_show("rom_screen", [], priority, draw=draw)
        self.shown.discard(info["slide"])
        self._send("slides_play", {info["slide"]: {"action": "remove", "key": info["slide"], "expire": None}},
                   need_data=False)

    def _played(self, slide):
        self.shown.add(slide)
        kept, self.kept = self.kept, None
        if kept and kept != slide:
            self._send("slides_play", {kept: {"action": "remove", "key": kept, "expire": None}}, need_data=False)

    def _remove(self, slide):
        self.shown.discard(slide)
        if not self.shown:
            self.kept = slide                      # nothing else up: its last frame stays (see self.kept)
            return
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}}, need_data=False)

    # ------------------------------------------------------------------ score display (deff 19)

    def credits_text(self):
        """FUN_00004ff4: "FREE PLAY", "CREDITS n", "CREDITS a/b" (coins toward the next credit) or
        "CREDITS n a/b". The credit count comes from the OS when it keeps one (os.credits,
        os.credit_fraction = (coins, coins per credit), os.free_play); 3 coins make a credit."""
        if getattr(self.os, "free_play", False):
            return "FREE PLAY"
        whole = int(getattr(self.os, "credits", 0) or 0)
        num, den = getattr(self.os, "credit_fraction", None) or (getattr(self.os, "coins", 0) % 3, 3)
        if num == 0:
            return "CREDITS %d" % whole
        if whole == 0:
            return "CREDITS %d/%d" % (num, den)
        return "CREDITS %d %d/%d" % (whole, num, den)

    def replay_text(self):
        """FUN_01023704: the current player's first replay level not yet awarded ("REPLAY AT <level>",
        the award text for adj 13 = 0; the other awards' texts are ROM messages not in the package)."""
        level_of = getattr(self.os, "replay_level", None)
        if not level_of:
            return ""
        done = getattr(self.os, "replays_awarded", {}).get(self.os.player_num, set())
        for n in range(1, 5):
            level = level_of(n)
            if level and n not in done:
                return "REPLAY AT " + format_rom_text("%,02lu", [level])
        return ""

    def redraw(self, *_):
        """A drawn deff's screen again (scores, credits, the replay row's phase), sent when it changed."""
        for deff_id in DRAWN:
            if deff_id in self.drawn:
                draw = self.drawn_screen(deff_id)
                if draw != self.drawn_last:
                    self.drawn_last = draw
                    self._send("slides_play", {"rom_screen": {"action": "update", "key": "rom_screen",
                                                              "expire": None}}, need_data=False, draw=draw)

    def score_changed(self, *_):
        """Score flush (and every 0.25 s while a panel shows): refresh the score display and the
        status panel of the effects on screen."""
        self.redraw()
        if not self.data:
            return
        args = None
        for deff_id in sorted(self.active):
            info = self.data["deffs"].get(deff_id)
            live = deff_id in getattr(self.os, "deff_values", {})
            if not info or not (info.get("panel") is not None or live):
                continue
            mine = self.panel_args(info)
            if live:
                # its own lines only: fresh RAM values for a live deff (one effect's lines never go to
                # another: they share the names line0, line1, ...)
                mine.update({k: v for k, v in self.deff_lines(deff_id, self.started.get(deff_id, {})).items()
                             if k.startswith("line") or k == "screen"})
            self._send("slides_play", {info["slide"]: {"action": "update", "key": info["slide"],
                                                       "expire": None}}, **mine)

    # ------------------------------------------------------------------ service menu

    def text_show(self, slide, lines, priority, **extra):
        """Rules text on a generic slide (game/slides/<slide>.tscn, labels line0-line2); needs no generated
        media: the service menu, the attract pages and the initials entry."""
        lines = {"line{}".format(i): text for i, text in enumerate(lines)}
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}}, need_data=False)
        self._send("slides_play", {slide: {"action": "play", "key": slide, "expire": None, "priority": priority}},
                   priority=priority, need_data=False, **lines, **extra)
        self._played(slide)

    def text_hide(self, slide):
        self._remove(slide)

    def service_show(self, lines, draw=None):
        """Service menu screen (tf/service.py), above every deff: the ROM draw list `draw` (tf/rom_draw.py,
        drawn by tf/service_screen.gd) and its text lines."""
        if self.service_shown:          # redrawn in place: a remove and play would show the slides below
            lines = {"line{}".format(i): text for i, text in enumerate(lines)}
            self._send("slides_play", {"service": {"action": "update", "key": "service", "expire": None}},
                       priority=SERVICE_PRIORITY, need_data=False, draw=draw or [], **lines)
            return
        self.text_show("service", lines, SERVICE_PRIORITY, draw=draw or [])
        self.service_shown = self.connected(need_data=False)

    def service_hide(self):
        self.service_shown = False
        self.shown.discard("service")               # the menu goes away: the attract effects take over
        self._send("slides_play", {"service": {"action": "remove", "key": "service", "expire": None}},
                   need_data=False)

    def confirm_show(self, draw):
        """The end-the-game question before the service menu opens in a game (tf/os_layer.py, not in the
        ROM), above every deff."""
        self.text_show("service_confirm", [], SERVICE_PRIORITY, draw=draw)

    def confirm_hide(self):
        self.shown.discard("service_confirm")
        self._send("slides_play", {"service_confirm": {"action": "remove", "key": "service_confirm",
                                                       "expire": None}}, need_data=False)

    # ------------------------------------------------------------------ sounds

    def sound_stop(self, call):
        """Stop every sample of sound call `call` (FUN_0002ceb4)."""
        pool = self.data["pools"].get(call) if self.data else None
        for sample in (pool or {}).get("samples", []):
            self._send("sounds_play", {sample: {"action": "stop", "key": sample}})

    def sound(self, call, index=None):
        if not self.data:
            return
        if 1 <= call <= 8:                             # channel stop
            if self.music_key:
                self._send("sounds_play", {self.music_key: {"action": "stop", "key": self.music_key}})
                self.music_key = None
            return
        pool = self.data["pools"].get(call)
        if not pool:
            return
        samples = pool["samples"]
        if index is not None and index < len(samples):  # the rules picked the sample (sound lengths)
            sample = samples[index]
        elif pool["type"].startswith("random"):
            sample = samples[self.os.random.randrange(len(samples))]
        else:                                          # sequence
            n = self.counters.get(call, 0)
            self.counters[call] = n + 1
            sample = samples[n % len(samples)]
        track = pool["track"]
        settings = {"action": "play", "bus": track, "key": sample}
        if track == "music":
            if self.music_key:
                self._send("sounds_play", {self.music_key: {"action": "stop", "key": self.music_key}})
            self.music_key = sample
            settings["loops"] = -1
        self._send("sounds_play", {sample: settings})
