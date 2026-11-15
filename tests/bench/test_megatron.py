"""The Megatron lock and multiball (rom/rules/modes/megatron_multiball.md), and the lock's ball handling
[0x0100a1f8] over balls, players and the operator adjustments 68, 69, 88, 89."""
from tests.bench.driver import AUTOBOT, BenchCase


class TestMegatronDecepticon(BenchCase):

    def test_locks_and_multiball(self):
        """4.1-4.3: all four locks lit at game start (adj 68 EXTRA EASY); 25,000 + 5,120 a lock, the ball stays
        and a new one is launched; the fourth ball starts the multiball: 100,000, four balls, level + 1."""
        self.start_game()
        self.assertEqual(4, self.pd.mtl_lit)
        for n in (1, 2, 3):
            self.assertEqual(25000 + 5120, self.lock())
            self.settle()
            self.assertEqual((n, 4 - n), (self.pd.mtl_locked, self.pd.mtl_lit))
            self.assertEqual(n, self.census()[3], "lock {} did not keep its ball".format(n))
            self.assertEqual(1, self.game.balls_in_play)
            self.check()
        self.assertEqual(100000 + 5120, self.lock(wait=1))
        side = self.feature("megatron").running()
        self.assertIsNotNone(side)
        self.assertTrue(self.tf.flag(0x29))
        self.assertEqual((1, 0, 0), (self.pd.mtl_level, self.pd.mtl_lit, self.pd.mtl_locked))
        self.wait(12)
        self.settle()
        self.assertEqual(4, self.game.balls_in_play)
        self.assertEqual(4, self.rolling(), "the four balls are not on the playfield: {}".format(self.census()))
        self.check()

    def test_jackpots_double_and_super(self):
        """5 (Decepticon): a lit shot 100,000 + 25,000 x jackpots (cap 250,000), Megatron 100,000 and relights;
        after 10 the center lane scores 3 doubles of 500,000, then Optimus the 1,000,000 super."""
        self.start_game()
        side = self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        self.mark()
        made = []
        for shot in ("left_orbit", "left_ramp", "right_ramp", "right_orbit", "center"):
            self.shoot(shot)
            made.append(side.total)
        gains = [b - a for a, b in zip([100000] + made, made)]
        self.assertEqual([100000, 125000, 150000, 175000, 200000], gains)
        self.lock()                                 # Megatron: 100,000 and every shot lit again
        self.assertEqual(0x7f, side.mask)
        while side.phase == 1:
            self.shoot(next(n for n in ("left_ramp", "right_ramp", "left_orbit", "right_orbit", "center")
                            if side.mask & (1 << {"left_orbit": 1, "left_ramp": 2, "center": 3, "right_ramp": 4,
                                                  "right_orbit": 5}[n])))
        self.assertEqual(10, side.jp)
        before = side.total
        for _ in range(3):
            self.shoot("center")
        self.assertEqual(3 * 500000, side.total - before)
        self.assertEqual(3, side.phase)
        self.shoot("optimus")
        self.assertEqual(3 * 500000 + 1000000, side.total - before)
        self.assertEqual(1, side.phase)
        self.assertIn(0x7d, self.audits())
        self.assertEqual([1, 1], self.feature("wizard").reqs()[0])      # requirement 0 collected and completed
        self.check(settled=False)

    def test_ends_with_one_ball_and_relights_with_energon(self):
        """6 and 4.1: down to one ball the multiball ends (total deff 80); at level 1 one Energon set relights all
        four locks."""
        self.start_game()
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        self.wait_ball_save()
        self.drain(3)
        self.wait(6)
        self.assertEqual(1, self.game.balls_in_play)
        self.assertFalse(self.tf.flag(0x29))
        self.assertIn(80, self.deffs())
        self.assertEqual(0, self.pd.mtl_lit)
        self.complete_energon()
        self.assertEqual(4, self.pd.mtl_lit)
        self.assertIn(139, self.deffs())
        self.settle()
        self.check()

    def test_locked_balls_stay_over_the_balls(self):
        """[0x0100a1f8]: the device keeps lit + locked balls (at most 3) of the player; a drain does not free them,
        and the multiball started on a later ball has its four balls."""
        self.start_game()
        self.lock()
        self.lock()
        self.settle()
        self.assertTrue(self.end_ball())
        self.plunge()
        self.settle()
        self.assertEqual(2, self.census()[3], "the locked balls left the lock at the end of the ball")
        self.assertEqual(2, self.pd.mtl_locked)
        self.check()
        self.lock()
        self.lock(wait=1)
        self.assertIsNotNone(self.feature("megatron").running())
        self.wait(12)
        self.settle()
        self.assertEqual((4, 4), (self.game.balls_in_play, self.rolling()))
        self.check()
        self.end_game()
        self.check()

    def test_lock_is_not_lit_during_a_multiball(self):
        """4.1: no lock while the Optimus multiball runs; the entry scores its 5,120 and the ball comes back."""
        self.start_game()
        self.start_optimus_multiball()
        self.wait(8)
        self.settle()
        locked = self.pd.mtl_locked
        self.lock()
        self.settle()
        self.assertEqual(locked, self.pd.mtl_locked)
        self.assertEqual(0, self.census()[3])
        self.check()


