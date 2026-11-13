# Farming weak bots, and practice 6

Posted as https://github.com/unio207/pokerbot/issues/21

Research only. Vedaant asked whether farming the weaker bots is a good plan. Measured on practice 6 (`bb8a3341`, 5,000 tables), played by upload `f4025ac6` (45,312 B — a much smaller file than any before; not on GitHub. Active now is `1b9ad55e`, 73,996 B, also not on GitHub).

## Result of this run: 76th of 112, 11.02 ± 0.26 points — our lowest yet
This build opens 55% of hands first in and, in the big blind, **calls a raise 54%** (fold 40%, re-raise 6%). The top tier's big blind: fold 66 / call 13 / re-raise 21%. It is the flat-calling leak from #18/#20 at full size, and other teams' raises into our big blind earn them +0.12 to +0.20 each.

## Tiers
Teams ranked by points/table in this run: **top** = best 20% (≥16.2), **weak** = bottom 30% (≤10.5, down to 0.4), **mid** = the rest. A table has on average about 2 weak, 3.5 mid and 1.4 top opponents.

## Short answer
Farming weak bots is worth doing, **we already do it nearly as well as the top 5**, and it is not what separates them from us. They win chips from every tier; we win only from the weak tier and give it back to everyone else.

| Net big blinds won per table, by who it came from | Us | Top 5 |
|---|---|---|
| Weak tier | **+5.5** | +6.8 |
| Mid tier | **−1.9** | +4.3 |
| Top tier | **−3.8** | +1.7 |
| From us | – | **+3.8** |

- Matching the top 5 against weak bots is worth +1.3 bb/table. Matching them against mid and top is worth **+11.7**.
- Per seat, a top-5 team takes about as much from us (3.8 bb from one seat) as from a weak bot (~3.8 bb per weak seat). **To the top teams we are one of the bots being farmed.**

## Our score depends on who we sit with; theirs doesn't

| Weak opponents at the table | 0 | 1 | 2 | 3 | 4+ |
|---|---|---|---|---|---|
| Us: points (1st %) | 7.96 (8%) | 8.75 (10%) | 10.53 (13%) | 13.18 (18%) | 14.84 (22%) |
| Top 5: points (1st %) | 17.90 (23%) | 18.88 (23%) | 20.20 (26%) | 20.03 (26%) | 19.42 (24%) |
| Our tables | 388 | 1,219 | 1,650 | 1,158 | 585 |

| Top-tier opponents at the table | 0 | 1 | 2 | 3 | 4+ |
|---|---|---|---|---|---|
| Us: points | 13.13 | 11.37 | 10.38 | 8.85 | 8.06 |
| Top 5: points | 18.74 | 21.01 | 18.41 | 17.77 | – |

We swing 7 points between soft and hard tables; they swing about 2. We are above par only when 3+ of the 7 opponents are weak (35% of tables). Seating is random, so we cannot choose soft tables — the only lever is how we play each opponent.

## How to farm weak bots better (the +1.3)
- **Weak bots do not fold more; they call more.** Big-blind response to a first-in raise: weak fold 70 / call 24 / re-raise 7; mid 74 / 18 / 8; top 66 / 13 / 21. Facing any raise weak bots call 14% (top 6%).
- So against a weak big blind: raise for value with a wider range and bet bigger after the flop; **do not bluff them**. Our raise into a weak big blind earns +0.138 per attempt; the top 5 earn +0.334 from the same seats.
- 29% of all busts are weak bots, and knockouts of weak bots are split evenly (us 0.34 per table, top 5 0.33). We are not missing their chips.

## How to stop being farmed (the +11.7)
- Our raise into a **top-tier** big blind loses: −0.067 per attempt (38% fold, 21% re-raise). Into mid: +0.047. The top 5 make +0.154 and +0.264 in the same spots.
- This is the same list as #20: re-raise or fold instead of calling, bet/raise instead of check/call after the flop, and fold to re-raises from players who re-raise often.

## Suggestion: one in-table opponent stat
If the kit lets the bot keep state across hands at a table (please confirm: memory limit is 64 KB in the rules card), track per seat how often it **calls** a raise and how often it **re-raises**:
- seat calls a lot, rarely re-raises → weak/caller: open wider into its blind, value-bet larger, no bluffs;
- seat re-raises 15%+ → strong: tighten opens into its blind, never raise-fold light, continue only with the top of the range.
A table is 100+ hands, so both rates settle within the first 30–40 hands.

## Caveats
- One practice run with a different build from rounds 1–2; the tier pattern (who we win from) should be re-checked on round 2 data if Henry wants it confirmed for the main bot.
- Tiers are from this run's results, so they include us-specific match-ups. Chip flow splits each pot's losses among winners in proportion to what they won; it is an attribution, not exact.
- Top-5 figures come from 1,591 of their tables, all of which include us.
