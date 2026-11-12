# STATE: hand-off from sequoia-launch to mid-round-iterate

Updated: 2026-11-12, before the event (no clock running). Machine: MacBook M5, Python 3.12.15.
Repo at `8f76ac0` plus uncommitted work (the launch skill, 12 added zoo bots).
**Every number below is from the unofficial mini simulator, not from the kit.**
Template: `sequoia-launch/templates/STATE.md`.

## Active bot

| Version | File | Uploaded at | Active | What it is |
| --- | --- | --- | --- | --- |
| v0 | `bots/final/agent.py` (no `v0/` copy made yet) | not uploaded: uploads open at the announcement | no | the `final` profile, unconverted, stamped from `tools/core_agent.py` (`tools/build.py --check` passes) |

Upload to ready: not measured. Rollback target: none yet.

## Variant

Not announced. No Rules Card yet (`rules_card.json` absent, so the scripts use
`sequoia-launch/templates/rules_card.json`: hold'em, 8 players, 2,000 chips, 10/20, 20 hands
per level, cap 250, payouts 50/30/20, 1 ms, 100 ms bank, 64 KB). `VARIANTS` in the core has
entries for irish, discard_reveal, omaha, auction, short_deck and holdem.

## Knobs in the active version (`PROFILES["final"]`, `tools/core_agent.py`)

```python
track=True, adapt=frozenset({"steal", "shover", "station", "minraise"}),
steal_widen=1.15, steal_any=0.85, cbet_air=0.3, vs_shover="doc",
icm_scale=1.0, cap_aware=True, open_size=2.3, semi_bluff=0.3,
call_margin=0.05, bubble_margin=0.08, push_scale=0.9, points_tight=0.08,
threebet=0.03, call_raise=0.08,
```

Everything else comes from `_BASE` in the same file.

## Gate

`gate.py bots/final`, runner mini, SDK stand-in, template card: **GATE: PASS** (one warning:
rules card not filled).

- build check: `bots/` match `tools/core_agent.py`
- fuzz: 20,000 states, 0 bad; 0 exceptions raised inside the bot on 10,000 clean states
- `tools/fuzz.py`: 5,000 states, no failures
- timing, 20,000 decisions in-process: p50 18 µs, p99 37 (allowed 250), p99.9 42 (allowed
  500), max 77, 0 over 1,000 µs
- memory: largest blob 96 bytes over a 250-hand busy table (allowed 16,384)
- tables: 300 over 3 line-ups, 0 failed decisions of 32,081
- upload-test imitation (no time bank): 0 of 3,000 failed
- `agent.py` 69,417 bytes; import 0.010 s

Also PASS with cards probed from the mini rulesets `irish`, `discard_reveal` and `short_deck`
(timing p99 73, 40 and 38 µs).

## Gauntlet baseline

`gauntlet.py bots/final --vs starter --tables 1000 --seed baseline`, runner mini, 5 jobs,
payouts 50/30/20, hold'em, 10 batches of 100 tables per line-up.

| Line-up | `final` | `starter` | Difference |
| --- | --- | --- | --- |
| mixed field | 29.50 ± 0.53 | 19.71 ± 0.56 | +9.79 ± 0.69 |
| passive field | 47.08 ± 0.38 | 40.65 ± 0.58 | +6.43 ± 0.62 |
| aggressive field | 30.14 ± 0.47 | 14.16 ± 0.20 | +15.98 ± 0.43 |
| seven starters | 15.04 ± 0.42 | 12.50 | +2.54 ± 0.42 |
| four of you, four starters | 14.84 ± 0.14 | 12.50 | +2.33 ± 0.14 |
| zoo field 1 (claude_*, 2 codex) | 16.08 ± 0.45 | 12.95 ± 0.42 | +3.13 ± 0.61 |
| zoo field 2 (codex, gpt) | 20.47 ± 0.66 | 17.31 ± 0.68 | +3.16 ± 0.63 |
| zoo field 3 (gpt) | 30.96 ± 0.70 | 27.76 ± 0.40 | +3.20 ± 0.86 |
| zoo field 4 (gpt, wraps to claude) | 16.89 ± 0.55 | 13.40 ± 0.52 | +3.49 ± 0.54 |
| all line-ups, equal weight (n = 9,000) | 24.55 ± 0.19 | 18.99 ± 0.16 | +5.56 ± 0.22 |

n = 1,000 tables per line-up per bot. Par is 12.5. Speed: 13,500 tables per minute. Detectable
A/B difference at 2.8 standard errors: 0.31 points in 5 minutes, 0.22 in 10, 0.13 in 30; by
hand `2.8 x 21 / sqrt(tables per bot)`.

Variant rulesets on the mini simulator, `final` against `starter`, all line-ups, n = 1,800
per bot: irish 32.45 ± 0.48 against 12.19 ± 0.12; short_deck 24.69 ± 0.42 against
14.75 ± 0.41; discard_reveal 26.25 ± 0.45 against 17.93 ± 0.18. Zero failed decisions.

Promotion rule in force: difference over all line-ups above 2 standard errors on one seed and
still positive on a fresh seed; zero failed decisions; gate PASS.

## Practice runs and rounds

None yet.

## Known weaknesses

- The zoo's strong bots: `final` scores 16.08 and 16.89 in the line-ups with the `claude_*`
  and `codex_*` strategy bots, against 29 to 47 in the hand-written fields. A field of
  prepared teams is where points are scarce.
- `_icm_me` prices only the first three payout places. With four or more places paid, or
  unusual per-table payouts, its ICM is approximate.
- An unknown phase gets the automatic choice. Whether the kit counts that as a failed decision
  for an action that needs `cards` is unknown until the kit is in hand.
- `skills/mid-round-iterate` runs `tools/bench.py --lineup ... ai_field`. That line-up does
  not exist in `tools/bench.py` on main (only on `origin/overnight/prep-2026-11-11`), so that
  command fails as written. `gauntlet.py --vs` covers the same job.
- `tools/field_report.py`'s reader for the organizers' history format is a guess.
- `starter` fails `tools/fuzz.py`'s repeat-call check because it bluffs with the global
  `random`. It is an opponent, not an upload, so this only matters if someone uploads it.

## First experiments to try

1. After the first hand histories: `tools/field_report.py --inspect`, fix `kit_hands`, then
   the report. Everything else follows from what the field is.
2. `tools/field_fit.py --sweep --bot bots/final` against the look-alike field.
3. If the field looks like zoo field 1 or 4 (strong bots), `points_tight` and `call_margin`
   are the first knobs; if it looks like zoo field 3 (weak first drafts), `steal_widen`.
4. If practice runs show many 2nd and 3rd places and few firsts: `hu_open` up.

## Log

- 2026-11-12, session 1: launch skill written against a checkout 49 commits behind main;
  found when the zoo looked empty. Pulled to `8f76ac0`, re-based the skill on `bots/final`
  and the repo's tools, moved it to `skills/sequoia-launch/`, added the 12 weak zoo bots from
  the overnight branch. Nothing uploaded. Pre-written code is allowed (Henry, 2026-11-12).
  Still open: whether there is an upload command (assume the team page in a browser).
