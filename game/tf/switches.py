"""Switch handlers of Transformers Pro 1.80: one per playfield switch, in the ROM's switch table order.

The ROM's switch table (rom/rom_data/io/switches.csv: handler, handler_arg, flags) gives every playfield switch
a handler in the game code. Each handler here applies the OS part every handler shares (the switch confirms the
ball is on the playfield, validates it, reloads the ball search), then calls the feature hooks registered under
"sw_<number>" and "switch" in registration order (os.hook), then adds the switch's base score.

The scores, sounds, display and lamp effects are the ROM extraction's per-switch trace (rom/rules/
switches_and_shots.md, switch_handlers.csv; observed from a fresh ball):
- BASE_SCORE: the points the switch's own handler adds after the rules (column "handler");
- slingshots: 440 (0x1033104 / 0x10331a4) and sound 0x15a;
- pop bumpers: 170 from the handler (0x1032f8c) and audit 73; the pop award is tf/features/pops.py.
Every handler adds 1 to the bonus count (0x1032d2c -> 0x1000dfc, hook bonus_add). The features behind the
switches register "sw_<number>" hooks (pops, lanes, spinner, Bumblebee, 2-bank, combos, skill shots; specs in
rom/rules/modes/).
"""

SW = {  # SAM switch number -> MPF switch name (rom/mpf_package/config/switches.yaml), playfield switches only
    1: "s_bumblebee_target", 2: "s_energon_left", 4: "s_l_ramp_entrance", 5: "s_left_orbit_bottom",
    6: "s_left_orbit_top", 7: "s_right_top_lane", 8: "s_left_top_lane", 10: "s_l_ramp_exit",
    11: "s_center_lane", 12: "s_right_orbit", 13: "s_megatron_back_door", 14: "s_r_ramp_exit",
    24: "s_left_outlane", 25: "s_left_return_lane", 26: "s_left_slingshot", 27: "s_right_slingshot",
    28: "s_right_return_lane", 29: "s_right_outlane", 30: "s_top_bumper", 31: "s_right_bumper",
    32: "s_bottom_bumper", 34: "s_right_orbit_spinner", 35: "s_r_ramp_entrance", 37: "s_r_2_bank_target_bot",
    45: "s_captive_ball", 46: "s_energon_right", 49: "s_energon_center", 50: "s_r_2_bank_target_top",
    51: "s_optimus_prime",
}
# ball device switches: a ball hitting one stays there until the device's coil ejects it (hardware.yaml)
HOLES = {3: "s_left_eject", 38: "s_megatron_lock_4", 39: "s_megatron_lock_3", 40: "s_megatron_lock_2",
         41: "s_m_tron_lock_1_back"}
NUM = {name: num for num, name in SW.items()}
OUTLANES = {24: 1, 29: 2}       # switch -> drain side (ball_save_try: 1 left, 2 right)
BASE_SCORE = {1: 30, 2: 1110, 4: 560, 5: 1220, 7: 2560, 8: 2560, 10: 1170, 11: 30, 12: 1220, 13: 30, 14: 1170,
              24: 100000, 25: 1090, 28: 1090, 29: 100000, 34: 90, 35: 560, 37: 30, 45: 30, 46: 1110, 49: 1110,
              50: 30, 51: 30}
SLINGS = {26: 440, 27: 440}
SLING_SOUND = 0x15a
POPS = (30, 31, 32)
POP_EXTRA = 170
# audit counters the handlers themselves add, first thing (switch_handlers.csv audit_counters, observed callers
# 0x1033aec, 0x1033c1c / 0x1033c5c, 0x1033b24, 0x1033050); the shot audits 65-68 are the mode-progress
# function's (0x1020074, with the modes)
SW_AUDIT = {1: 71, 30: 73, 31: 73, 32: 73, 37: 70, 45: 72, 50: 70}
EXTRA_BASE = {45: 30}           # the captive ball handler adds its 30 twice (observed 60)


class SwitchLayer:

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        sc = self.machine.switch_controller
        for num, name in SW.items():
            if name in self.machine.switches:
                sc.add_switch_handler(name, self._dispatch(num))

    def _dispatch(self, num):
        """The ROM runs a playfield handler as a task about one tick after the switch closes. A handler does
        not refresh the lamp rules by itself: the hooks that change rule state call rules_refresh_request
        (os.request_refresh) as the ROM does."""
        def on_close():
            if not self.os.game or not self.os.in_play:
                return
            self.os.after(1, lambda: self.handle(num))
        return on_close

    def handle(self, num):
        os_ = self.os
        if not os_.game or not os_.in_play:
            return
        os_.playfield_switch(num)
        if num in OUTLANES:
            os_.ball_save_try(OUTLANES[num])
        if num in SW_AUDIT and not os_.tilted:
            os_.audit(SW_AUDIT[num])
        os_.hook("bonus_add")
        os_.hook("sw_{}".format(num))
        os_.hook("switch", num)
        if os_.tilted:
            return
        if num in SLINGS:
            os_.score_add(SLINGS[num])
            os_.sound(SLING_SOUND)
        if num in POPS:
            os_.hook("pop", num)
            os_.score_add(POP_EXTRA)
        if BASE_SCORE.get(num):
            os_.base_score(BASE_SCORE[num])
        if EXTRA_BASE.get(num):
            os_.base_score(EXTRA_BASE[num])
