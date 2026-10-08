"""Game over: match, game-over music and the return to attract (OS code; Tron's game_flow.md 5.5 and 6.2).
Timings are Tron's reference traces (the same OS)."""
import random

from tf.features import Feature

MATCH_REVEAL = 258       # ticks from deff 38 to the match award (traces/game_flow.jsonl 4.19 s)
ATTRACT_DELAY = 370      # ticks from the match display to attract (traces/game_flow.jsonl 158.65 -> 164.66 s)
GAME_OVER_MUSIC, GAME_OVER_SPEECH, SPEECH_TICKS = 0x24, 0x4b, 0x7c   # task 0x9b [0x01006138]


class GameOver(Feature):
    name = "match"

    def run(self, done):
        os_ = self.os
        if os_.hook("slammed"):                   # a slam tilt resets the machine: straight to attract
            os_.hook("attract_start")
            done()
            return
        number = random.randrange(0, 100, 10)
        os_.deff_start(38, number=number, number_again=number)   # deff 38 prints the number (task + 0x34)
        forced = os_.forced.get("match")
        matched = 0
        # match [0x0001b660]: adj 30 MATCH PERCENTAGE (11 = OFF). The number can match only while the
        # machine's match rate (TOTAL MATCHES 0x0f x 100 / games 0x11, persistent audits) is below adj 30;
        # otherwise the ROM picks a number no player has.
        audits = os_.audits
        rate = audits[0x0f] * 100 // audits[0x11] if audits[0x11] else 0
        if os_.adj_value(30) < 11 and rate < os_.adj_value(30):
            matched = sum(1 for p in self.machine.game.player_list if p.score % 100 == number)
        if forced:
            matched = forced.pop(0)
        if matched:
            os_.after(MATCH_REVEAL, lambda: self._award(matched))
        os_.after(ATTRACT_DELAY, lambda: self._attract(done))

    def _award(self, matched):
        """Match award (adj 29): 0 = credit with knocker 0x019."""
        os_ = self.os
        for _ in range(matched):
            os_.audit(0x0f)
            if os_.adj_value(29) == 0:
                os_.award_credit()                # FUN_00004cf0, then the knocker FUN_0001b370
                os_.knock()
            else:
                self.machine.events.post("tf_award_ticket" if os_.adj_value(29) == 1 else "tf_award_token")

    def _attract(self, done):
        os_ = self.os
        os_.hook("attract_start")                 # event 0x08: deff 1, leff 1, attract tube rule
        # task 0x9b [0x01006138], one tick later: the game-over music 0x24 (unless it already plays), then the
        # speech 0x4b 124 ticks later (observed: game_flow.jsonl 164.68 / 166.66 s); no leff
        os_.after(1, lambda: os_.sound(GAME_OVER_MUSIC))
        os_.after(1 + SPEECH_TICKS, lambda: os_.game or os_.sound(GAME_OVER_SPEECH))   # a game start kills it
        done()


feature = GameOver
