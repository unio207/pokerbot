Analysis of the first practice run (`e74fdd75`, weight 0, 2,500 tables), from Claude on Vedaant's Mac. Research only: no code changes, nothing uploaded.

## Result
- **32nd of 82** teams that played: **15.95 ± 0.68** points/table (par 12.5, median 14.2, best 23.68).
- Health: 416,771 decisions, **0 missed**, 0 restarts. Timing is not a problem on the platform.
- Active upload at 18:36 was **73,246 bytes**. The v1 tested on the kit (`pittsburgh-v1`, `bots/final/agent.py`) is **73,276 bytes, sha256 `25590c64…`**. Worth checking which file is live.

## What went wrong: we rarely win the table
| Team (rank) | 1st | 2nd | 3rd | 8th |
|---|---|---|---|---|
| Claude Mythos 5.5 (1) | 34.8% | 12.4% | 12.7% | 5.4% |
| Alice Huang (2) | 33.3% | 12.2% | 12.2% | 7.0% |
| LLinusLLoveBot (3) | 32.5% | 12.0% | 7.4% | 13.2% |
| **Team Allow It (32)** | **11.4%** | **22.3%** | **17.8%** | **5.3%** |

We cash often and rarely bust, but take 1st a third as often as the leaders. With 50/30/20 payouts, that gap is the score gap.

## Why: we are too tight and fold to raises too much
`tools/field_report.py` on the practice histories:

| Team (rank) | VPIP | PFR | fold to raise | postflop bets | fold to bet |
|---|---|---|---|---|---|
| Claude Mythos 5.5 (1) | 23% | 19% | 80% | 40% | 53% |
| LLinusLLoveBot (3) | 22% | 21% | **71%** | 70% | 72% |
| Parity (4) | 20% | 15% | 82% | 60% | 29% |
| MY STREET (5) | 18% | 13% | 78% | 22% | 28% |
| **Team Allow It (32)** | **16%** | **13%** | **88%** | 35% | 27% |

The top teams play 20–23% of hands and fold to a raise 71–82% of the time. We play 16% and fold 88%, so any raise takes our blinds and pots. Short-handed, that bleeds the chips we'd need to win the table. (`field_report.py` labels 3-card hands as hold'em classes, so hand names are approximate; frequencies are fine.)

## What went right
- The two-board conversion is worth a lot. On the kit, v1 beat the unconverted v0 by **+3.02 ± 0.90** and **+4.74 ± 1.25** (two seed sets). The biggest gains came against the strong AI-written zoo fields (+5 to +10).
- Zero missed decisions; the 1 ms limit is not binding.

## Strategy findings (measured)
1. **Preflop pairs are overrated by 8–11 equity points** in this variant (Codex Monte Carlo on the kit evaluator, 30,000 deals per hand, heads-up, both players using `db_discard`). Example: 9-9-x is scored 72.1%, real 60.7%. Hand-class fits are in `docs/research_notes/pittsburgh-2026-11-12.md` on `pittsburgh-v2`.
2. **Postflop with 3 cards:** flop strength is underrated by ~3 points and turn strength overrated by ~2. Lookup tables are in the same notes.
3. **Two leaks in v1's betting logic (Codex review):**
   - The `strength < 0.75` big-call veto folds hands that are near the nuts on one board, which guarantees half the pot. Example: royal on board 1, calling 50 into 150 on the river.
   - The draw-only call fires on a draw on **one** board. That's half a draw here, and Codex's example loses ~21 chips.

## Recommended changes, ranked
1. **Fold to raises less and open wider.** This is the biggest gap to the leaders. Candidates: `call_raise` 0.08→~0.14, `threebet` 0.03→~0.06, open ranges ~×1.25, `hu_open` 0.65→~0.80.
2. **Cut the stacked survival margins** (`points_tight` 0.08 and `bubble_margin` 0.08 on top of ICM). They push us toward 2nd/3rd instead of 1st.
3. Fix the two v1 leaks above.
4. Apply the equity calibration (item 1–2 under findings).

## A/B evidence already measured (kit, 9 line-ups, 900 tables/bot)
- v3a (leak fixes + calibration, branch `pittsburgh-v2`) vs v1: **+0.62 ± 0.27** on the first seed set. The fresh-seed confirmation is running and I'll comment here.
- A version that also restricted semi-bluffs to two-board draws was flat (+0.03 ± 0.37) and lost in zoo field 1 (−1.70 ± 0.66). **Keep semi-bluffing on one-board draws.**
- The aggression settings in recommendation 1 (+ cut margins) are being A/B'd next; results will come as a comment.

Caveat: the A/B line-ups are zoo/example bots, not the real field. The practice histories are the stronger evidence for recommendations 1–2.
