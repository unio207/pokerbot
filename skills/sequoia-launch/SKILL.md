---
name: sequoia-launch
description: Launch playbook for Sequoia's NO LIMIT '26 poker bot tournament (regional and finals). Takes the team from the variant announcement to a legal, crash-proof, variant-converted bots/final that is the active upload with a measured baseline, inside the 60-minute build window, then hands off to mid-round-iterate. Use when the user says the variant is out, the rules are out, the competition started, build the bot, set up for the tournament, or asks to rehearse the launch.
---

# Sequoia launch

From "variant announced" to "active, safe, converted bot plus a baseline", on a clock.

This skill is the clocked version of [`skills/competition-build`](../competition-build/SKILL.md)
(same upload target, same conversion steps) with four things added: a clock with upload
cutoffs, a Rules Card read from the kit, one PASS/FAIL gate, and a gauntlet with error bars.
The strategy itself is not decided here: it is the locked `final` profile.

All paths are relative to the repo root (`pokerbot/`; on the build machine `~/work/pokerbot`,
kit at `~/work/starter-kit`). Set once per shell:

```bash
K=skills/sequoia-launch/scripts
PY=python3.12; for k in starter-kit ../starter-kit; do [ -x $k/.venv/bin/python ] && PY=$k/.venv/bin/python; done
```

The scripts find the kit by themselves (`practice.find_kit`) and print which runner they
used. "mini" means the unofficial simulator: it plays hold'em and our own versions of the
rulesets in `zoo/variants/`, never the kit's engine.

## Why the plan looks like this

1. **1 ms per decision rules out search.** Everything expensive is a table measured before
   upload and embedded in `tools/core_agent.py`.
2. **No active bot at a snapshot scores zero.** A legal bot goes up first; every later upload
   only has to beat it.
3. **Rounds weigh fibonacci** (`round_weighting` in `portal.py`; 1, 2, 3, 5, 8, 13 by Henry's
   reading, total 32: round 6 is 13 times round 1). A gain counts in every round after it
   lands, so most of the score is won by iterating after the build (`mid-round-iterate`); the
   build hour's job is a converted, safe bot and a working hand-history reader. A failure
   costs more the later it lands (round 6 is 41%), so nothing uploads without the gate. Read
   each round's real weight from `portal.py` once rounds exist.
4. **Memory resets per table and seats are anonymous.** Adaptation lives inside one table.
5. **Results lag a round.** Decisions rest on the gate, the gauntlet and practice runs.
6. **Converting to the variant is the largest measured gain** (`docs/event-day-setup.md`: 30.9
   against 17.3 points per table in the `irish` rehearsal). The build hour is spent there,
   not on tuning.

## The clock

Start it the moment the variant is announced: `$PY $K/clock.py start` (or `start 18:02`).
Run `$PY $K/clock.py` at every stage boundary and before every upload.

| Stage | Window | Output | Done when | Guards against |
| --- | --- | --- | --- | --- |
| 0 Before the day | earlier | checklist below ticked | each line's check passes | losing build minutes to setup |
| 1 Kit + active bot | T+0 to 10 | kit installed, `v0` uploaded | team page shows an active bot | a zero round |
| 2 Rules Card | T+10 to 18 | `rules_card.json`, `zoo/variants/<name>.md` | every field filled or listed as open | converting to a misread rule |
| 3 Convert | T+18 to 38 | `VARIANTS` entry, tables, rebuilt `bots/final` | conversion beats `v0` on the same seed | hold'em logic in another game |
| 4 Safety gate | T+38 to 44 | `GATE: PASS`, `v1` uploaded | active, 0 missed decisions | failed decisions on the platform |
| 5 Format corrections | T+44 to 50 | at most one measured change | passed the promotion rule | untested cleverness |
| 6 Gauntlet baseline | beside 3 to 5 | points/table ± error, n, tables/min | numbers in STATE.md | promoting noise |
| 7 Upload | each version | `vN/` copy, upload, confirmation | ready, active, clean | a bad auto-activated bot |
| 8 Practice runs | every 10 min | one line per run in STATE.md | counters read | flying blind |
| 9 Hand-off | T+52 to 60 | `skills/STATE.md` | `mid-round-iterate` can start from it | losing the state between skills |

## Reading the portal

`$PY $K/portal.py` prints, with the saved API key (read-only, never printed, Mac only):

- **competition:** `variant` and `variant_announced_at` (the exact T+0: pass its local time to
  `clock.py start HH:MM`), `frozen`, `round_weighting`;
- **uploads:** every submission and its state, so "ready and active" is checked here after
  each upload instead of asking the human;
- **health:** decisions, missed decisions, restarts and errors per run (stage 8);
- **rounds and practice runs:** results as they complete, and whatever links they carry.

