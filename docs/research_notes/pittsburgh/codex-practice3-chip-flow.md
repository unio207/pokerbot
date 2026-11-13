**The clearest leak is heads-up overfolding.** Heads-up produces **84.6% of our net chip loss**; BB is our worst position, and preflop-fold pots are our worst ending category.

Analyzed all **10,000 scored tables**, excluding filler appearances: **1,071,371 our player-hands** versus **369,704 top-five player-hands**. Top-team table counts: Pluto 636; LLinusLLoveBot 675; Claude Mythos 5.5 678; Cold Decks 654; SIGSEGV 636.

“Top-5” is the **equal-weight average of five team rates**, using their appearances at our tables. Below, **N = us / combined top-five observations**. Verified raises are street totals, calls are incremental, and `win` accounting varies with the ending; stack-based chip accounting reconciled across **1,156,052 relevant hands without mismatches**.

**Chip flow:** net chips per hand, including blinds. These are separate breakdowns, not additive categories across the entire table. HU button/SB counts as button. Ending street describes the whole pot, even if we folded earlier.

| Slice | Us chips/hand | Top-5 chips/hand | N |
|---|---:|---:|---:|
| Overall | −8.15 | +25.84 | 1,071,371 / 369,704 |
| 8–5 players | +0.11 | +12.33 | 803,472 / 271,999 |
| 4–3 players | −7.51 | +47.27 | 190,682 / 69,294 |
| Heads-up | **−95.73** | **+109.90** | 77,217 / 28,411 |
| Button | +12.77 | +74.91 | 215,227 / 75,247 |
| SB | −12.62 | +19.20 | 176,310 / 61,040 |
| BB | **−73.17** | −8.35 | 213,595 / 75,175 |
| Other position | +13.66 | +21.24 | 466,239 / 158,242 |
| Preflop fold ending | **−14.13** | +39.45 | 639,389 / 224,835 |
| Flop ending | −2.73 | +2.88 | 71,829 / 24,963 |
| Turn ending | −24.68 | −20.37 | 36,265 / 12,079 |
| River/showdown ending | +4.30 | +8.07 | 323,888 / 107,827 |

Total losses: **−8.736m chips overall; −7.392m heads-up; −15.629m in BB; −9.036m in preflop-ending pots.** Those categories overlap. Blind-normalized results also confirm the HU gap: **−18.9 versus +22.3 BB/100**.

**Preflop:** depth uses our hand-start stack, not effective stack. Open = raise when first into an unopened pot; fold-to-raise = first decision facing a raise; 3-bet = opportunity facing exactly one raise; shove = all-in raise per dealt hand, excluding all-in calls.

| Depth | Metric | Us | Top-5 | N |
|---|---|---:|---:|---:|
| ≤10 BB | Open | 33.2% | 52.3% | 99,776 / 14,737 |
| | Fold-to-raise | 86.1% | 70.7% | 80,604 / 12,207 |
| | 3-bet | 6.1% | 12.3% | 77,315 / 11,634 |
| | Shove | 19.8% | 30.8% | 201,528 / 28,997 |
| 10–20 BB | Open | 29.6% | 44.3% | 105,292 / 32,957 |
| | Fold-to-raise | 84.6% | 72.0% | 90,761 / 27,119 |
| | 3-bet | 5.8% | 15.8% | 82,150 / 24,084 |
| | Shove | 11.9% | 17.3% | 208,577 / 64,503 |
| >20 BB | Open | 30.8% | 35.8% | 320,746 / 135,669 |
| | Fold-to-raise | 84.6% | 76.1% | 308,532 / 127,992 |
| | 3-bet | 5.0% | 16.7% | 264,127 / 109,903 |
| | Shove | 2.0% | 3.8% | 661,266 / 276,204 |
| HU | Button open | **22.2%** | **80.1%** | 36,820 / 13,711 |
| HU | BB fold versus button raise | **83.7%** | **40.9%** | 21,431 / 6,935 |

**Postflop:** c-bet opportunities require being the final preflop raiser, able to act, without facing a flop lead. Fold rates count decisions facing a bet/raise. Split boards make “received chips” different from “net profitable.”

| Metric | Us | Top-5 | N |
|---|---:|---:|---:|
| Flop c-bet | 46.2% | 63.1% | 41,469 / 16,081 |
| Flop fold-to-bet | 25.9% | 48.0% | 32,942 / 10,449 |
| Turn fold-to-bet | 22.5% | 44.1% | 26,058 / 6,517 |
| River fold-to-bet | 33.4% | 47.3% | 22,338 / 4,555 |
| Reach showdown / dealt hands | 10.3% | 9.6% | 1,071,371 / 369,704 |
| Reach showdown / saw flop | 72.8% | 67.0% | 151,776 / 52,974 |
| Showdown: net-positive | 61.2% | 58.1% | 110,551 / 35,367 |
| Showdown: receive any payout | 76.0% | 77.0% | 110,551 / 35,367 |
| Fold river after flop/turn aggression¹ | 6.8% | 7.4% | 22,488 / 9,359 |

¹Among hands reaching river after our earlier bet/raise. **River abandonment is not unusually frequent.**

**Big pots:** matched pot, excluding uncalled excess, exceeds 40% of our **hand-start stack**, and we voluntarily invested on some street. Win = positive net chips. Aggressor = bet/raised at least once.

| Metric | Us | Top-5 | N |
|---|---:|---:|---:|
| Overall win rate | 58.9% | 57.1% | 99,880 / 31,031 |
| Were an aggressor | 77.9% | 80.4% | 99,880 / 31,031 |
| Win rate when aggressive | 65.2% | 60.1% | 77,792 / 24,907 |
| Win rate when entirely passive | **36.8%** | **45.7%** | 22,088 / 6,124 |
| Passive big-pot net chips/hand | **−126.00** | **+146.46** | 22,088 / 6,124 |

**Three priority leaks:**

1. **HU surrender.** We fold **73.9% of actionable buttons**, versus **17.6%**, and lose on both HU positions. **Change:** use dedicated HU ranges; substantially widen button steals and BB calls/reshoves, calibrated to effective stacks and opponent sizing.

2. **Insufficient preflop pressure beyond HU.** Excluding HU, ≤10-BB opens remain **34.8% versus 45.4%** (N **79,694/12,602**); >20-BB 3-bets remain **5.0% versus 16.4%** (N **259,998/106,795**). **Change:** widen late-position opens and introduce more selective 3-bets/reshoves against wide openers, with bubble-risk adjustments.

3. **Likely expensive passive continuations.** Low flop/turn folding, low c-betting, and **−2.783m chips in passive big pots** point here; overall big-pot win rate does not. **Change:** c-bet favorable board pairs more often; scrutinize marginal calls for combined two-board equity, discard implications, and future barrel costs.

These are observational priorities; the third diagnosis needs hand-level equity review before treating every extra call as a mistake.