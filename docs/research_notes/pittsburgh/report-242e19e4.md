# Tournament 242e19e4: what went well

Analyzed the complete downloaded file: 10,000 scored Team Allow It appearances,
1,091,202 hands while alive, and 1,327,755 betting/discard decisions.
Replay-derived score: **12.782 points/table**. Positive early-table results and
more second-place finishes drove the improvement; heads-up conversion remains weak.

## Results compared with the latest existing cached run

Baseline: tournament `ca825b02-0e0e-4306-9d7b-ef0ff04e51d4`, a cached prefix of
10,003 tables. This is an unpaired comparison across rounds, not a controlled bot test.

| Metric | Previous cached run | This run |
|---|---:|---:|
| Points/table | 12.352 | 12.782 |
| First | 8.05% | 7.78% |
| Second | 15.97% | 17.92% |
| Third | 17.69% | 17.58% |
| Top three | 41.71% | 43.28% |
| Top four | 58.48% | 59.95% |
| Seventh/eighth | 17.02% | 16.47% |
| Reach a hand starting heads-up | 23.67% | 25.31% |
| Win after reaching heads-up | 33.49% | 30.15% |

More second places account for approximately **+0.59 points/table**; fewer wins
subtract approximately 0.13. Net improvement is **+0.430 points/table**, or 3.5%.
The rough independent-table 95% interval for that improvement is **-0.02 to +0.88**.
This is encouraging, but does not establish that a particular code change improved the bot.

## What worked

1. **Reliable execution.** Zero automatic fallback events, across all 1,327,755
   recorded decisions. No timeout/illegal-action/exception fallback is recorded in this file.
2. **Positive early-table play.** With 5–8 players alive, recorded tournament equity
   increased **+0.951 points per original table**, versus +0.456 previously. This phase
   was positive in each of five consecutive 2,000-table blocks: +0.52, +0.68, +1.14,
   +1.23, and +1.18 points/table.
3. **Strong observed results in hands where we shoved preflop.** Those hands contributed
   +2.85 points/table at 5–8 players, +2.33 at 3–4, and +0.58 heads-up: **+5.77 total**.
   These are whole-hand realized equity changes, not the causal value of the shove.
   Postflop-aggressive hands outside the preflop-all-in categories contributed another
   **+2.73 points/table**. These are useful behaviors to preserve while testing changes.
4. **More paid finishes.** 4,328 of 10,000 tables paid points: 778 firsts, 1,792 seconds,
   and 1,758 thirds. The improvement was predominantly survival into second, not more wins.

## Where the improvement actually came from

| Players alive | Previous equity change/table | Current | Change |
|---|---:|---:|---:|
| 5–8 | +0.456 | +0.951 | +0.495 |
| 3–4 | -0.368 | -0.297 | +0.072 |
| 2 | -0.236 | -0.373 | -0.137 |
| Total above starting 12.5 | -0.148 | +0.282 | +0.430 |

Within the 5–8-player phase, hands with no voluntary preflop contribution lost
3.57 points/table versus 4.04 previously: about **0.47 of the 0.50 early-phase gain**.
That category includes checks from the big blind and later postflop play, so it is
not a clean measurement of folding quality. Preflop shove results were nearly unchanged
(+2.85 versus +2.81); postflop-aggressive results actually declined (+2.19 versus +2.33).
It would be misleading to credit the improvement to stronger aggression or better cards
without further analysis. Opponent changes and runout variance remain explanations.

## Next focused experiment

Investigate heads-up big-blind defense while preserving the effective early-game policy.
Heads-up small-blind hands added +0.25 points per original table; big-blind hands lost
**0.62**, producing the net -0.37. At 10–25 effective big blinds, our first response
to a non-all-in raise was a fold **71.3%** of the time (4,846 opportunities), versus
41.5% among the other observed players. Against shoves at <=10 effective big blinds,
we folded **84.1%** of the time (8,283 opportunities), versus 57.2% for those opponents.
These are hypotheses for range/raise-size analysis, not evidence to blindly match the field.
We also entered heads-up with only 37.5% of the chips on average; low win conversion is
partly explained by arriving behind. Winning 763/2,531 heads-up appearances is distinct
from 778 total firsts because some tables resolve without a hand starting heads-up.

## Validation, limits, and faster reuse

- The SDK reader validated every public/private pair, own-card alignment, and automatic
  event reference. The audit checked duplicate tables, chip conservation on every hand,
  and reconciliation of stage equity changes to final points. All passed.
- One table ended with multiple surviving players; the hero's recorded final payout
  still belongs to the 0/20/30/50 distribution. Final recorded equity is authoritative.
- The descriptive opponent ranking is 60/112 observed scored teams. This is not an
  official tournament rank: opponents are observed only at our tables, with unequal samples.
- These are realized outcomes, not all-in-adjusted equity or a causal strategy evaluation.
  The download does not identify the submitted bot version. Optional organizer resampling,
  if enabled, can make official scores differ from the replay's first continuation.
- [`scripts/audit_history.py`](scripts/audit_history.py) audits the complete 149 MiB download in **16.36 seconds** on the analysis
  machine, streaming one table at a time. `242e19e4-audit.json` contains the checks,
  five block summaries, and five large positive hands for inspection.
- `242e19e4.pkl` caches the detailed aggregate. Rerender `242e19e4-stats.txt` with
  `python3 rep.py 242e19e4.pkl`; no repeat download or replay scan is needed.
- `242e19e4-baseline.json` preserves the prior-run summary independently of its temporary cache.

The artifacts are in [`results/242e19e4`](results/242e19e4/README.md), including a
download command and source checksum. Full audit command, from the repository root:

```sh
python3 docs/research_notes/pittsburgh/scripts/audit_history.py hand-history/hands-242e19e4-657a-4a4f-9819-85b9850570fa.jsonl.gz /tmp/242e19e4-audit.json
```