class TestMegatronAutobot(BenchCase):
    SIDE = AUTOBOT

    def test_autobot_rules(self):
        """5 (Autobot): 250,000 at the start; Megatron lights the jackpot J = 100,000 x (supers + 1) + 25,000 x M,
        then the six shots score doubles 2 J; all six made: the super at Megatron, at least 1,000,000."""
        self.start_game()
        side = self.start_megatron_multiball()
        self.assertTrue(self.tf.flag(0x25))
        self.assertEqual(250000, side.total)
        self.wait(12)
        self.settle()
        self.lock()
        self.assertEqual(250000 + 125000, side.total)
        self.assertEqual(2, side.phase)
        before = side.total
        self.shoot("left_ramp")
        self.assertEqual(2 * (100000 + 25000 * 2), side.total - before)
        for shot in ("right_ramp", "center", "left_orbit", "right_orbit"):
            self.shoot(shot)
        self.eject()
        self.assertEqual(3, side.phase)
        before = side.total
        self.lock()
        self.assertGreaterEqual(side.total - before, 1000000)
        self.assertIn(0x79, self.audits())
        self.check(settled=False)


class TestVirtualLock(BenchCase):
    ADJ = {69: 1}

    def test_adj_69_keeps_no_ball(self):
        """adj 69 MEGATRON M.B. VIRTUAL LOCK = YES [0x0100a1f8]: every locked ball is kicked out again, the locks
        are only counted; the multiball still starts on the fourth and brings its balls from the trough."""
        self.start_game()
        for n in (1, 2, 3):
            self.assertEqual(25000 + 5120, self.lock())
            self.settle()
            self.assertEqual(n, self.pd.mtl_locked)
            self.assertEqual(0, self.census()[3], "the lock kept a ball on VIRTUAL LOCK")
            self.assertEqual((3, 1), (self.census()[0], self.rolling()))
            self.check()
        self.lock(wait=1)
        self.assertIsNotNone(self.feature("megatron").running())
        self.wait(12)
        self.settle()
        self.assertEqual((4, 4), (self.game.balls_in_play, self.rolling()))
        self.check()


class TestAutofireAfterLock(BenchCase):
    ADJ = {89: 0}

    def test_adj_89_no_leaves_the_ball_to_the_player(self):
        """adj 89 AUTOFIRE AFTER LOCK = NO [0x0100a074]: the ball served after a lock waits in the shooter lane."""
        self.start_game()
        self.assertGreater(self.rolling(), 0)
        self.sw("s_m_tron_lock_1_back", 1)
        self.wait(8)
        self.assertEqual((1, 1, 0), (self.census()[1], self.census()[3], self.rolling()),
                         "the ball after the lock was launched by the game: {}".format(self.census()))
        self.plunge()
        self.assertEqual(1, self.rolling())
        self.settle()
        self.check()

    def test_factory_setting_launches_it(self):
        self.set_adj(89, 1)
        self.start_game()
        self.sw("s_m_tron_lock_1_back", 1)
        self.wait(8)
        self.assertEqual((0, 1, 1), (self.census()[1], self.census()[3], self.rolling()))