Run it at every stage boundary. Uploading and switching the active bot stay with the human on
the team page: no upload endpoint is documented, and none is to be guessed. If a round entry
carries a hand-history link, ask the human before downloading it.

## Stage 0: before the day

- [ ] `/no-limit-2026-setup` run once; `ssh no-limit-2026-build` connects (before opening it prints the opening time, which still proves the key).
- [ ] `git pull` and `git status`: the checkout is current main. (This skill was first written against a checkout 49 commits behind.)
- [ ] `$PY tools/build.py --check` passes; `$PY $K/gate.py bots/final --mini` prints `GATE: PASS`.
- [ ] `$PY $K/gauntlet.py bots/final --vs starter --mini` prints nine line-ups and a tables/min figure.
- [ ] The timed rehearsal in `rehearsal/README.md` done by whoever converts on the day.
- [ ] Pre-written code: allowed (confirmed 2026-11-12). Upload command: unknown, so look for one in the kit's `README.md` and `AGENTS.md`; otherwise the team page.
- [ ] Team page open in a browser, logged in; the human knows where uploads and the active-bot switch are.

## Stage 1 (T+0 to 10): kit and an active bot

1. `$PY $K/clock.py start`.
2. Run the organizers' skill: `/no-limit-2026-setup`. It downloads and installs the kit and
   runs its smoke test. Do not duplicate its steps. Claude Code runs on the Mac, so have the
   kit locally too: unzip `starter-kit.zip` beside this repo and build its `.venv` (the
   skill's local step). The build machine's copy is for timing.
3. Copy the repo to the build machine (it has a copy already; this updates it, and leaves
   out git history, session files and a kit unpacked inside the repo):
   `rsync -a --exclude .git --exclude .claude --exclude starter-kit --exclude __pycache__ ./ no-limit-2026-build:work/pokerbot/`
4. `mkdir v0 && cp bots/final/agent.py v0/` then `$PY $K/gate.py v0 --tables 30`.
5. Decide the first upload:
   - the gate passes on the kit with 0 failed decisions: upload `v0/agent.py` (the unchanged
     `bots/final`, which answers an unknown phase with the automatic choice).
   - any failed decision: upload the **kit's own `agent.py`** now; it passes the kit's smoke
     test by construction. Fix in stage 3.
6. Human go, upload, confirm active. Time from upload to ready goes in STATE.md.

Done when the team page shows an active bot. If this is not true at T+10, nothing else starts.

## Stage 2 (T+10 to 18): Rules Card

1. `$PY $K/probe.py` plays 6 tables with a probe bot and writes `rules_card.json` with the
   real `state.config`, phases, legal actions per phase and card counts.
2. Read the kit's `RULES.md`, `README.md`, `AGENTS.md`. Correct `variant`, `limits`,
   `schedule` in the card by hand. `references/rules.md` lists what we assumed before the kit.
3. Write the ruleset as `zoo/variants/<name>.md` from `zoo/variants/TEMPLATE.md`. Its "What a
   bot must implement" section is the checklist for stage 3.
4. Fill `invalidates` in the card: which of `detect`, `phases`, `preflop`, `postflop`, the
   hand ranking or the deck the variant changes (`references/variants.md`).
5. Ask the human only when a rule is ambiguous **and** the two readings need different code.
   Write other doubts in `open_questions` and take the reading the kit's example bots imply.

Done when `variant` and `config` in the card come from the probe, `limits` and `schedule`
have been checked against the kit's docs (the probe cannot see them and leaves the
template's values without a marker), and the ruleset file exists. If the probe prints
"config differs between tables", payouts or blinds are drawn per table: read
`config_observed` in the card.

## Stage 3 (T+18 to 38): convert

Follow "Converting to the announced variant" in `docs/event-day-setup.md`, with the family
table and patterns in `references/variants.md`:

1. Variant class in `devtest/sim_variants.py` (the `Irish` class is the pattern), so the mini
   simulator can deal it. Set `variant.mini_name` in the card to its name.
2. Cross-check our reading against the kit: `$PY $K/probe.py --mini --variant <name>` must show
   the same phases, card counts and action kinds as the kit probe from stage 2 did.
3. One entry in `VARIANTS` in `tools/core_agent.py`; a job in `tools/gen_variant_tables.py`;
   `$PY tools/gen_variant_tables.py tools/core_agent.py --samples 400000`; `$PY tools/build.py`.
4. `$PY $K/gauntlet.py bots/final --vs v0 --tables 300`: the converted bot must beat the
   unconverted one on the same seeds, on the kit when it is installed.

Hold'em unchanged: skip to stage 5.

## Stage 4 (T+38 to 44): the safety gate. Never skipped.

`$PY $K/gate.py bots/final` then the upload checklist in `references/measure-and-upload.md`.
The gate reads every limit from the Rules Card and checks: `tools/build.py --check`, the
runner's `check`, sizes, import time, its own fuzz on states built from the card's phases
(including exceptions hidden by the bot's `try`), `tools/fuzz.py`, decision time against
`decision_ms` with margins, memory growth, 300 tables with zero failed decisions, and on the
mini simulator the no-time-bank upload test. `GATE: FAIL` means no upload: fix, or keep the
active bot. Timing is trusted only from the build machine.

## Stage 5 (T+44 to 50): format corrections only

`references/strategy.md`. Only what the Rules Card contradicts: payouts, the blind ladder and
the cap, antes. One change per A/B, through the promotion rule. Field exploits and `SETTINGS`
sweeps belong to `mid-round-iterate`, after hand histories exist.

## Stage 6: gauntlet and baseline

While a gauntlet runs, fix the hand-history reader once, before any round exists: the kit's
`hand-history/` folder holds a sample in the download format, so run
`$PY tools/field_report.py --inspect <kit>/hand-history/<sample file>` and adjust `kit_hands`
in `tools/field_report.py` until the report parses it. Our name in the files is the team
name, `Team Allow It`.

`$PY $K/gauntlet.py bots/final --vs v0` as soon as the conversion builds. Record points/table
± error with n, tables/min, and the detectable-difference lines. Details and the promotion
rule: `references/measure-and-upload.md`. On the mini simulator `tools/bench.py` does a
finer per-table paired comparison, hold'em only; the gauntlet is the one that plays the
variant and also runs on the kit.

## Stage 7: upload

The checklist in `references/measure-and-upload.md`. The human gives the go for every upload
and every active-bot switch. No upload in the last 5 minutes before a snapshot unless it
replaces a failing bot; a round-1 version should be active by T+48.

## Stage 8: practice runs

After each one, read missed decisions, restarts, errors, average, places. The table in
`references/measure-and-upload.md` says what each triggers. One line per run in STATE.md.

Practice runs are the only real-platform evidence before round 1 and are too noisy to A/B
(standard error about 0.6 per run). If one offers a hand history, ask the human to download
the subset and run `tools/field_report.py` on it during the build: it is the first read of
the real field, and it lets the first window after T+60 ship a change instead of waiting for
round 1's lagging history.

## Stage 9 (T+52 to 60): hand off

Fill `skills/STATE.md` from `templates/STATE.md`: active version, the `final` profile's knobs,
gauntlet baseline with n, tables/min, upload-to-ready time, known weaknesses, first
experiments. No new code after T+52. Then `skills/mid-round-iterate` takes over.

## Behind the clock

Never shrink: an active bot (stage 1) and the gate before any upload (stage 4).

| If | Then |
| --- | --- |
| T+18 and the Rules Card is not done | keep only `config`, `phases`, `hole_cards`; go to stage 3 |
| T+30 and no simulator class yet | skip it: write the `VARIANTS` entry with `phases` handlers only, reuse the nearest family's tables, test on the kit |
| T+40 and the conversion does not beat `v0` | ship phase handlers only (no failed decisions), keep hold'em scoring; tables later |
| T+45 and the gate still fails | stop changing the bot; the active bot stays; find the failing check's cause, nothing else |
| T+48 and no measured improvement | upload nothing more before round 1; round 1 is 1/32 |
| the kit will not install locally | work on the build machine over SSH; if that fails too, upload the kit's `agent.py` by hand and tell the organizers |
| gate tables are slow on the kit | `--tables 30`; never drop the fuzz or timing parts |

## Rules that do not bend

- Never upload or switch the active bot without the human's go in this session.
- Never print, log or copy the API key or a private key; never put either on the build machine.
- Never carry information between tables in the bot. Never import `poker_engine` or `pokerkit`.
- Edit `tools/core_agent.py`, never `bots/*/agent.py` (generated; the gate fails on drift).
- Never edit `starter/`, `sparring/` or `zoo/` bots on the day: they are the fixed opponents.
- Do not share the variant outside the team before the event ends (official rules 6.4).

## References

- `references/rules.md`: format, limits, failure modes, what is still assumed. Stage 2.
- `references/variants.md`: families, which existing `VARIANTS` entry to copy, timings. Stage 3.
- `references/strategy.md`: payouts and ICM, the cap, which knobs answer which format change. Stage 5.
- `references/measure-and-upload.md`: gauntlet, promotion rule, upload checklist, cutoff, practice runs. Stages 6 to 8.
- `templates/rules_card.json`, `templates/STATE.md`.
- Background, not needed on the day: `skills/RESEARCH_NOTES.md`.
