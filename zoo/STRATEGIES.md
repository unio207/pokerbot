# Five strategy opponents

These implement strategies A–E from the supplied strategy chat. They are zoo
opponents, not five claimed tournament winners. All were authored by Codex in
this session; separate implementation/review tasks do not imply different models.
Existing `bots/`, tools, and the user's other work were preserved.

| Folder | Strategy | Distinguishing behavior |
| --- | --- | --- |
| `codex_survival_icm_1` | A. Survival-first | Tight opens, narrower short shoves, payout-aware calls; heads-up removes survival premium. |
| `codex_chip_ev_1` | B. Chip-EV push/fold | Estimated shove ranges through 15 BB, chip pot odds plus 2 percentage points; no ICM. |
| `codex_steal_value_1` | C. Small-bet steal/value | Positional min-raises, evidence-based steals, selective small continuation bets, station value bets. |
| `codex_shove_aware_1` | D. Shove-aware counterstrategy | Depth-separated opponent observations, seven range buckets, equity/tie lookups, closing-call ICM. |
| `codex_adaptive_icm_1` | E. Adaptive ICM/exploitation | D plus fold/station/minimum-raise reads, wider cheap steals and adjusted value sizing. |

Each folder contains one standalone, standard-library `agent.py`. Upload/copy that
file alone: bots do not read this document, metadata, other bots, or generator
outputs. Table state persists only through memory bytes. Blinds, player counts,
and payouts come from the SDK state. Unknown phases take the first legal action
at its minimum. This is a fallback, not an implementation of an unknown variant.

## Estimates and limitations

- The opening and shove ranges are implementation estimates from the chat,
  not solved Nash masks. The exact published heads-up masks were not supplied;
  we do not claim the estimated shove ranges reproduce them.
- A/B reuse the starter's equity-versus-random table with explicit conservative
  discounts. C uses a simple independent strength ordering. Their calls are
  deliberately simpler than D/E, preserving strategy diversity.
- D/E contain 169 starting classes × seven range widths (5/10/20/35/50/75/100%).
  Opponent classes follow the starter's random-hand equity ordering, with the
  boundary class included. Actual widths and provenance are in
  `strategy_equity_provenance.json`. This is an approximate opponent model.
- Each D/E table cell uses 5,000 deterministic sampled runouts, with blockers
  removed and ties recorded separately. Total: 5,915,000 offline trials. Worst-case
  sampling standard error is 0.71 percentage points (about ±1.39 points at 95%
  per cell). This excludes range-model error and is not a simultaneous bound
  over all cells. D/E use a 3-point model margin. No rollouts run inside `act`.
- Exact ICM arithmetic does not make an entire poker decision exact. D/E compare
  modeled win/loss/tie utilities only for a closing single-opponent all-in with
  reconstructable contributions and no paid places beyond third. They account
  for eligible pots, excess bets and finishing payouts. Unsupported cases use
  conservative equity/risk estimates. Multiway equity is not independently
  calibrated. A's simpler closing-call model ignores ties.
- All postflop equity estimates are heuristics. Standard hold'em evaluation
  does not cover changed rankings, decks, discards, or card-use restrictions.
- Opponent observations are small, selected samples; depth buckets and sample
  gates reduce overreaction but do not identify opponents with certainty.

## Reproduce and validate

Run from the repository root:

```bash
python3 tools/gen_zoo_equity.py --samples 5000 --output /tmp/pokerbot-zoo-equity.json --embed-to-bots
python3 tools/validate_strategy_zoo.py
python3 tools/check_zoo.py
python3 devtest/mini_sim.py play zoo/codex_survival_icm_1 zoo/codex_chip_ev_1 zoo/codex_steal_value_1 zoo/codex_shove_aware_1 zoo/codex_adaptive_icm_1 starter sparring/nit sparring/shover --tables 200 --seed strategy-zoo-holdout
```

