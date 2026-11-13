# Bot test battery, 2026-11-11

> **Written before the Pittsburgh regional (2026-11-12) and left as it was.** Mini-simulator
> hold'em results from 2026-11-11. `bots/final` here is the pre-event bot.
> `zoo/claude_exploiter_1` is in the repo now, so `--extra` is no longer needed; its port to the
> Pittsburgh variant scored 11.02 on the platform, our lowest run. What happened:
> [`pittsburgh-results.md`](../../docs/pittsburgh-results.md).

Thirty-four tests per bot on the **unofficial** mini simulator, no-limit hold'em. Produced by [`tools/bot_tests.py`](../../tools/bot_tests.py) and scored by [`tools/bot_tests_report.py`](../../tools/bot_tests_report.py); the raw decisions and tables are in `raw-2026-11-11.json.gz`.

Each score is 0-100 (100 = the target behaviour) and each grade is A >= 85, B >= 70, C >= 55, D >= 40, F below. The overall score is the unweighted mean of the 34. Scores are formulas over the metric shown beside them in the per-test tables; the formulas are our choice, so read the metrics, not just the grades.

Reproduce (about 6 minutes on 14 processes):

```bash
python3.12 tools/bot_tests.py run --out eval-results/bot-tests/raw-2026-11-11.json.gz --extra ../zoo/claude_exploiter_1
python3.12 tools/bot_tests.py reprobe eval-results/bot-tests/raw-2026-11-11.json.gz --extra ../zoo/claude_exploiter_1
python3.12 tools/bot_tests.py report eval-results/bot-tests/raw-2026-11-11.json.gz --json eval-results/bot-tests/scores-2026-11-11.json
```

`--extra` adds bots outside the repo; `zoo/claude_exploiter_1` was untracked when this ran and is not
committed here. `reprobe` re-runs only the probe, fuzz and static tests (seconds) into an existing raw file.

## Findings

Written by hand from the tables below. Regenerating the report replaces everything after this section.

1. **`bots/final` has the best overall score (76, with 19 A grades).** `bots/adaptive` scores 74, and
   `bots/steal_heavy`, `zoo/codex_rubric_pressure_icm_1` and `bots/icm_survival` score 70 each.
   `final` and `icm_survival` make the soundest decisions on the tests a solver can check. In heads-up
   push/fold, an opponent playing a perfect counter-strategy gains only 13 mbb/hand against them, 8% of
   combos are off equilibrium, and 87% of clear all-in decisions maximise chip EV. Their ICM bubble calls
   match exact ICM almost perfectly.
2. **`zoo/claude_exploiter_1` wins the games that matter most, but it is not in the repo.** It is untracked
   in the main checkout, and the earlier strategy tuning never saw it. In the out-of-sample league (varied
   rules, random payouts, all six variants) it scores 22.8 points against 16.1 for `icm_survival` and 15.5
   for `final`, and it leads in every variant, including hold'em (17.3 vs 16.1). It also wins 76% of
   heads-up matches; `final` wins 40% against it. Its edge comes from reading opponents: it calls a
   maniac's shoves 56% of the time against 15% for a nit (best response 60% / 3%), and opens 100% against
   blinds that always fold. On theory it is weaker: push/fold exploitability is 193 mbb/hand, against 13
   for `final`. Against the fixed sparring fields it scores 27.9 points, below `final`'s 32.3. It is also
   non-deterministic, because it draws from the global `random`.
3. **Gaps shared by almost every bot:**
   - **River bluffing:** 15 of 19 bots never bluff the river when checked to. Only `codex_rubric_pressure_icm_1`
     and `claude_shark_1` come near a balanced bluff ratio.
   - **Mixing:** only 4 bots ever play more than one action in the same spot.
   - **Reading shovers:** `final` calls 26% against a maniac's shoves and 26% against a nit's. The best
     response is 60% and 3%.
   - **3-betting:** BTN 3-bets 2-4% against a CO open; reference solver charts use about 10%.
4. **Bugs found:** `codex_adaptive_icm_1` and `codex_shove_aware_1` raise `IndexError` in `behind()`
   (`order[1]`) in 83 fuzzed states each; the platform would play check/fold there. `starter` and
   `claude_exploiter_1` are non-deterministic. There were no failed decisions in about 7.9 million
   decisions of simulated play, and no bot's decisions changed when hidden cards changed.
5. **Suggested next steps for `bots/final`:**
   - Per-seat shove-range estimation, so it calls wider against wide shovers. This is where
     `claude_exploiter_1` gains most.
   - Some river bluffs, at about a quarter of river bets.
   - A wider 3-bet range.
   - Compare against `claude_exploiter_1` before relying on `final` as the strongest bot.

## Overall

| rank | bot | overall | A | B | C | D | F |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `bots/final` | 76 | 19 | 4 | 4 | 3 | 4 |
| 2 | `bots/adaptive` | 74 | 18 | 5 | 3 | 2 | 6 |
| 3 | `bots/steal_heavy` | 70 | 15 | 5 | 5 | 4 | 5 |
| 4 | `zoo/codex_rubric_pressure_icm_1` | 70 | 12 | 7 | 7 | 1 | 7 |
| 5 | `bots/icm_survival` | 70 | 17 | 3 | 5 | 4 | 5 |
| 6 | `bots/equity_bucket` | 68 | 15 | 5 | 4 | 3 | 7 |
| 7 | `bots/chart_nash` | 68 | 16 | 4 | 4 | 3 | 7 |
| 8 | `zoo/claude_exploiter_1` | 65 | 13 | 5 | 1 | 9 | 6 |
| 9 | `bots/push_fold` | 64 | 14 | 5 | 2 | 4 | 9 |
| 10 | `zoo/codex_adaptive_icm_1` | 62 | 11 | 6 | 4 | 4 | 9 |
| 11 | `zoo/claude_shark_1` | 62 | 13 | 5 | 3 | 2 | 11 |
| 12 | `starter` | 62 | 11 | 6 | 5 | 4 | 8 |
| 13 | `zoo/codex_chip_ev_1` | 60 | 11 | 7 | 3 | 4 | 9 |
| 14 | `zoo/codex_steal_value_1` | 58 | 9 | 4 | 6 | 5 | 10 |
| 15 | `zoo/codex_survival_icm_1` | 57 | 10 | 4 | 6 | 4 | 10 |
| 16 | `zoo/claude_maniac_1` | 56 | 8 | 4 | 9 | 4 | 9 |
| 17 | `zoo/codex_shove_aware_1` | 55 | 9 | 5 | 4 | 6 | 10 |
| 18 | `zoo/claude_tourist_1` | 47 | 6 | 5 | 5 | 1 | 17 |
| 19 | `zoo/claude_grinder_1` | 45 | 11 | 0 | 2 | 3 | 18 |

## Score matrix

| test | final | adaptive | steal_heavy | codex_rubric_pressure_icm_1 | icm_survival | equity_bucket | chart_nash | claude_exploiter_1 | push_fold | codex_adaptive_icm_1 | claude_shark_1 | starter | codex_chip_ev_1 | codex_steal_value_1 | codex_survival_icm_1 | claude_maniac_1 | codex_shove_aware_1 | claude_tourist_1 | claude_grinder_1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hand equity | 91 | 91 | 91 | 78 | 91 | 94 | 91 | 99 | 91 | 90 | 88 | 91 | 82 | 78 | 95 | 89 | 90 | 92 | 97 |
| Expected value | 76 | 76 | 76 | 62 | 76 | 83 | 76 | 30 | 76 | 82 | 91 | 76 | 92 | 82 | 72 | 79 | 82 | 72 | 0 |
| Pot odds | 63 | 63 | 63 | 40 | 63 | 63 | 63 | 13 | 63 | 64 | 81 | 63 | 81 | 63 | 56 | 60 | 64 | 54 | 0 |
| Minimum defence frequency | 87 | 87 | 87 | 80 | 87 | 82 | 87 | 46 | 86 | 71 | 75 | 87 | 77 | 66 | 76 | 74 | 71 | 77 | 36 |
| Bluffing frequency | 0 | 0 | 0 | 81 | 0 | 5 | 0 | 0 | 0 | 0 | 62 | 0 | 0 | 23 | 0 | 0 | 0 | 20 | 0 |
| Value betting | 92 | 92 | 92 | 64 | 92 | 96 | 92 | 81 | 52 | 80 | 94 | 92 | 76 | 55 | 54 | 80 | 80 | 72 | 45 |
| Bet sizing | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 80 | 100 | 80 | 100 | 100 | 100 | 100 | 100 | 100 | 80 | 100 |
| Range construction | 50 | 50 | 50 | 89 | 50 | 50 | 50 | 50 | 28 | 50 | 81 | 50 | 50 | 46 | 32 | 50 | 50 | 60 | 16 |
| Preflop strategy | 66 | 67 | 72 | 57 | 66 | 67 | 67 | 47 | 59 | 67 | 57 | 62 | 66 | 59 | 53 | 67 | 67 | 23 | 60 |
| Postflop strategy | 80 | 82 | 88 | 76 | 65 | 83 | 68 | 54 | 52 | 71 | 91 | 66 | 63 | 67 | 48 | 63 | 56 | 56 | 46 |
| Position awareness | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 99 | 100 | 100 | 85 | 94 | 65 | 100 | 0 | 94 |
| Board texture | 100 | 100 | 100 | 100 | 40 | 40 | 40 | 0 | 30 | 100 | 70 | 40 | 40 | 100 | 70 | 60 | 40 | 70 | 100 |
| Opponent range estimation | 0 | 0 | 0 | 45 | 0 | 0 | 0 | 72 | 0 | 0 | 0 | 42 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Exploitability | 97 | 93 | 58 | 62 | 97 | 93 | 93 | 61 | 93 | 36 | 16 | 70 | 83 | 2 | 68 | 54 | 36 | 35 | 7 |
| GTO deviation | 82 | 74 | 54 | 64 | 82 | 74 | 74 | 44 | 74 | 51 | 39 | 62 | 73 | 34 | 63 | 54 | 51 | 29 | 31 |
| Regret minimisation | 97 | 94 | 73 | 75 | 97 | 94 | 94 | 76 | 94 | 56 | 26 | 82 | 90 | 24 | 82 | 59 | 56 | 21 | 10 |
| Mixed strategy | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 100 | 0 | 70 | 0 |
| Opponent adaptation | 40 | 30 | 37 | 37 | 0 | 0 | 0 | 52 | 6 | 30 | 10 | 13 | 0 | 40 | 0 | 0 | 0 | 0 | 0 |
| Bluff catching | 71 | 71 | 71 | 24 | 71 | 65 | 71 | 3 | 71 | 75 | 38 | 71 | 44 | 75 | 58 | 69 | 75 | 68 | 2 |
| Fold equity | 100 | 100 | 92 | 78 | 0 | 0 | 0 | 100 | 19 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| Stack depth | 92 | 88 | 76 | 84 | 92 | 88 | 88 | 72 | 88 | 76 | 67 | 80 | 86 | 41 | 58 | 74 | 76 | 12 | 65 |
| Multiway pots | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 29 | 100 | 29 | 100 |
| All-in decisions | 87 | 79 | 57 | 68 | 87 | 79 | 79 | 47 | 79 | 54 | 42 | 65 | 78 | 36 | 67 | 58 | 54 | 31 | 33 |
| Monte Carlo simulation | 61 | 51 | 53 | 37 | 59 | 49 | 52 | 47 | 45 | 55 | 49 | 33 | 26 | 55 | 34 | 16 | 46 | 34 | 44 |
| Self-play | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| Baseline opponents | 44 | 38 | 42 | 27 | 44 | 37 | 38 | 41 | 32 | 35 | 33 | 24 | 11 | 38 | 18 | 18 | 27 | 20 | 27 |
| Head-to-head | 61 | 59 | 60 | 60 | 57 | 59 | 60 | 76 | 55 | 54 | 14 | 52 | 53 | 43 | 46 | 54 | 52 | 28 | 8 |
| Variance and confidence | 100 | 100 | 100 | 0 | 100 | 100 | 100 | 100 | 100 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| Out-of-sample | 40 | 32 | 38 | 0 | 47 | 29 | 36 | 100 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Strategy consistency | 100 | 100 | 100 | 96 | 100 | 100 | 100 | 100 | 100 | 100 | 97 | 100 | 100 | 100 | 100 | 87 | 100 | 100 | 100 |
| Action legality | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| Game state integrity | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 0 | 100 | 100 | 100 | 100 | 100 | 100 | 0 | 100 | 100 |
| Information leakage | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| Tournament ICM | 100 | 98 | 60 | 98 | 100 | 98 | 98 | 88 | 98 | 100 | 100 | 73 | 58 | 69 | 99 | 58 | 100 | 56 | 99 |
| **overall** | **76** | **74** | **70** | **70** | **70** | **68** | **68** | **65** | **64** | **62** | **62** | **62** | **60** | **58** | **57** | **56** | **55** | **47** | **45** |

