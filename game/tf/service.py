"""The service menu, mode tf_service: the ROM's menu engine (0x0000eb3c, menu lists 0x00030d04 / 0x00030cf8) and its
service deff 3 (deff_003 [0x0103f960], started by start_deff_3 [0x0000ed90]), driven by the coin-door buttons.

What it draws and in what order comes from the ROM extraction:
- rom/mpf_package/service_menu.json: the menus as 0xeb3c builds them at factory settings (items, kinds, submenus),
  the 98 adjustments (range, step, labels, menu order) and the 166 audits;
- rom/rom_data/settings/service_screens.json: every screen the ROM draws, walked in the ROM's code
  (rom/tools/service_walk.py): texts, fonts, flags and positions.

Screens, as the walk shows them:
- title (SELECT from attract): TRANSFORMERS / V1.8 / SYS. 1.64 / HDW. 0, SERVICE MENU, "PRESS 'SELECT' TO CONTINUE";
- a menu: the current item's text, font 2 centred at (64, 30); PLUS / MINUS move through the items, wrapping;
  SELECT opens the item, BACK goes up one menu;
- the adjustments: "STANDARD ADJUSTMENT #n" (font 2, y 5), the name (font 6, y 14), the value's label (font 8,
  y 22), "(INSTALLED/FACTORY DEFAULT)" (font 2, y 29) while the value is the default; SELECT starts the edit,
  PLUS / MINUS change the value (Adjustments.step), SELECT stores it, BACK cancels;
- the audits: "EARNINGS AUDIT #n" (y 5), the name (font 6, y 14), the value (font 8, y 22), PLUS / MINUS next and
  previous;
- installs and resets: the item (font 8), "PRESS 'SELECT' TO INSTALL" / "TO RESET", "PRESS 'BACK' TO CANCEL";
  SELECT does it (Adjustments.install, Audits.reset_*) and goes back to the menu;
- every other screen (tests, help, USB) shows the texts the ROM drew for it in the walk.
The menu items hidden at factory settings (service_menu.json shown_only_if: tournament, software errors) stay
hidden; GO TO REDEMPTION MENU is always shown (0x010088ac returns 1).
"""
import json
import os

from mpf.core.mode import Mode

from tf import rom_draw as rd
from tf.settings import ROOT, service_data

SCREENS_JSON = os.path.join(ROOT, "rom", "rom_data", "settings", "service_screens.json")
ALWAYS_SHOWN = {98}             # 0x010088ac: always 1
WIDTH_DOTS = 0x80
CUSTOM_PRICING = 68             # adj 28 GAME PRICING = CUSTOM
MENU_Y, MENU_FONT = 30, 2
DEFAULT_TEXT = "(INSTALLED/FACTORY DEFAULT)"
_SCREENS = None


def screens():
    """{path: [(text, font, flags, x, y)]}: the ROM's texts per walked screen, each once, top to bottom."""
    global _SCREENS
    if _SCREENS is None:
        _SCREENS = {}
        if os.path.exists(SCREENS_JSON):
            with open(SCREENS_JSON, encoding="utf-8") as f:
                for s in json.load(f)["screens"]:
                    seen = []
                    for t in s["texts"]:
                        item = (t["text"], t["font"], t["flags"], t["x"], t["y"])
                        if item not in seen:
                            seen.append(item)
                    _SCREENS.setdefault(s["path"], seen)
    return _SCREENS


def draw_of(texts):
    return [rd.text(t, font, x, y, flags) for t, font, flags, x, y in texts]


# the service loops' button sounds (deff 3 [0x0103f960] and the item screens): snd_resolve_call through
# 0x0000ecfc (BACK 0x009), 0x0000ed0c (MINUS 0x00a), 0x0000ed1c (PLUS 0x00b), 0x0000ed2c (SELECT 0x00c);
# 0x0000ed3c (0x00d) when a reset or install is done ([0x0104196c] [0x010417b4])
BEEP_BACK, BEEP_MINUS, BEEP_PLUS, BEEP_SELECT, BEEP_DONE = 0x009, 0x00a, 0x00b, 0x00c, 0x00d
BEEP_FAIL = 0x00e                # 0x0000ed4c: the custom pricing install failed [0x01044f7c]


