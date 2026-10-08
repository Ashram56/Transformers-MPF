"""Run a tron_ref reference scenario (assets/rules/traces/<name>.txt) against the MPF rebuild.

The scenario language is documented in assets/rules/tools/trace/README.md. The ball simulation is
MPF's smart_virtual platform: coil pulses move balls between devices, and this runner plays the
part of the player (plunge, drain, hits).

Usage: .venv/bin/python -m tests.scenario <name> [out.jsonl]
"""
import os
import shlex
import sys
import unittest

from tests.tf_test import ROOT, TfTestCase

TRACES = os.path.join(ROOT, "rom", "rules", "traces")
OUT = os.path.join(ROOT, "captures", "traces")

SCRIPT_START_TIME = 2.745 - 1.896   # 'start' runs this long after the Start press (reference traces)
# the reference traces credit a coin 0.528 s after the script starts; the coin task waits adj 62 COIN INPUT
# DELAY (30 ticks at factory settings) first, so the coin switch closes that much earlier, and START comes
# 0.144 s after the credit
COIN_DELAY = 30 * 0.01626
COIN_FIRST, COIN_GAP, START_AFTER_COIN = 0.528 - COIN_DELAY, 0.612, 0.144 + COIN_DELAY
# every hit is followed by 100 ms settle; with STEP_OVERSHOOT on both phases a hit lasts ~173 ms past
# its ms (reference traces: hit + wait 1 = 1.17-1.18 s)
SETTLE = 0.1
COINS_PER_PLAYER = 4                # tf_ref "start N": 4 coins per player, then Start N times
TROUGH_SWITCHES = (18, 19, 20, 21)  # tron_ref's 4-ball trough
# tron_ref's step_to() runs the emulator in 5 ms slices and stops at the first slice past the target, so
# each switch phase of a hit lasts about 6.5 ms longer (fit over the reference traces; plain waits do not
# drift: clu_hurryup's 51 waits stay on time).
STEP_OVERSHOOT = 0.00655
BUTTONS = {"left": "s_l_flipper_button", "right": "s_r_flipper_button", "tilt": "s_tilt_pendulum",
           "start": "s_start_button", "tournament": "s_tournament_start",
           # the coin door (states_ref's `button` names; coindoor -1 opens the door, 0 closes it)
           "back": "s_back", "minus": "s_minus", "plus": "s_plus",
           "select": "s_select", "slam": "s_slam_tilt", "coindoor": "s_coin_door_open", "coin": "s_right_coin_slot"}


def switch_name(num):
    from tf.switches import SW, HOLES
    return SW.get(int(num)) or HOLES[int(num)]


def forced_picks(name):
    """Random choices the ROM made in the reference run, so the rebuild makes the same ones."""
    import json
    forced = {}
    path = os.path.join(TRACES, name + ".jsonl")
    if not os.path.exists(path):
        return forced
    evs = [json.loads(line) for line in open(path, encoding="utf-8")]
    for i, e in enumerate(evs):
        if e.get("ev") == "deff_start" and e.get("id") == 38:
            hits = [n for n in evs[i + 1:] if n.get("ev") == "audit" and n.get("id") == 0x0f
                    and n["t"] - e["t"] < 7.5]
            forced.setdefault("match", []).append(len(hits))
    for deff_id, (stop_ev, stop_id) in CLIP_DEFFS.items():
        forced["deff_{}_seconds".format(deff_id)] = clip_lengths(evs, deff_id, stop_ev, stop_id)
    forced.update(forced_samples(evs))
    return forced


def forced_samples(evs):
    """Sample picks of sound calls that a chained sound (snd_play_chain, caller 0x2ccb8) waited for: the
    gap from the call to the chained sound tells which sample the ROM played."""
    from tf.os_layer import sample_lengths
    lengths = sample_lengths(os.path.join(ROOT, "rom", "rom_data", "sound"))
    sounds = [e for e in evs if e.get("ev") == "sound" and not e.get("in_deff")]
    picks, index = {}, {}
    for e in sounds:
        call = int(e["call"], 16)
        if e.get("caller") == "0x2ccb8":
            continue
        if len(lengths.get(call, [])) > 1:
            index[id(e)] = (call, len(picks.setdefault(call, [])))
            picks[call].append(None)
    for i, e in enumerate(sounds):
        if e.get("caller") != "0x2ccb8":
            continue
        for prev in reversed(sounds[:i]):
            if id(prev) not in index:
                continue
            call, n = index[id(prev)]
            gap = e["t"] - prev["t"]
            best = min(range(len(lengths[call])), key=lambda k: abs(lengths[call][k] - gap))
            if abs(lengths[call][best] - gap) < 0.05:
                picks[call][n] = best
                break
    return {"sample_0x{:03x}".format(c): p for c, p in picks.items() if any(x is not None for x in p)}


# Deffs that play a random film clip first, so their length varies: the ROM's length is read from the
# stop of the effect the deff runs (its exit handler stops it). A deff replaced by a new start of the
# same deff keeps the recorded length (None).
CLIP_DEFFS = {}     # deffs of random length, read from what stopped them in the trace (none known yet)


def clip_lengths(evs, deff_id, stop_ev, stop_id):
    out = []
    for i, e in enumerate(evs):
        if e.get("ev") != "deff_start" or e["id"] != deff_id:
            continue
        length = None
        for n in evs[i + 1:]:
            if n["t"] < e["t"] + 0.005:
                continue                    # the previous run's effect stops as this one starts
            if n.get("ev") == "deff_start" and n["id"] == deff_id:
                break                       # replaced by its next start
            if n.get("ev") == stop_ev and n.get("id") == stop_id:
                length = n["t"] - e["t"]
                break
        out.append(length)
    return out


