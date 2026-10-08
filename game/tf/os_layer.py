"""The Stern SAM "OS" layer of Transformers Pro 1.80 (tf_180), rebuilt on top of MPF.

MPF owns the hardware: switches, ball devices, the trough, players and turn order. This layer adds
the ROM's own semantics on top:

- ROM tasks: named timers counted in 16.26 ms ticks (task ids are the ROM's, for cross-reference).
- Game flags, audits, adjustments (operator settings by ROM number) and the trace log.
- score_add (nothing while tilted or out of game), valid playfield, ball save, tilt, extra ball,
  the end-of-ball sequence with the bonus, and game over.
- Feature hooks: each rules feature registers functions under the ROM hook names; switch handlers call
  them in the ROM's order.

Display effects, sounds, lamp effects and tube shows are posted as MPF events
(tf_deff_<id>, tf_sound_<call>, tf_leff_<id>) and written to the trace.

Where this comes from. Transformers runs the same Stern SAM OS as Tron Legacy, whose OS was rebuilt first
(github.com/Ashram56/Tron-Legacy-MPF, game/tron/os_layer.py, checked there against reference traces). The OS
parts of tf_180 that were compared match Tron's [code]: the display effects 1-39 (same numbers and priorities,
deff table 0x040ce7c4), the lamp effects 1-19 (same flags and priorities, leff table 0x040cfe00), the sound
calls 0x001-0x019 (same channel flags, sound call table 0x040dee08), the adjustments 1-64 and the audit counters
(same names and numbers, tables 0x040cb20c and 0x040cd5a4). So this module keeps Tron's OS model: addresses in
[brackets] and the tick counts are Tron 1.74's (the same OS code sits at other addresses in tf_180, e.g. leff 13
is 0x00028168 here, 0x0002fd60 on Tron) until the ROM extraction maps tf_180's OS and records its traces.
The game's own numbers (music, speech, lamps) are in GAME below, from tf_180's tables where known; None means
not known yet, and the call is skipped.
"""
import csv
import os
import random
import re

from mpf.core.custom_code import CustomCode

from tf.trace import Trace

TICK = 0.01626          # seconds per ROM tick in play
SECOND = 62             # ticks the ROM treats as one second
START_HOLD_TICKS = 62   # adj 36 GAME RESTART: START held this long (timer 4, 0x3e ticks)

# game state word bits (Tron 0x37274)
ST_BONUS, ST_END_BALL, ST_ATTRACT, ST_TILT = 0x01, 0x04, 0x10, 0x200

# Valid playfield (OS, game_flow.md 4.3): the switch descriptor's top byte (rom/rom_data/io/switches.csv
# flags_0x0c): 0x20 = force (one hit validates), the others count (3 different needed). The spec infers that
# slings and pops (0x04) do not count, but traces/basic validates on the 3rd different switch of slings 26, 27
# and pop 30 (play music 0x01f at 7.78 s): they count, as on Tron (observed).
FORCE_SWITCHES = {7, 8, 10, 11, 12, 14, 24, 25, 28, 29, 34}
COUNTING_SWITCHES = {1, 2, 4, 5, 6, 13, 26, 27, 30, 31, 32, 35, 37, 45, 46, 49, 50, 51}

# Game flags of the running multiballs: [0x01006704], named any_timed_mode_running in the decompile, tests these
# six flags (FUN_0100f918 on Tron). 0x1e Mudflap & Skids; the others come with their specs.
MULTIBALL_FLAGS = (0x1e, 0x1f, 0x22, 0x25, 0x29, 0x3e)
BALL_SAVE_GRACE = 218        # ticks (0xda) of grace after the ball-save timer
SERVE_EJECT_TICKS = 32
LATER_SERVE_EXTRA_TICKS = 6     # every later ball start: trough eject 0.645 s after the ball start, not 0.545 s
SAVE_EJECT_TICKS = 39
AUTO_LAUNCH_TICKS = 12      # task 0x3c after an auto-launch (inferred: covers the shooter lane opening)
MB_TASK = "multiball"       # the multiball task (ROM id: trough device + 0x18)
MB_EJECT_TICKS = 101        # trough eject cycle while it launches multiball balls (Tron traces)
# A device holding a ball for the rules (Tron: the VUK) stays busy for a fixed time after its kick, however
# soon MPF confirms the eject (Tron traces: 3.0 s from the kick to the first multiball ball's launch).
DEVICE_BUSY_TICKS = 149
# A request without a held ball (add-a-ball, a drain during the save) launches its first ball after a trough
# cycle (Tron traces: 1.43 s, of which MPF's trough eject + auto-launch take ~0.6 s).
MB_FIRST_EJECT_TICKS = 51
SAVE_SERVE_TICKS = 48           # ball save re-serve: deff 20 -> shooter lane opens 1.383 s (Tron traces)
BALL_SEARCH_EVENT_TICKS = 36
BALL_SEARCH_RUN_TICKS = 297     # a search that finds no ball: the coils cycle, then the countdown resumes
BALL_SEARCH_TICKS = 104     # search task 0x2b; a drain during it ends the ball after it
OUTLANE_TASK_TICKS = 625    # drain-side tasks 0x37 / 0x38 (0x271)
SPECIAL_OVER_LIMIT_SCORE = 5000000
# the search's coil sweep (ticks after the search starts, MPF coils), then the Optimus motor and the orbit gate
# (observed, the same in every search: traces/game_flow.jsonl 32.65 / 102.01 / 126.13 / 150.45 s,
# megatron_decepticon.jsonl 68.99 s; pulses 64 ms, the pops' search time; rom_data/io/coils.csv ballsearch_fn)
BALL_SEARCH_SWEEP = ((1, ("c_optimus_prime",)), (6, ("c_top_pop_bumper",)), (7, ("c_megatron_lockup", "c_left_eject")),
                     (11, ("c_right_pop_bumper",)), (14, ("c_auto_launch",)), (16, ("c_bottom_pop_bumper",)),
                     (21, ("c_left_slingshot",)), (26, ("c_right_slingshot",)))
BALL_SEARCH_GATE = (32, 91)         # orbit gate (coil 5) held 1.48 s
BALL_SEARCH_MOTOR_TICKS = 33        # hook "ball_search_motor": the Optimus motor runs to its time limit
LOST_BALL_SEARCH = 5        # ball_search_start(5) with adj 63 LOST BALL RECOVERY: a lost ball is fed [0x0001f79c]
COINDOOR_SAVE_TICKS, COINDOOR_GRACE_TICKS = 0x138, 0xbb     # coin door opened in play, adj 41 [0x0001ff74]
POWER_OFF_DEFF = 4          # "50V / 20V DISABLED / CLOSE COIN DOOR ..." while the door is open
POWER_OFF_DIM_TICKS = 8 + 10 * 8 + 1875     # deff 4: shown, title blinks 10 x 8 ticks, 1875 ticks, then dimmed
POWER_OFF_DIM_LEVEL = 6                     # palette_fill(6) of the dimmed screen
POWER_OFF_CANCEL_SOUND = 0x009              # BACK takes the warning away [0x0000fc20]
SERVICE_CONFIRM_SECONDS = 5                 # SELECT in a game: the end-the-game question waits this long
DYNAMIC_REPLAY_MIN = 5000000                                # dynamic replay floor [0x000231a4]

# The game's own numbers the OS uses. Lamps from rom/rom_data/io/lamps.csv [code]; None = not known yet.
GAME = {
    "start_lamp": 1,            # START BUTTON
    "shoot_again_lamp": 3,      # ROLL OUT: the insert between the flippers (VPX table: li3, x 0.45 y 0.88), inferred
    "eb_lamp": 55,              # EXTRA BALL
    "special_lamp": 53,         # SPECIAL
    # the base music is the side's (tf/features/side.py)
    "music_plunger": 0x1d,      # ball start, Decepticon (observed at each ball start)
    "music_play": 0x1f,         # main play, Decepticon (observed after the first award)
    "add_player_sound": 0x048,
    "game_start_sound": None,   # none observed (traces/sounds.jsonl: only the side choice music 0x1b)
    "tilt_warning_speech": 0x052,   # observed 0.51 s (31 ticks) after sound 0x016
    "tilt_speech": 0x053,       # observed 1.01 s (62 ticks) after sound 0x017
    "tilt_speech_ticks": 62,
    "launch_sound": 0x056,      # observed on every plunge and auto-launch, 0.08 s after the lane opens
    "launch_sound_ticks": 4,
    "game_over_music": None,    # not traced yet
    "game_over_leff": None,     # Tron 133, with it
}
SHOOT_AGAIN_LAMP = GAME["shoot_again_lamp"]
START_LAMP = GAME["start_lamp"]
EB_LAMP = GAME["eb_lamp"]
SPECIAL_LAMP = GAME["special_lamp"]


def adjustment_defaults(settings_path):
    """Read {adj number: (key, default)} from the asset package's settings.yaml comments."""
    out = {}
    key = None
    with open(settings_path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"  ([a-z0-9_]+):\s+# adj (\d+)", line)
            if m:
                key, num = m.group(1), int(m.group(2))
                out[num] = [key, None]
                continue
            m = re.match(r"    default: (-?\d+)", line)
            if m and key is not None:
                out[num][1] = int(m.group(1))
                key = None
    return {n: tuple(v) for n, v in out.items()}


# shaker(pattern, min_level) [0x010307a0 -> 0x0103070c]: pattern 1/2/3 runs the motor (coil 8) 200/384/1024 ms
# (table 0x040c7620); rom/rules/modes/shaker.md
SHAKER_MS = {1: 200, 2: 384, 3: 1024}
SHAKER_ADJ = 96              # adjustment 96 SHAKER MOTOR (OPTIONAL): 0 none, 1 minimal, 2 moderate, 3 maximal


