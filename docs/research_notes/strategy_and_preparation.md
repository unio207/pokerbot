# Strategy and Preparation for a Time-Boxed Pokerbot Competition (Sequoia "No Limit", Nov 2026)

Researcher notes, compiled 2026-11-10. Sourcing legend used below:
- **[fetched]** = page was opened and read this session.
- **[snippet]** = seen only as a search-result summary; not opened.
- **[background]** = well-known paper/tool cited from prior knowledge; the URL was NOT re-fetched this session, so the report writer should treat specific numbers as needing a spot-check.

Headline for the writer: the Sequoia event is NOT an MIT-Pokerbots-style month-long heads-up contest. It is a 60-minute, Python-only build with a 1 ms per-decision limit, played as 8-bot sit-and-gos scored by finishing position, with the poker variant hidden until the build starts. That makes most "state of the art" poker AI (CFR blueprints, real-time search) unusable at runtime, and shifts the edge to preparation, precomputed tables, ICM-aware push/fold, robustness, and fast iteration with a coding agent.

---

## Q0. What variant and format does the Sequoia event use? (brief relevance check)

### Takeaway
"No Limit: A Bot Building Tournament" (Sequoia, with OpenAI and Citadel Securities) gives teams of 1-2 sixty minutes to build a Python bot that must answer in 1 ms, offline; scoring is 10,000 simulated eight-bot sit-and-gos across six tournaments weighted 1x to 6x, and the exact poker variant is confidential until the build phase begins. As of today (Nov 10) applications are closed, two regionals have run, Pittsburgh is Nov 12, and the finals are Nov 15.

