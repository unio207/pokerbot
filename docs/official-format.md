# Official tournament format (Pittsburgh)

From the competition site's **Format** page for NO LIMIT '26 Pittsburgh. This is the
authority; where older notes in `docs/` disagree, this page wins.

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
| 4 | +60 min | 4x |
| 5 | +80 min | 5x |
| 6 | +100 min | 6x |

- Build for 60 minutes after the variant is announced, and keep building between rounds.
- Rounds start 20 minutes apart. Twenty minutes is the gap between starts, not a time
  limit; each round finishes when its iterations complete.
- Each scored round runs **at least 5,000 iterations**; every bot plays one table per
  iteration. (The published rules said 10,000.)
- Round score is average points per table. Results show the average and the finishes in
  every place.
- Final score is the sum of round score times weight.
- Practice runs: about 1,000 iterations every 10 minutes during the build. They never
  count.
- Results normally arrive within the following 20-minute window, so the result of round
  N may not be in hand before round N+1 is snapshotted.

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
- **Results lag a round.** The snapshot for round N+1 can be taken before round N's
  result arrives, so decisions between rounds lean on the practice runs, our own
  simulations and the hand histories, not on the last score.
- **Six practice runs during the build.** At about 1,000 tables each, the standard error
  is roughly 0.6 points per table: enough to spot a broken bot or a large gain, not a
  1-point change.
- **The last snapshot is at +100 minutes.** Work after that changes nothing.
- **Firsts break ties**, which agrees with playing for first place rather than survival.
