"""The mode-start shots and the eight battles (rom/rules/modes/battles.md), each one from its start to its
completion, its time-out and its end at a drain, on both sides."""
from tests.bench.driver import AUTOBOT, BenchCase

LONG_TIMERS = {72: 60, 73: 60, 74: 60, 75: 30, 76: 30, 77: 35, 79: 60}
# key -> (record, wizard requirement, started audit, completed audit, timer adjustment, shots to complete)
BATTLES = {"ss": (0, 1, 0x59, 0x5a, 72, 10), "sw": (1, 2, 0x5b, 0x5c, 73, 11), "bo": (2, 3, 0x5d, 0x5e, 74, 11),
           "dv": (3, 4, 0x5f, 0x60, 75, 10), "bb": (4, 6, 0x61, 0x62, 76, 7), "ih": (5, 7, 0x63, 0x64, 77, 10),
           "mf": (6, 8, 0x65, 0x66, 78, 11), "ra": (7, 9, 0x67, 0x68, 79, 11)}


class TestModeStart(BenchCase):

    def points(self):
        return [e["points"] for e in self.events("score_add")]

    def test_four_lit_shots_start_the_lit_battle(self):
        """4.2: a lit mode-start shot scores 10,000 + 10,000 x battles started + 5,000 x hits (cap 75,000); the
        fourth starts the lit battle (Decepticon: Starscream): 100,000, audits 0x59 and 0x58."""
        self.start_game()
        self.assertEqual(0x01, self.pd.battle_lit)
        self.assertEqual(4, bin(self.pd.ms_lit).count("1"))        # adj 66 HARD: four lit, at least three kept
        battle = self.start_battle()
        self.assertEqual("ss", battle.key)
        got = self.points()
        for value in (10000, 15000, 20000, 25000, 100000):
            self.assertIn(value, got)
        self.assertIn(91, self.deffs())
        self.assertIn(0x59, self.audits())
        self.assertIn(0x58, self.audits())
        self.assertEqual(0x01, self.pd.battle_started)
        self.assertEqual(0x02, self.pd.battle_lit)                  # the next of the ring: Shockwave
        self.assertEqual([1, 0], self.feature("wizard").reqs()[1])
        self.assertEqual(self.tf.adj[72], battle.seconds)
        self.check(settled=False)

    def test_the_second_battle_scores_more(self):
        self.start_game()
        self.start_battle()
        self.end_ball()
        self.plunge()
        self.mark()
        self.start_battle()
        got = self.points()
        for value in (20000, 25000, 30000, 35000):                  # 10,000 + 10,000 x 1 started + 5,000 x hits
            self.assertIn(value, got)

    def test_no_mode_start_while_a_battle_or_a_multiball_runs(self):
        """4.2 (clu_start_allowed [0x01022ca8]): the shots do not count during a battle or a multiball."""
        self.start_game()
        self.start_battle()
        hits = self.pd.ms_hits
        self.shoot("left_ramp")
        self.assertEqual(hits, self.pd.ms_hits)
        self.end_ball()
        self.plunge()
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        hits = self.pd.ms_hits
        for shot in ("left_ramp", "right_ramp", "left_orbit"):
            self.shoot(shot)
        self.assertEqual(hits, self.pd.ms_hits)
        self.assertIsNone(self.feature("battles").running())

    def test_pops_and_bumblebee_move_the_lit_battle(self):
        """[0x01022cf8]: each pop bumper or Bumblebee hit lights the side's next battle not yet started."""
        self.start_game()
        seen = [self.pd.battle_lit]
        for shot in ("pop_top", "bumblebee", "pop_right", "pop_bottom"):
            self.shoot(shot)
            seen.append(self.pd.battle_lit)
        self.assertEqual([0x01, 0x02, 0x04, 0x08, 0x01], seen)

    def test_a_started_battle_comes_back_after_the_others(self):
        """[0x010229ec]: the next battle is the first not started; with all four started, the first not completed."""
        self.set_adj(31, 5)
        self.start_game()
        for key in ("ss", "sw", "bo", "dv"):
            self.start_battle()
            self.assertEqual(key, self.feature("battles").running().key)
            self.end_ball()
            self.plunge()
        self.assertEqual(0x0f, self.pd.battle_started)
        self.assertEqual(0x01, self.pd.battle_lit)
        self.assertEqual(0, self.pd.battle_completed)


class TestModeStartDifficulty(BenchCase):

    def test_adj_66_sets_the_lit_shots(self):
        """adj 66 MODE START DIFFICULTY [0x0101fd14]: shots lit at a reset / kept lit: EXTRA EASY 5 / 5 (a hit
        shot stays lit), EASY 5 / 4, MEDIUM 4 / 4, HARD 4 / 3, EXTRA HARD 4 / 2."""
        for value, (lit, kept) in {0: (5, 5), 1: (5, 4), 2: (4, 4), 3: (4, 3), 4: (4, 2)}.items():
            with self.subTest(adj_66=value):
                self.set_adj(66, value)
                self.start_game()
                self.assertEqual(lit, bin(self.pd.ms_lit).count("1"))
                counts = []
                for _ in range(3):
                    first = next(i for i in (2, 3, 1, 4, 0) if self.pd.ms_lit & (1 << i))
                    self.shoot_any({0: "eject", 1: "left_orbit", 2: "left_ramp", 3: "right_ramp",
                                    4: "right_orbit"}[first])
                    counts.append(bin(self.pd.ms_lit).count("1"))
                self.assertEqual(kept, min(counts))
                self.assertEqual(3, self.pd.ms_hits)
                self.end_game()