### Cited Findings
- Official rules, variant: "The poker variant will be revealed on the day of each event at the start of the build phase." (§3.2) — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Table format: "10,000 simulated eight-bot sit-and-gos" (§4.3); "Each bot starts with 2,000 chips"; "Blinds start at 10/20 and increase every 25 hands"; "Each table plays until one bot holds all the chips or 200 hands have been played." (§4.4) — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Build and language: "Teams have 60 minutes to build a Python bot that implements the provided Agent interface." (§3.3). Starter kit contains "an agent template, local simulator, Independent Chip Model (ICM) calculator, payout structure, and blind schedule." — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Runtime limits: "Each bot must return a decision within one millisecond." On error or timeout the bot folds, or checks if checking is available (§3.7). "The maximum file size is 100mb." Bot state resets at the start of each table (§3.8). Memory limit not specified in the rules. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Sandbox: "Submitted bots run in isolated sandboxes without network access." "They cannot call OpenAI tools, external APIs, or any other outside service to make gameplay decisions." (§3.6) — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- AI tools: "Teams may use Astra and Codex to write, debug, and refine their bots during the build phase." "Publicly available documentation is permitted." (§3.4). Participants "must review and test AI-generated code." (§7.4) — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Submission cadence: "Each team may submit one bot every five minutes." (§3.5). Six scored tournaments T1-T6; T1 starts at the end of the build phase and later ones start "20 minutes apart" (§4.1). — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Scoring: a team's score is its average points per table; points are awarded by finishing position and "may vary by poker variant" (§4.5); "Final score = (T1 score × 1) + (T2 score × 2) + ... + (T6 score × 6)" (§4.7). — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Development continues after the first hour through T6, and the most recently accepted submission is the active entry; opponents are anonymous. — [Zeniteq article, fetched](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef)
- Dates: Menlo Park Fri Nov 6; Cambridge MA Mon Nov 9; Pittsburgh Thu Nov 12; Finals San Francisco Sun Nov 15, invitation only. Regionals run 6:00-9:00 PM local, check-in 5:30 PM. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Prizes: top 5 teams per regional get $5,000 per team and advance; up to five wildcard teams may also advance; Finals pay $100,000 / $50,000 / $25,000. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Eligibility: students "at any university in the United States and Canada" plus classes of 2025/2026; teams of one or two; free. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html). Note: several secondary write-ups say "U.S. universities" only — [Digg, fetched](https://digg.com/ai/smdduv3c).
- The landing page shows "NO-LIMIT HOLD'EM" imagery (blinds 50/100, an exhibit with eight-bot tables and another with a 10,000-hand heads-up match) and states "APPLICATIONS ARE NOW CLOSED." — [Event site, fetched](https://pokerbot.sequoiacap.com/)
- Sequoia's framing: "You don't need to be a poker pro, or even have any poker experience, to win No Limit. ... The starter kit handles the rules and the ICM math. You bring the creativity and strategy." — [Sequoia on X, snippet](https://x.com/sequoia/status/2117313159342268468)
- Noam Brown: MIT has run a 1-month pokerbot class (6.9630) and "Coding agents have accelerated that process so much that it's now possible to build a poker bot in an *hour*. Also, I'll be at the finals!" — [Noam Brown on X, snippet](https://x.com/polynoamial/status/2115125429619343609)
- Shaun Maguire (Sequoia) promised "rules for the age of AI" and "some plot twists." — [X, snippet](https://x.com/shaunmmaguire/status/2115131879452295182)
- UNOFFICIAL, secondhand: a participant's mock-engine repo says the SF/Bay Area regional game was "Discard & Reveal" ("as described by its winner", who is unnamed): 3 hole cards; each player discards one face down, keeps one hidden, turns one face up; the face-up card still plays. The repo author says the timing of the discard step is unconfirmed. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)
- UNOFFICIAL: another participant's overview says "The Finals use a different variant" and that pre-event points/blind tables were placeholders (he assumed 100/60/40/25/15/10/5/0); that author rehearsed pot-limit and "flush beats full house" variants. — [EthanXu07/poker-bot-overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- UNOFFICIAL SDK details from the same mock repo: `act(self, state, memory) -> (Action, bytes)`, 64 KB per-table memory, 1 ms per decision "plus a 100 ms per-table bank"; illegal raises are not clamped (they become check/fold); variant hooks `discard(obs)`, `reveal(obs)`, `bid(obs)`; the kit ships `AGENTS.md`/`CLAUDE.md`, example bots (`check_or_fold`, `min_raiser`), a `poker-agent` CLI (`play`, `check`, `pack`) and sample hand histories. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)

### Inferences
- Expect a hold'em-family game with a twist (extra hole cards, discards, changed hand rankings, different betting limit, possibly an auction/`bid` step) rather than plain NLHE. The variant may differ per regional and reportedly differs at the Finals. Anything prepared must be variant-agnostic or regenerable in minutes.
- The escalating weights (1 through 6, total 21) mean T4-T6 carry 15/21 = about 71% of the score. A team that ships a safe bot for T1 and keeps improving for another roughly 100 minutes is advantaged over one that polishes for 60 minutes and stops.
- Because scoring is by finishing place in an 8-player sit-and-go and not by chips won, tournament survival logic (ICM) matters more than chip-EV poker theory.

### Gaps
- No official statement of the variant used at any regional, the official points table, or whether pre-written code/tables may be brought in (the rules say "from scratch" in marketing but the fetched rules text is silent; the only explicit bans are copying another team's code and live AI gameplay decisions). Confirm with pokerbot@sequoiacap.com or on-site.
- "Astra" is named alongside Codex as a permitted tool; I did not confirm what it is or whether other assistants (e.g. Claude Code, Cursor) are allowed. The starter kit reportedly containing a `CLAUDE.md` is from an unofficial mock repo and proves nothing.
- No published regional results or winner post-mortems were found as of Nov 10.
- Memory limit, Python version, and whether third-party packages (numpy, eval7) are importable in the sandbox are unconfirmed. One participant shipped a single standard-library-only file, which is the safe assumption.

---

## Q1. Main algorithmic approaches, and which are realistic under tight time limits

### Takeaway
The research frontier (CFR blueprints + real-time subgame solving) needs days of compute and seconds per decision, so under 1 ms in Python it is out of reach at runtime; what is realistic is a precomputed-table, rule/threshold bot: equity lookups, pot-odds/EV comparisons, stack-depth-aware push/fold, ICM adjustment, and light opponent statistics. With weeks and a looser clock (MIT-style), tabular CFR/MCCFR on an abstracted game becomes the standard winning recipe.

### Cited Findings

Ladder of approaches (simple to state of the art):

- **Hand-strength / equity heuristics + pot odds.** A participant in the Sequoia event built an interpretable three-tree bot (stack tree, hand tree, opponent tree) where "each decision uses equity lookup tables and EV comparisons of fold, check, call, and raise, then picks the highest risk-adjusted utility"; equity-based hand ranking beat the older Chen-formula ordering (43.5 vs 40.9 points per table in his tests). — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- **Monte Carlo rollouts at decision time.** Under the Sequoia limit, "Monte Carlo bots often use their full 1 ms and get cut off, so they mostly check or fold"; the workable alternative was to precompute equity tables offline. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots). Independently: "Live Monte Carlo refinement gave no reliable gain and risked the time limit, so it was dropped." — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- **CFR family.** CFR iteratively minimizes counterfactual regret and converges to Nash equilibrium in two-player zero-sum games; CFR+ was used to essentially solve heads-up limit hold'em (Cepheus). — [Bowling et al., Science 2015, background](https://www.science.org/doi/10.1126/science.1259433). MCCFR samples parts of the tree per iteration so it scales to larger games. — [Lanctot et al., NeurIPS 2009, background](https://papers.nips.cc/paper/2009/hash/00411460f7c92d2124a67ea0f4cb5f85-Abstract.html). Deep CFR replaces the tabular regret store with neural networks, removing the need for hand-built abstraction. — [Brown et al., arXiv 1811.00164, background](https://arxiv.org/abs/1811.00164)
- **Card and bet abstraction.** The MIT Pokerbots 2017 winner's public repo states the bot was trained with CFR and that the code covers "abstracting the state space" and "dealing with off tree errors", with a helper that precomputes hand bucketing and discard logic (that year's variant included discards). — [Fro116/Pokerbots, fetched](https://github.com/Fro116/Pokerbots)
- **Real-time subgame solving / search.** Libratus combined an abstracted blueprint, nested safe subgame solving, and a self-improver, and beat four top professionals over 120,000 hands of heads-up no-limit. — [Brown & Sandholm, Science 2018, background](https://www.science.org/doi/10.1126/science.aao1733). Pluribus extended this to six-player NLHE with an MCCFR blueprint plus depth-limited search; the paper reports the blueprint was computed in about 8 days on a 64-core server and that it plays at roughly 20 seconds per hand on two CPUs. — [Brown & Sandholm, Science 2019, background](https://www.science.org/doi/10.1126/science.aay2400). DeepStack uses continual re-solving with learned counterfactual value networks. — [Moravcik et al., arXiv 1701.01724, background](https://arxiv.org/abs/1701.01724). ReBeL generalizes self-play RL + search to imperfect-information games via public belief states. — [Brown et al., arXiv 2007.13544, background](https://arxiv.org/abs/2007.13544)
- Commercial state of the art works the same way: "GTO Wizard AI considers each particular situation as it arises during play and solves it in real-time"; it beat Slumbot by 19.4 ± 4.1 bb/100 over 150,000 hands. — [PokerNews, fetched](https://www.pokernews.com/news/2026/04/gto-wizard-ai-outperforms-gpt-5-and-grok-4-in-new-benchmark-51020.htm); [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- **Opponent modeling / exploitation.** In the Sequoia format, bot state resets each table and opponents are anonymous, so modeling is limited to within one table (at most 200 hands). — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html); [Zeniteq, fetched](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef). One participant's in-table "opponent tree" used VPIP-based safety labels, style labels and bluff detection, but he reported it mis-read purely random opponents (kept only about 55% of chips heads-up vs random play, treating random raises as strength) and noted the simulator gave no showdown cards to learn from. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- A former MIT Pokerbots competitor described the non-CFR route: tracking opponent statistics to "mold our aggression and looseness to counter theirs", avoiding large lookup tables in favour of opponent tendencies plus hand equity. — [jlrubin MIT page, snippet](https://www.mit.edu/~jlrubin/projects/pokerbots)
- **Tournament (ICM) layer.** Standard Nash push/fold charts assume chip EV, and real tournament play needs ICM adjustment, most strongly near the bubble and payout jumps. — [ICMIZER blog, snippet](https://icmizer.com/en/blog/nash-calculator-and-nash-equilibrium-strategy-in-poker); [Deuces Cracked push/fold guide, snippet](https://www.deucescracked.com/blog/push-fold-poker-strategy-short-stack-tournaments-2026). ICMIZER's author cautions that in hard multiway spots exact equilibria are only approximated. — [ICMIZER, snippet](https://icmizer.com/en/blog/analysis-of-difficult-sng-push-fold-spots)
- Format-specific finding: with a top-heavy points table "finishing first matters more than finishing high"; an early version that folded about 77% of hands preflop "often finished second but rarely first" until it got endgame-specific logic (seat-position range gate, wider blind defense, near-zero risk aversion heads-up). — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- **Parameter search instead of game solving.** The same participant tuned 49 thresholds with an evolution strategy that plays full tournaments and optimizes the exact competition score, alternating three opponent environments and accepting a candidate only if it beat the incumbent by more than 1.5 standard errors and then won again on a fresh batch. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)

Feasibility table (my synthesis; variant dependence labelled):

| Technique | 60-min build, 1 ms Python (Sequoia) | Multi-week, ~seconds per hand (MIT-style) | Variant dependent? |
|---|---|---|---|
| Legal-action-safe baseline (check/fold, min-raise) | Minutes; ship first | Day 1 | No |
| Preflop hand tiers / precomputed equity table | Yes, core | Yes | Yes: tables must be regenerated per variant |
| Pot odds + EV thresholds postflop | Yes | Yes | Mostly no |
| Live Monte Carlo equity | No (reported to blow the 1 ms limit) | Yes, common | Evaluator must match variant |
| Push/fold by stack depth, ICM-adjusted | Yes; high value in SNG scoring | Only if tournament-scored | Depends on payout table, not on cards |
| In-table opponent stats (VPIP, aggression) | Yes if O(1) updates | Yes, cross-match | No |
| Evolutionary / black-box threshold tuning in local sim | Yes, if harness is ready | Yes | Re-run per variant |
| Tabular CFR/MCCFR on abstracted game | Not in the hour; only as a pre-baked table if rules were known | Standard winning approach heads-up | Yes, fully |
| Deep CFR / ReBeL / subgame solving | No | Rarely worth it for students | Yes |

### Inferences
- In an 8-player field of hastily built bots, the opposition is far from equilibrium. A robust, slightly tight-aggressive, ICM-aware bot that never errors probably beats most of the field; exploitability is a minor concern compared with crashes and passivity. (Equilibrium theory also gives no guarantee in 8-player games; Pluribus's approach was empirical.)
- The 1 ms limit in Python means each decision is essentially dictionary/array lookups plus a few arithmetic operations. Design the data so that a decision is: canonicalize hand -> table lookup -> compare to a threshold chosen by (stack in big blinds, players left, position, facing action).
- Precompute offline whatever can be precomputed: equity vs N random hands for every canonical starting hand, made-hand/draw classes, push/fold thresholds by stack depth and players remaining. With a hidden variant, the valuable asset is not the table itself but a generator script that rebuilds the table for a new rule set in a few minutes.
- A coding-agent-driven tuning loop (simulate, measure, adjust thresholds) is the practical substitute for solving the game.

### Gaps
- No source quantifies how much ICM-aware push/fold adds versus a chip-EV bot in this exact structure (2,000 chips, 10/20 blinds rising every 25 hands, 200-hand cap). It must be measured in the local simulator.
- Whether hand-evaluation of 7+ cards fits in 1 ms in pure Python for the revealed variant is untested here; participants report solving it with lookup tables.
- I did not re-fetch the classic papers this session; compute/time figures for Libratus/Pluribus are from background knowledge.

---

## Q2. Open-source tools and libraries

### Takeaway
For a research-grade or MIT-style bot, OpenSpiel, PokerRL, RLCard, fast hand evaluators and open postflop solvers are the standard kit; for the Sequoia event most of them are useful only before the event (to generate tables and sparring bots), since the sandbox is offline, Python-only and the safe assumption is standard library only.

### Cited Findings
- **Event-specific:** the official starter kit has an agent template, local simulator, ICM calculator, payout structure and blind schedule. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- **Unofficial rehearsal engine:** aniketxdey/pokerbots is a local mock of the tournament with a sit-and-go engine covering 45 poker variants, a tournament runner using the published scoring rules, 42 ported open-source bots, and a web UI; pure standard library apart from Flask for the UI. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots). A "Poker Gym rehearsal simulator with its sparring bots" is also mentioned by another participant (origin not confirmed). — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- **OpenSpiel** (DeepMind): game framework with CFR, CFR+, MCCFR, Deep CFR, NFSP implementations and small poker games (Kuhn, Leduc) plus universal poker via the ACPC engine. — [OpenSpiel GitHub, background](https://github.com/google-deepmind/open_spiel)
- **PokerRL**: framework for deep RL in poker (Deep CFR / SD-CFR, NFSP) with distributed training. — [PokerRL GitHub, background](https://github.com/EricSteinberger/PokerRL)
- **RLCard**: RL toolkit for card games including Leduc, limit and no-limit hold'em, with DQN/NFSP/CFR baselines. — [RLCard GitHub, background](https://github.com/datamllab/rlcard)
- **Hand evaluators:** eval7 (Python/Cython evaluator with equity and range tools) — [PyPI, background](https://pypi.org/project/eval7/); treys (pure-Python port of Deuces) — [treys GitHub, background](https://github.com/ihendley/treys); PokerHandEvaluator / phevaluator (perfect-hash 5-7 card evaluator, C/C++/Python) — [GitHub, background](https://github.com/HenryRLee/PokerHandEvaluator)
- **Open-source solvers:** TexasSolver (C++ postflop solver) — [GitHub, background](https://github.com/bupticybee/TexasSolver); postflop-solver (Rust) — [GitHub, background](https://github.com/b-inary/postflop-solver)
- **Benchmark opponents:** Slumbot offers a public heads-up NLHE bot/API (sample client in the author's repo) — [Slumbot, background](https://www.slumbot.com/). GTO Wizard Benchmark is a public HUNL API (ACPC rules, 50/100 blinds, 200 bb stacks reset each hand) that reports AIVAT-adjusted bb/100. — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- **Reference code from past winners:** MIT Pokerbots 2017 winning bot (Java player, C++ helper for bucketing/discards, strategy `report.pdf`). — [Fro116/Pokerbots, fetched](https://github.com/Fro116/Pokerbots). MIT Pokerbots organization publishes engines and reference bots. — [MIT Pokerbots, background](https://pokerbots.org/)
- **Theory primer:** MIT OCW 15.S50 lecture on game theory covers regret minimization, CFR and CFR+. — [MIT OCW, snippet](https://live.ocw.mit.edu/courses/15-s50-poker-theory-and-analytics-january-iap-2015/de12f68318d55abed783652357da6a5f_MIT15_S50IAP15_L7_GameTheor.pdf)
- **ICM / push-fold references:** Nash push/fold range charts — [PokerStrategy.com, snippet](https://www.pokerstrategy.com/strategy/sit-and-go/1779/); ICMIZER (commercial Nash/ICM calculator) — [ICMIZER, snippet](https://icmizer.com/en/blog/nash-calculator-and-nash-equilibrium-strategy-in-poker)

### Inferences
- Heads-up benchmarks (Slumbot, GTO Wizard) measure a different game from an 8-bot sit-and-go and are a poor proxy for Sequoia performance; a diverse pool of local sparring bots in the official simulator is the relevant benchmark.
- Use eval7/phevaluator offline to generate equity tables, then serialize them into a plain Python dict/tuple literal or a small data file inside the 100 MB cap. Check import/load time separately from the 1 ms per-decision budget.
- A team that arrives with its own variant-parameterized simulator, table generator and tournament harness has in effect extended the 60 minutes, if bringing such code is allowed (unconfirmed).

### Gaps
- Not confirmed whether the sandbox permits numpy or any third-party package, or what load-time budget applies.
- I did not verify current maintenance status of PokerRL, treys or the open solvers this session.
- The quality and licensing of the "42 ported open-source bots" in the mock repo were not examined.

---

## Q3. What winners of comparable contests said worked, and common mistakes

### Takeaway
In month-long heads-up contests (MIT Pokerbots, ACPC) winners converge on CFR over an abstracted game with careful off-tree handling; in the Sequoia-style speed format the documented lessons are different: precompute, never time out or act illegally, tune against a diverse field on the true scoring function, and play to win tables outright rather than to survive.

### Cited Findings
- MIT Pokerbots 2017 winner: CFR-trained bot; repo emphasizes state-space abstraction, off-tree error handling, precomputed bucketing and discard logic, plus opponent-move interpretation and state tracking. — [Fro116/Pokerbots, fetched](https://github.com/Fro116/Pokerbots)
- MIT competitor (non-CFR): statistics tracking of the opponent and adapting aggression/looseness; hand equity over big lookup tables. — [jlrubin MIT page, snippet](https://www.mit.edu/~jlrubin/projects/pokerbots)
- 2021 MIT participant: reported win rate above 50% and above-average ELO, and added randomization so the strategy would not be easily predicted. — [ngnnah/python_AutonomousPokerbot, snippet](https://github.com/ngnnah/python_AutonomousPokerbot)
- Sequoia-format participant results (self-reported, simulated, not regional outcomes): weighted scores 47.3-52.6 against three opponent fields where an average bot scores 31.9 (95% CI about ±0.6); +10.2 points per table against a tight-aggressive reference; heads-up endgames won 60-63%; "zero errors and zero illegal actions"; decisions over 1 ms in 1 of 283,227 cases under heavy machine load; bot was a single standard-library Python file of about 165 KB. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- Same author's lessons: (1) first place matters more than placing high, so build endgame play; (2) equity-based ranking beats Chen formula; (3) "training on diverse opponents, including naive bots, helped robustness"; (4) drop live Monte Carlo; (5) keep about 10 minutes of retraining available for when official rules are announced. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- Another participant's simulated "SF Contender" (precomputed equity tables for the discard-and-reveal variant) averaged 36.4 points per table versus a field average of 12.5 with 70.6% first places; best ported open-source bot scored 17.6 in the same seats. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)

Common failure modes with evidence:
- **Timeouts:** Monte Carlo bots get cut off at 1 ms and effectively check/fold; running more worker processes than cores, or other machine load, causes timing failures in local tests. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)
- **Illegal actions:** in the SDK as mocked, illegal raises are not clamped; a timeout, exception or illegal action becomes check-else-fold. — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots); official rule on errors/timeouts — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- **Variant brittleness:** "Hold'em-only bots often error or fold in other variants, so testing across variants is useful." — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)
- **Over-tight play:** folding about 77% preflop produced many second places and few wins. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- **Overfitting to sparring opponents / misreading randomness:** opponent model treated random raises as strength; mitigated by alternating several opponent environments and holding out validation tables. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- **Variance misreads:** see Q4; the Claudico match loss of over 9 bb/100 was only on the edge of statistical significance. — [AIVAT paper, snippet](https://ar5iv.arxiv.org/html/1612.06915)
- **Unreviewed AI-generated code:** the rules put the burden on participants to review and test AI-generated code. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- **Plain LLM poker instincts are unbalanced:** frontier LLMs misread about 2% of their own holdings and produced unbalanced preflop ranges (3-betting only the strongest hands, calling almost everything else). — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)

### Inferences
- A defensive wrapper is the highest-leverage ten lines in the bot: wrap `act` in try/except returning check-else-fold; clamp every raise to the legal min/max supplied in the state; never loop over unknown-length structures; avoid any per-decision allocation-heavy code; do expensive setup at import or `new_table`, not in `act`.
- Test timing on a loaded machine and target a large safety margin (for example a median far below 100 microseconds), since the organizer's sandbox hardware is unknown.
- Submit a working bot early (well before minute 60) because a late broken submission costs T1, and later tournaments allow recovery; but never replace a working bot with an untested one just before T5/T6, which carry the most weight.
- With a 5-minute submission cooldown and 20-minute gaps, there are at most about 4 submission slots between tournaments; plan a fixed loop of change, 2-3 minute local evaluation, submit.

### Gaps
- No write-ups from actual Sequoia regional qualifiers or winners were found; the two participant repos report simulated results only.
- I found no post-mortems from CMU or trading-firm-sponsored pokerbot events (e.g. Jane Street/HRT/Citadel-style campus contests) in this session's searches; no claims are made about them.
- ACPC winner methodology (Slumbot, Baby Tartanian, etc.) was not researched in detail this session beyond the search-result pointer to a 2016 PokerNews report — [PokerNews 2016, snippet](https://www.pokernews.com/strategy/poker-ai-2016-annual-computer-poker-competition-24246.htm).
- The MIT 2017 `report.pdf` was not opened, so the specific abstraction and off-tree translation method are not documented here.

---

## Q4. Evaluation under high variance

### Takeaway
Poker results are noisy enough that small samples mislead; use the competition's own metric (average points per table in 8-bot sit-and-gos) with standard errors, common random numbers/seat rotation, and acceptance rules based on standard errors. bb/100, duplicate matches and AIVAT are the standard tools for cash-game heads-up evaluation but map only partly onto a placement-scored tournament.

### Cited Findings
- AIVAT is an unbiased low-variance estimator that extends control variates to chance events and to the known strategy of one agent; in no-limit poker it can cut the hands needed for statistical conclusions by more than a factor of 10. — [Burch et al., AAAI 2018 / arXiv 1612.06915, snippet](https://www.arxiv.org/pdf/1612.06915)
- Illustration of raw variance: Claudico lost to humans by over 9 bb/100, "a margin that is considered huge by poker professionals", yet the result was only on the edge of statistical significance. — [AIVAT paper, snippet](https://ar5iv.arxiv.org/html/1612.06915)
- GTO Wizard Benchmark: AIVAT gives about a threefold reduction in standard deviation, equal to roughly 10 times less data; each LLM played 5,000 hands, giving results such as -16 ± 3 bb/100; strong human professionals win around 5 bb/100. — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- Beating Slumbot by 19.4 bb/100 was reported with a ±4.1 interval even after 150,000 hands. — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- Sequoia-format numbers: "100-500 iterations per round is enough to rank bots. Standard error is roughly 20/√iterations points" (iterations = tables, under that repo's points scale). — [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)
- Sequoia scoring itself averages over 10,000 tables, so official results are much less noisy than a short local test. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Practical acceptance rule used by a participant: promote a candidate only if it beats the incumbent by more than 1.5 standard errors and then wins again on a fresh batch; validate on held-out tables; reported 95% CI about ±0.6 points. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview)
- Husky Hold'em (NeurIPS 2025) averages results over several trials to reduce variance in its 6-player round-robin. — [NeurIPS 2025 page, fetched](https://neurips.cc/virtual/2025/122372)

### Inferences
- Using the cited 20/√n rule: 100 tables gives SE of about 2 points, 400 tables about 1 point, 1,600 tables about 0.5 points. Detecting a 1-point improvement at roughly 2 SE needs on the order of 1,600+ tables per arm unless variance is reduced. (Arithmetic on the cited rule; the constant depends on the points table.)
- Cheap variance reduction for A/B tests in a simulator: same seeds/decks for both versions (common random numbers), rotate the candidate through all eight seats, and keep the opponent pool fixed. This is the multi-player analogue of duplicate matches.
- Simulator throughput is therefore a competitive asset: tables per second determines how many ideas can be tested in a 20-minute gap. Profile the harness beforehand and run across all cores (but not more workers than cores, per the timing warning above).
- Report results as points per table with SE, and track first-place rate and bust-position distribution separately, since the score is placement-driven. bb/100 is not the right objective here.
- Do not conclude anything from watching a handful of tables or from a single T1 result; T1 is one draw of a 10,000-table average against an unknown field whose composition changes as others resubmit.

### Gaps
- No source gave a per-hand standard deviation for NLHE this session, so no "hands needed" formula is cited; the usual rule (required hands scale with (SD/edge)^2) is stated here as general statistics, not a sourced poker figure.
- AIVAT requires a value function and known agent strategy and has no off-the-shelf implementation for 8-player ICM-scored games that I could find.
- How the organizer seats bots (random tables across the whole field vs pools) and whether self-play copies can share a table is unconfirmed.

---

## Q5. LLM-based poker agents vs solver/CFR bots; role of AI coding assistants

### Takeaway
As players, frontier LLMs in 2026 still lose clearly to a real-time solver (best about -16 bb/100 against GTO Wizard AI) though they have improved fast and tool-using or skill-augmented variants narrow the gap; in the Sequoia event LLMs cannot play at all (offline, 1 ms), so their role is as coding agents, where evidence shows they can produce competitive bots quickly but need human review, testing and strategic direction.

### Cited Findings
- GTO Wizard Benchmark (paper March 2026; 5,000 hands per model, zero-shot, no tools, AIVAT-adjusted bb/100 vs GTO Wizard AI): GPT-5.3 extra-high reasoning -16 (±3); GPT-5.4 extra-high -17.8; GPT-5.3 high -18.2; Claude Opus 4.6 -20.4; Claude Opus 4.5 -22.3; Gemini 3.1 Pro -30.8; Grok 4 -60; GPT-4o about -65; GPT-4 -136.2. Baselines: Always Fold -64.6, Check-Call -241.1, Uniform Random -284.9, All-In -380.6. "All models remain far below the baseline established by our benchmark." — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- Caveats on that source: the benchmark is run by the vendor of the opponent, and the paper's two tables disagree on a few values (e.g. GPT-4o -64.9 vs -60.9). — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660); [PokerNews, fetched](https://www.pokernews.com/news/2026/04/gto-wizard-ai-outperforms-gpt-5-and-grok-4-in-new-benchmark-51020.htm)
- Note that several mid-tier LLMs did about as badly as, or worse than, folding every hand (-64.6). — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- Diagnosed weaknesses: card/suit misreads (about 2% of holdings for the best model), unbalanced ranges with little mixing, predictable and exploitable play. — [GTO Wizard Benchmark paper, fetched](https://arxiv.org/html/2603.23660)
- ToolPoker (arXiv 2602.00528, early 2026): an LLM that calls a CFR solver as a tool loses only slightly to equilibrium baselines (about -3 chips vs CFR+ in Leduc, -5 vs Deep CFR in limit hold'em) and beats NFSP/DQN/DMC. — [alphaXiv overview, snippet](https://www.alphaxiv.org/overview/2602.00528)
- PokerSkill (arXiv 2605.30094, mid-2026 preprint): authors report Claude Opus 4.7 with their skill layer lost about 87 mbb/hand to GTO Wizard's HUNL agent versus about 194 mbb/hand for Slumbot, with no solver calls at inference; default-prompted LLMs were far weaker. Preprint, numbers not checked against the full paper. — [arXiv 2605.30094, snippet](https://arxiv.org/html/2605.30094v1)
- SpinGPT (2025): fine-tuned LLM for 3-handed Spin & Go matching solver actions in 78% of decisions under a tolerant metric. — [arXiv 2509.22387, snippet](https://arxiv.org/pdf/2509.22387)
- Publicity LLM-vs-LLM event (late 2025): OpenAI's o3 won a multi-model poker "bot battle", Grok third. — [PokerNews, snippet](https://www.pokernews.com/news/2025/11/poker-bot-battle-results-49971.htm)
- LLMs as bot builders: Husky Hold'em Bench (NeurIPS 2025) has LLMs write poker bots through a 5-stage iterative refinement scaffold, then plays them in 6-player round-robins; Claude 4 Sonnet topped the leaderboard; top models produced balanced or aggressive bots while lower-ranked models produced more defensive ones. — [NeurIPS 2025 page, fetched](https://neurips.cc/virtual/2025/122372)
- The Sequoia event is premised on this: Noam Brown says coding agents make it "possible to build a poker bot in an *hour*". — [X, snippet](https://x.com/polynoamial/status/2115125429619343609). The rules allow Astra and Codex in the build phase, ban live AI gameplay decisions, and require participants to review and test generated code. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)

### Inferences
- Do not ask the coding agent to "play good poker from intuition": the benchmark evidence says LLM poker instincts are passive-calling and unbalanced, and Husky Hold'em says weaker LLM-built bots skew defensive, which is exactly the failure (too many folds, few first places) one Sequoia participant had to fix. Give the agent an explicit architecture and let measured simulator results, not the model's opinions, decide thresholds.
- Best use of the assistant in a 60-minute build: (a) read the variant rules and starter kit and enumerate rule edge cases; (b) write the hand evaluator/equity-table generator for the revealed variant; (c) write the defensive wrapper and legality checks; (d) run the tuning/evaluation harness in parallel while the human decides strategy; (e) profile timing.
- With two people, one agent session per person on separate concerns (bot logic vs evaluation harness/tuning) avoids merge thrash; agree the interface between them in the first five minutes.
- Prepare agent instructions in advance (a prompt/spec file describing architecture, constraints of 1 ms, stdlib only, check-else-fold fallback, test commands), since typing a good spec is slow and the clock is the binding constraint.

### Gaps
- No public data yet on how AI-built bots performed in the Sequoia regionals or which assistant/workflow winners used.
- "Astra" was not identified; whether non-OpenAI assistants are permitted on-site is unconfirmed.
- The LLM benchmark numbers are heads-up NLHE vs a solver and do not transfer directly to 8-player tournament play.

---

## Q6. Preparation plan and team skill mix

### Takeaway
For the Sequoia format, preparation is about rehearsing a 60-minute pipeline and arriving with variant-agnostic tooling and knowledge, not about training a strong poker AI; for a conventional multi-week contest, a four-to-five-week arc from legal baseline to abstraction + CFR to hardening is the pattern past winners followed. This whole section is my synthesis from the findings above, not a sourced schedule.

### Cited Findings
- Timeline facts that constrain any plan: applications are closed; remaining events are Pittsburgh (Nov 12) and the invitation-only Finals (Nov 15); regionals last three hours with a 60-minute build then T1-T6 at 20-minute spacing, submissions at most every 5 minutes. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html); [Event site, fetched](https://pokerbot.sequoiacap.com/)
- Team size is capped at two. — [Official Rules, fetched](https://pokerbot.sequoiacap.com/rules.html)
- Participants who prepared publicly built their own tournament engine, rehearsed multiple variants (pot-limit, altered hand rankings, 45-variant mock engine), tuned on the exact score, and budgeted about 10 minutes to retrain once real rules appeared. — [EthanXu07 overview, fetched](https://github.com/EthanXu07/poker-bot-overview); [aniketxdey/pokerbots, fetched](https://github.com/aniketxdey/pokerbots)
- MIT's comparable course runs about one month. — [Noam Brown on X, snippet](https://x.com/polynoamial/status/2115125429619343609)

### Inferences

**A. Sequoia-style speed format (prepare over about 2-3 weeks, or compress to days)**

- Week 1, foundations: learn hold'em-family rules and common variants (Omaha, pineapple/crazy pineapple discards, short deck, pot-limit, altered rankings, stud-style up cards, auctions). Learn sit-and-go theory: effective stack in big blinds, push/fold, ICM, bubble and heads-up play. Read the official rules line by line. Build or adopt a mock engine with the published structure (8 players, 2,000 chips, 10/20 rising every 25 hands, 200-hand cap, placement points, ICM split at the cap).
- Week 2, tooling: write a variant-parameterized equity-table generator (hole-card count, discard rule, deck, ranking order) and time how long regeneration takes; write the tournament harness with seat rotation, fixed seeds, SE reporting and a pool of 8-15 sparring bots (calling station, maniac, nit, random, tight-aggressive, push/fold bot, copies of own earlier versions); write the defensive agent skeleton and a timing profiler; write the coding-agent spec file.
- Week 3, rehearsal: run at least 3-5 full timed mocks with a surprise variant chosen by someone else, including the post-build phase (five more 20-minute improvement cycles). After each, record where minutes went. Practice the tuning loop (threshold search with an SE-based acceptance rule).
- If only days remain: prioritize (1) defensive skeleton, (2) harness with SE output, (3) one timed mock on an unfamiliar variant, (4) push/fold + ICM cheat sheet.

Suggested event-day run sheet (all inference):
- 0-5 min: read variant rules aloud; list what changes (cards, rankings, betting limit, extra actions). Run the kit's example bots.
- 5-15 min: submit a legal, crash-proof baseline (tight-aggressive preflop tiers, check/fold fallback). Start table generation for the variant in the background.
- 15-40 min: equity lookup, pot-odds EV rule, stack-depth push/fold, endgame aggression when 2-3 players remain; legality clamps; timing check.
- 40-55 min: evaluate vs sparring pool over several hundred tables; tune the 3-5 most sensitive thresholds; submit the best measured version by about minute 50-55.
- T1-T6: each 20-minute gap is one hypothesis, one measured test, one submission only if it beats the incumbent by a clear margin. Freeze risky changes before T5 and T6 (weights 5 and 6).

**B. Conventional multi-week contest (MIT-style, seconds per hand)**

- Week 1: engine, legal baseline, hand evaluator, logging, local match runner; pot-odds/equity bot.
- Week 2: Monte Carlo equity with a time budget, opponent stat tracking, first card abstraction (equity buckets), solve toy games (Kuhn, Leduc) with CFR in OpenSpiel to validate understanding.
- Week 3: MCCFR on an abstracted version of the actual variant; bet abstraction and action translation for off-tree bets; store strategy compactly.
- Week 4: hardening (time bank management, illegal-action guards), evaluation at scale with duplicate matches, selective exploitation layered on the equilibrium core.
- Final days: freeze features, scrimmage widely, fix only bugs.

**Team skill mix (two people in the Sequoia format)**
- Person A, strategy/poker lead: knows tournament poker and ICM, specifies the decision architecture, reads the variant rules, decides what to test.
- Person B, engineering/evaluation lead: owns the simulator harness, statistics, timing, submission discipline and the coding-agent workflow.
- Both should be fluent in driving a coding agent and in Python performance basics. For a larger multi-week team add: game-theory/CFR implementer, systems/performance (C++/Rust) engineer, and a data/evaluation person.

### Gaps
- Whether any of this pre-built tooling may be brought into the room is unconfirmed; "from scratch" in the announcement may mean no prior code. If so, the value of preparation shifts entirely to rehearsed prompts/specs and knowledge, and the team should practice rebuilding the harness from a prompt in under 10 minutes.
- No source describes how regional qualifiers actually spent their 60 minutes.
- Whether Sequoia will run the event again (and with the same format) is unknown; the plan for future editions assumes a similar structure.
