# Pittsburgh rehearsal

Standard no-limit hold'em, with one optional card exchange after the turn and one change
to the hand ranking.

## Rules

- Deal two private hole cards per player from one standard 52-card deck. Play normal
  preflop and flop betting.
- After dealing the turn card and before turn betting, every non-folded player chooses
  either to stand or to exchange exactly one hole card. Lock every choice before any
  card moves.
- An exchanged card is turned face up and leaves the hand. It stays public for the rest
  of the hand, including if its owner later folds. Its owner receives one replacement
  from the top of the deck, face down, in the position the exchanged card held.
  Replacements are dealt in seat order after all exchanged cards are exposed.
- How many cards each player exchanged (zero or one) is public. A player who stands
  exposes nothing.
- All-in players also choose. Pause automatic runouts at the turn for the exchange.
- If everyone but one player folds before the turn, award the pot without an exchange.
  Exchanging costs no chips and does not change betting order or side-pot eligibility.
- Continue normal turn and river betting. At showdown, use the best five cards from the
  board and the two hole cards then held, using zero, one, or both hole cards.
- **Straights do not count.** Five cards in sequence make no hand by themselves: they
  rank as high card, or as a pair and so on if they hold one. Five cards in sequence of
  one suit rank as a flush, compared like any other flush, highest card first. The order
  of hands is therefore: four of a kind, full house, flush, three of a kind, two pair,
  one pair, high card.
- On a failed exchange decision (timeout, exception, or invalid action), the player
  stands. This does not fold the player or surrender an all-in pot.
- Blinds, raises, side pots, uncalled refunds, and automatic showdown disclosure follow
  the hold'em reference. The exchange uses the normal decision time limit, time bank, and
  table memory. The variant supports 2–10 players.

## Bot interface

- `state.config.variant` is `"rehearsal"`.
- At `state.phase == "draw"`, `state.cards` contains the two hole cards in dealing order
  and `state.board` holds four cards. `state.legal_actions` contains one action of kind
  `draw` with `min_amount` 0 and `max_amount` 1: the fewest and most cards that may be
  exchanged. `state.to_call` is 0.
- To exchange, return `Action("draw", cards=(index,))`, where `index` is 0 or 1 into
  `state.cards`. To stand, return `Action("draw")` with empty `cards`. `amount` must be
  zero in both. More than one index, an index out of range, or a non-zero amount is an
  invalid action.
- The supplied template takes the first legal action at its minimum amount in unfamiliar
  phases, which here is to stand.
- Requests are collected in seat order, but nothing is published until all players have
  answered. Subsequent players cannot see earlier players' choices.
- After resolution, each non-folded player has a public `draw` event: `seat`, and
  `amount` 0 or 1 for the number of cards exchanged. These are followed by one `discard`
  event per exchanged card: `seat`, and the card in `cards`. The replacement is never
  published before showdown.
- After the exchange, `state.cards` contains the two cards now held, the replacement in
  the exchanged card's position. `state.seats[].shown_cards` is not used for exchanged
  cards; read them from the `discard` events. `state.variant` is empty.
- Betting uses the existing action API; showdown reveals are automatic without a bot
  turn, and show the two cards held at showdown.
- eval7 ranks straights and straight flushes as in standard hold'em. Its hand values and
  its range and equity helpers are therefore wrong for this variant wherever a straight
  is possible.

A minimal exchange handler is:

```python
if state.phase == "draw":
    return Action("draw"), memory
```

Improve the choice of whether and what to exchange; account for opponents' exchanges and
exposed cards in later decisions; and revalue hands for the changed ranking on every
street.

## Hand history

- A hand's events include each `draw` and `discard` as above. An exchanged card is public
  from its `discard` event onward.
- Your private `cards` are the two cards you were dealt. When you exchange, the
  replacement is recorded in owner-only `private_events`.
- An automatic exchange decision is a stand.