class ServiceMode(Mode):
    """The service menu. self.stack: the open menus [(menu name, item index, path)]; self.page: the item's screen
    when one is open (adjustments, audits, confirm, static), else None."""

    def mode_start(self, **kwargs):
        self.os = self.machine.tf
        self.os.in_service = True
        self.data = service_data()
        self.stack = []
        self.page = None
        self.title = True
        for name, fn in (("s_select", self._beep(BEEP_SELECT, self._select)), ("s_back", self._beep(BEEP_BACK, self._back)),
                         ("s_plus", self._beep(BEEP_PLUS, lambda: self._move(1))),
                         ("s_minus", self._beep(BEEP_MINUS, lambda: self._move(-1)))):
            if name in self.machine.switches:
                self.switch_handlers.append(self.machine.switch_controller.add_switch_handler(name, fn))
        self.os.trace.log("service", screen="title")
        self.show()

    def _beep(self, call, fn):
        def handler():
            self.os.sound(call)
            fn()
        return handler

    def mode_stop(self, **kwargs):
        if getattr(self, "_custom_timer", None):
            self.machine.clock.unschedule(self._custom_timer)
            self._custom_timer = None
        self.os.in_service = False
        self.os.media.service_hide()
        if "attract" in self.machine.modes and not self.machine.modes["attract"].active and not self.os.game:
            self.machine.modes["attract"].start()

    # ------------------------------------------------------------------ navigation

    def items(self, menu):
        return [i for i in self.data["menus"][menu]
                if not i.get("shown_only_if") or i["item"] in ALWAYS_SHOWN]

    def current(self):
        menu, index, _ = self.stack[-1]
        return self.items(menu)[index]

    def menu_path(self):
        return self.stack[-1][2] if self.stack else "title"

    def _open_menu(self, menu, path):
        self.stack.append((menu, 0, path))
        self.page = None

    def _select(self):
        if self.title:
            self.title = False
            self._open_menu("MAIN MENU", "MAIN MENU")
            return self.show()
        if self.page is not None:
            return self._page_select()
        item = self.current()
        kind = item["kind"]
        if kind == "submenu":
            name = MENU_NUMBERS[item["submenu"]]
            self._open_menu(name, "{} / {}".format(self.menu_path(), item["text"]))
        elif kind == "back":
            self._back()
            return
        elif kind == "exit":
            self.stop()
            return
        else:
            self._open_page(item)
        self.show()

    def _back(self):
        if self.title:
            self.stop()
            return
        if self.page is not None and self.page["kind"] == "custom":
            if self.page["editor"].installed is not None or not self.page["editor"].back():
                self._close_custom()
            return self.show()
        if self.page is not None:
            if self.page.get("editing"):
                self.page["editing"] = False
                self.page["value"] = self.os.adj[self.page["list"][self.page["i"]]]
            else:
                self.page = None
            return self.show()
        if len(self.stack) > 1:
            self.stack.pop()
            return self.show()
        self.stop()

    def _move(self, d):
        if self.title:
            return
        if self.page is not None:
            return self._page_move(d)
        menu, index, path = self.stack[-1]
        self.stack[-1] = (menu, (index + d) % len(self.items(menu)), path)
        self.show()

    # ------------------------------------------------------------------ item screens

    def _open_page(self, item):
        text = item["text"]
        path = "{} / {}".format(self.menu_path(), text)
        if text == "SET CUSTOM PRICING":
            self._open_custom(path, back_to=None)
        elif text in ("STANDARD ADJUSTMENTS", "FEATURE ADJUSTMENTS"):
            group = text.split()[0].lower()
            nums = self.os.adj.menu(group)
            self.page = {"kind": "adj", "group": group.upper(), "list": nums, "i": 0, "editing": False,
                         "value": self.os.adj[nums[0]] if nums else 0}
        elif text in ("EARNINGS AUDITS", "STANDARD AUDITS", "FEATURE AUDITS"):
            self.page = {"kind": "audit", "group": text.split()[0], "list": self.os.audits.menu(text.split()[0].lower()),
                         "i": 0}
        elif text.startswith("INSTALL ") and text in self.data["install_presets"] or text == "INSTALL FACTORY":
            self.page = {"kind": "confirm", "do": lambda: self.os.adj.install(text), "path": path}
        elif text in RESETS:
            self.page = {"kind": "confirm", "do": lambda: RESETS[text](self.os), "path": path}
        else:
            self.page = {"kind": "static", "path": path}
        self.os.trace.log("service", screen=path)

    def _page_select(self):
        page = self.page
        if page["kind"] == "custom":
            editor = page["editor"]
            if editor.installed is not None:            # "PRESS 'SELECT' TO CONTINUE"
                if editor.installed:
                    self.os.adj[28] = CUSTOM_PRICING    # adj_game_pricing [0x010457c4]: event 4 {0x1c, 0x44}
                self._close_custom()
            elif editor.select():
                self.os.sound(BEEP_DONE if editor.installed else BEEP_FAIL)
            else:
                self.os.sound(BEEP_SELECT)              # the loop's second snd_play_c_ed2c
            return self.show()
        if page["kind"] == "adj" and page["list"]:
            num = page["list"][page["i"]]
            if page["editing"] and num == 28 and page["value"] == CUSTOM_PRICING and \
                    self.os.adj[28] != CUSTOM_PRICING:
                # custom_pricing_check_457e4 [0x010457e4]: the change to CUSTOM runs the editor and holds only
                # when it installs
                page["editing"] = False
                self._open_custom(page.get("path", ""), back_to=page)
                return self.show()
            if page["editing"]:
                self.os.adj[num] = page["value"]
                page["editing"] = False
            else:
                page["editing"], page["value"] = True, self.os.adj[num]
        elif page["kind"] == "confirm":
            page["do"]()
            self.os.sound(BEEP_DONE)
            self.page = None
        self.show()

    def _open_custom(self, path, back_to):
        from tf.os_layer import TICK                     # noqa: PLC0415
        self.page = {"kind": "custom", "editor": CustomPricing(self.os.credit_model), "back_to": back_to,
                     "path": path}
        self._custom_timer = self.machine.clock.schedule_interval(lambda *_: self._custom_frame(), 2 * TICK)

    def _custom_frame(self):
        if self.page is None or self.page["kind"] != "custom":
            return
        self.page["editor"].frame()
        self.show()

    def _close_custom(self):
        timer = getattr(self, "_custom_timer", None)
        if timer:
            self.machine.clock.unschedule(timer)
            self._custom_timer = None
        back_to = self.page["back_to"]
        if back_to is not None:
            back_to["value"] = self.os.adj[28]
        self.page = back_to

    def _page_move(self, d):
        page = self.page
        if page["kind"] == "custom":
            (page["editor"].plus if d > 0 else page["editor"].minus)()
            return self.show()
        if page["kind"] == "adj" and page["list"]:
            if page["editing"]:
                page["value"] = self.os.adj.step(page["list"][page["i"]], page["value"], d)
            else:
                page["i"] = (page["i"] + d) % len(page["list"])
                page["value"] = self.os.adj[page["list"][page["i"]]]
        elif page["kind"] == "audit" and page["list"]:
            page["i"] = (page["i"] + d) % len(page["list"])
        self.show()

    # ------------------------------------------------------------------ drawing

    def draw(self):
        if self.title:
            return draw_of(screens().get("title", ()))
        page = self.page
        if page is None:
            return [rd.text(self.current()["text"], MENU_FONT, 64, MENU_Y, 2)]
        if page["kind"] == "custom":
            return page["editor"].draw()
        if page["kind"] == "adj":
            if not page["list"]:
                return []
            num = page["list"][page["i"]]
            info = self.os.adj.info[num]
            value = page["value"]
            draw = [rd.text(info["menu_label"].rsplit("#", 1)[0] + "#{}".format(page["i"] + 1), 2, 64, 5, 2),
                    rd.fit(info["name"], 64, 14, (6, 2, 0)),
                    rd.text(self.os.adj.label(num, value), 8, 64, 22, 2)]
            if value == self.os.adj.default(num):
                draw.append(rd.text(DEFAULT_TEXT, 2, 64, 29, 2))
            return draw
        if page["kind"] == "audit":
            if not page["list"]:
                return []
            num = page["list"][page["i"]]
            info = self.os.audits.info[num]
            return [rd.text(info["menu_label"], 2, 64, 5, 2), rd.fit(info["name"], 64, 14, (6, 2, 0)),
                    ] + self._value_lines(self.os.audits.text(num))
        texts = screens().get(page["path"] + " [select]")
        if texts:
            return draw_of(texts)
        return [rd.text(page["path"].rsplit(" / ", 1)[-1], MENU_FONT, 64, MENU_Y, 2)]

    @staticmethod
    def _value_lines(text):
        """draw_lifetime_s [0x01046598]: the value split at its newlines (split_lines_10ec), at most two lines in font
        8 from row 0x16, one dot plus the font height apart."""
        draw, y = [], 0x16
        for line in text.split("\n")[:2]:
            draw.append(rd.text(line, 8, 64, y, 2))
            y += 1 + rd.fonts().get(8, {}).get("height", 7)
        return draw

    def show(self):
        draw = self.draw()
        self.os.media.service_show(rd.lines_of(draw), draw=draw)