def shaker_table(shaker_csv):
    """{deff id: (pattern, min level)} from rom/rom_data/io/shaker.csv (rows "deff_NNN 0x..."; the fast-scoring
    award's call, FUN_01004644, is made by tf/features/twobank.py)."""
    deffs = {}
    if not os.path.exists(shaker_csv):
        return deffs
    with open(shaker_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            deff = re.match(r"deff_(\d+)", row["rom_function"])
            pattern = re.search(r"pattern (\d)", row["on_ms_or_pattern"])
            level = re.match(r"adj 96 (>=|=) (\d)", row["condition"])
            if deff and pattern and level:
                deffs[int(deff.group(1))] = (int(pattern.group(1)), int(level.group(2)))
    return deffs


def sample_lengths(base):
    """{sound call: [duration (s) of each sample it picks from]} from the ROM extraction's sound tables."""
    import csv
    dur = {}
    with open(os.path.join(base, "samples.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dur[int(row["sample"], 16)] = float(row.get("duration_s") or 0)
    out = {}
    with open(os.path.join(base, "sound_calls.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids = [int(x, 16) for x in (row["samples"] or "").split()]
            out[int(row["call"], 16)] = [dur.get(i, 0) for i in ids]
    return out


def sample_channels(base):
    """{sound call: [(channel mask, priority) of each sample it picks from]}: the sample's mask (samples.csv) and
    the low byte of the call's flags word (sound_calls.csv flags_0x10; meaning inferred: 0x157 with 0x9e is
    refused while a 0x0c-mask jackpot sample of a 0x1c1 call plays, played over a 0x10-mask one)."""
    import csv
    masks = {}
    with open(os.path.join(base, "samples.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            masks[int(row["sample"], 16)] = int(row.get("mask") or "0", 16)
    out = {}
    with open(os.path.join(base, "sound_calls.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids = [int(x, 16) for x in (row["samples"] or "").split()]
            prio = int(row.get("flags_0x10") or "0", 16) & 0xff
            out[int(row["call"], 16)] = [(masks.get(i, 0), prio) for i in ids]
    return out


class Task:
    """One ROM task: a timer that calls back after a number of ticks."""

    __slots__ = ("id", "handle", "ticks", "start", "data")

    def __init__(self, task_id, handle, ticks, start, data=None):
        self.id, self.handle, self.ticks, self.start, self.data = task_id, handle, ticks, start, data


class PlayerData:
    """Per-player rule state (the ROM's NVRAM arrays indexed [player-1]). Item and attribute access."""

    def __getitem__(self, name):
        return getattr(self, name)

    def __setitem__(self, name, value):
        setattr(self, name, value)

    def get(self, name, default=None):
        return getattr(self, name, default)

    def __contains__(self, name):
        return hasattr(self, name)


class TfOS(CustomCode):

    def on_load(self):
        self.trace = Trace(self.machine)
        self.tasks = {}
        self.flags = set()
        self.state = ST_ATTRACT
        self.hooks = {}             # hook name -> [functions], called in registration order
        self.pokes = {}             # ROM RAM address -> setter(value), for the scenarios' "poke"
        self.features = []
        self.players = []           # PlayerData per player
        self.pf_valid = False
        self._counting_seen = set()
        self.ball_save = None       # None, "armed" or "grace"
        self.ball_save_left = 0
        self.tilt_warnings = 0
        self._last_bob = -999.0
        self.eb_lit = []            # OS lit extra balls per player (0x3d46c)
        self.eb_collected = [0] * 4  # extra balls collected per player (0x3d470)
        self.specials_lit = [0] * 4  # 0x3d4ef
        self.specials_collected = [0] * 4  # 0x3d4f3
        self.lamps = None           # tf.lamps.Lamps: the lamp matrix (game image, flash mask, leff layers)
        self.replays_awarded = {}
        self.shoot_again = False    # game flag 9: this ball is a shoot-again ball
        self.ball_scored = False
        self.pf_mult = 1            # playfield multiplier 0x3243c (double scoring sets 2)
        self.serve_type = 0
        self._mb_pending = 0
        self._mb_save = (0, 0)
        self._mb_balls = 0          # balls requested from the running multiball task (rom_balls_in_play)
        self.rules = []
        self._refresh_pending = False
        self._score_pending = {}
        self.forced = {}             # name -> list of forced pick results (tests)
        # deff id -> function returning the values the deff's code reads from RAM each frame (timers,
        # mode values, the current stage): its display lines (tf/media_bridge.py, refreshed while shown)
        self.deff_values = {}
        self.random = random.Random()
        self._new_game = False
        self._new_game_ball = False
        self._search_handle = None
        self._search_at = 0.0
        self.ball_search_count = 0
        self.ball_held = False       # a ball sits in a device the rules hold (not in play) waiting for its kickout
        self.ball_validated = False  # the playfield was validated on this ball (the play music)
        self.device_ejecting = False    # a held ball's eject not yet confirmed by a playfield switch (no ball search)
        self.device_busy = False        # a held ball released, eject not yet confirmed by the ball device
        self.device_released_at = -999.0    # when a held ball was last kicked out
        self._mb_first_at = -999.0    # earliest launch of a new multiball request's first ball
        settings = os.path.join(self.machine.machine_path, "config", "rom", "settings.yaml")   # gen_config.py
        self.adj_table = adjustment_defaults(settings)
        from tf.settings import Adjustments, Audits   # noqa: E402
        self.adj = Adjustments(self.machine, self.adj_table)   # MPF settings, persisted (tf/settings.py)
        self.audits = Audits(self.machine)                     # ROM audit counters, persisted
        from tf.credits import Credits             # noqa: E402
        self.credit_model = Credits(self)                      # credits and pricing, persisted
        self._restart = False       # adj 36 GAME RESTART: the running game ends into a new one
        self._valid_at = None       # when the playfield was validated on this ball (play-time audits)
        self.game_seconds = 0.0     # validated play time of the running game
        self.replayed = False       # a replay was awarded in this game (DAT_0003817e)
        self._coindoor_save = False  # the running multiball save is the coin door ball saver's (adj 41)
        self.shaker_deffs = shaker_table(os.path.join(self.machine.machine_path, "..", "rom", "rom_data", "io",
                                                      "shaker.csv"))
        self.machine.tf = self

        ev = self.machine.events
        ev.add_handler("game_starting", self._game_starting, priority=1000)
        ev.add_handler("ball_starting", self._ball_starting, priority=1000)
        # the ROM starts the next ball (and deff 19) as soon as the bonus ends [0x00020658]; MPF first waits
        # for an empty playfield, so the score display comes back here (the screen was empty until then)
        ev.add_handler("ball_will_start", lambda **kwargs: self.display.refresh())
        ev.add_handler("ball_started", self._ball_started, priority=1000)
        ev.add_handler("ball_drain", self._ball_drain, priority=1000)
        ev.add_handler("ball_ending", self._ball_ending, priority=1000)
        ev.add_handler("game_ending", self._game_ending, priority=1000)
        ev.add_handler("game_ended", self._game_ended, priority=1000)
        ev.add_handler("request_to_start_game", self._request_start, priority=1000)
        ev.add_handler("player_add_request", self._player_add_request, priority=1000)
        ev.add_handler("player_added", self._player_added, priority=1000)
        ev.add_handler("mode_attract_started", self._attract_started)
        ev.add_handler("tf_hold_release", self._device_eject_confirmed, unconfirmed=True)
        ev.add_handler("balldevice_bd_shooter_lane_ejecting_ball", self._shooter_ejecting)
        sw = self.machine.switch_controller
        for slot in self.credit_model.slots():
            sw.add_switch_handler(slot, (lambda name: lambda: self.credit_model.coin(name))(slot))
        sw.add_switch_handler("s_start_button", self._start_held, ms=START_HOLD_TICKS * TICK * 1000)
        sw.add_switch_handler("s_back", self._service_back)
        sw.add_switch_handler("s_tilt_pendulum", self._plumb_bob)
        sw.add_switch_handler("s_l_flipper_button", lambda: self._flipper_launch(1))
        sw.add_switch_handler("s_r_flipper_button", lambda: self._flipper_launch(2))
        sw.add_switch_handler("s_shooter_lane", self._shooter_left, state=0)
        sw.add_switch_handler("s_coin_door_open", self._coin_door_opened)
        sw.add_switch_handler("s_coin_door_open", self._coin_door_closed, state=0)
        self._power_off_run = 0     # counts deff 4 starts, so a dim timer of an earlier start does nothing
        self._service_confirm = None    # clock handle while the end-the-game question is up
        self._service_kill = False      # the game is ending into the service menu
        sw.add_switch_handler("s_select", self._service_select)
        self.in_service = False     # the service menu (mode tf_service) is running

        self.register("rules_refresh", self.request_refresh)
        self.register_poke(0x3d46c, lambda p, v: self.eb_lit.__setitem__(p, v))
        from tf.media_bridge import MediaBridge   # noqa: E402 (import after machine setup)
        self.media = MediaBridge(self)
        from tf.display import Display, Leffs, Tubes     # noqa: E402
        self.display = Display(self)
        self.tubes = Tubes(self)
        self.leffs = Leffs(self)
        from tf.lamps import Lamps                # noqa: E402
        self.lamps = Lamps(self)
        self.lamps.leff_code(13, self._leff_save_lamp, priority=0x81)
        self.lamps.leff_code(14, self._leff_save_lamp, priority=0x80)
        from tf import switches                   # noqa: E402
        self.switches = switches.SwitchLayer(self)
        from tf.features import load_features     # noqa: E402
        self.features = load_features(self)
        if os.environ.get("TF_LIVE_SCENARIO"):
            from tf.live_scenario import LiveScenario  # noqa: E402
            self.live = LiveScenario(self, os.environ["TF_LIVE_SCENARIO"])

    # ------------------------------------------------------------------ infrastructure

    @property
    def now(self):
        return self.machine.clock.get_time()

    def task_start(self, task_id, ticks, callback=None, data=None):
        """(Re)start ROM task task_id: it runs for `ticks` ticks, then calls callback()."""
        self.task_kill(task_id)

        def fire():
            task = self.tasks.pop(task_id, None)
            if task is not None and callback:
                callback()
        handle = self.machine.clock.schedule_once(fire, ticks * TICK)
        self.tasks[task_id] = Task(task_id, handle, ticks, self.now, data)
        return self.tasks[task_id]

    def task_kill(self, task_id):
        task = self.tasks.pop(task_id, None)
        if task is not None:
            self.machine.clock.unschedule(task.handle)
            return True
        return False

    def task_running(self, task_id):
        return task_id in self.tasks

    def task_ticks_left(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return 0
        return max(0, task.ticks - round((self.now - task.start) / TICK))

    def after(self, ticks, callback):
        """Anonymous delay (not a ROM task id)."""
        return self.machine.clock.schedule_once(lambda: callback(), ticks * TICK)

    def hook(self, name, *args):
        """Call every feature function registered under ROM hook `name`; return the last result."""
        result = None
        for fn in self.hooks.get(name, ()):
            r = fn(*args)
            if r is not None:
                result = r
        return result

    def has_hook(self, name):
        return bool(self.hooks.get(name))

    def any_multiball(self):
        """A multiball runs: [0x01006704] (the decompile's any_timed_mode_running) tests the six multiball flags.
        It gates the Energon targets, the battle qualify (clu_start_allowed), the pops step and the combo window."""
        return any(f in self.flags for f in MULTIBALL_FLAGS)

    def timed_mode_running(self):
        """A timed mode runs ([0x010067bc]: the battle timer tasks 0x9c..0xaa, double scoring 0xac, fast scoring
        0xc3): the 2-bank scores 5,000 ([0x0102e994], with a multiball), ADD MORE TIME is offered. Hook "timed_mode"."""
        return bool(self.hook("timed_mode"))

    def timed_mode_paused(self):
        """Mode clocks hold while the playfield is not validated or while a show task waits or plays (Tron
        timed_mode_paused [0x0100ff64]; its game parts, such as Tron's pop bumper pause, come with the rules)."""
        return not self.pf_valid or self.show_running() or bool(self.hook("timer_pause"))

    def display_busy(self):
        """FUN_000287a4: a display effect other than the background one is running."""
        return self.display.fg is not None

    def pick(self, name, weights):
        """Weighted random pick (index into weights). A test can force the results per name through
        self.forced[name] (a list of indexes, used in order), e.g. from a ROM reference trace."""
        forced = self.forced.get(name)
        if forced:
            choice = forced.pop(0)
            if choice is not None:              # None: the reference run does not tell, pick freely
                return choice
        if max(weights) >= 1000:
            return weights.index(max(weights))
        total = sum(weights)
        if total <= 0:
            return None
        r = self.random.randrange(total)
        for i, w in enumerate(weights):
            if r < w:
                return i
            r -= w
        return None

    # ------------------------------------------------------------------ lamp rules

    def lamp_rule(self, cond, leff=None, tube=None, order=0):
        """Lamp/tube rule (leff_rule_init / FUN_00000da4): lamp-matrix effect `leff` and/or ramp tube show
        `tube` run while cond() is true. Re-evaluated by rules_refresh() in `order` (use the ROM address
        of the rule's condition function, so rules start in the ROM's order)."""
        self.rules.append([cond, leff, tube, False, order])
        self.rules.sort(key=lambda r: r[4])

    def deff_live(self, deff_ids, values):
        """values() -> {arg: value}: what deffs `deff_ids` print from RAM (not passed at deff start)."""
        for deff_id in deff_ids:
            self.deff_values[deff_id] = values

    def deff_rule(self, cond, deff_id, music=None, priority=0, on_start=None):
        """lamp_rule_init(list 2, cond, deff, music, priority): mode background deff + music (display.py)."""
        self.display.add_rule(cond, deff_id, music, priority, on_start)

    def request_refresh(self, *_):
        """rules_refresh_request: evaluate the lamp rules once the current handler has finished."""
        if not self._refresh_pending:
            self._refresh_pending = True
            self.machine.clock.schedule_once(self.rules_refresh, TICK / 2)

    def rules_refresh(self, leffs_only=False):
        """leffs_only: only start refused rule leffs whose flashers were freed (display.Leffs)."""
        if leffs_only:
            active_game = bool(self.game) and not self.state & (ST_ATTRACT | ST_END_BALL | ST_BONUS)
            for rule in self.rules:
                if rule[3] and rule[1] is not None and self.leffs.retry_due(rule[1]) and active_game and rule[0]():
                    self.leff_start(rule[1], loop=True)
            return
        self._refresh_pending = False
        if self.game and self.state & ST_TILT:
            return          # FUN_000196e4: a rule runs only when gf_state is 0 or matches its mode mask
        if self.hook("rules_hold"):
            return          # a game feature holds the rules (Tron: its arcade show task 0x97)
        active_game = bool(self.game) and not self.state & (ST_ATTRACT | ST_END_BALL | ST_BONUS)
        for rule in self.rules:
            cond, leff, tube, on = rule[:4]
            want = bool(active_game and cond())
            if want and leff is not None and (not on or self.leffs.retry_due(leff)):
                self.leff_start(leff, loop=True)     # also a refused one whose outputs are free now
            elif on and not want and leff is not None:
                self.leff_stop(leff)
            # a tube rule restarts its show whenever it is not running (refused or taken over before)
            if tube is not None:
                if want and not self.tubes.is_running(tube):
                    self.tube_start(tube)
                elif not want and self.tubes.is_running(tube):
                    self.tube_stop(tube)
            rule[3] = want
        self.display.rules_refresh()                 # list 2: background deff rules and their music
        if self.game and (self.state == 0 or self.state & 0x20):
            # list 5: the lamp rules (mode mask 0x20, FUN_000196e4) redraw the inserts from game state
            self.lamps.run_rules()
            self.shoot_again_lamp_update()
        self.machine.events.post("tf_rules_refresh")

    def lamp_update(self, fn, priority=0):
        """rule_obj_init(obj, 5, fn, 0x20, 0, priority): a lamp rule, fn() redraws its inserts from game
        state (lamps.lamp_set / lamp_flash / ...) on every rules refresh during the game. Higher priority
        runs first; equal priorities run newest first (FUN_00019578 inserts at the head)."""
        self.lamps.add_rule(fn, priority)

    def shoot_again_lamp_update(self):
        """shoot_again_lamp_update [0x0001a014]: the shoot again lamp flashes while this ball is a
        shoot-again ball (flag 9), is solid while an extra ball is pending, off otherwise. The ROM calls
        it when these change; here it also runs with the lamp rules."""
        self.eb_lamp_update()
        if self.flag(9):
            self.lamps.lamp_flash(SHOOT_AGAIN_LAMP)
        elif self.game and self.game.player and self.game.player.extra_balls:
            self.lamps.lamp_on_solid(SHOOT_AGAIN_LAMP)
        else:
            self.lamps.lamp_off(SHOOT_AGAIN_LAMP)

    def eb_lamp_update(self):
        """FUN_0001a2a4: the EXTRA BALL insert flashes while the player has an extra ball lit."""
        p = self.player_num - 1
        if p >= 0 and self.eb_lit[p]:
            self.lamps.lamp_flash(EB_LAMP)
        else:
            self.lamps.lamp_off(EB_LAMP)

    def register(self, name, fn):
        self.hooks.setdefault(name, []).append(fn)

    def register_poke(self, addr, setter, players=4, stride=1):
        """Map a per-player ROM RAM array (addr + stride*(p-1)) to a setter(player_index, value)."""
        for p in range(players):
            self.pokes[addr + stride * p] = (lambda p_: lambda v: setter(p_, v))(p)

    def poke(self, addr, value):
        if addr not in self.pokes:
            raise KeyError("no rebuild state mapped to ROM address 0x{:x}".format(addr))
        self.pokes[addr](value)

    # ------------------------------------------------------------------ outputs

    def deff_start(self, deff_id, **args):
        return self.display.start(deff_id, **args)

    def deff_media(self, deff_id, leff=None, sound=None):
        """The lamp effect and first sound that come with deff_id, unless its capture plays them already (a
        capture's media start with the deff; started twice they would show twice in a trace)."""
        info = self.display.media.get(deff_id)
        if leff is not None and not (info and leff in info.leffs):
            self.leff_start(leff)
        if sound is not None and not (info and any(c == sound and t < 0.05 for t, c in info.sounds)):
            self.sound(sound, in_deff=deff_id)

    def deff_stop(self, deff_id):
        self.display.stop(deff_id)

    def show(self, task_id, deff_id, **kwargs):
        """queue_fullscreen_deff [0x0100fbb0] run as show task task_id (0x81-0xa7)."""
        self.display.queue(task_id, deff_id, **kwargs)
        self.request_refresh()

    def show_running(self):
        return self.display.show_running()

    def base_music(self):
        """Music of the score-display deff rules (Tron [0x0100f594 / 0x0100f5c8]): the plunger music until the
        playfield is validated on this ball, then the play music; a feature may replace it (hook base_music)."""
        music = self.hook("base_music")
        if music is not None:
            return music
        return GAME["music_play"] if self.ball_validated else GAME["music_plunger"]

    def music(self, call):
        """Play a background music call and remember it (display.rules_refresh plays it again on a change)."""
        self.display.music = call
        if call is not None:
            self.sound(call)

    def sound(self, call, in_deff=0, index=None):
        """snd_play(call): returns the time the picked sample ends (for sound_chain), or None.
        index: the sample, when the caller picked it already (it needed its length)."""
        if call is None:            # a game sound call not known yet (GAME)
            return None
        self.trace.log("sound", call="0x{:03x}".format(call), in_deff=in_deff)
        self.machine.events.post("tf_sound_{:03x}".format(call))
        lengths = self.sample_lengths(call)
        if not lengths:
            self.media.sound(call)
            return None
        if index is not None and index < len(lengths):
            i = index
        else:
            i = self.pick("sample_0x{:03x}".format(call), [1] * len(lengths)) if len(lengths) > 1 else 0
        self.media.sound(call, i or 0)             # the media controller plays the same sample
        channels = self.sample_channels(call)
        if channels and (i or 0) < len(channels):
            self._playing = [p for p in getattr(self, "_playing", []) if p[0] > self.now]
            self._playing.append((self.now + lengths[i or 0],) + channels[i or 0])
        return self.now + lengths[i or 0]

    def sound_refused(self, call):
        """The sound board refuses `call` while a sample of a higher priority call plays on one of its channels
        (inferred from the Allspark's warning 0x157, [0x0100a788] event 7: refused during the jackpot speech)."""
        channels = self.sample_channels(call)
        if not channels:
            return False
        mask, prio = channels[0]
        return any(end > self.now and m & mask and p > prio for end, m, p in getattr(self, "_playing", []))

    def sample_channels(self, call):
        if not hasattr(self, "_sample_channels"):
            self._sample_channels = sample_channels(os.path.join(self.machine.machine_path, "..", "rom",
                                                                 "rom_data", "sound"))
        return self._sample_channels.get(call, [])

    def sound_stop(self, call):
        """FUN_0002ceb4(call): stop the sample a sound call plays (Tron: the arcade reel's roll)."""
        self.media.sound_stop(call)

    def sound_chain(self, call, after):
        """snd_play_chain [0x0002ca1c]: play `call` when the sample started by an earlier sound() ends."""
        if after is None or after <= self.now:
            return self.sound(call)
        self.machine.clock.schedule_once(lambda: self.sound(call), after - self.now)
        return None

    def sample_lengths(self, call):
        """Durations (s) of the samples a sound call picks from (rom/rom_data/sound: sound_calls.csv, samples.csv)."""
        if not hasattr(self, "_sample_lengths"):
            self._sample_lengths = sample_lengths(os.path.join(self.machine.machine_path, "..", "rom", "rom_data",
                                                               "sound"))
        return self._sample_lengths.get(call, [])

    def sound2(self, call, arg, index=None, in_deff=0):
        """snd_play2(call, arg) [0x0002c950]: a sound call with an argument (e.g. a spoken number). The
        ROM traces log these from inside snd_play2 (caller 0x2c97c), which trace_check leaves out.
        index: the sample of the call's list the argument picks (the SOS skipped item, a counter), which
        the media controller plays."""
        self.trace.log("sound", call="0x{:03x}".format(call), in_deff=in_deff, arg=arg, caller="0x2c97c")
        self.machine.events.post("tf_sound_{:03x}".format(call), arg=arg)
        if index is not None:
            self.media.sound(call, index)

    def leff_start(self, leff_id, loop=False, lamp=None):
        """Logged like the ROM's call; returns False when a higher-priority leff keeps the outputs.
        lamp: the lamp (number, light name or tag, or a list) a token effect draws (lamps.py)."""
        self.trace.log("leff_start", id=leff_id)
        if not self.leffs.start(leff_id, loop, lamp):
            return False
        self.machine.events.post("tf_leff_{}".format(leff_id))
        return True

    def leff_stop(self, leff_id):
        self.leffs.stop(leff_id)
        self.trace.log("leff_stop", id=leff_id)
        self.machine.events.post("tf_leff_{}_stop".format(leff_id))

    def tube_start(self, show_id):
        return self.tubes.start(show_id)

    def tube_stop(self, show_id):
        self.tubes.stop(show_id)

    def audit(self, audit_id, n=1):
        """audit_add(counter, n): the persistent audit counter (tf/settings.Audits) and the trace."""
        self.audits.add(audit_id, n)
        self.trace.log("audit", id=audit_id, n=n)

    def flag_set(self, flag):
        self.flags.add(flag)
        self.trace.log("flag_set", flag=flag)

    def flag_clear(self, flag):
        self.flags.discard(flag)
        self.trace.log("flag_clear", flag=flag)

    def flag(self, flag):
        return flag in self.flags

    # ------------------------------------------------------------------ game state

    @property
    def game(self):
        return self.machine.game

    @property
    def player_num(self):
        """Current player, 1-4 (0 when no game)."""
        game = self.machine.game
        return game.player.number if game and game.player else 0

    def current_score(self):
        """FUN_000233c8: the current player's score (gf_scores), as the deffs that print it read it."""
        game = self.machine.game
        return game.player.score if game and game.player else 0

    @property
    def pd(self):
        """Rule state of the current player."""
        return self.players[self.player_num - 1]

    @property
    def tilted(self):
        return bool(self.state & ST_TILT)

    def shaker_run(self, strength, min_setting):
        """shaker(pattern, min_level) [0x010307a0]: run the shaker motor (coil 8) when adjustment 96 is not 0 and
        at least min_level, never while tilted or in game over (gf_state & 0x310). A run already going for at
        least as long is not cut short [0x0103070c]. Returns True when it ran."""
        if not self.adj[SHAKER_ADJ] or self.adj[SHAKER_ADJ] < min_setting or self.state & 0x310 or not self.game:
            return False
        ms = SHAKER_MS.get(strength, SHAKER_MS[1])
        now = self.machine.clock.get_time()
        if now + ms / 1000.0 <= getattr(self, "_shaker_until", 0):
            return True             # a new run only replaces a shorter one [0x0103070c]
        self._shaker_until = now + ms / 1000.0
        coil = self.machine.coils.get("c_shaker_motor_optional")
        if coil is not None:
            try:
                coil.enable()
                if getattr(self, "_shaker_stop", None):
                    self.machine.clock.unschedule(self._shaker_stop)
                self._shaker_stop = self.machine.clock.schedule_once(lambda: coil.disable(), ms / 1000.0)
            except Exception:       # noqa: BLE001 (a disabled driver in a test machine)
                pass
        self.lamps.coil_log(8, ms)
        return True

    def shaker_deff(self, deff_id):
        """The display effects that call the shaker (shaker.csv, by effect number). The call is in the
        deff's own function, which runs once the deff has the display: a deff replaced in the same tick
        (e.g. by a higher priority one) does not run it."""
        if deff_id in self.shaker_deffs:
            def run():
                if self.display.running(deff_id):
                    self.shaker_run(*self.shaker_deffs[deff_id])
            self.machine.clock.schedule_once(run, 0)

    @property
    def in_play(self):
        """Normal play: a game runs and no tilt, end-of-ball or bonus is in progress."""
        return self.state == 0

    def balls_in_play(self):
        """MPF's live ball count (includes a ball a device holds for the rules)."""
        game = self.machine.game
        return game.balls_in_play if game else 0

    def rom_balls_in_play(self):
        """The ROM's balls_in_play [0x0001e4a8]: while the multiball task runs (balls still to launch, or its
        ball save / grace) it is the requested count; otherwise the balls not in a device (a ball held in
        a device is not in play). E.g. a second multiball started during the first one's save adds a ball."""
        if self.task_running(MB_TASK) or self.mb_save_running():
            return self._mb_balls
        return max(0, self.balls_in_play() - (1 if self.ball_held else 0))

    # ------------------------------------------------------------------ multiball (0x0001ed7c)

    def multiball_start(self, balls, save_ticks=0, grace_ticks=0):
        """multiball_start(balls, 0, save_ticks, grace_ticks) [0x0001ed7c]: bring the number of balls in
        play up to `balls` (counting a held ball, capped at the 4 installed), kill the single-ball save
        and (re)start the multiball task: leff 13, then the launches and the multiball save (a larger
        pending request wins). Returns False (nothing done) during tilt, end of ball or attract
        (gf_state & 0x214), else True."""
        if not self.game:
            return False
        self.trace.log("multiball_start", balls=balls, save_ticks=save_ticks, grace_ticks=grace_ticks)
        self._coindoor_save = False
        if self.state & 0x214:                       # tilt, end of ball or attract: refused (returns 0)
            return False
        self.machine.events.post("tf_multiball_start", balls=balls)
        self.kill_ball_save()
        target = min(balls, 4)
        running = self.task_running(MB_TASK) or self.mb_save_running()
        self._mb_balls = max(target, self._mb_balls) if running else target
        add = target - self.balls_in_play()
        if add > 0:
            self._mb_pending += add
            self.game.balls_in_play += add
        # the call recreates the multiball task, which starts leff 13 when it runs (one tick later)
        self.after(1, lambda: self.game and not self.state & 0x214 and self.leff_start(13))
        if not (self.task_running(MB_TASK) or self.mb_save_running()):
            self._mb_save = (save_ticks, grace_ticks)          # no multiball task: the new values
            self._mb_request()
            return True
        # a running multiball task: the larger save and grace win
        if self.task_running(MB_TASK) and not (self.task_running(0x34) or self.task_running(0x35)):
            self._mb_save = (max(self._mb_save[0], save_ticks), max(self._mb_save[1], grace_ticks))
        elif save_ticks > self.task_ticks_left(0x34):
            self.task_kill(0x35)
            self.task_start(0x34, save_ticks, lambda: self._mb_save_grace(grace_ticks))
        if not self.task_running(MB_TASK) and self._mb_pending:
            self._mb_request(start_save=False)
        return True

    def _mb_request(self, start_save=True):
        """(Re)create the multiball task for new balls: the first one waits a trough cycle."""
        self._mb_first_at = self.now + (MB_FIRST_EJECT_TICKS - 0.5) * TICK
        self._mb_task(start_save)

    def _mb_task(self, start_save=True):
        """Multiball task FUN_0001ea60: wait until no ball device is busy (a device keeps or is ejecting
        its ball), then start the save and launch the balls one per trough eject cycle, the first one
        after a trough cycle (_mb_request)."""
        device_busy_until = self.device_released_at + (DEVICE_BUSY_TICKS - 0.5) * TICK
        if self.ball_held or self.device_busy or self.now < device_busy_until:
            self.task_start(MB_TASK, 1, lambda: self._mb_task(start_save))
            return
        if start_save:
            save_ticks, grace_ticks = self._mb_save
            if save_ticks:
                self.task_kill(0x35)
                self.task_start(0x34, save_ticks, lambda: self._mb_save_grace(grace_ticks))
            else:
                self._mb_save_grace(grace_ticks)
        if self.now < self._mb_first_at:
            self.task_start(MB_TASK, 1, lambda: self._mb_task(False))
            return
        self._mb_launch()

    def _mb_launch(self):
        if self._mb_pending <= 0 or not self.game or self.state & 0x214:
            self._mb_pending = 0
            self.task_kill(MB_TASK)
            return
        self._mb_pending -= 1
        self.machine.playfield.add_ball(balls=1, player_controlled=False)
        self.task_start(MB_TASK, MB_EJECT_TICKS, self._mb_launch)

    def _mb_save_grace(self, grace_ticks):
        self.leff_stop(13)
        # the ball search waits for the end of the multiball task (save, then grace) [0x0001ea60]
        self.task_start(0x35, grace_ticks, self.ball_search_reload)

    def mb_save_running(self):
        """The multiball save, also while the multiball task still waits to start it."""
        return self.task_running(0x34) or self.task_running(0x35) or (
            self.task_running(MB_TASK) and bool(self._mb_save[0]))

    def kill_mb_save(self):
        if self.task_kill(0x34):
            self.leff_stop(13)
        self.task_kill(0x35)

    def score_add(self, points):
        """score_add [0x0002340c]: x playfield multiplier gf_pf_mult (2 during double scoring); nothing while
        tilted or out of game."""
        if not self.game or self.state & 0x210 or not self.game.player:
            return 0
        self.trace.log("score_add", points=points, multiplier=self.pf_mult, player=self.player_num)
        points = self.score_event(points * self.pf_mult)
        self.ball_search_reload()
        self._add_score(points)
        if not self.ball_scored:
            self.ball_scored = True
            if self.shoot_again:
                self.shoot_again = False
                self.flag_clear(9)
        return points

    def score_event(self, points):
        """Score event 0x4c: its hooks may change the points (TRON double scoring x2)."""
        for fn in self.hooks.get("score_event", ()):
            points = fn(points)
        return points

    def _add_score(self, points):
        """The score display reports the sum of all score_adds of one task run as one "score" event."""
        player = self.game.player
        player.score += points
        if not self._score_pending:
            self.machine.clock.schedule_once(self._score_flush, 0)
        self._score_pending[self.player_num] = self._score_pending.get(self.player_num, 0) + points
        self.replay_check(self.player_num, player.score)

    # ------------------------------------------------------------------ replay (game_flow.md 5.5)

    def replay_level(self, n):
        """FUN_00022998(n): replay level n (1-4) by adj 11 REPLAY TYPE (0 none, 1 fixed adj 17-20, 2 dynamic:
        level 1 only, the machine's dynamic level that starts at adj 16, 3 auto n x adj 15). With adj 21
        REPLAY BOOST the fixed and auto levels are multiplied by (boost count + 1) (NVRAM 0x0211097c, 0 on a
        fresh machine; see _replay_statistics)."""
        if n > self.adj_value(14):
            return 0
        kind = self.adj_value(11)
        boost = self.audits.extra.get("replay_boost", 0) + 1 if self.adj_value(21) == 1 else 1
        if kind == 1:
            return int(boost * self.adj_value(16 + n))
        if kind == 2:
            return int(self.audits.extra.get("dynamic_replay", self.adj_value(16))) if n == 1 else 0
        if kind == 3:
            return int(n * boost * self.adj_value(15))
        return 0

    def replay_check(self, player, score):
        """replay_check [0x00022f18], on every score change: each level reached and not yet awarded."""
        awarded = self.replays_awarded.setdefault(player, set())
        for n in range(1, 5):
            level = self.replay_level(n)
            if level and score >= level and n not in awarded:
                awarded.add(n)
                self.replay_award(n)

    def replay_award(self, n):
        """replay_award [0x00022d2c]: award per adj 13 (0 = credit + knocker 0x019), audit 9 + n, then task
        0x33 (an end-of-ball wait task) shows deff 28 REPLAY with leff 17 once no show runs (traces/
        portal_multiball.jsonl: replay 16.53 s, deff 28 at 25.09 s when show deff 140 ends), until it ends."""
        award = self.adj_value(13)                   # 0 credit, 1 ticket, 2 token, 3 extra ball
        if award == 0:
            if self.award_credit():                  # FUN_00004cf0: the knocker only when a credit was added
                self.after(1, self.knock)            # knocker, fired by the OS knocker queue
        elif award == 3:
            self.collect_extra_ball()                # eb_award(0) [0x0001a168]
        else:
            self.machine.events.post("tf_award_ticket" if award == 1 else "tf_award_token")
        self.replayed = True
        if self.adj_value(11) == 2:                  # dynamic replay: the level rises by adj 16 per replay
            self.audits.extra["dynamic_replay"] = self.replay_level(1) + self.adj_value(16)
        self.audits.add_extra("boost_replays", 1)    # DAT_0211097e
        self.audit(9 + n)

        def show():
            if self.display.show_running() or (self.display.fg is not None and self.display.fg_prio > 0x9f):
                # FUN_000287a4: wait while a show runs, or a mode's award deff (traces/wizard_multiball.jsonl:
                # the replay as the last wizard hit deff 88 ends)
                self.task_start(0x33, 1, show)
                return
            if self.deff_start(28):
                self.leff_start(17)
                self.task_start(0x33, round(self.display.media[28].seconds / TICK) if 28 in self.display.media
                                else 160)
        self.task_start(0x33, 1, show)

    def award_credit(self, n=1):
        """A free game: credits.award (adj 33, adj 25); event tf_award_credit per credit added."""
        added = self.credit_model.award(n)
        for _ in range(added):
            self.machine.events.post("tf_award_credit")
        return added

    def knock(self, forced=False):
        """Knocker queue [0x0001b370 / 0x0001b418]: sound 0x019 unless adj 35 KNOCKER VOLUME is OFF (a forced
        knock still sounds); with adj 44 Q24 OPTION = KNOCKER the Q24 output (coil 24) fires too."""
        if self.adj_value(44) == 2:
            self.machine.coils["c_optional_coil"].pulse()
        if self.adj_value(35) or forced:
            self.sound(0x019)

    def _score_flush(self):
        pending, self._score_pending = self._score_pending, {}
        for num, delta in pending.items():
            total = self.game.player_list[num - 1].score if self.game else 0
            self.trace.log("score", player=num, delta=delta, total=total)
        self.media.score_changed()

    def base_score(self, points):
        """FUN_0102a188: base switch score, nothing while tilted."""
        if not self.tilted:
            self.score_add(points)

    def adj_value(self, num):
        return self.adj[num]

    # ------------------------------------------------------------------ valid playfield (4.3)

    def playfield_switch(self, num):
        """Called by switch handlers: force switches validate at once, 3 distinct counting ones do."""
        self.device_ejecting = False                 # a playfield switch confirms a held ball's eject
        if not self.task_running(0x2b):
            self.ball_search_count = 0               # ball_search_reset [0x00019d58]: the ball was seen
        self.ball_search_reload()
        if num in COUNTING_SWITCHES:
            self.hook("counting_switch", num)        # event 0x6b
        elif num in FORCE_SWITCHES:
            self.hook("instant_switch", num)         # event 0x6c
        if self.pf_valid:
            return
        if num in FORCE_SWITCHES:
            self._validate()
        elif num in COUNTING_SWITCHES:
            self._counting_seen.add(num)
            if len(self._counting_seen) >= 3:
                self._validate()

    def _validate(self):
        self.pf_valid = True
        if self._valid_at is None:
            self._valid_at = self.now                # validated play time (game-time / ball-time audits)
        self.flag_set(0x1c)                          # event 0x6a handler [0x0100f25c]
        self.request_refresh()                       # ... which also requests a rules refresh
        self.hook("playfield_valid")
        self.ball_validated = True
        # the base music rule switches to the play music one tick later
        self.after(1, lambda: self.in_play and self.display.rules_refresh())

    # ------------------------------------------------------------------ coins and start

    def _request_start(self, **kwargs):
        """start_button_handler [0x00020d14] in attract: a game needs a credit or free play; otherwise event
        0x2d and deff 15 (credit text, PRESS START / INSERT COINS) unless it already runs."""
        if self.credit_model.can_start():
            return True
        self.machine.events.post("tf_start_refused")    # event 0x2d
        if not self.display.running(15):
            self.deff_start(15, credits=self.credit_model.text())
        return False

    def _player_add_request(self, **kwargs):
        """START on ball 1 adds a player when a credit (or free play) allows it [0x00020d14]."""
        game = self.machine.game
        return not (game and game.player_list) or self.credit_model.can_start()   # player 1 paid at game start

    def _player_added(self, num=1, **kwargs):
        if num > 1:
            self.credit_model.take(1)
            self.audit(0x11)
            self.sound(GAME["add_player_sound"])     # observed: traces/game_flow.jsonl 5.88 s (player 2)

    def _start_held(self):
        """adj 36 GAME RESTART [0x00020d14]: START held 62 ticks (timer 4) on ball 2 or later restarts the game,
        with the same credit check as a game start. The running game ends without its game-over (no
        high-score entry, match or game audits) and a new game starts."""
        game = self.game
        if (not game or game.ending or not game.player or game.player.ball < 2 or self.adj_value(36) != 1
                or self.state & 0x40 or not self.credit_model.can_start()):
            return
        self._restart = True
        game.end_game()

    def start_button_lamp(self):
        """FUN_00020448 (game_flow.md 8): with credit, the START BUTTON blinks in attract (task 0x2d,
        FUN_0002032c: 8 ticks on, 8 off) and is solid otherwise (a credit won at the match lights it at
        once); without credit it is off."""
        if self.state & ST_ATTRACT and not self.state & 0x08:      # attract proper, not the game's end
            if self.has_credit() and not self.task_running(0x2d):
                self._start_blink(True)
            return
        self.task_kill(0x2d)
        self.lamps.lamp_set(START_LAMP, 1 if self.has_credit() else 0)

    def has_credit(self):
        """A credit is left (the start button lamp's only question): credits or free play."""
        return self.credits > 0 or self.free_play

    # the credit state as the score display reads it (media_bridge.credits_text)
    @property
    def credits(self):
        return self.credit_model.credits

    @property
    def credit_fraction(self):
        return self.credit_model.fraction()

    @property
    def free_play(self):
        return self.credit_model.free_play()

    def _start_blink(self, on):
        (self.lamps.lamp_on if on else self.lamps.lamp_off)(START_LAMP)
        self.task_start(0x2d, 8, lambda: self._start_blink(not on))

    def _device_eject_confirmed(self, unconfirmed=False, **kwargs):
        """The holding device's task runs from the release until MPF confirms the eject (a playfield switch or
        the eject timeout); the multiball task waits for it."""
        self.device_busy = unconfirmed

    def _shooter_left(self):
        """The ball leaves the shooter lane, plunged or auto-launched: the launch sound (GAME, observed;
        FUN_01032dfc plays it, from which switch is not traced)."""
        if self.game and not self.tilted and GAME["launch_sound"] is not None:
            self.after(GAME["launch_sound_ticks"], lambda: self.game and self.sound(GAME["launch_sound"]))

    def _shooter_ejecting(self, mechanical_eject=False, **kwargs):
        """Auto-launch (coil 2): the OS runs task 0x3c from the launch, so the shooter lane does not raise
        the orbit post and the launched ball's orbit pass is ignored (sw23; portal_multiball_shots.jsonl
        24.07 launch, 0x3c at the launch, left orbit 1.8 s later scores no shot). Length not traced."""
        if not mechanical_eject:
            self.task_start(0x3c, AUTO_LAUNCH_TICKS)

    def _attract_started(self, **kwargs):
        self.state = ST_ATTRACT
        self.start_button_lamp()

    # ------------------------------------------------------------------ game start (4.1)

    def _game_starting(self, queue=None, **kwargs):
        self.state = 0
        self.players = [PlayerData() for _ in range(4)]
        self.eb_lit = [0] * 4
        self.eb_collected = [0] * 4
        self.specials_lit = [0] * 4
        self.specials_collected = [0] * 4
        self.lamps.clear()                           # FUN_00007eb8: lamp images cleared for the new game
        self.leffs.kill_all()                        # the attract leff tasks die with the other tasks
        self.replays_awarded = {}                    # player -> replay levels awarded (0x2110993)
        self.replayed = False
        self.game_seconds = 0.0
        self._valid_at = None
        self.shoot_again = False
        self.flags.clear()
        self.tasks_kill_all()
        self.credit_model.take(1)                         # FUN_00004e9c: the game's credit
        self.credit_model.free_games = 0
        self.audit(0x11)
        hs = self.features_by_name.get("high_scores")
        if hs:
            hs.game_started()                        # FUN_0001a4f0: adj 61 HSTD RESET COUNT
        self.display.clear()
        self._new_game = True
        self._new_game_ball = True
        self.hook("game_start")                      # event 0x2e

    def tasks_kill_all(self):
        for task_id in list(self.tasks):
            self.task_kill(task_id)

    # ------------------------------------------------------------------ ball start (4.2)

    def _ball_starting(self, queue=None, **kwargs):
        player = self.game.player
        first_ball = player.ball == 1 and not self.shoot_again
        self.state = 0
        self.pf_valid = False
        self._counting_seen = set()
        self.ball_scored = False
        self.tilt_warnings = 0
        self.pf_mult = 1                             # gf_pf_mult 0x3243c: 1 at ball start (game_flow.md 4.2)
        if first_ball:
            self.hook("player_first_ball")           # event 0x26
        self.hook("ball_start")                      # event 0x11
        if self.shoot_again:
            self.deff_start(26, player=self.player_num)   # its speech comes with the deff
            self.leff_start(16)
        self.deff_start(19)
        self.ball_validated = False
        self.music(self.base_music())
        self.hook("ball_start_media")                # leffs/tube shows the features start with the ball
        self.deff_stop(27)                           # instant info off
        if self._new_game:
            self._new_game = False
            self.sound(GAME["game_start_sound"])
        self.ball_search_count = 0
        self.ball_search_reload()
        later_ball = not self._new_game_ball
        self._new_game_ball = False
        self.serve(3)
        # The trough eject task kicks the ball about 32 ticks after the serve (traces/game_flow.jsonl
        # ball start 1.90 s, trough eject 2.42 s); MPF ejects when the ball_starting queue clears.
        if queue:
            queue.wait()
            # (all reference traces: 0.545 s for the game's first ball, 0.645 s for every later one)
            self.after(SERVE_EJECT_TICKS + (LATER_SERVE_EXTRA_TICKS if later_ball else 0), queue.clear)

    def _ball_started(self, **kwargs):
        pass

    def serve(self, serve_type):
        """serve(type) [0x0001f258]: 3 = new ball (arms ball save), 1/2 = ball-save replacement."""
        self.serve_type = serve_type
        self.pf_valid = False                        # gf_pf_valid 0 at every serve
        self._counting_seen = set()
        self.hook("ball_served", serve_type)         # event 0x0f
        if serve_type == 3:
            self._arm_ball_save()
        if self.adj_value(39):                       # FUN_0001e614: timed plunger task 0x17
            self.task_start(0x17, self.adj_value(39) * SECOND, self._timed_plunger)

    # ------------------------------------------------------------------ ball save (5.1)

    def _arm_ball_save(self):
        ticks = self.adj_value(38) * SECOND
        self.task_kill(0x31)
        self.task_kill(0x32)
        if ticks <= 0:
            self.ball_save = None
            return
        self.ball_save = "armed"
        self.ball_save_left = ticks
        self.after(1, lambda: self.ball_save == "armed" and self.leff_start(14))   # from task 0x31
        self.task_start(0x31, 6, self._ball_save_poll)

    def _ball_save_poll(self):
        if self.pf_valid and self.ball_save_left > 6:
            self.ball_save_left -= 6
        if self.ball_save_left > 6:
            self.task_start(0x31, 6, self._ball_save_poll)
            return
        self.leff_stop(14)
        self.ball_save = "grace"
        self.task_start(0x32, BALL_SAVE_GRACE, self._ball_save_end)

    def _leff_save_lamp(self, task):
        """leff_013 [0x0002fd60] / leff_014 [0x0002fe1c]: the multiball / ball save blinks SHOOT AGAIN on
        its own layer, every (save ticks left / 31) ticks (2-10). Leff 14 first waits for the valid
        playfield and ends with the ball save task 0x31; leff 13 runs until it is stopped."""
        if task.leff_id == 14:
            if not self.pf_valid and not self.ball_scored:     # FUN_00023638 (a switch scored) or valid
                task.sleep(2, self._leff_save_lamp)
                return
            if not self.task_running(0x31):
                task.end()
                return
            left = self.ball_save_left
        else:
            left = self.task_ticks_left(0x34)
        task.toggle(SHOOT_AGAIN_LAMP)
        task.sleep(max(2, left // 31) if left < 0x138 else 10, self._leff_save_lamp)

    def _ball_save_end(self):
        self.ball_save = None

    def kill_ball_save(self):
        """Multiball start kills the single-ball save (0x00019bdc)."""
        if self.ball_save == "armed":
            self.leff_stop(14)
        self.task_kill(0x31)
        self.task_kill(0x32)
        self.ball_save = None

    def _ball_drain(self, balls=0, **kwargs):
        """ball_drain relay: ball save and re-serve before the playfield is valid [0x0001dd90]."""
        if not balls or not self.game:
            return {"balls": balls}
        self.device_ejecting = False
        if self._coindoor_save and self.mb_save_running() and not self.tilted:
            # the coin door ball saver's save (adj 41) re-serves even the last ball [0x0001ff74]
            self._mb_pending += balls
            if not self.task_running(MB_TASK):
                self._mb_request(start_save=False)
            return {"balls": 0}
        if self.balls_in_play() - balls > 0:
            if self.mb_save_running() and not self.tilted:
                # multiball save: the multiball task launches a replacement. Unlike the single-ball save
                # (ball_save_try 0x00019b34) it shows nothing and audits nothing.
                self._mb_pending += balls
                if not self.task_running(MB_TASK):
                    self._mb_request(start_save=False)
                return {"balls": 0}
            self.hook("ball_drained", balls)
            # trough entry (0x0101bbc0 case 0xe): installed - balls in devices (a held ball counts) < 2
            if self.balls_in_play() - balls - (1 if self.ball_held else 0) < 2:
                self.kill_mb_save()
                self.hook("multiball_end")           # 0x0101bcec: fewer than 2 balls in play
            return {"balls": balls}
        if self.tilted:
            return {"balls": balls}
        if not self.pf_valid:
            # not a lost ball: re-serve the same ball (type 7), no bonus
            self.serve_type = 7
            self.machine.playfield.add_ball(player_controlled=True)
            return {"balls": 0}
        if self.ball_save:
            self.kill_ball_save()
            self.deff_start(20)
            self.leff_start(15)
            self.audit(0x2b)
            self.ball_scored = False                 # traces/game_flow_tilt: ball_scored 0 at BALL SAVED
            self.request_refresh()                   # the save re-runs the lamp rules (game_flow.jsonl 7.96)
            self.hook("ball_saved")
            self.serve(1)
            # trough eject task, then the auto-launch (traces/game_flow.jsonl: save 7.96 s, eject 8.60 s)
            self.after(SAVE_SERVE_TICKS, lambda: self.machine.playfield.add_ball(player_controlled=False))
            return {"balls": 0}
        return {"balls": balls}

    # ------------------------------------------------------------------ ball search (5.2)

    def ball_search_reload(self, seconds=10):
        """ball_search_reset [0x00019d58] / FUN_00019c1c: reload the ball-search countdown (every playfield
        switch, every score, a show deff). It only ever grows (the larger of what is left and `seconds`),
        and it does not count down while a search runs (ball_search_tick [0x00019c58])."""
        fire = self.now + (seconds * SECOND + self.task_ticks_left("search_run")) * TICK
        if self._search_handle:
            if self._search_at >= fire:
                return
            self.machine.clock.unschedule(self._search_handle)
        self._search_at = fire
        self._search_handle = self.machine.clock.schedule_once(self._ball_search, fire - self.now)

    def _ball_search(self):
        self._search_handle = None
        if not self.game:
            return
        # no search while the multiball task (save and grace, FUN_0001ea60) runs: it reloads at its end
        if (self.pf_valid and not self.state & (ST_END_BALL | ST_BONUS | 0x18) and not self.ball_held
                and not self.device_ejecting and not self.mb_save_running()):
            self.ball_search_count += 1
            if self.ball_search_count == LOST_BALL_SEARCH and self.adj_value(63) == 1:
                self._lost_ball_feed()
                self.ball_search_reload(15 if self.tilted else 10)
                return
            self.task_start(0x2b, BALL_SEARCH_TICKS)
            self.task_start("search_run", BALL_SEARCH_RUN_TICKS)
            # 36 ticks in, the search posts its events and the lamp rules run (game_flow 88.70 -> 89.29,
            # bonus_skip 15.35 -> 15.93)
            self.after(BALL_SEARCH_EVENT_TICKS, lambda: self.task_running(0x2b) and self.request_refresh())
            self.audit(0x25)
            self._search_sweep()
            self.hook("ball_search")
            self.machine.events.post("tf_ball_search", count=self.ball_search_count)
        self.ball_search_reload(15 if self.tilted else 10)

    def _search_sweep(self):
        """The coils a search fires, in the ROM's order and timing (BALL_SEARCH_SWEEP); none once the search has
        ended (a switch found the ball)."""
        def fire(names):
            if self.task_running(0x2b):
                for name in names:
                    self.lamps.flasher(name, 64)
        for ticks, names in BALL_SEARCH_SWEEP:
            self.after(ticks, lambda names=names: fire(names))
        self.after(BALL_SEARCH_MOTOR_TICKS, lambda: self.task_running(0x2b) and self.hook("ball_search_motor"))
        gate_at, gate_ticks = BALL_SEARCH_GATE
        self.after(gate_at, lambda: self.task_running("search_run") and self.hold_coil("c_orbit_control_gate", 5,
                                                                                       gate_ticks))

    def hold_coil(self, name, num, ticks):
        """Hold a driver on for `ticks` (the orbit gate), logged like the traces; a hold while held extends it."""
        coil = self.machine.coils.get(name) if hasattr(self.machine, "coils") else None
        if coil is None:
            return
        held = getattr(self, "_held", None)
        if held is None:
            held = self._held = {}
        until = self.now + ticks * TICK
        if name in held:
            held[name] = max(held[name], until)
            return
        coil.enable()
        self.trace.log("coil", coil=num, on=1)
        held[name] = until

        def off():
            left = held.get(name, 0) - self.now
            if left > 0.001:
                self.machine.clock.schedule_once(off, left)
                return
            held.pop(name, None)
            coil.disable()
            self.trace.log("coil", coil=num, on=0)
        self.machine.clock.schedule_once(off, ticks * TICK)

    def _lost_ball_feed(self):
        """ball_search_start(5) with adj 63 LOST BALL RECOVERY [0x0001f79c]: the balls missing from the
        playfield count are declared lost: deff 13 "PINBALL MISSING", a new ball is served (type 2, auto-
        launched) and the LOST BALL FEEDS record (counter 0x26) counts it (written directly, no audit_add)."""
        missing = max(1, self.rom_balls_in_play())
        self.deff_start(13)
        self.serve(2)
        for _ in range(missing):
            self.machine.playfield.add_ball(player_controlled=False)
        self.audits.add(0x26, missing)
        self.machine.events.post("tf_lost_ball_feed", balls=missing)

    # ------------------------------------------------------------------ coin door, flipper launch, plunger

    def coin_door_open(self):
        return bool(self.machine.switch_controller.is_active(self.machine.switches["s_coin_door_open"]))

    def _service_back(self):
        """Coin-door BACK outside the service menu [0x0000fc20]: with the "50V / 20V DISABLED" warning up it
        takes the warning away (deff_stop(4), sound 0x009); otherwise a service credit."""
        if self.in_service:
            return
        if self._service_confirm:
            self._service_confirm_close()          # BACK answers no
            return
        if self.display.running(POWER_OFF_DEFF):
            self.deff_stop(POWER_OFF_DEFF)
            self.sound(POWER_OFF_CANCEL_SOUND)
            return
        self.credit_model.service_credit()

    def _service_select(self):
        """Coin-door SELECT: the service menu (tf/service.py). In attract mode it opens at once. In a game the
        ROM suspends the game and resumes it after the menu (FUN_0000f9b0 / FUN_0000fa34); here the first
        SELECT asks "END GAME?" and a second one within SERVICE_CONFIRM_SECONDS ends the game, without its
        game over (no high scores, match or game audits, as a GAME RESTART), and opens the menu
        (docs/rom_differences.md). BACK or the timeout leaves the game running."""
        if self.in_service or self._service_kill:
            return
        if not self.game:
            if "tf_service" in self.machine.modes:
                self.machine.modes["tf_service"].start()
            return
        if self.game.ending:
            return
        if self._service_confirm:
            self._service_confirm_close()
            self._service_kill = True
            self.trace.log("service_end_game")
            self.game.end_game()
            return
        from tf import rom_draw as rd
        self.media.confirm_show([rd.fit("END GAME?", 64, 11, (15, 12, 8, 2)),
                                 rd.fit("PRESS 'SELECT' FOR SERVICE MENU", 64, 22, (2, 0)),
                                 rd.fit("PRESS 'BACK' TO CANCEL", 64, 30, (2, 0))])
        self._service_confirm = self.machine.clock.schedule_once(
            lambda: self._service_confirm_close(), SERVICE_CONFIRM_SECONDS)

    def _service_confirm_close(self):
        if self._service_confirm:
            self.machine.clock.unschedule(self._service_confirm)
            self._service_confirm = None
            self.media.confirm_hide()

    def _coin_door_opened(self):
        """Coin door opened: the door interlock cuts the 50 V and 20 V, so the IO board's power status (RAM
        0x3727c & 3) is no longer 3 and the power handler FUN_00007bc4 (table 0x040d748c, from FUN_00007c24)
        runs: event 0x3d, then the "50V / 20V DISABLED" warning, deff 4.
        Event 0x3d [0x0001ffac]: with adj 41 COINDOOR BALL SAVER, in play, every ball in play is saved:
        multiball_start(balls in play, 0, 312, 187) [0x0001ff74 / 0x0001ea28]."""
        if self.adj_value(41) == 1 and self.game and not self.state & 0x214:
            self.multiball_start(max(1, self.rom_balls_in_play()), COINDOOR_SAVE_TICKS, COINDOOR_GRACE_TICKS)
            self._coindoor_save = True
        self._power_off_warning()

    def _coin_door_closed(self):
        """Coin door closed, power back (FUN_00007c08): event 0x3d, and the warning goes if it is still the
        running deff."""
        self._power_off_run += 1
        if self.display.fg == POWER_OFF_DEFF:
            self.deff_stop(POWER_OFF_DEFF)

    def _power_off_warning(self):
        """FUN_00007bc4: deff 4 at priority 247, unless a higher one has the display (the volume display 248;
        the service menu, deff 3 at 253, which is why nothing shows when the door opens inside the menu).
        Deff 4 [0x01036f1c] never ends by itself: "50V / 20V DISABLED" blinks five times with sound 0x010,
        stays lit for 1875 ticks, then the whole screen dims to palette level 6 until the door is closed or
        BACK is pressed. Its captured frames hold the first part; the dimmed screen is drawn as the ROM draws it."""
        if self.in_service:
            return
        self._power_off_run += 1
        run = self._power_off_run
        if self.display.start(POWER_OFF_DEFF, hold=True, media=True):
            self.after(POWER_OFF_DIM_TICKS, lambda: self._power_off_dim(run))

    def _power_off_dim(self, run):
        if run != self._power_off_run or self.display.fg != POWER_OFF_DEFF:
            return
        from tf import rom_draw as rd
        level = POWER_OFF_DIM_LEVEL
        draw = [rd.text("50V / 20V DISABLED", 8, 64, 9, level=level)]
        draw += [rd.text(t, 2, 64, y, level=level) for t, y in (("CLOSE COIN DOOR", 16),
                                                               ("OR PULL INTERLOCK SWITCH", 22),
                                                               ("TO RESTORE POWER", 28))]
        self.media.deff_draw(POWER_OFF_DEFF, self.display.prio.get(POWER_OFF_DEFF, 0), draw)

    def _flipper_launch(self, side):
        """Flipper button with a ball waiting in the shooter lane [0x0002dcc0]: adj 40 FLIPPER BALL LAUNCH
        (1 left, 2 right, 3 either, 4 both: this button with the other one held) launches it."""
        mode = self.adj_value(40)
        if not mode or not self.game or self.state & 0x214:
            return
        other = "s_r_flipper_button" if side == 1 else "s_l_flipper_button"
        if (mode == side or mode == 3
                or (mode == 4 and self.machine.switch_controller.is_active(self.machine.switches[other]))):
            self._launch_shooter_lane()

    def _launch_shooter_lane(self):
        """FUN_0001fa5c(1): fire the auto-launch for a ball sitting in the shooter lane."""
        if self.machine.ball_devices["bd_shooter_lane"].balls:
            self.machine.coils["c_auto_launch"].pulse()
            self.task_start(0x3c, AUTO_LAUNCH_TICKS)     # as for every auto-launch (_shooter_ejecting)
            return True
        return False

    def _timed_plunger(self):
        """task_17 [0x0001e58c]: adj 39 TIMED PLUNGER seconds after a serve, a ball still waiting in the
        shooter lane is launched."""
        if self.game and not self.state & 0x214:
            self._launch_shooter_lane()

    # ------------------------------------------------------------------ tilt (5.3)

    def _plumb_bob(self):
        if not self.game or self.tilted or self.state & ST_END_BALL:
            return
        if self.now - self._last_bob < SECOND * TICK:
            return
        self._last_bob = self.now
        if self.adj_value(64) and self.coin_door_open():
            return                                   # FUN_00024344: adj 64 ignores the tilt with the door open
        if self.tilt_warnings < self.adj_value(32):
            self.tilt_warnings += 1
            self.deff_start(23)
            self.leff_start(11)
            self.sound(0x016)
            self.after(31, lambda: self.sound(GAME["tilt_warning_speech"]))
            return
        self.hook("tilt_start")                      # event 0x66, posted before the tilt state is set
        self.state |= ST_TILT
        self.ball_search_reload(15)
        self.audit(0x2a)
        self.kill_ball_save()
        self.machine.events.post("tf_tilt")
        self.hook("tilt")                            # event 0x65
        self.deff_start(21)
        self.leff_start(9)
        self.sound(0x017)
        self.after(GAME["tilt_speech_ticks"], lambda: self.sound(GAME["tilt_speech"]))
        for flipper in self.machine.flippers.values():
            flipper.disable()

    # ------------------------------------------------------------------ extra ball (5.4)

    def light_extra_ball(self):
        """OS part of 0x01012190: lit count +1 for the current player."""
        self.eb_lit[self.player_num - 1] += 1
        self.eb_lamp_update()

    def collect_extra_ball(self):
        """0x01012228 OS part: returns True when an extra ball was awarded, False when it paid points
        (eb_paid: the points scored, which deff 133 prints)."""
        p = self.player_num - 1
        self.eb_lit[p] = max(0, self.eb_lit[p] - 1)
        self.eb_lamp_update()
        if self.eb_collected[p] < self.adj_value(26):
            self.eb_collected[p] += 1
            self.game.player.extra_balls += 1
            self.audit(9)
            self.shoot_again_lamp_update()
            return True
        self.eb_paid = self.score_add(3000000)
        return False

    def light_special(self):
        """special_light(0) [0x00024014]: special lit for the current player, lamp update; deff 81
        "SPECIAL IS LIT" (the caller's display)."""
        self.specials_lit[self.player_num - 1] += 1
        self.special_lamp_update()
        self.deff_start(81)

    def special_lamp_update(self):
        """FUN_00024298: the special insert (SPECIAL_LAMP) is on while the player has a special lit, off
        otherwise. self.lamps holds the inserts the rules read back (lamp_test), not the lamp matrix."""
        if self.specials_lit[self.player_num - 1]:
            self.lamps.add(SPECIAL_LAMP)
        else:
            self.lamps.discard(SPECIAL_LAMP)

    def special_collect(self):
        """special_collect [0x00024218] + special_award [0x000240ac]: use one lit special and award it per
        adj 23 (0 credit, 3 points, 4 extra ball), or the over-limit points past the adj 22 limit. Returns
        True when a special was lit. The outlane shows deff 82 and scores 100,000 itself."""
        p = self.player_num - 1
        if not self.specials_lit[p]:
            return False
        self.specials_lit[p] -= 1
        if self.specials_collected[p] >= self.adj_value(22):
            self.score_add(SPECIAL_OVER_LIMIT_SCORE)
        else:
            award = self.adj_value(23)
            if award == 0:
                self.award_credit()
                self.knock()                         # FUN_0001b370(1, 1)
            elif award == 3:
                self.score_add(SPECIAL_OVER_LIMIT_SCORE)
            elif award == 4:
                self.collect_extra_ball()
            self.specials_collected[p] += 1
            self.audit(0x0e)
        self.special_lamp_update()
        return True

    # ------------------------------------------------------------------ outlane ball save

    def ball_save_try(self, side):
        """ball_save_try [0x00019b34] from the outlanes (side 1 left, 2 right): (re)start the drain-side
        task 0x37/0x38 for 625 ticks (read at end of ball for the LEFT/RIGHT DRAINS audits). While the
        ball save runs, the replacement ball is served at once (FUN_0001f368: serve type 2,
        auto-launched) and the save ends: deff 20 (leff 15 when it shows), audit 0x2b. Returns True then."""
        self.task_kill(0x37)
        self.task_kill(0x38)
        self.task_start(0x36 + side, OUTLANE_TASK_TICKS)
        if not self.ball_save or self.tilted:
            return False
        self.serve(2)
        self.game.balls_in_play += 1                 # the outlane ball still drains later
        self.after(SAVE_EJECT_TICKS, lambda: self.machine.playfield.add_ball(player_controlled=False))
        self.kill_ball_save()
        if self.deff_start(20):
            self.leff_start(15)
        self.audit(0x2b)
        self.hook("ball_saved")
        return True

    # ------------------------------------------------------------------ end of ball (6.1)

    def _ball_ending(self, queue=None, **kwargs):
        if self._service_kill:                       # ended for the service menu: no totals, no bonus
            self.kill_ball_save()
            self.kill_mb_save()
            self.display.clear()
            self.hook("ball_end")
            for flipper in self.machine.flippers.values():
                flipper.disable()
            return
        queue.wait()
        if self.task_running(0x2b):
            self.after(self.task_ticks_left(0x2b), lambda: self._ball_ending_go(queue))
            return
        self._ball_ending_go(queue)

    def _ball_ending_go(self, queue):
        self.state |= ST_END_BALL
        self.task_kill("search_run")                 # the search found the drained ball
        self.kill_ball_save()
        self.kill_mb_save()
        self._mb_pending = 0
        self.task_kill(MB_TASK)
        self.display.clear()
        self.hook("ball_end")                        # event 0x1d: every mode stops
        for flipper in self.machine.flippers.values():
            flipper.disable()
        self.audit(8)
        if self._valid_at is not None:               # play time of this ball (AVERAGE BALL / GAME TIME)
            played = self.now - self._valid_at
            self._valid_at = None
            self.game_seconds += played
            self.audits.add_extra("ball_seconds", played)
        if self.task_running(0x37):                  # end_of_ball [0x00020764]: last outlane drain side
            self.audit(0x28)
        if self.task_running(0x38):
            self.audit(0x29)
        wait_ticks = self.hook("ball_end_wait") or 0  # mode TOTAL displays (flag-0x2000 tasks)
        self.after(wait_ticks, lambda: self._ball_ending_bonus(queue))

    def _ball_ending_bonus(self, queue):
        if self.tilted:
            self._ball_ending_done(queue)
            return
        self.state |= ST_BONUS
        self.pf_mult = 1                             # end_of_ball: gf_pf_mult = 1 before the bonus (never doubled)
        bonus = self.features_by_name.get("bonus")
        if bonus:
            bonus.run(lambda total: self._bonus_done(queue, total))
        else:
            self._bonus_done(queue, 0)

    def _bonus_done(self, queue, total):
        if total:
            # event 0x16, multiplier 1, not a score_add
            self._add_score(self.score_event(total))
            self.hook("score_changed")
        self.state &= ~ST_BONUS
        self._wait_award_tasks(queue)

    def _wait_award_tasks(self, queue):
        """End of ball step 7: wait for the replay / award tasks 0x33-0x34."""
        if self.task_running(0x33) or self.task_running(0x34):
            self.after(1, lambda: self._wait_award_tasks(queue))
            return
        self._ball_ending_done(queue)

    def _ball_ending_done(self, queue):
        self.state &= ~(ST_TILT | ST_END_BALL)
        for flipper in self.machine.flippers.values():
            flipper.enable()
        if self.game.player.extra_balls:
            self.shoot_again = True
            self.flag_set(9)
        queue.clear()

    def shot_mult(self, shot):
        """[0x01023538]: shot `shot`'s multiplier (1X / 2X, 3X under the roving 3X: tf/features/combos.py)."""
        combos = self.features_by_name.get("combos")
        if combos:
            return combos.shot_mult(shot)
        mult = self.pd.get("shot_mult") if self.game else None
        return mult[shot] if mult and shot < len(mult) else 1

    @property
    def features_by_name(self):
        return {f.name: f for f in self.features}

    # ------------------------------------------------------------------ game over (6.2)

    def _game_ending(self, queue=None, **kwargs):
        self.state |= 0x18
        if self._restart or self._service_kill:      # adj 36 / the service menu: no game over
            return
        # game-time audit (audits 59-71, by the game's validated play time) and the score-range audits
        # (audits 30-46, one per player) [0x00023774]
        players = self.game.player_list if self.game else []
        self.audit(self.audits.game_time_counter(self.game_seconds))
        for player in players:
            self.audit(self.audits.score_range_counter(player.score))
        self.audits.add_extra("game_seconds", self.game_seconds)
        self.audits.add_extra("score_total", sum(p.score for p in players))
        self._replay_statistics(len(players))
        self.hook("game_over")
        queue.wait()
        match = self.features_by_name.get("match")
        hs = self.features_by_name.get("high_scores")

        def to_match():
            if match:
                match.run(queue.clear)
            else:
                queue.clear()
        if hs and not self.hook("slammed"):
            hs.run(to_match)                         # high_score_entry [0x0001ad4c], then match
        else:
            to_match()

    def _replay_statistics(self, players):
        """Game-over replay bookkeeping [0x000231a4]. Dynamic replay (adj 11 = 2): the level drops by
        adj 12 % x players (less the one that replayed) x adj 16 each game, never below 5,000,000 (a replay
        raised it by adj 16). Replay boost: a game with a replay boosts the levels once more; the boost ends
        when the games played since reach the replays won."""
        extra = self.audits.extra
        if self.adj_value(11) == 2:
            level = extra.get("dynamic_replay", self.adj_value(16))
            dec = (self.adj_value(12) * (players - (1 if self.replayed else 0)) * self.adj_value(16)) // 1000 * 10
            level = max(DYNAMIC_REPLAY_MIN, level - dec) if dec <= level else DYNAMIC_REPLAY_MIN
            extra["dynamic_replay"] = level
        if extra.get("replay_boost"):
            extra["boost_games"] = extra.get("boost_games", 0) + players
        if self.replayed:
            extra["replay_boost"] = extra.get("replay_boost", 0) + 1
        elif extra.get("boost_replays", 0) <= extra.get("boost_games", 0):
            for key in ("replay_boost", "boost_replays", "boost_games"):
                extra.pop(key, None)
        self.audits.save()

    def _game_ended(self, **kwargs):
        self.state = ST_ATTRACT
        self.tasks_kill_all()
        if self._search_handle:
            self.machine.clock.unschedule(self._search_handle)
            self._search_handle = None
        if self._restart:                            # adj 36: the new game starts at once
            self._restart = False
            self.after(1, lambda: self.machine.events.post("game_start"))
        if self._service_kill:                       # SELECT twice in the game: the menu opens
            self._service_kill = False
            self.after(1, lambda: self.in_service or "tf_service" not in self.machine.modes
                       or self.machine.modes["tf_service"].start())
