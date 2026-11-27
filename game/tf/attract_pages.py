"""The attract pages of deff 1, drawn live from the ROM's page code (rom/rules/modes/attract.md).

deff_001_game_over [0x0103c584] walks the page table at 0x00030d10 (39 entries of (condition, page), static data in
the ROM image): for entry i it calls condition(pass) (no condition: always), and when it passes it runs the page as
a child task with the pass at task +0x30, sleeping 1 tick at a time until the page task has ended or the right
flipper (bits_changed_on_68b4(.., 2)) goes on: next entry. The left flipper goes back one entry (one pass back
before entry 0). After the last entry the pass counts up. So a page of n ticks takes n + 1 in the cycle.

Each page is replayed from its op list, lifted by agent A from the page function run as ROM code
(rom/rom_data/dmd/deff_ops/deff_001__page<NN>[_<state>].json: fills, texts, rects, bitmaps, page shows and sleeps);
the texts that print game data are re-read now (credits, replay levels, the high score tables), and the left panel
of draw_way_palette_identity_2f200 [0x0102f200] is the live status panel (tf/score_screen.py, attract state: the
last game's scores, 0x02110900 / 0x021109e4).
"""
import json
import os

from tf import rom_draw as rd

OPS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "rom", "rom_data", "dmd", "deff_ops")
PANEL = (0x0102f200, 0x0102f700)     # draw_way_palette_identity_2f200 and its helpers: the status panel
ENTRIES = 39


def _hs(os_):
    return os_.features_by_name.get("high_scores")


def _hs_entry(os_, index):
    """hstd_entry_if_allowed_186d0 [0x000186d0]: the entry when high scores are on (adj 48), else None."""
    hs = _hs(os_)
    if not hs or os_.adj_value(48) != 1:
        return None
    return hs.entries[index]


def _replay(k):
    """Entries 2-5 [0x000270ec + 0x20 k]: check_task_29_1c174(k + 1) [0x0001c174], replay level k + 1 set."""
    return lambda os_, p: bool(os_.replay_level(k + 1))


def _table_entry(index):
    """Entries 6-17: [0x010004d4 + 0x60 k] (tables 2 and 3), [0x010027c4] (table 4), [0x01002958] (table 5); with
    a tournament of type 4 (not modelled) only on passes divisible by 5."""
    return lambda os_, p: _hs_entry(os_, index) is not None


def _custom_message(os_, p):
    """adj_custom_message_260 [0x01000260]: adj 2 CUSTOM MESSAGE on and a message (error_text_get_4d08
    [0x00004d08]: the NVRAM message, else the region message; neither is stored by the game: never)."""
    return os_.adj_value(2) == 1 and bool(getattr(os_, "custom_message", None))


def _never(os_, p):
    return False


# entry -> (condition or None, op list); tournament pages 18-33 need a Stern tournament (not modelled); entry 37's
# condition 0x0002b0f0 returns 0
CONDITIONS = {0: (lambda os_, p: p == 1, "page00"), 1: (None, "page01")}
CONDITIONS.update({2 + k: (_replay(k), "page02" if k == 0 else "page{:02d}_replays".format(2 + k)) for k in range(4)})
CONDITIONS.update({6 + k: (_table_entry(5 + k), "page{:02d}".format(6 + k)) for k in range(5)})
CONDITIONS.update({11 + k: (_table_entry(10 + k), "page{:02d}".format(11 + k)) for k in range(5)})
CONDITIONS.update({16: (_table_entry(15), "page16"), 17: (_table_entry(16), "page17")})
CONDITIONS.update({e: (_never, "page{:02d}_tournament".format(e)) for e in range(18, 34)})
CONDITIONS.update({34: (None, "page34"), 35: (None, "page35"), 36: (None, "page36"), 37: (_never, "page37"),
                   38: (_custom_message, "page38_custom_msg")})

_OPS = {}


def ops(name):
    if name not in _OPS:
        path = os.path.join(OPS_DIR, "deff_001__{}.json".format(name))
        with open(path, encoding="utf-8") as f:
            _OPS[name] = json.load(f)
    return _OPS[name]


def length(entry):
    """The page's run in ticks (its op list's end_tick: 126 for most, 233 the logo, 261 the animation)."""
    return ops(CONDITIONS[entry][1])["end_tick"]


def live_texts(os_, entry):
    """{call site: text} of a page's texts read from game data now; other texts are the page's own messages."""
    if entry == 1:                                     # credits_screen_120 [0x01000120]: credits_text_44a4
        text = os_.media.credits_text() if hasattr(os_.media, "credits_text") else None
        return {0x01000188: text} if text else {}
    if 2 <= entry <= 5:                                # adj_replay_award_1c21c [0x0001c21c]: the level
        return {"score": "{:,}".format(os_.replay_level(entry - 1))}
    if 6 <= entry <= 17:                               # [0x01000894], [0x010027e0], [0x01002974]: name, score
        index = entry - 1
        e = _hs_entry(os_, index)
        if not e:
            return {}
        hs = _hs(os_)
        score = hs.score_text(index, e["score"])
        return {"name": e["name"], "score": score if isinstance(score, str) else "{:,}".format(score)}
    if entry == 38:
        return {"lines": str(getattr(os_, "custom_message", "")).split("\n")}
    return {}


