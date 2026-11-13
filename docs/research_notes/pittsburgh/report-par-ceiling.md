# Why we are a par bot

Posted as https://github.com/unio207/pokerbot/issues/18

Research only. Vedaant asked why we are stuck as a par bot. This pools the three runs that show identical behaviour (practice 4, round 1, practice 5: 25,003 of our tables) and, using **our own hole cards**, compares what each hand class earned by action in the same spot. Units are tournament-equity points per hand (50/30/20 scale); "per table" = total ÷ 25,003.

## The short version
We are par because we play like the average bot in three specific ways, and each has a measurable price:

| # | Leak | Evidence | Rough size (points/table) |
|---|---|---|---|
| 1 | We **flat-call raises with our best hands** instead of re-raising | calls lose, re-raises win, same hand class | 0.5 – 1.2 |
| 2 | We **fold strong hands in the big blind when short** | TT+ pairs folded 21–46% of the time | 0.4 – 0.7 |
| 3 | Our **hand ranking overvalues low pairs** and undervalues big cards | low-pair opens lose; folded A/K hands win when played | 0.3 – 0.5 |
| 4 | We **reach the last four short** | 0.81× the average stack vs 1.13× for the top 5 | (result of 1–3) |

Sizes assume the hands we currently fold/call would do about as well as the same-class hands we already play the other way. That overstates it (we pick the better ones), so the low end is half the raw figure. Even the low ends add ~1.5 points, which is par → roughly 30th.

## 1. Calling loses, re-raising wins — with the same cards
Facing one raise, not in the big blind, 5–8 players, >20bb (n = 477,417):

| Our hand | Call | Re-raise | Shove |
|---|---|---|---|
| Pair TT+ | 55% of the time, **−0.22** (n=16,836) | 33%, **+1.38** (n=10,169) | 8%, +1.85 |
| Pair 99− | 11%, **−0.74** (n=5,957) | 1%, −0.23 | – |

Whole group: us call 5% at **−0.34**, re-raise 2% at +1.25. Top 5: call 4% at +0.11, **re-raise 10% at +0.54**. Field: call 8% at −0.23.

Same in the big blind (>20bb, n = 167,229): pair TT+ call 56% at +0.09 vs raise 29% at +1.22; pair 99− call 32% at **−0.70** when folding costs only −0.25. Top 5 there: re-raise 17% at +0.37 and fold only 59%.

- Flat-calling a pair to "see a flop" does not work in this game: two boards and a discard mean a pair rarely holds both halves, and we then call flop/turn and fold the river (#16).
- **Change:** with pair TT+ facing a raise, always re-raise or shove, never call. With pair 99− facing a raise, fold or reshove (short), don't call. Then add a bluff re-raise range to reach ~10% (A/K-high with a T+ second card).

## 2. Big blind when short: we fold hands that are clearly ahead

| Spot | Hand | We fold | Fold costs | Playing earns |
|---|---|---|---|---|
| BB vs raise, ≤10bb, 3–4 players | Pair TT+ | **39%** (n=1,154) | −1.62 | +2.40 shove / +2.90 call |
| | A with T+ | 63% (n=3,053) | −1.63 | −0.35 call / +1.10 shove |
| | K with T+ | 66% (n=2,294) | −1.64 | −0.74 call |
| BB vs raise, ≤10bb, 5–8 players | Pair TT+ | 21% (n=382) | −1.42 | +2.12 / +3.08 |
| | A with T+ | 43% (n=1,350) | −1.37 | −0.48 call / +1.33 shove |
| Heads-up BB vs shove, ≤10bb | Pair TT+ | **46%** (n=565) | −0.76 | +2.40 |
| | A with T+ | 69% (n=1,423) | −0.84 | +0.89 |
| | Pair 99− | 74% (n=1,525) | −0.85 | +0.47 |
| | K / Q with T+ | 69% / 79% | −0.85 | +0.05 / +0.06 |

In every row, the hands we do play earn more than folding costs, including the weakest class we ever play. That is the signature of a threshold set far too tight. Folding TT+ with ≤10bb is never right; it looks like a survival rule (`bubble_margin` / `points_tight` 0.08) overriding card strength.

**Change:** at ≤10bb in the big blind, never fold pair TT+ or A-with-T+; heads-up call any shove with those plus any pair, and K/Q with a T+ second card.

## 3. The hand ranking is off: low pairs are overrated, big cards underrated
First in, 5–8 players, >20bb:

| Seat | Hand | What we do | Result when raised | Result when folded |
|---|---|---|---|---|
| Early | Pair 99− | raise 39% (n=20,520) | **−0.25** | +0.03 |
| Early | A with T+ | fold 62% (n=35,022) | **+0.09** | +0.02 |
| Cutoff | Pair 99− | raise 51% (n=5,563) | **−0.21** | +0.03 |
| Button | Pair 99− | raise 63% (n=4,430) | **−0.13** | +0.01 |
| Button | K with low kicker | fold 89% (n=5,064) | +0.14 | +0.01 |
| Button | Q with T+ | fold 72% (n=2,527) | +0.10 | +0.01 |
| Small blind | J-high or lower | fold 85% (n=10,005) | +0.06 | **−0.15** |
| Small blind | K with low kicker | fold 52% (n=1,562) | +0.08 | −0.15 |

Low-pair opens cost about 0.25 points/table by themselves. **Change:** in the strength ordering, move pairs 99− below A/K/Q hands with a T+ second card for opening; open the small blind with almost everything (folding costs −0.15 every time and the field folds to a small-blind raise 64%).

Heads-up button has the same shape: J-high-or-lower is folded 56% at ≤10bb (−0.39) while shoving it earns +0.21 (n=5,211), and folded 86% at 10–20bb (−0.27) while shoving earns +0.18.

## 4. Supporting measurements
- **Stack when 4 are left:** us 0.81× average, top 5 1.13×, field 1.03×. We survive to the last four more often than the field but arrive short, so we collect 2nd–4th and not 1st.
- **Steals work for everyone:** a first-in raise at >20bb wins the pot immediately 40% of the time from early seats, 51% from the button and 64% from the small blind (field). No seat or stack depth has a negative average for raising first in.
- **Open size:** we raise to 2.5bb 79% of the time; the top 5 use 2.0bb 58% of the time and still get more folds (button 50% vs our 47%). Min-raising risks less for the same result.
- **Re-raises get paid by the field:** field-wide, a re-raise deep earns +0.5 to +0.9 per hand; a call earns −0.23 to −0.29.

## Suggested order for Henry
1. Pair TT+ vs a raise: re-raise/shove always (one rule, largest single item).
2. Big blind ≤10bb never-fold list, and the heads-up call list vs shoves.
3. Demote pairs 99− in the opening order; stop calling raises with them.
4. Small blind and heads-up button: open/shove nearly everything.
5. Open to 2.0bb.
Each is a single rule that can be A/B'd in a practice run by the same tables above (`scripts/edge.py`, `edgerep.py` on the research branch).

## Caveats
- Observational, not counterfactual: hands inside a class differ (TT vs AA, suits, third card), and we already choose the better ones to play. Treat signs as reliable where the gap is large (sections 1–2) and sizes as upper bounds.
- Classes use rank only (pair / highest card / second card), not suits or connectedness.
- Top-5 comparisons are their play at our tables.
