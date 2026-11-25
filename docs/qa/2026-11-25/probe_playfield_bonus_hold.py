"""F: BONUS HOLD / BONUS X HOLD flags 0x4b / 0x4a are never cleared in the game; ROM clears them at the next
ball start (event 0x13 hook 0x01000d58: bl 0x5a38 game_flag_clear(0x4a) / (0x4b))."""
from qa_base import QaBase
class T(QaBase):
    def test_hold(self):
        self.start_ball()
        a = self.tf.features_by_name["allspark"]
        a.run(8); a.run(9); a.run(4)           # BONUS HOLD, BONUS X HOLD, +1X -> 2X
        for _ in range(5): self.hit("s_left_slingshot", 0.3)
        for b in range(2, 4):
            self.next_ball()
            pd = self.tf.pd
            print("ball", self.machine.game.player.ball, "held", pd.bonus_held, "bonus_x", pd.bonus_x,
                  "flags 0x4a/0x4b set:", self.tf.flag(0x4a), self.tf.flag(0x4b),
                  "allspark weights item8/9:", a.weights()[7], a.weights()[8])
            for _ in range(5): self.hit("s_left_slingshot", 0.3)
