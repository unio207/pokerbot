# Omaha (four hole cards)

| | |
| --- | --- |
| Name | `omaha` (the key in each bot's `VARIANTS` table) |
| Status | practice: our own pick of a likely twist; extra hole cards with a rule on how many play |
| Source | Standard Omaha hand rules with this tournament's no-limit betting, written down by us on 2026-11-10 |
| Playable on the mini simulator | Yes |

## Summary

Hold'em with four private cards, where a hand must use **exactly two** of them and
**exactly three** board cards. Betting stays no-limit. Strong hands are common, and a bot
that takes the best five of all nine cards misreads its own hand.

## How a bot recognises it

- `state.config.variant`: unknown in a kit; `omaha` on the mini simulator.
- Signs in the state: four cards in `state.cards`.

## Cards

- Private cards dealt: 4, before the first betting round.
- Private cards that play at showdown: exactly 2 of the 4, with exactly 3 of the 5 board cards.
- Board: as the base game.
- Deck: as the base game.
- Hand ranking: as the base game.

## Extra decision phases

None.

## Betting

As the base game: no-limit, not pot-limit.

## State and events

- New or changed `GameState` fields: `state.cards` holds 4 cards.
- New event kinds: none.
- Where opponents' public cards appear: `show` events at showdown, with all 4 cards.

## Table settings and scoring

As the base game.

## What it changes for strategy

- Four cards make six two-card combinations, so everyone holds something. One pair and
  weak two pair are worth much less than in hold'em; the nuts matters.
- The exactly-two rule traps naive bots: four cards of one suit on the board give no
  flush without two of that suit in hand, and one ace in hand does not make an ace-high
  flush with four suited board cards. A pair on the board with one matching card in hand
  is trips, not a full house, unless a second hole card helps.
- Before the flop, hands are close in value: coordinated hands (suited aces, connected
  cards, pairs with suits) beat a single high pair with junk.
- Evaluating 6 hole pairs times 10 board triples is 60 five-card hands per look. Check
  the time against 1 ms.

## What a bot must implement

- [ ] `detect`: four cards in `state.cards`.
- [ ] `phases`: none.
- [ ] `strength`: best hand using exactly two private cards and exactly three board
      cards; before the flop, a score of the four cards together.
- [ ] Tighter value thresholds than hold'em.

## Local testing

The mini simulator plays this variant (class `Omaha` in
[`devtest/sim_variants.py`](../../devtest/sim_variants.py)):

```bash
python3.12 tools/check_zoo.py --variant omaha zoo/<bot>
```

The simulator makes these choices; a bot must not depend on them:

- Betting is no-limit. A real event could cap raises at the pot, which would show up as
  a lower `max_amount` on the raise action: always read it.
- `state.config.variant` is `omaha`.

## Open questions

- Whether a real event would use pot-limit betting or a high-low split.
