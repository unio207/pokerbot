# Strategy evaluation, 2026-11-11

Every strategy in the repo ranked on the **unofficial** mini simulator (`devtest/mini_sim.py`)
in all six variants it plays. Produced by [`tools/eval_all.py`](../tools/eval_all.py):

```bash
python3.12 tools/eval_all.py run league 3000 --seed eval1 --out eval-results/league-2026-11-11.json.gz
python3.12 tools/eval_all.py run weak 600 --seed eval1 --out eval-results/weak-2026-11-11.json.gz
python3.12 tools/eval_all.py report eval-results/league-2026-11-11.json.gz eval-results/weak-2026-11-11.json.gz \
    --pair bots/final bots/icm_survival --pair bots/final zoo/codex_adaptive_icm_1 \
    --pair bots/final bots/adaptive --pair bots/final bots/steal_heavy --pair bots/final starter
```

- **League:** 3,000 tables per variant (18,000 total), each seating 8 of the 18 candidates at random.
- **Weak field:** each candidate plus 7 bots drawn from `sparring/*` and `starter`, 600 tables per
  bot per variant (68,400 total). Every hero gets the same tables, so differences are paired.
- Rules: 2,000 chips, blinds up every 20 hands, 250-hand cap, 50/30/20 points, so par is 12.5.
- The `.json.gz` files hold every table's raw result for each bot; `report` rebuilds the tables below.

## Conclusion

`bots/final` is the best overall: first against weak fields (31.0), second in the league (16.4,
tied with `bots/icm_survival` at 16.7 within noise), and the highest worst-variant score in the
league (14.5). `zoo/codex_adaptive_icm_1` matches it against weak fields in the variants it
implements but falls well behind against strong opponents. The zoo bots do not implement Irish,
which lowers their averages.

Caveats: the simulator and the non-hold'em rules are our own guesses, the `bots/` profiles were
tuned on this simulator, and 7 of the 18 league entrants share one core. `zoo/claude_exploiter_1`
did not exist in the repo when this ran.

## League (8 random candidates per table)