class ScenarioRun(TfTestCase):
    """One scenario per test instance; the scenario name comes from the environment."""

    scenario = None
    out_path = None
    FREE_PLAY = False                 # factory settings: the script's coins pay for the game

    def runTest(self):
        self.run_scenario(self.scenario, self.out_path)

    # ------------------------------------------------------------------ helpers

    def wait(self, seconds):
        self.advance_time_and_run(seconds)

    def sw(self, name, state):
        self.machine.switch_controller.process_switch(name, state, True)

    def log(self, ev, **kw):
        self.tf.trace.log(ev, **kw)

    def _on_shooter(self, **kwargs):
        if self.autoplunge > 0:
            self.machine.clock.schedule_once(self._auto_plunge, self.autoplunge)

    def _auto_plunge(self):
        if self.machine.switches["s_shooter_lane"].state:
            self.log("sim", what="plunged")
            self.sw("s_shooter_lane", 0)

    # ------------------------------------------------------------------ commands

    def run_scenario(self, name, out_path=None):
        os.makedirs(OUT, exist_ok=True)
        out_path = out_path or os.path.join(OUT, name + ".jsonl")
        trace = self.tf.trace
        trace.path = out_path
        trace._file = open(out_path, "w", encoding="utf-8")
        self.autoplunge = 1.0
        self.machine.switch_controller.add_switch_handler("s_shooter_lane", self._on_shooter, state=1)
        self.tf.forced = forced_picks(name)
        self.fill_trough()
        self.wait(6)                                  # the ROM boots 8 s before line 1
        self.log("ready")
        with open(os.path.join(TRACES, name + ".txt"), encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line.startswith("mark "):
                    self.command(["mark", line[5:].strip()])     # free text (may hold quotes)
                elif line:
                    self.command(shlex.split(line))
        self.log("end")
        trace.close()
        return out_path

    def command(self, args):
        cmd, rest = args[0], args[1:]
        getattr(self, "cmd_" + cmd)(*rest)

    def cmd_start(self, n="1"):
        n = int(n)
        self.log("script", what="start", players=n)
        self.wait(COIN_FIRST)
        for i in range(COINS_PER_PLAYER * n):
            if i:
                self.wait(COIN_GAP)
            self.sw("s_right_coin_slot", 1)
            self.wait(0.01)
            self.sw("s_right_coin_slot", 0)
        self.wait(START_AFTER_COIN - 0.01)
        for _ in range(n):
            self.sw("s_start_button", 1)
            self.wait(0.01)
            self.sw("s_start_button", 0)
            self.wait(0.09)
        self.wait(SCRIPT_START_TIME - 0.1 * n)

    def step(self, seconds):
        """One tron_ref step_to(): the requested time plus the average overshoot."""
        self.wait(seconds + STEP_OVERSHOOT)

    def cmd_wait(self, s):
        self.wait(float(s))                            # plain waits do not drift (see STEP_OVERSHOOT)

    def cmd_hit(self, sw, ms="60"):
        from tf.switches import HOLES
        name = switch_name(sw)
        self.log("switch", sw=int(sw))
        self.sw(name, 1)
        if int(sw) in HOLES:                          # the ball stays in the hole until its coil ejects it
            self.wait(SETTLE + STEP_OVERSHOOT)
            return
        self.wait(float(ms) / 1000 + STEP_OVERSHOOT)
        self.sw(name, 0)
        self.wait(SETTLE + STEP_OVERSHOOT)

    def cmd_hold(self, sw):
        self.log("switch_hold", sw=int(sw))
        if int(sw) in TROUGH_SWITCHES:              # a ball arriving in the trough is a drain
            self.cmd_drain()
            return
        self.sw(switch_name(sw), 1)

    def cmd_release(self, sw):
        self.log("switch_release", sw=int(sw))
        if int(sw) in TROUGH_SWITCHES:              # MPF's trough device owns its ball switches
            return
        self.sw(switch_name(sw), 0)

    def cmd_plunge(self):
        self._auto_plunge()

    def cmd_autoplunge(self, s="1"):
        self.autoplunge = float(s)

    def cmd_drain(self, side=None):
        if side:
            name = "s_left_outlane" if side == "left" else "s_right_outlane"
            self.log("switch", sw=24 if side == "left" else 29)
            self.sw(name, 1)
            self.step(0.06)                           # tron_ref pulses the outlane, then drains at once
            self.sw(name, 0)
        self.log("sim", what="drain")
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.step(0.1)

    def cmd_adj(self, num, value):
        self.tf.adj[int(num)] = int(value)

    def cmd_poke(self, addr, value, size="1"):
        self.tf.poke(int(addr, 16), int(value))

    def cmd_button(self, button, ms="100"):
        name = BUTTONS[button]
        ms = int(ms)
        self.log("button", button=button, ms=ms)
        if ms == 0:
            self.sw(name, 0)
        elif ms < 0:
            self.sw(name, 1)
        else:
            self.sw(name, 1)
            self.step(ms / 1000)
            self.sw(name, 0)
            self.step(0.05)                           # tron_ref: 50 ms settle after a button pulse

    def cmd_mark(self, *text):
        self.log("mark", text=" ".join(text))


def run(name, out_path=None):
    test = ScenarioRun()
    test.scenario, test.out_path = name, out_path
    result = unittest.TextTestRunner(verbosity=0).run(test)
    return result.wasSuccessful()


if __name__ == "__main__":
    ok = run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    sys.exit(0 if ok else 1)