## Per test

### 1. Hand equity

AUC of continuing (call/raise) vs exact equity when facing flop and river bets.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_exploiter_1` | 99 A | AUC 0.95 |
| `zoo/claude_grinder_1` | 97 A | AUC 0.94 |
| `zoo/codex_survival_icm_1` | 95 A | AUC 0.93 |
| `bots/equity_bucket` | 94 A | AUC 0.92 |
| `zoo/claude_tourist_1` | 92 A | AUC 0.91 |
| `bots/push_fold` | 91 A | AUC 0.91 |
| `bots/final` | 91 A | AUC 0.91 |
| `bots/adaptive` | 91 A | AUC 0.91 |
| `bots/steal_heavy` | 91 A | AUC 0.91 |
| `bots/icm_survival` | 91 A | AUC 0.91 |
| `bots/chart_nash` | 91 A | AUC 0.91 |
| `starter` | 91 A | AUC 0.91 |
| `zoo/codex_adaptive_icm_1` | 90 A | AUC 0.90 |
| `zoo/codex_shove_aware_1` | 90 A | AUC 0.90 |
| `zoo/claude_maniac_1` | 89 A | AUC 0.90 |
| `zoo/claude_shark_1` | 88 A | AUC 0.89 |
| `zoo/codex_chip_ev_1` | 82 B | AUC 0.87 |
| `zoo/codex_rubric_pressure_icm_1` | 78 B | AUC 0.85 |
| `zoo/codex_steal_value_1` | 78 B | AUC 0.85 |

### 2. Expected value

River call/fold: EV lost per decision vs the best action, scaled so a coin flip scores 0.

| bot | score | measured |
|---|---:|---|
| `zoo/codex_chip_ev_1` | 92 A | 0.37 bb lost/decision (coin flip 4.51) |
| `zoo/claude_shark_1` | 91 A | 0.41 bb lost/decision (coin flip 4.51) |
| `bots/equity_bucket` | 83 B | 0.76 bb lost/decision (coin flip 4.51) |
| `zoo/codex_adaptive_icm_1` | 82 B | 0.79 bb lost/decision (coin flip 4.51) |
| `zoo/codex_shove_aware_1` | 82 B | 0.79 bb lost/decision (coin flip 4.51) |
| `zoo/codex_steal_value_1` | 82 B | 0.83 bb lost/decision (coin flip 4.51) |
| `zoo/claude_maniac_1` | 79 B | 0.93 bb lost/decision (coin flip 4.51) |
| `bots/final` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `bots/adaptive` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `bots/steal_heavy` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `bots/icm_survival` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `bots/chart_nash` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `bots/push_fold` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `starter` | 76 B | 1.08 bb lost/decision (coin flip 4.51) |
| `zoo/codex_survival_icm_1` | 72 B | 1.25 bb lost/decision (coin flip 4.51) |
| `zoo/claude_tourist_1` | 72 B | 1.26 bb lost/decision (coin flip 4.51) |
| `zoo/codex_rubric_pressure_icm_1` | 62 C | 1.72 bb lost/decision (coin flip 4.51) |
| `zoo/claude_exploiter_1` | 30 F | 3.17 bb lost/decision (coin flip 4.51) |
| `zoo/claude_grinder_1` | 0 F | 4.67 bb lost/decision (coin flip 4.51) |

### 3. Pot odds

River: share of clear call/fold decisions (|equity - required| >= 5%) on the right side of the price.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_shark_1` | 81 B | 91% right of 439 |
| `zoo/codex_chip_ev_1` | 81 B | 90% right of 439 |
| `zoo/codex_adaptive_icm_1` | 64 C | 82% right of 439 |
| `zoo/codex_shove_aware_1` | 64 C | 82% right of 439 |
| `bots/equity_bucket` | 63 C | 82% right of 439 |
| `zoo/codex_steal_value_1` | 63 C | 82% right of 439 |
| `bots/final` | 63 C | 81% right of 439 |
| `bots/adaptive` | 63 C | 81% right of 439 |
| `bots/steal_heavy` | 63 C | 81% right of 439 |
| `bots/icm_survival` | 63 C | 81% right of 439 |
| `bots/chart_nash` | 63 C | 81% right of 439 |
| `bots/push_fold` | 63 C | 81% right of 439 |
| `starter` | 63 C | 81% right of 439 |
| `zoo/claude_maniac_1` | 60 C | 80% right of 439 |
| `zoo/codex_survival_icm_1` | 56 C | 78% right of 439 |
| `zoo/claude_tourist_1` | 54 D | 77% right of 439 |
| `zoo/codex_rubric_pressure_icm_1` | 40 F | 70% right of 439 |
| `zoo/claude_exploiter_1` | 13 F | 56% right of 439 |
| `zoo/claude_grinder_1` | 0 F | 43% right of 439 |

### 4. Minimum defence frequency

Flop and river continue rate vs MDF = pot/(pot+bet) at five and four bet sizes.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 87 A | cont/MDF % f0.33:66/75 f0.5:59/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `bots/adaptive` | 87 A | cont/MDF % f0.33:66/75 f0.5:59/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `bots/steal_heavy` | 87 A | cont/MDF % f0.33:66/75 f0.5:59/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `bots/icm_survival` | 87 A | cont/MDF % f0.33:66/75 f0.5:59/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `bots/chart_nash` | 87 A | cont/MDF % f0.33:66/75 f0.5:59/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `starter` | 87 A | cont/MDF % f0.33:66/75 f0.5:59/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `bots/push_fold` | 86 A | cont/MDF % f0.33:66/75 f0.5:55/67 f0.75:41/57 f1:32/50 f1.5:40/40 r0.33:70/75 r0.5:62/67 r1:45/50 r2:36/33 |
| `bots/equity_bucket` | 82 B | cont/MDF % f0.33:82/75 f0.5:66/67 f0.75:56/57 f1:50/50 f1.5:56/40 r0.33:60/75 r0.5:55/67 r1:45/50 r2:52/33 |
| `zoo/codex_rubric_pressure_icm_1` | 80 B | cont/MDF % f0.33:59/75 f0.5:59/67 f0.75:45/57 f1:32/50 f1.5:45/40 r0.33:62/75 r0.5:52/67 r1:33/50 r2:32/33 |
| `zoo/codex_chip_ev_1` | 77 B | cont/MDF % f0.33:88/75 f0.5:69/67 f0.75:45/57 f1:35/50 f1.5:40/40 r0.33:90/75 r0.5:84/67 r1:65/50 r2:52/33 |
| `zoo/claude_tourist_1` | 77 B | cont/MDF % f0.33:54/75 f0.5:60/67 f0.75:57/57 f1:45/50 f1.5:60/40 r0.33:53/75 r0.5:55/67 r1:38/50 r2:47/33 |
| `zoo/codex_survival_icm_1` | 76 B | cont/MDF % f0.33:50/75 f0.5:48/67 f0.75:29/57 f1:29/50 f1.5:34/40 r0.33:57/75 r0.5:60/67 r1:45/50 r2:32/33 |
| `zoo/claude_shark_1` | 75 B | cont/MDF % f0.33:92/75 f0.5:82/67 f0.75:62/57 f1:38/50 f1.5:50/40 r0.33:85/75 r0.5:76/67 r1:62/50 r2:57/33 |
| `zoo/claude_maniac_1` | 74 B | cont/MDF % f0.33:100/75 f0.5:48/67 f0.75:41/57 f1:31/50 f1.5:40/40 r0.33:75/75 r0.5:40/67 r1:41/50 r2:49/33 |
| `zoo/codex_adaptive_icm_1` | 71 B | cont/MDF % f0.33:46/75 f0.5:45/67 f0.75:41/57 f1:20/50 f1.5:31/40 r0.33:71/75 r0.5:58/67 r1:47/50 r2:52/33 |
| `zoo/codex_shove_aware_1` | 71 B | cont/MDF % f0.33:46/75 f0.5:45/67 f0.75:41/57 f1:20/50 f1.5:31/40 r0.33:71/75 r0.5:58/67 r1:47/50 r2:52/33 |
| `zoo/codex_steal_value_1` | 66 C | cont/MDF % f0.33:46/75 f0.5:59/67 f0.75:18/57 f1:20/50 f1.5:31/40 r0.33:65/75 r0.5:86/67 r1:47/50 r2:52/33 |
| `zoo/claude_exploiter_1` | 46 D | cont/MDF % f0.33:40/75 f0.5:41/67 f0.75:18/57 f1:16/50 f1.5:18/40 r0.33:41/75 r0.5:37/67 r1:17/50 r2:17/33 |
| `zoo/claude_grinder_1` | 36 F | cont/MDF % f0.33:30/75 f0.5:35/67 f0.75:19/57 f1:15/50 f1.5:22/40 r0.33:23/75 r0.5:20/67 r1:7/50 r2:12/33 |

### 5. Bluffing frequency

River IP when checked to: share of bets that are bluffs (equity < 35%) vs bet/(pot+2*bet).

| bot | score | measured |
|---|---:|---|
| `zoo/codex_rubric_pressure_icm_1` | 81 B | bluffs 22% of bets vs 27% balanced (bets 87/300) |
| `zoo/claude_shark_1` | 62 C | bluffs 18% of bets vs 28% balanced (bets 147/300) |
| `zoo/codex_steal_value_1` | 23 F | bluffs 7% of bets vs 29% balanced (bets 90/300) |
| `zoo/claude_tourist_1` | 20 F | bluffs 4% of bets vs 20% balanced (bets 99/300) |
| `bots/equity_bucket` | 5 F | bluffs 1% of bets vs 28% balanced (bets 144/300) |
| `bots/final` | 0 F | bluffs 0% of bets vs 27% balanced (bets 92/300) |
| `bots/adaptive` | 0 F | bluffs 0% of bets vs 27% balanced (bets 92/300) |
| `bots/steal_heavy` | 0 F | bluffs 0% of bets vs 29% balanced (bets 92/300) |
| `bots/icm_survival` | 0 F | bluffs 0% of bets vs 27% balanced (bets 92/300) |
| `bots/chart_nash` | 0 F | bluffs 0% of bets vs 27% balanced (bets 92/300) |
| `zoo/claude_exploiter_1` | 0 F | bluffs 0% of bets vs 30% balanced (bets 71/300) |
| `bots/push_fold` | 0 F | bluffs 0% of bets vs 28% balanced (bets 46/300) |
| `zoo/codex_adaptive_icm_1` | 0 F | bluffs 0% of bets vs 27% balanced (bets 77/300) |
| `starter` | 0 F | bluffs 0% of bets vs 27% balanced (bets 92/300) |
| `zoo/codex_chip_ev_1` | 0 F | bluffs 0% of bets vs 27% balanced (bets 69/300) |
| `zoo/codex_survival_icm_1` | 0 F | bluffs 0% of bets vs 28% balanced (bets 48/300) |
| `zoo/claude_maniac_1` | 0 F | bluffs 0% of bets vs 25% balanced (bets 78/300) |
| `zoo/codex_shove_aware_1` | 0 F | bluffs 0% of bets vs 27% balanced (bets 77/300) |
| `zoo/claude_grinder_1` | 0 F | bluffs 0% of bets vs 28% balanced (bets 40/300) |

