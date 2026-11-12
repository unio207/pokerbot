# STATE: hand-off from sequoia-launch to mid-round-iterate

Updated: 2026-11-12 16:40, before the event (no clock running). Machine: MacBook M5, Python 3.12.15.
Repo: `main`, the readiness commit on top of `3cff4e7` (adds `SETTINGS`), pushed.
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

Everything else comes from `_BASE` in the same file. The 13 float knobs (these, plus
`hu_open=0.65` from `_BASE`) are repeated in the `SETTINGS` table below the profiles with the
same values. `SETTINGS` is applied last, so it overrides the profile: change a knob there.

## Gate

`gate.py bots/final`, runner mini, SDK stand-in, template card: **GATE: PASS** (one warning:
rules card not filled).

- build check: `bots/` match `tools/core_agent.py`
- fuzz: 20,000 states, 0 bad; 0 exceptions raised inside the bot on 10,000 clean states
- `tools/fuzz.py`: 5,000 states, no failures
- timing, 20,000 decisions in-process: p50 18 µs, p99 37 (allowed 250), p99.9 42 (allowed
  500), max 60, 0 over 1,000 µs
- memory: largest blob 96 bytes over a 250-hand busy table (allowed 16,384)
- tables: 300 over 3 line-ups, 0 failed decisions of 32,081
- upload-test imitation (no time bank): 0 of 3,000 failed
- `agent.py` 70,036 bytes; import 0.010 s

On the build machine (2 cores, Python 3.12.3, mini simulator, 2026-11-12 16:45), same commit:
**GATE: PASS** in 15 s. Timing there: hold'em p50 44 µs, p99 81, p99.9 93, max 156; with the
`irish` card p99 157, p99.9 172, max 608; with the `discard_reveal` card p99 90, p99.9 102,
max 152. The build machine is about 2.4 times slower than the Mac per decision, and a
four-card discard handler already uses 157 of the 250 µs our p99 margin allows.

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

Variant rulesets on the mini simulator, `final` against `starter`, all nine line-ups,
`--tables 300`, seed `gauntlet`, n = 2,700 per bot (re-measured 2026-11-12 16:33): irish
31.58 ± 0.42 against 10.62 ± 0.17; short_deck 24.24 ± 0.41 against 16.02 ± 0.30;
discard_reveal 25.68 ± 0.35 against 18.21 ± 0.33. Zero failed decisions.

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
- `tools/field_fit.py --sweep` and `tools/bench.py` play the mini simulator only, and
  `bench.py` plays hold'em only. `skills/mid-round-iterate` therefore promotes on
  `gauntlet.py bots/final --vs vN` and `gate.py`, which follow the kit and the variant. The
  sweep's rows are hints from our own ruleset, not kit numbers.
- `tools/field_report.py`'s reader for the organizers' history format is a guess.
- `starter` fails `tools/fuzz.py`'s repeat-call check because it bluffs with the global
  `random`. It is an opponent, not an upload, so this only matters if someone uploads it.

## First experiments to try

1. After the first hand histories: `tools/field_report.py --inspect`, fix `kit_hands`, then
   the report. Everything else follows from what the field is.
2. `tools/field_fit.py --sweep --bot bots/final --variant <mini_name>` against the look-alike field.
3. If the field looks like zoo field 1 or 4 (strong bots), `points_tight` and `call_margin`
   are the first knobs; if it looks like zoo field 3 (weak first drafts), `steal_widen`.
4. If practice runs show many 2nd and 3rd places and few firsts: `hu_open` up.

## Log

- 2026-11-12, session 1: launch skill written against a checkout 49 commits behind main;
  found when the zoo looked empty. Pulled to `8f76ac0`, re-based the skill on `bots/final`
  and the repo's tools, moved it to `skills/sequoia-launch/`, added the 12 weak zoo bots from
  the overnight branch. Nothing uploaded. Pre-written code is allowed (Henry, 2026-11-12).
  Still open: whether there is an upload command (assume the team page in a browser).
- 2026-11-12 16:20 to 16:40, readiness check: every command and identifier in the three
  skills cross-checked against the code. Two faults fixed. (1) `tools/core_agent.py` had no
  `SETTINGS` table, so `field_fit.py --sweep --bot bots/final` exited; ported from PR #10
  (same values as the profile: the `--seed parity` gauntlet was identical before and after,
  and `--seed baseline` reproduces 24.55 ± 0.19 against 18.99 ± 0.16). (2)
  `mid-round-iterate` promoted on `tools/bench.py`, which plays hold'em on the mini
  simulator only; it now promotes on `gauntlet.py --vs vN` and `gate.py`, with the launch
  skill's promotion rule and upload checklist. Gate re-run on the rebuilt bot: PASS. The
  mid-round commands were run once on the mini `irish` ruleset in a scratch copy; reading a
  real hand-history file is still untested. PR #10 stays open (shim path order, hiding
  `zoo/_template` in the practice page).
- 2026-11-12 16:38 to 17:06, dry run and build machine. A fresh agent followed
  `sequoia-launch` on the sealed `rehearsal` variant in a scratch copy (mini simulator as
  the kit). It was cut off by a network error at T+27, with the conversion built and `v1/`
  made. Measured afterwards on what it left: build check ok; `GATE: PASS`, 0 failed
  decisions of 34,669, p99 42 µs; converted 26.13 ± 0.44 against unconverted `v0`
  23.29 ± 0.69, +2.84 ± 0.72 (n = 900 per bot, one seed). The build machine was synced to
  `96575d3` and passes the gate (numbers under "Gate"). The copy command in the skills is
  now `rsync` with excludes; `starter-kit/` is ignored by git; the skills' `PY=` line also
  finds a kit unpacked inside the repo.
