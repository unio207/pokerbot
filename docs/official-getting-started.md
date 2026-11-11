# Official "Getting started" page: what it says and what it changes for us

Condensed from a team member's summary of the competition site's Getting started page
(pokerbot.sequoiacap.com). The **Format** page is summarised in [`official-format.md`](official-format.md).

## Facts that override our earlier notes

| Topic | Official page | What we had assumed |
| --- | --- | --- |
| Starter kit | Unlocks at the variant announcement, along with uploads | That accepted teams could download it beforehand |
| Upload rate | One upload per team every 30 seconds | One every 5 minutes (published rules) |
| Upload size | 50 MB uploaded, 200 MB unpacked, 1,000 entries, 1 MB of code in `agent.py` | 50 or 100 MB |
| Upload test | Heads-up, up to 20 hands, against check-or-fold, 1 ms limit and **no time bank**; rejected if the bot does not start, crashes, or fails more than 10% of decisions | Not known |
| No active bot | Forfeits the round with 0 points | Not known |
| Payouts | Read `state.config.payouts`; rounds may draw payouts per table | 50/30/20 as a default |
| Build box | An EC2 Ubuntu machine per team, similar to the tournament runtime, reached by SSH | Mentioned in the kit only |

## Limits

- 1 ms per decision (`state.config.decision_ms`) plus a small delivery allowance.
- 100 ms time bank per table (`state.config.time_bank_ms`). A timeout empties the bank.
  The next table starts full. Local `poker-agent play` always gives the bank; the upload
  test does not.
- 64 KB of memory per table, cut beyond that. About 16 KB is effectively free.
- Python 3.12, standard library, `poker_agent_sdk`, `poker_agent_protocol`, and exactly
  the libraries in `requirements.txt`. No network, no GPU.
- The bot folder is read-only and non-executable; `/tmp` (64 MB) is the only writable
  place. No files kept between tables, no computing between decisions.
- Carrying information between tables breaks the rules.

## Ways a decision fails

- Timeout, exception, or illegal action. The platform then checks if free, else folds
  (or takes the automatic choice in a variant phase).
- Illegal means a kind not offered, or a `raise_to` total outside
  `[min_amount, max_amount]`. Raises are **not clamped**; an undersized raise facing a bet
  folds.
- Check and call are never offered together. Reference hold'em offers no fold when
  checking is free.
- Float amounts are rounded down, so a computed size can land one chip under the minimum.
  Use ints and clamp.
- After a timeout, exception or crash the previous memory is kept and that turn's events
  are delivered again. After an illegal action the returned memory **is** stored.
- Memory that makes `act` raise comes back unchanged on every later turn at that table,
  so a bad memory blob can lose the whole table.

## Process model

- The platform imports `agent.py` once and forks copies. Load tables at import. Threads
  started at import do not exist in the copies.
- A copy that crashes or stalls is killed and restarted, with a limited number of
  restarts per round. An exception inside `act` fails only that decision.
- The team page shows decisions, missed decisions, restarts and the latest errors per
  round. It never shows what the bot prints.

## Hand histories

After each round the team page offers every table our bot played: opponents named, our
cards every hand, others' cards when public, and the actions played for our failed
decisions. Showdowns reveal all hole cards of everyone who reaches them.

## How the starter bot stands against this

- **Crash safety:** `act` is wrapped; any exception returns check/fold and the memory it
  was given. Memory is parsed defensively and rebuilt if unreadable.
- **Raise legality:** all raise totals are ints and are clamped to the legal range before
  being returned.
- **Unknown events and phases:** unknown event kinds are ignored; an unknown phase takes
  the first legal action at its minimum, which is the automatic choice.
- **Payouts and table settings:** read from `state.config`, not hard-coded.
- **Speed:** about 60 µs typical with two hole cards. The placeholder scoring for three
  or four hole cards is slower (about 140–250 µs typical, occasionally over 1 ms). With
  no time bank in the upload test, replace it before uploading a bot for such a variant.
- **Upload test:** `python3.12 practice.py <bot> --mini` now starts with an imitation of
  it (heads-up against check-or-fold, 20 hands, no time bank) and reports the share of
  failed decisions against the 10% rejection line.

## What this changes in our plan

1. **We cannot get our kit before the event.** Until the announcement, practice runs on
   the mini simulator. The only real kit available beforehand is the Bay Area one a
   participant published, which has the Bay Area variant.
2. **First ten minutes on the day:** download the kit, install it, start
   `python ui/server.py` from its environment so the page uses the real engine, and
   upload a legal bot immediately so there is always an active bot.
3. **Uploads are cheap.** At one per 30 seconds the limit is our testing, not the rate.
   Keep the previous upload selectable on the team page as the rollback.
4. **Time on the build box.** Benchmark `act` there, and compare the 99th percentile and
   the maximum to 1 ms, not the average.
5. **Set up beforehand:** SSH key added to the portal, API key generated, and the
   connection to the build box tested (it reports its opening time before it opens).
6. **The Format page** is summarised in [`official-format.md`](official-format.md).
