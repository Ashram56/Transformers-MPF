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
- SWITCH TEST runs live as the ROM's loop [0x0104cae4] (SwitchTest below), the single and cycling coil and flash
  lamp tests as theirs [0x01046f4c] [0x01046a98] [0x010492b8] [0x01048de4] (SingleCoilTest and its variants);
- the lamp tests [0x0104a6c8] [0x01049cf4] [0x0104aeac] [0x0104a0d0] (LampTest below) and the knocker, trough,
  sound, dot matrix, active switch and Optimus motor tests (tf/service_tests.py) as theirs too;
- every other screen (help, USB, the remaining pages) shows the texts the ROM drew for it in the walk.
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
        self.os.lamps.leff_code(2, _leff_all_off)
        self.os.leff_start(2)               # start_deff_3 [0x0000ed90]: leff 2 (leff_002 [0x0002b238]) over the lamps
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
            if self.page is not None and self.page["kind"] == "switch_test" and call != BEEP_BACK:
                return                      # in the switch test only BACK acts [0x0104cae4]; the others are switches
            if self.page is not None and self.page["kind"] in ("coil_test", "lamp_test", "loop"):
                self.page["records"][call] += 1     # the button handlers post their records; the test's pass reads them
                return
            self.os.sound(call)
            fn()
        return handler

    def mode_stop(self, **kwargs):
        self._close_switch_test()
        self._close_coil_test()
        self._close_lamp_test()
        self._close_loop()
        if getattr(self, "_custom_timer", None):
            self.machine.clock.unschedule(self._custom_timer)
            self._custom_timer = None
        self.os.in_service = False
        self.os.leff_stop(2)
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
        if self.page is not None and self.page["kind"] == "switch_test":
            self._close_switch_test()
            self.page = None
            return self.show()
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
        elif text == "SWITCH TEST":
            self._open_switch_test(path)
        elif text == "SINGLE COIL TEST":
            self._open_coil_test(path, SingleCoilTest)
        elif text == "SINGLE FLASH LAMP TEST":
            self._open_coil_test(path, SingleFlashLampTest)
        elif text == "CYCLING COIL TEST":
            self._open_coil_test(path, CyclingCoilTest)
        elif text == "CYCLING FLASH LAMP TEST":
            self._open_coil_test(path, CyclingFlashLampTest)
        elif text in LAMP_TESTS:
            self._open_lamp_test(path, LAMP_TESTS[text])
        elif text in LOOP_TESTS:
            self._open_loop(path, text)
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

    def _open_switch_test(self, path):
        """SwitchTest [0x0104cae4]: its loop once a tick; every switch change reaches it (MPF's switch monitor),
        the switches already closed are drawn but not taken as new."""
        from tf.os_layer import TICK                     # noqa: PLC0415
        test = SwitchTest()
        numbers = {}
        for sw in self.machine.switches.values():
            num = str(sw.config.get("number", ""))
            if num.isdigit():
                numbers[sw.name] = int(num)
            elif num[:1] == "D" and num[1:].isdigit():
                numbers[sw.name] = 0x80 + int(num[1:])
        for name, num in numbers.items():
            if self.machine.switch_controller.is_active(self.machine.switches[name]):
                test.closed.add(num)

        def monitor(change):
            num = numbers.get(change.name)
            if num is None or self.page is None or self.page.get("test") is not test:
                return
            if change.state:
                self.os.sound(test.closing(num))
            else:
                test.opening(num)
        self.machine.switch_controller.add_monitor(monitor)
        self.page = {"kind": "switch_test", "test": test, "path": path, "monitor": monitor, "draw": test.tick()}

        def frame(*_):
            if self.page is not None and self.page.get("test") is test:
                self.page["draw"] = test.tick()
                self.show()
        self.page["timer"] = self.machine.clock.schedule_interval(frame, TICK)

    def _open_coil_test(self, path, kind):
        """SingleCoilTest [0x01046f4c]: one pass every 2 ticks; the button records (0x00036ac0 BACK, 0x00036ad0 MINUS,
        0x00036ae0 PLUS, 0x00036af0 SELECT) are read in the pass."""
        from tf.os_layer import TICK                     # noqa: PLC0415
        test = kind(coil_records(), lambda: not self.os.coin_door_open())
        names = {num: name for name, num in self.os.lamps.coil_numbers.items()}
        records = {BEEP_BACK: 0, BEEP_MINUS: 0, BEEP_PLUS: 0, BEEP_SELECT: 0}
        page = {"kind": "coil_test", "test": test, "path": path, "records": records, "draw": [], "task": None}
        self.page = page

        def task_end():
            page["task"] = None

        def fire():
            """coil_task_body_46e24 [0x01046e24]: the record's test function, else coil_pulse_now_wait(coil, test ms)."""
            num = test.index
            rec = test.coils[num]
            if rec["fn"] == "0x100a374":            # pulse_megatron_lockup_a374: coil 3 for 0x40 ms, task 0x58 (0x3e)
                self.os.lamps.flasher(names.get(3), 0x40)
                self.os.task_start(0x58, 0x3e)
                return None
            if rec["fn"] == "0x1025568":            # optimus_motor_test: the motor to the other position, waited for
                mech = self.os.features_by_name.get("optimus_mech")
                if mech is None or mech.moving is not None:
                    return None
                mech._move(0x2c if mech.position() == 0x2b else 0x2b)
                return "motor"
            if names.get(num) and rec["ms"]:
                self.os.lamps.flasher(names[num], rec["ms"])
            return self.machine.clock.schedule_once(lambda *_: task_end(), max(rec["ms"] / 1000.0, TICK))

        def stop_task():
            """task_kill_own_children_ade4 and coil_slot_246c: the test task and its coil stop."""
            task = page["task"]
            if task == "motor":
                mech = self.os.features_by_name.get("optimus_mech")
                if mech is not None:
                    mech._motor_off()
            elif task is not None:
                self.machine.clock.unschedule(task)
            page["task"] = None
            test.running = False

        page["rest"] = 0

        def cycle():
            """[0x01046a98]: start the coil's task when none runs; when it has ended, rest 0x3e passes, then the
            next coil. BACK stops the task and leaves."""
            if not test.running:
                page["task"] = fire()
                test.running = True
                page["rest"] = 0
            ended = False
            if test.running:
                if page["rest"] == 0:
                    if page["task"] == "motor":
                        mech = self.os.features_by_name.get("optimus_mech")
                        if mech is None or mech.moving is None:
                            page["task"] = None
                    ended = page["task"] is None
                    if ended:
                        page["rest"] = test.REST_PASSES
                else:
                    page["rest"] -= 1
                    if page["rest"] == 0:
                        test.index = test.next(test.index)
                        test.running = False
            if ended or records[BEEP_BACK]:
                running = test.running
                stop_task()
                test.running = running and not records[BEEP_BACK]
            if records[BEEP_BACK]:
                self.os.sound(BEEP_BACK)
                self._close_coil_test()
                self.page = None

        def tick(*_):
            if self.page is not page:
                return
            draw, sounds = test.frame()
            for call in sounds:
                self.os.sound(call)
            page["draw"] = draw
            if test.CYCLING:
                cycle()
                return self.show()
            if not test.running and records[BEEP_MINUS]:
                records[BEEP_MINUS] -= 1
                self.os.sound(BEEP_MINUS)
                test.index = test.prev(test.index)
            if not test.running and records[BEEP_PLUS]:
                records[BEEP_PLUS] -= 1
                self.os.sound(BEEP_PLUS)
                test.index = test.next(test.index)
            if records[BEEP_SELECT]:
                records[BEEP_SELECT] = 0
                if not test.running:
                    page["task"] = fire()
                    test.running = True
            if page["task"] == "motor":
                mech = self.os.features_by_name.get("optimus_mech")
                if mech is None or mech.moving is None:
                    page["task"] = None
            done = False
            if test.running and (page["task"] is None or records[BEEP_BACK]):
                if records[BEEP_BACK]:
                    records[BEEP_BACK] -= 1
                    self.os.sound(BEEP_BACK)
                records[BEEP_MINUS] = records[BEEP_PLUS] = records[BEEP_SELECT] = 0
                done = True
            if done or records[BEEP_BACK]:
                stop_task()
            if records[BEEP_BACK]:
                self.os.sound(BEEP_BACK)            # snd_play_9_ecfc on the way out
                self._close_coil_test()
                self.page = None
            self.show()
        page["timer"] = self.machine.clock.schedule_interval(tick, SingleCoilTest.PASS_TICKS * TICK)
        page["stop"] = stop_task
        tick()

    def _open_lamp_test(self, path, kind):
        """The lamp tests [0x0104a6c8] [0x01049cf4] [0x0104aeac] [0x0104a0d0]: one pass every 2 ticks; the button
        records are read in the pass; the test's leff (3 to 6) lights the lamps."""
        from tf.os_layer import TICK                     # noqa: PLC0415
        test = kind()
        for leff_id, fn in LAMP_LEFFS.items():
            self.os.lamps.leff_code(leff_id, fn)
        records = {BEEP_BACK: 0, BEEP_MINUS: 0, BEEP_PLUS: 0, BEEP_SELECT: 0}
        page = {"kind": "lamp_test", "test": test, "path": path, "records": records, "draw": []}
        self.page = page

        def tick(*_):
            if self.page is not page:
                return
            pressed = {call: bool(records[call]) for call in (BEEP_BACK, BEEP_MINUS, BEEP_PLUS)}
            for call in (BEEP_MINUS, BEEP_PLUS):
                records[call] = max(records[call] - 1, 0)
            draw, actions = test.step(pressed)
            for kind_, arg in actions:
                if kind_ == "sound":
                    self.os.sound(arg)
                elif kind_ == "leff":
                    self.os.leff_stop(arg[0])           # task_group_kill_b7e4(leff)
                    self.os.leff_start(arg[0], lamp=arg[1])
                elif kind_ == "kill":
                    self.os.leff_stop(arg)
            page["draw"] = draw
            if test.done:
                self._close_lamp_test()
                self.page = None
            self.show()
        page["timer"] = self.machine.clock.schedule_interval(tick, LampTest.PASS_TICKS * TICK)
        tick()

    def switch_numbers(self):
        """{ROM switch number: MPF switch}: the config numbers, "Dn" as 0x80 + n."""
        out = {}
        for sw in self.machine.switches.values():
            num = str(sw.config.get("number", ""))
            if num.isdigit():
                out[int(num)] = sw
            elif num[:1] == "D" and num[1:].isdigit():
                out[0x80 + int(num[1:])] = sw
        return out

    def _open_loop(self, path, text):
        """A test of tf/service_tests.py: its pass every PASS_TICKS ticks, the button records read in the pass."""
        from tf import service_tests as st                # noqa: PLC0415
        from tf.os_layer import TICK                     # noqa: PLC0415
        kind = LOOP_TESTS[text]
        cls = getattr(st, kind)
        test = cls(self, self.switch_numbers()) if kind in ("TroughTest", "ActiveSwitchTest") else cls(self)
        records = {BEEP_BACK: 0, BEEP_MINUS: 0, BEEP_PLUS: 0, BEEP_SELECT: 0}
        page = {"kind": "loop", "test": test, "path": path, "records": records, "draw": []}
        self.page = page

        def tick(*_):
            if self.page is not page:
                return
            page["draw"] = test.step(records)
            if test.done:
                self._close_loop()
                self.page = None
            self.show()
        page["timer"] = self.machine.clock.schedule_interval(tick, test.PASS_TICKS * TICK)
        tick()

    def _close_loop(self):
        page = getattr(self, "page", None)
        if page is not None and page.get("kind") == "loop":
            self.machine.clock.unschedule(page["timer"])
            page["test"].close()

    def _close_lamp_test(self):
        page = getattr(self, "page", None)
        if page is not None and page.get("kind") == "lamp_test":
            self.machine.clock.unschedule(page["timer"])
            self.os.leff_stop(page["test"].LEFF)

    def _close_coil_test(self):
        page = getattr(self, "page", None)
        if page is not None and page.get("kind") == "coil_test":
            page["stop"]()
            self.machine.clock.unschedule(page["timer"])

    def _close_switch_test(self):
        page = getattr(self, "page", None)
        if page is not None and page.get("kind") == "switch_test":
            self.machine.switch_controller.remove_monitor(page["monitor"])
            self.machine.clock.unschedule(page["timer"])

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
        if page["kind"] in ("switch_test", "coil_test", "lamp_test", "loop"):
            return page["draw"]
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


