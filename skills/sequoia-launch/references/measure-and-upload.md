# Measuring, uploading, reading practice runs (stages 6 to 8)

## Gauntlet (stage 6)

```bash
$PY $K/gauntlet.py bots/final --vs v0                     # converted against the active upload
$PY $K/gauntlet.py bots/final --vs v1 --seed fresh1 --tables 400   # confirmation on new deals
$PY $K/gauntlet.py bots/final                             # one bot: points/table ± error, n, tables/min
```

- Line-ups are fixed: `practice.py`'s five (mixed, passive, aggressive, seven starters, four
  of us with four starters) plus one line-up per seven zoo bots (four with the 23-bot zoo).
  The opponents are `starter/`, `sparring/` and `zoo/`: do not edit them on the day.
- Versions are copies of the built file: `mkdir vN && cp bots/final/agent.py vN/`. `--vs vN`
  then compares the working `bots/final` with what is uploaded.
- Same `--seed` means the same seating and the same decks for both versions. The error bar on
  the difference comes from the ten batch differences and is what the verdict uses.
- **Promotion rule:** the difference over all line-ups is above 2 standard errors, and still
  positive on a fresh seed; zero failed decisions; the gate passes. Otherwise the incumbent
  stays. `skills/mid-round-iterate` uses this same rule.
- With the kit installed the gauntlet plays the kit's engine; without it, the mini simulator
  (and the ruleset named in the card's `variant.mini_name`).
- On the mini simulator, `tools/bench.py` is the finer instrument: it differences per-table
  points and reports latency. It plays hold'em only and does not run on the kit, so it is
  never the go/no-go for a converted bot.
- Parallel runner calls (`--jobs`, default half the cores) slow each decision. If failed
  decisions appear only under load on the kit, rerun with `--jobs 1` before believing them.

### What can be detected

Measured on the mini simulator, MacBook M5, 5 jobs, 2026-11-12, `bots/final` against
`starter`, nine line-ups, 1,000 tables per line-up per bot: 13,500 tables per minute;
per-table spread of the paired difference about 21 points (0.22 x sqrt(9,000)). Smallest
difference detectable at 2.8 standard errors (5% false alarm, 80% power):

| A/B length | Tables per bot | Detectable difference, points per table |
| --- | --- | --- |
| 5 min | 33,750 | 0.31 |
| 10 min | 67,500 | 0.22 |
| 30 min | 202,500 | 0.13 |

**These are mini-simulator speeds.** The kit runs each bot in a sandboxed process and will be
slower by an unknown factor; `gauntlet.py` prints the same three lines for whatever machine
and runner it is on. By hand: `2.8 x 21 / sqrt(tables per bot)`: 1.9 points at 1,000 tables
per bot, 1.0 at 3,500, 0.5 at 14,000. Two close versions of the same bot differ less per
table than `final` and `starter` do, so their A/B is tighter than this.

## Upload checklist (stage 7)

Every upload and every switch of the active bot needs the human's explicit go. The agent
prepares; the human clicks.

1. `$PY $K/clock.py`: uploads must be OPEN (see the cutoff below).
2. `$PY tools/build.py`, then `mkdir vN && cp bots/final/agent.py vN/` (next free N). The
   upload is `vN/agent.py`: one file, no zip needed.
3. `$PY $K/gate.py bots/final` prints `GATE: PASS`. Then on the build machine, whose timing is
   the one that counts:
   `rsync -a --exclude .git --exclude .claude --exclude starter-kit --exclude __pycache__ ./ no-limit-2026-build:work/pokerbot/` and
   `ssh no-limit-2026-build 'cd ~/work/pokerbot && ../starter-kit/.venv/bin/python skills/sequoia-launch/scripts/gate.py bots/final'`.
4. State to the human: the file path, what changed since the active version, the gate line,
   the gauntlet difference with its error and n. Ask for the go.
5. The human uploads on the team page (or by the kit's documented command if there is one;
   never by a guessed API call, and the API key never goes to the build machine).
6. Confirm on the team page: the upload is **ready**, it is the **active** bot, and after the
   next practice run it shows **0 missed decisions, 0 restarts, no errors**.
7. Append a line to `skills/STATE.md`: version, time (T+), what changed, gate, gauntlet.
8. Rollback is never a re-upload: switch the active bot back to the previous ready version on
   the team page.

### The cutoff, derived

An upload becomes active by itself once ready. So an upload that lands just before a snapshot
is scored without anyone having looked at it. Needed between upload and snapshot: the upload
test and readiness (not measured yet: time it on the first upload and write it in STATE.md),
one look at the team page, and room for one switch back, at the site's rate limit of one
upload per 30 s. Until the first upload is timed, allow 5 minutes:

- **No upload in the last 5 minutes before a snapshot**, unless the active bot is failing
  (missed decisions, restarts, rejected) and the upload is the last version that was clean.
- **Round 1:** the last practice run that can show a problem before the T+60 snapshot starts
  around T+50. A version meant for round 1 should be active by **T+48**; anything later goes
  in unseen by any practice run and needs a clean gate on the build machine instead.
- **Rounds 4 to 6** (15/21 of the score): only versions that passed the promotion rule. There
  are no practice runs after the build, so the gauntlet and the gate are the only evidence.

## Reading a practice run or a round result (stage 8)

| What the team page shows | Meaning | Do |
| --- | --- | --- |
| Missed decisions above 0 | timeouts, exceptions or illegal actions on the real platform | top priority. Read the latest errors and the hand history's failed decisions. If the previous version had none, switch back now, fix after. |
| Restarts above 0 | the process crashed or stalled (import, memory, a hang) | switch back now. Check import time and anything done at import. |
| Missed decisions only in the first decisions of tables | slow first call | build tables at import, not on first use |
| Average points below par (sum of payouts / players, 12.5) by more than 1.3 | weaker than the field; one practice run of about 1,000 tables has a standard error near 0.6 (`docs/official-format.md`) | check the place histogram before changing anything |
| Many 2nd and 3rd, few 1st | too tight once in the points | `points_tight` down, `hu_open` up |
| Many 6th to 8th | busting early | tighter opens and calls (`call_raise`, `call_margin`); look for a variant-scoring error in the histories first |
| Two versions differ by less than about 1.8 points across two practice runs | inside the noise of two independent 1,000-table runs (0.6 x 1.4 x 2) | believe the gauntlet A/B, not the practice runs |
| Round result arrives after the next snapshot | normal (`docs/official-format.md`) | never wait for it to decide an upload |

Hand histories: `tools/field_report.py <file> --hero <our name>` (`--inspect` first; the
organizers' format was not known when it was written). That, `tools/field_fit.py --sweep`
and what to change are `skills/mid-round-iterate`'s job. Nothing about named opponents goes
into the bot: seats are anonymized and cross-table information breaks the rules.
