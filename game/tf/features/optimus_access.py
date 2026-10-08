"""Center lane: "N MORE TO ACCESS OPTIMUS" (rom/rules/switches_and_shots.md, sw 11; code [0x01025de4],
observed in every trace with a center lane hit: battle_*, combos, switches).

Each center lane shot (sw 11, after the battles' hit, before the combo): 2,500, game flag 0x48, deff 141
"%u MORE / TO ACCESS / OPTIMUS", leff 170, sound 0x2a3 (0x2a4 from the deff). The Optimus target (sw 51) does
not do it (traces/switches.jsonl, coils.jsonl). N is 4 minus the player's center lane count (the deff's
starter: 4 - a per-player counter at 0x2111f7b); what happens at 0 belongs to the Optimus spec (not delivered
yet): here N stops at 0 and the award goes on (no trace has more than two center shots in a game).
"""
from tf.features import Feature

ORDER = 41
POINTS, FLAG, DEFF, LEFF, SOUND = 2500, 0x48, 141, 170, 0x2a3
NEEDED = 4


class OptimusAccess(Feature):
    name = "optimus_access"
    HOOKS = ("player_first_ball", "sw_11")

    def player_first_ball(self):
        self.pd.optimus_access = 0

    def sw_11(self):
        os_ = self.os
        if os_.tilted:
            return
        pd = self.pd
        pd.optimus_access = pd.get("optimus_access", 0) + 1
        os_.score_add(POINTS)
        os_.flag_set(FLAG)
        os_.deff_start(DEFF, values=[max(NEEDED - pd.optimus_access, 0)])
        os_.leff_start(LEFF)
        os_.sound(SOUND)


def feature(os_):
    return OptimusAccess(os_)
