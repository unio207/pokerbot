# Pittsburgh regional, 2026-11-12: research notes (Claude on Vedaant's Mac)

Variant: `double_board_turn_discard` ("pittsburgh"). Three hole cards, two boards, each
board wins half the pot, one discard after the turn's betting, river with two cards.
Announced 18:13:58 EST. All A/B numbers are **kit** numbers (the real engine, on the Mac,
`gauntlet.py`, nine line-ups, 100 tables x 5 batches per line-up per bot).

## Versions

| Version | Where | sha256 (agent.py) | What |
| --- | --- | --- | --- |
| v0 | `main` before this work | `93764abe…` | unconverted `final`: plays board 1 only, empty discard (lowest card thrown) |
| v1 | branch `pittsburgh-v1` | `25590c64…` | variant entry: 3-card preflop, two-board strength, one-card discard |
| v3a | branch `pittsburgh-v2` | `1e0e7bb9…` | v1 + half-pot veto fix + no draw-only call + Codex calibration |

- v1 vs v0: +3.02 ± 0.90 (seed pgh-ab1), +4.74 ± 1.25 (fresh seed pgh-ab2). Gate PASS on
  the build machine, p99 123 µs.
- v2 (both-board draw flag, also cut semi-bluffs) vs v1: +0.03 ± 0.37, zoo field 1
  −1.70 ± 0.66. Not promoted; split into the v3a changes.
- v3a vs v1: running at commit time.

## Practice run (e74fdd75, weight 0, 2,500 tables)

- Team Allow It 32nd of 82 that played: 15.95 ± 0.68 (median 14.2, best 23.68).
  0 missed decisions in 416,771.
- **We rarely win the table:** 1st 11.4% vs ~33% for the top three; many 2nds and 3rds.
- `field_report.py` on the histories (`hand-history/hands-e74fdd75-….jsonl.gz`, ignored):

| Team (rank) | VPIP | PFR | fold to raise | bets | fold to bet |
| --- | --- | --- | --- | --- | --- |
| Claude Mythos 5.5 (1) | 23% | 19% | 80% | 40% | 53% |
| LLinusLLoveBot (3) | 22% | 21% | 71% | 70% | 72% |
| Parity (4) | 20% | 15% | 82% | 60% | 29% |
| MY STREET (5) | 18% | 13% | 78% | 22% | 28% |
| **Team Allow It (32)** | **16%** | **13%** | **88%** | 35% | 27% |

  We play too few hands and fold to raises far too often. (The report labels 3-card hands
  as hold'em classes; frequencies are fine, hand names approximate.)

## Codex calibration (computed, kit evaluator, db_discard policy, heads-up)

- Preflop: best-pair hold'em equity overrates pairs by 8–11 points (99x: 72.1 vs 60.7).
  Hand-class fit in `_db_preflop_equity`, RMSE 7.96 → 1.04.
- Postflop (3 cards, before discard): flop underrated ~3 points, turn overrated ~2; lookup
  `_DB_FLOP` / `_DB_TURN`. River not calibrated.

## Next experiment: v3b (not in the core; generated from v3a for the A/B)

v3a plus: `threebet` 0.03→0.06, `call_raise` 0.08→0.14, `hu_open` 0.65→0.80,
`points_tight` 0.08→0.03, `bubble_margin` 0.08→0.04, and every `P["open"]` range ×1.25
(capped at 0.6). To be judged on zoo fields and 1st-place share, not the average alone.

## Ops notes

- Failed decisions in Mac gauntlets (1–9 per 900 tables, v0 included) were CPU contention
  (load 7+ with Codex running); 0 on a quiet re-run and 0 missed on the platform.
- `probe.py` cannot write from the kit's sandbox; `rules_card.json` was filled by hand
  (phase_shapes need `phase`, `cards`, `board`, `kinds`).
- Uploaded active file was 73,246 bytes at 18:36; v1 is 73,276. Verify the upload's sha256.