### 6. Value betting

River IP when checked to: bet rate with equity >= 75%.

| bot | score | measured |
|---|---:|---|
| `bots/equity_bucket` | 96 A | bets 96% of 83 strong hands |
| `zoo/claude_shark_1` | 94 A | bets 94% of 83 strong hands |
| `bots/final` | 92 A | bets 92% of 83 strong hands |
| `bots/adaptive` | 92 A | bets 92% of 83 strong hands |
| `bots/steal_heavy` | 92 A | bets 92% of 83 strong hands |
| `bots/icm_survival` | 92 A | bets 92% of 83 strong hands |
| `bots/chart_nash` | 92 A | bets 92% of 83 strong hands |
| `starter` | 92 A | bets 92% of 83 strong hands |
| `zoo/claude_exploiter_1` | 81 B | bets 81% of 83 strong hands |
| `zoo/codex_adaptive_icm_1` | 80 B | bets 80% of 83 strong hands |
| `zoo/claude_maniac_1` | 80 B | bets 80% of 83 strong hands |
| `zoo/codex_shove_aware_1` | 80 B | bets 80% of 83 strong hands |
| `zoo/codex_chip_ev_1` | 76 B | bets 76% of 83 strong hands |
| `zoo/claude_tourist_1` | 72 B | bets 72% of 83 strong hands |
| `zoo/codex_rubric_pressure_icm_1` | 64 C | bets 64% of 83 strong hands |
| `zoo/codex_steal_value_1` | 55 C | bets 55% of 83 strong hands |
| `zoo/codex_survival_icm_1` | 54 D | bets 54% of 83 strong hands |
| `bots/push_fold` | 52 D | bets 52% of 83 strong hands |
| `zoo/claude_grinder_1` | 45 D | bets 45% of 83 strong hands |

### 7. Bet sizing

Bets within 25-150% pot; more than one size; bigger on wet flops than dry.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | median 55% pot, 100% in 25-150%, 4 sizes, wet>=dry yes |
| `bots/adaptive` | 100 A | median 55% pot, 100% in 25-150%, 4 sizes, wet>=dry yes |
| `bots/steal_heavy` | 100 A | median 66% pot, 100% in 25-150%, 3 sizes, wet>=dry yes |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | median 34% pot, 100% in 25-150%, 3 sizes, wet>=dry yes |
| `bots/icm_survival` | 100 A | median 50% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `bots/equity_bucket` | 100 A | median 55% pot, 100% in 25-150%, 3 sizes, wet>=dry yes |
| `bots/chart_nash` | 100 A | median 55% pot, 100% in 25-150%, 3 sizes, wet>=dry yes |
| `zoo/claude_exploiter_1` | 100 A | median 40% pot, 100% in 25-150%, 4 sizes, wet>=dry yes |
| `zoo/codex_adaptive_icm_1` | 100 A | median 50% pot, 100% in 25-150%, 3 sizes, wet>=dry yes |
| `starter` | 100 A | median 50% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `zoo/codex_chip_ev_1` | 100 A | median 66% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `zoo/codex_steal_value_1` | 100 A | median 66% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `zoo/codex_survival_icm_1` | 100 A | median 66% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `zoo/claude_maniac_1` | 100 A | median 140% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `zoo/codex_shove_aware_1` | 100 A | median 66% pot, 100% in 25-150%, 2 sizes, wet>=dry yes |
| `zoo/claude_grinder_1` | 100 A | median 66% pot, 100% in 25-150%, 3 sizes, wet>=dry yes |
| `bots/push_fold` | 80 B | median 66% pot, 100% in 25-150%, 1 sizes, wet>=dry yes |
| `zoo/claude_shark_1` | 80 B | median 66% pot, 100% in 25-150%, 1 sizes, wet>=dry yes |
| `zoo/claude_tourist_1` | 80 B | median 33% pot, 100% in 25-150%, 1 sizes, wet>=dry yes |

### 8. Range construction

River: bluff share near the balanced ratio and 5-35% of strong hands checked (traps).

| bot | score | measured |
|---|---:|---|
| `zoo/codex_rubric_pressure_icm_1` | 89 A | bluff share 22% (balanced 27%), traps 36% |
| `zoo/claude_shark_1` | 81 B | bluff share 18% (balanced 28%), traps 6% |
| `zoo/claude_tourist_1` | 60 C | bluff share 4% (balanced 20%), traps 28% |
| `bots/equity_bucket` | 50 D | bluff share 1% (balanced 28%), traps 4% |
| `bots/final` | 50 D | bluff share 0% (balanced 27%), traps 8% |
| `bots/adaptive` | 50 D | bluff share 0% (balanced 27%), traps 8% |
| `bots/steal_heavy` | 50 D | bluff share 0% (balanced 29%), traps 8% |
| `bots/icm_survival` | 50 D | bluff share 0% (balanced 27%), traps 8% |
| `bots/chart_nash` | 50 D | bluff share 0% (balanced 27%), traps 8% |
| `zoo/claude_exploiter_1` | 50 D | bluff share 0% (balanced 30%), traps 19% |
| `zoo/codex_adaptive_icm_1` | 50 D | bluff share 0% (balanced 27%), traps 20% |
| `starter` | 50 D | bluff share 0% (balanced 27%), traps 8% |
| `zoo/codex_chip_ev_1` | 50 D | bluff share 0% (balanced 27%), traps 24% |
| `zoo/claude_maniac_1` | 50 D | bluff share 0% (balanced 25%), traps 20% |
| `zoo/codex_shove_aware_1` | 50 D | bluff share 0% (balanced 27%), traps 20% |
| `zoo/codex_steal_value_1` | 46 D | bluff share 7% (balanced 29%), traps 45% |
| `zoo/codex_survival_icm_1` | 32 F | bluff share 0% (balanced 28%), traps 46% |
| `bots/push_fold` | 28 F | bluff share 0% (balanced 28%), traps 48% |
| `zoo/claude_grinder_1` | 16 F | bluff share 0% (balanced 28%), traps 55% |

### 9. Preflop strategy

Open-raise ranges by position vs solver-sized reference ranges (weighted Jaccard), plus BTN 3-bet rate vs CO.

| bot | score | measured |
|---|---:|---|
| `bots/steal_heavy` | 72 B | overlap 76%; opens UTG 15 UTG1 17 MP 22 HJ 29 CO 35 BTN 51 SB 55; vs CO open: 3-bet 5%, call 7% |
| `zoo/codex_adaptive_icm_1` | 67 C | overlap 75%; opens UTG 14 UTG1 15 MP 18 HJ 22 CO 30 BTN 45 SB 55; vs CO open: 3-bet 4%, call 6% |
| `zoo/codex_shove_aware_1` | 67 C | overlap 75%; opens UTG 14 UTG1 15 MP 18 HJ 22 CO 30 BTN 45 SB 55; vs CO open: 3-bet 4%, call 6% |
| `bots/adaptive` | 67 C | overlap 74%; opens UTG 12 UTG1 13 MP 17 HJ 22 CO 29 BTN 40 SB 46; vs CO open: 3-bet 4%, call 6% |
| `bots/equity_bucket` | 67 C | overlap 74%; opens UTG 12 UTG1 13 MP 17 HJ 22 CO 29 BTN 40 SB 46; vs CO open: 3-bet 4%, call 6% |
| `bots/chart_nash` | 67 C | overlap 74%; opens UTG 12 UTG1 13 MP 17 HJ 22 CO 29 BTN 40 SB 46; vs CO open: 3-bet 4%, call 6% |
| `zoo/claude_maniac_1` | 67 C | overlap 60%; opens UTG 41 UTG1 41 MP 41 HJ 41 CO 41 BTN 56 SB 65; vs CO open: 3-bet 11%, call 33% |
| `bots/final` | 66 C | overlap 74%; opens UTG 12 UTG1 13 MP 17 HJ 22 CO 29 BTN 40 SB 46; vs CO open: 3-bet 3%, call 5% |
| `bots/icm_survival` | 66 C | overlap 74%; opens UTG 12 UTG1 13 MP 17 HJ 22 CO 29 BTN 40 SB 46; vs CO open: 3-bet 3%, call 5% |
| `zoo/codex_chip_ev_1` | 66 C | overlap 75%; opens UTG 14 UTG1 15 MP 18 HJ 22 CO 30 BTN 45 SB 50; vs CO open: 3-bet 3%, call 10% |
| `starter` | 62 C | overlap 69%; opens UTG 10 UTG1 12 MP 15 HJ 19 CO 25 BTN 36 SB 45; vs CO open: 3-bet 4%, call 6% |
| `zoo/claude_grinder_1` | 60 C | overlap 58%; opens UTG 14 UTG1 14 MP 14 HJ 20 CO 28 BTN 41 SB 29; vs CO open: 3-bet 6%, call 3% |
| `bots/push_fold` | 59 C | overlap 66%; opens UTG 10 UTG1 11 MP 13 HJ 17 CO 22 BTN 32 SB 37; vs CO open: 3-bet 3%, call 2% |
| `zoo/codex_steal_value_1` | 59 C | overlap 73%; opens UTG 15 UTG1 15 MP 15 HJ 15 CO 30 BTN 50 SB 55; vs CO open: 3-bet 0%, call 13% |
| `zoo/claude_shark_1` | 57 C | overlap 60%; opens UTG 10 UTG1 11 MP 17 HJ 17 CO 24 BTN 41 SB 41; vs CO open: 3-bet 4%, call 6% |
| `zoo/codex_rubric_pressure_icm_1` | 57 C | overlap 61%; opens UTG 12 UTG1 14 MP 17 HJ 22 CO 28 BTN 40 SB 45; vs CO open: 3-bet 4%, call 18% |
| `zoo/codex_survival_icm_1` | 53 D | overlap 60%; opens UTG 10 UTG1 10 MP 10 HJ 14 CO 21 BTN 30 SB 38; vs CO open: 3-bet 3%, call 4% |
| `zoo/claude_exploiter_1` | 47 D | overlap 55%; opens UTG 27 UTG1 31 MP 35 HJ 44 CO 54 BTN 75 SB 100; vs CO open: 3-bet 2%, call 3% |
| `zoo/claude_tourist_1` | 23 F | overlap 21%; opens UTG 3 UTG1 3 MP 3 HJ 3 CO 3 BTN 3 SB 51; vs CO open: 3-bet 3%, call 40% |

### 10. Postflop strategy

