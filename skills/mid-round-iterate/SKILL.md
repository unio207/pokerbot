---
name: mid-round-iterate
description: >-
  Mid-round No Limit 2026 iteration: read each finished run's result and hand
  history against that run's ten best teams, copy the largest measured gap, pass
  the gate, test the candidate in a practice run and promote it on points minus
  the field median.
  Use between scored rounds once the first practice run has finished, or when
  changing the active bots/final upload without rewriting architecture.
disable-model-invocation: true
---

# Mid-round iterate (No Limit 2026)

Improve the already-uploaded `bots/final` between round snapshots. This is where most of the
score is won. Never experiment without a rollback. Architecture rewrites belong in
`competition-build`, not here.

Rewritten after the Pittsburgh regional (2026-11-12). The first version of this skill judged
changes on the kit gauntlet and swept `SETTINGS` on the mini simulator. Neither tracked the
field: the gauntlet scored the round 1 bot at 28.08 points per table and the platform scored it
12.40, and four rounds went by at 11.64 to 13.04. Rounds 5 and 6 (15.37 and 15.96) came from
the method below. The record is `skills/STATE.md` and `docs/pittsburgh-results.md`.

Rounds weigh fibonacci (1, 2, 3, 5, 8, 13, total 32: round 6 is 13 times round 1 and 41% of the
score). Two consequences:

- **Gains: ship early.** A change active from round k counts in every round after it: 31/32
  of the weight from round 2, 29 from 3, 26 from 4, 21 from 5, 13 from 6. The same +0.5
  points per table is worth 2.4 times as much shipped for round 2 as for round 6.
- **Risk: a broken bot costs 13/32 in round 6 and 8/32 in round 5.** Nothing uploads without
  the gate, in any window.

Start from `skills/STATE.md`, written by `sequoia-launch`: the active version `vN` and the
upload-to-ready time. Append one line there per upload and per run. Uploading uses the launch
skill's checklist (`skills/sequoia-launch/references/measure-and-upload.md`): one gate, one
promotion rule.

## What judges a change

| Evidence | What it is good for | What it got wrong at Pittsburgh |
| --- | --- | --- |
| The platform's result for a run (`results.py`): points minus the field median | the verdict on a version | nothing; it is the score |
| The run's hand history against its ten best teams (`tools/history/`) | finding what to change, in chips per situation | nothing found |
| `gate.py` | crashes, illegal actions, timing, memory | nothing; no missed decision in 14 runs |
| Our own uploaded versions against each other on the kit, two seats each | a rough order when no practice run fits | could not separate v971 from v96 (+0.54 ± 0.60) |
| `gauntlet.py` against starter, sparring and zoo bots | failed decisions under load | every preflop change read as flat; v94 against v13 read as -0.27 ± 0.32 where the platform had v94 at +1.59 against the median and v13 at -1.00 |
| `tools/field_fit.py --sweep`, `tools/bench.py` | nothing here: they play the mini simulator, which has no class for a kit-only variant | not used |

The kit's opponents go to showdown in 20 to 90% of hands; real teams in 8 to 13%. A change
that beats them says nothing about the field.

## When to use

- After any finished run, practice or scored: its result is on the portal within seconds
  and its hand history can be downloaded from the team page.
- Between round starts (a snapshot freezes the **active** bot at the start of each run).

## Constraints that shape iteration

| Fact | Implication |
| --- | --- |
| Rounds start 20 minutes apart; a practice run starts about halfway between two rounds | Each window has one practice snapshot to test a candidate and one round snapshot that counts |
| Round 6's 20,000 tables took 9 minutes | A round's result and history arrive at about the time of the next practice snapshot |
| The snapshot takes whatever is active | The candidate is active at the practice snapshot; the best platform-tested version is active at the round snapshot |
| No active bot scores zero for the round | Always keep a ready, previously good upload selectable |
| 1 ms, never fail | Gate after every edit, on the build machine for timing |
| Seats are anonymous; memory is per table | Copy population frequencies; nothing about a named team goes into the bot |

## Every window (S is the round snapshot that just happened)

Run `$PY $K/clock.py` at each step.

| Time | Step |
| --- | --- |
| S+0 to 2 | `portal.py`: the round that just started is the active version's health. Missed decisions or restarts above 0: switch back first, then fix. `results.py`: the practice run that just ended. |
| S+2 to 8 | The newest finished run's history against its ten best teams (commands below). Pick the one largest gap. Write the change, `build.py`, `gate.py`. |
| before the practice snapshot (about S+10) | The human's go and the upload: the candidate plays the practice run. |
| when the practice run ends | `results.py`: the candidate's points minus the field median against the active version's latest. Promote, or switch back on the team page. |
| before the next round snapshot | The active bot is decided, with the card's cutoff to spare (5 minutes by default). |

At Pittsburgh an upload was ready in under 60 seconds, and the two latest uploads of the night
landed 4.2 and 3.6 minutes before their snapshots.

## The loop

