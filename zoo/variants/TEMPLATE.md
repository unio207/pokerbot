# <Variant title>

Copy this file to `zoo/variants/<name>.md` and fill in every section. Write "unknown"
where a fact is not known. Only describe what differs from the base game
([`README.md`](README.md#the-base-game)); write "As the base game" where nothing does.

| | |
| --- | --- |
| Name | `<name>` (the key in each bot's `VARIANTS` table) |
| Status | official / reported / practice |
| Source | <where the rules come from, with a link or a date> |
| Playable on the mini simulator | Yes / No |

## Summary

<Two or three sentences: what the game is and the one thing that most changes strategy.>

## How a bot recognises it

- `state.config.variant`: <the kit's name for it, or "unknown">
- Signs in the state: <e.g. "three cards in `state.cards` before the flop", a phase name>

## Cards

- Private cards dealt: <number, and when>
- Private cards that play at showdown: <which and how many>
- Board: <As the base game, or what differs>
- Deck: <As the base game, or what differs>
- Hand ranking: <As the base game, or the changed order>

## Extra decision phases

One block per phase. Delete this section's blocks and write "None" if there are none.

### `<phase name>`

- When: <at what point in the hand, and who acts>
- `state.phase`: `<value>`
- Legal action kinds: <as listed in `state.legal_actions`>
- Action to return: <exact form, e.g. `Action("select", cards=(discard_index, reveal_index))`>
- Automatic choice (played on a failed decision): <what the platform does>
- What others see: <what becomes public, and when>

## Betting

<As the base game, or what differs: limits, extra rounds, antes, forced bets.>

## State and events

- New or changed `GameState` fields: <e.g. what `state.variant` holds>
- New event kinds: <kind, and what `.seat`, `.amount`, `.cards` mean>
- Where opponents' public cards appear: <event kind or seat field>

## Table settings and scoring

<As the base game, or what differs: players, stacks, blinds, hand cap, payouts.>

## What it changes for strategy

- <Short points a bot author needs: how hand values shift, what the extra phase is worth,
  what information becomes public.>

## What a bot must implement

- [ ] `detect`: <the test>
- [ ] `phases`: <a handler per extra phase>
- [ ] `strength`: <how to score the private cards before and after each phase>
- [ ] <anything else, e.g. a new evaluator or equity table>

## Local testing

<Whether `devtest/sim_variants.py` has a class for it and the commands to play it. List
every guess that class makes where this ruleset says "unknown", so a bot does not depend
on them. If there is no class, say what can still be checked by hand.>

## Open questions

- <Facts still unknown, to settle from the kit's `RULES.md`.>