Mean of: c-bet rate in 45-80%, flop MDF, river EV and value-bet scores.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_shark_1` | 91 A | c-bet 66%, flop MDF 79, river EV 91, value 94 |
| `bots/steal_heavy` | 88 A | c-bet 52%, flop MDF 83, river EV 76, value 92 |
| `bots/equity_bucket` | 83 B | c-bet 36%, flop MDF 89, river EV 83, value 96 |
| `bots/adaptive` | 82 B | c-bet 39%, flop MDF 83, river EV 76, value 92 |
| `bots/final` | 80 B | c-bet 38%, flop MDF 83, river EV 76, value 92 |
| `zoo/codex_rubric_pressure_icm_1` | 76 B | c-bet 60%, flop MDF 80, river EV 62, value 64 |
| `zoo/codex_adaptive_icm_1` | 71 B | c-bet 34%, flop MDF 64, river EV 82, value 80 |
| `bots/chart_nash` | 68 C | c-bet 25%, flop MDF 83, river EV 76, value 92 |
| `zoo/codex_steal_value_1` | 67 C | c-bet 38%, flop MDF 60, river EV 82, value 55 |
| `starter` | 66 C | c-bet 23%, flop MDF 83, river EV 76, value 92 |
| `bots/icm_survival` | 65 C | c-bet 23%, flop MDF 83, river EV 76, value 92 |
| `zoo/claude_maniac_1` | 63 C | c-bet 100%, flop MDF 75, river EV 79, value 80 |
| `zoo/codex_chip_ev_1` | 63 C | c-bet 16%, flop MDF 86, river EV 92, value 76 |
| `zoo/codex_shove_aware_1` | 56 C | c-bet 18%, flop MDF 64, river EV 82, value 80 |
| `zoo/claude_tourist_1` | 56 C | c-bet 11%, flop MDF 80, river EV 72, value 72 |
| `zoo/claude_exploiter_1` | 54 D | c-bet 90%, flop MDF 44, river EV 30, value 81 |
| `bots/push_fold` | 52 D | c-bet 7%, flop MDF 82, river EV 76, value 52 |
| `zoo/codex_survival_icm_1` | 48 D | c-bet 9%, flop MDF 66, river EV 72, value 54 |
| `zoo/claude_grinder_1` | 46 D | c-bet 44%, flop MDF 42, river EV 0, value 45 |

### 11. Position awareness

Spearman correlation of open-raise rate with position, UTG to BTN.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | rho 1.00 (UTG 12% -> BTN 40%) |
| `bots/adaptive` | 100 A | rho 1.00 (UTG 12% -> BTN 40%) |
| `bots/steal_heavy` | 100 A | rho 1.00 (UTG 15% -> BTN 51%) |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | rho 1.00 (UTG 12% -> BTN 40%) |
| `bots/icm_survival` | 100 A | rho 1.00 (UTG 12% -> BTN 40%) |
| `bots/equity_bucket` | 100 A | rho 1.00 (UTG 12% -> BTN 40%) |
| `bots/chart_nash` | 100 A | rho 1.00 (UTG 12% -> BTN 40%) |
| `zoo/claude_exploiter_1` | 100 A | rho 1.00 (UTG 27% -> BTN 75%) |
| `bots/push_fold` | 100 A | rho 1.00 (UTG 10% -> BTN 32%) |
| `zoo/codex_adaptive_icm_1` | 100 A | rho 1.00 (UTG 14% -> BTN 45%) |
| `starter` | 100 A | rho 1.00 (UTG 10% -> BTN 36%) |
| `zoo/codex_chip_ev_1` | 100 A | rho 1.00 (UTG 14% -> BTN 45%) |
| `zoo/codex_shove_aware_1` | 100 A | rho 1.00 (UTG 14% -> BTN 45%) |
| `zoo/claude_shark_1` | 99 A | rho 0.99 (UTG 10% -> BTN 41%) |
| `zoo/codex_survival_icm_1` | 94 A | rho 0.94 (UTG 10% -> BTN 30%) |
| `zoo/claude_grinder_1` | 94 A | rho 0.94 (UTG 14% -> BTN 41%) |
| `zoo/codex_steal_value_1` | 85 B | rho 0.85 (UTG 15% -> BTN 50%) |
| `zoo/claude_maniac_1` | 65 C | rho 0.65 (UTG 41% -> BTN 56%) |
| `zoo/claude_tourist_1` | 0 F | rho 0.00 (UTG 3% -> BTN 3%) |

### 12. Board texture

C-bet rate differs by texture (dry, wet, paired, monotone) and is not higher on wet boards.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | dry 45% wet 27% paired 47% monotone 32% |
| `bots/adaptive` | 100 A | dry 45% wet 29% paired 48% monotone 33% |
| `bots/steal_heavy` | 100 A | dry 68% wet 29% paired 75% monotone 35% |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | dry 64% wet 61% paired 65% monotone 51% |
| `zoo/codex_adaptive_icm_1` | 100 A | dry 59% wet 20% paired 35% monotone 24% |
| `zoo/codex_steal_value_1` | 100 A | dry 31% wet 20% paired 96% monotone 5% |
| `zoo/claude_grinder_1` | 100 A | dry 60% wet 37% paired 43% monotone 36% |
| `zoo/claude_shark_1` | 70 B | dry 60% wet 64% paired 72% monotone 68% |
| `zoo/codex_survival_icm_1` | 70 B | dry 3% wet 8% paired 11% monotone 13% |
| `zoo/claude_tourist_1` | 70 B | dry 1% wet 8% paired 31% monotone 5% |
| `zoo/claude_maniac_1` | 60 C | dry 100% wet 100% paired 100% monotone 100% |
| `bots/icm_survival` | 40 D | dry 17% wet 24% paired 19% monotone 31% |
| `bots/equity_bucket` | 40 D | dry 28% wet 47% paired 33% monotone 35% |
| `bots/chart_nash` | 40 D | dry 17% wet 29% paired 20% monotone 33% |
| `starter` | 40 D | dry 17% wet 24% paired 19% monotone 33% |
| `zoo/codex_chip_ev_1` | 40 D | dry 13% wet 20% paired 11% monotone 21% |
| `zoo/codex_shove_aware_1` | 40 D | dry 17% wet 20% paired 11% monotone 24% |
| `bots/push_fold` | 30 F | dry 1% wet 8% paired 11% monotone 9% |
| `zoo/claude_exploiter_1` | 0 F | dry 88% wet 89% paired 88% monotone 93% |

### 13. Opponent range estimation

Call rate vs a 15 bb shove after 40 hands of a maniac (shoves all) minus after a nit (top 5%), vs best response.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_exploiter_1` | 72 B | calls 56% vs maniac, 15% vs nit (best response 60/3) |
| `zoo/codex_rubric_pressure_icm_1` | 45 D | calls 29% vs maniac, 3% vs nit (best response 60/3) |
| `starter` | 42 D | calls 39% vs maniac, 14% vs nit (best response 60/3) |
| `bots/final` | 0 F | calls 26% vs maniac, 26% vs nit (best response 60/3) |
| `bots/adaptive` | 0 F | calls 33% vs maniac, 33% vs nit (best response 60/3) |
| `bots/steal_heavy` | 0 F | calls 15% vs maniac, 15% vs nit (best response 60/3) |
| `bots/icm_survival` | 0 F | calls 26% vs maniac, 26% vs nit (best response 60/3) |
| `bots/equity_bucket` | 0 F | calls 33% vs maniac, 33% vs nit (best response 60/3) |
| `bots/chart_nash` | 0 F | calls 33% vs maniac, 33% vs nit (best response 60/3) |
| `bots/push_fold` | 0 F | calls 33% vs maniac, 33% vs nit (best response 60/3) |
| `zoo/codex_adaptive_icm_1` | 0 F | calls 2% vs maniac, 5% vs nit (best response 60/3) |
| `zoo/claude_shark_1` | 0 F | calls 7% vs maniac, 7% vs nit (best response 60/3) |
| `zoo/codex_chip_ev_1` | 0 F | calls 19% vs maniac, 19% vs nit (best response 60/3) |
| `zoo/codex_steal_value_1` | 0 F | calls 2% vs maniac, 2% vs nit (best response 60/3) |
| `zoo/codex_survival_icm_1` | 0 F | calls 14% vs maniac, 14% vs nit (best response 60/3) |
| `zoo/claude_maniac_1` | 0 F | calls 18% vs maniac, 18% vs nit (best response 60/3) |
| `zoo/codex_shove_aware_1` | 0 F | calls 2% vs maniac, 5% vs nit (best response 60/3) |
| `zoo/claude_tourist_1` | 0 F | calls 20% vs maniac, 20% vs nit (best response 60/3) |
| `zoo/claude_grinder_1` | 0 F | calls 6% vs maniac, 6% vs nit (best response 60/3) |

### 14. Exploitability

Heads-up push/fold (5-15 bb): bb/hand a best-responding opponent gains over the equilibrium value.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 97 A | 13 mbb/hand (5bb 6, 8bb 11, 10bb 13, 15bb 22) |
| `bots/icm_survival` | 97 A | 13 mbb/hand (5bb 6, 8bb 11, 10bb 13, 15bb 22) |
| `bots/adaptive` | 93 A | 33 mbb/hand (5bb 23, 8bb 14, 10bb 40, 15bb 55) |
| `bots/equity_bucket` | 93 A | 33 mbb/hand (5bb 23, 8bb 14, 10bb 40, 15bb 55) |
| `bots/chart_nash` | 93 A | 33 mbb/hand (5bb 23, 8bb 14, 10bb 40, 15bb 55) |
| `bots/push_fold` | 93 A | 33 mbb/hand (5bb 23, 8bb 14, 10bb 40, 15bb 55) |
| `zoo/codex_chip_ev_1` | 83 B | 84 mbb/hand (5bb 75, 8bb 98, 10bb 90, 15bb 73) |
| `starter` | 70 B | 149 mbb/hand (5bb 126, 8bb 166, 10bb 133, 15bb 170) |
| `zoo/codex_survival_icm_1` | 68 C | 161 mbb/hand (5bb 101, 8bb 142, 10bb 139, 15bb 263) |
| `zoo/codex_rubric_pressure_icm_1` | 62 C | 188 mbb/hand (5bb 52, 8bb 76, 10bb 144, 15bb 478) |
| `zoo/claude_exploiter_1` | 61 C | 193 mbb/hand (5bb 91, 8bb 162, 10bb 200, 15bb 318) |
| `bots/steal_heavy` | 58 C | 210 mbb/hand (5bb 214, 8bb 215, 10bb 203, 15bb 209) |
| `zoo/claude_maniac_1` | 54 D | 231 mbb/hand (5bb 308, 8bb 248, 10bb 215, 15bb 153) |
| `zoo/codex_adaptive_icm_1` | 36 F | 318 mbb/hand (5bb 269, 8bb 304, 10bb 307, 15bb 390) |
| `zoo/codex_shove_aware_1` | 36 F | 318 mbb/hand (5bb 269, 8bb 304, 10bb 307, 15bb 390) |
| `zoo/claude_tourist_1` | 35 F | 326 mbb/hand (5bb 388, 8bb 314, 10bb 365, 15bb 236) |
| `zoo/claude_shark_1` | 16 F | 422 mbb/hand (5bb 523, 8bb 400, 10bb 381, 15bb 386) |
| `zoo/claude_grinder_1` | 7 F | 463 mbb/hand (5bb 445, 8bb 416, 10bb 449, 15bb 541) |
| `zoo/codex_steal_value_1` | 2 F | 489 mbb/hand (5bb 390, 8bb 470, 10bb 498, 15bb 598) |

