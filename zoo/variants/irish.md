# Irish (four hole cards, discard two after the flop)

| | |
| --- | --- |
| Name | `irish` (the key in each bot's `VARIANTS` table) |
| Status | practice: written to rehearse converting a bot to a variant nobody had seen |
| Source | The card game Irish poker with this tournament's no-limit betting, written down by us on 2026-11-11 |
| Playable on the mini simulator | Yes |

## Summary

Hold'em with four private cards before the flop. After the flop is dealt, each player
still in the hand discards two cards face down and plays the rest of the hand as hold'em
with the two kept. Preflop a hand is worth the best pair of cards it can turn into once
the flop is known, so four cards are worth far more than their best two.

## How a bot recognises it

- `state.config.variant`: unknown in a kit; `irish` on the mini simulator.
- Signs in the state: `state.phase == "discard"`. Four cards in `state.cards` before the
  flop is also what `omaha` shows, so without the name a table looks like `omaha` until
  the discard phase arrives.

## Cards

- Private cards dealt: 4, before the first betting round.
- Private cards that play at showdown: the 2 kept after the discard, with the board.
- Board: as the base game.
- Deck: as the base game.
- Hand ranking: as the base game.

## Extra decision phases

### `discard`

- When: after the flop is dealt and before flop betting, for each player still in the
  hand, including players who are all-in.
- `state.phase`: `"discard"`
- Legal action kinds: `discard`
- Action to return: `Action("discard", cards=(first_index, second_index))`, two different
  indices into `state.cards`: the cards thrown away.
- Automatic choice (played on a failed decision): discards the last two cards.
- What others see: nothing. Discards stay hidden.

## Betting

As the base game.

## State and events

- New or changed `GameState` fields: `state.cards` holds 4 cards before the discard and
  the 2 kept, in their original order, after it.
- New event kinds: none.
- Where opponents' public cards appear: `show` events at showdown, with the two kept cards.

## Table settings and scoring

As the base game.

## What it changes for strategy

- Before the flop everyone holds six two-card combinations and will keep the best one
  for the flop, so hands run close together and all-in calls can be wider.
- The discard is a pure card-strength decision with the flop known: keep the pair of
  cards that plays best with it, draws included.
- After the discard the game is hold'em, but ranges are much stronger than hold'em
  ranges: everyone picked their best two of four for this flop.
- The two discards are dead cards only their owner knows.

## What a bot must implement

- [ ] `detect`: `state.phase == "discard"`, or the variant's name.
- [ ] `phases`: a `discard` handler returning `Action("discard", cards=(i, j))`.
- [ ] `strength`: before the flop, a score of the four cards together; after the
      discard, the two kept cards as hold'em.

## Local testing

The mini simulator plays this variant (class `Irish` in
[`devtest/sim_variants.py`](../../devtest/sim_variants.py)):

```bash
python3.12 tools/check_zoo.py --variant irish zoo/<bot>
```

The whole ruleset is our own, so every rule is a guess about a real event. A bot must not
depend on: the phase name, the action form, the discard coming before flop betting, the
automatic choice, or `state.config.variant` being `irish`. A `discard` action with no
cards is taken as asking for the automatic choice and is not counted as a failed decision.

## Open questions

- None: this is a rehearsal variant. A real event could reveal discards or put the
  discard after flop betting.
