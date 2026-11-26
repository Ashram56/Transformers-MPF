"""Hint speech, task 0xc6 (rom/rules/modes/game_flow.md 5.7; code [0x01025030] [0x01024fe8] [0x0102523c] [0x01025294]
[0x010250f4]).

A per-player hint call (0x02111f54 + 2 (p - 1)) and its next sample index (0x02111f64 + 4 (p - 1)):
- set(1) (the side mode's start, count_megatron_m_b_a [0x0100fff0] case 4): flags 0x48 / 0x49 cleared, index 0, call
  0x14e, flag 0x48 set; set(0) (the side choice, start_deff_41 [0x01033f54]): flags cleared, index 0, call 0x148 +
  random(3) for the Autobots, else 0x14c + random(2), flag 0x48 left clear;
- the left eject, at every Allspark shot [0x0100a788] (hint_speech_set_allspark [0x01024fe8]): unless flag 0x48 is
  set, set it and the call 0x145; after the show tasks 0x5d-0x7e are over, start;
- the Optimus access (start_deff_141 [0x01025de4]) sets flag 0x48 (0x01024fe0); its deff 141 starts it at frame 10
  ([0x01025f18], 3 ticks a frame);
- start (hint_speech_start [0x01025294]): task 0xc6 when no multiball, no timed mode, flag 0x3c clear (0x0100ff6c),
  flag 0x49 clear and flag 0x48 set (hint_speech_allowed [0x0102523c]);
- task 0xc6 [0x010250f4]: 125 ticks, then, while the index is below the call's sample count (0x00025924), it plays
  sample `index` of the call (0x00025250; tried once a tick, at most 31 times); 0x145 sample 2 queues 0x146 twice,
  0x145 sample 4 queues 0x147 twice, 0x14a sample 1 queues 0x14b (0x0002539c); then the index + 1.
"""
from tf.features import Feature

ORDER = 60
TASK, WAIT_TICKS, TRIES = 0xc6, 0x7d, 31
FLAG, DONE_FLAG, SIDE_FLAG = 0x48, 0x49, 0x3c
ALLSPARK_CALL, SIDE_MODE_CALL = 0x145, 0x14e
AUTOBOT = 1
# (call, sample) -> the call queued after it, and whether twice (0x0002539c with last argument 0, then 1)
QUEUED = {(0x145, 2): (0x146, 2), (0x145, 4): (0x147, 2), (0x14a, 1): (0x14b, 1)}


class Hint(Feature):
    name = "hint"
    HOOKS = ("player_first_ball", "hint_set", "hint_set_allspark", "hint_start")

    def player_first_ball(self):
        self.pd.hint_call = 0
        self.pd.hint_index = 0

    def hint_set(self, arg):
        """hint_speech_set [0x01025030]."""
        os_ = self.os
        pd = self.pd
        os_.flag_clear(FLAG)
        os_.flag_clear(DONE_FLAG)
        pd.hint_index = 0
        if arg == 1:
            pd.hint_call = SIDE_MODE_CALL
            os_.flag_set(FLAG)
            return
        if pd.get("side") == AUTOBOT:
            pd.hint_call = 0x148 + os_.pick("hint_autobot", [1, 1, 1])
        else:
            pd.hint_call = 0x14c + os_.pick("hint_decepticon", [1, 1])

    def hint_set_allspark(self):
        """hint_speech_set_allspark [0x01024fe8]."""
        if self.os.flag(FLAG):
            return
        self.os.flag_set(FLAG)
        self.pd.hint_call = ALLSPARK_CALL

    def allowed(self):
        """hint_speech_allowed [0x0102523c]."""
        os_ = self.os
        return (not os_.any_multiball() and not os_.timed_mode_running() and not os_.flag(SIDE_FLAG)
                and not os_.flag(DONE_FLAG) and os_.flag(FLAG))

    def hint_start(self):
        """hint_speech_start [0x01025294]: (re)start task 0xc6."""
        if not self.os.game or not self.allowed():
            return False
        self.os.task_start(TASK, WAIT_TICKS, self._speak)
        return True

    def _speak(self, tries=0):
        """Task 0xc6 [0x010250f4], after its 125 ticks."""
        os_ = self.os
        if not os_.game:
            return
        pd = self.pd
        call, index = pd.get("hint_call", 0), pd.get("hint_index", 0)
        if not call or index >= len(os_.sample_lengths(call)):
            return
        if os_.sound_refused(call):
            if tries < TRIES - 1:
                os_.task_start(TASK, 1, lambda: self._speak(tries + 1))
            return
        end = os_.sound(call, index=index)
        queued = QUEUED.get((call, index))
        if queued:
            self._queue(queued[0], queued[1], end)
        pd.hint_index = index + 1

    def _queue(self, call, times, after):
        """snd_play_after [0x0002539c]: `call` once the previous sample ends, `times` times."""
        os_ = self.os

        def play():
            end = os_.sound(call)
            if times > 1:
                self._queue(call, times - 1, end)
        if after is None or after <= os_.now:
            play()
        else:
            os_.machine.clock.schedule_once(lambda: play(), after - os_.now)


def feature(os_):
    return Hint(os_)