def _s32(v):
    """A coordinate lifted as an unsigned word (the logo scroll's negative rows)."""
    return v - (1 << 32) if v >= 1 << 31 else v


def _text_item(op, text):
    if op.get("font_list"):
        return rd.fit(text, op["x"], op["y"], op["font_list"], op["flags"], op.get("fit", rd.WIDTH))
    return rd.text(text, op["font"], op["x"], op["y"], op["flags"])


def screen(os_, entry, tick, panel):
    """The draw list of page `entry` at `tick` of its run: the last show's bg page then its fg page, each as
    drawn since its last fill; the panel's ops replaced by `panel` (a draw list)."""
    doc = ops(CONDITIONS[entry][1])
    live = live_texts(os_, entry)
    show = None
    for op in doc["ops"]:
        if op["t"] > tick:
            break
        if op["op"] == "show":
            show = (op["fg"], op["bg"])
    if show is None:
        return []
    contents, panelled = {}, set()
    for op in doc["ops"]:
        if op["t"] > tick:
            break
        page = op.get("page")
        if page is None:
            continue
        if op["op"] == "fill":
            contents[page] = []
            panelled.discard(page)
            continue
        at = int(op.get("at", "0"), 16)
        if PANEL[0] <= at < PANEL[1]:
            panelled.add(page)
            continue
        items = contents.setdefault(page, [])
        if op["op"] == "text":
            items.append(_text_item(op, op["text"]))
        elif op["op"] == "rect":
            items.append(rd.box(op["x0"], op["y0"], op["x1"] - op["x0"] + 1, op["y1"] - op["y0"] + 1, op["value"]))
        elif op["op"] in ("bitmap", "bitmap_masked"):
            items.append(rd.image(op["img"], _s32(op["x"]), _s32(op["y"])))   # the scroll goes above row 0
    _substitute(entry, doc, contents, live)
    fg, bg = show
    draw = list(contents.get(bg, []))
    if bg in panelled or fg in panelled:
        draw = panel + draw
    return draw + list(contents.get(fg, []))


def _substitute(entry, doc, contents, live):
    """Put the live texts in place of the lifted ones (the lifted state's values)."""
    if not live:
        return
    for items in contents.values():
        texts = [d for d in items if "t" in d]
        if entry == 1 and 0x01000188 in live:
            for d in texts:
                d["t"] = live[0x01000188]
        elif 2 <= entry <= 5 and texts:
            texts[-1]["t"] = live["score"]
        elif 6 <= entry <= 17 and len(texts) >= 2 and "name" in live:
            texts[-2]["t"], texts[-1]["t"] = live["name"], live["score"]
        elif entry == 38 and "lines" in live:
            for d, line in zip(texts, live["lines"]):
                d["t"] = line


class Walker:
    """deff 1's walk [0x0103c584]: the entry, the pass and when the page started."""

    def __init__(self, os_):
        self.os = os_
        self.entry = 0
        self.passes = 1
        self.started = 0.0
        self._handle = None

    def start(self, now):
        self.entry, self.passes = 0, 1
        self._enter(self._first_from(0, 1), now)

    def stop(self):
        if self._handle is not None:
            self.os.machine.clock.unschedule(self._handle)
            self._handle = None

    def _passes(self, entry, p):
        cond = CONDITIONS[entry][0]
        return cond is None or cond(self.os, p)

    def _first_from(self, entry, p):
        """The first entry from `entry` whose condition passes (the pass counts up after the last)."""
        for _ in range(ENTRIES * 2):
            if entry >= ENTRIES:
                entry, p = 0, p + 1
            if self._passes(entry, p):
                self.passes = p
                return entry
            entry += 1
        return 1

    def _enter(self, entry, now):
        self.stop()
        self.entry, self.started = entry, now
        # the page runs its length; deff 1 starts the next one tick after it ended
        self._handle = self.os.machine.clock.schedule_once(lambda _dt=None: self.next(), (length(entry) + 1) * 0.016)

    def next(self):
        self._enter(self._first_from(self.entry + 1, self.passes), self.os.now)

    def back(self):
        """Left flipper: back one entry whose condition passes (one pass back before entry 0)."""
        entry, p = self.entry, self.passes
        for _ in range(ENTRIES * 2):
            entry -= 1
            if entry < 0:
                entry, p = ENTRIES - 1, max(p - 1, 1)
            if self._passes(entry, p):
                break
        self.passes = p
        self._enter(entry, self.os.now)

    def tick(self, now):
        return max(0, int((now - self.started) / 0.016))