class TestLockDifficulty(BenchCase):
    ADJ = {68: 2}

    def test_adj_68_needs_energon_sets(self):
        """adj 68 MEGATRON LOCK DIFFICULTY: level 2 starts with no lock lit; each Energon set lights one lock
        (need min(level - 1, 5) = 1 completion per lock)."""
        self.start_game()
        self.assertEqual((0, 2), (self.pd.mtl_lit, self.pd.mtl_level))
        self.lock()
        self.settle()
        self.assertEqual((0, 0), (self.pd.mtl_locked, self.census()[3]))
        self.complete_energon()
        self.assertEqual(1, self.pd.mtl_lit)
        self.lock()
        self.settle()
        self.assertEqual((1, 0, 1), (self.pd.mtl_locked, self.pd.mtl_lit, self.census()[3]))
        self.check()


class TestLockTwoPlayers(BenchCase):
    PLAYERS = 2

    def test_two_players_share_the_device(self):
        """[0x0100a1f8]: the lock counts are each player's, the three places in the device are shared. Player 1
        locks three; player 2's locks are then counted with the ball kicked out again (the device is full),
        and player 2's multiball still has four balls. The game never runs out of balls."""
        self.start_game()
        for _ in range(3):
            self.lock()
        self.settle()
        self.assertEqual(3, self.census()[3])
        self.assertTrue(self.end_ball())
        self.plunge()
        self.settle()
        self.assertEqual(2, self.game.player.number)
        self.assertEqual((0, 4), (self.pd.mtl_locked, self.pd.mtl_lit))
        self.assertEqual(3, self.census()[3], "player 1's balls left the lock")
        self.check()
        for n in (1, 2, 3):
            self.lock()
            self.settle()
            self.assertEqual(n, self.pd.mtl_locked)
            self.assertEqual(3, self.census()[3])
            self.assertEqual(1, self.rolling(), "player 2 has no ball to play: {}".format(self.census()))
            self.check()
        self.lock(wait=1)
        self.assertIsNotNone(self.feature("megatron").running())
        self.wait(12)
        self.settle()
        self.assertEqual((4, 4), (self.game.balls_in_play, self.rolling()))
        self.wait_ball_save()
        self.drain(3)
        self.wait(6)
        self.assertTrue(self.end_ball())
        self.plunge()
        self.settle()
        self.assertEqual(1, self.game.player.number)
        self.assertEqual(3, self.pd.mtl_locked)       # player 1 still has three locks counted, the device is empty
        self.check()
        self.lock(wait=1)
        self.assertIsNotNone(self.feature("megatron").running())
        self.wait(12)
        self.settle()
        self.assertEqual((4, 4), (self.game.balls_in_play, self.rolling()))
        self.check()
        self.end_game()
        self.check()


class TestOutlaneSaveWithEveryBallInPlay(BenchCase):
    PLAYERS = 2

    def test_count_stays_exact(self):
        """Stress seed 1105: the next player gets the three balls a back door shot releases from the lock, so all
        four balls roll. An outlane save then cannot add a ball to MPF's count (capped at the balls it knows): the
        outlane ball's drain is the replacement's serve [0x00019b34], and the lock still counts later."""
        self.start_game()
        self.assertTrue(self.end_ball())            # player 1's first ball is over
        self.plunge()
        self.settle()
        for _ in range(3):                          # player 2 locks three
            self.lock()
        self.settle()
        self.assertTrue(self.end_ball())            # player 1's second ball
        self.plunge()
        self.settle()
        self.shoot("back_door")                     # the back door task keeps nothing [0x0100a1f8]: they come out
        self.wait(12)
        self.settle()
        self.assertEqual(4, self.game.balls_in_play)
        self.shoot("outlane_left")
        self.drain(1)
        self.wait(3)
        self.settle()
        self.check()
        self.assertEqual(4, self.game.balls_in_play)
        self.lock()
        self.settle()
        self.check()
