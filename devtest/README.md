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
| Upload check | Rejects imports of `poker_engine`/`pokerkit`, more than 1 MB of code, and libraries the competition machines lack |
| Payouts per table | `--random-payouts` draws a different split of 100 per table |

## Differs from the kit

- **Variant.** Standard hold'em only. The announced variant's extra phases, cards and
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

## When the kit is available

Use it: the web page and `practice.py` switch to it automatically (see
`docs/event-day-setup.md`). Keep the mini simulator for the things only it reports:
decision times, per-decision failure details, the no-time-bank upload test, and replays
with every bot's cards visible.
