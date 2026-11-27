# Attract: the pages of deff 1 (code)

Agent A, 2026-11-26, from the decompile (`rom/code/tf_decompiled.c`) and the page functions run as ROM code
(`rom/tools/attract_pages.py`). Ticks are OS ticks (16.0 ms). Fact tags: **code** unless said. Machine-readable:
[`rom/rom_data/dmd/attract_pages.json`](../../rom_data/dmd/attract_pages.json) (table, conditions per state and
pass, lengths, every text with its call site, msg, format, values and source) and one op list per page,
`rom/rom_data/dmd/deff_ops/deff_001__page<NN>[_<state>].json`.

## The walk

`deff_001_game_over` [0x0103c584] walks the page table at **0x00030d10**: 39 entries of (condition, page),
ended by a page of 0. The table is static data in the ROM image (file 0x30d10); nothing writes it at start-up
(the same bytes before and after the boot run). For entry i it calls `condition(pass)` (an entry with no
condition always passes); when it passes, it allocates the page pair, creates the page as a child task
(`task_create_same_id_ac20(page, 0, 0x300)`) with the pass at task +0x30, and sleeps 1 tick at a time until the
page task has ended (`task_count_b3b0`) or the right flipper goes on (`bits_changed_on_68b4(.., 2)`): next
entry. The left flipper (bit 1) goes back one entry (one pass back before entry 0). After the last entry, the
pass counts up. Each page is killed with the deff's children (`task_kill_own_children_ade4`) before the next.

So the next page starts one tick after a page ends: a page of n ticks takes n + 1 in the cycle. Run as ROM code
at factory settings (`schedule_factory` in the JSON): pass 1 lasts **2,528 ticks (40.4 s)**, from GAME OVER
(tick 0), CREDITS (127), REPLAY AT (254), the ten high scores (381 to 1,524, 127 apart), the two combo
champions (1,651, 1,778), the logo scroll (1,905), the image animation (2,139), LEARN MORE (2,401); passes 2 and
up skip GAME OVER and last **2,401 ticks (38.4 s)**.

## The table

