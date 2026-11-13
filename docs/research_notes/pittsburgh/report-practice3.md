Quick report on practice 3 (`78b91f28`, 10,000 tables). Research only. More detail will follow as a comment.

## Result: we're getting worse
| | Practice 1 | Practice 2 | **Practice 3** |
|---|---|---|---|
| Upload | `920a2429` (73,246 B) | `066139f9` = v3a | `393c48a3` (73,364 B) |
| Rank | 32 / 82 | 43 / 100 | **59 / 105** |
| Points | 15.95 | 14.47 | **12.43 ± 0.31** (below par 12.5) |
| 1st | 11.4% | 7.5% | **7.0%** (top 8: 23–30%) |
| 8th | 5.3% | 3.5% | **8.5%** |
| Missed decisions | 0 | 0 | 0 |

## 1. The heads-up bug (#13) is still in the build that played
Same measurement as practice 2, first 3,000 of our tables in each:

| | Practice 2 | Practice 3 |
|---|---|---|
| Our button, >15bb: fold | 89% | **88%** |
| Our button, ≤15bb: fold | 71% | **71%** |
| Facing a button raise: fold | 84% | **84%** |
| Heads-up tables won | 24.5% | 26.7% |

Opponents on the button: raise 58%, fold 30%. **The #13 fix is still the top priority.**

## 2. New regression: we bust earlier
- We reach heads-up at **25.7%** of tables (practice 2: 29.8%).
- We finish 8th **8.5%** of the time (practice 2: 3.5%).

Whatever changed between v3a and `393c48a3` loses chips in the early and middle game. I can't name the change because:

## 3. The last three uploads aren't on GitHub
`393c48a3` (73,364 B, played practice 3), `d55b4134` (73,673 B, **active now**) and `920a2429` match no commit on any branch. Please push them, ideally with a note on what changed in each, so I can tie results to code.

## Pending
Codex is breaking down chip flow vs the top 5 (by players left, position, street; preflop/postflop frequencies; big pots). Results will come as a comment here.
