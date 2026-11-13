# Research notes for the NO LIMIT '26 skills

> **Written before the Pittsburgh regional (2026-11-12) and left as it was.** Written that
> morning. "Current main" in it is `8f76ac0`. It treats the kit gauntlet as the final word; the
> gauntlet scored the round 1 bot 28 where the field scored it 12.4. What happened:
> [`pittsburgh-results.md`](../docs/pittsburgh-results.md).

Written 2026-11-12. An index plus what is new; existing documents are linked, not repeated.
Every number names its source. "mini" means `devtest/mini_sim.py`: unofficial. No kit was
installed in this session, so nothing here is a kit number.

**History of this file.** The launch skill was first researched and built against a checkout
49 commits behind `origin/main` (local `a0facb6`, Nov 11 03:31). That checkout had only the
starter bot and an empty zoo. After pulling to `8f76ac0` the skill was re-based on what main
actually has: `bots/final`, `tools/core_agent.py`, the variant simulator, the repo's own
fuzzer and bench, and two team skills. Sections below describe current main. Measurements
taken on the old checkout are marked.

Contents: [Design](#design) · [Rules check](#rules-check) · [Repo inventory](#repo-inventory) ·
[The two team skills](#the-two-team-skills) · [Strategy conclusions](#strategy-conclusions) ·
[Dry runs](#dry-runs) · [Open questions](#open-questions-the-announcement-will-answer)

## Design

The skill is `skills/sequoia-launch/` (linked from `.claude/skills/` locally so Claude Code
lists it). Its spine is the clock.

| Stage | Budget | Produces | Failure it guards against | Machine time measured (mini, M5) |
| --- | --- | --- | --- | --- |
| 1 Kit + active bot | T+0 to 10 | kit installed, `v0` = unchanged `bots/final` active | a round scored zero | gate on `bots/final`: about 6 s |
| 2 Rules Card | T+10 to 18 | `rules_card.json`, `zoo/variants/<name>.md` | converting to a misread rule | probe: about 1 s |
| 3 Convert | T+18 to 38 | simulator class, `VARIANTS` entry, tables, rebuilt bot | hold'em logic in another game | `gen_variant_tables.py` 30.7 s; writing the code not timed |
| 4 Safety gate | T+38 to 44 | `GATE: PASS`, `v1` uploaded | failed decisions on the platform | about 6 s |
| 5 Format corrections | T+44 to 50 | at most one measured change | untested cleverness | |
| 6 Gauntlet | beside 3 to 5 | points/table ± error, n, tables/min | promoting noise | 18,000 tables (A/B, nine line-ups) in 80 s |
| 7 to 9 Upload, practice runs, hand-off | to T+60 | `vN/`, STATE.md | a bad auto-activated bot; lost state | not exercised |

The scripts are not the bottleneck. The budgets are for what cannot be timed here: the kit
install, reading RULES.md, writing the simulator class and the `VARIANTS` entry, kit table
speed, and the human's uploads. `rehearsal/README.md` is the timed human rehearsal for
stage 3 (45 minutes allowed); its `RULES.md` is sealed and was not opened in this session.

Why each added piece exists:

- **`clock.py`**: an upload activates itself, so the cutoff before each snapshot has to be
  visible, not remembered.
- **`probe.py` and `rules_card.json`**: the gate, gauntlet and clock read limits and phases
  from one file filled from the real `state.config`, so a halved `decision_ms` or different
  payouts change the checks without code edits. Probing the kit and then our own simulator
  class gives a diff that tests our reading of the rules.
- **`gate.py`**: one PASS/FAIL that adds, to the repo's `build.py --check` and `tools/fuzz.py`
  (both of which it runs), timing against the card with margins, memory growth, the
  no-time-bank upload imitation, states built from the variant's own phases, and a count of
  exceptions raised inside any bot (it uses `sys.monitoring`, so it also works on bots
  without a `DEBUG_RAISE` switch, such as the kit's template).
- **`gauntlet.py`**: the same A/B on the kit and on the mini simulator. `tools/bench.py` is
  finer but mini-only.

Retired in the re-base (moved to the ignored `.claude/scratch/retired/`): `gen_table.py` and
`variant_snippets.py`, a table generator and variant block for the starter bot. The core's
`VARIANTS` and `tools/gen_variant_tables.py` do that job for the bot we actually upload.

## Rules check

Authority inside the repo: [`docs/official-format.md`](../docs/official-format.md),
[`docs/official-getting-started.md`](../docs/official-getting-started.md),
[`docs/event-day-setup.md`](../docs/event-day-setup.md). Day-of digest:
`sequoia-launch/references/rules.md`.

Fetched 2026-11-12:

| Page | Result | Differs from the docs? |
| --- | --- | --- |
| `pokerbot.sequoiacap.com/` | public; dates, eligibility, "from scratch", demo exhibits | no change |
| `pokerbot.sequoiacap.com/rules.html` | public; still blinds every 25 hands, 200-hand cap, 10,000 tables, one submission per 5 min, 100 MB | no change; `docs/official-format.md` overrides it (20, 250, at least 5,000, 30 s, 50 MB) |
| `pokerbot.sequoiacap.com/tournament` | **login wall**. Format, Getting started, team page, uploads are behind it | could not compare |
| `.../tournament/no-limit-2026-setup/SKILL.md` | public; version 2026-11-05.2, same as the installed copy | no change |
| Web search for the Boston variant or any result | nothing found | still unknown |

Pages to paste from behind the login if they changed: Format, Getting started, the team page,
any API or upload documentation.

Still assumed: pre-written code is allowed; uploads are browser-only (the setup skill shows
`/api/auth/api-key` and `/api/teams/<team>/machine[/keys]`, no upload endpoint);
`poker-agent play` takes `--seed` and prints the summary `practice.py` parses; the blind
ladder after 10/20; the kit runs on macOS; upload-to-ready time.

## Repo inventory

Current main, `8f76ac0`. "Re-measured" means run on 2026-11-12 in a scratch copy.

| Path | What it does | Status | Re-measured or trusted |
| --- | --- | --- | --- |
| `tools/core_agent.py` → `bots/<profile>/agent.py` via `tools/build.py` | the competition bots; `bots/final` is the upload; `VARIANTS` has holdem, discard_reveal, short_deck, omaha, auction, irish | ready | `build.py --check` ok; gate PASS; README's "26.6 against the starter's 19.0" re-measured as 24.55 ± 0.19 against 18.99 ± 0.16 over nine line-ups including the zoo (29.50 against 19.71 in the mixed field) |
| `starter/agent.py` | the original starter, now the baseline opponent | ready for hold'em | 0 failed decisions; fails `tools/fuzz.py`'s repeat-call check (global `random`) |
| `sparring/*` | five fixed opponents | ready | trusted |
| `zoo/` | 11 bots on main (5 `claude_*`, 6 `codex_*`) plus 12 weak first-draft bots (`gpt_*`, `codex_default_1`) added from `origin/overnight/prep-2026-11-11`, uncommitted | ready | `check_zoo.py` on the 12: all OK, 0 failed decisions |
| `zoo/variants/*.md`, `devtest/sim_variants.py` | rulesets and the simulator classes that play them | ready; our readings, not the kit | probe, gate and gauntlet run on irish, discard_reveal, short_deck |
| `rehearsal/` | sealed variant for a timed human rehearsal | ready | not opened, by its own rule |
| `practice.py`, `devtest/mini_sim.py` | upload check, upload-test imitation, line-ups; simulator with `--variant`, `--workers`, `--vary` | ready | every run in this session |
| `tools/fuzz.py` | random and malformed states; `DEBUG_RAISE` pass | ready | 5,000 states on `bots/final`: no failures; now a gate step |
| `tools/gen_variant_tables.py` | measures the variant tables in the core | ready | 30.7 s for all variants at 400,000 samples |
| `tools/bench.py` | per-table paired comparison, latency; mini only | ready; line-ups mixed, passive, aggressive, starters, zoo | trusted, not run |
| `tools/field_report.py`, `tools/field_fit.py` | field statistics from hand histories; settings sweep | history reader is a guess at the organizers' format | trusted, not run |
| `tools/check_zoo.py`, `bot_tests.py`, `eval_all.py`, `eval-results/` | zoo status; a 34-test battery; league and weak-field evaluations | ready | `check_zoo.py` run; the rest trusted |
| `ui/` | practice page with a version list (see `CLAUDE.md`) | kit engine tested only against a stand-in | trusted, not run |
| `docs/` | rules, setup, conversion procedure, strategy | current | read |

## The two team skills

Read after the re-base, as asked. `skills/competition-build` and `skills/mid-round-iterate`
(vkulk, 2026-11-12, both `disable-model-invocation: true`).

| Theirs | Adopted into sequoia-launch | Not adopted, and why |
| --- | --- | --- |
| Upload target `bots/final/agent.py`, never starter or zoo | yes, throughout | |
| Upload it unchanged first | yes, stage 1, with one guard: gate it on the kit first, and fall back to the kit's own `agent.py` if any decision fails | "unchanged is fine" is unverified until the kit shows how it scores an automatic choice |
| Conversion: ruleset file, `VARIANTS` entry, `gen_variant_tables.py`, `build.py`, fuzz | yes, stage 3, plus a simulator class and the probe diff | |
| Validation gates: check, fuzz, practice smoke | yes, all inside `gate.py`, plus timing margins, memory, upload imitation | |
| "Stop chasing mini-EV" in the build hour | yes: stage 5 is format corrections only | |
| Strategy spec and locked knobs | referenced, not repeated | one source of truth is `tools/core_agent.py` |
| Promote at about +1 point over 1,600 same-seed tables | same bar stated as 2 standard errors plus a fresh seed | their bench command's `ai_field` line-up was missing from `tools/bench.py` on main; added 2026-11-12 from the overnight branch |
| `bots/final_prev` as the rollback copy | `vN/` copies instead | one folder per upload matches what the team page lists |
| Commands run on the build machine | Mac with a local kit, gate repeated on the build machine | Claude Code runs on the Mac (decided 2026-11-12) |

What theirs lack and this adds: a clock and upload cutoff, a Rules Card from the real
`state.config`, hidden-exception and timing checks tied to the card, error bars on the kit,
how to read practice runs, a behind-the-clock path, and the human's go on every upload.

`mid-round-iterate` already is the iteration skill session 2 was going to write. Session 2
should extend it (add the clock, the cutoff and the gate, all of which exist in
`sequoia-launch` and can be referenced) rather
than start a third one.

## Strategy conclusions

Full text: `sequoia-launch/references/strategy.md` and `references/variants.md`.

1. **ICM under 50/30/20** (shim's `icm`): win chance needed to call an all-in is 0.556 with
   eight equal stacks, 0.652 on the four-handed bubble, up to 0.752 for the second stack
   calling the big stack with a short stack present, 0.571 three-handed, 0.500 heads-up.
   Winner take all is 0.500 everywhere.
2. **The core's ICM (`_icm_me`) prices the first three places only.** Fine for 50/30/20,
   approximate for flatter payouts.
3. **The cap rarely binds on the mini ladder** (old checkout, starter bot: 2 of 300 tables
   reached hand 250; median 153 hands). The real ladder decides.
4. **Where the points are scarce:** `final` scores 29 to 47 in hand-written fields and about
   16 to 17 in line-ups of the zoo's strategy bots. Against weak first-draft bots (zoo field
   3) it scores 30.96.
5. **Global call-widening against shovers loses** (old checkout, starter: -0.73 ± 0.23,
   n = 5,000 each). `final` uses the conservative `vs_shover="doc"`.
6. **Measurement:** per-table spread of the `final` against `starter` paired difference is
   about 21 points; detectable difference `2.8 x 21 / sqrt(tables per bot)`. 13,500 tables per
   minute on the mini simulator with 5 jobs; the kit's rate is the first number to measure.

## Dry runs

| Walk | Result |
| --- | --- |
| Current main, `irish` ruleset on the mini simulator: probe, gate, gauntlet | probe saw the `discard` phase (four cards, three-card board); gate PASS, p99 73 µs, 0 failed of 31,988; `final` 32.45 ± 0.48 against `starter` 12.19 ± 0.12 |
| Current main, `short_deck` | gate PASS, p99 38 µs; 24.69 ± 0.42 against 14.75 ± 0.41 |
| Current main, `discard_reveal` | probe saw `select` (three cards); gate PASS, p99 40 µs; 26.25 ± 0.45 against 17.93 ± 0.18 |
| Old checkout, card with `decision_ms` 0.5 | gate thresholds halved by themselves; PASS |
| Old checkout, payouts `[100]` | gauntlet passed the payouts through; starter ran unchanged; its bubble margin at 0 gave +0.30 ± 0.31, not detectable |

Not exercised: the kit in any form (`check`, `play`, flags, summary, speed); the real
`Action` format of a variant phase; the fuzz against the real SDK classes; `probe.py` when
the kit hides the temp dir; timing on the build machine; SSH and `scp`; uploads and the team
page; practice runs; and a conversion to a variant nobody here has seen (the sealed
rehearsal is for that).

The five most likely ways the day still goes wrong, and the patch:

1. **The kit's CLI or summary differs from what `practice.py` assumes.** Every parse goes
   through `common.summary()`, which stops with the raw output; stage 1 runs the gate on the
   kit at about T+3.
2. **The unconverted bot's automatic choice counts as a failed decision and the upload is
   rejected.** Stage 1 gates `v0` on the kit and falls back to the kit's own `agent.py`.
3. **Our simulator class misreads the rules, so tables and A/Bs are measured on the wrong
   game.** The probe diff between kit and class; the kit gauntlet as the final word.
4. **Timing is worse on the platform than on the laptop.** Margins of 25% (p99) and 50%
   (p99.9) of `decision_ms`, and the gate repeated on the build machine.
5. **A late upload activates itself just before a snapshot.** `clock.py` prints OPEN/CLOSED
   against a 5-minute cutoff; T+48 for round 1; the human's go for every upload.

A sixth, already hit once: **working from a stale checkout.** Stage 0 now starts with
`git pull`.

## Open questions the announcement will answer

1. The variant: hole cards, phases and their `Action` format, showdown rule, deck, rankings,
   betting structure.
2. Payouts: 50/30/20, something else, or drawn per table.
3. The real blind ladder, hence whether the hand cap matters.
4. `decision_ms`, `time_bank_ms`, `memory_bytes` as the kit reports them.
5. The kit's CLI: `--seed`, summary shape, tables per minute.
6. Whether the kit scores an automatic choice in a variant phase as a failed decision.
7. Upload mechanics and upload-to-ready time.
