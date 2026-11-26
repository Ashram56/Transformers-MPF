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
        for name, fn in (("s_select", self._select), ("s_back", self._back), ("s_plus", lambda: self._move(1)),
                         ("s_minus", lambda: self._move(-1))):
            if name in self.machine.switches:
                self.switch_handlers.append(self.machine.switch_controller.add_switch_handler(name, fn))
        self.os.trace.log("service", screen="title")
        self.show()

    def mode_stop(self, **kwargs):
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
        if text in ("STANDARD ADJUSTMENTS", "FEATURE ADJUSTMENTS"):
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
        if page["kind"] == "adj" and page["list"]:
            num = page["list"][page["i"]]
            if page["editing"]:
                self.os.adj[num] = page["value"]
                page["editing"] = False
            else:
                page["editing"], page["value"] = True, self.os.adj[num]
        elif page["kind"] == "confirm":
            page["do"]()
            self.page = None
        self.show()

    def _page_move(self, d):
        page = self.page
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
                    rd.text(self.os.audits.text(num), 8, 64, 22, 2)]
        texts = screens().get(page["path"] + " [select]")
        if texts:
            return draw_of(texts)
        return [rd.text(page["path"].rsplit(" / ", 1)[-1], MENU_FONT, 64, MENU_Y, 2)]

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
