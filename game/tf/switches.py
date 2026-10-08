"""Switch handlers of Transformers Pro 1.80: one per playfield switch, in the ROM's switch table order.

The ROM's switch table (rom/rom_data/io/switches.csv: handler, handler_arg, flags) gives every playfield switch
a handler in the game code. Each handler here applies the OS part every handler shares (the switch confirms the
ball is on the playfield, validates it, reloads the ball search), then calls the feature hooks registered under
"sw_<number>" and "switch" in registration order (os.hook), then adds the switch's base score.

What the game handlers do (their hooks, the order, the base scores) comes from the ROM extraction's rules specs,
which are not delivered yet: until then no handler scores (BASE_SCORE is empty) and the only game behaviour is the
outlanes' ball save, which every SAM game's outlane handler starts (ball_save_try, OS code; Tron's outlane handlers
call it first, inferred to be the same here).
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
# the outlane handlers' media (observed, traces/sounds.jsonl): saved -> sound 0x169 + leff 97 (FUN_0102db28),
# lost -> sound 0x16d + leff 100 (FUN_0102e208)
OUTLANE_SAVED, OUTLANE_LOST = (0x169, 97), (0x16d, 100)
BASE_SCORE = {}                 # switch -> base points (from the rules specs, not delivered yet)


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
            sound, leff = OUTLANE_SAVED if os_.ball_save_try(OUTLANES[num]) else OUTLANE_LOST
            os_.sound(sound)
            os_.leff_start(leff)
        os_.hook("sw_{}".format(num))
        os_.hook("switch", num)
        if BASE_SCORE.get(num):
            os_.base_score(BASE_SCORE[num])