def _image_sizes():
    """{image: (w, h)} from rom/rom_data/dmd/images.csv (the ROM's image table)."""
    import csv                                   # noqa: PLC0415
    path = os.path.join(ROOT, "rom", "rom_data", "dmd", "images.csv")
    with open(path, encoding="utf-8") as f:
        return {int(r["image"]): (int(r["w"]), int(r["h"])) for r in csv.DictReader(f)}


def switch_records():
    """{ROM switch number: (name, wire 1, wire 2)}: the switch table records (rom/rom_data/io/switches.csv and
    dedicated_switches.csv: name +8, wire colour messages +0x16 / +0x18); dedicated Dn is 0x80 + n."""
    import csv                                   # noqa: PLC0415
    out = {}
    io = os.path.join(ROOT, "rom", "rom_data", "io")
    with open(os.path.join(io, "switches.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[int(r["number"])] = (r["name"], r.get("msg_0x16_text", ""), r["msg_0x18_text"])
    with open(os.path.join(io, "dedicated_switches.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[int(r["rom_switch_number"])] = (r["name"], r.get("msg_0x16_text", ""), r["msg_0x18_text"])
    return out


class SwitchTest:
    """SWITCH TEST, play_sound_00f_4cae4 [0x0104cae4], run once a tick until BACK (record 0x00036ac0, posted by the
    BACK button's handler 0x0000f290 arg 1).

    - The grid on the background page: image 0xa4 (a 52 x 1 line) above, image 0xa7 (50 x 3) once per row of 16
      matrix switches (1-0x40: 4 rows, switch_rec_d2d4 gives number - 1, >> 4), 0xa4, the rows of the dedicated
      switches (0x81-0xa0: 2), 0xa4; centred in the 32 rows; "SWITCH TEST" fit (fonts 2, 0; 0x4c wide) at
      x = 50 + (128 - 50) / 2 = 89, y 8.
    - Every tick: a 3 x 3 dot (image 0xa5) for each closed switch at x 2 + 3 k, 3 rows a grid row; a switch
      newly closed since the last tick goes into a ring of 8 (dropped when full) with sound 0x00f.
    - The text column at x 89, font 0, centred: with the ring caught up, "NONE" (y 0xf) and "LAST SW. #%d"
      (msg 0x113, matrix) or "LAST SW. D-%d" (msg 0x114, dedicated, number - 0x80) of the last one (y 0x15); else the
      entry's name (y 0xf), its number line (y 0x15) and "%s / %s" of its two wire colours (y 0x1b) when both
      are set. An entry shows 3 ticks at least; the last one stays while its switch is closed, then the ring is
      caught up.
    """
    RING = 8
    TOP, ROW, DOT = 0xa4, 0xa7, 0xa5
    MATRIX, DEDICATED = (1, 0x40), (0x81, 0xa0)
    SOUND = 0x00f

    def __init__(self):
        sizes = _image_sizes()
        self.top_h = sizes[self.TOP][1]
        self.row_w, self.row_h = sizes[self.ROW]
        self.records = switch_records()
        self.rows = [((hi - 1) >> 4) - ((lo - 1) >> 4) + 1 for lo, hi in (self.MATRIX, self.DEDICATED)]
        height = self.row_h * sum(self.rows) + self.top_h * 3
        self.y0 = (0x20 - height) // 2 if height < 0x21 else 0
        self.x_text = self.row_w + (0x80 - self.row_w) // 2
        self.ring = [0] * self.RING
        self.write = self.read = 0
        self.frames = 0
        self.closed = set()

    def closing(self, num):
        """A switch closed since the last tick: into the ring unless it is full. Returns the sound to play."""
        self.closed.add(num)
        nxt = (self.write + 1) % self.RING
        if nxt != self.read:
            self.ring[self.write] = num
            self.write = nxt
        return self.SOUND

    def opening(self, num):
        self.closed.discard(num)

    @staticmethod
    def number_text(num):
        return "LAST SW. #{}".format(num) if num < 0x80 else "LAST SW. D-{}".format(num - 0x80)

    def tick(self):
        """One pass of the loop: the drawing, then the ring's read position."""
        draw = []
        y = self.y0
        starts = []
        draw.append(rd.image(self.TOP, 0, y))
        y += self.top_h
        for rows in self.rows:
            starts.append(y)
            for _ in range(rows):
                draw.append(rd.image(self.ROW, 1, y))
                y += self.row_h
            draw.append(rd.image(self.TOP, 0, y))
            y += self.top_h
        draw.append(rd.fit("SWITCH TEST", self.x_text, 8, (2, 0), 2, width=0x4c))
        for (lo, hi), rows, y_start in zip((self.MATRIX, self.DEDICATED), self.rows, starts):
            x, yy = 2, y_start
            for num in range(lo, lo + rows * 16):
                if num in self.closed:
                    draw.append(rd.image(self.DOT, x, yy))
                x += 3
                if x >= self.row_w:
                    x, yy = 2, yy + 3
        nxt = self.read
        if self.read == self.write:
            draw.append(rd.text("NONE", 0, self.x_text, 0xf, 2))
            last = self.ring[(self.read - 1) % self.RING]
            if last:
                draw.append(rd.text(self.number_text(last), 0, self.x_text, 0x15, 2))
        else:
            num = self.ring[self.read]
            name, wire1, wire2 = self.records.get(num, ("", "", ""))
            draw.append(rd.text(name, 0, self.x_text, 0xf, 2))
            draw.append(rd.text(self.number_text(num), 0, self.x_text, 0x15, 2))
            if wire1 and wire2:
                draw.append(rd.text("{} / {}".format(wire1, wire2), 0, self.x_text, 0x1b, 2))
            self.frames += 1
            if self.frames > 2:
                following = (self.read + 1) % self.RING
                if following == self.write:
                    if num not in self.closed:
                        nxt = following
                else:
                    nxt = following
                self.frames = 0
        self.read = nxt
        return draw


def coil_records():
    """{coil: record} from rom/rom_data/io/coils.csv (the coil table, DAT_00030b48 entries 1-0x23): name +0xc,
    test pulse +0x10, wire colours +0x14 / +0x16, flags (0x800 hidden in the tests), the test function +4."""
    import csv                                   # noqa: PLC0415
    with open(os.path.join(ROOT, "rom", "rom_data", "io", "coils.csv"), encoding="utf-8") as f:
        return {int(r["coil"]): {"name": r["name"], "ms": int(r["test_pulse_ms"] or 0), "flags": int(r["flags_hex"], 16),
                                 "fn": r["test_fn"], "wires": (r["wire_color_1"], r["wire_color_2"])}
                for r in csv.DictReader(f)}


class SingleCoilTest:
    """SINGLE COIL TEST, play_sound_010_46f4c [0x01046f4c], ported line by line: one pass every 2 ticks
    (deff_frame_sleep(2)) until BACK.

    - Header (font 2, y 5): "COIL TEST" (msg 0x11b) with the power on (RAM 0x00031470 & 3); with it off "50V / 20V
      DISABLED" (msg 0x11c) blinking 4 passes on, 4 off, with sound 0x010 at each blink, 5 times, then steady.
    - The coil (font 6, y 0xe: "%s" msg 0x11e, +0x19 is 1 for every coil), "#%d" (msg 0x120, font 8, y 0x16), the
      wire colours "%s / %s" (font 8, y 0x1e).
    - MINUS / PLUS (sounds 0x00a / 0x00b): the previous / next coil of 1-0x23 not hidden (flag 0x800)
      [0x01046e7c] [0x01046eec]; SELECT: the coil's test task coil_task_body_46e24 [0x01046e24] (the record's test
      function, else coil_pulse_now_wait for the test pulse); while it runs the buttons are ignored (and dropped when
      it ends); BACK while it runs stops it (sound 0x009) and the test stays; BACK otherwise leaves (sound 0x009).
    """
    PASS_TICKS = 2
    COUNT = 0x23
    TITLE = "COIL TEST"                     # msg 0x11b
    MASK, WANT = 0x800, 0                   # shown: flags & 0x800 == 0 [0x01046eec]
    CYCLING = False
    REST_PASSES = 0x3e                      # cycling: passes between the end of a coil's task and the next coil

    def __init__(self, coils, power_on):
        self.coils = coils
        self.power_on = power_on            # () -> bool: RAM 0x00031470 & 3 != 0
        self.blinks = 5                     # local_44
        self.index = self.next(0)
        self.running = False                # bVar11
        self.counter = 4                    # uVar12
        self.disabled = not power_on()      # bVar2

    def _shown(self, n):
        rec = self.coils.get(n)
        return rec is not None and rec["flags"] & self.MASK == self.WANT

    def next(self, n):
        start = n
        while True:
            n = n + 1 if n < self.COUNT else 1
            if self._shown(n) or n == start:
                return n

    def prev(self, n):
        start = n
        while True:
            n -= 1
            if n == 0 or n > self.COUNT:
                n = self.COUNT
            if self._shown(n) or n == start:
                return n

    def frame(self):
        """The drawing of one pass and the sounds it plays (the header's warning sound)."""
        sounds = []
        step = self.counter - 1
        draw = []
        if self.disabled:
            if self.blinks and step == 3:
                sounds.append(0x010)
            if step >= 0 or self.blinks < 2:
                draw.append(rd.text("50V / 20V DISABLED", 2, 0x40, 5, 2))
        else:
            draw.append(rd.text(self.TITLE, 2, 0x40, 5, 2))
        rec = self.coils.get(self.index)
        if rec:
            draw.append(rd.text(rec["name"], 6, 0x40, 0xe, 2))
            draw.append(rd.text("#{}".format(self.index), 8, 0x40, 0x16, 2))
            draw.append(rd.text("{} / {}".format(*rec["wires"]), 8, 0x40, 0x1e, 2))
        if step <= -4:
            step = 4
            self.blinks = max(self.blinks - 1, 0)
        on = self.power_on()
        became_off = (not on) and not self.disabled    # bVar2 ^ 1 while the power is off: it just went off
        self.counter = step
        if became_off:
            self.counter, self.blinks = 4, 5
        self.disabled = not on
        return draw, sounds


class SingleFlashLampTest(SingleCoilTest):
    """SINGLE FLASH LAMP TEST, play_sound_010_492b8 [0x010492b8]: the single coil test's loop over the flashers
    (flags & 0x1004 == 4 [0x01049248] [0x010491c8]), header "FLASH LAMP TEST" (msg 0x130) or "50V / 20V DISABLED"
    (msg 0x131), the same texts (msgs 0x132 / 0x134) and test task (coil_task_body_49170 [0x01049170])."""
    TITLE = "FLASH LAMP TEST"
    MASK, WANT = 0x1004, 4

    def __init__(self, coils, power_on):
        SingleCoilTest.__init__(self, coils, power_on)


class CyclingCoilTest(SingleCoilTest):
    """CYCLING COIL TEST, play_sound_010_46a98 [0x01046a98]: the same screen ("CYCLING COIL TEST", msg 0x121, or the
    power warning msg 0x122); no button but BACK is read. Each pass with no test task starts the coil's
    (coil_task_body_469e0 [0x010469e0]); once it has ended, 0x3e passes later the next coil not hidden
    (service_index_check_46a38 [0x01046a38]) takes its turn."""
    TITLE = "CYCLING COIL TEST"
    CYCLING = True


class CyclingFlashLampTest(SingleCoilTest):
    """CYCLING FLASH LAMP TEST [0x01048de4]: the cycling loop over the flashers (flags & 0x1004 == 4
    [0x01048d74]), "CYCLING FLASH LAMP TEST" (msg 0x135) or the power warning (msg 0x136)."""
    TITLE = "CYCLING FLASH LAMP TEST"
    MASK, WANT = 0x1004, 4
    CYCLING = True


def _lamp_tables():
    """The lamp wire tables, array descriptors in RAM: 0x00030c14 (10 rows: wire colour, connector pin, driver) and
    0x00030c20 (8 columns), entries of 4 messages at 0x040d11c8 / 0x040d1220 (code; read in the ROM's RAM after
    its start-up, rom/rom_data/io/lamp_wires.csv)."""
    import csv                                   # noqa: PLC0415
    rows, cols = {}, {}
    with open(os.path.join(ROOT, "rom", "rom_data", "io", "lamp_wires.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            (rows if r["table"] == "row" else cols)[int(r["index"])] = (r["wire"], r["pin"], r["driver"])
    return rows, cols


def lamp_names():
    import csv                                   # noqa: PLC0415
    with open(os.path.join(ROOT, "rom", "rom_data", "io", "lamps.csv"), encoding="utf-8") as f:
        return {int(r["lamp"]): r["name"] for r in csv.DictReader(f)}


class LampTest:
    """The lamp tests' common screen: the lamp grid of the ROM's lamp tests (images 0xaa 28 x 1 above and below,
    0xac 26 x 3 once per row of 8 lamps, 10 rows; centred in the 32 rows: y0 = (32 - (3 x 10 + 1 x 2)) >> 1),
    a 3 x 3 dot (image 0xab) per lamp shown at x 2 + 3 x ((n - 1) & 7), y y0 + 1 + 3 x ((n - 1) >> 3)
    (draw_bitmap_bits_4a5f8 [0x0104a5f8]), the texts centred at x 26 + (128 - 26) / 2 = 77.
    lamp_rec_of_7578 [0x00007578]: lamp n is record n - 1, row (n - 1) >> 3, column bit (n - 1) & 7."""
    PASS_TICKS = 2
    LINE, ROW, DOT = 0xaa, 0xac, 0xab
    LEFF = 0
    COUNT = 0

    def __init__(self):
        sizes = _image_sizes()
        self.line_h = sizes[self.LINE][1]
        self.row_w, self.row_h = sizes[self.ROW]
        self.dot_w = sizes[self.DOT][0]
        self.y0 = (0x20 - (self.row_h * 10 + self.line_h * 2)) >> 1
        self.x_text = self.row_w + (0x80 - self.row_w) // 2
        self.names = lamp_names()
        self.rows, self.cols = _lamp_tables()
        self.index = 1
        self.done = False
        self.started = False

    def grid(self):
        draw = [rd.image(self.LINE, 0, self.y0)]
        y = self.y0 + self.line_h
        for _ in range(10):
            draw.append(rd.image(self.ROW, 1, y))
            y += self.row_h
        draw.append(rd.image(self.LINE, 0, y))
        return draw

    def dot(self, lamp):
        n = lamp - 1
        return rd.image(self.DOT, 2 + self.dot_w * (n & 7), self.y0 + self.line_h + self.row_h * (n >> 3))

    def wires(self, lamp):
        """lamp_row_mask_7604 [0x00007604] (column bit + 1, table 0x00030c20) / lamp_column_of_75cc [0x000075cc]
        (row + 1, table 0x00030c14): the record's own wire messages (+4, +6) are 0 for every lamp."""
        n = lamp - 1
        return "{} / {}".format(self.cols[(n & 7) + 1][0], self.rows[(n >> 3) + 1][0])

    def lamps(self):
        return [self.index]

    def texts(self):
        return []

    def step(self, pressed):
        """One pass: (draw list, actions). The single, row and column tests: the leff on the current lamp(s) from
        the start; MINUS / PLUS (sounds 0x00a / 0x00b) the previous / next one, wrapping, the leff started again
        on it; BACK (sound 0x009) kills the leff and leaves."""
        actions = []
        if not self.started:
            self.started = True
            actions.append(("leff", (self.LEFF, self.lamps())))
        if pressed[BEEP_BACK]:
            self.done = True
            return [], actions + [("sound", BEEP_BACK), ("kill", self.LEFF)]
        draw = self.grid() + [self.dot(n) for n in self.lamps()] + self.texts()
        if pressed[BEEP_MINUS]:
            self.index = self.index - 1 if self.index > 1 else self.COUNT
            actions += [("sound", BEEP_MINUS), ("leff", (self.LEFF, self.lamps()))]
        if pressed[BEEP_PLUS]:
            self.index = self.index + 1 if self.index < self.COUNT else 1
            actions += [("sound", BEEP_PLUS), ("leff", (self.LEFF, self.lamps()))]
        return draw, actions


class SingleLampTest(LampTest):
    """SINGLE LAMP TEST, start_leff_3 [0x0104a6c8]: "SINGLE LAMP TEST" (msg 0x126, font 2, y 8), the lamp's name
    (font 0, y 0xf), "LAMP #%d" (msg 0x127, font 0, y 0x15), its wires "%s / %s" (font 2, y 0x1b); lamps 1-0x50;
    leff 3 (leff_003 [0x0104a464]: every lamp off in its layer, the lamp toggled every 8 ticks)."""
    LEFF, COUNT = 3, 0x50

    def texts(self):
        x = self.x_text
        return [rd.text("SINGLE LAMP TEST", 2, x, 8, 2), rd.text(self.names.get(self.index, ""), 0, x, 0xf, 2),
                rd.text("LAMP #{}".format(self.index), 0, x, 0x15, 2), rd.text(self.wires(self.index), 2, x, 0x1b, 2)]


class RowLampTest(LampTest):
    """LAMP ROW TEST, start_leff_5 [0x0104aeac]: "ROW LAMPS TEST" (msg 0x12a, fit fonts 2, 0 in 100 dots, y 8),
    "LAMP ROW #%d" (msg 0x12b, font 0, y 0xf), the row's wire colour (font 2, y 0x15) and "%s / %s" of its
    connector pin and driver (font 2, y 0x1b), table 0x00030c14; rows 1-10, lamps 8 (r - 1) + 1 to 8 r
    (column_first_switch_4adf8, times_8_4ae10); leff 5 (leff_005 [0x0104ae28]) toggles them every 8 ticks."""
    LEFF, COUNT = 5, 10
    TITLE = "ROW LAMPS TEST"

    def lamps(self):
        return list(range(8 * (self.index - 1) + 1, 8 * self.index + 1))

    def entry(self):
        return self.rows[self.index]

    def texts(self):
        x = self.x_text
        wire, pin, driver = self.entry()
        label = "LAMP ROW #{}" if self.LEFF == 5 else "LAMP COLUMN #{}"
        return [rd.fit(self.TITLE, x, 8, (2, 0), 2, width=100), rd.text(label.format(self.index), 0, x, 0xf, 2),
                rd.text(wire, 2, x, 0x15, 2), rd.text("{} / {}".format(pin, driver), 2, x, 0x1b, 2)]


class ColumnLampTest(RowLampTest):
    """LAMP COLUMN TEST, start_leff_6 [0x0104a0d0]: "COLUMN LAMPS TEST" (msg 0x12c), "LAMP COLUMN #%d" (msg 0x12d),
    table 0x00030c20; columns 1-8, lamps c, c + 8, ... c + 0x48 (bit_index_49fb8, switch_row_letter_49ff8,
    plus_8_4a040); leff 6 (leff_006 [0x0104a04c])."""
    LEFF, COUNT = 6, 8
    TITLE = "COLUMN LAMPS TEST"

    def lamps(self):
        return list(range(self.index, self.index + 0x49, 8))

    def entry(self):
        return self.cols[self.index]


class AllLampsTest(LampTest):
    """TEST ALL LAMPS, start_leff_4 [0x01049cf4]: the grid and "ALL LAMPS TEST" (msg 0x128, font 2, y 0xb); then
    until BACK: leff 4 (leff_004 [0x01049cac]: every lamp on in its layer) with every lamp's dot and "ALL LAMPS ON"
    (msg 0x129, font 8, y 0x18) for 15 passes, then leff 4 killed and no dots for 15 passes. MINUS / PLUS do
    nothing."""
    LEFF = 4
    HALF = 0xf

    def __init__(self):
        LampTest.__init__(self)
        self.n = 0

    def step(self, pressed):
        if pressed[BEEP_BACK]:
            self.done = True
            return [], [("sound", BEEP_BACK), ("kill", self.LEFF)]
        actions = []
        phase = self.n % (2 * self.HALF)
        if phase == 0:
            actions.append(("leff", (self.LEFF, None)))
        elif phase == self.HALF:
            actions.append(("kill", self.LEFF))
        self.n += 1
        draw = self.grid() + [rd.text("ALL LAMPS TEST", 2, self.x_text, 0xb, 2)]
        if phase < self.HALF:
            draw += [self.dot(n) for n in range(1, 0x51)] + [rd.text("ALL LAMPS ON", 8, self.x_text, 0x18, 2)]
        return draw, actions


def _leff_blink(task):
    """leff_003 / leff_005 / leff_006 [0x0104a464] [0x0104ae28] [0x0104a04c]: a layer owning every lamp, all off
    (lamp_row_fill_7b74 0xff on the mask), the task's lamp(s) toggled (lamp_bit_flash_78dc) every 8 ticks."""
    lamps_ = task.data.get("lamp") or []
    for n in range(1, 0x51):
        task.set(n, False)

    def run(t):
        for n in lamps_:
            t.toggle(n)
        t.sleep(8, run)
    run(task)


def _leff_all_off(task):
    """leff_002 [0x0002b238], the service menu's (start_deff_3 [0x0000ed90]), priority 253: a layer owning every
    lamp (lamp_row_fill_7b74 0xff on the mask), all off, until killed; the lamp tests' leffs (254) draw over it."""
    for n in range(1, 0x51):
        task.set(n, False)


def _leff_all_on(task):
    """leff_004 [0x01049cac]: a layer owning every lamp, all on (lamp_rows_fill_7b24 0xff), until killed."""
    for n in range(1, 0x51):
        task.set(n, True)


LOOP_TESTS = {"KNOCKER TEST": "KnockerTest", "BALL TROUGH TEST": "TroughTest", "SOUND/SPEAKER TEST": "SoundTest",
              "DOT MATRIX TEST": "DotMatrixTest", "ACTIVE SWITCH TEST": "ActiveSwitchTest",
              "OPTIMUS PRIME MOTOR TEST": "MotorTest", "BEGIN BURN-IN": "BurnInTest"}
LAMP_LEFFS = {3: _leff_blink, 4: _leff_all_on, 5: _leff_blink, 6: _leff_blink}
LAMP_TESTS = {"SINGLE LAMP TEST": SingleLampTest, "TEST ALL LAMPS": AllLampsTest, "LAMP ROW TEST": RowLampTest,
              "LAMP COLUMN TEST": ColumnLampTest}
