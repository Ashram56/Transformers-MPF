"""The test bench's player: starts games, shoots the shots, drains, and checks what must always hold.

BenchCase is the base of every bench test (docs/test_bench.md). It runs the real game code on MPF's smart_virtual
platform (coil pulses move the balls between the ball devices) and plays the part of the player and of the balls:
- start_game(players), plunge(), end_ball(), end_game();
- shoot(name): one of SHOTS, waiting first for the ROM's own switch debounces (orbit tokens, the center lane's
  one-hit-per-pass, ...) so that the shot counts; hit(switch) closes a switch as it is;
- eject() and lock(): a ball into the left eject (the Allspark) or the Megatron lock, back when the game kicks it;
- drain(n), with the ball census: a ball can only drain or enter a hole when one is rolling on the playfield;
- check(): the invariants of section "Invariants" in docs/test_bench.md (ball count, balls in play, scores, flags).
Class attributes set the game up: SIDE (1 Autobot, 2 Decepticon), ADJ ({adjustment number: value}, set the way
the service menu sets them), PLAYERS.
"""
from tests.tf_test import TfTestCase

AUTOBOT, DECEPTICON = 1, 2
TROUGH = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")
LOCKS = ("s_m_tron_lock_1_back", "s_megatron_lock_2", "s_megatron_lock_3", "s_megatron_lock_4")
SHOOTER, EJECT = "s_shooter_lane", "s_left_eject"
DEVICE_SWITCHES = TROUGH + LOCKS + (SHOOTER, EJECT)
BALLS = 4

# the shots by name: the switch that makes them (tf/switches.py)
SHOTS = {"left_orbit": 6, "left_ramp": 10, "center": 11, "right_ramp": 14, "right_orbit": 12, "optimus": 51,
         "bumblebee": 1, "spinner": 34, "back_door": 13, "captive": 45,
         "energon_left": 2, "energon_center": 49, "energon_right": 46,
         "bank_top": 50, "bank_bottom": 37, "pop_top": 30, "pop_right": 31, "pop_bottom": 32,
         "sling_left": 26, "sling_right": 27, "top_lane_left": 8, "top_lane_right": 7,
         "return_left": 25, "return_right": 28, "outlane_left": 24, "outlane_right": 29,
         "ramp_entry_left": 4, "ramp_entry_right": 35}
MS_SHOTS = {0: "eject", 1: "left_orbit", 2: "left_ramp", 3: "right_ramp", 4: "right_orbit"}     # mode-start shots
BATTLE_SHOTS = {0: "eject", 1: "left_orbit", 2: "left_ramp", 3: "center", 4: "right_ramp", 5: "right_orbit",
                6: "bumblebee"}                                                                  # battle shot ids
MAIN_SHOTS = ("left_orbit", "left_ramp", "center", "right_ramp", "right_orbit")
# seconds the ROM ignores a repeat of these shots (tf/features/battles.py: ORBIT_TOKEN_S, RIGHT_IGNORE_S,
# RIGHT_REPEAT_S, CENTER_LOCK_S; tf/features/optimus.py HIT_IGNORE_S; tf/features/twobank.py HIT_TICKS)
LEFT_ORBIT_GAP, RIGHT_ORBIT_GAP, CENTER_GAP, BANK_GAP = 2.4, 3.1, 1.1, 0.2
MULTIBALL_FLAGS = (0x1e, 0x1f, 0x22, 0x25, 0x29, 0x3e)
MODE_FLAGS = MULTIBALL_FLAGS + (0x3c,)


