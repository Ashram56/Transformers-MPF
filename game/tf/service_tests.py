"""The service menu's other test screens, ported from their ROM loops pass by pass (tf/service.py runs them).

Each test is an object with PASS_TICKS (ticks between passes: deff_frame_sleep / task_sleep), step(records) -> the
draw list of the pass (records: the button records 0x00036ac0 BACK, 0x00036ad0 MINUS, 0x00036ae0 PLUS,
0x00036af0 SELECT that the buttons' handlers post; a test consumes them the way its loop does), done (the loop
left) and close() (what the loop does on its way out).

- KNOCKER TEST [0x010405ec], BALL TROUGH TEST [0x010402c0], SOUND/SPEAKER TEST [0x01047ee0],
  DOT MATRIX TEST [0x01047a50], ACTIVE SWITCH TEST [0x0104b95c], OPTIMUS PRIME MOTOR TEST [0x01025844],
  BEGIN BURN-IN [0x010476b8].
"""
from tf import rom_draw as rd
from tf.features.optimus_mech import SWITCH

BACK, MINUS, PLUS, SELECT = 0x009, 0x00a, 0x00b, 0x00c          # the buttons' records, by their beep (service.py)
WARN_SOUND = 0x010


class PowerBlink:
    """The 50V / 20V warning of the coil, trough and motor tests: with the power off (RAM 0x00031470 & 3 == 0,
    the coin door open here) the warning blinks `period` passes on and `period` off, with sound 0x010 at each
    blink, 5 times, then stays; it starts again each time the power goes off."""

    def __init__(self, period, power_on):
        self.period = period
        self.power_on = power_on
        self.counter = period
        self.blinks = 5
        self.disabled = not power_on()

    def frame(self, os_):
        """(show the warning, show the title) of this pass; the bookkeeping after the pass's sleep."""
        step = self.counter - 1
        warn = title = False
        if self.disabled:
            if self.blinks and step == self.period - 1:
                os_.sound(WARN_SOUND)
            warn = step >= 0 or self.blinks < 2
        else:
            title = True
        if step <= -self.period:
            step = self.period
            self.blinks = max(self.blinks - 1, 0)
        on = self.power_on()
        self.counter = step
        if not on and not self.disabled:
            self.counter, self.blinks = self.period, 5
        self.disabled = not on
        return warn, title


class Test:
    PASS_TICKS = 2

    def __init__(self, svc):
        self.svc = svc
        self.os = svc.os
        self.done = False

    def leave(self, records):
        """The loop's end test (DAT_00036ac0 != 0): snd_play_9_ecfc on the way out."""
        if records[BACK]:
            self.done = True
            self.os.sound(BACK)
            return True
        return False

    def close(self):
        pass


class KnockerTest(Test):
    """KNOCKER TEST, draw_knocker_test_deff_frame_sleep_405ec [0x010405ec], every 2 ticks: "KNOCKER TEST" (msg 0x3aa,
    font 8, y 8), "PRESS 'SELECT' TO ACTIVATE" (msg 0x3ab, fit fonts 2, 0 [0x040c95d8], y 0xf), "KNOCKER" (msg 0x3ac,
    the same font, y 0x16), "ACTIVATING KNOCKER" (msg 0x3ad, font 2, y 0x1d) while a knock is queued or its wait runs
    (award_pending_193f4 [0x000193f4]). SELECT with none pending: adj_q24_option(2, 1) [0x00019378], one knock with
    the sound forced (adj_knocker_volume [0x00019420])."""

    def step(self, records):
        os_ = self.os
        pending = bool(getattr(os_, "_knocks", None)) or os_.task_running("knocker")
        title = rd.fit("PRESS 'SELECT' TO ACTIVATE", 0x40, 0xf, (2, 0), 2)
        draw = [rd.text("KNOCKER TEST", 8, 0x40, 8, 2), title, rd.text("KNOCKER", title["f"], 0x40, 0x16, 2)]
        if pending:
            draw.append(rd.text("ACTIVATING KNOCKER", 2, 0x40, 0x1d, 2))
        if records[SELECT]:
            records[SELECT] = 0
            if not pending:
                os_.knock(forced=True)
        self.leave(records)
        return draw