| bot | avg | ±SE | holdem | omaha | short_deck | irish | auction | discard_reveal | worst | 1st% | VPIP% | PFR% | fail% | tables |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bots/icm_survival` | 16.7 | 0.21 | 15.1 | 16.2 | 16.5 | 22.0 | 13.2 | 16.9 | 13.2 | 17.9 | 22.4 | 17.7 | 0.00 | 8250 |
| `bots/final` | 16.4 | 0.22 | 15.1 | 15.4 | 15.8 | 21.4 | 14.5 | 16.2 | 14.5 | 17.8 | 23.0 | 18.4 | 0.01 | 7926 |
| `bots/steal_heavy` | 16.3 | 0.23 | 15.2 | 16.2 | 15.0 | 22.0 | 13.9 | 15.3 | 13.9 | 21.4 | 29.6 | 25.3 | 0.01 | 7938 |
| `bots/chart_nash` | 15.9 | 0.22 | 14.7 | 16.8 | 15.2 | 21.2 | 12.6 | 14.8 | 12.6 | 18.8 | 24.1 | 18.6 | 0.00 | 8172 |
| `bots/adaptive` | 15.6 | 0.22 | 14.7 | 15.4 | 15.3 | 20.5 | 12.9 | 15.0 | 12.9 | 18.5 | 24.5 | 19.2 | 0.01 | 7854 |
| `bots/equity_bucket` | 15.5 | 0.22 | 13.6 | 15.6 | 14.5 | 21.4 | 12.9 | 14.9 | 12.9 | 19.3 | 24.0 | 18.5 | 0.00 | 8004 |
| `bots/push_fold` | 15.3 | 0.21 | 13.3 | 16.3 | 14.7 | 20.9 | 12.8 | 14.1 | 12.8 | 17.5 | 21.4 | 16.5 | 0.01 | 8022 |
| `zoo/codex_adaptive_icm_1` | 12.8 | 0.19 | 14.6 | 11.3 | 13.4 | 9.0 | 14.6 | 13.9 | 9.0 | 10.0 | 23.3 | 19.5 | 0.13 | 8010 |
| `zoo/codex_shove_aware_1` | 12.2 | 0.19 | 13.5 | 11.4 | 12.5 | 8.7 | 13.8 | 13.4 | 8.7 | 9.3 | 21.1 | 17.2 | 0.13 | 7944 |
| `zoo/claude_shark_1` | 11.8 | 0.17 | 11.6 | 12.6 | 11.6 | 7.6 | 15.0 | 12.4 | 7.6 | 5.9 | 21.2 | 18.3 | 0.14 | 8040 |
| `zoo/claude_grinder_1` | 11.5 | 0.15 | 11.4 | 12.4 | 12.5 | 7.7 | 11.2 | 13.6 | 7.7 | 1.9 | 17.9 | 15.1 | 0.00 | 7908 |
| `zoo/codex_steal_value_1` | 11.4 | 0.18 | 12.9 | 10.8 | 11.9 | 8.6 | 11.3 | 13.0 | 8.6 | 7.6 | 25.0 | 19.5 | 0.04 | 8046 |
| `zoo/codex_rubric_pressure_icm_1` | 11.1 | 0.20 | 11.8 | 11.5 | 12.1 | 8.8 | 11.2 | 11.0 | 8.8 | 13.3 | 31.1 | 19.5 | 0.08 | 7974 |
| `zoo/codex_survival_icm_1` | 10.8 | 0.17 | 12.1 | 10.3 | 11.7 | 7.3 | 10.4 | 12.9 | 7.3 | 5.5 | 15.5 | 12.5 | 0.00 | 7740 |
| `starter` | 9.7 | 0.20 | 11.2 | 11.6 | 11.3 | 5.1 | 8.4 | 10.9 | 5.1 | 13.2 | 36.8 | 28.2 | 0.02 | 8034 |
| `zoo/claude_maniac_1` | 8.7 | 0.19 | 8.2 | 9.8 | 7.9 | 4.9 | 15.8 | 5.5 | 4.9 | 13.2 | 51.7 | 29.7 | 0.02 | 8250 |
| `zoo/codex_chip_ev_1` | 8.6 | 0.18 | 10.5 | 8.8 | 9.9 | 5.8 | 8.0 | 8.6 | 5.8 | 8.1 | 23.0 | 17.0 | 0.00 | 7884 |
| `zoo/claude_tourist_1` | 4.7 | 0.14 | 5.7 | 2.6 | 3.3 | 1.7 | 12.3 | 2.7 | 1.7 | 5.2 | 47.5 | 2.8 | 0.00 | 8004 |

## Weak field (hero + 7 sparring/starter bots)

| bot | avg | ±SE | holdem | omaha | short_deck | irish | auction | discard_reveal | worst | 1st% | VPIP% | PFR% | fail% | tables |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bots/final` | 31.0 | 0.32 | 30.0 | 27.5 | 26.9 | 37.7 | 32.5 | 31.5 | 26.9 | 42.8 | 34.0 | 32.2 | 0.01 | 3600 |
| `bots/icm_survival` | 30.8 | 0.30 | 28.7 | 28.0 | 26.8 | 37.0 | 32.5 | 32.0 | 26.8 | 38.8 | 30.5 | 28.0 | 0.00 | 3600 |
| `zoo/codex_adaptive_icm_1` | 30.7 | 0.30 | 30.6 | 27.0 | 28.9 | 31.7 | 34.5 | 31.8 | 27.0 | 37.9 | 36.0 | 33.1 | 0.11 | 3600 |
| `zoo/codex_shove_aware_1` | 29.6 | 0.30 | 28.0 | 26.8 | 27.9 | 30.8 | 33.0 | 30.9 | 26.8 | 34.6 | 29.3 | 26.5 | 0.08 | 3600 |
| `bots/chart_nash` | 29.4 | 0.32 | 27.4 | 26.5 | 25.7 | 36.7 | 30.6 | 29.3 | 25.7 | 39.6 | 32.0 | 29.1 | 0.00 | 3600 |
| `bots/equity_bucket` | 29.2 | 0.33 | 26.5 | 26.7 | 25.0 | 36.6 | 30.9 | 29.3 | 25.0 | 39.5 | 31.9 | 29.1 | 0.00 | 3600 |
| `bots/adaptive` | 28.7 | 0.34 | 26.9 | 25.9 | 24.7 | 37.1 | 29.4 | 28.3 | 24.7 | 42.4 | 35.6 | 33.4 | 0.01 | 3600 |
| `zoo/codex_steal_value_1` | 28.7 | 0.30 | 31.4 | 24.4 | 24.7 | 28.9 | 34.1 | 28.8 | 24.4 | 33.2 | 37.9 | 34.6 | 0.02 | 3600 |
| `bots/push_fold` | 27.7 | 0.32 | 24.7 | 24.9 | 23.8 | 35.4 | 28.9 | 28.6 | 23.8 | 34.6 | 28.7 | 26.0 | 0.01 | 3600 |
| `bots/steal_heavy` | 27.0 | 0.36 | 25.3 | 22.0 | 22.7 | 35.7 | 28.7 | 27.4 | 22.0 | 41.9 | 42.6 | 39.7 | 0.01 | 3600 |
| `zoo/claude_exploiter_1` | 25.6 | 0.38 | 24.3 | 21.5 | 19.4 | 33.9 | 27.8 | 26.6 | 19.4 | 43.7 | 48.5 | 35.7 | 0.00 | 3600 |
| `zoo/claude_shark_1` | 24.9 | 0.31 | 26.2 | 24.0 | 21.8 | 21.4 | 28.9 | 26.9 | 21.4 | 24.8 | 21.7 | 20.4 | 0.07 | 3600 |
| `zoo/claude_grinder_1` | 24.6 | 0.28 | 23.9 | 23.6 | 25.0 | 21.4 | 25.0 | 28.9 | 21.4 | 20.0 | 18.9 | 17.3 | 0.00 | 3600 |
| `zoo/codex_survival_icm_1` | 24.5 | 0.32 | 22.8 | 23.7 | 22.1 | 24.8 | 27.0 | 26.6 | 22.1 | 26.2 | 23.1 | 21.3 | 0.01 | 3600 |
| `zoo/codex_rubric_pressure_icm_1` | 22.3 | 0.37 | 21.1 | 18.8 | 20.1 | 23.2 | 25.7 | 25.1 | 18.8 | 35.0 | 33.0 | 26.7 | 0.04 | 3600 |
| `zoo/codex_chip_ev_1` | 21.1 | 0.35 | 20.3 | 18.5 | 18.1 | 23.0 | 24.4 | 22.3 | 18.1 | 27.7 | 30.1 | 26.5 | 0.00 | 3600 |
| `zoo/claude_maniac_1` | 17.1 | 0.36 | 14.5 | 15.5 | 13.3 | 17.0 | 22.1 | 20.6 | 13.3 | 27.1 | 45.0 | 31.6 | 0.00 | 3600 |
| `starter` | 17.1 | 0.36 | 20.2 | 12.3 | 15.9 | 14.4 | 20.7 | 18.8 | 12.3 | 26.1 | 38.1 | 33.0 | 0.03 | 3600 |
| `zoo/claude_tourist_1` | 16.7 | 0.35 | 17.0 | 12.9 | 13.7 | 14.9 | 24.5 | 17.1 | 12.9 | 24.9 | 41.1 | 2.2 | 0.01 | 3600 |