Generation is offline, using the repository evaluator and no installed packages.
The embedded values are sufficient for playing; regeneration is optional.
The validator checks legal actions and bounded memory over 100,000 generated
decisions, recreates agents between calls, and independently checks ICM, pot
conservation, and opponent classifications. It is not an official upload check.

Validation here uses Python 3.11 and the unofficial mini simulator. Use Python
3.12 and the organizers' kit/build box before competition. Host scheduling can
produce millisecond wall-time spikes even in simple sparring bots. A normal-bank
`OK` result does not certify the strict 1 ms upload test; inspect full-decision
timing on the competition hardware.

Use the fixed-field 60-table zoo check to characterize opponents, not to rank
the strategies statistically. The supplied 12–44 point forecasts are not test
results. Keep held-out seeds and opponent compositions for subsequent tuning;
do not repeatedly optimize the zoo opponents themselves.

## Recorded checks

`strategy_validation.json` contains the final raw results. All five passed
100,000 generated decisions in total, 1,258 differential ICM cases, 14 closing-pot
regressions, eight opponent-classification cases, and all 500 simulated tables
(60 per bot in the fixed field, plus 200 mixed tables), with zero failed decisions.

| Bot | Fixed-field points (60 tables) | Mixed-field points (200 tables) |
| --- | ---: | ---: |
| A. Survival-first | 24.0 | 11.30 |
| B. Chip-EV | 20.0 | 8.70 |
| C. Steal/value | 32.0 | 19.05 |
| D. Shove-aware | 31.2 | 15.40 |
| E. Adaptive | 34.3 | 18.20 |

Fixed-field full-decision p99.9 was 84–192 microseconds. Scheduling outliers in
mixed play reached 3.2 ms and used the time bank. Neither these timings nor the
point estimates certify platform performance or a reliable strategy ordering.

## Strategy F: RubricPressure ICM ("Vedaant Seceret Strategies HeHeHe")

`codex_rubric_pressure_icm_1` was added after the five bots above, from Vedaant's design
in [`VEDAANT_SECERET_STRATEGIES.md`](VEDAANT_SECERET_STRATEGIES.md). It was implemented by
Claude (Fable 5.2), not Codex; the folder name is the one the design fixed. It is not
covered by `strategy_validation.json` or by the generator above.

| Folder | Strategy | Distinguishing behavior |
| --- | --- | --- |
| `codex_rubric_pressure_icm_1` | F. RubricPressure ICM | The only bot here that bluffs: small c-bets, turn/river probes and semibluff raises at rubric-set frequencies, switched off when ICM pressure is high. |

- Every decision is a fixed prior plus bounded points, clipped: open and shove fractions
  by players left to act, bluff frequencies by spot (c-bet, barrel, stab, probe, raise).
- Per-seat counters (preflop fold/call/raise, postflop fold when facing a bet) are ignored
  below 10 samples and reach full weight at 24.
- ICM is a rubric (bubble distance, chip leader, shortest stack), not an exact
  calculation. Near the bubble, a weak hand with a good bluffing story checks instead.
- Mixed plays use a deterministic hash of the hand, seat and cards, not a random number.
- All ranges, strengths and frequencies are hand-set estimates. Standard hold'em only.

Checks on Python 3.12 with the unofficial mini simulator:

| Check | Result |
| --- | --- |
| `tools/check_zoo.py` (upload test, then 60 tables against the sparring field) | OK, 19.0 points, 37% firsts, 0 failed decisions |
| 200 mixed tables with A–E, `starter` and `sparring/nit` (seed `strategy-f-holdout`) | 13.25 points (A 11.45, B 12.95, C 12.05, D 12.90, E 17.30, starter 13.60), 0 failed decisions |
| `replay_checks` from `tools/validate_strategy_zoo.py`, 60,000 generated decisions, also with the catch-all handler removed | 0 failures, memory at most 142 bytes |

Full-decision p99.9 was 152–200 microseconds. As above, these small samples describe the
bot; they do not rank it, and nothing here was run on the organizers' kit.
