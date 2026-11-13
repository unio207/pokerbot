# STATE: hand-off from sequoia-launch to mid-round-iterate

Updated: 2026-11-12 19:03 (T+50), during the Pittsburgh regional. Clock: T+0 = 18:13 (portal
`variant_announced_at` 23:13:58Z). Round 1 snapshot at T+60 = 19:13. Machine: MacBook M5, kit
at `../starter-kit` (its `.venv`, Python 3.12); build machine synced by `rsync`, kit at
`~/work/starter-kit`.
Repo: `main`, **nothing committed since `2f9741d`**: the conversion is in the working tree
(`tools/core_agent.py`, `bots/`, `tools/field_report.py`, `skills/sequoia-launch/scripts/gate.py`,
`zoo/variants/double_board_turn_discard.md`). `v0/`, `v1/` and `rules_card.json` are ignored by git.
**Numbers below are from the organizers' kit unless a line says mini.**
Template: `sequoia-launch/templates/STATE.md`.

## Active bot

| Version | File | Uploaded at | Active | What it is |
| --- | --- | --- | --- | --- |
| v0 | `v0/agent.py`, 70,036 bytes | 18:20:31 (T+7:31), submission `7e4d8e8e` | no (rollback target) | the `final` profile, unconverted: scores board 1 only, lets the platform discard its lowest card |
| v1 | `v1/agent.py`, 73,246 bytes, sha256 `2df6cc1cf4e70d03...` | 18:30:54 (T+17:54), submission `920a2429` | no | `final` converted to Pittsburgh (this session's conversion) |
| v2 | `v2/agent.py`, 75,994 bytes | 18:43:35, submission `066139f9` | no | Vedaant's conversion (`db_*` functions, his v3a, branch `pittsburgh-v2`), uploaded by Henry; not built from this core |
| v3 | `v3/agent.py`, 73,364 bytes, sha256 `5f7235d541933e20...` | 18:52:04, submission `393c48a3` | no | v1 plus the looser preflop bundle; played practice 3 as a field test |
| v4 | `v4/agent.py`, 73,673 bytes, sha256 `11f2e107c0d62c6d...` | 18:58:00, submission `d55b4134` | no (rollback target; played round 1) | v1 plus the heads-up big-blind fix; `bots/final/agent.py` at `9daa6a9` |
| v6 | `v6/agent.py`, 73,890 bytes | 19:18:20, submission `0e986661`, uploaded by Henry | no | v4 plus a heads-up big-blind call of a non-committing raise (top 50%, price up to 0.40, at most 12% of the stack) |
| v7 | `v7/agent.py`, 73,759 bytes | 19:20:38, submission `10809172`, uploaded by Henry | no (rollback target) | v4 plus one line: the shover rule in `_call_all_in` (call only the top 13% against a seat that shoved over 30% of its hands) is off heads-up |
| v9 | `v9/agent.py`, 73,949 bytes, sha256 `aca48a9e070cd1b5...` | 19:29:05 (T+76), submission `fc9b02c4`, uploaded by Henry | no (rollback target; active 19:29 to 19:33, played no run) | v7 plus wider first-in raises in `final`'s `open` table: small blind 0.45 to 0.70, button 0.40 to 0.55, cutoff 0.28 to 0.33 |
| v11 | `v11/agent.py`, 74,862 bytes | 19:33:57 (T+80:57), submission `469e96f5`; not uploaded by the iterate session, four seconds after the file was built, no gate and no A/B at that time | no; played round 2 | v9 plus a first draft of the big-blind re-raises (`bb_reraise`: 0.35 heads-up, else `min(0.2, 0.45 x width)`, all-in up to 30 bb), a call with any pair in the big blind, heads-up call of an all-in of 10 bb or less with any ace, king or pair, and first in at 5 bb or less a 1.25 times wider shove with no completion |
| v90 | `v90/agent.py`, 45,312 bytes (the launch session's port of `zoo/claude_exploiter_1`, not built from this core) | 19:43:06, submission `f4025ac6`, uploaded by Henry for practice 6 | no | exploiter with Pittsburgh handlers; the relay session's Mac gate failed its timing (0.050% over 1 ms) |
| v13 | `v13/agent.py`, 73,996 bytes, sha256 `9c4bfd93aa77f46a...`, equal to `bots/final/agent.py` | 19:48:33 (T+95:33), submission `1b9ad55e`, uploaded by Henry | no (rollback target); played round 3 | v4 plus postflop only: flop and turn calls need 0.10 more strength and a draw alone calls at a price of 0.20 or less; `value_bet` 0.70, `medium_bet` 0.52, `cbet_air` 0.6; raise a flop or turn bet at strength 0.78. None of v7, v9, v11 or v12 is in it |
| v91 | `v91/agent.py`, 74,507 bytes, sha256 `46d14729ce9341ed...` (p2's build: v13 plus nine lines of lighter re-raises against one raise) | 19:56:16, submission `e140891a`, uploaded by Henry | no; played practice 7 | big blind 0.15, small blind 0.12, other seats 0.06, times 0.6 when the re-raise is a shove (30 bb or less), halved on the bubble |
| v17 | `v17/agent.py`, 75,006 bytes | 20:12:48, submission `20a9e4ae`, uploaded by Henry | no; played round 4 | v13 plus the endgame package: heads-up button raises or shoves 0.90, heads-up big blind reshoves the top half over a raise at 25 bb or less and calls an all-in of 10 bb or less with the top half, no survival discount and a 1.3 times shove range with three left, `points_tight` 0, shover rule off heads-up |
| v94 | `v94/agent.py`, 79,563 bytes, sha256 `eff252efdd50ff34...`, equal to `bots/final/agent.py` | 20:22:21 (T+129), submission `881d49d6`, uploaded by Henry | no; played practice 8 | v13 plus p2's `_cloned()` (v93 as of 20:20: first-in, all-in-call and re-raise frequencies of the ten best teams in round 1, by seat, players left and stack) plus the one-board lock rule of v18 (bet two pair or better on one board, top pair or better when two or fewer opponents; never fold trips or better on one board at a price up to 0.42; raise it with 0.72 average strength) |
| v96 | `v96/agent.py`, 79,712 bytes, sha256 `24c9125e626f7e2b...` (p2's "go crazy bot", built from the v94 file) | 20:31:12, submission `25276ffb`, uploaded by Henry | no; played round 5 | v94 with round 3's top-ten tables, `icm_scale` 0, `points_tight` 0, `bubble_margin` 0, `call_margin` 0.02, `push_scale` 1.1, and first-in and re-raise shares times 1.1 with three or fewer left. Gate PASS on the idle build machine (p2 at 20:29: p99 186 µs, 0 failed of 90; this session at 20:32: p99 185 µs, 0 bad of 20,000 fuzz states, 0 failed of 300) |
| v971 | `v971/agent.py`, 80,989 bytes, sha256 `ad2551c62fc741a9...` (p2's build, not in the core) | 20:45:55, submission `2f1d6444`, uploaded by Henry; uploaded again at 20:52:17 as submission `eb6caf1a` (same 80,989 bytes) | **yes: `eb6caf1a` played round 6** (no practice run took place after 20:31) | v96 with the preflop percentile from the measured three-card pot share (`pittsburgh_preflop`), no 1.1 multiplier, `call_margin` 0.05, `push_scale` 0.9, opens of 2.3 bb. p2's gate PASS (p99 185 µs, 0 failed of 90) |

Upload to ready: under 60 s both times (v1 was ready and active at the first portal read, 56 s
after upload; not timed more finely). Rollback target: v1, on the team page (the active switch, not a re-upload).

## Variant

Pittsburgh, kit name `double_board_turn_discard`, portal name `pittsburgh`. Ruleset:
`zoo/variants/double_board_turn_discard.md`. Rules Card: `rules_card.json`, from `probe.py` on
the kit plus `RULES.md`, `README.md`, `AGENTS.md` and the engine source.

- Three hole cards through preflop, flop and turn betting. Two boards; `state.board` is board
  1, `state.variant["boards"]` holds both.
- `discard` phase after turn betting when two or more players remain:
  `Action("discard", cards=(i,))`, `i` the index of the card thrown away. A failure discards
  the lowest card.
- Showdown per board with the two kept cards; each board wins half of every pot.
- Table settings equal the template: 8 players, 2,000 chips, 10/20, 20 hands per level, cap
  250, payouts 50/30/20, 1 ms, 100 ms bank, 64 KB.
- Side prizes (raw counts over scored rounds, no points): scoops and rivers seen. Not chased.

What the conversion is (`tools/core_agent.py`, the `double_board_turn_discard` entry, first in
`VARIANTS`):

- `detect`: `"boards" in state.variant`, so it holds whichever name the platform sends.
- `double_board_strength(hole, boards, facing)`: two cards scored per board with the hold'em
  code (`_pair_strength`, split out of `holdem_postflop`), averaged.
- `double_board_keep(cards, boards)`: the pair with the most strength summed over both boards.
  The discard handler throws away the third card; flop and turn strength is that pair's.
- Preflop: `discard_reveal_preflop` (three cards, best two), unchanged.
- `hand_rank` and `_draws` are memoised (`lru_cache`, 64 entries): three pairs share each
  board's rank. 4,096 entries made the garbage collector pause for 1 to 2 ms; keep it small.
- No mini-simulator class for this game. `--mini` plays hold'em: every measurement is on the kit.

## Knobs in the active version (`PROFILES["final"]`, `tools/core_agent.py`)

```python
track=True, adapt=frozenset({"steal", "shover", "station", "minraise"}),
steal_widen=1.15, steal_any=0.85, cbet_air=0.3, vs_shover="doc",
icm_scale=1.0, cap_aware=True, open_size=2.3, semi_bluff=0.3,
call_margin=0.05, bubble_margin=0.08, push_scale=0.9, points_tight=0.08,
threebet=0.03, call_raise=0.08,
```

Unchanged from before the event. Everything else comes from `_BASE` (`value_bet=0.80`,
`medium_bet=0.60`, `call_edge=0.12`, `post="basic"`). The 13 float knobs are repeated in
`SETTINGS`, applied last: change a knob there.

## Gate

`gate.py bots/final --tables 30`, runner kit, SDK kit, card `rules_card.json`: **GATE: PASS** on
both machines, on the file that is v1 (table below) and again on v4 (build machine: p50 137 µs,
p99 191, p99.9 211, max 288, 90 kit tables with 0 failed decisions). `gate.py` now deals a second board into
`state.variant["boards"]` when the card shows a two-board game; before that its fuzz and timing
never reached the new code.

| Check | Mac | Build machine |
| --- | --- | --- |
| fuzz legality, 20,000 states | 0 bad | 0 bad |
| hidden exceptions, 10,000 clean states | 0 | 0 |
| timing, 20,000 decisions, µs | p50 64, p99 88, p99.9 99, max 117 | p50 137, p99 193 (allowed 250), p99.9 212 (allowed 500), max 249 |
| kit tables | 90 over 3 line-ups, 0 failed | 90 over 3 line-ups, 0 failed |

Memory: largest blob 96 bytes (allowed 16,384). `agent.py` 73,246 bytes, import 0.010 s. The
upload-test imitation is skipped on the kit (its `play` always gives the time bank).

Failed decisions under load: the gauntlet (5 kit jobs at once on the Mac) logged 3, 2 and 2
failed decisions in three runs, each time on one bot only and once on v1 while the candidate
had 0. The one that could be located replayed with 0 failures alone, twice. The platform
logged 0 missed of 416,771. Treat a handful in a gauntlet as load, and a failure in `gate.py`
(which plays its tables alone) as real.

## Gauntlet baseline

`gauntlet.py bots/final --vs v0 --tables 100`, runner kit, 5 jobs, payouts 50/30/20, nine
line-ups, n = 900 tables per bot per seed. Par is 12.5.

| Seed | v1 | v0 | v1 minus v0 |
| --- | --- | --- | --- |
| `convert` | 25.17 ± 0.27 | not recorded | +2.42 ± 0.69 |
| `convert2` | 26.89 ± 0.71 | 23.31 ± 0.46 | +3.58 ± 0.74 |

Seed `convert2` by line-up (n = 100 tables per bot per line-up):

| Line-up | v1 | v0 | Difference |
| --- | --- | --- | --- |
| mixed field | 33.30 ± 2.51 | 29.50 ± 2.39 | +3.80 ± 1.70 |
| passive field | 40.40 ± 1.36 | 35.80 ± 2.11 | +4.60 ± 2.22 |
| aggressive field | 30.20 ± 1.42 | 29.50 ± 1.34 | +0.70 ± 1.20 |
| seven starters | 26.80 ± 1.65 | 19.60 ± 0.86 | +7.20 ± 1.44 |
| four of you, four starters | 17.77 ± 0.49 | 16.60 ± 0.50 | +1.18 ± 0.65 |
| zoo field 1 | 16.30 ± 2.00 | 18.10 ± 1.99 | -1.80 ± 2.49 |
| zoo field 2 | 27.00 ± 1.73 | 18.90 ± 1.21 | +8.10 ± 1.48 |
| zoo field 3 | 31.70 ± 1.44 | 29.00 ± 1.65 | +2.70 ± 1.90 |
| zoo field 4 | 18.50 ± 1.84 | 12.80 ± 1.75 | +5.70 ± 2.16 |

**v4, the active version, against v1** (`gauntlet.py v4 --vs v1`): 28.08 ± 0.25 against 26.31 ± 0.33,
+1.77 ± 0.25, positive in all nine line-ups (seed `hu1`, n = 2,700 per bot); 27.79 ± 0.58 against
26.43 ± 0.68, +1.36 ± 0.28 (seed `hu2`, n = 900). The number a candidate has to beat is v4's.

v1 as the incumbent in two earlier runs, n = 2,700 tables: 26.83 ± 0.23 (seed `river1`) and
26.94 ± 0.27 (seed `bet1`).

Speed: 1,200 tables per minute on the Mac (kit, 5 jobs). `--tables 300` for both bots takes
3.7 minutes and gives a standard error of 0.20 to 0.23 on the difference. Detectable at 2.8
standard errors: 1.06 points in 5 minutes, 0.75 in 10, 0.43 in 30.

Promotion rule in force: difference over all line-ups above 2 standard errors on one seed and
still positive on a fresh seed; `gate.py` PASS.

Before the event, mini simulator, hold'em, for reference only: `final` 24.55 ± 0.19 against
`starter` 18.99 ± 0.16 (n = 9,000). Not comparable with the kit numbers above.

## Tried during the build and not shipped

| Change | Result against v1 (kit, n = 2,700 per bot) | Decision |
| --- | --- | --- |
| River strength refit to measured pot share (`-0.152 + 1.195 x strength`) | -0.14 ± 0.23, seed `river1` | reverted |
| `value_bet` 0.80 to 0.70 and `medium_bet` 0.60 to 0.52 | +0.31 ± 0.20, seed `bet1`; mixed field -1.93 ± 0.64, seven starters +1.50 ± 1.07 | reverted; candidate, needs more tables |
| Looser preflop bundle (v3): `threebet` 0.06, `call_raise` 0.14, `hu_open` 0.80, `points_tight` 0.03, `bubble_margin` 0.04, opens x 1.25 | -1.49 ± 0.40, seed `loose1`; negative in eight of nine line-ups. Measured with the big-blind bug still in | reverted; re-measure piece by piece on v4 |
| Vedaant's conversion (v2) in place of this one | +0.07 ± 0.35, seed `ved1`. Timing on the Mac p99 250 µs against 88 (no memo) | not adopted; ideas to port one at a time |
| `hu_open` 0.65 to 0.80 on v4 (`v5/`) | -0.17 ± 0.23 against v4, seed `huopen1`; zoo field 1 -2.03 ± 0.67, aggressive field +0.70 ± 0.22 | dropped |
| v6: heads-up big-blind call of a small raise | -0.20 ± 0.26 against v4, seed `hubb1`; zoo field 4 -1.90 ± 0.89 | not promoted; uploaded as a field test |
| v7: shover rule off heads-up | -0.12 ± 0.19 against v4, seed `hushove1`; 0.00 ± 0.00 in zoo fields 2 and 3 (never fires), zoo field 4 -1.37 ± 0.52. Gate PASS on the build machine: p99 190 µs, 300 kit tables, 0 failed | below the promotion rule; active from 19:20 on Henry's upload, on the histories (we fold 80.2% of heads-up button all-ins, n = 9,604; our chip share when calling 0.557 at a price of 0.40 to 0.45) |
| v8: wider first-in raises on v4 (the `open` line of v9) | +0.35 ± 0.21 against v4, seed `steal1`; zoo field 4 +1.47 ± 0.76, zoo field 3 -0.70 ± 0.63 | 1.7 standard errors; shipped as v9 (v7 plus this line). v9 gate PASS on the build machine: p99 194 µs, 300 kit tables, 0 failed |
| v9 against v7 (fresh seed for the opens) | +0.13 ± 0.22, seed `steal2`, n = 3,600 per bot | positive on both seeds, neither above 2 standard errors |
| v11 against v9 | -0.39 ± 0.34, seed `bbrr1`, n = 2,700 per bot (run under another session's load, 1,036 tables per minute); mixed field -1.37 ± 0.62, passive field -2.00 ± 1.02 | measured after it was already active in round 2 |
| v12 against v9 (v11 with low pairs folding deep, wider re-raises all-in only to 20 bb, heads-up 0.45) | +0.32 ± 0.32, seed `bbrr2`; zoo fields 1 to 3 +1.30 to +1.60 | not uploaded: it sits on the preflop changes that scored 11.64 in round 2. Core changes saved as a patch in the session scratchpad |
| **v13 against v4** (postflop only) | **+1.88 ± 0.27**, seed `post1`, n = 2,700 per bot, positive in all nine line-ups (zoo field 4 +4.53 ± 0.77, seven starters +4.07 ± 0.78, zoo field 1 +3.03 ± 0.72). Gate PASS on the build machine at 19:44: p99 189 µs, 0 bad in 20,000 fuzz states, 300 kit tables with 0 failed. Frequencies on 3,000 sampled spots, v4 to v13 (top five): flop bet as the raiser 50 to 76% (74), fold to a 2/3-pot flop bet 25 to 46% (51), turn 17 to 36% (43), raise when bet into 0 to 5-7% (5) | uploaded as v13 for round 3 |
| v14 (v13 plus the steal switch in `_steal`) | +0.16 ± 0.29 against v13, seed `farm1` | parked: flat, and the histories say weak bots call more, not fold more |
| v91 against v13 | -0.20 ± 0.28, seed `rr1` | flat on the kit; +0.47 on the platform (practice 7 against round 3) |
| v15: `open_size` 2.0 on v13 | +0.44 ± 0.33, seed `size1` | not confirmed |
| v16: `threebet` 0.08 and `call_raise` 0 on v13 | -1.92 ± 0.47, seed `rrfold1`; passive field -5.03, mixed -3.83 | dropped |
| v17 against v13 (place counts, `places.py` in the scratchpad, seed `end1`, n = 2,700) | 29.29 against 29.78 points; firsts 41.3% against 42.5%; heads-up wins 68.0% both | the kit cannot test the endgame: its opponents lose heads-up anyway |
| **v18: one-board lock rule on v13** | **+0.86 ± 0.30**, seed `lock1`, positive in seven of nine line-ups | in v94 |
| v19 (v13 plus lock, endgame, blind re-raises, small blind 0.75) | first build-machine gate failed under p2's load (p99 392 µs); not re-gated | superseded by v94 |
| Head to head, 300 kit tables, two seats per version (our bots against each other, not the field) | v93 16.43 points and 23.0% firsts, v19 13.35 and 15.5%, v18 11.25 and 6.7%, v13 8.97 and 4.8%. With v94: v94 15.03 and 19.0%, v93 13.63 and 16.2%, v19 12.40 and 10.3%, v13 8.93 and 4.5% | v94 uploaded. Its gate on the idle build machine: PASS, p99 199 µs, 0 bad of 20,000 fuzz states, 0 failed of 300 kit tables |
| v94 against v13, nine line-ups | -0.27 ± 0.32, seed `clone1`: zoo field 1 +4.43 ± 0.79, seven starters +2.93 ± 1.02; passive field -4.83 ± 1.74, zoo field 2 -2.87, mixed -2.80, zoo field 3 -2.60 | better against strong bots, worse against callers; the platform said +1.9 |
| Predictor (`predict.py` in the scratchpad): the candidate in the eighth seat against v94, v17, v91, v13, v4, v7, v11, a line fitted from their kit points to their platform scores (fit error 0.2 to 0.4, valid to about 15) | v96 15.2 and 15.1, v95 15.0, v970 14.8, v971 14.8, `wild` 1.25 / 1.5 / 2.0 on v96: 15.2 / 15.3 / 14.8, v103 (wild 1.5, all-in calls 1.4 times wider, `cbet_air` 1.0, `semi_bluff` 0.7, `value_bet` 0.62, `medium_bet` 0.45) 15.8 | v96's real round 5 score was 15.37. More aggression flattens out near 15 to 16 |
| Head to head, 900 kit tables, two seats per version | v971 13.64 ± 0.35, v96 13.11 ± 0.32, v103 12.77 ± 0.27, v94 10.48 ± 0.25; v971 minus v96 +0.54 ± 0.60. Earlier: v970 14.01 ± 0.32, v96 12.99 ± 0.35, v103 12.18 ± 0.45, v94 10.82 ± 0.34. v96 against v95 on 1,500 tables: +0.41 ± 0.40; v95 against v94 +1.88 ± 0.44 | no kit evidence separates v971 from v96 |
| Preflop refit from Monte Carlo | not run as an A/B: the borrowed fit is within 0.004 of the measured share in the top seven deciles and 0.016 to 0.022 low in the bottom two | not worth a window |

Monte Carlo behind those (heads-up, both hands keep the pair the bot keeps, scripts in the
session scratchpad, not in the repo): preflop n = 800,000; postflop n = 400,000 per street.
Flop and turn strength is within 0.04 of the real pot share in every decile. The river
overrates weak hands (predicted 0.30 is 0.18, 0.37 is 0.29) against a random hand, yet
correcting it did not score.

## Practice runs and rounds

| Run | Time | Bot | Decisions | Missed | Restarts | Errors | Points, place |
| --- | --- | --- | --- | --- | --- | --- | --- |
| practice 1 | 18:34:34 | v1 | 416,771 | 0 | 0 | none | 15.95 ± 0.68, 32nd of 82 that played; 1st 11.4%, 2nd 22.3%, 3rd 17.8% |
| practice 2 | 18:45:01 | v2 | 803,861 | 0 | 0 | none | 14.47 ± 0.45, 43rd of 100; 1st 7.5%, 2nd 23.3%, 3rd 18.6% |
| practice 3 | 18:54:04 | v3 | 1,551,886 | 0 | 0 | none | not read |
| practice 4 | 19:04:02 | v4 | 1,509,669 | 0 | 0 | none | 13.06 ± 0.17 over 10,479 tables; 1st 9.9%, 2nd 15.4%, 3rd 17.4%, out of the points 57.3% (our own read of the download) |
| round 1 (weight 1) | 19:14:02 | v4 | 2,888,728 at 19:27 | 0 | 0 | none | 12.40 ± 0.23 (margin, about 2 standard errors) over 20,000 tables, 67th of 109, field median 13.04, 1st 9.2% (results endpoint: `portal.get("tournaments/<run id>/results")`) |
| practice 5 | 19:24:11 | v7 | 703,480 | 0 | 0 | none | 11.73 ± 0.45 (margin, about 2 standard errors), 74th of 111, field median 12.95, 1st 8.0% (results endpoint) |
| round 2 (weight 2) | 19:34:08 | v11 | 2,816,064 | 0 | 0 | none | 11.64 ± 0.23 over 20,000 tables, 72nd of 111, field median 13.00, 1st 9.2%, 2nd 13.0%, 3rd 15.8% |
| round 3 (weight 3) | 19:55 | v13 | 2,302,312 at 20:03 | 0 | 0 | none | 12.31 ± 0.22 over 20,000 tables, 68th of 112, field median 13.30, 1st 7.8%, 2nd 16.4%, 3rd 17.4%. Vedaant on the first 10,000 tables: fold to a flop bet 48.3% (was 25), turn 38.4% (was 22), flop bets as the raiser 75.5%, raises when bet into 4.7% |
| practice 7 | 20:06:46 | v91 | 1,327,755 | 0 | 0 | none | 12.78 ± 0.32 over 10,000 tables, 60th of 112, field median 13.01, 1st 7.8%, 2nd 17.9%, 3rd 17.6% |
| round 4 (weight 5) | 20:15:05 | v17 | 2,673,318 | 0 | 0 | none | 13.04 ± 0.24 over 20,000 tables, 59th of 112, field median 13.12, 1st 11.2%, 2nd 12.7%, 3rd 18.1% |
| practice 8 | 20:26:12 | v94 | 1,284,050 | 0 | 0 | none | 14.90 ± 0.38 over 10,000 tables, 37th of 112, field median 13.31, 1st 17.3%, 2nd 12.6%, 3rd 12.4%. Vedaant: heads-up win 57.9% (was 33.5%), big blind at 5 to 8 players -1.71 per table (was -3.57) |
| round 5 (weight 8) | 20:35:22 | v96 | 2,421,407 | 0 | 0 | none | 15.37 ± 0.28 over 20,000 tables, 21st of 112, field median 13.24, 1st 20.0%, 2nd 11.1%, 3rd 10.2% (p2's read; health from the portal). Standings after it: 48th, total 260.8 = 12.40 + 2 x 11.64 + 3 x 12.31 + 5 x 13.04 + 8 x 15.37, so the weights are fibonacci whatever the portal's weight field says |
| round 6 (weight 13) | 20:55:51 | v971 (`eb6caf1a`) | 480,781 at 20:58, still running | 0 | 0 | none | not out at 21:00 |
| practice 6 | 19:45:01 | v90 | 726,640 | 0 | 0 | none | 11.02 ± 0.50 over 5,000 tables, 75th of 112, field median 13.37, 1st 13.8%, 2nd 7.2%, 3rd 9.9% |

Health columns are from `portal.py`. Points and places are Vedaant's, from the hand histories
(relayed, not re-derived here). Practice 1 had 146 entries, 64 forfeits, 2,500 tables; the runs
grow (5,000, then 10,000 tables). Field read from practice 1 and 2: the top teams win about a
third of their tables, play 19 to 32% of hands and fold to raises 67 to 81%; we played 15 to
16% and folded 88 to 89%, all of it with the big-blind bug below.

## Known weaknesses

- Practice 4, v4, from the history (`hand-history/practice4/`, 169 MB, 1,571,390 hands): heads-up on
  the button it raises 67.8% and folds 27.4% (n = 30,979; the fold rate was 75% before the fix).
  Heads-up in the big blind it folds 49.0%, calls 12.6% and raises 4.7% (n = 30,567): the next
  place to look. 9.9% firsts against about a third for the top teams. Scores are not comparable
  across practice runs: forfeits fell from 64 to 39, so fewer dead seats.
- Fixed in v4, present in v0 to v3: `_big_blind_seat` took the last `blind` event, but heads-up
  the kit posts the big blind first (small blind last in 13,786 of 13,967 heads-up hands in our
  kit histories). On the button heads-up the bot thought it was the big blind, so `hu_open`
  never applied. Every heads-up or tightness measurement before v4 is suspect.
- A big blind all-in for less than the small blind still picks the wrong seat (rare).
- Every strength number is hold'em's, averaged over two boards. Thresholds (`value_bet`,
  `medium_bet`, `call_edge`, the 0.88 raise) were tuned for one board; averaged strength
  reaches 0.80 rarely (top flop decile averages 0.74), so the bot value-bets less than in
  hold'em.
- The draw flag is true with a draw on either board, though that draw wins half a pot.
- Before the discard the hand is scored as the pair it would keep now; the option to choose
  after the turn is not priced.
- Opponents hold three cards and keep their best two: nothing models that their ranges are
  stronger than hold'em ranges.
- Timing headroom on the build machine: p99 193 of our 250 µs margin. Anything that adds work
  per pair or per board needs `gate.py` there first.
- `zoo field 1` (the strong `claude_*` bots) is the one line-up where v1 did not beat v0
  (-1.80 ± 2.49, n = 100).
- `tools/field_fit.py --sweep` and `tools/bench.py` play the mini simulator, which cannot
  deal this game: use `gauntlet.py bots/final --vs v1` on the kit for every decision.
- `tools/field_report.py` reads the download format now, but its hand types and advice were
  set on hold'em: "maniac" and "station" trigger easily with three-card ranges, shown hands are
  the kept pair, and filler seats count like scored seats.
- `probe.py` on the kit needs `TMPDIR=/tmp` (bots run with a clean environment, so the probe
  bot writes to `/tmp`). It rewrites `rules_card.json`: the hand-filled fields would be lost.
- `_icm_me` prices only the first three payout places.

## First experiments to try

Judge each on `gauntlet.py bots/final --vs v4` on the kit and on the share of 1st places in the
next practice run. Vedaant's ranked list (GitHub issues #12 and #13, branch `research/pittsburgh`):

0. Practice 3's and practice 4's results for v3 and v4: does the heads-up fix lift the 1st-place
   share (11.4% and 7.5% before)? Heads-up button fold rate was 75% against the field's 33%.
0. `hu_open` and `push_scale` again, now that the bug is fixed; then wider opens and `call_raise`
   one at a time; then `points_tight` and `bubble_margin` down.
0. His half-pot veto (`db_floor`: do not fold a hand that is near the nuts on one board to a big
   bet) and dropping the draw-only call. His v3a with both plus a calibration read +0.62 ± 0.27
   and +0.34 ± 0.31 against his own v1.
1. Henry, 18:25: port `zoo/claude_exploiter_1`'s postflop read into the core (PR #11's mock
   tournament on the mini simulator had it about 3 points per table ahead of `final` against
   the strong AI-written bots, hold'em). Judge it on the zoo line-ups' rows of
   `gauntlet.py bots/final --vs v1`, on the kit.
2. Hand histories: about 5,000 hands from the first practice run or round,
   `tools/field_report.py <file> --hero "Team Allow It"`. What the field is decides the rest.
3. The betting-threshold candidate (`value_bet` 0.70, `medium_bet` 0.52 in `SETTINGS`): rerun
   with `--tables 600` on a fresh seed. It lost in the mixed field and gained against starters,
   so check the field report first.
4. `call_edge` and `points_tight` if the field is strong; `steal_widen` if it is weak.

## What moved the score, and what to do first next time (p2, the launch session, 21:10)

Round 6 (`268dab24`, multiplier 13) finished at 21:05:06 with `eb6caf1a` (the v971 file): 2,510,126
decisions, 0 missed, 0 restarts. Its results were still held by the organizers at 21:05; the
standings showed five rounds (48th, 260.80; 40th 269.63, 30th 282.92, 20th 298.89, 5th 336.31).
The totals fit multipliers 1, 2, 3, 5, 8, 13 although the portal's `weight` field reads 1 to 6.

**The method that worked.** Stream the real hand histories (one file per run, about 150 MB) and
compare us with that run's ten best teams, spot by spot. Every finding below came from that;
none came from the kit gauntlet.

| Step | What the histories showed | Change | Platform result |
| --- | --- | --- | --- |
| 1 | Every calling line lost (a call of a raise outside the blinds -1.55 bb, a call of a flop bet after opening -1.07); the top ten re-raised 4.2% of hands, we 1.1% | v91: re-raise one raise with the top 15% / 12% / 6% (big blind, small blind, others) | 12.78 against v13's 12.31; -0.13 against the median, was -0.98 |
| 2 | The gap to first was all first places (9% against 26%); heads-up we won 38%, the top ten 65%, and folded the big blind two to three times as often | `_cloned()`: the top ten's measured preflop frequencies by players left, seats behind and stack depth, used as percentile thresholds | v94: 14.90, 37th, 17.3% firsts, heads-up 57.9% |
| 3 | By round 3 the top ten re-raised and called shoves far more than in round 1 and opened tighter; survival margins steer us to 2nd to 4th | v96: round 3's tables, `icm_scale`, `points_tight`, `bubble_margin` 0 | round 5: 15.37, 21st, 20.0% firsts, heads-up 65.0% (top ten 54.6%) |
| 4 | Our ranking (best two cards) is wrong by up to 12 points of equity: 9-9-2 is 0.603 not 0.721, A-K-Q 0.603 not 0.651, A-7-2 0.489 not 0.588 (12,000 deals each). Our opens lose 2.89 bb when re-raised, the top ten's 2.35 | v971: percentile from the by-class three-card fit (`pittsburgh_preflop`, `_PITT_MARKS`), opens of 2.3 bb | round 6, held |

**Still open after round 5** (us against that round's top ten, 4+ players): +9.4 against +11.3 bb per
100 hands. Re-raised after opening and continuing: +2.44 bb against +4.76 (that decision still runs
on the old code, not on a cloned rate). Reaching heads-up: 30.0% of tables against 35.0%. More
aggression is not the gap: the variants at 1.25 to 1.5 times the leaders' rates lost head to head.

**The kit gauntlet as a judge.** Its opponents go to showdown 20 to 90% of hands; real teams 8 to
13%. It scored v4 at 28 where the field scored it 12.4, and the one clean pair (v3 and v4, back to
back) was +0.57 on the platform against +3.3 predicted. Use it for crashes and timing only. A
finished run's scores are on `portal.get("tournaments/<id>/results")` within seconds.

**Side prizes** (scoops and rivers seen, raw counts): we are near the median on both (round 5:
1.82 scoops per table, 56th of 112; 8.89 rivers seen, 47th). One team sees 20 to 23 rivers per table.

**Where the analysis scripts are.** Not in the repo: in the launch session's scratchpad,
`/private/tmp/claude-501/-Users-zou-Desktop-pokerbot/a445c7bc-433c-41df-889a-4f7fbf35b113/scratchpad/`
(`freq2.py` frequency tables, `chipflow.py`, `opens.py`, `headsup.py`, `field_deep.py`, `prizes.py`).
The histories are in `hand-history/` (ignored by git). The cloned tables themselves are in
`v971/agent.py` (ignored by git) and, in their round 1 and round 3 forms, in the core's `_cloned()`.

## Log

- 2026-11-12 19:13 to 21:00, the six rounds (`mid-round-iterate`). What moved the platform score, in order: v13's postflop (fold flop and turn bets twice as often, bet thinner): level with v4 on points, calling lines fixed; v17's endgame package: firsts 7.8 to 11.2%, 13.04; p2's cloned preflop of the ten best teams plus the one-board lock rule (v94): 14.90, firsts 17.3%; the same with round 3's tables and the survival settings off (v96): 15.37, 21st of 112. What did not: wider opens, big-blind calls, heads-up tweaks one at a time, the exploiter port (11.02). The nine-line-up gauntlet read every preflop change as flat and was right only about postflop; the two tests that tracked the platform were a table of our own versions head to head and `predict.py` (a candidate against seven uploads with known platform scores). `tools/core_agent.py` and `bots/final` hold v971, the round 6 bot (`cmp` equal to `v971/agent.py`, `build.py --check` ok). Unplayed candidates left as ignored folders: v95, v97 to v103 (the `wild` multiplier variants; the v103 core is saved in the session scratchpad only), v970.

- 2026-11-12, session 1: launch skill written against a checkout 49 commits behind main;
  found when the zoo looked empty. Pulled to `8f76ac0`, re-based the skill on `bots/final`
  and the repo's tools, moved it to `skills/sequoia-launch/`, added the 12 weak zoo bots from
  the overnight branch. Nothing uploaded. Pre-written code is allowed (Henry, 2026-11-12).
  Still open: whether there is an upload command (assume the team page in a browser).
- 2026-11-12 16:20 to 16:40, readiness check: every command and identifier in the three
  skills cross-checked against the code. Two faults fixed. (1) `tools/core_agent.py` had no
  `SETTINGS` table, so `field_fit.py --sweep --bot bots/final` exited; ported from PR #10
  (same values as the profile: the `--seed parity` gauntlet was identical before and after,
  and `--seed baseline` reproduces 24.55 ± 0.19 against 18.99 ± 0.16). (2)
  `mid-round-iterate` promoted on `tools/bench.py`, which plays hold'em on the mini
  simulator only; it now promotes on `gauntlet.py --vs vN` and `gate.py`, with the launch
  skill's promotion rule and upload checklist. Gate re-run on the rebuilt bot: PASS. The
  mid-round commands were run once on the mini `irish` ruleset in a scratch copy; reading a
  real hand-history file is still untested. PR #10 stays open (shim path order, hiding
  `zoo/_template` in the practice page).
- 2026-11-12 16:38 to 17:06, dry run and build machine. A fresh agent followed
  `sequoia-launch` on the sealed `rehearsal` variant in a scratch copy (mini simulator as
  the kit). By its own clock: Rules Card at T+2:14, conversion at T+4:40, gate PASS at
  T+4:55, fresh-seed confirmation +2.82 ± 0.22 at T+5:36, `v1/` at T+5:55; then a network
  error cut it off before the hand-off stage. No command in the skill failed as written.
  Measured afterwards by the main session on what it left: build check ok; `GATE: PASS`, 0 failed
  decisions of 34,669, p99 42 µs; converted 26.13 ± 0.44 against unconverted `v0`
  23.29 ± 0.69, +2.84 ± 0.72 (n = 900 per bot, one seed). The build machine was synced to
  `96575d3` and passes the gate (numbers under "Gate"). The copy command in the skills is
  now `rsync` with excludes; `starter-kit/` is ignored by git; the skills' `PY=` line also
  finds a kit unpacked inside the repo.
- 2026-11-12 17:30 to 17:40, team portal read in Henry's Chrome (read-only). Team `Team Allow
  It`, 2 of 2 members, build box `pittsburgh-team-116` at the address in `~/.ssh/config`, 0
  submissions, no active bot, uploads closed until the announcement; 145 teams, 0 bots ready,
  0 rounds. The Format page matches the template Rules Card on every value. Getting started
  confirms `poker-agent play --seed`, and says the kit ships a hand-history sample and reader.
  The API key file exists locally. Not opened: Account settings, the portal's chat.
- 2026-11-12 17:55, portal API. The saved key can read the competition record, our uploads,
  health and the rounds list (`skills/sequoia-launch/scripts/portal.py`, read-only). The
  competition record for `Pittsburgh` says `round_weighting: "fibonacci"`, not the 1x to 6x of
  the Format page's default table: the late rounds weigh even more than planned for. Variant
  still null at 17:55. The organizers' setup skill is unchanged (version 2026-11-05.2). The
  public rules page still names Astra and Codex as the assistants teams may use; the portal's
  Getting started page names Claude Code as well.
- 2026-11-12 18:13 to 18:45, the launch (T+0 to T+32). Variant on the portal at 18:13:58.
  Kit installed on both machines; `v0` gated on the kit and uploaded at T+7:31. `probe.py`
  needed `TMPDIR=/tmp`. Conversion written at T+8: two helpers, a discard handler, a
  `VARIANTS` entry, no simulator class. Its first timing on the build machine was p99 250 µs
  for the scoring alone; a memo on `hand_rank` and `_draws` brought it to 165. Against `v0`:
  +2.42 ± 0.69 and +3.58 ± 0.74 on two seeds. `v1` uploaded at T+17:54, clean in practice 1
  (0 missed of 416,771). `gate.py` taught to deal two boards. `tools/field_report.py`'s reader
  fixed against the kit sample by a subagent (64 hands, 13 tables, equal to the kit's
  `read.py`). Two changes tried against `v1` and not shipped (table above). Someone else ran
  `gate.py bots/final` on the build machine at 18:23 while I was timing there.
- 2026-11-12 18:45 to 19:03 (T+32 to T+50). Henry uploaded Vedaant's bot as v2 (clean in practice
  2); it measured equal to v1 (+0.07 ± 0.35). The looser bundle went up as v3 for practice 3 as a
  field test while its A/B ran: -1.49 ± 0.40, reverted. Vedaant found the heads-up big-blind bug
  (issue #13); confirmed on our kit histories, fixed, v4 gated and uploaded at 18:58, +1.77 ± 0.25
  and +1.36 ± 0.28 against v1 on two seeds. `v0/` to `v4/` are ignored by git: `bots/final` in this
  commit is v4; v1 is v4 without the `_big_blind_seat` change; v3 is v1 with the bundle above.
