# What to implement next (for Henry)

One page that collects every recommendation from the hand-history reports of 2026-11-12, in the order I would build them. Research only; nothing here has been tested in code. Each item links to the report with the evidence. Figures are tournament-equity points per table unless stated.

Where we are: par (11.0–13.0 points, 53rd–76th of ~110) on every run. The top five score 19–22. The gap is the same on every run: the big blind (4–5 points), calling instead of re-raising, and passive play after the flop.

## Latest (after round 3)

- Round 3 (v13) showed the postflop settings work; keep them. v13 dropped the round 2 preflop and heads-up fixes; merge them back, without the any-pair big-blind call. See [round 3](report-round3.md).
- Aggression is needed in four places only (heads-up big blind, re-raise instead of call, heads-up button, short-stack shoves), not in opening or postflop betting. See [aggression](report-aggression.md).
- Items 3–5 below are now largely done by v13; items 1, 2, 6 and 7 are the open ones.

## Build order

| # | Change | Rule to implement | Evidence | Report |
|---|---|---|---|---|
| 1 | **Stop calling raises** | Facing a raise: re-raise to ~3× the open or fold. Call only when the price is tiny. Target: call ≤3%, re-raise ~11% outside the big blind and ~35–40% in it. Never call with pairs 99 or lower. | Our calls lose 0.30–0.86 per hand; re-raises win. Top 5 call 2.4% and re-raise 18%. Round 2's new low-pair calls cost ~0.3/table. Practice 6's 54% big-blind call rate scored 11.02. | [round 2](report-round2.md), [par ceiling](report-par-ceiling.md) |
| 2 | **Big blind never-fold list when short** | At ≤10bb never fold pair TT+ or ace with a T+ card to one raise. Heads-up, call a ≤10bb shove with those plus any pair, and K/Q with a T+ card. | We fold TT+ 21–46% in these spots; folding costs 0.8–1.6, playing earns 2.1–3.1. | [par ceiling](report-par-ceiling.md) |
| 3 | **C-bet more, smaller** | As preflop raiser in a heads-up pot, bet ~75% of flops at 40–50% pot. Do not bluff the turn, the river, or pots with 3+ players. | We c-bet 49%, top 5 78%. The field folds ~40% to a flop c-bet at any size; checking as raiser is negative. | [postflop](report-postflop-made-hand.md) |
| 4 | **Bet with one good board** | Bet when we have top pair or better on either board; always bet two pair or trips on one board. | We bet top pair/air 9% and trips/air 32%. In every hand class, betting beats checking by 0.4–0.9. | [postflop](report-postflop-made-hand.md) |
| 5 | **Raise strong hands, fold weak pairs, facing a bet** | Raise with trips+ on one board and top pair+ on the other. Fold low pair/low pair and low pair/air to flop bets. | We raise 0.3% of flop bets (top 5: 14%) and call 83% with low pairs on both boards at −1.98. | [postflop](report-postflop-made-hand.md), [round 2](report-round2.md) |
| 6 | **Short-stack shoves** | Small blind ≤10bb: shove everything. 10–20bb first in: shove or fold, no small raise. ≤5bb: never limp. | Small-blind folds cost 0.6–0.7 each; shoving junk earns +0.3. Our 10–20bb raises do worse than shoves with the same hand. | [postflop](report-postflop-made-hand.md), [round 1](report-round1.md) |
| 7 | **Heads-up big blind** | Reshove 10–25bb over a button raise with about the top half; re-raise deep instead of calling. | Top 5 reshove 50% and win 68% of heads-up matches; we win 40%. | [round 2](report-round2.md) |
| 8 | **Hand order** | Rank pairs 99 or lower below A/K/Q hands with a T+ second card for opening. Fold low pairs in early seats. | Low-pair opens lose 0.13–0.25 per hand; ace-with-T+ wins when opened but is folded 62% early. | [par ceiling](report-par-ceiling.md) |
| 9 | **Open size** | Open to 2.0bb at >20bb. | Our 2.0bb opens earn about double our 2.5bb opens in every seat for 3–5 points fewer folds. Top 5 use 2.0bb 53% of the time. | [postflop](report-postflop-made-hand.md) |
| 10 | **Opponent tag (if state persists across hands)** | Per seat, count calls and re-raises of raises. Callers: open wider into them, bet bigger, no bluffs. Re-raisers (15%+): tighten opens into their blind. | We win +5.5 bb/table from weak teams and lose 5.7 to mid/top; raising into a top team's big blind loses. | [farming](report-farming-practice6.md) |

Items 1–3 are frequency rules that need no new hand reading and account for most of the gap. I would ship 1 and 2 together first.

## Things that did not help (do not repeat)
- Wider button/small-blind opens by themselves (round 2): frequency now matches the top 5, result unchanged. The added hands earn the same as folding until items 1, 3 and 4 are in.
- Calling more from the big blind (round 2 low pairs, practice 6 at 54%): both made results worse.

## Open questions for Henry
- Which upload played round 2: the portal says `469e96f5` (74,862 B); `uploads/README.md` says v9.
- Not on GitHub: `469e96f5`, `f4025ac6` (45,312 B, played practice 6), `1b9ad55e` (73,996 B, active at the time of writing).
- Can the bot keep per-seat counters between hands at a table (item 10)?

## How to check a change
After any practice run, from the repo root:

```bash
python3.12 -I docs/research_notes/pittsburgh/scripts/an.py <hands.jsonl.gz> /tmp/agg.pkl
python3.12 -I docs/research_notes/pittsburgh/scripts/rep.py /tmp/agg.pkl      # standings, stages, heads-up, preflop
python3.12 -I docs/research_notes/pittsburgh/scripts/post.py <hands.jsonl.gz> # fold-to-bet, c-bet, busts
python3.12 -I docs/research_notes/pittsburgh/scripts/edge.py /tmp/edge.pkl <hands.jsonl.gz> && python3.12 -I docs/research_notes/pittsburgh/scripts/edgerep.py /tmp/edge.pkl
```

Numbers to watch: big-blind points per table (ours −7, top 5 −2 to −3), call vs re-raise share facing a raise, flop c-bet %, raise % facing a flop bet, stack when four players are left (ours 0.8× average, top 5 1.14×).

## Caveats that apply to all of it
Observational data from our own tables. Within a hand class we already choose the better hands to play, so per-item sizes are upper bounds; the direction is consistent across four runs. Top-five figures are their play at our tables.
