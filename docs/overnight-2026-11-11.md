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

## Still blocked / next human steps

1. Run `/no-limit-2026-setup` until `ssh no-limit-2026-build` works.
2. On kit day: upload `bots/final` first, convert variant, scout rounds 1–3 with
   `field_report` / `field_fit --sweep`, ship best version for rounds 4–6.
3. Optionally merge this branch to `main` after review.