```text
Iterate:
- [ ] results.py: our points, rank, the field median, the ten best teams of the run
- [ ] Download that run's history from the team page (the human; the first 10,000 tables)
- [ ] chipflow, opens, headsup against the ten best: where do we lose chips that they win?
- [ ] freq2 for that situation: the ten best teams' measured frequencies
- [ ] One change in tools/core_agent.py that moves our frequency to theirs
- [ ] build.py, then gate.py bots/final: GATE: PASS, then again on the build machine
- [ ] Upload checklist (human go, clock, cutoff); the previous vN stays as rollback
- [ ] results.py after the practice run: promote or switch back; one line in STATE.md
```

### Commands

From the repo root, on the Mac (the kit beside the repo, the API key local). The build machine
is for the gate's timing.

```bash
K=skills/sequoia-launch/scripts
PY=python3.12; for k in starter-kit ../starter-kit; do [ -x $k/.venv/bin/python ] && PY=$k/.venv/bin/python; done

# 1. The verdict on what is uploaded, and the names to compare with.
$PY $K/results.py                 # every finished run: points ± margin, rank, median, minus median
$PY $K/results.py <run id>        # one run, and its ten best teams' names

# 2. The run's history, read by streaming (10 s for 10,000 practice tables, 90 s for a round).
H=hand-history/<downloaded file>.jsonl.gz
$PY -I tools/history/run_stats.py $H                       # our places and heads-up actions
$PY -I tools/history/chipflow.py $H "<team>" "<team>" ...  # bb per 100 hands by preflop situation, us and them
$PY -I tools/history/opens.py $H "<team>" ...              # what happens after a first-in open
$PY -I tools/history/headsup.py $H "<team>" ...            # how often heads-up is reached and won
$PY -I tools/history/field_deep.py $H                      # every team's style at our tables, how we bust
$PY -I tools/history/freq2.py $H "<team>" ...              # their preflop frequencies as Python literals

# 3. The change goes in tools/core_agent.py (a float knob: in SETTINGS, which overrides
#    PROFILES["final"]). Then:
$PY tools/build.py
$PY $K/gate.py bots/final          # GATE: PASS, then again on the build machine
mkdir vN && cp bots/final/agent.py vN/
```

`chipflow.py` has ten team names built in as its default: they are one Pittsburgh run's ten
best. Always pass the names from `results.py`.

### Rollback

Every upload has a copy made at upload time: `mkdir vN && cp bots/final/agent.py vN/`
(upload checklist, step 2). Rollback is switching the active bot back to the previous ready
version on the team page, never a re-upload.

## Promote / rollback rule

**Promote (leave active at a round snapshot)** only when **all** hold:

1. `gate.py bots/final`: **GATE: PASS**, on the build machine too.
2. The change answers a gap measured in a history: a named situation, our number, the ten
   best teams' number.
3. The candidate played a practice run, and its points minus the field median beat the active
   version's latest figure by more than the two margins combined (the root of the sum of
   their squares: about 0.5 when both runs have 10,000 tables).
4. The human gives the go, after the upload checklist.

**When no practice run fits before the snapshot:** rules 1, 2 and 4 still hold, the version
it is built on has a platform result, and the change copies a measured frequency rather than
trying an idea. Say to the human that it is untested on the platform. At Pittsburgh this was
the usual case: only the round 1 bot had played a practice run before its round. One upload went in with no gate and no measured gap behind it (v11, a first
draft of big-blind re-raises): it played round 2 and scored 11.64, the lowest round.

**Otherwise:** keep the current active bot.

If the active bot shows a missed decision or a restart in a run: **switch back immediately**
to the last version that was clean.

## What moved the score at Pittsburgh, in order

| Finding in the histories | Change | Platform result |
| --- | --- | --- |
| Every calling line lost chips; the ten best re-raised 4.2% of hands, we 1.1% | re-raise a single raise with the top 15% / 12% / 6% (big blind, small blind, others) | 12.78 against 12.31 |
| The gap to the leaders was first places (9% against 26%); heads-up we won 38%, they 65% | `_cloned()`: the ten best teams' preflop frequencies by players left, seats behind and stack depth | 14.90, 17.3% firsts |
| Survival margins steered us to 2nd to 4th place | `icm_scale`, `points_tight`, `bubble_margin` to 0, the newest round's tables | 15.37, 20.0% firsts |
| Ranking three cards by their best two overrated pairs by 8 to 12 points of equity | the measured three-card ranking (`pittsburgh_preflop`) | 15.96; against the median +2.26 after +2.10, inside the margins |

What did not: wider opens, big-blind calls, heads-up tweaks one at a time, a port of
`zoo/claude_exploiter_1` (11.02), and more aggression than the leaders' own rates (1.25 to
1.5 times their frequencies lost head to head).

## Do not, mid-round

- Live Monte Carlo, CFR, search, neural live play
- Rewriting `act`, the memory protocol or the legal-action clamping
- Replacing `bots/final` with a zoo or starter bot
- An upload without the gate, however small the change

## Handoff back

If the variant was wrong or the bot is not legal under kit `RULES.md`, return to
`competition-build` for conversion and a fresh safe upload, then resume this loop.
