---
name: mid-round-iterate
description: >-
  Mid-round No Limit 2026 iteration: mine hand histories, sweep SETTINGS with
  field_fit, promote only on same-seed gauntlet evidence and a passing gate, and
  ship for rounds 4–6.
  Use between scored rounds after histories exist, or when tuning the active
  bots/final upload without rewriting architecture.
disable-model-invocation: true
---

# Mid-round iterate (No Limit 2026)

Improve the already-uploaded `bots/final` between round snapshots. This is where most of the
score is won. Never experiment without a rollback. Architecture rewrites belong in
`competition-build`, not here.

Rounds weigh fibonacci (`round_weighting` in `portal.py`; 1, 2, 3, 5, 8, 13 by Henry's reading,
total 32: round 6 is 13 times round 1 and 41% of the score). Two consequences:

- **Gains: ship early.** A change active from round k counts in every round after it: 31/32
  of the weight from round 2, 29 from 3, 26 from 4, 21 from 5, 13 from 6. The same +0.5
  points per table is worth 2.4 times as much shipped for round 2 as for round 6. Every
  window that ends without a promoted change is lost score: do not hold changes back to scout.
- **Risk: lock down late.** A broken bot costs 13/32 in round 6 and 8/32 in round 5. Those two
  windows take only changes that clear the stricter bar under "Round posture".

Start from `skills/STATE.md`, written by `sequoia-launch`: the active version `vN`, the
baseline, tables per minute, the upload-to-ready time. Append one line there per upload and
per practice run. Measuring and uploading use the launch skill's scripts and its checklist
(`skills/sequoia-launch/references/measure-and-upload.md`): one gate, one promotion rule.
`python3.12 skills/sequoia-launch/scripts/portal.py` reads round results, each round's weight,
upload states and health from the portal, so check it before and after every upload.

## When to use

- After a scored or practice round when the team page offers hand histories
- Between round starts (snapshots freeze the **active** bot at round start)
- When practice-run feedback or local benches suggest a knob change

Do **not** wait for the previous round's official score: results often lag into the next
20-minute window. Decide from practice runs, kit sim, and histories.

## Constraints that shape iteration

| Fact | Implication |
| --- | --- |
| Snapshots at T+60, 80, …, 160; weights fibonacci | A gain is worth more the earlier it lands; a failure costs more the later it lands |
| Snapshot at round start | Upload before the next start or it misses that round |
| No active bot → zero for the round | Always keep a ready, previously good upload selectable |
| 1 ms / never-fail | Prefer knob tweaks over new logic; fuzz after every edit |
| Seats anonymized; memory per table | Field reads are population habits, not named opponents across tables |
| ≥5,000 tables/scored round | Small gains count there; `gauntlet.py` prints the smallest difference its A/B can detect (about `2.8 x 21 / sqrt(tables per bot)`) |

## Every window (20 minutes; S is the snapshot that just happened)

One change per window, measured, uploaded by S+15. Run `$PY $K/clock.py` at each step.

| Time | Step |
| --- | --- |
| S+0 to 2 | `portal.py`: the round that just started is the active version's first real health. Missed decisions or restarts above 0: switch back first, then fix. New hand histories listed: ask the human to download about 5,000 hands (see step 1 of the commands). |
| S+2 to 7 | Pick one change. With a history: the report and the sweep below. Before any history exists (round results lag): the sweep with `--field` set to the zoo bots of the line-up the field most resembles, so the first windows after the build are not idle. |
| S+7 to 13 | `gauntlet.py bots/final --vs vN`, then the fresh seed, in the background. One measuring job at a time. |
| S+13 to 15 | `gate.py bots/final` on the Mac, then on the build machine. |
| by S+15 | The human's go and the upload; `portal.py` shows it ready and active. After S+15 no upload unless the active bot is failing. |

If the A/B cannot finish by S+13 at the size it needs (the kit is slower than the mini
simulator), the change waits one window rather than shipping unmeasured: one window later it
still earns most of its value (26 of 29 from round 4 instead of 3).

## Loop checklist (after each history download)

```text
Iterate:
- [ ] Download history from team page
- [ ] field_report --inspect (fix kit_hands once if needed)
- [ ] field_report with --hero
- [ ] field_fit --sweep on bots/final, with --variant (the sweep plays the mini simulator)
- [ ] Apply only suggested SETTINGS knobs
- [ ] build.py
- [ ] gauntlet.py bots/final --vs vN (the active version), then again on a fresh seed
- [ ] gate.py bots/final prints GATE: PASS
- [ ] Upload checklist (human go, clock, cutoff); the previous vN stays as rollback
```

### Commands

From the repo root, on the machine Claude Code runs on (the Mac, with the kit beside the
repo). The build machine is for the gate's timing.

