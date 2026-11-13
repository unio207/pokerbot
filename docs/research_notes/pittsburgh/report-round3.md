# Round 3 (v13): 64th/112, 12.35 pts

Posted as https://github.com/unio207/pokerbot/issues/22

Research only. Scored round 3 (`ca825b02`, first 10,000 tables) was played by v13 `1b9ad55e` (73,996 B, on `origin/uploads`): v4's preflop plus the new postflop settings, with none of the v7/v9/v11 preflop changes.

## Result: 64th of 112, 12.35 ± 0.16 points (par 12.5)

| | Round 1 (v4) | Round 2 (v11) | **Round 3 (v13)** | Top 5, round 3 |
|---|---|---|---|---|
| Points/table | 12.52 | 11.78 | **12.35 ± 0.16** | 18.3 – 20.8 |
| 1st | 9.4% | 9.1% | **8.0%** | 19–30% |
| 2nd–4th | 48% | 45% | **50.5%** | |
| Heads-up matches won | 38.0% | 40.2% | **33.5%** | 65.6% |

Top 5: Poker is all you need 20.8, Pluto 20.3, Claude Mythos 5.5 19.3, LLinusLLoveBot 19.3, Cold Decks 18.3.

## 1. The postflop change worked
Frequencies now match the top 5, and the hands it touches stopped losing:

| | Round 1 | **Round 3** | Top 5 |
|---|---|---|---|
| Flop c-bet | 51% | **75.5%** | 74.8% |
| Facing a flop bet: fold / call / raise | 25 / 75 / 0.4% | **48 / 47 / 4.7%** | 46 / 44 / 9.9% |
| Facing a turn bet: fold / raise | 22 / 0.8% | **38 / 5.0%** | 42 / 5.7% |
| Our first-in raise, result per attempt (mid-tier BB) | +0.05 | **+0.34** | +0.28 |
| Calling a raise in the BB, >20bb | −0.23 | **−0.06** | −0.01 |
| Calling a raise elsewhere, >20bb | −0.30 | **−0.06** | – |
| Points won at 5–8 players | +0.29 | **+0.46** | +4.39 |

Our opens now earn as much per attempt as the top 5's. Keep every v13 postflop setting.

## 2. But v13 threw away the preflop and heads-up fixes, and that cancelled it out
v13 is built on v4, so everything round 2 fixed is gone again:

| | Round 2 (v11) | **Round 3 (v13)** | Top 5 |
|---|---|---|---|
| Heads-up BB fold to raise, 10–25bb | 58% | **70%** | **7%** (shove 57%, raise 27%) |
| Heads-up BB call a ≤10bb shove | 26% | **16.5%** | 65% |
| Heads-up result per table | +0.02 | **−0.24** | +0.77 |
| BB: pair TT+ re-raise or shove vs a raise | 89% | **40%** (call 58%) | – |
| Busts from being blinded out | 5.9% | **9.8%** | 1.8% |
| First in at ≤5bb: shove | 52% | 41% | 47% |
| Button / small blind first in, >20bb | 59 / 76% | 43 / 58% | 47 / 73% |

Each build so far fixes one area and drops the others: v11 had the preflop pieces without the postflop, v13 has the postflop without the preflop. **They have never run together.**

## 3. What is still missing in both: re-raising
| Facing a raise, >20bb, 5–8 players | Us | Top 5 |
|---|---|---|
| Not in BB: re-raise + shove | 2.5% | **19.7%** |
| Big blind: fold / call / re-raise + shove | 80 / 17 / **3%** | 47 / 10 / **42%** |
| Big blind result per hand | −0.191 | **−0.021** |
| Big blind, total points per table | **−7.06** | −1.48 |

The big blind is now 5.6 of the 7.25 points between us and the top 5. They re-raise 36% and shove 6% from it; we do 3%. Our rare re-raises with TT+ earn +1.06 and shoves +1.32, against +0.17 for calling the same hands.

Also: 73% of top-5 opens are now 2.0bb (ours 21%).

## Build to ship next (one merge, no new ideas)
1. **v13 postflop, unchanged.**
2. **From v11, bring back:** `bb_reraise`, the heads-up big-blind defence and ≤10bb all-in calls (any ace, king, pair), wider ≤5bb first-in shoves, and v9's `open` table.
3. **Do not bring back** v11's "call with any pair in the big blind" (it cost ~0.3/table in round 2). Pairs 99− fold or reshove.
4. **Raise the re-raise frequency**: pair TT+ always re-raises or shoves; target ~35% re-raise from the big blind and ~12% elsewhere when deep; heads-up reshove 10–25bb with about the top half.
5. Open to 2.0bb.

Expected direction from the measurements: round 2 showed the preflop/heads-up pieces moved heads-up from −0.10 to +0.02 and halved blind-outs; round 3 shows the postflop pieces turned calls from −0.3 to −0.06 and tripled what an open earns. Neither alone moved the total, because each build gave back what the other had gained.

## Farming check on round 3 (same method as #21)
Net bb per table: from weak +3.6, mid −2.6, top −2.6 (top 5: +7.5 / +5.7 / +1.4, and +2.6 from us). Same pattern as practice 6 with the main bot: we profit only from the weak tier.

## Note
A practice run `242e19e4` has already been played by a newer upload `e140891a` (74,507 B, active, not on GitHub). I will report on it separately.

Caveats: one run; ranks are among teams at our tables in the first 10,000 tables; top-5 figures are their play at our tables.
