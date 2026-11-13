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
- **The gauntlet does not promote.** It answers two questions: does the converted bot beat
  the unconverted one on the same seeds (stage 3), and do failed decisions appear under load.
  At Pittsburgh it scored the round 1 bot at 28.08 ± 0.25 where the platform scored it 12.40,
  and read v94 against v13 as -0.27 ± 0.32 where the platform had v94 at +1.59 against the
  median (practice 8) and v13 at -1.00 (round 3). Its opponents go
  to showdown in 20 to 90% of hands; real teams in 8 to 13%. The promotion rule is below.
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

## Promotion rule

One rule, used here and in `skills/mid-round-iterate`. A version stays active at a round
snapshot only when:

1. `gate.py bots/final` prints `GATE: PASS`, on the build machine too.
2. Before any history exists (the build hour): it is the conversion, and it beats the
   unconverted bot on the kit on two seeds. After that: the change answers a gap measured in
   a hand history against that run's ten best teams (`tools/history/`).
3. It played a practice run and its points minus the field median (`$PY $K/results.py`) beat
   the active version's latest figure by more than the two margins combined: about 0.5 when
   both runs have 10,000 tables. When no practice run fits before the snapshot, say so to the
   human; `skills/mid-round-iterate` lists what must hold then.
4. The human gives the go.

Compare on points minus the median, not on points: the field's level moves (the median was
13.28 in round 5 and 13.71 in round 6).

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
   the measured gap it answers, and whether it has played a practice run. Ask for the go.
5. The human uploads on the team page (or by the kit's documented command if there is one;
   never by a guessed API call, and the API key never goes to the build machine).
6. Confirm on the team page: the upload is **ready**, it is the **active** bot, and after the
   next practice run it shows **0 missed decisions, 0 restarts, no errors**.
7. Append a line to `skills/STATE.md`: version, time (T+), what changed, gate, and its
   platform result once it has one.
8. Rollback is never a re-upload: switch the active bot back to the previous ready version on
   the team page.

### The cutoff, derived

An upload becomes active by itself once ready. So an upload that lands just before a snapshot
is scored without anyone having looked at it. Needed between upload and snapshot: the upload
test and readiness (under 60 s at Pittsburgh; time it again on the first upload),
one look at the team page, and room for one switch back, at the site's rate limit of one
upload per 30 s. Until the first upload is timed, allow 5 minutes:

- **No upload in the last 5 minutes before a snapshot**, unless the active bot is failing
  (missed decisions, restarts, rejected) and the upload is the last version that was clean.
- **Round 1:** the last practice run that can show a problem before the T+60 snapshot starts
  around T+50. A version meant for round 1 should be active by **T+48**; anything later goes
  in unseen by any practice run and needs a clean gate on the build machine instead.
- **Rounds 2 to 6:** only versions that passed the promotion rule. Practice runs go on
  between the scored rounds (four at Pittsburgh, each about ten minutes after a round's
  start), so a candidate can play one before the round it is meant for. Rounds 5 and 6 are
  21/32 of the score: there the active version must also be clean in the run in progress.

## Reading a practice run or a round result (stage 8)

| What the team page shows | Meaning | Do |
| --- | --- | --- |
| Missed decisions above 0 | timeouts, exceptions or illegal actions on the real platform | top priority. Read the latest errors and the hand history's failed decisions. If the previous version had none, switch back now, fix after. |
| Restarts above 0 | the process crashed or stalled (import, memory, a hang) | switch back now. Check import time and anything done at import. |
| Missed decisions only in the first decisions of tables | slow first call | build tables at import, not on first use |
| Points below the field median (`results.py`) by more than the margin | weaker than the field. Par (12.5) is not the bar: the median of the teams that played was 12.95 to 14.22 | read the run's history against its ten best teams before changing anything |
| Many 2nd and 3rd, few 1st | playing to survive, and losing heads-up. At Pittsburgh: 9% firsts against the leaders' 26% | `icm_scale`, `points_tight`, `bubble_margin` to 0; `tools/history/headsup.py` for the heads-up rates |
| Many 6th to 8th | busting early | tighter opens and calls (`call_raise`, `call_margin`); look for a variant-scoring error in the histories first |
| Two versions differ, minus the median, by less than the two margins combined | inside the noise (about 0.5 for two 10,000-table runs, 0.64 for two of 5,000) | no evidence either way; do not turn to the gauntlet for a verdict |
| A run has finished | its results for every team are on the portal within seconds, its history on the team page | `results.py`, then the readers |

Hand histories: the seven readers in `tools/history/`, each a streaming pass over one
download, comparing us with the run's ten best teams. Which to run and what to change are
`skills/mid-round-iterate`'s job. `tools/field_report.py` also reads the format, but its
types and advice were set on hold'em. Nothing about named opponents goes into the bot: seats
are anonymized and cross-table information breaks the rules.