```bash
K=skills/sequoia-launch/scripts
PY=python3.12; for k in starter-kit ../starter-kit; do [ -x $k/.venv/bin/python ] && PY=$k/.venv/bin/python; done
# The ruleset the mini simulator plays for the announced variant (set in stage 3 of the launch):
V=$($PY -c "import json;print(json.load(open('rules_card.json'))['variant'].get('mini_name') or 'holdem')")

# 1. Understand the file once. The kit's hand-history/ folder has a sample in this same format
#    (and a streaming reader): if the launch did not already fix kit_hands on it, do that first.
#    <our name> is the team name, "Team Allow It". The download lets you choose how many
#    hands: ask for about 5,000. Seats are anonymous, so the report measures population
#    rates; a 30% rate over 5,000 chances has a standard error of sqrt(0.3 x 0.7 / 5,000),
#    under 1 point. More only if the report counts fewer than about 200 chances for a stat
#    you need (that stat's error is then above 3 points); more hands cost download and
#    parse time inside the window.
$PY tools/field_report.py --inspect history.jsonl.gz
# If no hands parse: edit kit_hands in tools/field_report.py to match --inspect, re-run.

# 2. Field mix and knob hints
$PY tools/field_report.py history.jsonl.gz --hero <our name>

# 3. Sweep the day-of knobs: the SETTINGS table of tools/core_agent.py, stamped into bots/final.
#    The sweep always plays the mini simulator, so it has to be told the variant.
$PY tools/field_fit.py history.jsonl.gz --hero <our name> --bot bots/final --sweep --variant $V

# 4. Change the knob in SETTINGS in tools/core_agent.py, then rebuild.
#    SETTINGS overrides PROFILES["final"]: editing only the profile changes nothing.
$PY tools/build.py

# 5. Promote gate: against vN/, the copy of the active upload, on the same seeds.
$PY $K/gauntlet.py bots/final --vs vN                               # the kit's engine when it is installed
$PY $K/gauntlet.py bots/final --vs vN --seed fresh1 --tables 400    # must still be positive
$PY $K/gate.py bots/final                                           # GATE: PASS, then again on the build machine
```

`gauntlet.py` and `gate.py` play the kit when it is installed and the announced variant
either way. `field_fit.py` plays the mini simulator only. `tools/bench.py` is mini
simulator and **hold'em only** (no `--variant`): use it as a finer paired comparison only
when the announced variant is hold'em, never as the go/no-go.

### Rollback

Every upload has a copy made at upload time: `mkdir vN && cp bots/final/agent.py vN/`
(upload checklist, step 2). The active version's `vN/` is what `--vs` compares against.
Rollback is switching the active bot back to the previous ready version on the team page,
never a re-upload.

## Promote / rollback rule

**Promote (upload as active)** only when **all** hold:

1. `gate.py bots/final`: **GATE: PASS** (it includes the fuzz, timing and memory checks)
2. `gauntlet.py bots/final --vs vN`: the difference over all line-ups is above **2 standard
   errors**, still positive on a fresh seed, with zero failed decisions
3. Change is a **SETTINGS** tweak suggested by report/sweep, not a speculative rewrite
4. The human gives the go, after the upload checklist in
   `skills/sequoia-launch/references/measure-and-upload.md` (clock and cutoff, what changed,
   confirm ready and active, one line in `skills/STATE.md`)

**Otherwise:** keep the current active bot; stash the experiment; do not burn an upload
slot on noise.

If a promoted bot looks broken in the next practice run or fails fuzz after a hot fix:
**roll back immediately** to the last known-good upload.

## Round posture

### Windows before rounds 2 to 4 (the value)

- Ship every change that passes the promotion rule, one per window. This is where a gain
  counts the most rounds.
- Fix parser / `kit_hands` once, if the launch did not.
- Learn the field: dead seats, shove rate, stations, raise frequency.
- `SETTINGS` moves first (steal widen, vs-shover margins, open size); do not overfit to one
  history file.

### Windows before rounds 5 and 6 (the risk)

- The promotion rule plus: positive on **two** fresh seeds, the gate passed on the build
  machine, and the active version shows 0 missed decisions and 0 restarts in the round in
  progress.
- `SETTINGS` changes only; no new logic.
- In doubt, keep the bot that is clean in the current round: a never-fail good bot beats a
  clever flaky one (errors are check/fold).

## What to tune vs what not to touch

**Tune (all thirteen are in `SETTINGS`):**

```text
open_size, steal_widen, steal_any, call_margin, bubble_margin,
semi_bluff, cbet_air, hu_open, push_scale, threebet, call_raise,
points_tight, icm_scale
```

Typical report-driven moves: widen steals vs foldy blinds; tighten calls vs shovers if
still over-calling; nudge bubble/cap tightness if many tables hit the cap.

**Do not mid-round:**

- Live Monte Carlo, CFR, search, neural live play
- River-bluff / mixing systems unless sweep **and** gauntlet both clear the promote gate
- Rewriting `act` / memory protocol / legal-action clamping
- Replacing `bots/final` with a zoo or starter bot
- Chasing official scoreboard noise from a single lagged round

## Handoff back

If the variant was wrong or the bot is not legal under kit `RULES.md`, return to
`competition-build` for conversion and a fresh safe upload, then resume this loop.
