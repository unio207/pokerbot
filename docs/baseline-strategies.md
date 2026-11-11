# Baseline strategies

For an 8-bot sit-and-go scored on finishing place with a 1 ms decision limit, the useful
baselines form a ladder. Each rung is a working bot you can submit, and each one beats
the one below it. `starter/agent.py` implements rungs 1 to 6.

1. **Never-fail skeleton.** Wrap everything in a try/except that falls back to
   check-else-fold, and clamp every raise to the legal range. Errors and timeouts are
   played as check/fold, so a crash costs every hand at that table.

2. **Tight-aggressive preflop chart.** Rank starting hands by equity from a precomputed
   table (169 classes for hold'em) and raise the top slice, wider in late position and
   tighter in early position. Fold the rest. After the flop, bet strong made hands and
   check/fold everything else.

3. **Pot-odds caller.** Call when estimated win chance exceeds the price (call amount ÷
   pot after calling), and raise when it is well above. Estimate postflop strength from
   cheap categories (pair, two pair, flush draw, overcards), not live simulation: two
   entrants reported that live Monte Carlo blows the time limit.

4. **Push/fold when short.** Under roughly 10–15 big blinds, stop making small raises and
   either shove all-in or fold, with a range that widens as the stack shrinks and as
   fewer players remain. Blinds rise every 20–25 hands, so most of each table is played
   at these depths. This is the highest-value rung.

5. **Payout-aware endgame.** Tighten calls when one more elimination moves you up a
   paying place, loosen shoves against stacks that cannot afford to call, then turn
   aggressive three-handed and heads-up. One entrant's bot that folded about 77% of hands
   finished second often and rarely first until it got endgame logic. The kit's ICM
   function is there for this.

6. **Light opponent stats.** Track per table how often each seat raises or folds, and
   steal blinds more from seats that fold a lot. State resets every table and opponents
   are anonymised, so anything longer-term is wasted effort.

## Making it portable to a secret variant

- **Isolate hand strength.** Keep the variant-specific part in one function that returns
  a 0–1 strength score. Rungs 3–6 only consume that number, so a new variant means
  rewriting one function. Bots written only for standard hold'em reportedly broke on the
  Bay Area variant.
- **Tune on the real score.** Measure average points per table against a mixed pool, not
  chips won. Detecting a 1-point difference takes on the order of 1,600 tables per
  version.

## On the day

Submit rung 1 or 2 in the first ten minutes so there is always a scoring bot, then
climb. The last three rounds carry about 71% of the score, so a late improvement is
worth more than an early one.

The points table is announced on the day; the 50/30/20 for the top three reported by one
entrant is unofficial. If the real table pays more places or is flatter, shift toward
survival and away from first-place aggression.
