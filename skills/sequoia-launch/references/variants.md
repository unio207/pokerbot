# Variant playbook (stage 3)

The procedure is "Converting to the announced variant" in `docs/event-day-setup.md`. This
file adds: which existing pattern to copy for each family, the cross-check against the kit,
and what was measured. Timings: MacBook M5, 2026-11-12, mini simulator.

## What is public about earlier variants

- Bay Area (Nov 6), from two entrants' repositories cited in
  `docs/research_notes/rules_and_technical_format.md`: three hole cards; after the flop each
  live player discards one and exposes one; showdown uses the two kept cards. Our ruleset:
  `zoo/variants/discard_reveal.md`.
- Boston (Nov 9): not found anywhere (searched again 2026-11-12).
- Finals use a different variant from every regional.

## The three places a conversion touches

| Where | What | Pattern to copy |
| --- | --- | --- |
| `zoo/variants/<name>.md` | the ruleset, from `TEMPLATE.md` | `irish.md` |
| `devtest/sim_variants.py` | a class so the mini simulator deals it: `hole_cards`, `deck()`, `after_board()` for an extra phase, `rank()` for the showdown | `Irish` (extra phase), `ShortDeck` (deck and ranking), `Omaha` (which cards play) |
| `tools/core_agent.py`, `VARIANTS` | `detect`, `phases`, `preflop`, `postflop`; then a job in `tools/gen_variant_tables.py` and `tools/build.py` | the entry of the nearest family below |

Never edit `bots/*/agent.py`: they are stamped from the core, and the gate fails on drift.

## Families and the entry to start from

| Family | Signs in the Rules Card | Copy this `VARIANTS` entry | Simulator class | Converted `final` against `starter` on the mini ruleset |
| --- | --- | --- | --- | --- |
| More hole cards, discard or select phase | `hole_cards` 3 or 4, a phase other than `betting` | `irish` (discard two of four) or `discard_reveal` (discard one, expose one) | `Irish`, `DiscardReveal` | irish +20.96 ± 0.41; discard_reveal +7.47 ± 0.42 |
| Exactly two hole cards play | four cards, no extra phase, RULES.md says two must play | `omaha` | `Omaha` | not run this session |
| Changed deck or hand ranking | `deck_cards` under 52, ranking notes | `short_deck` (detected by `state.config.variant` only: nothing in the state marks it) | `ShortDeck`, `rank_five(low_straight=, flush_beats_full_house=)` | short_deck +8.21 ± 0.39 |
| Bidding or extra information | a `bid`-like phase with an amount, `Seat.shown_cards` | `auction` | `Auction` | not run this session |
| Changed betting only (pot-limit, fixed-limit, antes) | same cards and phases, different `legal_actions` ranges or `BlindLevel.ante` | none needed: every raise is clamped to the legal range by `legal` | none | not run |
| Something else | | `holdem` stays the fallback; write `phases` handlers first | | |

Differences are points per table over all nine gauntlet line-ups, same seeds, n = 2,700
tables per bot, `gauntlet.py bots/final --vs starter --tables 300` (re-measured 2026-11-12
16:33 with the 23-bot zoo). They compare two different bots, so
they show that the variant code runs and scores, not the size of the conversion gain. The
repo's own measure of that gain is 30.9 against 17.3 for the unconverted bot (`irish`, 300
tables, `docs/event-day-setup.md`).

## The cross-check that the simulator class matches the kit

```bash
$PY $K/probe.py                               # on the kit: writes rules_card.json
cp rules_card.json rules_card.kit.json
$PY $K/probe.py --mini --variant <name>       # on our class: overwrites rules_card.json
diff <($PY -c "import json;print(json.dumps(json.load(open('rules_card.kit.json'))['variant']['phase_shapes'],indent=1))") \
     <($PY -c "import json;print(json.dumps(json.load(open('rules_card.json'))['variant']['phase_shapes'],indent=1))")
cp rules_card.kit.json rules_card.json        # the kit's card is the one to keep
```

Then set `variant.mini_name` to `<name>` in the kept card, so the gate and gauntlet play the
class whenever they fall back to the mini simulator. Same phases, card counts per street and
action kinds means our reading matches where a bot can see it. It does not prove the showdown
rule: add one hand-built showdown to the class's test or check a kit hand history.

Measured on the mini rulesets, probe output per variant: `irish` shows a `discard` phase with
four cards on a three-card board, then betting with two cards; `discard_reveal` shows
`select` with three cards; `short_deck` shows betting only with two cards.

## Tables

```bash
$PY tools/gen_variant_tables.py tools/core_agent.py --samples 400000    # 30.7 s for every variant, 8 processes
$PY tools/build.py
```

It remeasures every variant's tables; keep only the new variant's lines in the diff if the
others should stay. It needs the simulator class. Without one (behind the clock), reuse the
nearest family's fit and marks and say so in STATE.md.

## Runtime cost

`gate.py` timing of `bots/final`, 20,000 in-process decisions, states built from each
variant's probed shapes:

| Card | p50 | p99 | p99.9 | max |
| --- | --- | --- | --- | --- |
| hold'em (template card) | 18 µs | 37 | 42 | 77 |
| irish (four cards, discard) | 22 | 73 | 78 | 94 |
| short_deck | 19 | 38 | 44 | 54 |
| discard_reveal (three cards, select) | 22 | 40 | 49 | 114 |

The gate allows p99 up to 25% and p99.9 up to 50% of `decision_ms`. More hole cards mean more
combinations: time the variant, not hold'em, and on the build machine.

## Writing a phase handler

- The kit's own `agent.py` and `examples/` show the exact `Action` for the new phase. Copy the
  shape from there, not from memory.
- A handler falls back to `automatic(state)` when the cards are not what the ruleset says.
- `bots/final` answers a phase it has no handler for with the automatic choice. If the kit
  counts that as a failed decision, the upload test rejects above 10%: that is why stage 1
  gates `v0` on the kit before uploading it.
- `OK` from a checker does not show the handler ran: a bot taking the automatic choice also
  passes. The gauntlet against `v0` is the evidence.

## If the variant fits no family

Keep the unconverted bot active. Write only the `phases` handlers so that no decision fails,
pass the gate, upload. Then improve `preflop` with whatever table can be measured in ten
minutes. A legal bot with hold'em instincts scores; a clever bot that fails decisions does not.
