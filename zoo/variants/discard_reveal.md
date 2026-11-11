# Discard and reveal (Bay Area regional)

| | |
| --- | --- |
| Name | `discard_reveal` (the key in each bot's `VARIANTS` table) |
| Status | reported: described by two entrant teams, not confirmed by the organizers |
| Source | Entrants' public repositories, summarised in [`docs/research_notes/rules_and_technical_format.md`](../../docs/research_notes/rules_and_technical_format.md) |
| Playable on the mini simulator | Yes, with the guesses listed under "Local testing" |

## Summary

Hold'em with three private cards. After the flop, each player still in the hand discards
one card face down and turns one of the two kept cards face up; the other stays hidden.
Showdown uses the two kept cards and the board. Half of every live hand becomes public.

## How a bot recognises it

- `state.config.variant`: unknown in the kit; `discard_reveal` on the mini simulator.
- Signs in the state: three cards in `state.cards`, or `state.phase == "select"`.
- After the select phase a player holds two cards and the phase is `"betting"`, which
  looks like `holdem`. A bot that needs to know it is still in this variant must note it
  in `memory` or read it from the events.

## Cards

- Private cards dealt: 3, before the first betting round.
- Private cards that play at showdown: the 2 kept after the discard, with the board.
- Board: as the base game.
- Deck: as the base game.
- Hand ranking: as the base game.

## Extra decision phases

### `select`

- When: after the flop, for each player still in the hand. One entrant says all choices
  are collected first and shown together, so nobody sees another reveal before choosing.
  The exact timing was not confirmed.
- `state.phase`: `"select"`
- Legal action kinds: `select`
- Action to return: `Action("select", cards=(discard_index, reveal_index))`, both indices
  into `state.cards`. As used by one Bay Area team; another mock used separate `discard`
  and `reveal` actions.
- Automatic choice (played on a failed decision): the first legal action at its minimum.
  Which cards that discards and reveals is unknown.
- What others see: the revealed card of every live player. The discard stays hidden.

## Betting

As the base game. Unknown whether a betting round follows the select phase on the flop or
the select phase comes after flop betting.

## State and events

- New or changed `GameState` fields: unknown. `state.cards` holds 3 cards before the
  select phase and presumably the 2 kept afterwards.
- New event kinds: unknown.
- Where opponents' public cards appear: unknown. Look for a new event kind and for
  `seat.shown_cards` in the kit.

## Table settings and scoring

As the base game, as far as reported.

## What it changes for strategy

- Before the flop, a hand is worth its best two-card combination, and three cards make
  strong combinations more common for everyone. Tighten what counts as a strong hand.
- The select phase is a card-strength decision once the flop is known: keep the pair of
  cards that plays best with the board, including draws.
- The reveal leaks information. Showing the lower or less telling kept card hides more.
  Opponents' revealed cards narrow their hands and block cards.
- The discard is a known dead card for the player who made it.

## What a bot must implement

- [ ] `detect`: three cards in `state.cards`, or `state.phase == "select"`.
- [ ] `phases`: a `select` handler returning `Action("select", cards=(discard, reveal))`.
- [ ] `strength`: before the select phase, the best two-card combination of the three
      (with the board once it is out); after it, the two kept cards.
- [ ] Optional: read opponents' revealed cards and adjust.

## Local testing

The mini simulator plays this variant (class `DiscardReveal` in
[`devtest/sim_variants.py`](../../devtest/sim_variants.py)):

```bash
python3.12 tools/check_zoo.py --variant discard_reveal zoo/<bot>
```

```bash
python3.12 devtest/mini_sim.py play zoo/<bot> starter sparring/nit sparring/shover --variant discard_reveal --tables 200
```

The practice web page offers it in the Variant box, and the hand replay shows each
discard and reveal.

The simulator fills the unknowns above with guesses. A bot must not depend on them:

- The select phase comes after the flop is dealt and before flop betting.
- All live players choose, including those all-in, and choices are shown together.
- The reveal reaches other bots as a `reveal` event (`.seat`, `.cards` holding the one
  card) and in `seat.shown_cards`. The discard is never sent.
- After the select phase `state.cards` holds the two kept cards in their original order.
- The automatic choice discards the first card and reveals the second.
- A `select` action with no cards is taken as asking for the automatic choice and is not
  counted as a failed decision. The kit may count it as one. This is why a hold'em-only
  bot shows no failed decisions here.
- `state.config.variant` is `discard_reveal`.

## Open questions

- The kit's variant name, the exact action form, and when the select phase happens.
- How revealed cards are delivered to other players.
- What the automatic choice discards and reveals.
