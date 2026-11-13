# Round 1 (scored, v4): 62nd/109, 12.52 pts. Same leaks as practice 4: blinds cost 5.7 of the 7.3-point gap

Posted as https://github.com/unio207/pokerbot/issues/16

Research only. Scored round 1 (`74913ac4`, weight 1, first 10,000 of 20,000 tables) was played by upload v4 `d55b4134` — the same build as practice 4 — so this is a second, independent measurement of v4.

## Result: 62nd of 109, 12.52 ± 0.17 points (par 12.5)

| | Practice 4 (v4) | **Round 1 (v4)** | Top 5, round 1 |
|---|---|---|---|
| Points/table | 13.00 ± 0.17 | **12.52 ± 0.17** | 18.8 – 22.1 |
| 1st | 9.8% | **9.4%** | 24 – 29% |
| 8th | 5.1% | 5.9% | 3 – 11% |
| Reach heads-up | 24.8% | 24.2% | 39.4% |
| Win heads-up when there | 38.8% | 38.0% | 64.4% |

Top 5 at our tables: Pluto 22.1, Cold Decks 19.9, LLinusLLoveBot 19.3, Amateur Pros 18.8, SIGSEGV 18.8. The field got slightly tougher against us (v4 is the same); every leak from #15 repeats to within a point or two.

## Where the 7.3 points to the top 5 go

| Tournament equity / table | Us | Top 5 | Gap |
|---|---|---|---|
| 5–8 players | +0.29 | +4.75 | 4.5 |
| 3–4 players | −0.16 | +1.75 | 1.9 |
| Heads-up | −0.10 | +0.80 | 0.9 |
| *Big blind, all stages* | −7.17 | −3.15 | 4.0 |
| *Small blind, non-heads-up* | −1.46 | +0.26 | 1.7 |

The blinds alone are 5.7 of the 7.3 points.

## Preflop, us vs top 5 (round 1)

| | Us | Top 5 |
|---|---|---|
| Fold to a raise, 5–8 players | 86–90% | 74–79% |
| Fold to a raise, 3–4 players | 83–87% | 64–72% |
| Re-raise or reshove, >20bb, 5–8 players | 2.9% | 14.4% |
| Reshove, 10–20bb, 5–8 players | 4.5% | 13.1% |
| Button first in, 5–8 players | 35–43% | 56–60% |
| Small blind first in, 5–8 players | 57–62% | 76–85% |
| First in at 3–4 players, >20bb | 47% | 61% |

By our cards facing a raise at >20bb: fold 54% of pairs, 89% of ace-high, 98% of king-high. At ≤10bb: fold 62% of pairs, 80% of ace-high.

The top 5 mostly **re-raise** rather than call: 12.3% re-raise vs 6.3% call when deep. Our 7.5% call / 2.3% re-raise is the reverse.

## Heads-up (round 1)

| | Us | Top 5 |
|---|---|---|
| Button fold ≤10bb / 10–25bb / >25bb | 22 / 37 / 31% | 9 / 21 / 19% |
| Big blind fold to raise ≤10 / 10–25 / >25bb | 61 / 71 / 85% | 20 / 29 / 40% |
| Big blind reshove vs raise ≤10 / 10–25bb | 16 / 8% | 60 / 46% |
| Big blind 3-bet vs raise >25bb | 3% | 46% |
| Big blind call a shove ≤10bb | 20% | 49% |

We still fold 57% of jack-high-or-lower buttons at ≤10bb and 86% at 10–25bb, and as big blind fold 72% of ace-high and 63% of pairs to a ≤10bb shove.

## Recommended changes (same order as #15, now confirmed on two runs)
1. **Big blind defence**, all table sizes: never fold a pair to one raise; continue with ace-high and king-high; heads-up reshove ≤25bb over a button raise with pairs, aces, kings and good queens (they reshove 46–60%); call ≤10bb shoves with any ace, king or pair.
2. **Re-raise, don't call**: move `threebet` up to roughly 0.10–0.12 deep and reshove ~12% at 10–20bb. v4 has 0.03.
3. **Wider first-in**: button ≥ 55%, small blind ≥ 75%, heads-up button ≥ 80–90%.
4. Postflop and bust numbers follow as a comment.

## Not analysed
Two uploads made after this round are not on GitHub, so I can't tie code to results for the next run: `0e986661` (73,890 B, 19:18 EST) and `10809172` (73,759 B, 19:20 EST, **active now**). `bots/final` on `main` (e24d24b) is still the 73,673-byte v4. Please push both to `uploads/` with a line on what changed.

Rounds are fibonacci-weighted and this was weight 1, so the cost of this result is small; the same leaks in later rounds will cost much more.


---

## Follow-up comment

Postflop and bust half of round 1 (same file, same top 5).

**Fold to a bet (first decision facing a bet on that street)**

| | Us | Top 5 | Practice 4 us / top 5 |
|---|---|---|---|
| Flop | 24.8% (n=30,848) | 50.7% (n=11,773) | 26.6 / 41.3 |
| Turn | 22.4% (n=22,777) | 42.6% (n=6,564) | 23.6 / 32.5 |
| River | 34.9% (n=18,223) | 41.2% (n=4,324) | 34.7 / 35.4 |
| Raise when bet into, flop | 0.4% | 5.3% | – |
| Flop c-bet | 50.6% (n=25,252) | 54.9% (n=13,631) | 49 / 57 |

**Tournament equity per table by how the hand ended**

| | Us | Top 5 |
|---|---|---|
| Fold on flop | −1.12 | −2.02 |
| Fold on turn | −1.57 | −1.56 |
| Fold on river | −2.43 | −1.28 |
| Showdown, bet/raised postflop | +1.96 | +2.30 |

**Busts**

| | Us (n=9,063) | Top 5 (n=2,357) |
|---|---|---|
| Blinded out (forced all-in from a blind) | 9.0% | 2.5% |
| Preflop shover | 74.8% | 68.2% |
| Preflop caller | 10.5% | 19.3% |
| Postflop | 5.7% | 10.1% |
| Hands played at ≤5bb | 6.3% | 1.8% |
| First in at ≤5bb: shove / fold / limp | 42.5 / 49.9 / 7.7% (n=29,446) | 52.6 / 44.3 / 3.1% |

**Recommendations**
1. Fold about twice as often to flop and turn bets (top 5: ~50% and ~40%). We pay to reach the river and then fold it, which costs 1.15 points/table more than the top 5.
2. Add raises when bet into postflop: ours are 0.4% on the flop against 5.3%.
3. Shove earlier when short: we spend 3.4× as many hands at ≤5bb, still fold half of them first-in and limp 8%; 9% of our busts are forced blind all-ins. At ≤5bb first-in should be shove or fold, never limp, and much wider.

Caveats: the chip ledger was not re-reconciled for this file (same street logic as practice 4); rank is among teams at our tables in the first 10,000 tables, not the official standing.
