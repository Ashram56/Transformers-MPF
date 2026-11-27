"""The Optimus Prime figure: its motor (coil 30) and its hit kicker (coil 12) (rom/rules/modes/optimus_multiball.md
4.2 and 11; code [0x010253d8] [0x010253b8] [0x01033d3c] [0x01033cfc] [0x00016c88], confirmed by traces/optimus_*.jsonl
and megatron_decepticon.jsonl).

- Position [0x010253d8]: up ('+', 0x2b) while the Optimus battle can progress, while Optimus D waits for the
  Optimus shot (its phase 2 or 3 [0x0102a0d8]) or while Megatron D is at its Optimus phase 3 (flag 0x29 or its
  end task 0xbf [0x0100e798]); down (',', 0x2c) otherwise, and with no game. The mech moves when the wanted
  position is not the one it is at, never while tilted (state 0x300) [0x010253b8]: coil 30 runs until the
  position switch closes (sw 43 OPTIMUS PRIME UP / sw 44 OPTIMUS PRIME DOWN), at most 468 ticks (motor_move_task
  [0x00016c88]); the simulator's moves confirm it (7.65 s in optimus_autobot.jsonl, 16.2 -> 23.84 s).
- Hit kicker [0x01033d3c]: every Optimus hit (sw 51) not within task 0x54 starts task 0x54: 15 ticks later coil 12
  for 64 ms, then 47 ticks more (task 0x54 [0x01033cfc]; the traces show coil 12 0.37 s after each hit).
- The simulator never moves the position switches: sw 44 stays closed (the figure reads down) and every move up
  runs into the 468-tick limit (the traces: 7642-7694 ms), after which the next rules check starts it again while
  up is still wanted (optimus_decepticon.jsonl: 14.95, 23.53, 31.81, 42.68, 51.36 s). The virtual platforms do the
  same here: the down switch starts closed and nothing else moves it, so the coil 30 runs match the traces.
- Ball search: 33 ticks into each search the motor runs to its time limit (tf/os_layer.py BALL_SEARCH_SWEEP).
- Adj 85 DISABLE OPTIMUS PRIME MOTOR = YES: the motor device's record carries adj 85 and its "disabled" method
  (vtable +0x74, 0x00017120: adj_get == 1) makes motor_goto [0x00016f88] and motor_move_task [0x00016c88] do
  nothing: the figure never moves (QA D-ADJ-85).
"""
from tf.features import Feature
from tf.os_layer import TICK

ORDER = 60
UP, DOWN = 0x2b, 0x2c
MOTOR = "c_optimus_prime_motor"
KICKER, KICKER_NUM, KICKER_MS = "c_optimus_prime", 12, 64
MOTOR_NUM = 30
SWITCH = {UP: "s_optimus_prime_up", DOWN: "s_optimus_prime_down"}
# motor_move_task [0x00016c88]: the task waits at most 0x1d4 = 468 ticks (vtable +0x24, 0x00016830); the poll
# [0x00016a24] stops the motor once the target switch is seen in 2 polls (1 ms each), after an after-run of 157 polls
# going up (table 0x040c702e: DOWN 0, UP 0x9d) (optimus_multiball.md 4.2, QA CC motor)
MOVE_TICKS = 468
AFTER_RUN_S = {UP: 0.002 + 0.157, DOWN: 0.002}
HIT_TASK, HIT_DELAY, HIT_TAIL = 0x54, 15, 47