# the menus by number (service_menu.json submenu values, menu engine 0x0000eb3c)
MENU_NUMBERS = {1: "MAIN MENU", 2: "DIAGNOSTICS", 3: "SWITCH MENU", 4: "COIL MENU", 5: "LAMP MENU",
                6: "FLASH LAMPS MENU", 7: "DR. PINBALL", 8: "AUDITS", 9: "ADJUSTMENTS", 10: "UTILITIES",
                11: "INSTALLS", 12: "RESETS", 13: "SERIAL", 14: "USB", 15: "TOURNAMENT", 16: "REDEMPTION",
                17: "GAME-SPECIFIC TESTS"}
RESETS = {
    "RESET COIN AUDITS": lambda os_: os_.audits.reset_coin(),        # 0x0104b3e4
    "RESET GAME AUDITS": lambda os_: os_.audits.reset_game(),        # 0x0104b244
    "RESET FACTORY SETTINGS": lambda os_: os_.adj.factory_reset(),   # 0x0104b728
    "RESET CREDITS": lambda os_: os_.credit_model.reset(),           # 0x0104b584
    "RESET GRAND CHAMPION": lambda os_: os_.features_by_name["high_scores"].reset(1),   # 0x0104196c, FUN_000189fc
    "RESET HIGH SCORES": lambda os_: os_.features_by_name["high_scores"].reset(2),      # 0x01041b10, FUN_000189fc
}


