# Variant rulesets

One file per game variant. A ruleset says what the variant changes from the base game,
in a fixed layout, so that a person or an AI can write a zoo bot for it from
[`zoo/_template/`](../_template/README.md) without guessing.

The tournament's variant is secret until the build starts, and the finals use a different
one. Rulesets here are therefore of three kinds, and each file says which it is:

- **official**: taken from the organizers' pages or the kit's `RULES.md`.
- **reported**: described by entrants of an earlier event; details may be wrong.
- **practice**: our own invention, to rehearse converting bots to something unfamiliar.

## Rulesets

| File | Name | Status | Playable on the mini simulator |
| --- | --- | --- | --- |
| [`holdem.md`](holdem.md) | `holdem` | official (the base game) | Yes |
| [`discard_reveal.md`](discard_reveal.md) | `discard_reveal` | reported (Bay Area regional) | Yes, with guesses |
| [`short_deck.md`](short_deck.md) | `short_deck` | practice: changed deck and hand ranking | Yes |
| [`omaha.md`](omaha.md) | `omaha` | practice: four hole cards, exactly two play | Yes |
| [`auction.md`](auction.md) | `auction` | practice: a bidding phase for an extra card | Yes |

The four variants were picked to cover the kinds of twist entrants and the organizers'
wording point to: an extra phase that chooses cards (`discard_reveal`), a changed deck and
ranking (`short_deck`), extra hole cards with a rule on which play (`omaha`), and an extra
phase that spends chips (`auction`). The real variant will be something else; a bot that
handles all four through one `VARIANTS` table is quick to convert.

## The base game

Every variant is a change to the same base: no-limit hold'em sit-and-go tables, 8 players,
2,000 chips, blinds 10/20 rising every 20 hands, a 250-hand cap, points by finishing place
with an ICM split at the cap, 1 ms per decision. The full list is in
[`docs/official-format.md`](../../docs/official-format.md) and
[`docs/official-getting-started.md`](../../docs/official-getting-started.md). A ruleset
only writes down what differs.

## Add a variant

1. **Copy** [`TEMPLATE.md`](TEMPLATE.md) to `zoo/variants/<name>.md`. The name is
   lowercase letters, digits and `_`, for example `short_deck`. It becomes the key in
   every bot's `VARIANTS` table and the word used in bot headers and prompts.
2. **Fill in every section.** Write "unknown" where a fact is not known; never leave a
   section out, and never guess silently. A bot author treats the file as the whole truth.
3. **Add a row** to the table above.
4. **Add an entry to the template** in [`zoo/_template/agent.py`](../_template/agent.py)
   under the same name, with a placeholder `detect`, `phases` and `strength`, so every
   new bot starts with a slot for it.
5. **Add it to the mini simulator** in [`devtest/sim_variants.py`](../../devtest/sim_variants.py):
   a class with the same name that sets the hole-card count and overrides the hooks the
   variant needs (deck, an extra phase after a street's cards, showdown ranking), then an
   entry in its `VARIANTS`. The command line, `tools/check_zoo.py` and the practice web
   page pick it up from there. Mark every choice the ruleset does not settle as a GUESS
   in the class and list it in the ruleset's "Local testing" section.
6. **On event day,** when the kit's `RULES.md` is in hand, write the announced variant as
   a new ruleset first (status: official), then build bots from it.

## How bots use a ruleset

Each bot keeps a `VARIANTS` table with one entry per ruleset it implements, keyed by the
ruleset's name. The entry holds the three things that depend on the variant: how to
recognise the table (`detect`), how to answer the variant's extra decision phases
(`phases`), and how to score private cards (`strength`). The betting strategy is written
once and only reads the strength score. The layout is explained in
[`zoo/_template/README.md`](../_template/README.md).

## Playing a variant locally

```bash
python3.12 devtest/mini_sim.py play starter zoo/_template sparring/nit --variant discard_reveal --tables 200
```

```bash
python3.12 tools/check_zoo.py --variant discard_reveal zoo/<bot>
```

The practice web page has a Variant box under Match settings, and its hand replay shows
discards and reveals.

## What cannot be tested here

The simulator's variants are our re-implementations of the rulesets, not the organizers'
engine. Where a ruleset says "unknown", the simulator makes a guess, and the ruleset's
"Local testing" section lists those guesses. A bot that passes here can still meet a
different action form, phase order or event name in the kit, so its variant code must
fail safe. A variant with no class in `devtest/sim_variants.py` cannot be played locally
at all.
