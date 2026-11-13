# Pittsburgh (three hole cards, two boards, one discard after the turn)

| | |
| --- | --- |
| Name | `double_board_turn_discard` (the key in `VARIANTS`); the portal calls it `pittsburgh` |
| Status | official: the variant of the Pittsburgh regional, 2026-11-12 |
| Source | The kit's `RULES.md` and `sdk/engine/src/poker_engine/variants/_double_board.py`, and `probe.py` on the kit |
| Playable on the mini simulator | No. Test on the kit. |

## Summary

No-limit hold'em with three private cards and two boards dealt side by side (a flop, a turn
and a river on each), one betting round per street. After the turn's betting every player
still in the hand throws away one card face down; the river is played with two. Each board
wins half of every pot.

## How a bot recognises it

- `state.config.variant`: `double_board_turn_discard` in the kit. Not read on the platform: the
  bot detects the game by the `boards` key, and played all six rounds with no missed decision.
- Signs in the state: `state.variant` is a dict with a `boards` key (two lists of cards);
  `state.phase == "discard"`.

## Cards

- Private cards dealt: 3. They stay through preflop, flop and turn betting.
- Private cards that play at showdown: the 2 kept, with each board's five cards, any number
  of hole cards.
- Board: two. `state.board` is the first; `state.variant["boards"]` holds both.
- Deck and hand ranking: as the base game.

## Extra decision phases

### `discard`

- When: after turn betting, before the river, for every player still in, all-in or not. Not
  played when one player is left.
- Legal action kinds: `discard` (min 1, max 1).
- Action to return: `Action("discard", cards=(i,))`, `i` the index in `state.cards` of the
  card thrown away.
- Automatic choice (on a failure, a timeout or `cards=()`): the lowest card is discarded.
- What others see: a `discard` event with the seat, never the card.

## Betting

As the base game.

## State and events

- `state.variant["discarded"]`: our own discard, once made.
- `board` events carry the board number (1 or 2) in `amount`.
- `prize_scoops` and `prize_rivers_seen` events: counters for side prizes, no chips.
- Showdown: every hand still in shows both kept cards automatically.

## Table settings and scoring

As the base game: 8 players, 2,000 chips, 10/20 rising every 20 hands, cap 250 hands, payouts
50/30/20, 1 ms per decision, 100 ms bank, 64 KB memory (`rules_card.json`, from the probe).
A pot that does not divide evenly gives the odd chip to the first board.

## What it changes for strategy

- The share of the pot we expect is the mean of our equity on the two boards, so a hand
  strong on one board and dead on the other is worth about half a pot.
- The same two cards have to play on both boards: the discard keeps the pair with the most
  equity summed over the boards, not the best pair for either one.
- Scoops (winning both boards) are rarer than hold'em wins; split pots are common, so
  calling ranges at showdown are wider and big value hands are rarer.
- Three cards see the flop and the turn, so preflop hands run closer together than hold'em's.

## What a bot must implement

- [x] `detect`: `"boards" in state.variant`, or the kit's name.
- [x] `phases`: `discard` returning `Action("discard", cards=(i,))` (`pittsburgh_discard`).
- [x] `strength`: after the flop, the mean over both boards (`double_board_strength`), with
      three cards the pair we would keep (`double_board_keep`). Before the flop:
      `pittsburgh_preflop`, the measured pot share of the three cards by class
      (`_three_card_equity`; `tools/preflop_check.py` checks it on eight hands). Up to v96 it
      was the `discard_reveal` table (best two cards), which overrated pairs by 8 to 12 points.

## Open questions

- Whether the platform's `state.config.variant` is the kit's name or `pittsburgh` (never read).
- The made-hand strengths after the flop are hold'em's, averaged over the two boards: not
  measured on two boards. The preflop ranking is measured (above).
