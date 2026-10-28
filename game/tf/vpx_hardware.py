"""Visual Pinball X only (hw_vpx.yaml overlay): make MPF's virtual_pinball platform answer like VPinMAME.

The Transformers Pro table was written for PinMAME. Its script (and VPinMAME's core.vbs / sam.vbs, which it loads)
reads the controller the way VPinMAME answers, so the TransformersMPF.Controller COM bridge (scripts/vpx_bridge.py)
forwards each call to MPF's virtual_pinball platform over BCP ("vpcom_bridge" commands, port 5051), and this module
fixes the answers where MPF 0.80's platform differs from VPinMAME:

- Switches MPF does not know (the upper flipper buttons sam.vbs may send, anything the table adds) are ignored
  instead of raising: an error in a Controller.Switch call stops the table's script.
- Solenoids are reported as VPinMAME does: number and 0 or 255 (the table sets UseVPMModSol = 2, core.vbs scales
  by 1/255). A pulse is reported even when it ends between two polls (the table polls once a frame or more).
- The hardware rules drive their coils like the SAM CPU does: a flipper coil follows its button while MPF has the
  rule on, an autofire coil (slings, pops) pulses when its switch closes. Solenoid 33 is on while any flipper rule
  is on: that is the input of the table's fast flips (sam.vbs cvpmFFlipsSAM: SolCallback(33) switches the flippers
  from ROM to button control), so the flippers react without a round trip to MPF, and stop when MPF disables
  them (tilt, ball end, game over).
- Coin door open (End key, switch -4): every solenoid but the optional coil 24 reads 0 and solenoid 33 is off
  until the door closes, as with the door interlock cutting the 50 V / 20 V (inferred for tf_180 from the same
  SAM OS: Tron 1.74 masks its outputs that way, IO interrupt 0x12070; coil 24's descriptor flag 0x2 "power exempt"
  is in rom/rom_data/io/coils.csv).
- Lamps 1-80 are reported 0-255 (MPF's brightness; core.vbs with UseVPMModSol = 2 expects that and scales by
  1/255). scripts/vpx_bridge.py turns them into 0/1 for a table without physical outputs (SolMask(2) < 2).
- GI: MPF does not switch the GI (the ROM extraction found no GI output), so GI string 0 reads 255 from the start:
  the table's GiCallBack2 (GI_PWM) turns its GI on, as PinMAME does when the machine powers up.
- Stop: the table closed; MPF quits too when the bridge started it.

MPF's platform classes have __slots__, so the methods are replaced on the classes; they fall back to MPF's own
code for any platform this module did not attach to.

Another SAM game: change the constants below (flipper coils, the solenoid range, the coils powered with the door
open, the GI strings) and the overlay's numbers; the rest is the same for every SAM table that loads sam.vbs.
"""
import logging

from mpf.core.custom_code import CustomCode
from mpf.platforms.virtual_pinball import virtual_pinball as vp

FLIPPER_COILS = ("15", "16")           # c_left_flipper, c_right_flipper (sam.vbs InitVpmFFlipsSAM: 15 and 16)
FLIPPERS_ON_SOLENOID = 33              # sam.vbs: SolCallback(33) = "vpmFFlipsSAM.RomControl = not"
MAX_SOLENOID = 32
POWERED_WITH_DOOR_OPEN = (24,)         # coil descriptor flag 0x2 (rom/rom_data/io/coils.csv): OPTIONAL COIL
GI_STRINGS = {0: 255}                  # the table's GI_PWM ignores the string number: one string, on

_ADAPTERS = {}          # id(platform) -> VpxAdapter
_ORIGINAL = {}


def _number(value):
    """VBScript passes switch numbers as ints (or strings); the platform keys them by str."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _flag(value):
    """VBScript's True is -1; anything non-zero is closed."""
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false")
    return bool(value)