class SoundTest(Test):
    """SOUND/SPEAKER TEST, draw_sound_speaker_test_text_draw_str_page_47ee0 [0x01047ee0], every 2 ticks: the sound
    list (array 0x00030cbc, entries {name, call} at 0x040e25d0, count 7 [0x040c469c]; entry 0 INVALID): "SOUND /
    SPEAKER TEST" (msg 0x238, font 2, y 5), the entry's name (font 6, y 0xe), "#%d" (msg 0x239, font 8, y 0x16),
    "PLAYING SOUND #%d" (msg 0x23a) while its call plays, else "PRESS 'SELECT' TO PLAY" (msg 0x23b) (fit fonts 2, 0
    [0x040c9c64] in 128 dots, y 0x1d). MINUS / PLUS (sounds 0x00a / 0x00b): the call stopped (snd_chan_257b4), the
    previous / next entry, wrapping in 1-6; SELECT: the call stopped and played; BACK while it plays stops it (sound
    0x009) and the test stays; BACK otherwise leaves."""
    ENTRIES = ((0x01f, "MUSIC: DECEPTICON"), (0x01e, "MUSIC: AUTOBOT"), (0x03e, "SOUND: ENERGY BEAM"),
               (0x03f, "SOUND: CAR REV."), (0x040, "SPEECH: 'I AM OPTIMUS...'"), (0x041, "SPEECH: 'GIVE ME...'"))

    def __init__(self, svc):
        Test.__init__(self, svc)
        self.index = 1

    def call(self):
        return self.ENTRIES[self.index - 1][0]

    def step(self, records):
        os_ = self.os
        call, name = self.ENTRIES[self.index - 1]
        playing = os_.sound_playing(call)
        last = "PLAYING SOUND #{}".format(self.index) if playing else "PRESS 'SELECT' TO PLAY"
        draw = [rd.text("SOUND / SPEAKER TEST", 2, 0x40, 5, 2), rd.text(name, 6, 0x40, 0xe, 2),
                rd.text("#{}".format(self.index), 8, 0x40, 0x16, 2), rd.fit(last, 0x40, 0x1d, (2, 0), 2, width=0x80)]
        if records[MINUS]:
            records[MINUS] -= 1
            os_.sound(MINUS)
            os_.sound_stop(self.call())
            self.index = self.index - 1 if self.index > 1 else len(self.ENTRIES)
        if records[PLUS]:
            records[PLUS] -= 1
            os_.sound(PLUS)
            os_.sound_stop(self.call())
            self.index = self.index + 1 if self.index < len(self.ENTRIES) else 1
        if records[SELECT]:
            records[SELECT] = 0
            os_.sound_stop(self.call())
            os_.sound(self.call())
        if records[BACK]:
            records[BACK] = 0
            playing = os_.sound_playing(self.call())
            os_.sound_stop(self.call())
            os_.sound(BACK)
            if not playing:
                self.done = True
        return draw


class DotMatrixTest(Test):
    """DOT MATRIX TEST, deff_device_failure_2_47a50 [0x01047a50], every 6 ticks until BACK, over and over: on black
    a lit column sweeping x 0-127, then a lit row sweeping y 0-31; the same lit with a black line; then a
    checkerboard and its inverse, 32 times."""
    PASS_TICKS = 6

    def __init__(self, svc):
        Test.__init__(self, svc)
        self.frames = self._frames()

    @staticmethod
    def _frames():
        while True:
            for back in (0, 15):
                line = 15 - back
                for x in range(0x80):
                    yield [rd.box(0, 0, 0x80, 0x20, back), rd.box(x, 0, 1, 0x20, line)]
                for y in range(0x20):
                    yield [rd.box(0, 0, 0x80, 0x20, back), rd.box(0, y, 0x80, 1, line)]
            for _ in range(0x20):
                for phase in (0, 1):
                    yield [rd.checker(phase)]

    def step(self, records):
        draw = next(self.frames)
        if records[SELECT]:
            records[SELECT] = 0
        self.leave(records)
        return draw