### 15. GTO deviation

Heads-up push/fold (5-15 bb): mean |bot frequency - equilibrium frequency| over all 1,326 combos.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 82 B | 8.8% of combos off equilibrium |
| `bots/icm_survival` | 82 B | 8.8% of combos off equilibrium |
| `bots/adaptive` | 74 B | 12.9% of combos off equilibrium |
| `bots/equity_bucket` | 74 B | 12.9% of combos off equilibrium |
| `bots/chart_nash` | 74 B | 12.9% of combos off equilibrium |
| `bots/push_fold` | 74 B | 12.9% of combos off equilibrium |
| `zoo/codex_chip_ev_1` | 73 B | 13.5% of combos off equilibrium |
| `zoo/codex_rubric_pressure_icm_1` | 64 C | 18.2% of combos off equilibrium |
| `zoo/codex_survival_icm_1` | 63 C | 18.5% of combos off equilibrium |
| `starter` | 62 C | 19.2% of combos off equilibrium |
| `zoo/claude_maniac_1` | 54 D | 23.0% of combos off equilibrium |
| `bots/steal_heavy` | 54 D | 23.0% of combos off equilibrium |
| `zoo/codex_adaptive_icm_1` | 51 D | 24.3% of combos off equilibrium |
| `zoo/codex_shove_aware_1` | 51 D | 24.3% of combos off equilibrium |
| `zoo/claude_exploiter_1` | 44 D | 28.2% of combos off equilibrium |
| `zoo/claude_shark_1` | 39 F | 30.5% of combos off equilibrium |
| `zoo/codex_steal_value_1` | 34 F | 33.1% of combos off equilibrium |
| `zoo/claude_grinder_1` | 31 F | 34.5% of combos off equilibrium |
| `zoo/claude_tourist_1` | 29 F | 35.4% of combos off equilibrium |

### 16. Regret minimisation

Heads-up push/fold (5-15 bb): bb/hand lost against an equilibrium opponent vs the best response.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 97 A | 8 mbb/hand |
| `bots/icm_survival` | 97 A | 8 mbb/hand |
| `bots/adaptive` | 94 A | 16 mbb/hand |
| `bots/equity_bucket` | 94 A | 16 mbb/hand |
| `bots/chart_nash` | 94 A | 16 mbb/hand |
| `bots/push_fold` | 94 A | 16 mbb/hand |
| `zoo/codex_chip_ev_1` | 90 A | 25 mbb/hand |
| `starter` | 82 B | 44 mbb/hand |
| `zoo/codex_survival_icm_1` | 82 B | 45 mbb/hand |
| `zoo/claude_exploiter_1` | 76 B | 60 mbb/hand |
| `zoo/codex_rubric_pressure_icm_1` | 75 B | 63 mbb/hand |
| `bots/steal_heavy` | 73 B | 68 mbb/hand |
| `zoo/claude_maniac_1` | 59 C | 103 mbb/hand |
| `zoo/codex_adaptive_icm_1` | 56 C | 110 mbb/hand |
| `zoo/codex_shove_aware_1` | 56 C | 110 mbb/hand |
| `zoo/claude_shark_1` | 26 F | 185 mbb/hand |
| `zoo/codex_steal_value_1` | 24 F | 191 mbb/hand |
| `zoo/claude_tourist_1` | 21 F | 197 mbb/hand |
| `zoo/claude_grinder_1` | 10 F | 224 mbb/hand |

### 17. Mixed strategy

Share of repeated identical spots (river and BTN open) where the bot plays more than one action.

| bot | score | measured |
|---|---:|---|
| `zoo/codex_rubric_pressure_icm_1` | 100 A | 14.4% of 229 spots mixed |
| `zoo/claude_shark_1` | 100 A | 10.5% of 229 spots mixed |
| `zoo/claude_maniac_1` | 100 A | 19.2% of 229 spots mixed |
| `zoo/claude_tourist_1` | 70 C | 3.5% of 229 spots mixed |
| `bots/final` | 0 F | 0.0% of 229 spots mixed |
| `bots/adaptive` | 0 F | 0.0% of 229 spots mixed |
| `bots/steal_heavy` | 0 F | 0.0% of 229 spots mixed |
| `bots/icm_survival` | 0 F | 0.0% of 229 spots mixed |
| `bots/equity_bucket` | 0 F | 0.0% of 229 spots mixed |
| `bots/chart_nash` | 0 F | 0.0% of 229 spots mixed |
| `zoo/claude_exploiter_1` | 0 F | 0.0% of 229 spots mixed |
| `bots/push_fold` | 0 F | 0.0% of 229 spots mixed |
| `zoo/codex_adaptive_icm_1` | 0 F | 0.0% of 229 spots mixed |
| `starter` | 0 F | 0.0% of 229 spots mixed |
| `zoo/codex_chip_ev_1` | 0 F | 0.0% of 229 spots mixed |
| `zoo/codex_steal_value_1` | 0 F | 0.0% of 229 spots mixed |
| `zoo/codex_survival_icm_1` | 0 F | 0.0% of 229 spots mixed |
| `zoo/codex_shove_aware_1` | 0 F | 0.0% of 229 spots mixed |
| `zoo/claude_grinder_1` | 0 F | 0.0% of 229 spots mixed |

### 18. Opponent adaptation