class OptimusMech(Feature):
    name = "optimus_mech"
    HOOKS = ("sw_51", "ball_search_motor")

    def __init__(self, os_):
        super().__init__(os_)
        self.moving = None              # target position while the motor runs
        self._stop = None
        self.claimed = False            # the service test holds the motor (motor_claim [0x01025844])
        self.failed = None              # the target of a move that ran out of time (0x0003520c)
        self.last = DOWN                # the position last reached (0x00035208)
        self.virtual = "virtual" in type(self.machine.default_platform).__name__.lower()
        sc = self.machine.switch_controller
        for pos, name in SWITCH.items():
            if name in self.machine.switches:
                sc.add_switch_handler(name, (lambda p: lambda: self._arrived(p))(pos))
        self.machine.events.add_handler("tf_rules_refresh", self._check)
        self.machine.events.add_handler("init_phase_4", self._start)

    def _start(self, **kwargs):
        if self.virtual and self.position() is None and SWITCH[DOWN] in self.machine.switches:
            self._set_switches(DOWN)
        self._check()

    # ------------------------------------------------------------------ position

    def position(self):
        sc = self.machine.switch_controller
        for pos, name in SWITCH.items():
            if name in self.machine.switches and sc.is_active(self.machine.switches[name]):
                return pos
        return None

    def wanted(self):
        """[0x010253d8]."""
        os_ = self.os
        if not os_.game:
            return DOWN
        optimus = os_.features_by_name.get("optimus")
        if optimus:
            d = optimus.sides.get(2)
            if d is not None and d.active and d.phase in (2, 3):
                return UP
        megatron = os_.features_by_name.get("megatron")
        if megatron:
            d = megatron.sides.get(2)
            if d is not None and (d.active or d.alive) and d.phase == 3:
                return UP
        if optimus and optimus.battle_progress():
            return UP
        return DOWN

    def _check(self, **kwargs):
        """[0x010253b8]: start a move when the wanted position is not the one the figure is at."""
        if self.moving is not None or self.claimed or self.os.state & 0x300 or MOTOR not in self.machine.coils:
            return
        want = self.wanted()
        if self.position() != want:
            self._move(want)

    def ball_search_motor(self):
        """The ball search runs the motor too, to its time limit: event 0xc at search tick 30 [0x0103b808] starts the
        motor's search task [0x00016674] (tf/os_layer.py BALL_SEARCH_SWEEP)."""
        if self.moving is None and MOTOR in self.machine.coils:
            self._move("search")

    def goto(self, target):
        """motor_goto_check (the service test): a move to `target`, False when the motor cannot start one."""
        if self.moving is not None or MOTOR not in self.machine.coils or self.os.adj_value(85) == 1:
            return False
        self._move(target)
        return True

    def _move(self, target):
        if self.os.adj_value(85) == 1:              # motor_goto [0x00016f88]: the disabled motor does not move
            return
        self.failed = None
        self.moving = target
        self.machine.coils[MOTOR].enable()
        self.os.trace.log("coil", coil=MOTOR_NUM, on=1)
        self._stop = self.machine.clock.schedule_once(lambda: self._timed_out(), MOVE_TICKS * TICK)

    def _timed_out(self):
        """motor_move_task [0x00016c88]: the time limit without the target switch: the move failed."""
        if self.moving in SWITCH:
            self.failed = self.moving
        self._motor_off()

    def _set_switches(self, pos):
        sc = self.machine.switch_controller
        for p, name in SWITCH.items():
            if name in self.machine.switches:
                sc.process_switch(name, 1 if p == pos else 0, logical=True)

    def _arrived(self, pos):
        self.last = pos
        if self.moving == pos:
            if self._stop is not None:
                self.machine.clock.unschedule(self._stop)
            self._stop = self.machine.clock.schedule_once(lambda: (self._motor_off(), self._check()),
                                                          AFTER_RUN_S[pos])

    def _motor_off(self):
        if self._stop is not None:
            self.machine.clock.unschedule(self._stop)
            self._stop = None
        if self.moving is not None:
            self.machine.coils[MOTOR].disable()
            self.os.trace.log("coil", coil=MOTOR_NUM, on=0)
        self.moving = None

    # ------------------------------------------------------------------ the hit kicker

    def sw_51(self):
        """[0x01033d3c]: task 0x54, coil 12 after 15 ticks (the switch layer already ran its 5-tick delay)."""
        os_ = self.os
        if os_.task_running(HIT_TASK):
            return
        os_.task_start(HIT_TASK, HIT_DELAY, self._kick)

    def _kick(self):
        if KICKER in self.machine.coils:
            self.machine.coils[KICKER].pulse(KICKER_MS)
            self.os.lamps.coil_log(KICKER_NUM, KICKER_MS)
        self.os.task_start(HIT_TASK, HIT_TAIL)


def feature(os_):
    return OptimusMech(os_)
