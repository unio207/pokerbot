# Pittsburgh regional, 2026-11-12: research notes

Latest addition: [tournament 242e19e4 review](report-242e19e4.md), covering all
10,000 tables, improved early-table results, zero automatic fallbacks, and the
remaining heads-up weakness. [Results and reproduction instructions](results/242e19e4/README.md)
include cached aggregates and a streaming audit measured at 16 seconds.

Analysis and research from Claude on Vedaant's Mac. **Research only:** this branch holds
notes, no bot code. Development and uploads are Henry's. Reports are also posted as issues:
[#12](https://github.com/unio207/pokerbot/issues/12) (practice 1),
[#13](https://github.com/unio207/pokerbot/issues/13) (heads-up bug, practice 2).

Every A/B number is a **kit** number (real engine, run on the Mac, `gauntlet.py`, nine
line-ups, 100 tables × 5 batches per line-up per bot) unless labelled otherwise.

## Most important finding: the heads-up big-blind bug (#13)

`_big_blind_seat()` in `tools/core_agent.py` takes the **last** `blind` event as the big
blind. On the platform the small blind posts last in **98% of heads-up hands** (37,779 of
38,382 in practice 2). Heads-up the bot misreads its position on every hand:

- On the button it thinks it is the big blind: `hu_open` never applies. We fold **75%** of
  buttons (opponents 33%), **89%** at 15–30bb.
- In the big blind it defends too little: we fold **84%** to a button raise (opponents 64%).
- We reach heads-up at 30.6% of tables and win 25% of those (48.8% as chip leader, 10.3%
  from behind).

Suggested fix (not applied): find the big blind by amount (`event.amount ==
state.blinds.big_blind`, falling back to the largest blind). Estimated worth: about
+1 point/table or more. Details and checks in `report-practice2-headsup-bug.md`.

## Variant

`double_board_turn_discard` ("pittsburgh"), announced 18:13:58 EST. Three hole cards, two
boards, each board wins half the pot, one discard after the turn's betting
(`Action("discard", cards=(i,))`; empty or failed = lowest card discarded, not a failed
decision), river with two cards. `state.variant["boards"]` holds both boards;
`state.config.variant` is `double_board_turn_discard`. Kit defaults: 8 players, 2,000
chips, blinds every 20 hands, 250-hand cap, 50/30/20, 1 ms + 100 ms bank, 64 KiB memory.
Round weighting is **fibonacci**: rounds 5 and 6 carry about two-thirds of the score.

## Uploads and the code behind them

| Upload | Size | Time (EST) | Code | Ran |
| --- | --- | --- | --- | --- |
| `7e4d8e8e` | 70,036 | 18:20 | v0 = `main` `96575d3` (unconverted `final`) | nothing scored |
| `920a2429` | 73,246 | 18:30 | **unknown: no matching commit** | practice 1 |
| `066139f9` | 75,994 | 18:43 | v3a = `pittsburgh-v2` `bc36edb`, sha256 `1e0e7bb9…` | practice 2 |
| `393c48a3` | 73,364 | 18:52 | **unknown: no matching commit** (active at 18:58) | round 1? |

The API's submission-file endpoint returns 403 to our key, so uploads can only be matched
through GitHub. Please push every upload.

## Practice runs

| | Practice 1 (`e74fdd75`) | Practice 2 (`13b7f112`) |
| --- | --- | --- |
| Tables | 2,500 | 5,000 |
| Teams played | 82 | 100 |
| Our rank | 32nd | 43rd |
| Our points | 15.95 ± 0.68 | 14.47 ± 0.45 |
| Median / best | 14.22 / 23.68 | 13.69 / 23.34 |
| Our 1st / 2nd / 3rd / 8th | 11.4 / 22.3 / 17.8 / 5.3% | 7.5 / 23.3 / 18.6 / 3.5% |
| Leaders' 1st | ~33% | ~30% |
| Missed decisions | 0 of 416,771 | 0 of 803,861 |

No table reached the hand cap; every table paid 50/30/20 (practice 2).

### Field profile (`tools/field_report.py`, practice 2)

| Team | VPIP | PFR | fold to raise | postflop bets | fold to bet |
| --- | --- | --- | --- | --- | --- |
| Pluto (1) | 24% | 22% | 79% | 46% | 44% |
| Claude Mythos 5.5 (2) | 23% | 19% | 79% | 39% | 50% |
| Cold Decks (3) | 19% | 15% | 79% | 46% | 29% |
| Gambling 1010 (4) | 23% | 18% | 79% | 40% | 41% |
| Amateur Pros (5) | 25% | 18% | 68% | 27% | 32% |
| MY STREET (6) | 32% | 23% | 67% | 26% | 46% |
| Parity (7) | 20% | 15% | 81% | 59% | 33% |
| LLinusLLoveBot (8) | 21% | 20% | 71% | 69% | 70% |
| **Team Allow It (43)** | **15%** | **12%** | **89%** | 37% | 26% |

Practice 1 showed the same pattern (us 16% / 13% / 88%). Part of our 89% is the heads-up
bug; the rest is general tightness. `field_report.py` labels 3-card hands as hold'em
classes, so its hand names are approximate; frequencies are fine. Full reports:
`field-report-practice1.txt`, `field-report-practice2.txt`.

## Kit A/B results

| Comparison | Seed | All line-ups | Notes |
| --- | --- | --- | --- |
| v1 − v0 | pgh-ab1 | **+3.02 ± 0.90** | zoo fields +5 to +6 |
| v1 − v0 | pgh-ab2 (fresh) | **+4.74 ± 1.25** | confirmed |
| v2 − v1 | pgh-v2a | +0.03 ± 0.37 | two-board-only draws cut semi-bluffs; zoo 1 −1.70 ± 0.66 |
| v3a − v1 | pgh-v3a | +0.62 ± 0.27 | |
| v3a − v1 | pgh-v3a-2 (fresh) | +0.34 ± 0.31 | **not confirmed** |
| v3b − v3a | pgh-v3b | −1.03 ± 0.63 | not detectable; leaned worse on zoo |

Versions: v1 = variant entry (3-card preflop, two-board strength, one-card discard;
`pittsburgh-v1` `a2d477d`). v3a = v1 + half-pot veto fix + no draw-only call + Codex
calibration (`pittsburgh-v2` `bc36edb`). v3b = v3a with `threebet` 0.06, `call_raise` 0.14,
`hu_open` 0.80, `points_tight` 0.03, `bubble_margin` 0.04, open ranges ×1.25 (experiment
file only). **Every version carries the heads-up bug**, so `hu_open` changes could not show
an effect. The zoo line-ups are not the real field; the practice histories are the better
evidence for style changes. Raw outputs: `gauntlet_*.txt`.

Failed decisions in Mac gauntlets (1–12 per 900 tables, v0 included) were CPU contention
(load 7+); 0 on a quiet re-run and 0 missed on the platform.

## Strategy research (Codex, computed on the kit evaluator)

- `codex-equity-calibration.md`: best-pair hold'em equity overrates 3-card pairs by 8–11
  points preflop (99x: 72.1 scored vs 60.7 real); flop strength underrated ~3 points, turn
  overrated ~2. Hand-class fits and lookup tables included.
- `codex-v1-diff-review.md`: two leaks in v1. The `strength < 0.75` big-call veto folds
  hands that guarantee half the pot; the draw-only call fires on one-board draws.
- `codex-variant-brief.md`: what the unconverted bot did in this variant, conversion plan,
  risks.
- `codex-pre-announcement-review.md`: review of the 13 SETTINGS knobs and the six
  pre-built variants (Omaha preflop error, ICM top-3 only, stacked survival margins).

## Recommendations for development, ranked

1. **Fix the heads-up big-blind misread** (#13). Biggest measured leak.
2. **Re-measure heads-up and short-handed aggression after the fix** (`hu_open`,
   `push_scale`), judged on the share of 1st places.
3. **Fold to raises less and open wider**: the top 8 play 19–32% of hands and fold to raises
   67–81%; we play 15% and fold 89%.
4. **Cut the stacked survival margins** (`points_tight`, `bubble_margin` on top of ICM).
5. Keep semi-bluffing one-board draws; drop the draw-only call (half a draw here).
6. Calibration (Codex tables) showed no confirmed gain on its own; low priority.

## Process notes

- `probe.py` cannot write from the kit's sandbox; `rules_card.json` was filled by hand
  (`phase_shapes` need `phase`, `cards`, `board`, `kinds`).
- `poker-agent play` shuffles seats between tables: never assume seat 0 is the hero when
  reading a local history.
- Practice histories: the team page's download command (`/teams/<team>/tournaments/<id>/hands`)
  with the API key. Practice 1's file uses a different record layout than practice 2's.
