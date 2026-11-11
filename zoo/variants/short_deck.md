# Short deck

| | |
| --- | --- |
| Name | `short_deck` (the key in each bot's `VARIANTS` table) |
| Status | practice: our own pick of a likely twist; a changed deck and hand ranking |
| Source | The common "six-plus hold'em" rules, written down by us on 2026-11-10 |
| Playable on the mini simulator | Yes |

## Summary

Hold'em with the 2s, 3s, 4s and 5s removed, leaving 36 cards. A flush beats a full house,
and the ace plays low only in A-6-7-8-9. Hands run much closer in value, so equity tables
and hand-strength thresholds built for a full deck are wrong.

## How a bot recognises it

- `state.config.variant`: unknown in a kit; `short_deck` on the mini simulator.
- Signs in the state: none that are reliable in one decision. No card below a 6 ever
  appears, which a bot could only notice over many hands.
- A bot that cannot read the variant's name plays this as `holdem`.

## Cards

- Private cards dealt: 2, as the base game.
- Private cards that play at showdown: best five of the 2 private cards and the 5 board cards.
- Board: as the base game.
- Deck: 36 cards, ranks 6 to ace in four suits.
- Hand ranking, best first: straight flush, four of a kind, **flush, full house**,
  straight, three of a kind, two pair, pair, high card. The lowest straight is A-6-7-8-9.
  A-2-3-4-5 does not exist.

## Extra decision phases

None.

## Betting

As the base game (blinds, no antes).

## State and events

- New or changed `GameState` fields: none.
- New event kinds: none.
- Where opponents' public cards appear: as the base game.

## Table settings and scoring

As the base game.

## What it changes for strategy

- Starting hands are closer together: a pocket pair or two high cards is a smaller
  favourite, so all-in calls can be wider and shove ranges wider.
- Straights are far more common (connected cards go up in value); flushes are rarer, which
  is why they rank higher. A set or full house is easier to make and easier to be beaten.
- Open-ended straight draws and sets hit more often than in a full deck; flush draws less
  (only 5 cards of the suit remain unseen instead of 9).
- Any full-deck equity table, preflop chart or made-hand threshold must be rebuilt.

## What a bot must implement

- [ ] `detect`: by `state.config.variant` only.
- [ ] `phases`: none.
- [ ] `strength`: scoring for a 36-card deck, with flush above full house and the
      A-6-7-8-9 straight. Do not treat A-2-3-4-5 as a straight.
- [ ] A hand evaluator that follows this ranking, if the bot evaluates made hands.

## Local testing

The mini simulator plays this variant (class `ShortDeck` in
[`devtest/sim_variants.py`](../../devtest/sim_variants.py)):

```bash
python3.12 tools/check_zoo.py --variant short_deck zoo/<bot>
```

The simulator makes these choices where real events differ; a bot must not depend on them:

- A straight beats three of a kind (some short-deck games reverse this).
- Blinds as in the base game, with no antes (many short-deck games use antes).
- `state.config.variant` is `short_deck`.

## Open questions

- Whether a real event would rank three of a kind above a straight, or use antes.