Points with memory minus memory wiped, vs aggressive/passive/tight/loose fields; plus the two history tests.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_exploiter_1` | 52 D | memory on-off: aggressive -1.6 passive +0.4 tight +8.2 loose -1.0; range est 72, fold eq 100 |
| `bots/final` | 40 D | memory on-off: aggressive -0.8 passive -0.8 tight +7.0 loose -0.9; range est 0, fold eq 100 |
| `zoo/codex_steal_value_1` | 40 D | memory on-off: aggressive +1.0 passive -3.8 tight +4.7 loose +0.4; range est 0, fold eq 100 |
| `bots/steal_heavy` | 37 F | memory on-off: aggressive +0.0 passive +0.6 tight +4.8 loose -0.1; range est 0, fold eq 92 |
| `zoo/codex_rubric_pressure_icm_1` | 37 F | memory on-off: aggressive -0.6 passive +0.8 tight -0.7 loose -0.9; range est 45, fold eq 78 |
| `bots/adaptive` | 30 F | memory on-off: aggressive -2.5 passive -1.0 tight +5.4 loose -2.3; range est 0, fold eq 100 |
| `zoo/codex_adaptive_icm_1` | 30 F | memory on-off: aggressive -2.8 passive +8.1 tight +4.3 loose -1.6; range est 0, fold eq 100 |
| `starter` | 13 F | memory on-off: aggressive -0.2 passive +0.0 tight +0.0 loose -0.2; range est 42, fold eq 0 |
| `zoo/claude_shark_1` | 10 F | memory on-off: aggressive +0.1 passive -0.8 tight +4.8 loose -0.1; range est 0, fold eq 0 |
| `bots/push_fold` | 6 F | memory on-off: aggressive +0.1 passive -1.1 tight +1.6 loose +0.2; range est 0, fold eq 19 |
| `bots/icm_survival` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |
| `bots/equity_bucket` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |
| `bots/chart_nash` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |
| `zoo/codex_chip_ev_1` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |
| `zoo/codex_survival_icm_1` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |
| `zoo/claude_maniac_1` | 0 F | memory on-off: aggressive -0.3 passive -1.8 tight -1.1 loose -1.2; range est 0, fold eq 0 |
| `zoo/codex_shove_aware_1` | 0 F | memory on-off: aggressive -2.6 passive +0.0 tight -0.4 loose -1.2; range est 0, fold eq 0 |
| `zoo/claude_tourist_1` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |
| `zoo/claude_grinder_1` | 0 F | memory on-off: aggressive +0.0 passive +0.0 tight +0.0 loose +0.0; range est 0, fold eq 0 |

### 19. Bluff catching

River pot or 2x pot bets: call rate of medium hands (equity 30-70%) vs MDF.

| bot | score | measured |
|---|---:|---|
| `zoo/codex_adaptive_icm_1` | 75 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 44% (MDF 33%, n=45); mean EV of those calls +9.1 bb |
| `zoo/codex_steal_value_1` | 75 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 44% (MDF 33%, n=45); mean EV of those calls +9.1 bb |
| `zoo/codex_shove_aware_1` | 75 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 44% (MDF 33%, n=45); mean EV of those calls +9.1 bb |
| `bots/final` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `bots/adaptive` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `bots/steal_heavy` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `bots/icm_survival` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `bots/chart_nash` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `bots/push_fold` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `starter` | 71 B | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 20% (MDF 33%, n=45); mean EV of those calls +9.9 bb |
| `zoo/claude_maniac_1` | 69 C | 1x pot: calls 33% (MDF 50%, n=58); 2x pot: calls 42% (MDF 33%, n=45); mean EV of those calls +9.6 bb |
| `zoo/claude_tourist_1` | 68 C | 1x pot: calls 34% (MDF 50%, n=58); 2x pot: calls 44% (MDF 33%, n=45); mean EV of those calls +8.5 bb |
| `bots/equity_bucket` | 65 C | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 51% (MDF 33%, n=45); mean EV of those calls +9.5 bb |
| `zoo/codex_survival_icm_1` | 58 C | 1x pot: calls 41% (MDF 50%, n=58); 2x pot: calls 11% (MDF 33%, n=45); mean EV of those calls +9.6 bb |
| `zoo/codex_chip_ev_1` | 44 D | 1x pot: calls 79% (MDF 50%, n=58); 2x pot: calls 51% (MDF 33%, n=45); mean EV of those calls +7.8 bb |
| `zoo/claude_shark_1` | 38 F | 1x pot: calls 72% (MDF 50%, n=58); 2x pot: calls 60% (MDF 33%, n=45); mean EV of those calls +7.5 bb |
| `zoo/codex_rubric_pressure_icm_1` | 24 F | 1x pot: calls 17% (MDF 50%, n=58); 2x pot: calls 4% (MDF 33%, n=45); mean EV of those calls +9.8 bb |
| `zoo/claude_exploiter_1` | 3 F | 1x pot: calls 3% (MDF 50%, n=58); 2x pot: calls 0% (MDF 33%, n=45); mean EV of those calls +11.4 bb |
| `zoo/claude_grinder_1` | 2 F | 1x pot: calls 2% (MDF 50%, n=58); 2x pot: calls 0% (MDF 33%, n=45); mean EV of those calls +11.5 bb |

### 20. Fold equity

BTN open rate after 40 hands of blinds that always fold minus blinds that always call.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | opens 86% vs folders, 49% vs callers |
| `bots/adaptive` | 100 A | opens 86% vs folders, 49% vs callers |
| `zoo/claude_exploiter_1` | 100 A | opens 100% vs folders, 57% vs callers |
| `zoo/codex_adaptive_icm_1` | 100 A | opens 95% vs folders, 45% vs callers |
| `zoo/codex_steal_value_1` | 100 A | opens 100% vs folders, 40% vs callers |
| `bots/steal_heavy` | 92 A | opens 100% vs folders, 73% vs callers |
| `zoo/codex_rubric_pressure_icm_1` | 78 B | opens 52% vs folders, 28% vs callers |
| `bots/push_fold` | 19 F | opens 52% vs folders, 46% vs callers |
| `bots/icm_survival` | 0 F | opens 58% vs folders, 58% vs callers |
| `bots/equity_bucket` | 0 F | opens 58% vs folders, 58% vs callers |
| `bots/chart_nash` | 0 F | opens 58% vs folders, 58% vs callers |
| `zoo/claude_shark_1` | 0 F | opens 41% vs folders, 41% vs callers |
| `starter` | 0 F | opens 47% vs folders, 47% vs callers |
| `zoo/codex_chip_ev_1` | 0 F | opens 45% vs folders, 45% vs callers |
| `zoo/codex_survival_icm_1` | 0 F | opens 30% vs folders, 30% vs callers |
| `zoo/claude_maniac_1` | 0 F | opens 56% vs folders, 56% vs callers |
| `zoo/codex_shove_aware_1` | 0 F | opens 45% vs folders, 45% vs callers |
| `zoo/claude_tourist_1` | 0 F | opens 2% vs folders, 2% vs callers |
| `zoo/claude_grinder_1` | 0 F | opens 64% vs folders, 64% vs callers |

### 21. Stack depth

Raises at 12 and 8 bb are all-in; heads-up push/fold at 5-10 bb close to equilibrium.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 92 A | BTN open 100bb 40% 40bb 40% 20bb 37% 12bb 33% 8bb 37%; all-in share at <=12bb 100%; push/fold dev 8% |
| `bots/icm_survival` | 92 A | BTN open 100bb 40% 40bb 40% 20bb 37% 12bb 33% 8bb 37%; all-in share at <=12bb 100%; push/fold dev 8% |
| `bots/adaptive` | 88 A | BTN open 100bb 40% 40bb 40% 20bb 37% 12bb 37% 8bb 42%; all-in share at <=12bb 100%; push/fold dev 12% |
| `bots/equity_bucket` | 88 A | BTN open 100bb 40% 40bb 40% 20bb 37% 12bb 37% 8bb 42%; all-in share at <=12bb 100%; push/fold dev 12% |
| `bots/chart_nash` | 88 A | BTN open 100bb 40% 40bb 40% 20bb 37% 12bb 37% 8bb 42%; all-in share at <=12bb 100%; push/fold dev 12% |
| `bots/push_fold` | 88 A | BTN open 100bb 32% 40bb 32% 20bb 28% 12bb 37% 8bb 42%; all-in share at <=12bb 100%; push/fold dev 12% |
| `zoo/codex_chip_ev_1` | 86 A | BTN open 100bb 45% 40bb 45% 20bb 45% 12bb 28% 8bb 36%; all-in share at <=12bb 100%; push/fold dev 14% |
| `zoo/codex_rubric_pressure_icm_1` | 84 B | BTN open 100bb 40% 40bb 40% 20bb 40% 12bb 40% 8bb 44%; all-in share at <=12bb 100%; push/fold dev 16% |
| `starter` | 80 B | BTN open 100bb 36% 40bb 36% 20bb 36% 12bb 36% 8bb 51%; all-in share at <=12bb 100%; push/fold dev 20% |
| `zoo/codex_adaptive_icm_1` | 76 B | BTN open 100bb 45% 40bb 45% 20bb 45% 12bb 28% 8bb 36%; all-in share at <=12bb 100%; push/fold dev 24% |
| `zoo/codex_shove_aware_1` | 76 B | BTN open 100bb 45% 40bb 45% 20bb 45% 12bb 28% 8bb 36%; all-in share at <=12bb 100%; push/fold dev 24% |
| `bots/steal_heavy` | 76 B | BTN open 100bb 51% 40bb 51% 20bb 46% 12bb 40% 8bb 46%; all-in share at <=12bb 100%; push/fold dev 24% |
| `zoo/claude_maniac_1` | 74 B | BTN open 100bb 56% 40bb 56% 20bb 56% 12bb 52% 8bb 52%; all-in share at <=12bb 100%; push/fold dev 26% |
| `zoo/claude_exploiter_1` | 72 B | BTN open 100bb 75% 40bb 75% 20bb 75% 12bb 40% 8bb 44%; all-in share at <=12bb 100%; push/fold dev 28% |
| `zoo/claude_shark_1` | 67 C | BTN open 100bb 41% 40bb 41% 20bb 41% 12bb 41% 8bb 41%; all-in share at <=12bb 100%; push/fold dev 33% |
| `zoo/claude_grinder_1` | 65 C | BTN open 100bb 41% 40bb 41% 20bb 41% 12bb 28% 8bb 41%; all-in share at <=12bb 100%; push/fold dev 35% |
| `zoo/codex_survival_icm_1` | 58 C | BTN open 100bb 30% 40bb 30% 20bb 30% 12bb 30% 8bb 29%; all-in share at <=12bb 50%; push/fold dev 17% |
| `zoo/codex_steal_value_1` | 41 D | BTN open 100bb 50% 40bb 50% 20bb 50% 12bb 50% 8bb 36%; all-in share at <=12bb 50%; push/fold dev 34% |
| `zoo/claude_tourist_1` | 12 F | BTN open 100bb 3% 40bb 3% 20bb 3% 12bb 3% 8bb 3%; all-in share at <=12bb 0%; push/fold dev 38% |

### 22. Multiway pots

C-bet rate on the same hands and flops 4-way vs heads-up (should fall).

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | c-bet 35% heads-up -> 11% 4-way (x0.31) |
| `bots/adaptive` | 100 A | c-bet 36% heads-up -> 11% 4-way (x0.30) |
| `bots/steal_heavy` | 100 A | c-bet 50% heads-up -> 11% 4-way (x0.21) |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | c-bet 57% heads-up -> 35% 4-way (x0.61) |
| `bots/icm_survival` | 100 A | c-bet 21% heads-up -> 11% 4-way (x0.52) |
| `bots/equity_bucket` | 100 A | c-bet 33% heads-up -> 16% 4-way (x0.48) |
| `bots/chart_nash` | 100 A | c-bet 23% heads-up -> 11% 4-way (x0.47) |
| `zoo/claude_exploiter_1` | 100 A | c-bet 90% heads-up -> 8% 4-way (x0.09) |
| `bots/push_fold` | 100 A | c-bet 9% heads-up -> 3% 4-way (x0.38) |
| `zoo/codex_adaptive_icm_1` | 100 A | c-bet 36% heads-up -> 0% 4-way (x0.00) |
| `zoo/claude_shark_1` | 100 A | c-bet 64% heads-up -> 15% 4-way (x0.24) |
| `starter` | 100 A | c-bet 22% heads-up -> 11% 4-way (x0.48) |
| `zoo/codex_chip_ev_1` | 100 A | c-bet 17% heads-up -> 3% 4-way (x0.19) |
| `zoo/codex_steal_value_1` | 100 A | c-bet 38% heads-up -> 11% 4-way (x0.28) |
| `zoo/codex_survival_icm_1` | 100 A | c-bet 9% heads-up -> 0% 4-way (x0.00) |
| `zoo/codex_shove_aware_1` | 100 A | c-bet 17% heads-up -> 0% 4-way (x0.00) |
| `zoo/claude_grinder_1` | 100 A | c-bet 43% heads-up -> 7% 4-way (x0.17) |
| `zoo/claude_maniac_1` | 29 F | c-bet 100% heads-up -> 100% 4-way (x1.00) |
| `zoo/claude_tourist_1` | 29 F | c-bet 10% heads-up -> 10% 4-way (x1.00) |

### 23. All-in decisions

Heads-up shove/call/fold: share of clear decisions (EV gap >= 0.05 bb) that maximise chip EV vs equilibrium play.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 87 A | 93.7% of clear decisions |
| `bots/icm_survival` | 87 A | 93.7% of clear decisions |
| `bots/adaptive` | 79 B | 89.4% of clear decisions |
| `bots/equity_bucket` | 79 B | 89.4% of clear decisions |
| `bots/chart_nash` | 79 B | 89.4% of clear decisions |
| `bots/push_fold` | 79 B | 89.4% of clear decisions |
| `zoo/codex_chip_ev_1` | 78 B | 88.8% of clear decisions |
| `zoo/codex_rubric_pressure_icm_1` | 68 C | 84.2% of clear decisions; 127/513 SB raises not all-in |
| `zoo/codex_survival_icm_1` | 67 C | 83.3% of clear decisions; 141/419 SB raises not all-in |
| `starter` | 65 C | 82.6% of clear decisions; 105/522 SB raises not all-in |
| `zoo/claude_maniac_1` | 58 C | 78.8% of clear decisions; limps 10; 112/415 SB raises not all-in |
| `bots/steal_heavy` | 57 C | 78.4% of clear decisions; 128/562 SB raises not all-in |
| `zoo/codex_adaptive_icm_1` | 54 D | 77.0% of clear decisions; 141/483 SB raises not all-in |
| `zoo/codex_shove_aware_1` | 54 D | 77.0% of clear decisions; 141/483 SB raises not all-in |
| `zoo/claude_exploiter_1` | 47 D | 73.4% of clear decisions; 169/676 SB raises not all-in |
| `zoo/claude_shark_1` | 42 D | 70.8% of clear decisions; 51/291 SB raises not all-in |
| `zoo/codex_steal_value_1` | 36 F | 67.9% of clear decisions; 280/440 SB raises not all-in |
| `zoo/claude_grinder_1` | 33 F | 66.6% of clear decisions; 1/216 SB raises not all-in |
| `zoo/claude_tourist_1` | 31 F | 65.5% of clear decisions; limps 292; 14/88 SB raises not all-in |

### 24. Monte Carlo simulation

Mean points over 2,000 random-deal tables in eight fixed fields (par 12.5).

| bot | score | measured |
|---|---:|---|
| `bots/final` | 61 C | 32.3 ± 0.4 points over 2000 tables |
| `bots/icm_survival` | 59 C | 31.7 ± 0.4 points over 2000 tables |
| `zoo/codex_adaptive_icm_1` | 55 C | 30.4 ± 0.4 points over 2000 tables |
| `zoo/codex_steal_value_1` | 55 D | 30.3 ± 0.5 points over 2000 tables |
| `bots/steal_heavy` | 53 D | 29.6 ± 0.5 points over 2000 tables |
| `bots/chart_nash` | 52 D | 29.3 ± 0.5 points over 2000 tables |
| `bots/adaptive` | 51 D | 29.2 ± 0.5 points over 2000 tables |
| `zoo/claude_shark_1` | 49 D | 28.4 ± 0.5 points over 2000 tables |
| `bots/equity_bucket` | 49 D | 28.4 ± 0.5 points over 2000 tables |
| `zoo/claude_exploiter_1` | 47 D | 27.9 ± 0.5 points over 2000 tables |
| `zoo/codex_shove_aware_1` | 46 D | 27.6 ± 0.5 points over 2000 tables |
| `bots/push_fold` | 45 D | 27.2 ± 0.5 points over 2000 tables |
| `zoo/claude_grinder_1` | 44 D | 26.7 ± 0.4 points over 2000 tables |
| `zoo/codex_rubric_pressure_icm_1` | 37 F | 24.4 ± 0.5 points over 2000 tables |
| `zoo/codex_survival_icm_1` | 34 F | 23.7 ± 0.5 points over 2000 tables |
| `zoo/claude_tourist_1` | 34 F | 23.4 ± 0.5 points over 2000 tables |
| `starter` | 33 F | 23.2 ± 0.5 points over 2000 tables |
| `zoo/codex_chip_ev_1` | 26 F | 21.1 ± 0.5 points over 2000 tables |
| `zoo/claude_maniac_1` | 16 F | 17.8 ± 0.5 points over 2000 tables |

### 25. Self-play

Eight copies: no failed decisions and tables finish before the hand cap.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | 147 hands/table, 0% reach the cap, 0 failed of 92625 |
| `bots/adaptive` | 100 A | 132 hands/table, 0% reach the cap, 0 failed of 79469 |
| `bots/steal_heavy` | 100 A | 143 hands/table, 0% reach the cap, 0 failed of 81193 |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | 140 hands/table, 0% reach the cap, 0 failed of 92650 |
| `bots/icm_survival` | 100 A | 145 hands/table, 0% reach the cap, 0 failed of 91940 |
| `bots/equity_bucket` | 100 A | 130 hands/table, 0% reach the cap, 0 failed of 76420 |
| `bots/chart_nash` | 100 A | 134 hands/table, 0% reach the cap, 0 failed of 79595 |
| `zoo/claude_exploiter_1` | 100 A | 122 hands/table, 0% reach the cap, 0 failed of 103914 |
| `bots/push_fold` | 100 A | 127 hands/table, 0% reach the cap, 0 failed of 77825 |
| `zoo/codex_adaptive_icm_1` | 100 A | 158 hands/table, 0% reach the cap, 0 failed of 102826 |
| `zoo/claude_shark_1` | 100 A | 190 hands/table, 0% reach the cap, 0 failed of 90159 |
| `starter` | 100 A | 146 hands/table, 0% reach the cap, 0 failed of 87246 |
| `zoo/codex_chip_ev_1` | 100 A | 147 hands/table, 0% reach the cap, 0 failed of 97376 |
| `zoo/codex_steal_value_1` | 100 A | 172 hands/table, 0% reach the cap, 0 failed of 121953 |
| `zoo/codex_survival_icm_1` | 100 A | 171 hands/table, 0% reach the cap, 0 failed of 107756 |
| `zoo/claude_maniac_1` | 100 A | 71 hands/table, 0% reach the cap, 0 failed of 35871 |
| `zoo/codex_shove_aware_1` | 100 A | 160 hands/table, 0% reach the cap, 0 failed of 103283 |
| `zoo/claude_tourist_1` | 100 A | 145 hands/table, 0% reach the cap, 0 failed of 133928 |
| `zoo/claude_grinder_1` | 100 A | 198 hands/table, 0% reach the cap, 0 failed of 105323 |

### 26. Baseline opponents

Points vs 7 random, 7 rule-based (starter), 7 tight-aggressive and 7 calling-station bots.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 44 D | random 34.4 rule_based 17.9 tag 15.8 station 39.2 |
| `bots/icm_survival` | 44 D | random 34.5 rule_based 16.3 tag 16.2 station 39.8 |
| `bots/steal_heavy` | 42 D | random 28.7 rule_based 16.8 tag 20.3 station 39.0 |
| `zoo/claude_exploiter_1` | 41 D | random 21.1 rule_based 19.0 tag 25.0 station 37.7 |
| `zoo/codex_steal_value_1` | 38 F | random 33.3 rule_based 14.4 tag 21.5 station 29.9 |
| `bots/adaptive` | 38 F | random 30.4 rule_based 15.8 tag 13.9 station 39.0 |
| `bots/chart_nash` | 38 F | random 30.8 rule_based 14.6 tag 14.2 station 39.1 |
| `bots/equity_bucket` | 37 F | random 29.4 rule_based 15.2 tag 15.2 station 37.6 |
| `zoo/codex_adaptive_icm_1` | 35 F | random 35.2 rule_based 17.1 tag 15.2 station 28.4 |
| `zoo/claude_shark_1` | 33 F | random 32.3 rule_based 13.6 tag 16.0 station 31.3 |
| `bots/push_fold` | 32 F | random 29.9 rule_based 12.4 tag 16.0 station 32.8 |
| `zoo/codex_shove_aware_1` | 27 F | random 34.0 rule_based 13.0 tag 12.4 station 26.3 |
| `zoo/codex_rubric_pressure_icm_1` | 27 F | random 22.6 rule_based 12.7 tag 16.2 station 33.9 |
| `zoo/claude_grinder_1` | 27 F | random 29.4 rule_based 12.6 tag 12.0 station 31.0 |
| `starter` | 24 F | random 16.9 rule_based 13.6 tag 11.4 station 39.0 |
| `zoo/claude_tourist_1` | 20 F | random 25.4 rule_based 4.6 tag 4.7 station 40.8 |
| `zoo/codex_survival_icm_1` | 18 F | random 26.3 rule_based 11.3 tag 9.9 station 26.5 |
| `zoo/claude_maniac_1` | 18 F | random 28.0 rule_based 11.7 tag 20.2 station 13.5 |
| `zoo/codex_chip_ev_1` | 11 F | random 20.1 rule_based 9.2 tag 8.5 station 26.0 |

### 27. Head-to-head

Heads-up matches against every other bot: share won.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_exploiter_1` | 76 B | wins 76% of heads-up matches; worst vs zoo/codex_rubric_pressure_icm_1 53% |
| `bots/final` | 61 C | wins 61% of heads-up matches; worst vs zoo/claude_exploiter_1 40% |
| `bots/steal_heavy` | 60 C | wins 60% of heads-up matches; worst vs zoo/claude_exploiter_1 33% |
| `zoo/codex_rubric_pressure_icm_1` | 60 C | wins 60% of heads-up matches; worst vs bots/steal_heavy 46% |
| `bots/chart_nash` | 60 C | wins 60% of heads-up matches; worst vs zoo/claude_exploiter_1 36% |
| `bots/adaptive` | 59 C | wins 59% of heads-up matches; worst vs zoo/claude_exploiter_1 36% |
| `bots/equity_bucket` | 59 C | wins 59% of heads-up matches; worst vs zoo/claude_exploiter_1 29% |
| `bots/icm_survival` | 57 C | wins 57% of heads-up matches; worst vs zoo/claude_exploiter_1 30% |
| `bots/push_fold` | 55 D | wins 55% of heads-up matches; worst vs zoo/claude_exploiter_1 31% |
| `zoo/claude_maniac_1` | 54 D | wins 54% of heads-up matches; worst vs zoo/claude_exploiter_1 42% |
| `zoo/codex_adaptive_icm_1` | 54 D | wins 54% of heads-up matches; worst vs zoo/claude_exploiter_1 18% |
| `zoo/codex_chip_ev_1` | 53 D | wins 53% of heads-up matches; worst vs zoo/claude_exploiter_1 15% |
| `starter` | 52 D | wins 52% of heads-up matches; worst vs zoo/claude_exploiter_1 26% |
| `zoo/codex_shove_aware_1` | 52 D | wins 52% of heads-up matches; worst vs zoo/claude_exploiter_1 13% |
| `zoo/codex_survival_icm_1` | 46 D | wins 46% of heads-up matches; worst vs zoo/claude_exploiter_1 11% |
| `zoo/codex_steal_value_1` | 43 D | wins 43% of heads-up matches; worst vs zoo/claude_exploiter_1 13% |
| `zoo/claude_tourist_1` | 28 F | wins 28% of heads-up matches; worst vs zoo/claude_exploiter_1 17% |
| `zoo/claude_shark_1` | 14 F | wins 14% of heads-up matches; worst vs bots/steal_heavy 2% |
| `zoo/claude_grinder_1` | 8 F | wins 8% of heads-up matches; worst vs bots/steal_heavy 0% |

