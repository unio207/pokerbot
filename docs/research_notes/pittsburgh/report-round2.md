# Round 2: 71st/111, 11.78 pts

Posted as https://github.com/unio207/pokerbot/issues/20

Research only. Scored round 2 (`d44e4147`, **weight 2**, first 10,000 of 20,000 tables). The portal's health record says this round was played by `469e96f5` (74,862 B, uploaded 19:33:57 EST, active). That file is not on GitHub; `uploads/README.md` says v9 `fc9b02c4` played round 2. **Please confirm which, and push `469e96f5`.** Behaviour below is measured from the hands.

## Result: 71st of 111, 11.78 ± 0.17 points (par 12.5)

| | Round 1 (v4) | **Round 2** | Top 5, round 2 |
|---|---|---|---|
| Points/table | 12.52 ± 0.17 | **11.78 ± 0.17** | 18.7 – 20.8 |
| 1st / 8th | 9.4% / 5.9% | 9.1% / **7.4%** | 24–29% / 5–16% |
| Stack when 4 are left (× average) | 0.81 | 0.82 | 1.14 |

Top 5: Pluto 20.8, Poker is all you need 20.0, Ferdabot II 19.0, LLinusLLoveBot 18.9, Hold Em Trophies 18.7.

## What changed in our play, and what it did

| | Round 1 | Round 2 | Top 5 | Effect |
|---|---|---|---|---|
| Button first in, >20bb | 43% | **59%** | 52% | none: +0.076/open vs their +0.197 |
| Small blind first in, >20bb | 58% | **76%** | 83% | none: +0.047 vs +0.110 |
| Heads-up BB fold to raise (10–25bb) | 71% | **58%** (reshove 33%) | 29% | heads-up −0.10 → **+0.02**/table |
| BB, pair TT+ vs raise: re-raise or shove | 42% | **89%** | – | good: +0.52 / +0.94 |
| BB, pair 99− vs raise: **call** | 32% | **76%** | – | **bad: −0.86 each** (n=5,320) |
| Big blind total, 5–8 players | −3.72 | **−4.17** | −1.15 | worse |

- Opening frequencies now match the top 5, but the extra opens earn nothing: the added hands (K-low +0.03, Q-low +0.01, A-low −0.02) do no better than folding (+0.01). Their opens earn 2.5× ours at the same frequency, so the difference is after the open.
- The new low-pair calls in the big blind cost about **0.32 points/table** by themselves (folding costs −0.26, calling −0.86). This is the flat-call leak from #18 made bigger. **Revert it now**: fold or re-raise, never call.

## What the top 5 do that we don't

**1. Facing a raise they re-raise or fold. They almost never call.**

| >20bb, 5–8 players | Us | Top 5 |
|---|---|---|
| Not in BB: call / re-raise+shove | 5% (−0.30) / 2% | **0%** / 11% (+0.37) |
| All seats: call / re-raise+shove | 7.7% / 4.1% | **2.4%** / 18.1% |
| Big blind: fold / call / re-raise+shove | 74 / 17 / 9% | 56 / **6** / **39%** |
| Big blind result per hand | −0.226 | **−0.025** |

Their big blind nearly breaks even against a raise; ours loses 9× as much. Over ~6.6 such hands per table at 5–8 players that is 1.3 points/table, and the big blind in total is 5.0 of the 7.7 points between us (−7.3 vs −2.3).

**2. After the flop they bet, raise, or fold. We check and call.**

| | Us | Top 5 |
|---|---|---|
| Flop c-bet | 49% | **78%** |
| Facing a flop bet: fold / call / raise | 26 / 74 / **0.3%** | 51 / 35 / **14%** |
| Facing a turn bet: fold / call / raise | 22 / 77 / 0.8% | 41 / 51 / 8.5% |
| Facing a river bet: fold / call / raise | 35 / 64 / 0.8% | 46 / 48 / 5.8% |

They call a flop bet half as often as we do and raise it 50× as often.

**3. Heads-up they 3-bet the button.** Big blind vs a raise: >25bb they re-raise 52% and call 1%; 10–25bb they reshove 50% and raise 21%. They call a ≤10bb shove 52% (us 26%). They win 68% of heads-up matches (us 40%).

**4. They never get short.** 2.0% of their hands are at ≤5bb (us 5.8%); 1.7% of their busts are blind-outs (us 5.9%, down from 9.0%).

**5. They min-raise.** 2.0bb opens 53% of the time (us 22%).

## Changes, in order of expected value
1. **Stop calling raises.** Big blind and elsewhere: re-raise to ~3× with the top ~15–20% (in the BB ~35%), fold the rest; call only when the price is tiny. Revert the low-pair BB calls today.
2. **C-bet ~75% of flops in heads-up pots at 40–50% pot** (the field folds 40% to a c-bet at any size; see the sizing comment on #19).
3. **Raise flop bets** with trips+/top pair or better (we call 97% with those, #19) and **fold low pairs** to flop bets.
4. Heads-up big blind: reshove 10–25bb over a button raise with the top half; call ≤10bb shoves with any ace, king, or pair.
5. Open to 2.0bb.

Items 1 and 2 are frequency rules that do not depend on reading the boards well; they are what separate the top 5 from the field, which plays like us (field BB call 26%, re-raise 6%).

Caveats: one run; top-5 numbers come from ~3,200 of their tables against us; ranks are among teams at our tables in the first 10,000 tables.
