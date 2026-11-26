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
TICK = 0.016                                     # seconds per ROM tick (os_layer.TICK)
SPEC = re.compile(r"%(P\d/[^%]*%|[-+ #0,]*\d*l?[dius])")     # %i = %d (deff 52 "%iX BONUS"; QA V-TXT3)
# The values of a deff's printf lines, in the ROM's argument order, for effects whose callers also pass
# arguments the text does not print (the others: every argument not in the deff's "args", in call order).
# Filled per deff as the rules are ported (Tron's table: game/tron/media_bridge.py).
TEXT_ARGS = {}


def format_rom_text(line, args, last=None):
    """printf as the ROM's text_printf_msg uses it: %d %u %s, %,02lu (score with commas),
    %P1/a/b/c/% (plural or ordinal pick by the previous number; `last`, a one-item list, carries that number
    from one text of a screen to the next)."""
    args = list(args)
    last = last if last is not None else [0]

    def sub(m):
        spec = m.group(1)
        if spec.startswith("P"):
            # vsprintf [0x0002fef0]: %P1/c1/c2/.../cn//% picks choice n-1 (unsigned), clamped to the last one:
            # "%d COMBO%P1//S/%" gives "1 COMBO", "0 COMBOS", "3 COMBOS" (deff op lists, e.g. deff_044). The
            # caller passes the number again for %P; every live text passes the previous %d's value, so `last`
            # holds it (QA V-TXT1; the tournament texts 36 / 37 pass another value: V-TXT2, not modelled).
            choices = spec[3:-1].split("/")[:-1] or [""]
            n = last[0]
            return choices[min(max(n - 1, 0) if n > 0 else len(choices) - 1, len(choices) - 1)]
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


def format_values(sources, values):
    """The texts of a captured deff's printf slots (media_data "values": their ROM formats, in the order the
    deff draws them) from `values`, the deff's arguments in the ROM's order; a slot whose values are missing
    is None (the slide keeps the capture's string)."""
    values, last, out = list(values), [0], []
    for source in sources:
        n = sum(1 for spec in SPEC.findall(source) if not spec.startswith("P"))
        if len(values) < n:
            out.append(None)
            values = []
            continue
        out.append(format_rom_text(source, values[:n], last))
        values = values[n:]
    return out


CREDIT_LINE_DEFFS = (10, 15, 17)    # deff_017_insert_coins [0x01000000] (scripts/gen_media.py credit_slots)