### 28. Variance and confidence

Out-of-sample league: probability the true edge over par is positive (normal approx.).

| bot | score | measured |
|---|---:|---|
| `bots/icm_survival` | 100 A | 16.1 points, 95% CI 15.3-16.8 over 2487 seats; P(edge>0) 100% |
| `zoo/claude_exploiter_1` | 100 A | 22.8 points, 95% CI 21.9-23.7 over 2528 seats; P(edge>0) 100% |
| `bots/final` | 100 A | 15.5 points, 95% CI 14.7-16.2 over 2536 seats; P(edge>0) 100% |
| `bots/steal_heavy` | 100 A | 15.4 points, 95% CI 14.6-16.2 over 2485 seats; P(edge>0) 100% |
| `bots/chart_nash` | 100 A | 15.2 points, 95% CI 14.5-16.0 over 2504 seats; P(edge>0) 100% |
| `bots/adaptive` | 100 A | 14.9 points, 95% CI 14.1-15.7 over 2515 seats; P(edge>0) 100% |
| `bots/equity_bucket` | 100 A | 14.6 points, 95% CI 13.9-15.4 over 2496 seats; P(edge>0) 100% |
| `bots/push_fold` | 100 A | 14.1 points, 95% CI 13.3-14.8 over 2557 seats; P(edge>0) 100% |
| `zoo/codex_adaptive_icm_1` | 12 F | 12.1 points, 95% CI 11.5-12.8 over 2576 seats; P(edge>0) 12% |
| `zoo/codex_shove_aware_1` | 2 F | 11.8 points, 95% CI 11.2-12.5 over 2550 seats; P(edge>0) 2% |
| `zoo/codex_steal_value_1` | 0 F | 11.3 points, 95% CI 10.7-12.0 over 2495 seats; P(edge>0) 0% |
| `zoo/claude_grinder_1` | 0 F | 11.4 points, 95% CI 10.9-12.0 over 2531 seats; P(edge>0) 0% |
| `zoo/claude_shark_1` | 0 F | 11.3 points, 95% CI 10.7-12.0 over 2519 seats; P(edge>0) 0% |
| `zoo/codex_survival_icm_1` | 0 F | 10.4 points, 95% CI 9.8-11.0 over 2471 seats; P(edge>0) 0% |
| `zoo/codex_rubric_pressure_icm_1` | 0 F | 9.9 points, 95% CI 9.2-10.5 over 2533 seats; P(edge>0) 0% |
| `starter` | 0 F | 9.5 points, 95% CI 8.8-10.2 over 2536 seats; P(edge>0) 0% |
| `zoo/codex_chip_ev_1` | 0 F | 8.3 points, 95% CI 7.7-8.9 over 2553 seats; P(edge>0) 0% |
| `zoo/claude_maniac_1` | 0 F | 8.5 points, 95% CI 7.8-9.2 over 2531 seats; P(edge>0) 0% |
| `zoo/claude_tourist_1` | 0 F | 4.7 points, 95% CI 4.2-5.1 over 2597 seats; P(edge>0) 0% |

### 29. Out-of-sample

League with unseen seed, varied stacks/levels/caps, random payouts, 6 variants and an unseen bot.

| bot | score | measured |
|---|---:|---|
| `zoo/claude_exploiter_1` | 100 A | 22.8 points, rank 1/19 |
| `bots/icm_survival` | 47 D | 16.1 points, rank 2/19 |
| `bots/final` | 40 F | 15.5 points, rank 3/19 |
| `bots/steal_heavy` | 38 F | 15.4 points, rank 4/19 |
| `bots/chart_nash` | 36 F | 15.2 points, rank 5/19 |
| `bots/adaptive` | 32 F | 14.9 points, rank 6/19 |
| `bots/equity_bucket` | 29 F | 14.6 points, rank 7/19 |
| `bots/push_fold` | 21 F | 14.1 points, rank 8/19 |
| `zoo/codex_rubric_pressure_icm_1` | 0 F | 9.9 points, rank 15/19 |
| `zoo/codex_adaptive_icm_1` | 0 F | 12.1 points, rank 9/19 |
| `zoo/claude_shark_1` | 0 F | 11.3 points, rank 13/19 |
| `starter` | 0 F | 9.5 points, rank 16/19 |
| `zoo/codex_chip_ev_1` | 0 F | 8.3 points, rank 18/19 |
| `zoo/codex_steal_value_1` | 0 F | 11.3 points, rank 12/19 |
| `zoo/codex_survival_icm_1` | 0 F | 10.4 points, rank 14/19 |
| `zoo/claude_maniac_1` | 0 F | 8.5 points, rank 17/19 |
| `zoo/codex_shove_aware_1` | 0 F | 11.8 points, rank 10/19 |
| `zoo/claude_tourist_1` | 0 F | 4.7 points, rank 19/19 |
| `zoo/claude_grinder_1` | 0 F | 11.4 points, rank 11/19 |