class TroughTest(Test):
    """BALL TROUGH TEST, play_sound_010_402c0 [0x010402c0], every 2 ticks: "TROUGH TEST" (msg 0x3ae, font 0, left
    edge x 0, y 4) or the power warning (msg 0x3af, PowerBlink 4), a line at y 6 (level 3), image 0xb0 bottom left
    and 0xaf top right; the ball devices' switches (draw_switch_edge_page_4015c [0x0104015c], ball device table
    0x040d17fc): the trough's (device 1, its type 5 put in 0x00031624 [0x01039ca0]) at the positions 0x040c9588, the
    shooter lane's (device 2, type 1, 0x00031628) at 0x040c95c0: box 0xad (15 x 15) with the switch number (font 0,
    centred, +7, +9), drawn through the palette 0x040c95c8 while the switch is closed; a switch whose flags (+0x10)
    have 0x400 (the trough jam) goes to (0x5f, 0) and leaves the positions alone. SELECT: with the devices idle
    (balldev_task_running_3a4f0) and a ball in the trough (game_device_37f10), serve_ball(8) and sound 0x00c."""
    DEVICES = (((22, 21, 20, 19, 18), ((95, 15), (79, 14), (63, 13), (47, 12), (31, 11), (15, 10))),
               ((23,), ((112, 16),)))
    JAM = 22                                  # switch flags 0x483: 0x400 set

    def __init__(self, svc, numbers):
        Test.__init__(self, svc)
        self.numbers = numbers                # ROM switch number -> MPF switch
        self.power = PowerBlink(4, lambda: not self.os.coin_door_open())

    def closed(self, num):
        sw = self.numbers.get(num)
        return sw is not None and self.svc.machine.switch_controller.is_active(sw)

    def step(self, records):
        warn, title = self.power.frame(self.os)
        draw = []
        if warn:
            draw.append(rd.text("50V / 20V DISABLED", 0, 0, 4, 1))
        if title:
            draw.append(rd.text("TROUGH TEST", 0, 0, 4, 1))
        draw += [rd.box(0, 6, 0x80, 1, 3), rd.image(0xb0, 0, 0x20 - 8), rd.image(0xaf, 0x80 - 17, 0)]
        for switches, places in self.DEVICES:
            k = 0
            for num in switches:
                if num == self.JAM:
                    x, y = 0x5f, 0
                else:
                    x, y = places[k]
                    k += 1
                closed = self.closed(num)
                draw.append(rd.image(0xad, x, y, inv=closed))
                draw.append(rd.text(str(num), 0, x + 7, y + 9, 2, level=0 if closed else 15))
        if records[SELECT]:
            records[SELECT] = 0
            machine = self.svc.machine
            trough = machine.ball_devices.get("bd_trough")
            shooter = machine.ball_devices.get("bd_shooter_lane")
            idle = all(d is not None and d.state == "idle" for d in (trough, shooter))
            if idle and trough.balls:
                trough.eject(target=shooter)
                self.os.sound(SELECT)
        self.leave(records)
        return draw