def price_summary(ladder, n, money, font=0, width=WIDTH_DOTS):
    """text_wrap_9ff8 [0x00009ff8](buf, unit, ladder, n, plain money format, font 0, 0x80, -1): for each of the first n
    steps that gives credits, "<credits so far>/<money of the units so far>", one per line; while the next entry does
    not fit 0x80 dots (the lines' width plus a space and a dot per line), the first line goes; when one went,
    "(... " leads and ")" ends, and the lines are joined by spaces."""
    space = rd.text_width(font, " ")
    lines, total, dropped = [], 0, False

    def used(ls):
        return rd.text_width(font, "".join(ls)) + (space * len(ls) + len(ls) if ls else 0)
    for i in range(min(n, len(ladder))):
        if not ladder[i]:
            continue
        total += ladder[i]
        entry = "%d/" % total + money(i + 1)
        while lines and used(lines) + rd.text_width(font, entry) > width:
            dropped = True
            lines.pop(0)
        lines.append(entry)
    if dropped:
        more = rd.text_width(font, "(... )")
        while len(lines) >= 2 and rd.text_width(font, "".join(lines)) + more + space * len(lines) + len(lines) + 2 > width:
            lines.pop(0)
        return "(... " + " ".join(lines) + ")"
    return " ".join(lines)


