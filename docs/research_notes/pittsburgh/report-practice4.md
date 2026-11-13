# Practice 4 (v4): 53rd/107, 13.00 pts. Heads-up button fixed; big blind and steals still far too tight

Posted as https://github.com/unio207/pokerbot/issues/15

Research only, no code changed. Practice 4 (`c6824739`, 10,000 tables) was played by upload v4 `d55b4134` (73,673 B, sha256 `11f2e107…`, = `uploads/v4_d55b4134/agent.py` on `origin/uploads`, = `bots/final` at `9daa6a9`).

## Result: 53rd of 107, 13.00 ± 0.17 points (par 12.5)

| | Practice 3 (v3) | **Practice 4 (v4)** | Top 5 now |
|---|---|---|---|
| Points/table | 12.43 | **13.00 ± 0.17** | 19.5 – 21.9 |
| 1st | 7.0% | **9.8%** | 26 – 28% |
| 8th | 8.5% | **5.1%** | 2 – 10% |
| Reach heads-up | 25.7% | 24.8% | 40.7% |
| Win heads-up when there | 26.7% | **38.8%** | 65.2% |

Top 5 = Pluto, Amateur Pros, Cold Decks, Claude Mythos 5.5, MY STREET (their tables against us, ~650 each). Codex computed the standings separately and got the same rank, points and place counts.

## 1. The heads-up fix worked, but only for the button
Our heads-up button fold fell from 74% to 22% (≤10bb), 36% (10–25bb), 27% (>25bb). The big blind is still far too tight:

| Heads-up, we are big blind | Us fold | Top 5 fold |
|---|---|---|
| vs raise, ≤10bb | 60% (n=2,830) | 36% |
| vs raise, 10–25bb | 72% (n=5,205) | 37% |
| vs raise, >25bb | 84% (n=1,120) | 46% |
| vs shove, ≤10bb | 79% (n=7,596) | 48% |
| vs shove, 10–25bb | 89% (n=2,191) | 77% |

By our own cards (3 hole cards): vs a shove at ≤10bb we fold 70% of ace-high, 74% of king-high and 64% of hands holding a pair. vs a raise at >25bb we fold 95% of king-high and 100% of queen-high or lower. On the button at 10–25bb we still fold 85% of jack-high-or-lower hands; the top 5 fold 15% of everything.

We also arrive heads-up with 40% of the chips on average (top 5: 55%), and are the short stack in 66% of our heads-up matches.

## 2. Where the 7.4 points to the top 5 go (tournament equity per table)

| Stage | Us | Top 5 | Gap |
|---|---|---|---|
| 5–8 players | +0.91 | +4.84 | 3.9 |
| 3–4 players | −0.33 | +2.20 | 2.5 |
| Heads-up | −0.07 | +0.82 | 0.9 |

**The big blind is about half of it.** Our big blind costs −3.49 (5–8 players) and −3.05 (3–4 players) per table; the top 5 lose −1.72 and −1.19. That is 3.6 of the 7.4 points.

- Facing a raise (any seat) we fold 86–90% with 5–8 players, 82–87% with 3–4. Top 5: 75–80% and 65–71%.
- By cards, >20bb: we fold 54% of hands holding a pair, 88% of ace-high, 98% of king-high. At ≤10bb we still fold 62% of pairs and 80% of ace-high.
- Re-raise over 20bb deep: us 2.8%, top 5 10.2%.

**Steals are the other large piece.** Pots won preflop without all-in: us 5.6% of hands for +0.84/table (5–8 players); top 5 11.5% for +2.06. With 3–4 players: +0.19 vs +0.91.

| First in, raise or shove | Us | Top 5 |
|---|---|---|
| Button, 5–8 players | 36–43% | 62–66% |
| Small blind, 5–8 players | 57–61% | 85–89% |
| Button, 3–4 players | 36–49% | 49–74% |
| Small blind, 3–4 players | 58–66% | 80–89% |

**Postflop calling loses more than theirs.** Hands where we called a bet after the flop without ever betting: −2.80/table (−168 per 100 such hands) vs −1.36 (−101) for the top 5, 5–8 players. Hands where we bet or raised are fine (+2.96).

## 3. v4 took v3's looser preflop back out
The diff v3 → v4 is the big-blind fix plus `threebet` 0.06 → 0.03, `call_raise` 0.14 → 0.08, `hu_open` 0.80 → 0.65, `open_scale` 1.25 removed, `bubble_margin`/`points_tight` 0.04/0.03 → 0.08/0.08. So practice 4 measured the fix on v1's tight settings. The measurements above say tight is the wrong direction.

## Recommended changes, in order
1. **Defend the big blind**, heads-up and at every table size. Targets from the top 5: fold to a raise ≤ 45% heads-up and ≤ 75% otherwise; call a heads-up shove ≤10bb with any ace, any king, any pair (they call 52%). Never fold a pair to a single raise.
2. **Open the button and small blind much wider when first in**: button ≥ 60%, small blind ≥ 85%, heads-up button ≥ 85% (≥ 90% above 25bb). These are plain range-limit changes (`open` table, `hu_open`).
3. **Restore and extend v3's `threebet` / `call_raise`** on top of the fix; v4's 0.03 / 0.08 are below v3's and far below what the top 5 do (10% re-raise deep, 9–12% reshove short).
4. **Tighten postflop calls** when we have not bet: raise the two-board equity needed to call, especially on the turn before the discard.
5. Check the `bubble_margin` / `points_tight` 0.08 values: we finish 2nd–4th 50% of the time and 1st 9.8%, which looks like survival over winning.

## Caveats
- One run; observational. Per-seat numbers have n in the tens of thousands for us, hundreds to thousands for the top 5.
- "Top 5 at our tables" is their play against a field that includes us, not their whole run.
- Card classes are coarse (pair / highest card), not equity.
- A fuller Codex breakdown (c-bets, fold-to-bet by street, bust modes) was still running when this was posted and will follow as a comment if it adds anything.


---

## Follow-up comment

Codex's separate pass over the same file (its own scripts, chip ledger reconciled on all 1,571,390 hands) agrees with the report above: same standings, big blind −7.0 vs −2.9 points/table, same open / fold-to-raise / re-raise gaps. It adds two things:

**1. We get blinded out.** 800 of our 9,021 busts (8.9%) are a forced all-in from posting a blind; the top 5 have 43 of 2,409 (1.8%). We are waiting too long to shove when short. Related: only 10% of our busts are as a preflop caller, against 23% for the top 5.

**2. We call the flop and turn, then fold the river.**

| Fold to a bet | Us | Top 5 |
|---|---|---|
| Flop | 26.6% (n=31,168) | 41.3% |
| Turn | 23.6% (n=23,628) | 32.5% |
| River | 34.7% (n=20,173) | 35.4% |

Hands where we fold on the river cost −2.51 points/table against −1.14 for the top 5; turn folds −1.51 against −1.14. So change 4 above is specifically: fold more on the flop and turn (before paying to reach the discard), not on the river. Flop c-bet is also low: 49% against 57%.

Caveat: Codex excluded 2 unfinished tables, which puts us 54th instead of 53rd; nothing else moves.