class ActiveSwitchTest(Test):
    """ACTIVE SWITCH TEST, draw_active_switches_sw_bumblebee_target_4b95c [0x0104b95c], every tick: the switch
    test's grid (images 0xa4 / 0xa7, 4 matrix rows, 2 dedicated) and "ACTIVE SWITCHES" (msg 0x116, fit fonts 2, 0
    [0x040c9d54] in 0x7e - 50 dots, x 89, y 0xb); a dot (0xa5) per closed switch; one closed switch at a time is
    the one shown: the first closed found in the scan once the last one opened or had its turn; its dot blinks
    (off when its count & 4) for 0x40 passes, then the next closed one in the scan takes over; its name (font 0,
    y 0x12) and wire colours "%s / %s" (+0x16 / +0x18, font 0, y 0x18) at x 89; "NONE" (msg 0x117) with none."""
    PASS_TICKS = 1

    def __init__(self, svc, numbers):
        from tf.service import SwitchTest                # noqa: PLC0415
        Test.__init__(self, svc)
        self.grid = SwitchTest()
        self.numbers = numbers
        self.shown = 0                        # uVar15
        self.free = True                      # uVar16
        self.count = 0                        # uVar17

    def closed(self, num):
        sw = self.numbers.get(num)
        return sw is not None and self.svc.machine.switch_controller.is_active(sw)

    def step(self, records):
        g = self.grid
        draw = []
        y = g.y0
        starts = []
        draw.append(rd.image(g.TOP, 0, y))
        y += g.top_h
        for rows in g.rows:
            starts.append(y)
            for _ in range(rows):
                draw.append(rd.image(g.ROW, 1, y))
                y += g.row_h
            draw.append(rd.image(g.TOP, 0, y))
            y += g.top_h
        draw.append(rd.fit("ACTIVE SWITCHES", g.x_text, 0xb, (2, 0), 2, width=0x7e - g.row_w))
        for (lo, _hi), rows, y_start in zip((g.MATRIX, g.DEDICATED), g.rows, starts):
            x, yy = 2, y_start
            for num in range(lo, lo + rows * 16):
                if not self.closed(num):
                    if num == self.shown:
                        self.free, self.shown = True, 0
                else:
                    if self.free:
                        self.count, self.shown, self.free = 0, num, False
                    if num == self.shown:
                        if not self.count & 4:
                            if self.count < 0x40:
                                draw.append(rd.image(g.DOT, x, yy))
                            else:
                                self.free = True
                        self.count += 1
                    else:
                        draw.append(rd.image(g.DOT, x, yy))
                x += 3
                if x >= g.row_w:
                    x, yy = 2, yy + 3
        if self.shown == 0:
            draw.append(rd.text("NONE", 0, g.x_text, 0x12, 2))
        else:
            name, wire1, wire2 = g.records.get(self.shown, ("", "", ""))
            draw.append(rd.text(name, 0, g.x_text, 0x12, 2))
            if wire1 and wire2:
                draw.append(rd.text("{} / {}".format(wire1, wire2), 0, g.x_text, 0x18, 2))
        self.leave(records)
        return draw


class MotorTest(Test):
    """OPTIMUS PRIME MOTOR TEST, play_sound_010_25844 [0x01025844], every tick: the motor claimed (motor_claim on
    0x000351e8, so the rules leave it alone); "OPTIMUS PRIME MOTOR TEST" (msg 0x50c, font 2, y 4) or the power
    warning (msg 0x50d, PowerBlink 8); a line at y 6 (level 3); the position switches (list 0x040c702c: 44 DOWN,
    43 UP; draw_switch_test_page_255f8 [0x010255f8]): a 19 x 11 box at x 30 and 80, y 8, outlined, or filled
    while the switch is closed, its number (font 0, left x + 3, y 0xf, dark on the filled box); while the motor
    moves "MOVING TO SWITCH %s" (msg 0x50f, y 0x1e), else "MOVE TO SWITCH %s: FAILED" (msg 0x510, y 0x18) after a
    move that timed out, and "USE -/+ OR 'SELECT' TO TEST" (msg 0x50e, y 0x1e), font 2. With the motor still:
    SELECT the position after the current one in the list (else DOWN), PLUS the next one, MINUS the previous one
    (list_find_351f0_25764 / _257dc), a move (motor_goto_check) with sound 0x00b (0x00a for MINUS)."""
    PASS_TICKS = 1
    POSITIONS = (0x2c, 0x2b)

    def __init__(self, svc):
        Test.__init__(self, svc)
        self.power = PowerBlink(8, lambda: not self.os.coin_door_open())
        self.mech = self.os.features_by_name.get("optimus_mech")
        self.started = False
        if self.mech is not None:
            self.mech.claimed = True

    def close(self):
        if self.mech is not None:
            self.mech.claimed = False

    def _goto(self, target, sound):
        mech = self.mech
        if target and mech.moving is None and mech.goto(target):
            self.started = True
            self.os.sound(sound)

    def step(self, records):
        warn, title = self.power.frame(self.os)
        draw = []
        if warn:
            draw.append(rd.text("50V / 20V DISABLED", 2, 0x40, 4, 2))
        if title:
            draw.append(rd.text("OPTIMUS PRIME MOTOR TEST", 2, 0x40, 4, 2))
        draw.append(rd.box(0, 6, 0x80, 1, 3))
        mech = self.mech
        sc = self.svc.machine.switch_controller
        n = len(self.POSITIONS)
        gap = (0x80 - 0x13 * n) // (n + 1)
        x = gap
        for pos in self.POSITIONS:
            sw = self.svc.machine.switches.get(SWITCH[pos]) if mech else None
            closed = sw is not None and sc.is_active(sw)
            if closed:
                draw.append(rd.box(x, 8, 0x13, 0xb, 15))
            else:
                draw += [rd.box(x, 8, 0x13, 1, 15), rd.box(x, 0x12, 0x13, 1, 15), rd.box(x, 8, 1, 0xb, 15),
                         rd.box(x + 0x12, 8, 1, 0xb, 15)]
            draw.append(rd.text(str(pos), 0, x + 3, 0xf, 1, level=0 if closed else 15))
            x += 0x14 + gap
        moving = mech is not None and mech.moving is not None
        if moving:
            draw.append(rd.text("MOVING TO SWITCH {}".format(mech.moving), 2, 0x40, 0x1e, 2))
        else:
            if self.started and mech is not None and mech.failed:
                draw.append(rd.text("MOVE TO SWITCH {}: FAILED".format(mech.failed), 2, 0x40, 0x18, 2))
            draw.append(rd.text("USE -/+ OR 'SELECT' TO TEST", 2, 0x40, 0x1e, 2))
        if mech is not None and not moving:
            here = mech.position() or mech.last
            if records[SELECT]:
                self._goto(self._next(here) or 0x2c, PLUS)
            if records[MINUS]:
                self._goto(self._prev(here), MINUS)
            if records[PLUS]:
                self._goto(self._next(here), PLUS)
        records[SELECT] = 0
        records[MINUS] = max(records[MINUS] - 1, 0)
        records[PLUS] = max(records[PLUS] - 1, 0)
        self.leave(records)
        return draw

    def _next(self, here):
        lst = self.POSITIONS
        return lst[lst.index(here) + 1] if here in lst and lst.index(here) + 1 < len(lst) else 0

    def _prev(self, here):
        lst = self.POSITIONS
        return lst[lst.index(here) - 1] if here in lst and lst.index(here) > 0 else 0