Paired `bots/final` minus `bots/icm_survival` (same tables):

| variant | Δ points | ±SE |
|---|---:|---:|
| holdem | +1.33 | 0.65 |
| omaha | -0.50 | 0.63 |
| short_deck | +0.03 | 0.59 |
| irish | +0.68 | 0.68 |
| auction | +0.00 | 0.69 |
| discard_reveal | -0.48 | 0.61 |

Paired `bots/final` minus `zoo/codex_adaptive_icm_1` (same tables):

| variant | Δ points | ±SE |
|---|---:|---:|
| holdem | -0.53 | 0.79 |
| omaha | +0.47 | 0.81 |
| short_deck | -1.99 | 0.71 |
| irish | +6.03 | 0.82 |
| auction | -2.03 | 0.84 |
| discard_reveal | -0.33 | 0.72 |

Paired `bots/final` minus `bots/adaptive` (same tables):

| variant | Δ points | ±SE |
|---|---:|---:|
| holdem | +3.12 | 0.76 |
| omaha | +1.56 | 0.57 |
| short_deck | +2.18 | 0.61 |
| irish | +0.61 | 0.64 |
| auction | +3.04 | 0.72 |
| discard_reveal | +3.19 | 0.76 |

Paired `bots/final` minus `bots/steal_heavy` (same tables):

