# Standard no-limit hold'em

| | |
| --- | --- |
| Name | `holdem` (the key in each bot's `VARIANTS` table) |
| Status | official (the base game every variant changes) |
| Source | The competition's Format and Getting started pages: [`docs/official-format.md`](../../docs/official-format.md), [`docs/official-getting-started.md`](../../docs/official-getting-started.md) |
| Playable on the mini simulator | Yes |

## Summary

Plain no-limit Texas hold'em at an 8-player sit-and-go table. It is the fallback: a bot
that recognises no other variant plays this.

## How a bot recognises it

- `state.config.variant`: `holdem` on the mini simulator; the kit's own name is unknown.
- Signs in the state: two cards in `state.cards`, and `state.phase` is always `"betting"`.
- It is the last entry in `VARIANTS` and matches anything not recognised earlier.

## Cards

- Private cards dealt: 2, before the first betting round.
- Private cards that play at showdown: best five of the 2 private cards and the 5 board cards.
- Board: flop of 3, turn of 1, river of 1.
- Deck: 52 cards, written rank then suit, for example `"As"`, `"Td"`.
- Hand ranking: standard.

## Extra decision phases

None.

## Betting

Four rounds: before the flop, flop, turn, river. Legal actions are fold and call when
facing a bet, check when checking is free, and raise as a total for the round within
`[min_amount, max_amount]`, where the maximum is all-in. No antes in the default schedule.

## State and events

- New or changed `GameState` fields: none. `state.variant` is an empty dict.
- Event kinds: `hand`, `blind`, `fold`, `check`, `call` (chips added), `raise` (total),
  `board` (new cards), `show`, `win`, `stack`.
- Where opponents' public cards appear: `show` events at showdown.

## Table settings and scoring

8 players, 2,000 chips, blinds 10/20 rising every 20 hands, 250-hand cap. Points per
place come from `state.config.payouts` (50/30/20 by default; they can differ per table).
Survivors at the cap split the remaining points by ICM.

## What it changes for strategy

- Nothing: this is the baseline all the strategy notes in `docs/` are written for.

## What a bot must implement

- [ ] `detect`: always true (the fallback).
- [ ] `phases`: none.
- [ ] `strength`: a 0..1 score of the two private cards with the board.

## Local testing

Fully supported: `python3.12 tools/check_zoo.py zoo/<bot>` and
`python3.12 devtest/mini_sim.py play ...`. What the mini simulator does and does not
share with the kit is listed in [`devtest/README.md`](../../devtest/README.md).

## Open questions

- The kit's value of `state.config.variant` for the base game.