### 30. Strategy consistency

Same decision after relabelling suits and rotating seats.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `bots/adaptive` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `bots/steal_heavy` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `bots/icm_survival` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `bots/equity_bucket` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `bots/chart_nash` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/claude_exploiter_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `bots/push_fold` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/codex_adaptive_icm_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `starter` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/codex_chip_ev_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/codex_steal_value_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/codex_survival_icm_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/codex_shove_aware_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/claude_tourist_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/claude_grinder_1` | 100 A | 100.0% same (suits 100%, seats 100%) |
| `zoo/claude_shark_1` | 97 A | 97.3% same (suits 99%, seats 96%) |
| `zoo/codex_rubric_pressure_icm_1` | 96 A | 96.0% same (suits 97%, seats 95%) |
| `zoo/claude_maniac_1` | 87 A | 87.1% same (suits 100%, seats 74%) |

### 31. Action legality

tools/fuzz.py (illegal actions) and failed decisions across all simulated tables.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | fuzz: none; failed decisions in play 0/468168 (0.000%); illegal in probes 0 |
| `bots/adaptive` | 100 A | fuzz: none; failed decisions in play 0/443201 (0.000%); illegal in probes 0 |
| `bots/steal_heavy` | 100 A | fuzz: none; failed decisions in play 0/388608 (0.000%); illegal in probes 0 |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | fuzz: none; failed decisions in play 0/342442 (0.000%); illegal in probes 0 |
| `bots/icm_survival` | 100 A | fuzz: none; failed decisions in play 0/490709 (0.000%); illegal in probes 0 |
| `bots/equity_bucket` | 100 A | fuzz: none; failed decisions in play 0/419543 (0.000%); illegal in probes 0 |
| `bots/chart_nash` | 100 A | fuzz: none; failed decisions in play 0/466079 (0.000%); illegal in probes 0 |
| `zoo/claude_exploiter_1` | 100 A | fuzz: nondeterministic=45; failed decisions in play 0/292249 (0.000%); illegal in probes 0 |
| `bots/push_fold` | 100 A | fuzz: none; failed decisions in play 0/467837 (0.000%); illegal in probes 0 |
| `zoo/codex_adaptive_icm_1` | 100 A | fuzz: exception=83, exception_B=83; failed decisions in play 0/463754 (0.000%); illegal in probes 0 |
| `zoo/claude_shark_1` | 100 A | fuzz: none; failed decisions in play 0/381431 (0.000%); illegal in probes 0 |
| `starter` | 100 A | fuzz: nondeterministic=26; failed decisions in play 0/376717 (0.000%); illegal in probes 0 |
| `zoo/codex_chip_ev_1` | 100 A | fuzz: none; failed decisions in play 0/371973 (0.000%); illegal in probes 0 |
| `zoo/codex_steal_value_1` | 100 A | fuzz: none; failed decisions in play 0/400015 (0.000%); illegal in probes 0 |
| `zoo/codex_survival_icm_1` | 100 A | fuzz: none; failed decisions in play 0/402193 (0.000%); illegal in probes 0 |
| `zoo/claude_maniac_1` | 100 A | fuzz: none; failed decisions in play 0/227672 (0.000%); illegal in probes 0 |
| `zoo/codex_shove_aware_1` | 100 A | fuzz: exception=83, exception_B=83; failed decisions in play 0/455557 (0.000%); illegal in probes 0 |
| `zoo/claude_tourist_1` | 100 A | fuzz: none; failed decisions in play 0/607304 (0.000%); illegal in probes 0 |
| `zoo/claude_grinder_1` | 100 A | fuzz: none; failed decisions in play 0/458982 (0.000%); illegal in probes 0 |

### 32. Game state integrity

tools/fuzz.py malformed states and corrupted memory: no exceptions, bounded memory, deterministic.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | fuzz: none; harness errors 0 |
| `bots/adaptive` | 100 A | fuzz: none; harness errors 0 |
| `bots/steal_heavy` | 100 A | fuzz: none; harness errors 0 |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | fuzz: none; harness errors 0 |
| `bots/icm_survival` | 100 A | fuzz: none; harness errors 0 |
| `bots/equity_bucket` | 100 A | fuzz: none; harness errors 0 |
| `bots/chart_nash` | 100 A | fuzz: none; harness errors 0 |
| `zoo/claude_exploiter_1` | 100 A | fuzz: nondeterministic=45; harness errors 0 |
| `bots/push_fold` | 100 A | fuzz: none; harness errors 0 |
| `zoo/claude_shark_1` | 100 A | fuzz: none; harness errors 0 |
| `starter` | 100 A | fuzz: nondeterministic=26; harness errors 0 |
| `zoo/codex_chip_ev_1` | 100 A | fuzz: none; harness errors 0 |
| `zoo/codex_steal_value_1` | 100 A | fuzz: none; harness errors 0 |
| `zoo/codex_survival_icm_1` | 100 A | fuzz: none; harness errors 0 |
| `zoo/claude_maniac_1` | 100 A | fuzz: none; harness errors 0 |
| `zoo/claude_tourist_1` | 100 A | fuzz: none; harness errors 0 |
| `zoo/claude_grinder_1` | 100 A | fuzz: none; harness errors 0 |
| `zoo/codex_adaptive_icm_1` | 0 F | fuzz: exception=83, exception_B=83; harness errors 0 |
| `zoo/codex_shove_aware_1` | 0 F | fuzz: exception=83, exception_B=83; harness errors 0 |

### 33. Information leakage

Same decision when hidden cards (opponent hands, future board) change; static scan for introspection.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `bots/adaptive` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `bots/steal_heavy` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/codex_rubric_pressure_icm_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `bots/icm_survival` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `bots/equity_bucket` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `bots/chart_nash` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/claude_exploiter_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `bots/push_fold` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/codex_adaptive_icm_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/claude_shark_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `starter` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/codex_chip_ev_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/codex_steal_value_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/codex_survival_icm_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/claude_maniac_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/codex_shove_aware_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/claude_tourist_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |
| `zoo/claude_grinder_1` | 100 A | 100.0% unchanged when hidden cards change; static hits 0 |

### 34. Tournament ICM

Bubble (4 left, 3 paid): calls vs a chip leader's shove agree with exact ICM, and are tighter than winner-takes-all.

| bot | score | measured |
|---|---:|---|
| `bots/final` | 100 A | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 5%; agrees with ICM on 100% |
| `bots/icm_survival` | 100 A | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 5%; agrees with ICM on 100% |
| `zoo/codex_adaptive_icm_1` | 100 A | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 9%; agrees with ICM on 100% |
| `zoo/claude_shark_1` | 100 A | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 7%; agrees with ICM on 100% |
| `zoo/codex_shove_aware_1` | 100 A | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 9%; agrees with ICM on 100% |
| `zoo/codex_survival_icm_1` | 99 A | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 14%; agrees with ICM on 99% |
| `zoo/claude_grinder_1` | 99 A | bubble call 3% (ICM-correct 1%, chip-EV 15%), winner-takes-all 6%; agrees with ICM on 98% |
| `zoo/codex_rubric_pressure_icm_1` | 98 A | bubble call 3% (ICM-correct 1%, chip-EV 15%), winner-takes-all 19%; agrees with ICM on 98% |
| `bots/adaptive` | 98 A | bubble call 3% (ICM-correct 1%, chip-EV 15%), winner-takes-all 8%; agrees with ICM on 97% |
| `bots/equity_bucket` | 98 A | bubble call 3% (ICM-correct 1%, chip-EV 15%), winner-takes-all 8%; agrees with ICM on 97% |
| `bots/chart_nash` | 98 A | bubble call 3% (ICM-correct 1%, chip-EV 15%), winner-takes-all 8%; agrees with ICM on 97% |
| `bots/push_fold` | 98 A | bubble call 3% (ICM-correct 1%, chip-EV 15%), winner-takes-all 8%; agrees with ICM on 97% |
| `zoo/claude_exploiter_1` | 88 A | bubble call 18% (ICM-correct 1%, chip-EV 15%), winner-takes-all 53%; agrees with ICM on 83% |
| `starter` | 73 B | bubble call 40% (ICM-correct 1%, chip-EV 15%), winner-takes-all 67%; agrees with ICM on 61% |
| `zoo/codex_steal_value_1` | 69 C | bubble call 0% (ICM-correct 1%, chip-EV 15%), winner-takes-all 1%; agrees with ICM on 99% |
| `bots/steal_heavy` | 60 C | bubble call 15% (ICM-correct 1%, chip-EV 15%), winner-takes-all 15%; agrees with ICM on 86% |
| `zoo/claude_maniac_1` | 58 C | bubble call 18% (ICM-correct 1%, chip-EV 15%), winner-takes-all 18%; agrees with ICM on 83% |
| `zoo/codex_chip_ev_1` | 58 C | bubble call 19% (ICM-correct 1%, chip-EV 15%), winner-takes-all 19%; agrees with ICM on 82% |
| `zoo/claude_tourist_1` | 56 C | bubble call 20% (ICM-correct 1%, chip-EV 15%), winner-takes-all 20%; agrees with ICM on 81% |

## Method and limits

- **Spots.** Every probe is one hand on the simulator's own `Table` (8 seats, blinds 10/20, 100 bb unless
  stated), with a rigged deck and scripted opponents, so the bot sees the same `GameState` it sees in play.
  Earlier actions of the bot in the hand can be forced: it is still asked (its memory sees the hand), the
  scripted action is played, and only the decision at the probe point is scored. Equities are exact on the
  river and Monte Carlo (400 runouts) on the flop, against the range the scripted opponent's cards were drawn
  from (BTN top 45%, BB top 50%, ranked by equity against a top-25% range).
- **Solver.** No 8-max no-limit solver is available here. The "trusted solver" for exploitability, GTO
  deviation, regret and all-in tests is the exact heads-up push/fold equilibrium (fictitious play, 600
  iterations, on a 169x169 preflop equity matrix from 1,500 runouts per pair). It reproduces the published
  push/fold charts (10 bb: SB pushes 58%, BB calls 37%). A bot that min-raises or limps instead of shoving is
  scored as if it folded or shoved respectively; the all-in row reports how often that happened. Preflop
  reference ranges are top-X% ranges sized like common 8-max solver charts (UTG 16% ... BTN 46%), not solver
  output.
- **Simulations.** Each fixed field is 250 tables (hero + 7 opponents, same deals for every bot); memory
  ablation wipes the bot's memory before every decision on the same tables; self-play is 100 tables of 8
  copies; heads-up is 100 two-seat tables per pair; the out-of-sample league is 1,000 tables per variant over
  all six variants with varied stacks, levels, hand caps and random payouts, including
  `zoo/claude_exploiter_1`, which was written after the strategies were tuned.
- **What does not transfer.** Everything runs on our re-implementation of the rules, not the organizers' kit.
  Mixed-strategy frequencies cannot be checked against a solver, so that test only checks whether the bot
  mixes at all. Hand-equity is judged by the bot's decisions, since bots do not expose their own estimate.