# Deffs drawn live as ROM draw lists from their captured draw calls (tf/score_screen.py)
DRAWN = (19, 1)      # the score display and the attract pages (tf/attract_pages.py)
DRAWN_SLIDES = {19: "rom_screen", 1: "attract_pages"}


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
        self._panel_last = {}                     # deff -> the panel arguments last sent (sent again only on change)
        self.variant_of = {}                       # deff -> the variant whose slide runs (deff_start)
        self.active = set()                        # deffs on screen that draw the status panel or live values
        self.started = {}                          # deff id -> the args of its last start
        self.slides = {}                           # deff id -> the slide it plays (a side variant: deff_slide)
        # (deff, line, ROM text) of every printf line left blank because the rules gave no value for it
        # (tests/test_dmd_text.py: a value line drawn without its value shows a bare label, "RIGHT SPINNER =")
        self.missing = []
        # the DMD keeps its last frame while no effect draws (the ROM never clears it between effects): the
        # last deff / text slide stays up until the next one plays, never GMC's base slide below them all
        self.shown = set()                         # deff and text slides playing now
        self.kept = None                           # the last one, stopped but left up until the next plays
        self.drawn = set()                         # deffs shown by deff_draw (rom_screen) in place of their frames
        self.drawn_since = {}                      # deff in DRAWN -> when it started
        self.drawn_last = {}
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
        if deff_id in CREDIT_LINE_DEFFS:               # [0x01000000]: the credit line and PRESS START / INSERT COINS
            args = dict(args, slot_texts={0: self.credits_text(), 1: "PRESS START" if self.can_start() else
                                          "INSERT COINS"})
        passed = {k: args[k] for k in info.get("args", []) if k in args}   # e.g. letters for letter_panel.gd
        own = (info.get("variant_values") or {}).get(self.variant_of.get(deff_id))
        sources, sites = (own["values"], own["sites"]) if own else (info.get("values"), info.get("sites"))
        if sources:                                    # captured printf texts drawn live (tf/deff_values.gd)
            values = args.get("values") or []
            if args.get("site_values") is not None and sites:   # by the printf's call site in the deff's code
                values = [args["site_values"].get(site) for site in sites]
            passed["values"] = format_values(sources, values)
            for slot, text in (args.get("slot_texts") or {}).items():   # a fixed message drawn in a slot's place
                if slot < len(passed["values"]):
                    passed["values"][slot] = text
            for slot, text in zip(sources, passed["values"]):
                if text is None:
                    self.note_missing(deff_id, "slot", slot)
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
                self.note_missing(deff_id, i, line)
                values = []
                continue
            out["line{}".format(i)] = format_rom_text(line, values[:n])
            values = values[n:]
        return out

    def note_missing(self, deff_id, where, text):
        """A printf text the rules gave no value for (the capture's string shows). TF_MISSING_VALUES=<file>
        appends them there, one per line, to list what the rules still have to pass."""
        self.missing.append((deff_id, where, text))
        path = os.environ.get("TF_MISSING_VALUES")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write("{}\t{}\t{}\n".format(deff_id, where, text))

    def deff_start(self, deff_id, priority, variant=None, **args):
        """variant: the state the deff runs with (tf/display.py deff_variant): its own slide when the package has
        that variant's frames (media_data "variants")."""
        info = self.data["deffs"].get(deff_id) if self.data else None
        if deff_id in DRAWN:                             # drawn live from its draw calls
            self.drawn.add(deff_id)
            self.drawn_since[deff_id] = self.machine.clock.get_time()
            self.drawn_last[deff_id] = self.drawn_screen(deff_id)
            self.text_show(DRAWN_SLIDES[deff_id], [], priority, draw=self.drawn_last[deff_id])
            if self._drawn_timer is None and self.connected(need_data=False):
                self._drawn_timer = self.machine.clock.schedule_interval(self.redraw, TICK)   # blink, fade
            return
        if not info:
            return
        slide = (info.get("variants") or {}).get(variant) if variant else None
        self.variant_of[deff_id] = variant if slide else None     # its own printf slots (deff_lines)
        slide = slide or self.deff_slide(info)
        old = self.slides.get(deff_id)
        if old not in (None, slide):               # the other side's slide of the same deff (a side change)
            self._remove(old)
        self.slides[deff_id] = slide
        self.started[deff_id] = args
        if info.get("panel") is not None or deff_id in getattr(self.os, "deff_values", {}):
            self.active.add(deff_id)
            self._panel_last.pop(deff_id, None)
            # the deff's code draws the panel every frame (draw_way_palette_identity_2f200 [0x0102f200]: the score
            # box blink, the award fade, the combo slide, timer bars): checked every tick, sent when it changed
            # (QA V-SC11)
            if self._refresh is None and self.connected():
                self._refresh = self.machine.clock.schedule_interval(lambda *_: self.panels_refresh(), TICK)
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}})
        self._send("slides_play", {slide: {"action": "play", "key": slide, "expire": None,
                                           "priority": priority}},
                   priority=priority, **self.deff_lines(deff_id, args))
        self._played(slide)

    def deff_slide(self, info):
        """The slide of a deff that draws the player's side (deff 40, 41: media_data "sides", scripts/gen_media.py
        SIDE_VARIANTS) for the current player's side; else the deff's one slide."""
        sides = info.get("sides")
        if sides and self.os.game:
            return sides.get(str(self.os.pd.get("side")), info["slide"])
        return info["slide"]

    def deff_stop(self, deff_id):
        info = self.data["deffs"].get(deff_id) if self.data else None
        self.active.discard(deff_id)
        if deff_id in self.drawn:
            self.drawn.discard(deff_id)
            if self._drawn_timer is not None and not self.drawn & set(DRAWN):
                self.machine.clock.unschedule(self._drawn_timer)
                self._drawn_timer = None
            self._remove(DRAWN_SLIDES.get(deff_id, "rom_screen"))
        elif info:
            self._remove(self.slides.pop(deff_id, info["slide"]))

    def scores(self):
        game = self.os.game
        return [p.score for p in game.player_list] if game else []

    def panel_args(self, info):
        """The live status panel of a deff that draws it (tf/score_screen.py panel_draw, at the deff's level)."""
        if not info or info.get("panel") is None:
            return {}
        from tf import score_screen
        return {"draw": score_screen.panel_draw(self.scores(), self.os.player_num or 1, info["panel"],
                                                **self.status_args())}

    def status_args(self):
        """The status counters, game state and playfield-valid flag the score drawing reads [0x0102f200]."""
        status = getattr(self.os, "status", None)
        return {"status": (status, self.machine.clock.get_time()) if status else None,
                "state": getattr(self.os, "state", 0), "valid": getattr(self.os, "pf_valid", False)}

    def drawn_screen(self, deff_id):
        """The screen of a deff in DRAWN: the score display (tf/score_screen.py), the attract pages
        (tf/attract_pages.py, with the status panel in attract state: the last game's scores)."""
        from tf import score_screen
        if deff_id == 1:
            from tf import attract_pages
            walker = getattr(self.os, "attract_walker", None)
            if walker is None:
                return []
            panel = score_screen.panel_draw(list(getattr(self.os, "last_scores", []) or []), 0, state=0x10)
            return attract_pages.screen(self.os, walker.entry, walker.tick(self.machine.clock.get_time()), panel)
        game = self.os.game
        ball = game.player.ball if game and game.player else 1
        ticks = int((self.machine.clock.get_time() - self.drawn_since.get(deff_id, 0)) / TICK)
        return score_screen.score_draw(self.scores(), self.os.player_num or 1, ball, self.credits_text(),
                                       self.replay_text() if game else "", ticks, **self.status_args())

    def deff_draw(self, deff_id, priority, draw):
        """A running deff whose next screen its captured frames do not hold (deff 4 dims after 30 s): the ROM
        draw list `draw` (tf/rom_draw.py) on the rom_screen slide (tf/service_screen.gd), in place of the
        deff's frames, until the deff stops."""
        info = self.data["deffs"].get(deff_id) if self.data else None
        if not info:
            return
        self.drawn.add(deff_id)
        self.text_show("rom_screen", [], priority, draw=draw)
        slide = self.slides.get(deff_id, info["slide"])
        self.shown.discard(slide)
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}}, need_data=False)

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
        """FUN_000044a4: "FREE PLAY", "CREDITS n", "CREDITS a/b" (coins toward the next credit) or
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

    def can_start(self):
        """leaf_19988 [0x00019988]: free play (0x00004464: the pricing's adjustment is 1), else the credit record's
        +4 (0x000041d4: whole credits)."""
        if getattr(self.os, "free_play", False):
            return True
        return int(getattr(self.os, "credits", 0) or 0) > 0

    def replay_text(self):
        """adj_replay_award_2f804 [0x0102f804] (deff 19): the current player's first replay level not yet awarded ("REPLAY AT <level>",
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
                if draw != self.drawn_last.get(deff_id):
                    self.drawn_last[deff_id] = draw
                    slide = DRAWN_SLIDES[deff_id]
                    self._send("slides_play", {slide: {"action": "update", "key": slide,
                                                              "expire": None}}, need_data=False, draw=draw)

    def score_changed(self, *_):
        """Score flush: refresh the score display and the status panel of the effects on screen."""
        self.redraw()
        self.panels_refresh()

    def panels_refresh(self):
        """The status panel and live values of the effects on screen, sent when they changed (every tick)."""
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
                             if k.startswith("line") or k in ("screen", "values")})
            if self._panel_last.get(deff_id) == mine:
                continue
            self._panel_last[deff_id] = mine
            slide = self.slides.get(deff_id, info["slide"])
            self._send("slides_play", {slide: {"action": "update", "key": slide, "expire": None}}, **mine)

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
        """Stop every sample of sound call `call` (FUN_000257b4)."""
        pool = self.data["pools"].get(call) if self.data else None
        for sample in (pool or {}).get("samples", []):
            self._send("sounds_play", {sample: {"action": "stop", "key": sample}})

    def sound_fade(self, call, seconds):
        """Fade out and stop every sample of sound call `call` over `seconds` (task 0x9b [0x01006138])."""
        pool = self.data["pools"].get(call) if self.data else None
        for sample in (pool or {}).get("samples", []):
            self._send("sounds_play", {sample: {"action": "stop", "key": sample, "fade_out": seconds}})
        if pool and pool["track"] == "music":
            self.music_key = None

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
