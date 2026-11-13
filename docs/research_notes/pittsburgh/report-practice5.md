# Practice 5 (upload 10809172): 71st/111, 11.73 pts

Posted as https://github.com/unio207/pokerbot/issues/17

Research only. Practice 5 (`b808eec7`, 5,000 tables) was played by the new upload `10809172` (73,759 B, uploaded 19:20 EST, **active**). That file is on no branch (`main` and `uploads/` still end at v4, 73,673 B), so this is behaviour measured from the hands, not from code.

## Result: 71st of 111, 11.73 ± 0.23 points (below par 12.5)

| | Practice 4 (v4) | Round 1 (v4) | **Practice 5 (`10809172`)** | Top 5 now |
|---|---|---|---|---|
| Points/table | 13.00 ± 0.17 | 12.52 ± 0.17 | **11.73 ± 0.23** | 19.5 – 21.6 |
| Rank at our tables | 53 / 107 | 62 / 109 | **71 / 111** | |
| 1st | 9.8% | 9.4% | **8.0%** | 24 – 28% |
| 8th | 5.1% | 5.9% | 6.3% | |
| Reach heads-up | 24.8% | 24.2% | 22.0% | 39.8% |
| Win heads-up when there | 38.8% | 38.0% | 35.8% | 65.4% |

Top 5: Pluto 21.6, Cold Decks 19.8, kangbot 19.8, Poker is all you need 19.6, SIGSEGV 19.5.

## 1. The new upload plays the same as v4
Every frequency I measure is within a point of round 1:

| | Round 1 (v4) | Practice 5 | Top 5 (practice 5) |
|---|---|---|---|
| Fold to a raise, 5–8 players, >20bb | 89.6% | 89.6% | 79.2% |
| Re-raise or reshove, 5–8 players, >20bb | 2.9% | 2.8% | 15.2% |
| Button first in, 5–8 players, >20bb | 42.9% | 42.3% | 50.3% |
| Small blind first in, 5–8 players, >20bb | 58.0% | 58.7% | 72.5% |
| Heads-up button fold ≤10 / 10–25bb | 22 / 37% | 21 / 37% | 9 / 22% |
| Heads-up big blind fold to raise ≤10 / 10–25 / >25bb | 61 / 71 / 85% | 62 / 72 / 87% | 36 / 20 / 21% |
| Heads-up big blind call a ≤10bb shove | 20% | 18% | 50% |
| Fold to bet flop / turn / river | 25 / 22 / 35% | 25 / 22 / 35% | 44 / 38 / 39% |
| Raise when bet into, flop | 0.4% | 0.3% | 6.0% |
| Flop c-bet | 50.6% | 50.1% | 74.3% |
| Busts that are forced blind all-ins | 9.0% | 8.7% | 2.4% |
| First in at ≤5bb: shove / fold / limp | 43 / 50 / 8% | 41 / 51 / 8% | 53 / 44 / 3% |

Whatever changed in `10809172` (+86 bytes over v4) does not show up in play. **We are slipping because the field is improving and we are not**: the same behaviour scored 13.0, then 12.5, now 11.7, while the top 5 stay near 20.

## 2. Where the 8.3 points to the top 5 go (tournament equity / table)

| | Us | Top 5 | Gap |
|---|---|---|---|
| 5–8 players | −0.30 | +4.87 | 5.2 |
| 3–4 players | −0.32 | +1.94 | 2.3 |
| Heads-up | −0.14 | +0.76 | 0.9 |
| *Big blind, all stages* | −7.50 | −2.95 | 4.6 |
| *Small blind, non-heads-up* | −1.49 | +0.47 | 2.0 |
| *Hands we fold on the river* | −2.39 | −1.14 | 1.3 |

By our cards facing a raise at >20bb we still fold 54% of pairs, 89% of ace-high, 98% of king-high. Heads-up as big blind we fold 74% of ace-high and 65% of pairs to a ≤10bb shove.

## Recommended changes (unchanged, third run confirming)
1. **Big blind defence**: never fold a pair to one raise; continue ace-high and king-high; heads-up reshove ≤25bb over a button raise (they do 44–46%), call ≤10bb shoves with any ace, king or pair.
2. **Re-raise instead of call**: ~13–15% deep, ~10% reshove at 10–20bb. We are at 2.8% and 4.4%.
3. **Postflop**: fold flop and turn about twice as often to bets, c-bet much more (74% vs our 50%), add raises when bet into.
4. **Short stack**: shove-or-fold at ≤5bb, no limps, wider; we spend 2.7× as many hands there as the top 5.
5. **Wider first-in** on button and small blind.

## Needed from Henry
- Push `0e986661` (73,890 B) and `10809172` (73,759 B) to `uploads/` with what changed. If `10809172` was meant to change preflop or heads-up behaviour, it did not take effect — worth checking the setting is actually read (as with the dropped `hu_open` change noted in e24d24b).

Caveats: 5,000 tables, so ± 0.23 on our points; top-5 rates come from ~1,600 of their tables against us.
