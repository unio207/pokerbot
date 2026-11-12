---
name: competition-build
description: >-
  Build and ship the proven No Limit 2026 competition bot at build-phase start.
  Use when the variant/rules are revealed, the starter kit lands, or the team needs
  a legal upload in the first minutes before mid-round iteration.
disable-model-invocation: true
---

# Competition build (No Limit 2026)

Ship a never-fail, ICM-aware, steal-and-shove-aware bot as fast as possible. Do not invent
a new architecture. Encode the strategy ladder below (the locked `bots/final` profile).
After the first legal upload, hand off to `mid-round-iterate`.

## Authority

Prefer the event **Format** page / kit docs over older notes. Pittsburgh defaults:

| Setting | Value |
| --- | --- |
| Table | 8-max SNG, 2,000 chips, blinds 10/20 |
| Blind increases | Every **20** hands |
| Hand cap | **250** (ICM split of remaining points at cap) |
| Points (default) | **50 / 30 / 20**, 4th–8th = 0 — read `state.config.payouts` |
| Rounds | 6 scored, weights **1×…6×** (~**71%** on rounds 4–6) |
| Iterations | ≥ **5,000** tables per scored round; practice ~1,000 / 10 min (uncounted) |
| Decision limit | **1 ms**; error / timeout / illegal → check if free, else fold |
| Memory | Empty each table; seats anonymized — only in-table stats |
| AI | May write/refine code during build; **must not** make live decisions |
| Upload | `agent.py` or zip with `agent.py` at root; keep under size limit |

Ignore conflicting older figures (blinds every 25, 200-hand cap, 10k tables) unless the
kit `RULES.md` / Format page for *this* event explicitly says otherwise.

## Upload target

**`bots/final/agent.py`** — generated from `tools/core_agent.py` with `ACTIVE = "final"`.

- Not `starter/`, not zoo bots, not one-off experiments.
- Proven on prep benches (mini sim): ~**29.3** pts/table vs starter ~**19.5**; weak field
  ~**31**; fuzz 8k states / **0** failures. Stop chasing more mini-EV; process and variant
  conversion are the remaining edge.

If pre-written repo code is allowed: copy the repo, build, upload `bots/final` first, then
convert. If not: rebuild the same ladder from the kit template using the strategy spec
below (same behavior, no dead weight).

## Minute 0–10 checklist

Copy and track:

```text
Build progress:
- [ ] Kit installed (re-run no-limit-2026-setup if needed)
- [ ] Repo on build box next to kit (`~/work/pokerbot` beside `~/work/starter-kit`)
- [ ] build.py --check + fuzz bots/final
- [ ] FIRST UPLOAD of bots/final (unchanged is fine — legal in unknown phases)
- [ ] Read kit RULES.md; write zoo/variants/<name>.md from TEMPLATE.md
- [ ] Variant conversion + table regen
- [ ] Rebuild, fuzz, practice smoke
- [ ] Second upload of converted bot; keep first as rollback
- [ ] Hand off to mid-round-iterate
```

### Commands (on the build machine, Python 3.12 / kit venv)

```bash
cd ~/work/pokerbot
../starter-kit/.venv/bin/python tools/build.py --check
../starter-kit/.venv/bin/python tools/fuzz.py bots/final --states 5000
# upload bots/final NOW

# after RULES.md is read and VARIANTS entry added:
../starter-kit/.venv/bin/python tools/gen_variant_tables.py tools/core_agent.py --samples 400000
../starter-kit/.venv/bin/python tools/build.py
../starter-kit/.venv/bin/python tools/fuzz.py bots/final --states 20000
../starter-kit/.venv/bin/python practice.py bots/final --tables 50
```

SSH with practice ports if using the UI:

```bash
ssh -L 8765:127.0.0.1:8765 -L 8766:127.0.0.1:8766 no-limit-2026-build
```

## Strategy spec (`final` = A + F + C)

Implement in this order. Each rung is a shippable bot; climb only when the previous is
stable under fuzz.

1. **Never-fail skeleton** — try/except → check-else-fold; clamp every raise to
   `[min_amount, max_amount]` with whole numbers; no state on `self`/globals; use
   `memory` bytes only (≤64 KB, parse defensively).
2. **Tight-aggressive preflop chart** — precomputed equity / percentile table; open wider
   late, tighter early; fold the rest.
3. **Pot-odds postflop** — call when win chance > price; bet/raise strong made hands and
   selected draws. Use cheap categories or precomputed buckets — **not** live Monte Carlo.
4. **Push/fold when short** — under ~10–15 BB (profile may start shove logic ~20 BB for
   push_fold rung), shove or fold; widen as stack shrinks and players remain. Blinds rise
   every 20 hands — most of the table is short.
5. **Payout-aware endgame** — ICM-priced calls; tighten near bubble and hand cap
   (`cap_aware`); play for **first** (50/30/20); aggressive 3-handed and heads-up.
6. **Light in-table stats** — track seats that never raise/call; steal any two vs dead
   blinds; `vs_shover="doc"` (conservative vs constant shovers); adapt to stations and
   min-raisers. Reset with the table.

Locked `final` knobs (edit via `PROFILES["final"]` / top-level `SETTINGS` in
`tools/core_agent.py`, then `tools/build.py`):

```text
track + adapt {steal, shover, station, minraise}
steal_widen=1.15  steal_any=0.85  vs_shover=doc  cbet_air=0.3
icm_scale=1.0  cap_aware  open_size=2.3  semi_bluff=0.3
call_margin=0.05  bubble_margin=0.08  push_scale=0.9  points_tight=0.08
threebet=0.03  call_raise=0.08  hu_open≈0.65
```

## Variant portability

- Isolate card strength in one place (`VARIANTS` entry: `detect`, `phases`, `preflop`,
  `postflop`). Betting strategy consumes 0–1 scores only.
- Unknown phase → kit `automatic(state)` so an unconverted bot stays legal.
- Pattern: copy an existing entry (`irish`, `discard_reveal`, `short_deck`) in
  `tools/core_agent.py`; regen tables; compare converted vs unconverted on the **same seed**
  before promoting.
- Do not hard-code hold'em-only assumptions into `decide()`.

## Hard bans (1 ms Python)

- Live Monte Carlo / rollouts at decision time
- CFR, search, neural nets as the live player
- LLM / network / files / subprocesses inside `act`
- Float raise amounts; out-of-range raises (illegal → check/fold)
- Chasing river bluffs or mixing before a never-fail converted bot is uploaded

Allowed imports: stdlib, `poker_agent_sdk`, and the kit's listed scientific stack only.
Never `poker_engine` / `pokerkit`.

## Validation gates before any upload

1. Kit or `poker-agent check` / `tools/build.py --check` passes.
2. `tools/fuzz.py bots/final` — **zero** exceptions and illegal actions.
3. Short practice match — **zero** failed decisions; p99 decision time well under 1 ms.
4. Prefer the kit engine over the mini simulator for final go/no-go.

## Handoff

Once a legal (preferably variant-converted) `bots/final` is the active upload, stop
rewriting strategy from scratch. Use **`mid-round-iterate`** for hand-history scouting,
`SETTINGS` sweeps, promote/rollback, and spending weight on rounds 4–6.
