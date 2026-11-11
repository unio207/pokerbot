# How we gain an edge

Most teams will arrive with nothing and spend the hour getting a bot to run at all, so
the edge is mostly preparation and process, not cleverer poker. In rough order of payoff.

## Biggest levers

1. **Build the field tonight.** Everyone is using AI assistants, so the field will look
   like what an assistant writes by default. Ask several models to "write a bot for this
   kit" ten or twenty times, drop the results into `sparring/`, and tune against that zoo
   instead of the five hand-written opponents.

2. **Mine the hand histories between rounds.** The kit's README says the team page offers
   a hand-history download after each round, with opponents named. Seats are anonymous
   during play, but the histories show what the field is: how many bots never raise, how
   many shove constantly, what ranges they show down. Write the analysis script against
   the kit's sample file beforehand, so on the day one command says "40% of seats are
   dead, widen the steals".

3. **Spend the weighting, not the hour.** Rounds 4–6 are 71% of the score. Upload a safe
   bot in the first ten minutes, use rounds 1–3 as scouting, and aim the best version at
   round 4 onward. Only promote a change that wins on the same seed over roughly 1,600
   tables, and keep the previous upload ready to roll back.

4. **Never fail a decision.** A crashed or slow bot is played as check/fold. In our
   simulator a field of mostly passive bots was worth 41 points per table against a par
   of 12.5. Every broken opponent is a gift, and we must not be one. Note that the
   upload test (no time bank, rejected above 10% failed decisions) keeps always-failing
   bots out of the field, so expect weak and passive opponents more than dead seats. Test timing on the
   team build machine the kit mentions, not only on a laptop.

## Poker edges specific to this format

- **Steal from dead seats.** Track per table which seats have never raised or called.
  Against them, raise any two cards when they are in the blinds. Likely the single most
  profitable rule.
- **Fix the known weakness.** The starter scores only 14.4 against shove-heavy bots.
  Calling ranges against a seat that shoves every hand should widen quickly.
- **Play for first.** With 50/30/20, first is worth as much as second and third together.
  The starter wins often in soft fields but rarely converts in tough ones, so
  three-handed and heads-up aggression is worth tuning.
- **Watch the hand cap.** At the cap, survivors split the remaining points by chip share.
  If tables often reach it, chips near the end are worth points directly, and reckless
  late all-ins cost more than they look.

## Variant-day speed

- **Make the equity generator generic.** `tools/gen_preflop.py` takes about 14 seconds
  for standard hold'em. Extend it to take "number of hole cards" and "how many play at
  showdown" so a new table is one command once the variant is announced.
- **Rehearse a conversion.** Take the Bay Area variant (three hole cards, discard one,
  expose one) and time converting the starter to it.
- **Split roles.** One person owns card scoring for the variant; the other owns testing,
  uploads and field analysis.

## Before relying on any of this

- **Ask about pre-written code.** The rules do not say whether a bot, tools or tables may
  be brought in. If not, the edge becomes knowing exactly what to ask the assistant to
  rebuild.
- **Run everything on the real kit once.** All numbers here are from the unofficial mini
  simulator.

## Top three for tonight

The bot zoo, the hand-history script, and the dead-seat stealing rule.
