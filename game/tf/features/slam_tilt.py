"""Slam tilt (game_flow.md 5.3, slam_tilt [0x0001d534], slam_reset_task [0x0001d50c]).

The slam switch, in a game or not (no game test in [0x0001d534]; only state & 0x100, the service menu, and a running
task 0x39 stop it; QA F14): flippers and coils off, the tasks of flag 0x1000 killed (task_kill(0, 0x1000), modelled
by the modes' tilt hooks), event 0x54, deff 24 "SLAM TILT", leff 12, sound 0x018; task 0x39 then resets the
machine after 218 + 93 ticks. The reset is modelled as the end of the game without the game-over sequence (no
bonus, no match), back to attract; in attract it changes nothing else.
"""
from tf.features import Feature
from tf.os_layer import ST_TILT

ORDER = 7
SLAM_RESET_TICKS = 0xda + 0x5d


class SlamTilt(Feature):
    name = "slam_tilt"
    HOOKS = ("slammed",)

    def __init__(self, os_):
        super().__init__(os_)
        self.slam = False
        if "s_slam_tilt" in self.machine.switches:
            self.machine.switch_controller.add_switch_handler("s_slam_tilt", self.slam_tilt, state=1)
        self.machine.events.add_handler("game_starting", self._reset_flag)

    def _reset_flag(self, **kwargs):
        self.slam = False

    def slammed(self):
        return self.slam

    def slam_tilt(self):
        os_ = self.os
        if os_.in_service or os_.state & 0x100 or os_.task_running(0x39):
            return
        if os_.game:
            self.slam = True
            os_.state |= ST_TILT                     # no scores, no rules, no bonus
            os_.kill_ball_save()
            os_.hook("tilt")                         # task_kill(0, 0x1000): the modes' tasks stop
        for flipper in self.machine.flippers.values():
            flipper.disable()
        os_.task_start(0x39, SLAM_RESET_TICKS, self.reset)
        os_.deff_start(24)
        os_.leff_start(12)
        os_.sound(0x018)
        os_.ball_search_reload(15)

    def reset(self):
        """thunk_FUN_000100d0(0): the machine resets; the game in progress is gone."""
        if self.machine.game:
            self.machine.game.end_game()


feature = SlamTilt
