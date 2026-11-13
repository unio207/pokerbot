# Official tournament format (Pittsburgh)

From the competition site's **Format** page for NO LIMIT '26 Pittsburgh, read before the
event. Where older notes in `docs/` disagree, this page wins. Where the regional itself
(2026-11-12) differed from the page, the line says so; what happened is in
[`pittsburgh-results.md`](pittsburgh-results.md).

## One table

| Setting | Value |
| --- | --- |
| Players | 8 |
| Starting stack | 2,000 chips |
| Starting blinds | 10 / 20 |
| Blind increases | Every 20 hands |
| Hand cap | 250 |
| Team limit | 2 members |

A table ends when one bot holds every chip or the table reaches the hand cap.

## Points by place (default)

| Place | Points |
| --- | --- |
| 1st | 50 |
| 2nd | 30 |
| 3rd | 20 |
| 4th–8th | 0 |

At the hand cap, surviving bots split the remaining points by ICM on their stacks. The
Getting started page adds that rounds may draw payouts per table, so read
`state.config.payouts`.

## Schedule and scoring

| Round | Starts | Weight |
| --- | --- | --- |
| 1 | When the build ends | 1x |
| 2 | +20 min | 2x |
| 3 | +40 min | 3x |
| 4 | +60 min | 5x |
| 5 | +80 min | 8x |
| 6 | +100 min | 13x |

The Format page's table read 1x to 6x. Pittsburgh's competition record said `fibonacci`, and
the final totals fit 1, 2, 3, 5, 8, 13 (32 in all; rounds 4 to 6 are 26 of the 32).

- Build for 60 minutes after the variant is announced, and keep building between rounds.
- Rounds start 20 minutes apart. Twenty minutes is the gap between starts, not a time
  limit; each round finishes when its iterations complete.
- Each scored round runs **at least 5,000 iterations**; every bot plays one table per
  iteration. (The published rules said 10,000. Pittsburgh played 20,000.)
- Round score is average points per table. Results show the average and the finishes in
  every place.
- Final score is the sum of round score times weight.
- Practice runs: about 1,000 iterations every 10 minutes during the build. They never
  count. (At Pittsburgh: 2,500 to 10,000 tables, and they went on between the scored rounds.)
- Results normally arrive within the following 20-minute window, so the result of round
  N may not be in hand before round N+1 is snapshotted. (At Pittsburgh a finished run's
  results were on the portal within seconds, and a round took about 10 minutes.)

## Bots and snapshots

- Each upload becomes the active bot once it is ready, unless a newer upload is already
  active. Any earlier ready upload can be switched back to.
- Each round freezes a snapshot of every team's active bot at its start. Later uploads
  apply to later rounds.
- No active bot at a round's start: that round scores zero.
- The organizers can freeze uploads and active-bot changes competition-wide.
- Default decision allowance 1 ms. A timeout, error or illegal action checks when free,
  otherwise folds.
- Upload `agent.py` or a zip with `agent.py` at its root; default limit 50 MB.

## Fairness and ties

- Seats are randomized each iteration. Short tables are filled with bots not already
  seated; a filler's finish never scores for its team.
- Several bots busting in one hand: the one with more chips at the start of the hand
  places higher.
- Memory starts empty at every table and seat IDs are anonymized, so bots cannot learn
  across tables.
- Equal final totals are ordered by countback: the share of tables won in each round,
  times that round's weight, summed; then the same for second places, and so on.
- A disqualified team has no rank and sits out later rounds.

## Regionals and finals

Regionals in Boston, Stanford and Pittsburgh. Five teams from each, plus five wildcards,
are invited to finals. Finals use the same format with a different variant.

## What this means for us

- **Our simulator's defaults already match:** 8 seats, 2,000 chips, 10/20 blinds rising
  every 20 hands, 250-hand cap, 50/30/20.
- **Results did not lag.** We planned for round N's result arriving after round N+1's
  snapshot. It arrived in time, with every team's score, and it and the hand histories were
  the only evidence that tracked the field; our own simulations did not.
- **Practice runs all evening.** Eight at Pittsburgh, four of them between scored rounds.
  The portal's margin (about two standard errors) was 0.68 at 2,500 tables, 0.45 to 0.50 at
  5,000 and 0.31 to 0.38 at 10,000: a candidate can be judged on one.
- **The last snapshot is at +100 minutes.** Work after that changes nothing.
- **Firsts break ties**, which agrees with playing for first place rather than survival.
