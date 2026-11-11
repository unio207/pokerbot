# Mini simulator: what matches the organizers' kit and what does not

`mini_sim.py` is our own re-implementation, used when the kit is not available (it
unlocks only at the variant announcement). Bots written for it use the kit's real
interface, so a bot folder moves to `poker-agent play` unchanged. This page lists how far
the behaviour matches, checked against the competition's Getting started and Format pages
and against the Bay Area kit's source.

## Matches the kit

| Area | Behaviour |
| --- | --- |
| Interface | `act(state, memory) -> (Action, bytes)`; the same `GameState`, `TableConfig`, `Seat`, `Event`, `Action` fields |
| Table | 8 seats (2–10), 2,000 chips, blinds 10/20 up to 2000/4000, a level every 20 hands, 250-hand cap |
| Legal actions | Fold and call when facing a bet; only check when checking is free; raise as a total for the round with `min_amount`/`max_amount` |
| Events | `hand`, `blind`, `fold`, `check`, `call` (chips added), `raise` (total), `board` (new cards), `show`, `win`, `stack` |
| Failed decisions | Exception, timeout or illegal action is played as check, else fold |
| Raises | Not clamped: a total outside the range fails. Whole numbers pass; floats are rounded down |
| Time | 1 ms per decision; overruns spend a 100 ms per-table bank; a timeout empties it; `--bank-ms 0` imitates the upload test |
| Memory | Empty at each table, cut at 64 KB, kept after a timeout or exception, stored after an illegal action |
| Events after a failure | A timeout or exception delivers that turn's events again on the next turn |
| Copies | `agent.py` is imported once and two `Agent()` copies answer turns at random, so state kept on `self` breaks |
| Scoring | Points by place; survivors at the cap split the rest by ICM; same-hand busts rank by starting stack, equal stacks tie and split |
| Seating | Seats reshuffled every table; random starting button |
| Repeatable | A table's cards, seats and any `random` calls a bot makes depend only on the seed and the table number, so the same seed gives the same match, in one process or many |
| Upload check | Rejects imports of `poker_engine`/`pokerkit`, more than 1 MB of code, and libraries the competition machines lack |
| Payouts per table | `--random-payouts` draws a different split of 100 per table |

## Differs from the kit

- **Variant.** Hold'em plus our own versions of the rulesets in `zoo/variants/`, chosen
  with `--variant` (see below). They are built from entrants' reports with guesses where
  facts are unknown. The announced variant's real extra phases, cards and
  actions exist only in the kit. This is the big one.
- **Timing.** Bots run inside the simulator's process, with no message passing, so
  decisions look faster than on the platform. The kit also allows a small delivery
  allowance on top of the 1 ms. Treat our timings as a lower bound and time on the build
  box.
- **Sandbox.** Nothing stops a bot here from opening files or the network; the platform
  does. A bot that imports an allowed library not installed on this computer fails to
  load here but would load there.
- **Raise re-opening.** After a short all-in raise we always let players raise again; the
  kit follows stricter no-limit rules about when a raise re-opens the betting.
- **Seat numbers.** The kit anonymises seat numbers per table; we use 0 to n-1.
- **`shown_cards`.** Not filled in on seats; showdown cards arrive as `show` events only.
- **Antes.** None, as in the kit's default blind schedule.
- **Random payout draw.** Our distribution for `--random-payouts` is our own guess; the
  organizers' ranges are not published.
- **Fillers and field size.** Every seat scores here; the platform fills short tables
  with bots whose finishes do not count.

## Speed and variation

`play` runs tables in several processes at once: half the processors by default,
`--workers N` to change, `--workers 1` for one process. Decision times read slightly
higher with many workers than with one; time a bot with `--workers 1` when it is close to
the limit.

`--vary` draws the hand cap, hands per level and starting stack from the seed and gives
every table its own payouts, so different seeds are slightly different tournaments. The
summary's `rules` shows what was used. Each bot's `vpip` and `pfr` in the summary are the
share of hands it entered by choice, and raised, before the flop: 0 means the bot is not
really playing, which is what a hold'em-only bot does in most other variants.

## Variants

`sim_variants.py` holds one class per ruleset in [`zoo/variants/`](../zoo/variants/README.md),
under the same name. A variant sets the number of hole cards and overrides a few hooks:
the deck, an extra decision phase after a street's cards are dealt, and the showdown
ranking. Play one with:

```bash
python3.12 devtest/mini_sim.py play starter zoo/_template sparring/nit --variant discard_reveal
```

`tools/check_zoo.py --variant <name>`, `practice.py --mini --variant <name>` and the
practice web page's Variant box use the same list. Hold'em deals are unchanged by this:
the same seed gives the same hold'em match as before.

In a variant's own phase a failed decision gets that variant's automatic choice. A
variant action sent with no cards is treated as asking for the automatic choice and is
not counted as failed; the kit may count it. The guesses each variant makes are listed in
its ruleset's "Local testing" section.

## When the kit is available

Use it: the web page and `practice.py` switch to it automatically (see
`docs/event-day-setup.md`). Keep the mini simulator for the things only it reports:
decision times, per-decision failure details, the no-time-bank upload test, and replays
with every bot's cards visible.
