# Zoo bot template

Start every zoo bot from this folder. It is written so that the same bot can play any
variant we have a ruleset for: the strategy is written once, and everything that depends
on the variant sits in one table.

If you are an AI asked to "make a zoo bot from the template", this page is your brief.

## What to read first

1. This page.
2. [`agent.py`](agent.py) in this folder: the structure to keep.
3. [`zoo/variants/README.md`](../variants/README.md), then the ruleset of every variant
   the bot must support.
4. [`zoo/README.md`](../README.md): the rules for zoo bots and how to check one.
5. [`docs/official-format.md`](../../docs/official-format.md) and
   [`docs/official-getting-started.md`](../../docs/official-getting-started.md): the base
   game and the platform's limits.

## What the request must say

A request for a new bot has three parts. If one is missing, use the default.

| Part | Meaning | Default |
| --- | --- | --- |
| Profile | The bot's temperament: tight, aggressive, passive, adaptive and so on | The template's placeholder is not a profile; ask, or pick one from [`docs/bot-zoo.md`](../../docs/bot-zoo.md) |
| Variants | One ruleset name, several, or `all` | `all`: every ruleset listed in `zoo/variants/README.md` |
| Name | The folder name | `<source>_<profile>_<n>`, with the variant added when the bot supports only one: `<source>_<profile>_<variant>_<n>` |

Examples:

- "Make a tight zoo bot for all variants" → `zoo/claude_tight_1/`, an entry for every ruleset.
- "Make an aggressive zoo bot for discard_reveal" → `zoo/claude_aggro_discard_reveal_1/`,
  entries for `discard_reveal` and `holdem`.

Every bot keeps the `holdem` entry, whatever was asked: it is the fallback when a table is
not recognised.

## How `agent.py` is organised

| Part | What it is | Changes per variant? |
| --- | --- | --- |
| `act` | Crash-proof wrapper: finds the variant, routes the phase, makes the action legal | No |
| `VARIANTS` | One entry per ruleset: `detect`, `phases`, `strength` | Yes: this is the only part that does |
| `decide` | The betting strategy, which is the bot's temperament | No: it reads the strength score |
| Helpers | Legal actions, clamped raises, stacks, pot odds | No |

A `VARIANTS` entry has the same name as its ruleset file and three fields:

- `detect(state) -> bool`: true when this table plays the variant. An exact match on
  `state.config.variant` is tried first; then entries are tried in order; `holdem` is
  last and always matches.
- `phases`: `{phase name: handler(state) -> Action}` for each extra decision phase the
  ruleset lists. A phase with no handler gets the automatic choice.
- `strength(state) -> float`: 0 to 1, how good our private cards are now. It is the only
  code that knows how many cards we hold, which ones play, and how hands rank.

## Steps

1. **Copy** this folder to `zoo/<name>/`.
2. **Fill in the header** of `agent.py`: Source, Profile, Variants, Notes. `Variants`
   lists the rulesets the bot implements, or `all` with the date.
3. **For each requested variant,** read its ruleset and write its `VARIANTS` entry. The
   ruleset's "What a bot must implement" section is the checklist. Remove entries for
   variants the bot does not support, apart from `holdem`.
4. **Write `decide`** for the profile. Keep it free of variant tests: if the strategy
   needs something variant-specific, add a field to the variant entries and read that.
   A bot may give an entry extra fields, for example a preflop table or a different
   opening threshold per variant.
5. **Replace `two_card_strength`** with real scoring. It ignores the board; a real bot
   scores made hands and draws after the flop.
6. **Keep the wrapper and `legal`.** They are what turns a bug into a check or fold
   instead of a failed decision.
7. **Check it** as described below.

## Rules that do not bend

The docstring at the top of `agent.py` lists them. The ones most often broken:

- 1 ms per decision, for every variant. More private cards mean more combinations: time
  the slowest variant, not hold'em.
- Nothing kept on `self` or in globals between calls. Tables built at import are fine.
- A ruleset marked "reported" or with open questions may be wrong. Code for it must fail
  safe: an unexpected phase, card count or action kind ends in the automatic choice or a
  check or fold, never an exception. Do not invent rules the ruleset does not state.
- One file, standing alone. No imports from `starter/`, `sparring/` or other zoo bots.

## Check the bot

1. **Hold'em, on the mini simulator.** Must report `OK`:

   ```bash
   python3.12 tools/check_zoo.py zoo/<name>
   ```

2. **Every other variant the bot supports, on the mini simulator.** Once per variant;
   must report `OK`, and the decision time must stay well under 1,000 µs:

   ```bash
   python3.12 tools/check_zoo.py --variant <variant> zoo/<name>
   ```

   `OK` alone does not show the variant code ran: a bot that takes the automatic choice
   also passes. Confirm the bot's own handler is used, for example by watching a hand in
   the practice web page's replay with that variant selected. Follow the ruleset's "Local
   testing" section, which lists what the simulator guesses. A variant the simulator does
   not play is checked by hand: build its states from `devtest/shim/poker_agent_sdk`,
   call `act`, and confirm a legal action comes back. Keep test scripts outside the repo.
3. **Unknown tables.** Call `act` with a phase name and a card count no ruleset has.
   It must return the first legal action, not raise.
4. **Say what was not tested.** In the bot's `Notes` line or the hand-off, state which
   variants ran in the mini simulator and which were only checked by hand.

## When a variant is added later

A bot whose header says `Variants: all` covers the rulesets that existed on its date. To
bring it up to date, read the new ruleset, add one entry to its `VARIANTS`, and update the
header. Nothing else in the file should need to change; if it does, the variant-specific
part has leaked into `decide`.
