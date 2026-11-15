"""Several players: what one player earns or starts must not reach the others (the ROM keeps its game flags and
its rules' state per player: rom/rom_data/io/game_flags.csv, the 0x0211xxxx player areas)."""
from tests.bench.driver import BenchCase


class TestPlayers(BenchCase):
    PLAYERS = 2

    def next_player(self):
        self.end_ball()
        self.plunge()
        self.settle()

    def test_a_battle_belongs_to_its_player(self):
        self.start_game()
        self.start_battle()
        self.assertEqual(0x01, self.pd.battle_started)
        self.next_player()
        self.assertEqual(2, self.game.player.number)
        self.check_fresh_ball()
        self.assertEqual((0, 0x01), (self.pd.get("battle_started", 0), self.pd.battle_lit))
        self.assertEqual([[0, 0]] * 11, self.feature("wizard").reqs())
        self.assertEqual("ss", self.start_battle().key)
        self.next_player()
        self.assertEqual((1, 2), (self.game.player.number, self.game.player.ball))
        self.assertEqual(0x01, self.pd.battle_started)
        self.assertEqual("sw", self.start_battle().key)             # player 1 goes on with the next battle
        self.check(settled=False)

    def test_game_flags_are_per_player(self):
        """Flags without attribute bit 1 (BONUS HOLD 0x4b, BONUS X HOLD 0x4a, the extra ball's 0x15, the side
        mode's 0x3d ...) are saved and restored at each player change [0x00005bb0 / 0x00005bf4]."""
        self.start_game()
        for flag in (0x4b, 0x4a, 0x15, 0x3d):
            self.tf.flag_set(flag)
        self.next_player()
        for flag in (0x4b, 0x4a, 0x15, 0x3d):
            self.assertFalse(self.tf.flag(flag), "flag {:#x} of player 1 reached player 2".format(flag))
        self.tf.flag_set(0x40)
        self.next_player()
        for flag in (0x4b, 0x4a, 0x15, 0x3d):
            self.assertTrue(self.tf.flag(flag), "player 1 lost flag {:#x}".format(flag))
        self.assertFalse(self.tf.flag(0x40))

    def test_bonus_hold_is_the_players_own(self):
        self.start_game()
        self.tf.flag_set(0x4b)
        self.shoot("sling_left")
        self.validate()
        held = 670 * self.pd.bonus_count + 125000
        self.next_player()
        self.assertEqual(125000, self.pd.get("bonus_held", 125000))
        self.next_player()
        self.assertEqual(held, self.pd.bonus_held)

    def test_the_extra_ball_road_is_per_player(self):
        """adj 83: each player lights their own extra ball once (flag 0x15)."""
        self.set_adj(83, 1)
        self.start_game()
        self.start_battle()
        self.assertEqual([1, 0, 0, 0], self.tf.eb_lit)
        self.next_player()
        self.start_battle()
        self.assertEqual([1, 1, 0, 0], self.tf.eb_lit)

    def test_scores_and_progress_do_not_mix(self):
        self.start_game()
        self.complete_energon()
        self.shoot("bumblebee")
        one = (self.pd.energon_sets, self.pd.bb_letters, self.pd.allspark_lit)
        score = self.score
        self.next_player()
        self.assertEqual((0, 2, 0), (self.pd.get("energon_sets", 0), self.pd.bb_letters,
                                     self.pd.get("allspark_lit", 0)))
        self.shoot("left_ramp")
        self.assertEqual(score + self.game.player_list[0].score - score, self.game.player_list[0].score)
        self.assertGreater(self.game.player_list[0].score, self.game.player_list[1].score)
        self.next_player()
        self.assertEqual(one, (self.pd.energon_sets, self.pd.bb_letters, self.pd.allspark_lit))

    def test_a_multiball_of_player_one_leaves_player_two_a_clean_ball(self):
        self.start_game()
        self.start_megatron_multiball()
        self.wait(12)
        self.settle()
        self.next_player()
        self.assertEqual(2, self.game.player.number)
        self.assertEqual(1, self.game.balls_in_play)
        self.check_fresh_ball()
        self.check()


class TestFourPlayers(BenchCase):
    PLAYERS = 4

    def test_every_player_plays_every_ball(self):
        self.start_game()
        order = []
        while self.game:
            order.append((self.game.player.ball, self.game.player.number))
            self.shoot("left_ramp")
            self.check(settled=False)
            self.end_ball()
            self.plunge()
        self.assertEqual([(ball, player) for ball in (1, 2, 3) for player in (1, 2, 3, 4)], order)
        self.wait(15)
        self.settle()
        self.check()
