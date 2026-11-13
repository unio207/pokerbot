# Strategy research prompt

> **Written before the Pittsburgh regional (2026-11-12) and left as it was.** The prompt is kept
> as it was sent. Its format figures are the pre-event ones: the weights were 1, 2, 3, 5, 8, 13,
> practice runs were 2,500 to 10,000 tables, and results arrived within seconds. Its "about 21
> points per table" is hold'em on our own simulator. What happened:
> [`pittsburgh-results.md`](pittsburgh-results.md).

Paste the block below into each model. It is self-contained and asks for the same output
structure from each, so the answers line up for comparison.

- The table settings in the facts section are from the official Format page for
  Pittsburgh (`docs/official-format.md`).
- The expected-points figures in sections 2 and 11 will be guesses from every model.
  Section 4's ranges are the part worth pasting into the bot and running through
  `practice.py`.

```text
You are advising a two-person team entering an in-person poker-bot tournament tomorrow.
Research and reason carefully, then recommend concrete strategies we can implement and
test. Be specific and quantitative. Where you are unsure, say so and give your best
estimate with a confidence level; do not pad with generic poker advice.

## The competition (facts we have)

Format
- 60 minutes to build a Python 3.12 bot from a starter kit. AI coding assistants are
  allowed for building. The bot itself runs offline: no network, no LLM calls.
- The poker variant is SECRET until the build starts. It is a no-limit hold'em
  derivative. A previous regional used: three hole cards, and after the flop every
  player discards one face down and exposes one of the two they keep. Ours will differ.
- Tables: 8 bots, sit-and-go, 2,000 chips each. Blinds start at 10/20 and rise every
  20 hands (10/20, 20/40, 30/60, 50/100, 80/160, 125/250, 200/400, 300/600,
  500/1000, 800/1600, 1200/2400, 2000/4000). A table ends when one bot has all the
  chips or at a hand cap of 250 hands.
- Scoring: points by finishing place, reported default 50/30/20 for 1st/2nd/3rd and 0
  for the rest (par = 12.5 per table). The split can vary by table and is given to the
  bot in the table config. At the hand cap, survivors split the remaining points by ICM
  (Malmuth-Harville) on their chip stacks.
- Six scored tournaments, starting 20 minutes apart, each at least 5,000 tables. Final
  score = sum of (tournament number x average points per table), so tournaments 4-6 are
  71% of the total. Each tournament snapshots our active bot at its start; its result
  usually arrives during the following 20 minutes. We may upload a new bot every 30
  seconds. Unscored practice runs of about 1,000 tables happen every 10 minutes during
  the build. Ties are broken by share of tables won.
- Every upload first plays a test match with NO time bank and is rejected if more than
  10% of its decisions fail.
- The field is the other teams' bots, all built in the same hour, mostly by students
  with AI assistants. Expect some bots that crash or time out (the platform plays
  check-else-fold for them), some that shove constantly, and many tight heuristic bots.

Bot constraints
- Interface: act(state, memory) -> (action, memory_bytes). Actions: fold, check, call,
  raise-to-amount, plus variant-specific actions.
- 1 ms per decision, measured by the platform. A 100 ms time bank per table absorbs
  overruns. A timeout, exception or illegal action is played as check-else-fold.
- Stateless between calls. The only memory is a per-table byte blob (keep under 16 KB),
  empty at the start of every table. Opponent seats are anonymised per table, so
  nothing can be learned across tables.
- The bot sees: its cards, board, pot, amount to call, legal actions with raise range,
  every seat's stack/bet/status, button, blind level, hands until the next level,
  players remaining, bust order, payouts, and all public events (including cards shown
  at showdown; all showdown hands are revealed automatically).
- Available libraries: standard library, NumPy, SciPy, pandas, scikit-learn, PyTorch
  (CPU), LightGBM, XGBoost, ONNX Runtime, Numba, eval7 (a fast standard hold'em
  evaluator). An ICM function is provided. Lookup tables can be shipped with the bot
  (upload limit 50 MB) and loaded at import time.

Our current baseline
- Open-raise chart by position when deep; shove-or-fold preflop at 12 big blinds or
  fewer; tighter all-in calls one place off the points; pot-odds play after the flop
  using a hand-category heuristic; a small per-table record of how often each seat
  raises. In our own simulator it scores about 21 points per table in a mixed field,
  41 against mostly passive bots, and 14 against aggressive shove-heavy bots.

## What I want from you

Answer every section below, in this order, with these exact headings.

### 1. Format analysis
What does this scoring and structure reward? Cover: the value of 1st vs 2nd vs 3rd under
50/30/20, how much survival is worth vs chip accumulation, how the fast blind schedule
changes things (how many hands are realistically played deep vs short), what the ICM
split at the hand cap implies, and how the 1x-6x weighting should shape what we do in
the hour. Give numbers.

### 2. Candidate strategies
Propose 4 to 6 distinct overall strategies (not variations of one). For each: a
one-line description, the core decision rules with concrete thresholds (ranges as
percentages of hands, stack depths in big blinds, bet sizes), which opponent types it
beats and loses to, expected points per table against (a) a passive/broken field,
(b) a tight heuristic field, (c) an aggressive shove-heavy field, implementation time
in minutes, and risk of bugs or timeouts.

### 3. Ranking and recommendation
Rank the candidates for this specific event and name one to build first and one to
evolve into for tournaments 4-6. Justify with the format analysis, not general
principles.

### 4. Preflop detail
Give concrete tables: open-raise ranges by position for 8, 6, 4, 3 and 2 players at
deep stacks; shove ranges by stack depth (2 to 15 big blinds) and position; calling
ranges against an all-in by stack depth and pot odds; adjustments on the bubble (4
players left) and when in the points. State where your numbers come from (Nash
push/fold, ICM solutions, your own estimate).

### 5. Postflop detail
A decision procedure that fits in 1 ms of Python without rollouts: how to score a hand,
bet sizing, when to continuation-bet, when to give up, multiway adjustments, and how
much postflop play matters at all given the blind schedule.

### 6. Endgame
Three-handed and heads-up play: ranges and aggression, and how to convert second places
into firsts. Our baseline finishes 1st far more often than 2nd or 3rd in soft fields
but drops to even in aggressive ones.

### 7. Exploiting this field
How to detect and exploit, within one table and with a tiny memory: bots that always
check/fold, constant shovers, calling stations, min-raisers, and tight bots. Give the
statistic to track, the sample size before acting on it, and the adjustment.

### 8. Adapting to an unknown variant
The variant is revealed at the start of the hour. Give a checklist for converting a
standard hold'em bot in under 15 minutes, and specific guidance for likely twists:
extra hole cards with discards, exposed cards, changed hand rankings, short deck,
extra betting or bidding phases, antes or bounties. What should be precomputed in
advance versus computed on the day?

### 9. Using the hour and the six tournaments
A minute-by-minute plan for the 60-minute build and the two hours of scored rounds:
what to upload when, what to measure between rounds, how many simulated tables are
needed to trust a change (give the statistics), and when to stop changing things.

### 10. What could go wrong
The five most likely ways a team loses points in this format, and the guard for each.

### 11. Summary table
One table: strategy name, expected points per table in fields (a)/(b)/(c), build time,
main risk, your confidence (low/medium/high).

Rules for your answer
- Use numbers everywhere a number is possible. "Play tighter" is not an answer; "open
  the top 15% from early position" is.
- Mark each claim as [solved/known], [estimate], or [guess].
- Do not recommend anything that cannot run in 1 ms in Python or that needs network
  access or state across tables.
- If you believe any of the facts above lead to a counter-intuitive best strategy, say
  so prominently at the top.
```