class BattleCase(BenchCase):
    ADJ = LONG_TIMERS

    def play(self, key):
        index, req, started, completed, _, shots = BATTLES[key]
        self.start_game()
        battle = self.start_battle(key)
        self.assertEqual(key, battle.key)
        self.battle = battle
        self.assertIn(started, self.audits())
        self.assertEqual(100000, battle.total)
        self.settle()
        before = self.score
        self.mark()
        self.complete_battle(battle)
        self.assertIn(completed, self.audits())
        self.assertEqual([1, 1], self.feature("wizard").reqs()[req])
        lit_hits = [e for e in self.events("deff_start", id=battle.hit_deff)]
        self.assertEqual(shots, len(lit_hits), "lit hits to complete {}".format(key))
        self.assertGreater(self.score - before, 0)
        if not battle.multiball:
            self.assertFalse(battle.scoring)
            self.wait(12)
            self.assertIn(battle.total_deff, self.deffs())
        self.settle()
        self.check()
        return battle

    def hit_values(self):
        """The points of each lit hit: the score added right before the hit's display effect."""
        out, last = [], 0
        for ev in self.tf.trace.events:
            if ev["ev"] == "score_add":
                last = ev["points"]
            elif ev["ev"] == "deff_start" and ev["id"] == self.battle.hit_deff:
                out.append(last)
        return out


class TestDecepticonBattles(BattleCase):

    def test_starscream(self):
        """5.1: ten shots on the moving pair, 100,000 + 12,500 a hit."""
        self.play("ss")
        values = self.hit_values()
        self.assertEqual([100000 + 12500 * n for n in range(10)], values)

    def test_shockwave(self):
        """5.2: the Allspark, the right ramp, then nine of the six shots: 200,000 + 25,000 a hit."""
        self.play("sw")
        values = self.hit_values()
        self.assertEqual([200000 + 25000 * n for n in range(11)], values)

    def test_blackout(self):
        self.play("bo")
        values = self.hit_values()
        self.assertEqual([200000 + 50000 * n for n in range(11)], values)

    def test_devastator(self):
        self.play("dv")
        values = self.hit_values()
        self.assertEqual([100000 + 100000 * n for n in range(10)], values)


class TestAutobotBattles(BattleCase):
    SIDE = AUTOBOT

    def test_bumblebee(self):
        """5.5: the six shots at the decaying value build the jackpot, then the Bumblebee target collects it."""
        battle = self.play("bb")
        self.assertEqual(2, self.pd.bb_phase)
        values = self.hit_values()
        self.assertEqual(sum(values[:6]), values[6])

    def test_ironhide(self):
        self.play("ih")
        values = self.hit_values()
        self.assertEqual([200000 + 50000 * n for n in range(10)], values)

    def test_mudflap_and_skids(self):
        """5.7: a two-ball multiball (ball save adj 78 seconds); it ends with one ball left."""
        battle = self.play("mf")
        self.assertTrue(self.tf.flag(0x1e))
        self.assertEqual(2, self.game.balls_in_play)
        self.wait_ball_save()
        self.drain(1)
        self.wait(6)
        self.assertFalse(self.tf.flag(0x1e))
        self.assertFalse(battle.scoring)
        self.assertIn(119, self.deffs())
        self.settle()
        self.check()

    def test_ratchet(self):
        """5.8: the lowest lit shot scores double."""
        self.play("ra")
        values = self.hit_values()
        self.assertEqual(11, len(values))
        base = [100000 + 50000 * n for n in range(11)]        # no completion yet: 100,000 + 50,000 x hits
        for n, value in enumerate(values):
            self.assertIn(value, (base[n], 2 * base[n]))
        self.assertTrue(any(value == 2 * base[n] for n, value in enumerate(values)))


class TestBattleEnds(BenchCase):

    def test_time_out(self):
        """6: the timer counts the adjustment's seconds once the intro is over; at 0 the battle ends, its lit shots
        score 125 ticks more, then the total. It is not completed and comes back after the others."""
        self.set_adj(72, 30)
        self.start_game()
        battle = self.start_battle("ss")
        self.assertEqual(30, battle.seconds)
        self.wait(20)
        self.assertTrue(battle.active)
        self.assertLess(battle.seconds, 30)
        self.wait(40)
        self.assertFalse(battle.scoring)
        self.assertIn(95, self.deffs())
        self.assertEqual((0x01, 0), (self.pd.battle_started, self.pd.battle_completed))
        self.assertEqual([1, 0], self.feature("wizard").reqs()[1])
        self.settle()
        self.check()

    def test_timer_adjustments(self):
        """adj 72-77, 79: each timed battle starts with its adjustment's seconds."""
        for key, adj, value in (("ss", 72, 33), ("sw", 73, 41), ("bo", 74, 52), ("dv", 75, 11), ("ih", 77, 17),
                                ("ra", 79, 23)):
            with self.subTest(battle=key):
                self.tf.forced["side"] = [1 if key in ("ss", "sw", "bo", "dv") else 0] * 4
                self.set_adj(adj, value)
                self.start_game()
                self.assertEqual(value, self.start_battle(key).seconds)
                self.end_game()

    def test_a_drain_ends_the_battle(self):
        self.start_game()
        battle = self.start_battle()
        self.end_ball()
        self.assertFalse(battle.scoring)
        self.assertIn(battle.total_deff, self.deffs())
        self.plunge()
        self.settle()
        self.check_fresh_ball()
        self.check()

    def test_a_tilt_ends_the_battle_without_total(self):
        self.set_adj(32, 0)
        self.start_game()
        battle = self.start_battle()
        self.mark()
        self.hit("s_tilt_pendulum", wait=1)
        self.assertTrue(self.tf.tilted)
        self.assertFalse(battle.scoring)
        self.drain(self.rolling())
        self.wait(8)
        self.assertNotIn(battle.total_deff, self.deffs())
        self.plunge()
        self.settle()
        self.check_fresh_ball()