| # | condition | page | shown when | length (ticks) |
|---|---|---|---|---|
| 0 | `is_one_c20` [0x01000c20] | `draw_game_over` [0x01000c30]: msg 0x1db GAME OVER | pass 1 only | 126 |
| 1 | none | `credits_screen_120` [0x01000120]: `credits_text_44a4` [0x000044a4] (CREDITS n, FREE PLAY, partial credits msgs 0x284-0x286) | always | 126 |
| 2-5 | 0x000270ec + 0x20 k: `check_task_29_1c174(k + 1)` [0x0001c174] | 0x01000c00 + 8 k -> [0x01000af4] (decompile name `attr_page_last_score`, but it is the replay page): `adj_replay_award_1c21c(buf, k + 1)` [0x0001c21c], REPLAY AT / the score | in attract, replay level k + 1 is set (`adj_replay_levels_adj_get_1c07c` [0x0001c07c]: adj 14 REPLAY LEVELS, adj 11 REPLAY TYPE; factory: level 1 only, 20,000,000) | 126 |
| 6-10 | `hstd_show_2_k` [0x010004d4 + 0x60 k] | 0x01000aac - 0xc k -> [0x01000894](2, k): AUTOBOT high scores, grand champion then #1-#4 | `hstd_entry_if_allowed_186d0(2, k)` [0x000186d0]; with a tournament of type 4, only on passes divisible by 5 | 126 |
| 11-15 | `hstd_show_3_k` [0x010006b4 + 0x60 k] | 0x01000ae8 - 0xc k -> [0x01000894](3, k): DECEPTICON high scores | same, table 3 | 126 |
| 16 | 0x010027c4: `hstd_entry_if_allowed_186d0(4, 0)` | `draw_02lu_combo_p1_s` [0x010027e0]: COMBO CHAMPION, initials, msg 0x6e0 n COMBOS | always at factory | 126 |
| 17 | 0x01002958: table 5 entry 0 | `draw_p1_double_triple_u` [0x01002974]: BEST COMBO CHAMPION, initials, msg 0x6e1 n-WAY | always at factory | 126 |
| 18 | `tournament_state_1_27670` [0x00027670] | `draw_prize_pool` [0x000276a8] | tournament type 4, record +0x2c == 1 | 127 |
| 19 | `tournament_type_is_4_277d0` [0x000277d0] | `tournament_time_screen_277e8` [0x000277e8]: days left | tournament type 4 (draws only while it runs and the clock reads) | 127 |
| 20 | 0x00027558 | `draw_tournament_font_height_27570` [0x00027570]: msgs 0x4bb, 0x4bc | tournament type 4 | 127 |
| 21-25 | `tournament_level_1..5` [0x000273cc, 0x00027418, 0x00027468, 0x000274b8, 0x00027508] | [0x00027400, 0x00027450, 0x000274a0, 0x000274f0, 0x00027540]: each level's leader and score | type 4 and more than k levels (+0x31) | 127 |
| 26 | `tournament_active_27270` [0x00027270] | `draw_bump_n_win_score` [0x000272a8] | type 4, bump 'n win (+0x28 == 0) | 127 |
| 27 | `tournament_started_27a3c` [0x00027a3c] | `tournament_level_screen_27a70` [0x00027a70]: TOP n SCORES WIN / PRIZES (blinking) | type 4, +0x2c != 0 | 127 |
| 28 | 0x00027e2c: `tournament_1ec8c` [0x0001ec8c] | `tournament_title_screen_27e40` [0x00027e40]: CURRENT WINNERS | a past tournament (type 2) | 127 |
| 29-33 | 0x00027c3c ... 0x00027dc8 | 0x00027c64 ... 0x00027df4: the past tournament's leaders | the past one had more than k levels | 127 |
| 34 | none | `attr_page_logo_scroll` [0x010001e4]: image 0x59a scrolled from y 32 up, 1 dot per 2 ticks | always | 233 |
| 35 | none | `anim_images_226c_cd0` [0x01000cd0]: the 128 images 0x226c-0x22eb, 2 ticks each, then 2 ticks | always | 261 |
| 36 | none | `draw_learn_more_about_font_height_3e4` [0x010003e4]: msgs 0x360-0x362, font per language (0x040c5ba4) | always | 126 |
| 37 | 0x0002b0f0: `mov r0, #0` | `draw_clock_not_set` [0x0002b0f8] | **never** | (126) |
| 38 | `adj_custom_message_260` [0x01000260] | `error_text_screen_28c` [0x0100028c]: the custom message, one line per `\n` | adj 2 CUSTOM MESSAGE = ON and a message: NVRAM 0x02110040 (with its flag 0x02110081 and ~sum8 at 0x02110082) or the region message `region_msg_55c0` [0x000055c0] | 126 |

Every page that calls `draw_way_palette_identity_2f200` [0x0102f200] (0, 1, 2-17, 36, 38) also draws the
**left panel** on its bg page (x < 41, separator at x = 40): in attract no player is up, so it prints the
scores of the last game, one line per player of `num_players` [0x0001a94c] (0x02110900), each
`player_score_1cacc(n)` [0x0001cacc] (0x021109e4 + 4 (n - 1)) through msg 0x502 `%,02lu`, plus the combo
counters (msgs 0x6d1-0x6d3). The `_last_game` op lists show it with 2 players.

## States the pages were run in

The values are test inputs written to NVRAM the way the ROM stores them, after the ROM's own factory resets
(`error_log_530_all_728` [0x00000728], `factory_reset_game_265e8` [0x000265e8], `high_score_tables_init_190bc`
[0x000190bc]): `factory` (credits 0, no last game: the default high score table OPT 75,000,000, JAZ, PWL, IRN,
BEE; MEG 75,000,000, STR, SND, SHK, BLK; combo LON 20 and 5-WAY), `credits` (3), `free_play` (adj 34 YES),
`replays` (adj 14 = 4: 20, 40, 60, 80 million), `last_game` (2 players, 12,345,670 and 3,456,780),
`custom_msg` (WELCOME / TO THE ARCADE), `tournament` (record 0 of type 4 started now for 30 days, 5 levels, and
a past record of type 2). `tournament_2c000` [0x0002c000] turns a type 4 record into type 2 once its start
(+0xfc) plus its length (+0x10c) has passed, every 62 ticks; so a tournament record needs an end in the future
to stay current.
