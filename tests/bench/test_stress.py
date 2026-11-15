"""Stress games: a seeded random player shoots everything in any order, in and out of the modes and multiballs,
with one to four players, tilts and drains, and the invariants of driver.check() are verified all along
(docs/test_bench.md "Stress"). A failure prints the seed and the last actions: rerun it with
TF_BENCH_SEED=<seed> TF_BENCH_GAMES=1.

Environment: TF_BENCH_GAMES (games per test, default 2), TF_BENCH_SEED (first seed, default 1),
TF_BENCH_ACTIONS (actions per ball at most, default 60)."""
import os
import random

from tests.bench.driver import AUTOBOT, DECEPTICON, SHOTS, BenchCase

GAMES = int(os.environ.get("TF_BENCH_GAMES", "2"))
SEED = int(os.environ.get("TF_BENCH_SEED", "1"))
ACTIONS = int(os.environ.get("TF_BENCH_ACTIONS", "60"))

# what the random player does, with its weight
PLAIN = [name for name in SHOTS if name not in ("outlane_left", "outlane_right")]
MENU = (("shot", 50), ("eject", 8), ("lock", 8), ("mode", 6), ("megatron", 2), ("optimus", 2), ("drain", 5),
        ("outlane", 2), ("wait", 5), ("tilt", 1), ("flipper", 3), ("wizard", 1), ("award", 3))


class StressCase(BenchCase):
    ADJ = {31: 3}

    def play(self, seed, players=1, side=None, tilt=True):
        rng = random.Random(seed)
        self.log = []
        # the game's own picks follow the seed too, so that a seed replays the same game
        import tf.features.megatron as megatron
        import tf.features.optimus as optimus
        self.tf.random.seed(seed)
        megatron.VARIANTS.seed(seed)
        optimus.VARIANTS.seed(seed)
        random.seed(seed)
        self.tf.forced["side"] = [rng.randrange(2) if side is None else (0 if side == AUTOBOT else 1)
                                  for _ in range(4)]
        try:
            self._play(rng, players, tilt)
        except BaseException:
            print("\nstress seed {} players {}: last actions".format(seed, players))
            for entry in self.log[-25:]:
                print("   ", entry)
            raise

    def note(self, what):
        game = self.game
        self.log.append((round(self.now, 1), game and game.player.number, game and game.player.ball, what))

    def _play(self, rng, players, tilt):
        self.start_game(players=players)
        names, weights = zip(*MENU)
        balls = 0
        while self.game and balls < 40:
            balls += 1
            turn = self.balls_started
            self.settle()
            self.check_fresh_ball()
            self.check()
            for _ in range(rng.randrange(5, ACTIONS)):
                if not self.playing(turn):
                    break
                self.plunge(wait=0.2)
                action = rng.choices(names, weights)[0]
                if action == "tilt" and not tilt:
                    action = "shot"
                self.act(rng, action)
                game = self.game                 # what the game looks like after the action, for the failure print
                self.log[-1] += ("state {:#x}".format(self.tf.state), self.census(),
                                 game and game.balls_in_play, self.feature("megatron").locked_held,
                                 tuple(self.running_modes()) if game else ())
                self.check(settled=False)
                if rng.random() < 0.15:
                    self.settle()
                    self.check()
            if self.playing(turn):
                self.note("end ball")
                self.end_ball()
            else:                           # the random player lost the ball: wait for the next one
                waited = 0.0
                while self.game and self.balls_started == turn and waited < 90:
                    if self.tf.tilted and self.rolling():
                        self.drain(self.rolling())
                    self.wait(0.5)
                    waited += 0.5
                self.assertLess(waited, 90, "no next ball: census {} state {:#x}".format(self.census(),
                                                                                        self.tf.state))
                self.wait(2.5)
            self.plunge()
        self.assertIsNone(self.game, "the game did not end")
        self.wait(3)
        self.drain(self.rolling())
        self.wait(15)
        self.settle()
        self.check()

    def playing(self, turn):
        """The ball that started as `turn` is still in play."""
        return bool(self.game and self.balls_started == turn and self.tf.in_play and self.game.balls_in_play > 0)

    def act(self, rng, action):
        rolling = self.rolling()
        self.note(action)
        if action == "shot":
            if rolling:
                name = rng.choice(PLAIN)
                self.log[-1] += (name,)
                self.shoot(name, wait=rng.choice((0.05, 0.3, 1.0)))
        elif action == "eject":
            if rolling and not self.active("s_left_eject"):
                self.eject()
        elif action == "lock":
            if rolling and self.census()[3] < 4:
                self.lock(wait=rng.choice((0.5, 2.0, 4.5)))
        elif action == "mode":
            if rolling and not self.feature("battles").running() and not self.tf.any_multiball():
                lit = [i for i in (1, 2, 3, 4) if self.pd.ms_lit & (1 << i)]
                for i in lit[:rng.randrange(1, 5)]:
                    self.shoot({1: "left_orbit", 2: "left_ramp", 3: "right_ramp", 4: "right_orbit"}[i])
        elif action == "megatron":
            for _ in range(rng.randrange(1, 5)):
                if self.rolling() and self.census()[3] < 4 and self.tf.in_play:
                    self.lock(wait=3.0)
        elif action == "optimus":
            for _ in range(rng.randrange(2, 9)):
                if self.rolling() and self.tf.in_play:
                    self.shoot(rng.choice(("center", "optimus")))
        elif action == "drain":
            if rolling:
                self.drain(rng.randrange(1, rolling + 1))
                self.wait(rng.choice((0.2, 2.0, 6.0)))
        elif action == "outlane":
            if rolling:
                self.shoot(rng.choice(("outlane_left", "outlane_right")))
                self.drain(1)
                self.wait(2)
        elif action == "wait":
            self.wait(rng.choice((1, 5, 20)))
        elif action == "tilt":
            for _ in range(rng.randrange(1, 4)):
                self.hit("s_tilt_pendulum", wait=1.2)
        elif action == "flipper":
            self.hit_and_release_switch(rng.choice(("s_l_flipper_button", "s_r_flipper_button")))
            self.wait(0.1)
        elif action == "wizard":
            # the long road's end, reached by a shortcut: requirements completed out of order
            reqs = rng.sample(range(11), rng.randrange(1, 12))
            self.log[-1] += (tuple(reqs),)
            self.poke_wizard(reqs)
        elif action == "award":
            self.pd.allspark_lit = self.pd.get("allspark_lit", 0) + 1
            self.tf.request_refresh()


