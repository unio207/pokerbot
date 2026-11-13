# Postflop by made hand, and short-stack shoves

Posted as https://github.com/unio207/pokerbot/issues/19

Research only; follow-up to #18, done while round 2 runs. Same pooled data (practice 4, round 1, practice 5: 25,003 of our tables), now with **our made hand on each of the two boards** at every postflop decision, plus short-stack shove results by hand class. Values are tournament-equity points for the whole hand; "per table" = total ÷ 25,003.

Hand labels are per board, best board first: `trips+`, `twopair`, `toppair` (top pair or overpair), `lowpair`, `fdraw`, `air`. Flop and turn use the best two of our three cards for each board separately.

## 1. We only bet when we are strong on both boards
When no one has bet yet (flop, n = 168,186) we bet 37%. By holding:

| Our hand (board A / board B) | We bet | Result when we bet | Result when we check | n |
|---|---|---|---|---|
| top pair / top pair | 97% | +1.27 | −0.33 | 11,964 |
| trips+ / top pair | 98% | +2.00 | +0.43 | 7,364 |
| top pair / low pair | 49% | +0.14 | −0.42 | 17,580 |
| **top pair / air** | **9%** | +0.25 | −0.33 | 16,796 |
| **two pair / low pair** | **17%** | +0.22 | −0.63 | 12,123 |
| **two pair / air** | **8%** | +0.33 | −0.22 | 8,638 |
| **trips+ / air** | **32%** | +0.88 | +0.28 | 3,631 |
| low pair / low pair | 9% | −0.23 | −0.72 | 18,826 |
| low pair / air | 8% | −0.06 | −0.51 | 14,797 |
| air / air | 8% | −0.17 | −0.58 | 19,254 |

- In **every** class, the hands we bet do 0.4–0.9 better than the ones we check. The turn table has the same shape (bet 38% overall; top pair/air bet 6%, two pair/air 7%, trips+/air 44%).
- We check trips-or-better on one board 68% of the time on the flop when the other board missed. A hand that wins half the pot outright is being played as a check.
- Because we bet only with both boards, our bets are easy to fold to and our checks are safe to attack.
- **Change:** bet whenever we have top pair or better on at least one board; bet two pair/trips on one board always. Then add bluffs with air and low pairs at some frequency (even our rare air bets lose less than checking: −0.17 vs −0.58). The 106,000 flop checks are the largest pool of hands in the postflop game; moving a third of them at +0.3 each is ~0.4 points/table, and the turn adds about as much.

## 2. Facing a bet we call with any pair and never raise
Flop, facing a bet (n = 41,874): fold 19%, call 81%, **raise 1%** (raises earn +3.98).

| Our hand | Call | Result of calling | Result of folding | n |
|---|---|---|---|---|
| low pair / low pair | 83% | **−1.98** | −1.03 | 5,585 |
| two pair / low pair | 90% | −1.87 | −1.39 | 3,778 |
| top pair / low pair | 96% | −1.43 | −2.63 | 5,104 |
| top pair / air | 90% | −1.22 | −1.47 | 3,317 |
| low pair / air | 40% | −1.16 | −0.97 | 2,508 |
| trips+ / top pair | 97% (raise 2%) | +1.72 | – | 2,186 |
| trips+ / two pair | 98% | +0.26 | – | 1,252 |
| trips+ / trips+ | 44% (raise 55%) | +2.18, raise **+4.24** | – | 310 |

Turn is the same: call 82%, raise 1%; low pair/low pair calls −2.45 (fold −2.40 after already paying the flop); trips+/top pair calls 93% and raises 4%.

- Calling the flop with only low pairs costs about 1 point more than folding, 4,640 times: ~0.18 points/table, and it sets up the turn call and river fold (#16: river folds cost −2.4/table).
- We just call with trips-or-better. Our few raises are the most profitable action we have.
- **Change:** fold low pair/low pair and low pair/air to a flop bet unless the price is small; raise (not call) with trips+ on one board plus top pair or better on the other; raise two pair+/two pair+.

## 3. Short stack: shove wider, and shove instead of small-raising
First in, ≤10bb:

| Seat | Hand | We fold | Fold result | Shove result | n folded |
|---|---|---|---|---|---|
| Small blind, 3–4 players | J-high or lower | **81%** | **−0.72** | +0.32 | 6,557 |
| Small blind, 3–4 players | Q/K with low kicker | 62% / 35% | −0.66 | +0.49 / +0.47 | 1,835 |
| Small blind, 5–8 players | J-high or lower | 81% | −0.61 | +0.40 | 2,277 |
| Button, 5–8 players | K with low kicker | 83% | +0.04 | +0.91 | 1,201 |
| Button / cutoff | A with low kicker | 47% / 70% | +0.07 | +0.51 / +0.56 | 2,236 |
| Cutoff | K with T+ | 49% | +0.08 | +0.69 | 1,030 |
| Facing a raise, not BB | Pair TT+ | **24%** | −0.19 | +2.33 | 1,079 |

- Small blind at ≤10bb: folding costs 0.6–0.7 every time. Shoving any three cards is better; the J-high row alone is ~0.3 points/table at face value.
- At 10–20bb our small raises do worse than our shoves with the same hand: A with T+ on the button, raise +0.11 vs shove +0.72; A-low raise −0.18 vs shove +0.64; low pair raise −0.15 vs shove +0.29. **Change:** at 10–20bb, shove or fold; drop the raise-then-fold line.
- Early-seat low pairs lose at every depth (shove −0.29 at 10–20bb, raise −0.22): fold them there.

## Rule list for Henry (adds to #18)
1. Bet with top pair+ on **either** board; always bet two pair/trips on one board.
2. Raise, don't call, with trips+ on one board and top pair+ on the other.
3. Fold low pair/low pair and low pair/air to flop bets.
4. Small blind ≤10bb: shove everything. Never fold pair TT+ to a raise when short.
5. 10–20bb first in: shove or fold.

## Caveats
- Results are whole-hand outcomes, so a fold's figure includes chips already put in; compare rows, don't read them as the price of that one action.
- Observational: inside a class we choose which hands to bet or call, so differences overstate what the rest would earn. Signs are consistent across all classes and both streets, which is the real evidence.
- "Two pair" includes one of our cards pairing a paired board. River classes are not reported: after the discard I can't tell which two cards we kept unless the hand was shown.
- Bet-size and fold-equity numbers (how often the field folds to each size) follow as a comment.
