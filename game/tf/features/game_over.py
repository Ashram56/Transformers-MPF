"""Game over: match, game-over music and the return to attract (OS code; Tron's game_flow.md 5.5 and 6.2).
The match sequence is read from match [0x00019668] and deff 38 [0x0100820c] (QA F9)."""
from tf.features import Feature
from tf.os_layer import TICK

# deff 38 [0x0100820c]: 68 frames of 5 ticks (sound 0x023 at 0, 0x072 matched / 0x073 not at frame 60), the
# awards after the last frame, then if any: 0x074 and 24 more frames; task_sleep(0x1f) and a 2-tick hold
FRAME_TICKS, VERDICT_FRAME, FRAMES, WIN_FRAMES, TAIL_TICKS = 5, 60, 68, 24, 0x1f + 2
MATCH_SOUND, MATCHED_SOUND, NO_MATCH_SOUND, WIN_SOUND = 0x023, 0x072, 0x073, 0x074
GAME_OVER_MUSIC, GAME_OVER_SPEECH, SPEECH_TICKS = 0x24, 0x4b, 0x7c   # task 0x9b [0x01006138]
# sample 0x28f's script sets slot +0x8c (op 0x0d, snd_op_set_8c [0x000245a8]) after 6501 + 98240 units of 1/4000 s;
# the task then raises voice 0's attenuation by 1 every 2 ticks up to 0x100 (snd_chan_25dc4 [0x00025dc4]), from
# the 0 snd_start_sample [0x00024ae4] gives each voice it takes, and frees the slot; the sample ends 20000 units after the cue
MUSIC_CUE_S, MUSIC_FADE_S, MUSIC_END_S = (6501 + 98240) / 4000, 0x100 * 2 * 0.016, 124741 / 4000


class GameOver(Feature):
    name = "match"

    def number(self, scores):
        """match [0x00019668]: a random 00-90; while the machine's match rate (audits 0x0f x 100 / 0x11) is below adj
        30 MATCH PERCENTAGE, the players whose score ends with it match; otherwise the number steps by 10 until no
        player has it (QA F9a). -> (number, matched player count)."""
        os_ = self.os
        number = os_.pick("match_number", [1] * 10)
        number = (number or 0) * 10
        audits = os_.audits
        rate = audits[0x0f] * 100 // audits[0x11] if audits[0x11] else 0
        if rate < os_.adj_value(30):
            return number, sum(1 for score in scores if score % 100 == number)
        start = n = number
        while True:
            n = n + 10 if n + 10 <= 99 else 0
            if not any(score % 100 == n for score in scores) or n == start:
                return n, 0

    def run(self, done):
        os_ = self.os
        if os_.hook("slammed"):                   # a slam tilt resets the machine: straight to attract
            os_.hook("attract_start")
            done()
            return
        if os_.adj_value(30) == 11:               # MATCH OFF: no deff 38 [0x00019668] (QA F9c; tournament not modelled)
            self._attract(done)
            return
        number, matched = self.number([p.score for p in self.machine.game.player_list])
        forced = os_.forced.get("match")
        if forced:
            matched = forced.pop(0)
        ticks = FRAMES * FRAME_TICKS + (WIN_FRAMES * FRAME_TICKS if matched else 0) + TAIL_TICKS
        verdict = MATCHED_SOUND if matched else NO_MATCH_SOUND
        os_.deff_start(38, number=number, number_again=number, run_seconds=ticks * TICK, sounds=[
            (0.0, lambda: os_.sound(MATCH_SOUND, in_deff=38)),
            (VERDICT_FRAME * FRAME_TICKS * TICK, lambda: os_.sound(verdict, in_deff=38))])
        if matched:                               # inside the deff, after its 68th frame (QA F9b)
            os_.after(FRAMES * FRAME_TICKS, lambda: self._award(matched))
        os_.after(ticks, lambda: self._attract(done))

    def _award(self, matched):
        """match_award [0x00019874] per matched player (adj 29: 0 = credit with knocker 0x019), then 0x074."""
        os_ = self.os
        for _ in range(matched):
            os_.audit(0x0f)
            if os_.adj_value(29) == 0:
                os_.award_credit()                # FUN_000041a0, then the knocker FUN_00019378
                os_.knock()
            else:
                self.machine.events.post("tf_award_ticket" if os_.adj_value(29) == 1 else "tf_award_token")
        os_.sound(WIN_SOUND, in_deff=38)

    def _music(self):
        """Task 0x9b [0x01006138]: 0x24 in attract unless it plays already; at the script's cue a fade out."""
        os_ = self.os
        if os_.game:
            return
        if not os_.sound_playing(GAME_OVER_MUSIC):
            if os_.sound(GAME_OVER_MUSIC) is None and not os_.sound_playing(GAME_OVER_MUSIC):
                return
        start = os_.now
        def fade():
            if not os_.game and os_.sound_playing(GAME_OVER_MUSIC):
                os_.media.sound_fade(GAME_OVER_MUSIC, MUSIC_FADE_S)
                os_.machine.clock.schedule_once(lambda _dt=None: os_.game or os_.sound_stop(GAME_OVER_MUSIC),
                                                max(MUSIC_END_S - (os_.now - start), 0))
        os_.machine.clock.schedule_once(lambda _dt=None: fade(), MUSIC_CUE_S)

    def _attract(self, done):
        os_ = self.os
        os_.hook("attract_start")                 # event 0x08: deff 1, leff 1, attract tube rule
        # task 0x9b [0x01006138], one tick later: the game-over music 0x24 (unless it already plays), then the
        # speech 0x4b after task_sleep(0x7c) (confirmed: game_flow.jsonl 164.68 / 166.66 s); no leff
        os_.after(1, self._music)
        os_.after(1 + SPEECH_TICKS, lambda: os_.game or os_.sound(GAME_OVER_SPEECH))   # a game start kills it
        done()


feature = GameOver
