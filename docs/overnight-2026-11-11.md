# Overnight prep results (2026-11-11)

Work landed on branch `overnight/prep-2026-11-11`. Local machine has Python 3.14; numbers
are mini-simulator only. Kit and build-box SSH were **not** available (need team API key
+ `/no-limit-2026-setup`).

## Done

1. Synced disk to `origin/main`.
2. Added 12 AI-default zoo opponents (`zoo/gpt_*`, `zoo/codex_default_1`); all `OK` on
   `check_zoo` (0 failures).
3. Added bench lineup `ai_field` in `tools/bench.py`.
4. Wrote [`docs/day-of-runbook.md`](day-of-runbook.md).
5. Wired `SETTINGS` into `tools/core_agent.py` for `bots/final` so
   `tools/field_fit.py --sweep` can move day-of knobs.
6. Fuzz: `bots/final` — 8000 states, **no failures**, p99.9 ≈ 509 µs, max 670 µs.

## Bench (1600 tables/line-up, seed `overnight1600`, rules=kit)

| lineup | final pts | starter pts | Δ | sig |
|--------|-----------|-------------|---|-----|
| mixed | 27.48 ± 0.49 | 17.18 ± 0.52 | +10.29 | YES |
| aggressive | 29.41 ± 0.35 | 14.26 ± 0.46 | +15.14 | YES |
| ai_field | 31.05 ± 0.53 | 27.04 ± 0.56 | +4.01 | YES |
| **overall** | **29.31 ± 0.27** | **19.50 ± 0.30** | **+9.82** | YES |

No failed decisions. Conclusion: do **not** chase more EV on mini tonight; `final` already
crushes shove-heavy and prints on the AI-shaped field. Edge left is process (build box,
variant conversion, field_fit on real histories).

## Setup completed later the same night

- API key validated for **Team Allow It** (Pittsburgh).
- SSH alias `no-limit-2026-build` → `ubuntu@18.205.162.141` (key
  `~/.ssh/no-limit-2026`). Login probe: `ubuntu`, `pittsburgh-team-116`,
  `cloud-init status: done`, `~/work` ready.
- Repo synced to `~/work/pokerbot` on the box (Python **3.12.3** there).
- Starter kit download: **404** (variant not announced yet). Re-run setup skill after
  announcement.

## Lesser follow-ups also landed

- Hide `zoo/_template` from UI discovery / bot list.
- Harden `mini_sim.load_agent` so the SDK shim is always on `sys.path` for fresh loads.
- `discard_reveal` smoke: final 30.4 vs starter 20.8 / 300 tables / 0 fails.

## Still blocked / next human steps

1. On kit day: re-run setup skill to unpack kit; upload `bots/final` first; convert
   variant; scout rounds 1–3 with `field_report` / `field_fit --sweep`; ship best
   version for rounds 4–6.
2. Merge this branch to `main` after review.
3. Optional: connect Codex/Claude desktop app to `no-limit-2026-build` (skill step 4).
