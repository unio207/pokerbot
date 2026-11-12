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

Improve the already-uploaded `bots/final` between round snapshots. Scout lightly in
rounds 1–3; spend changes on rounds **4–6** (~**71%** of final score). Never experiment
without a rollback. Architecture rewrites belong in `competition-build`, not here.

Start from `skills/STATE.md`, written by `sequoia-launch`: the active version `vN`, the
baseline, tables per minute, the upload-to-ready time. Append one line there per upload and
per practice run. Measuring and uploading use the launch skill's scripts and its checklist
(`skills/sequoia-launch/references/measure-and-upload.md`): one gate, one promotion rule.

## When to use

- After a scored or practice round when the team page offers hand histories
- Between round starts (snapshots freeze the **active** bot at round start)
- When practice-run feedback or local benches suggest a knob change

Do **not** wait for the previous round's official score: results often lag into the next
20-minute window. Decide from practice runs, kit sim, and histories.

## Constraints that shape iteration

| Fact | Implication |
| --- | --- |
| Round starts every +20 min; weights 1×…6× | Early rounds are scouting; late rounds are the prize |
| Snapshot at round start | Upload before the next start or it misses that round |
| No active bot → zero for the round | Always keep a ready, previously good upload selectable |
| 1 ms / never-fail | Prefer knob tweaks over new logic; fuzz after every edit |
| Seats anonymized; memory per table | Field reads are population habits, not named opponents across tables |
| ≥5,000 tables/scored round | Small gains count there; `gauntlet.py` prints the smallest difference its A/B can detect (about `2.8 x 21 / sqrt(tables per bot)`) |

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
PY=python3.12; [ -x ../starter-kit/.venv/bin/python ] && PY=../starter-kit/.venv/bin/python
# The ruleset the mini simulator plays for the announced variant (set in stage 3 of the launch):
V=$($PY -c "import json;print(json.load(open('rules_card.json'))['variant'].get('mini_name') or 'holdem')")

# 1. Understand the file once
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

### Rounds 1–3 (scout)

- Fix parser / `kit_hands` once.
- Learn the field: dead seats, shove rate, stations, raise frequency.
- At most light `SETTINGS` moves (steal widen, vs-shover-related margins, open size).
- Do not overfit to one history file.

### Rounds 4–6 (ship)

- Upload the best promoted `bots/final` before each heavily weighted snapshot.
- No live architecture experiments without rollback already staged.
- Prefer stability: a never-fail good bot beats a clever flaky one (errors are check/fold).

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
