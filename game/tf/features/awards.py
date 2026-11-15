"""Extra ball and special: lit by the rules, collected at the right orbit (code [0x01007b40] [0x01007b74]
[0x01008528] [0x01008684], called from the right orbit's handler [0x01033488]; not traced).

- Extra ball lit [0x01007b40] (the Allspark award EXTRA BALL LIT, the wizard requirements of adj 83): the OS count
  of lit extra balls + 1 [0x000180c8], show task 0x5f with deff 53 "EXTRA BALL IS LIT", the EXTRA BALL insert (55).
- Special lit [0x01008528] (the Allspark award LIGHT SPECIAL): the SPECIAL insert (53) on in the player's lamps
  (one special, however often it is lit), show task 0x61 with deff 55 "SPECIAL IS LIT".
- The right orbit, after the shot multiplier and the wizard modes' hits and before the multiball and battle
  rules: a lit special is collected [0x01008684]: insert off, the OS award of adj 23 SPECIAL AWARD within the
  limit of adj 22 [0x0001d7a0], show task 0x62 with deff 56; then a lit extra ball [0x01007b74]: the OS award
  [0x00018204] (an extra ball within adj 26 EXTRA BALL LIMIT, else its points) and deff 54.
"""
from tf.features import Feature

ORDER = 36
EB_LIT_TASK, EB_LIT_DEFF, EB_DEFF = 0x5f, 53, 54
SPECIAL_LIT_TASK, SPECIAL_LIT_DEFF, SPECIAL_TASK, SPECIAL_DEFF = 0x61, 55, 0x62, 56


class Awards(Feature):
    name = "awards"
    HOOKS = ("eb_light", "special_light", "orbit_awards")

    def eb_light(self):
        """[0x01007b40]."""
        os_ = self.os
        os_.light_extra_ball()
        os_.show(EB_LIT_TASK, EB_LIT_DEFF)
        os_.request_refresh()

    def special_light(self):
        """[0x01008528]: the insert is the state, so a second award lights nothing more."""
        os_ = self.os
        os_.specials_lit[os_.player_num - 1] = 1
        os_.special_lamp_update()
        os_.show(SPECIAL_LIT_TASK, SPECIAL_LIT_DEFF)
        os_.request_refresh()

    def orbit_awards(self):
        """The right orbit's collects [0x01033488]: the special, then the extra ball."""
        os_ = self.os
        if not os_.game or os_.tilted:
            return
        p = os_.player_num - 1
        if os_.specials_lit[p]:
            os_.special_collect()
            os_.show(SPECIAL_TASK, SPECIAL_DEFF)
            os_.request_refresh()
        if os_.eb_lit[p]:
            os_.collect_extra_ball()
            os_.deff_start(EB_DEFF)
            os_.request_refresh()


def feature(os_):
    return Awards(os_)
