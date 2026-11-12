---
name: mid-round-iterate
description: >-
  Mid-round No Limit 2026 iteration: mine hand histories, sweep SETTINGS with
  field_fit, promote only on same-seed bench evidence, and ship for rounds 4–6.
  Use between scored rounds after histories exist, or when tuning the active
  bots/final upload without rewriting architecture.
disable-model-invocation: true
---

# Mid-round iterate (No Limit 2026)

Improve the already-uploaded `bots/final` between round snapshots. Scout lightly in
rounds 1–3; spend changes on rounds **4–6** (~**71%** of final score). Never experiment
without a rollback. Architecture rewrites belong in `competition-build`, not here.

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
| ≥5,000 tables/scored round | A ~1 pt/table gain needs ~1,600 same-seed tables to trust |

## Loop checklist (after each history download)

```text
Iterate:
- [ ] Download history from team page
- [ ] field_report --inspect (fix kit_hands once if needed)
- [ ] field_report with --hero
- [ ] field_fit --sweep on bots/final
- [ ] Apply only suggested SETTINGS / PROFILES knobs
- [ ] build.py + fuzz
- [ ] Same-seed bench vs previous (~1600 tables, +1 pt gate)
- [ ] Upload only if gate clears; keep prior zip as rollback
```

### Commands

Use the kit venv on the build box:

```bash
cd ~/work/pokerbot

# 1. Understand the file once
../starter-kit/.venv/bin/python tools/field_report.py --inspect history.jsonl.gz
# If no hands parse: edit kit_hands in tools/field_report.py to match --inspect, re-run.

# 2. Field mix and knob hints
../starter-kit/.venv/bin/python tools/field_report.py history.jsonl.gz --hero <our name>

# 3. Sweep day-of knobs (bots/final exposes SETTINGS from tools/core_agent.py)
../starter-kit/.venv/bin/python tools/field_fit.py history.jsonl.gz --hero <our name> \
  --bot bots/final --sweep

# 4. Apply edits in tools/core_agent.py (SETTINGS and/or PROFILES["final"]), then:
../starter-kit/.venv/bin/python tools/build.py
../starter-kit/.venv/bin/python tools/fuzz.py bots/final --states 5000

# 5. Promote gate — keep previous build as bots/final_prev (copy before overwriting)
../starter-kit/.venv/bin/python tools/bench.py \
  --hero bots/final --hero bots/final_prev \
  --lineup mixed aggressive ai_field \
  --tables 1600 --seed promote --baseline bots/final_prev
```

Without the kit, the same tools run under `python3.12` with `--mini` practice / mini
benches, but prefer kit numbers for go/no-go.

### Saving rollback

Before changing knobs that you might upload:

```bash
cp -a bots/final bots/final_prev
# or keep the last uploaded zip/agent.py copy outside the tree
```

On the team page, leave the previous ready upload selectable so you can switch active
bots without rebuilding.

## Promote / rollback rule

**Promote (upload as active)** only when **all** hold:

1. Fuzz: **zero** failures
2. Same-seed bench vs previous: about **+1 point per table** (or clearly past noise) over
   roughly **1,600** tables on `mixed` / `aggressive` / `ai_field`
3. Change is a **SETTINGS** (or small profile) tweak suggested by report/sweep — not a
   speculative rewrite

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

**Tune (via `SETTINGS` / small profile edits):**

```text
open_size, steal_widen, steal_any, call_margin, bubble_margin,
semi_bluff, cbet_air, hu_open, push_scale, threebet, call_raise,
points_tight, icm_scale
```

Typical report-driven moves: widen steals vs foldy blinds; tighten calls vs shovers if
still over-calling; nudge bubble/cap tightness if many tables hit the cap.

**Do not mid-round:**

- Live Monte Carlo, CFR, search, neural live play
- River-bluff / mixing systems unless sweep **and** bench both clear the promote gate
- Rewriting `act` / memory protocol / legal-action clamping
- Replacing `bots/final` with a zoo or starter bot
- Chasing official scoreboard noise from a single lagged round

## Handoff back

If the variant was wrong or the bot is not legal under kit `RULES.md`, return to
`competition-build` for conversion and a fresh safe upload, then resume this loop.