class BenchCase(TfTestCase):
    SIDE = DECEPTICON
    ADJ = {}
    PLAYERS = 1

    def setUp(self):
        super().setUp()
        self.tf.forced["side"] = [0 if self.SIDE == AUTOBOT else 1] * 4
        for num, value in self.ADJ.items():
            self.set_adj(num, value)
        self._last = {}                 # shot family -> time of the driver's last hit
        self._score_seen = {}
        self.balls_started = 0          # every ball start, the extra balls' too: what tells one ball from the next
        self.machine.events.add_handler("ball_started", self._count_ball)
        self.fill_trough()

    def _count_ball(self, **kwargs):
        self.balls_started += 1

    # ------------------------------------------------------------------ small helpers

    @property
    def game(self):
        return self.machine.game

    @property
    def pd(self):
        return self.tf.pd

    @property
    def now(self):
        return self.machine.clock.get_time()

    @property
    def score(self):
        return self.game.player.score if self.game and self.game.player else 0

    def feature(self, name):
        return self.tf.features_by_name[name]

    def set_adj(self, num, value):
        """An operator change, as the service menu's adjustment editor makes it (tf/settings.py)."""
        self.tf.adj[num] = value

    def wait(self, seconds):
        self.advance_time_and_run(seconds)

    def active(self, name):
        return bool(self.machine.switches[name].state)

    def sw(self, name, state):
        self.machine.switch_controller.process_switch(name, state, True)

    def events(self, ev, **match):
        return [e for e in self.tf.trace.of(ev) if all(e.get(k) == v for k, v in match.items())]

    def deffs(self):
        return [e["id"] for e in self.tf.trace.of("deff_start")]

    def audits(self):
        return [e["id"] for e in self.tf.trace.of("audit")]

    def mark(self):
        """Forget the trace so far: the next events()/deffs()/audits() see only what follows."""
        del self.tf.trace.events[:]

    # ------------------------------------------------------------------ the balls

    def census(self):
        """Where the four balls are: (trough, shooter lane, left eject, Megatron lock, playfield)."""
        trough = sum(self.active(n) for n in TROUGH)
        locks = sum(self.active(n) for n in LOCKS)
        shooter, eject = int(self.active(SHOOTER)), int(self.active(EJECT))
        return trough, shooter, eject, locks, BALLS - trough - shooter - eject - locks

    def rolling(self):
        """Balls on the playfield (not in a ball device)."""
        return self.census()[4]

    def busy(self):
        """A ball is on its way: a pending multiball launch, a ball device ejecting or waiting, a serve after a
        lock or a ball save, a kept ball kicked out of the lock, or the last ball just drained and the ball is about to end."""
        megatron = self.feature("megatron")
        if self.tf._mb_pending or self.tf.task_running("multiball") or megatron.pending or megatron.kicking:
            return True
        if self.census()[3] < megatron.locked_held:      # a kept ball just left the lock (ball search)
            return True
        if any(getattr(d, "state", "idle") not in ("idle", "waiting_for_ball", "waiting_for_target_ready")
               for d in self.machine.ball_devices.values()):
            return True
        game = self.game
        if game and self.tf.in_play:
            trough, shooter, eject, locks, rolling = self.census()
            return game.balls_in_play == 0 or shooter + eject + rolling < game.balls_in_play
        return False

    def settle(self, limit=30.0):
        """Wait until every ball the game is serving has arrived and nothing is left to plunge."""
        waited = 0.0
        while waited < limit:
            self.plunge(wait=0)
            if not self.busy():
                self.wait(0.05)
                if not self.busy():
                    break
            self.wait(0.25)
            waited += 0.25

    def plunge(self, wait=1.2):
        """The player's plunge: the ball leaves the shooter lane (the game's own launches need no help)."""
        # only a ball MPF has counted in the lane (its entrance count delay): one plunged sooner would be a ball
        # the trough never sees arrive
        if self.active(SHOOTER) and self.machine.ball_devices["bd_shooter_lane"].balls > 0:
            self.sw(SHOOTER, 0)
        if wait:
            self.wait(wait)
        self._last["right_block"] = self.now

    def land(self, limit=2.5):
        """Wait until the balls on their way to the playfield are on it for MPF too (a kickout is confirmed by a
        playfield switch or after its eject time-out). A real ball takes longer than that to reach another
        device; a bench ball moved sooner would be one MPF counts twice."""
        waited = 0.0
        while waited < limit and any(getattr(d, "state", "idle") in ("ball_left", "failed_confirm")
                                     for d in self.machine.ball_devices.values()):
            self.wait(0.1)
            waited += 0.1

    def drain(self, n=1, wait=0.3):
        """n rolling balls fall into the trough. Returns how many did (a ball must be on the playfield)."""
        done = 0
        self.land()
        for _ in range(n):
            if self.rolling() <= 0:
                break
            self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
            done += 1
            self.wait(wait)
        return done

    # ------------------------------------------------------------------ the game

    def start_game(self, players=None, plunge=True):
        players = players or self.PLAYERS
        self._score_seen = {}
        self._last = {}
        for _ in range(players):
            self.hit_and_release_switch("s_start_button")
            self.wait(0.6)
        self.wait(2.0)
        self.assertIsNotNone(self.game, "the game did not start")
        self.assertEqual(players, len(self.game.player_list))
        if plunge:
            self.plunge()

    def validate(self):
        """Make the playfield valid with the least rules: one right orbit spinner turn (a force switch)."""
        if not self.tf.pf_valid:
            self.hit("s_right_orbit_spinner", wait=0.2)

    def wait_ball_save(self, limit=40.0):
        waited = 0.0
        while (self.tf.ball_save or self.tf.mb_save_running()) and waited < limit:
            self.wait(0.5)
            waited += 0.5

    def end_ball(self, limit=90.0):
        """Lose the ball in play for good: validate, let the ball save run out, drain everything, then wait for the
        next ball (or the game's end). Returns True when the game goes on."""
        game = self.game
        if not game:
            return False
        started = self.balls_started
        self.settle()
        self.validate()
        self.wait_ball_save()
        waited = 0.0
        while self.game and self.balls_started == started and waited < limit:
            self.plunge(wait=0)
            if self.tf.tilted and self.rolling():
                self.drain(self.rolling())                  # a tilted ball: nothing to wait for
            elif self.tf.in_play and self.rolling():
                self.validate()
                self.wait_ball_save()
                self.drain(self.rolling())
            self.wait(0.5)
            waited += 0.5
        self.assertLess(waited, limit, "the ball never ended: census {} state {:#x} balls_in_play {}".format(
            self.census(), self.tf.state, self.tf.balls_in_play()))
        self.wait(2.5)                      # the next ball's serve
        self.settle()
        self._last = {}
        return bool(self.game)

    def end_game(self, limit=40):
        """Play the game out by losing every ball; then wait for the attract mode."""
        balls = 0
        while self.game and balls < limit:
            self.plunge()
            self.end_ball()
            balls += 1
        self.assertIsNone(self.game, "the game did not end after {} balls".format(balls))
        self.wait(2)
        self.drain(self.rolling())          # the balls the Megatron lock kept roll home
        self.wait(10)

    # ------------------------------------------------------------------ switches and shots

    def hit(self, switch, wait=0.3):
        """Close and open a playfield switch (name or SAM number). Returns the points it scored."""
        name = switch if isinstance(switch, str) else self.switch_name(switch)
        before = self.score
        self.hit_and_release_switch(name)
        if wait:
            self.wait(wait)
        return self.score - before

    @staticmethod
    def switch_name(num):
        from tf.switches import SW
        return SW[num]

    def _gap(self, key, seconds):
        last = self._last.get(key)
        if last is not None and self.now - last < seconds:
            self.wait(seconds - (self.now - last))

    def shoot(self, shot, wait=0.3):
        """Make a shot by name so that the ROM counts it. Returns the points scored."""
        num = SHOTS[shot]
        if shot == "left_orbit":
            self._gap("left_orbit", LEFT_ORBIT_GAP)
        elif shot == "right_orbit":
            self._gap("right_block", RIGHT_ORBIT_GAP)
            self._gap("right_orbit", RIGHT_ORBIT_GAP)
        elif shot in ("center", "optimus"):
            self._gap("center", CENTER_GAP)
        elif shot in ("bank_top", "bank_bottom"):
            self._gap("bank", BANK_GAP)
        points = self.hit(num, wait)
        at = self.now - wait
        if shot == "left_orbit":
            self._last["left_orbit"] = self._last["right_block"] = at
        elif shot == "right_orbit":
            self._last["right_orbit"] = at
        elif shot in ("center", "optimus"):
            self._last["center"] = at
            if shot == "center":
                self._last["right_block"] = at
        elif shot == "back_door":
            self._last["right_block"] = at
        elif shot in ("bank_top", "bank_bottom"):
            self._last["bank"] = at
        return points

    def eject(self, limit=40.0):
        """A ball into the left eject (the Allspark); waits until the game kicks it out. Returns the points."""
        self.assertGreater(self.rolling(), 0, "no ball on the playfield for the left eject")
        before = self.score
        self.land()
        self.sw(EJECT, 1)
        waited = 0.0
        while self.active(EJECT) and waited < limit:
            self.wait(0.25)
            waited += 0.25
        self.assertFalse(self.active(EJECT), "the left eject never kicked its ball out")
        self.wait(0.5)
        return self.score - before

    def lock(self, wait=4.5):
        """A ball into the Megatron lock (its first free switch). Returns the points; the ball stays (locked) or
        is kicked out, and a locked ball's replacement is served and launched meanwhile."""
        self.assertGreater(self.rolling(), 0, "no ball on the playfield for the Megatron lock")
        before = self.score
        free = [n for n in LOCKS if not self.active(n)]
        self.assertTrue(free, "the Megatron lock is full")
        self.land()
        self.sw(free[0], 1)
        self.wait(wait)
        self.plunge(wait=0.2)
        return self.score - before

    # ------------------------------------------------------------------ getting into the modes

    def shoot_any(self, name):
        """A shot by name, the left eject included ("eject")."""
        return self.eject() if name == "eject" else self.shoot(name)

    def poke_wizard(self, reqs):
        """Set-up shortcut: mark wizard requirements completed (as the reference scenarios' pokes do)."""
        req = self.feature("wizard").reqs()
        for r in reqs:
            req[r] = [max(req[r][0], 1), max(req[r][1], 1)]
        self.tf.request_refresh()

    def start_battle(self, key=None):
        """Make the lit mode-start shots until a battle starts (four hits at factory settings); key lights that
        battle first ("ss" Starscream, "sw" Shockwave, "bo" Blackout, "dv" Devastator, "bb" Bumblebee,
        "ih" Ironhide, "mf" Mudflap & Skids, "ra" Ratchet). Returns the running battle."""
        battles = self.feature("battles")
        if key:
            self.pd.battle_lit = next(b.bit for b in battles.battles if b.key == key)
        for _ in range(8):
            if battles.running():
                break
            lit = [i for i in (1, 2, 3, 4, 0) if self.pd.ms_lit & (1 << i)]
            self.assertTrue(lit, "no mode-start shot is lit")
            self.shoot_any(MS_SHOTS[lit[0]])
        battle = battles.running()
        self.assertIsNotNone(battle, "no battle started after the mode-start shots")
        return battle

    def lit_shots(self, battle):
        """The names of the battle's lit shots."""
        return [name for shot, name in BATTLE_SHOTS.items() if battle.lit & (1 << shot)]

    def complete_battle(self, battle, limit=40):
        """Make the battle's lit shots until it is completed (its bit in the player's battle_completed)."""
        for _ in range(limit):
            if self.pd.battle_completed & battle.bit or not battle.scoring:
                break
            lit = self.lit_shots(battle)
            self.assertTrue(lit, "battle {} has no lit shot".format(battle.key))
            # the quick shots first: the orbits wait for the ROM's debounce
            self.shoot_any(sorted(lit, key=("left_ramp", "right_ramp", "center", "bumblebee", "eject",
                                           "left_orbit", "right_orbit").index)[0])
        self.assertTrue(self.pd.battle_completed & battle.bit, "battle {} not completed".format(battle.key))

    def start_megatron_multiball(self):
        """Light and make the four locks (factory setting: all four lit at game start)."""
        megatron = self.feature("megatron")
        for _ in range(12):
            if megatron.running():
                break
            if not self.pd.mtl_lit:
                self.complete_energon()
            self.lock()
        self.assertIsNotNone(megatron.running(), "the Megatron multiball did not start")
        return megatron.running()

    def start_optimus_multiball(self):
        """Four center lanes for the battle, then the Optimus hits (factory setting: 3 + the starting one)."""
        optimus = self.feature("optimus")
        for _ in range(6):
            if self.pd.opt_battle:
                break
            self.shoot("center")
        self.assertTrue(self.pd.opt_battle, "the Optimus battle did not start")
        for _ in range(12):
            if optimus.running():
                break
            self.shoot("optimus")
        self.assertIsNotNone(optimus.running(), "the Optimus multiball did not start")
        return optimus.running()

    def complete_energon(self):
        """The three Energon targets: one set (an Allspark banked, a Megatron lock completion)."""
        for name in ("energon_left", "energon_center", "energon_right"):
            self.shoot(name)

    # ------------------------------------------------------------------ invariants

    def running_modes(self):
        """What the features say is running (for the leak checks)."""
        tf = self.tf
        f = tf.features_by_name
        out = []
        out += ["battle " + b.key for b in f["battles"].battles if b.active or b.scoring]
        out += ["megatron mb" for s in f["megatron"].sides.values() if s.active or s.alive]
        out += ["optimus mb" for s in f["optimus"].sides.values() if s.active or s.alive]
        wizard = f["wizard"]
        out += ["side mode"] if wizard.side_running else []
        out += ["wizard mb"] if wizard.wmb_running or wizard.wmb_alive else []
        out += ["double scoring"] if f["bumblebee"].running else []
        out += ["fast scoring"] if f["twobank"].running else []
        out += ["flag {:#x}".format(flag) for flag in MODE_FLAGS if tf.flag(flag)]
        return out

    def check(self, settled=True):
        """The invariants (docs/test_bench.md). Call it after settle(), or with settled=False for the checks that
        hold at any moment."""
        tf = self.tf
        trough, shooter, eject, locks, rolling = self.census()
        self.assertGreaterEqual(rolling, 0, "more than {} balls: census {}".format(BALLS, self.census()))
        for device, count in (("bd_trough", trough), ("bd_megatron", locks)):
            self.assertLessEqual(self.machine.ball_devices[device].balls, BALLS)
        game = self.game
        if not game:
            if settled:
                self.assertEqual(BALLS, trough, "balls not home after the game: census {}".format(self.census()))
                left = sorted(str(t) for t in tf.tasks if t != 0x2d)      # 0x2d: the attract START lamp blink
                self.assertFalse(left, "tasks left after the game: {}".format(left))
            return
        for player in game.player_list:
            seen = self._score_seen.get(player.number, 0)
            self.assertGreaterEqual(player.score, seen, "player {}'s score went down".format(player.number))
            self._score_seen[player.number] = player.score
        self.assertGreaterEqual(tf.pf_mult, 1)
        megatron = self.feature("megatron")
        self.assertGreaterEqual(megatron.locked_held, 0)
        if settled and tf.in_play and not self.busy():
            self.assertLessEqual(megatron.locked_held, locks, "more balls counted locked than the lock holds")
            self.assertEqual(BALLS - trough - megatron.locked_held, game.balls_in_play,
                             "balls in play {} but census {} with {} locked".format(
                                 game.balls_in_play, self.census(), megatron.locked_held))
            self.assertGreaterEqual(game.balls_in_play, 1)
            if game.balls_in_play < 2:
                self.assertFalse([flag for flag in MULTIBALL_FLAGS if tf.flag(flag)],
                                 "a multiball flag with one ball in play")

    def check_fresh_ball(self):
        """At a ball start nothing of the previous ball (or player) may still run."""
        self.assertEqual([], self.running_modes(), "left running at a ball start")
        self.assertEqual(1, self.tf.pf_mult)
        self.assertEqual(0, self.pd.get("bonus_count", 0))
