# Auction (bid for a third hole card)

| | |
| --- | --- |
| Name | `auction` (the key in each bot's `VARIANTS` table) |
| Status | practice: our own pick of a likely twist. An entrant's mock of this tournament has a `bid` hook, and MIT Pokerbots 2024 used an auction for an extra card |
| Source | Our own rules, modelled on those two, written down on 2026-11-10 |
| Playable on the mini simulator | Yes |

## Summary

Hold'em with one sealed-bid auction per hand. After the flop is dealt, each player still
in the hand bids chips for a third private card. The highest bidder gets the card and
pays the second-highest bid into the pot. The bot must price information and equity in
chips, inside a tournament where chips are survival.

## How a bot recognises it

- `state.config.variant`: unknown in a kit; `auction` on the mini simulator.
- Signs in the state: `state.phase == "bid"`. After winning an auction a player holds
  three cards while the board is out.

## Cards

- Private cards dealt: 2, before the first betting round. The auction winner gets a 3rd.
- Private cards that play at showdown: best five of all private cards (2 or 3) and the
  5 board cards.
- Board: as the base game.
- Deck: as the base game.
- Hand ranking: as the base game.

## Extra decision phases

### `bid`

- When: after the flop is dealt and before flop betting. Every player still in the hand
  who has chips bids once, at the same time. Players who are all-in do not bid. There is
  no auction when fewer than two players remain in the hand.
- `state.phase`: `"bid"`
- Legal action kinds: `bid`, with `min_amount` 0 and `max_amount` the player's stack.
- Action to return: `Action("bid", amount)` with a whole number in that range.
- Automatic choice (played on a failed decision): a bid of 0.
- Outcome: the highest bidder receives one card from the deck and pays the
  **second-highest** bid into the pot. If several players tie for the highest bid, each
  of them pays their own bid and each receives a card. A bid of 0 never wins. Chips paid
  are not a bet: they do not need to be called and they go to the main pot.
- What others see: every bid, and who won at what price. The card stays private.

## Betting

As the base game. Chips paid in the auction come out of the winner's stack, so the winner
can be left short or all-in for the betting that follows.

## State and events

- New or changed `GameState` fields: `state.cards` holds 3 cards for an auction winner.
  `state.pot` includes chips paid in the auction.
- New event kinds: `bid` (`.seat`, `.amount` = that seat's bid), one per bidder, sent
  after all bids are in; `auction` (`.seat` = a winner, `.amount` = the price paid).
- Where opponents' public cards appear: `show` events at showdown, with all their cards.

## Table settings and scoring

As the base game.

## What it changes for strategy

- The card is worth the equity it adds times the pot you expect to play for, so its value
  depends on the flop, your hand and how many players remain. Draws gain most.
- It is a second-price auction with one winner: bidding what the card is worth to you is
  close to right. A high bid from an opponent says the flop helped them or they are
  drawing; a bid of 0 says little.
- Paying shrinks your stack and feeds the pot others can win. Near the bubble, chips paid
  cost more than their face value. Never bid chips you need to survive.
- An opponent who won the auction has three cards: give their bets more credit.
- Denying a card to a dangerous opponent can be worth a bid on its own.

## What a bot must implement

- [ ] `detect`: `state.phase == "bid"`, or the variant's name.
- [ ] `phases`: a `bid` handler returning `Action("bid", amount)`, a whole number clamped
      to `[min_amount, max_amount]`.
- [ ] `strength`: best five of two or three private cards with the board.
- [ ] Optional: read `bid` and `auction` events to adjust to opponents.

## Local testing

The mini simulator plays this variant (class `Auction` in
[`devtest/sim_variants.py`](../../devtest/sim_variants.py)):

```bash
python3.12 tools/check_zoo.py --variant auction zoo/<bot>
```

The whole ruleset is our own design, so every rule above is a guess about what a real
event would do. A bot must fail safe if the kit differs, in particular on: when the
auction happens, whether bids are revealed, the price rule, how ties are settled, and the
event names. A bot that takes the automatic choice bids 0 and reports no failed decisions.

## Open questions

- Everything, until a kit with an auction exists. The parts most likely to differ: a
  first-price rule, an auction before the flop, and bids kept secret.