def games(cls, name, first, count, **kwargs):
    """One test per game: test_<name>_<seed>."""
    for n in range(count):
        seed = SEED + first + n
        setattr(cls, "test_{}_seed_{}".format(name, seed),
                (lambda seed_: lambda self: self.play(seed_, **kwargs))(seed))


class TestStress(StressCase):
    pass


games(TestStress, "one_player", 0, GAMES, players=1)
games(TestStress, "two_players", 100, GAMES, players=2)
games(TestStress, "four_players", 200, max(1, GAMES // 2), players=4)
games(TestStress, "autobot_without_tilt", 300, GAMES, players=1, side=AUTOBOT, tilt=False)


class TestStressHard(StressCase):
    """The same games on the settings furthest from the factory ones."""
    ADJ = {31: 2, 32: 0, 38: 0, 66: 4, 67: 2, 68: 2, 69: 1, 70: 2, 82: 4, 83: 1, 86: 1, 87: 0, 88: 0, 89: 0,
           72: 30, 75: 10, 76: 5, 80: 10, 81: 10}


games(TestStressHard, "hard_settings", 400, GAMES, players=2)


class TestStressEasy(StressCase):
    ADJ = {31: 3, 32: 3, 38: 16, 66: 0, 67: 0, 68: 0, 26: 10, 83: 1, 41: 1, 42: 1, 65: 1}


games(TestStressEasy, "easy_settings", 500, GAMES, players=1)