class CustomPricing:
    """SET CUSTOM PRICING, draw_custom_pricing_msg_get_44f7c [0x01044f7c]: one unit step at a time, the credits it
    gives (0-10) and the money paid so far; MINUS / PLUS change the credits (below 0 or above 10 they wrap, or
    become INSTALL once an earlier step gives credits), SELECT goes to the next step (at most 100) or installs,
    BACK goes back one step (from the first: leaves without installing). The screen is redrawn every 2 ticks
    (deff_frame_sleep(2)): the step blinks (solid for 15 frames after a button), the help line alternates every
    0x4e frames."""
    TITLE, INSTALL, CREDITS_FMT, AT_FMT = "CUSTOM PRICING", "INSTALL", "%d", " CREDIT%P1//S/% AT:"   # msgs 0x4df-0x4e2
    HELP = ("USE -/+ TO CHANGE CREDITS", "USE -/+ TO 'INSTALL'", "PRESS 'SELECT' TO INSTALL")       # 0x4e3-0x4e5
    DONE = ("CUSTOM PRICING", "INSTALLED", "PRESS 'SELECT' TO CONTINUE")                            # 0x4e6-0x4e8

    def __init__(self, credits):
        self.credits = credits
        ladder, self.pos = credits.custom_record()
        self.ladder = ladder + [0] * (101 - len(ladder))
        self.end = self.any_before(self.pos)
        self.solid, self.blink, self.help_wait, self.help = 0, 8, 0x4e, 0
        self.installed = None           # None editing, True / False after the install

    def any_before(self, n):
        """buf_any_nonzero_44f3c [0x01044f3c](ladder, n): MINUS / PLUS pass the step in r1 ([0x0104551c],
        [0x010455b8]), the last step 100 ([0x0104575c])."""
        return any(self.ladder[:max(0, n)])

    def frame(self):
        """One 2-tick frame of the loop's counters."""
        if self.solid < 0:
            self.blink -= 1
        else:
            self.solid -= 1
        if self.blink + 7 < 0:
            self.blink = 8
        if not self.end:
            if self.help_wait == 0:
                self.help_wait = 0x4e
                self.help = (self.help + 1) % 2
            else:
                self.help_wait -= 1

    def touched(self):
        self.solid, self.blink, self.help_wait = 0xf, 8, 0x4e

    def back(self):
        """Returns False when the editor is left."""
        if self.pos < 1:
            return False
        self.end = False
        self.ladder[self.pos] = 0
        self.pos -= 1
        self.touched()
        return True

    def minus(self):
        if self.pos < 100:
            if self.end:
                self.end, self.ladder[self.pos] = False, 10
            elif self.ladder[self.pos] == 0:
                if self.any_before(self.pos):
                    self.end = True
                else:
                    self.ladder[self.pos] = 10
            else:
                self.ladder[self.pos] -= 1
        self.touched()

    def plus(self):
        if self.pos < 100:
            if self.end:
                self.end, self.ladder[self.pos] = False, 0
            elif self.ladder[self.pos] < 10:
                self.ladder[self.pos] += 1
            else:
                self.end = self.any_before(self.pos)
                self.ladder[self.pos] = 0
        self.touched()

    def select(self):
        """True when it installed."""
        if self.end:
            self.ladder[self.pos] = 0
            self.installed = self.credits.custom_install(self.ladder[:self.pos])
            return True
        if self.pos < 100:
            if self.pos == 99:
                self.end = self.any_before(100)
                if self.end:
                    self.pos += 1
            else:
                self.pos += 1
        else:
            self.pos = 99
        self.solid, self.blink, self.help_wait = 0, 8, 0x4e
        return False

    def draw(self):
        from tf.media_bridge import format_rom_text      # noqa: PLC0415
        if self.installed is not None:
            return [rd.text(self.DONE[0], 8, 0x40, 10, 2), rd.text(self.DONE[1], 8, 0x40, 0x12, 2),
                    rd.fit(self.DONE[2], 0x40, 0x1b, (2, 0))]
        draw = [rd.text(self.TITLE, 2, 0x40, 4, 2), rd.box(0, 6, 0x80, 1, 3), rd.box(0, 0x10, 0x80, 1, 3)]
        shown = self.blink >= 0 or self.solid >= 0
        if self.end:
            if shown:
                draw.append(rd.text(self.INSTALL, 2, 0x40, 0xd, 2))
        else:
            n = self.ladder[self.pos]
            left = format_rom_text(self.CREDITS_FMT, [n])
            if shown:
                draw.append(rd.text(left, 2, 0, 0xd, 1))
            draw.append(rd.text(format_rom_text(self.AT_FMT, [n], last=[n]), 2, rd.text_width(2, left) + 1, 0xd, 1))
            draw.append(rd.text(self.credits.unit_money(self.pos + 1), 2, 0x7f, 0xd, 4))
        summary = price_summary(self.ladder, min(self.pos + 1, 100), lambda u: self.credits.unit_money(u, "plain"))
        if summary:
            draw.append(rd.text(summary, 0, 0x40, 0x17, 2))
        help_ = self.HELP[2] if self.end else self.HELP[1 if self.help and self.any_before(self.pos) else 0]
        draw.append(rd.text(help_, 2, 0x40, 0x1f, 2))
        return draw
