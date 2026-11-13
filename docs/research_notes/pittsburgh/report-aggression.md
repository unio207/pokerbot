# Do we just need to be more aggressive?

Posted as https://github.com/unio207/pokerbot/issues/23

Research only. Vedaant's question: to close the gap, do we just need to be more aggressive?

**Answer: not in general. We need to be aggressive in four specific places, and passive in none.** Across the whole field, how *often* a team raises first in or puts money in has almost no link to its score. What separates the top is **what they do instead of calling**: they re-raise or fold. Calling is the habit that predicts losing.

## Method
For every team at our tables (109–112 teams, each with 300+ tables) I computed the same behaviour measures and correlated them with points per table, separately for rounds 1, 2 and 3. "Top 10" = the ten best teams that round; quartiles are by points.

## What predicts points across the field

| Measure | Correlation with points (R1 / R2 / R3) | Top 10 (R3) | Middle half | Bottom quarter | **Us (R3)** |
|---|---|---|---|---|---|
| Heads-up BB: re-raise a button raise | +0.35 / +0.65 / **+0.55** | 64% | 24% | 15% | **10%** |
| Heads-up button: raise | +0.59 / +0.59 / +0.47 | 82% | 69% | 60% | **70%** |
| When continuing vs a raise, share that is a re-raise | +0.33 / +0.50 / +0.46 | 72% | 44% | 33% | **29%** |
| Heads-up BB: call a shove | +0.24 / +0.46 / +0.30 | 54% | 38% | 29% | **15%** |
| Facing a raise: call | −0.38 / −0.36 / −0.43 | 6% | 10% | 14% | 8% |
| After the flop: call without ever betting | −0.29 / −0.46 / −0.48 | 9% | 14% | 21% | 10% (was 24%) |
| First in: limp | −0.49 / −0.50 / −0.40 | 0.8% | 1.1% | 6.2% | 0.5% |
| **First in: raise** | +0.34 / +0.37 / **−0.01** | 30% | 30% | 33% | 26% |
| **Hands with money in voluntarily** | −0.16 / +0.12 / −0.24 | 29% | 25% | 32% | **20%** |
| After the flop: bet or raise share | −0.04 / +0.19 / +0.14 | 41% | 45% | 41% | **54%** |

Reading it:
- **Raising more hands first in does not predict winning** (correlation −0.01 in round 3; the bottom quarter opens the most). Round 2 confirmed it on us: we opened as wide as the top 5 and gained nothing.
- **Betting more after the flop does not predict winning either.** In round 3 we bet or raised on 54% of flops seen, more than the top 10 (41%). That part is done; more would be overshooting.
- **The top 10 choose re-raise over call 72% of the time; we choose it 29%**, below the bottom quarter (33%). This gap is widening: the top 10 were at 56% in round 1, 59% in round 2, 72% in round 3.
- **Heads-up is where aggression pays most directly**, and it decides 1st vs 2nd (50 vs 30 points). The top 10 re-raise a button raise 64% of the time from the big blind and call a shove 54%; we do 10% and 15%, both below the bottom quarter. We win 33.5% of heads-up matches; they win ~66%.
- **We are the tightest team in the field overall** (20% of hands played; every quartile is 25–32%), but this has no clear link to points, so loosening across the board is not the lever.

## So: where to add aggression, and where not

**Add (ordered by evidence):**
1. **Heads-up big blind:** re-raise or reshove a button raise ~55–65% (we: 10%); call ≤10bb shoves ~50% (we: 15%).
2. **Facing a raise at a full table:** turn calls into re-raises. Target re-raise share of continues ≥60% (we: 29%): re-raise ~12–17% of hands, call ≤6%. From the big blind, re-raise ~35–40%.
3. **Heads-up button:** raise ~82%+ (we: 70%).
4. **Short stack:** shove first in before reaching 5bb; 9.8% of our round 3 busts were blind-outs (top 5: 1.8%).

**Do not add:**
- More first-in opens from early seats, more hands overall, or more postflop betting. None of these separates the top from the middle, and the third is already above the top 10.
- Any calling. Every calling measure is negatively linked to points in every round; our two calling experiments (round 2 low pairs, practice 6 at 54% big-blind calls) were our two worst results.

## How much is it worth
From the round 3 stage breakdown (#22), the gap to the top 5 is 7.25 points/table: big blind at full tables 5.0, heads-up 1.0, everything else ~1.2. Items 1–3 above act on exactly the first two. A realistic first target is half the big-blind gap plus half the heads-up gap, about **+3 points/table**, which would move us from ~64th to roughly the top 25. That is an estimate from differences between teams, not a tested result.

## Caveats
- Correlation across teams is not proof of cause: strong teams may re-raise more because they also play the later streets better. The evidence that it is causal for us is in #18/#20: with the same cards our re-raises earn +1.1 to +1.4 and our calls −0.2 to −0.9.
- Measures are from tables that include us, 300–700 tables per team.
- Three rounds only; the round-to-round drift of the top 10 suggests the target is still moving.