class BurnInTest(Test):
    """BEGIN BURN-IN, start_leff_8 [0x010476b8], every 2 ticks: "BURN-IN" (msg 0x254) or the power warning (msg
    0x255, PowerBlink 4), font 2, y 4; "TOTAL BURN-IN TIME:" (msg 0x256, font 8, y 0xe) and the time kept in the
    NVRAM word 0x10248 (stored_value_248_get_10a10, ticks: "%d:%02d" msg 0x257 or "%d:%02d:%02d" msg 0x258, font 8,
    y 0x17); "PRESS 'SELECT' TO START" (msg 0x259, fit fonts 2, 0 [0x040c9c54], y 0x1f). SELECT (sound 0x00c):
    event 0x17 (no hook in tf_180), the burn-in until BACK, one tick added to the time each tick:
    - the coils: task_coil_test_loop_47388 [0x01047388], each coil not hidden (service_index_check_46a38) and
      without flag 0x400 fires its test task, then 0x3e ticks, then the next;
    - the display: deff_device_failure_4743c [0x0104743c], the DOT MATRIX TEST's frames every 6 ticks;
    - the lamps: leff 8 (leff_008 [0x0104759c]): every lamp in its layer, the odd ones (row bytes 0xaa) then the
      even ones (0x55), 8 ticks each;
    - the sounds: task_sound_test_loop_475fc [0x010475fc], each sound test entry played until it ends (at most
      0x3a9 x 2 ticks), 6 ticks, stopped, the next.
    BACK ends it (the tasks killed, leff 8, the sound and the coil stopped, event 0x18, sound 0x009) and the screen
    comes back; BACK again leaves."""
    VAR = "tf_burn_in_ticks"                  # NVRAM word 0x10248

    def __init__(self, svc):
        Test.__init__(self, svc)
        self.power = PowerBlink(4, lambda: not self.os.coin_door_open())
        self.running = None
        variables = svc.machine.variables
        variables.configure_machine_var(self.VAR, persist=True)
        if variables.get_machine_var(self.VAR) is None:
            variables.set_machine_var(self.VAR, 0)

    @property
    def ticks(self):
        return int(self.svc.machine.variables.get_machine_var(self.VAR) or 0)

    def step(self, records):
        if self.running is not None:
            return self._burn(records)
        warn, title = self.power.frame(self.os)
        draw = []
        if warn:
            draw.append(rd.text("50V / 20V DISABLED", 2, 0x40, 4, 2))
        if title:
            draw.append(rd.text("BURN-IN", 2, 0x40, 4, 2))
        draw.append(rd.text("TOTAL BURN-IN TIME:", 8, 0x40, 0xe, 2))
        s = self.ticks // 0x3e
        h, m, sec = s // 3600, s // 60 % 60, s % 60
        draw.append(rd.text("{}:{:02d}:{:02d}".format(h, m, sec) if h else "{}:{:02d}".format(m, sec), 8, 0x40, 0x17, 2))
        draw.append(rd.fit("PRESS 'SELECT' TO START", 0x40, 0x1f, (2, 0), 2))
        if records[SELECT]:
            records[SELECT] = 0
            records[BACK] = 0
            self.os.sound(SELECT)
            self._start()
            return draw
        self.leave(records)
        return draw

    # ------------------------------------------------------------------ the burn-in

    def _start(self):
        from tf.service import coil_records                 # noqa: PLC0415
        os_ = self.os
        self.running = {"frames": DotMatrixTest._frames(), "draw": [], "coil": 0, "coil_wait": 0, "sound": 0,
                        "sound_left": 0, "sound_gap": 0, "frame_wait": 0, "coils": coil_records()}
        os_.lamps.leff_code(8, _leff_burn_in)
        os_.leff_start(8)
        self._next_coil()
        self._next_sound()

    def _next_coil(self):
        """service_index_check_46a38: the next coil not hidden (flag 0x800); one with flag 0x400 is skipped."""
        run = self.running
        coils = run["coils"]
        n = run["coil"]
        for _ in range(0x23):
            n = n + 1 if n < 0x23 else 1
            rec = coils.get(n)
            if rec is not None and not rec["flags"] & 0x800:
                break
        run["coil"] = n
        rec = coils.get(n)
        ms = 0
        if rec is not None and not rec["flags"] & 0x400 and rec["ms"]:
            names = {num: name for name, num in self.os.lamps.coil_numbers.items()}
            if names.get(n):
                self.os.lamps.flasher(names[n], rec["ms"])
            ms = rec["ms"]
        run["coil_wait"] = -(-ms // 16) + 0x3e         # the coil's task, then 0x3e ticks

    def _next_sound(self):
        run = self.running
        run["sound"] = run["sound"] + 1 if run["sound"] < len(SoundTest.ENTRIES) else 1
        call = SoundTest.ENTRIES[run["sound"] - 1][0]
        self.os.sound(call)
        run["sound_left"] = 0x3a9 * 2
        run["sound_gap"] = 0

    def _burn(self, records):
        run = self.running
        ticks = self.PASS_TICKS
        self.svc.machine.variables.set_machine_var(self.VAR, self.ticks + ticks)
        run["coil_wait"] -= ticks
        if run["coil_wait"] <= 0:
            self._next_coil()
        call = SoundTest.ENTRIES[run["sound"] - 1][0]
        if run["sound_gap"]:
            run["sound_gap"] -= ticks
            if run["sound_gap"] <= 0:
                self.os.sound_stop(call)
                self._next_sound()
        else:
            run["sound_left"] -= ticks
            if run["sound_left"] <= 0 or not self.os.sound_playing(call):
                run["sound_gap"] = 6
        run["frame_wait"] -= ticks
        if run["frame_wait"] <= 0:
            run["draw"] = next(run["frames"])
            run["frame_wait"] = DotMatrixTest.PASS_TICKS
        if records[BACK]:
            records[BACK] = 0
            self._stop()
            self.os.sound(BACK)
        return run["draw"]

    def _stop(self):
        run, self.running = self.running, None
        if run is None:
            return
        self.os.leff_stop(8)
        self.os.sound_stop(SoundTest.ENTRIES[run["sound"] - 1][0])
        self.power = PowerBlink(4, lambda: not self.os.coin_door_open())

    def close(self):
        self._stop()


def _leff_burn_in(task):
    """leff_008 [0x0104759c]: a layer owning every lamp; row bytes 0xaa (lamps (n - 1) & 7 even: 1, 3, 5, ...) and
    0x55 in turn, 8 ticks each, until killed."""
    def run(t, odd=True):
        for n in range(1, 0x51):
            t.set(n, ((n - 1) & 1 == 0) == odd)
        t.sleep(8, lambda t2: run(t2, not odd))
    run(task)