| variant | Δ points | ±SE |
|---|---:|---:|
| holdem | +4.74 | 0.98 |
| omaha | +5.52 | 0.87 |
| short_deck | +4.16 | 0.89 |
| irish | +1.99 | 0.89 |
| auction | +3.75 | 0.97 |
| discard_reveal | +4.12 | 0.92 |

Paired `bots/final` minus `starter` (same tables):

| variant | Δ points | ±SE |
|---|---:|---:|
| holdem | +9.81 | 1.01 |
| omaha | +15.23 | 1.03 |
| short_deck | +10.93 | 1.07 |
| irish | +23.36 | 1.05 |
| auction | +11.74 | 1.05 |
| discard_reveal | +12.65 | 1.11 |

## Mock tournament, 2026-11-12

A mock of the official event on the **unofficial** mini simulator, for 10 top bots, in 3 variants drawn at
random (seed `mock1`, from `holdem`, `omaha`, `short_deck`, `auction`, `discard_reveal`; `irish` excluded):
`short_deck`, `holdem`, `auction`. Raw results: `mock-tournament-2026-11-12.json.gz`
(`{seed, iters, variants, res: {variant: {round: {bot: [[points, place, failures, decisions], ...]}}}}`).
The script that ran it is not in the repo.

- **Format** (per `docs/official-format.md`): 6 rounds weighted 1x to 6x, 5,000 iterations per round, 8 seats,
  2,000 chips, blinds up every 20 hands, 250-hand cap, 50/30/20. Each iteration seats every bot once with
  random seats: 2 tables, the second topped up with bots not already seated, whose finishes do not score.
  Score = sum of round average times weight; par is 12.5 x 21 = 262.5. The standard error is 2-3 points.
- **Field:** `bots/final`, `icm_survival`, `steal_heavy`, `chart_nash`, `adaptive`, and zoo `claude_exploiter_1`,
  `codex_adaptive_icm_1`, `codex_shove_aware_1`, `claude_shark_1`, `codex_rubric_pressure_icm_1`.

| # | bot | short_deck | holdem | auction | mean |
|--|--|--:|--:|--:|--:|
| 1 | `zoo/claude_exploiter_1` | 343.5 | 345.1 | 587.4 | 425.3 |
| 2 | `zoo/claude_shark_1` | 254.2 | 266.8 | 338.9 | 286.7 |
| 3 | `bots/final` | 283.6 | 283.0 | 225.3 | 264.0 |
| 4 | `bots/icm_survival` | 283.0 | 279.0 | 222.4 | 261.5 |
| 5 | `bots/adaptive` | 283.5 | 263.6 | 216.3 | 254.5 |
| 6 | `bots/chart_nash` | 275.8 | 261.5 | 213.4 | 250.2 |
| 7 | `bots/steal_heavy` | 260.5 | 264.8 | 210.0 | 245.1 |
| 8 | `zoo/codex_adaptive_icm_1` | 221.3 | 237.1 | 230.1 | 229.5 |
| 9 | `zoo/codex_shove_aware_1` | 213.5 | 220.3 | 214.4 | 216.1 |
| 10 | `zoo/codex_rubric_pressure_icm_1` | 207.4 | 202.7 | 162.1 | 190.7 |

`zoo/claude_exploiter_1` won all three variants (about 16.5 points per table in `short_deck` and `holdem`, about
28 in `auction`). `bots/final` was the best `bots/` profile in `short_deck` and `holdem` and 4th in `auction`.
No bot failed a decision. Caveats: the `bots/` profiles were tuned on this simulator, and the exploiter
reads opponents, which suits a mixed field.