class VpxAdapter:

    """VPinMAME-style answers for one virtual_pinball platform."""

    def __init__(self, machine, platform):
        self.machine = machine
        self.platform = platform
        self.log = logging.getLogger("VPX bridge")
        self.unknown = set()
        self.pulsed = set()             # drivers pulsed since the last ChangedSolenoids, by number
        self.last_sol = {}
        self.last_lamp = {}
        self.last_gi = {}

    # ------------------------------------------------------------------ switches
    def switch_known(self, number):
        if number in self.platform._switches:
            return True
        if number not in self.unknown:
            self.unknown.add(number)
            self.log.info("table switch %s is not an MPF switch, ignored", number)
        return False

    def set_switch(self, number, value):
        number, value = _number(number), _flag(value)
        if not self.switch_known(number):
            return True
        switch = self.platform._switches[number]
        switch.state = value
        self.machine.switch_controller.process_switch_by_num(state=1 if value else 0, num=number,
                                                             platform=self.platform)
        self.apply_rules(switch, value)
        return True

    def get_switch(self, number):
        number = _number(number)
        if not self.switch_known(number):
            return False
        switch = self.platform._switches[number]
        return bool(switch.state) != bool(switch.config.invert)

    def pulse_switch(self, number):
        self.set_switch(number, True)
        self.set_switch(number, False)
        return True

    def apply_rules(self, hw_switch, active):
        """What the SAM CPU does with a rule's switch: a flipper coil fires and holds while the button is down,
        an autofire coil (sling, pop) pulses."""
        for (rule_switch, driver), hold in list(self.platform.rules.items()):
            if rule_switch is not hw_switch:
                continue
            if active:
                if hold:
                    driver._state = True
                else:
                    pulse_ms = driver.config.default_pulse_ms or 10
                    driver._state = self.machine.clock.get_time() + pulse_ms / 1000.0
                    self.pulsed.add(driver.number)
            elif hold:
                driver._state = False

    # ------------------------------------------------------------------ outputs
    def door_open(self):
        door = self.machine.switches.get("s_coin_door_open")
        return bool(door) and self.machine.switch_controller.is_active(door)

    def flippers_on(self):
        return any(driver.number in FLIPPER_COILS for (_, driver) in self.platform.rules)

    def changed_solenoids(self):
        states = {}
        for number, driver in self.platform._drivers.items():
            if not number.isdigit() or not 1 <= int(number) <= MAX_SOLENOID:
                continue        # the ticket outputs (aux1-3) are not PinMAME solenoids
            states[int(number)] = driver.state or number in self.pulsed
        self.pulsed.clear()
        states[FLIPPERS_ON_SOLENOID] = self.flippers_on()
        if self.door_open():
            states = {n: v and n in POWERED_WITH_DOOR_OPEN for n, v in states.items()}
        changed = []
        for number in sorted(states):
            value = 255 if states[number] else 0
            if self.last_sol.get(number, 0) != value:
                self.last_sol[number] = value
                changed.append([number, value])
        return changed

    def lamp_levels(self):
        levels = {}
        for light in self.platform._lights.values():
            if light.subtype != "matrix" or not light.hw_number.isdigit():
                continue
            levels[int(light.hw_number)] = max(0, min(255, int(round(light.current_brightness * 255))))
        return levels

    def changed_lamps(self):
        changed = []
        for number, value in sorted(self.lamp_levels().items()):
            if self.last_lamp.get(number, 0) != value:
                self.last_lamp[number] = value
                changed.append([number, value])
        return changed

    def changed_gi_strings(self):
        changed = []
        for number, value in sorted(GI_STRINGS.items()):
            if self.last_gi.get(number) != value:
                self.last_gi[number] = value
                changed.append([number, value])
        return changed

    def stop(self, quit_game):
        """The table closed. When the bridge started the game for it, the game quits too (run.py then stops Godot)."""
        self.log.info("the table closed%s", ", quitting" if quit_game else "")
        if quit_game:
            self.machine.stop("VPX table closed")
        return True

    def pulse_driver(self, driver):
        self.pulsed.add(driver.number)


def _adapter(platform):
    return _ADAPTERS.get(id(platform))


def _wrap(name, method):
    original = _ORIGINAL.setdefault(name, getattr(vp.VirtualPinballPlatform, name, None))

    def patched(self, *args, **kwargs):
        adapter = _adapter(self)
        if adapter is None:
            if original is None:
                raise AttributeError(name)
            return original(self, *args, **kwargs)
        return method(adapter, *args, **kwargs)
    patched.__name__ = name
    setattr(vp.VirtualPinballPlatform, name, patched)


def _install_class_patches():
    if _ORIGINAL:
        return
    _wrap("vpx_set_switch", lambda a, number, value: a.set_switch(number, value))
    _wrap("vpx_get_switch", lambda a, number: a.get_switch(number))
    _wrap("vpx_switch", lambda a, number: a.get_switch(number))
    _wrap("vpx_pulsesw", lambda a, number: a.pulse_switch(number))
    _wrap("vpx_changed_solenoids", lambda a: a.changed_solenoids())
    _wrap("vpx_changed_lamps", lambda a: a.changed_lamps())
    _wrap("vpx_changed_gi_strings", lambda a: a.changed_gi_strings())
    _wrap("vpx_get_mech", lambda a, number: 0)
    _wrap("vpx_mech", lambda a, number: 0)
    _wrap("vpx_stop", lambda a, quit=False: a.stop(quit))

    driver_pulse = vp.VirtualPinballDriver.pulse

    def pulse(self, pulse_settings):
        driver_pulse(self, pulse_settings)
        for adapter in _ADAPTERS.values():
            if adapter.platform._drivers.get(self.number) is self:
                adapter.pulse_driver(self)
    vp.VirtualPinballDriver.pulse = pulse


class VpxHardware(CustomCode):

    def on_load(self):
        platform = self.machine.hardware_platforms.get("virtual_pinball")
        if platform is None:
            self.warning_log("hw_vpx: the virtual_pinball platform is not loaded, nothing to adapt")
            return
        _install_class_patches()
        _ADAPTERS[id(platform)] = VpxAdapter(self.machine, platform)
        self.machine.events.add_handler("shutdown", self._detach, platform=platform)

    @staticmethod
    def _detach(platform, **kwargs):
        del kwargs
        _ADAPTERS.pop(id(platform), None)
