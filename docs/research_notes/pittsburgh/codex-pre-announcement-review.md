**The repo supports a competitive mini-simulator baseline, not validated settings for the real field.** I found confirmed equity errors and gaps in legality testing. No files were changed; no network calls, uploads, or key searches were made.

Local checks: build parity passed; 20,000 fuzz states passed, p99.9 **205 µs**, maximum **537 µs**. These checks do not cover all variant contracts.

The 13 settings are applied last at [core_agent.py:442](/Users/vedaant/pokerbot/tools/core_agent.py:442). **I found no isolated experiment establishing any exact value as optimal.** Whole-profile comparisons support the conservative package, but confound multiple changes: [eval-results/README.md:101](/Users/vedaant/pokerbot/eval-results/README.md:101).

| Knob | Evidence versus guess | Concern; real-field effect unverified |
|---|---|---|
| `open_size=2.3` | Exact value is a heuristic. | Reasonable starting point; optimal size depends on opponents’ calling/3-betting and variant equity realization. |
| `steal_widen=1.15` | Tracking has evidence: memory added **7 points against tight opponents**, but lost slightly in three other fields. Exact multiplier unverified. [Report:570](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:570) | Eight observations suffice to classify opponents; position and stack changes are ignored. |
| `steal_any=0.85` | Exploit works against scripted folders: 86% opens. Exact floor unverified. [Report:621](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:621) | **Potentially too aggressive** after a small sample: the same floor can authorize 85% shove ranges. [Core:584](/Users/vedaant/pokerbot/tools/core_agent.py:584) |
| `call_margin=0.05` | Conservative package supported; exact margin a guess. | **Likely too tight in combination** with range discount, callers/players-behind penalties, bubble margin and ICM. [Core:630](/Users/vedaant/pokerbot/tools/core_agent.py:630) |
| `bubble_margin=0.08` | ICM rationale supported; extra eight percentage points unverified. | Adds another premium atop calculated ICM. Also applies heads-up under winner-take-all, where no survival premium is warranted. [Core:520](/Users/vedaant/pokerbot/tools/core_agent.py:520), [Core:632](/Users/vedaant/pokerbot/tools/core_agent.py:632) |
| `semi_bluff=0.3` | Guess; no isolated frequency test found. | Frequency rests on faulty draw classification: board-only straight draws and already-made straights can qualify. [Core:1180](/Users/vedaant/pokerbot/tools/core_agent.py:1180) |
| `cbet_air=0.3` | Texture-sensitive betting observed; exact frequency unverified. [Report:413](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:413) | Only dry-flop aggression; does nothing about the observed **zero river bluffs**. [Core:732](/Users/vedaant/pokerbot/tools/core_agent.py:732), [Report:236](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:236) |
| `hu_open=0.65` | Guess; no isolated heads-up sweep. | Normally becomes **74.75%** through `points_widen=1.15`; this is not a literal 65% opening range. [Core:571](/Users/vedaant/pokerbot/tools/core_agent.py:571), [Core:605](/Users/vedaant/pokerbot/tools/core_agent.py:605) |
| `push_scale=0.9` | Package has favorable heads-up push/fold tests. [Report:465](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:465) | Multiway and variant transfer unverified. Under default payouts, heads-up widening makes the net multiplier **1.035**, before exploits. |
| `threebet=0.03` | Direct evidence of narrow play: approximately 3% versus CO opens. [Report:342](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:342) | **Likely too narrow against competent late-position openers**; lacks a blocker-based bluff range. The report’s reference ranges are not full-game solver output. |
| `call_raise=0.08` | Exact value a guess. | Because 3-bets execute first, this often means roughly **5% calls**, not 8%; separate closing-action exceptions apply. Likely underdefends small late-position raises. [Core:557](/Users/vedaant/pokerbot/tools/core_agent.py:557) |
| `points_tight=0.08` | Conservative package only. | **Most questionable fixed margin:** adds to `call_edge=0.12` even heads-up, making the threshold pot odds +20 percentage points. [Core:739](/Users/vedaant/pokerbot/tools/core_agent.py:739) |
| `icm_scale=1.0` | Strongest conceptual evidence; bubble probes approximately match exact ICM. [Report:985](/Users/vedaant/pokerbot/eval-results/bot-tests/README.md:985) | Implemented ICM ignores fourth-plus prizes and assumes a single opponent receives the pot after folding/losing. Full confidence in that approximation is unwarranted. [Core:783](/Users/vedaant/pokerbot/tools/core_agent.py:783), [Core:834](/Users/vedaant/pokerbot/tools/core_agent.py:834) |

For the six variants, showdown ranking and strategic equity estimation must be distinguished. A local comparison of **2,000 random seven-card hands** found no hold’em/short-deck ranking disagreement with the mini simulator’s five-card enumeration; that does not validate the equity heuristics.

| Variant | Findings |
|---|---|
| **holdem** | Preflop equities are measured against one random hand, then converted into ranges and discounted heuristically against raisers. **`final` uses `post="basic"`; calibrated buckets are bypassed.** [Core:116](/Users/vedaant/pokerbot/tools/core_agent.py:116), [Core:368](/Users/vedaant/pokerbot/tools/core_agent.py:368). Confirmed: a royal-flush board gets strength **0.30** and the bot folds a profitable guaranteed heads-up split. [Core:1130](/Users/vedaant/pokerbot/tools/core_agent.py:1130), [Core:747](/Users/vedaant/pokerbot/tools/core_agent.py:747). |
| **irish** | Discards two distinct indices correctly for the mock contract. Selection maximizes a coarse hold’em heuristic; post-discard equity ignores opponents having selected their best two of four, plus known dead discards. [Core:201](/Users/vedaant/pokerbot/tools/core_agent.py:201), [Core:310](/Users/vedaant/pokerbot/tools/core_agent.py:310). Preflop regression measures both players using this same discard policy, not optimal discarding. [Generator:119](/Users/vedaant/pokerbot/tools/gen_variant_tables.py:119). Unknown variant names route four-card preflop hands to **Omaha**. |
| **discard_reveal** | Selection indices match the mock rules. Preflop compresses three cards to their best hold’em pair; postflop uses ordinary hold’em strength. Revealed opponent cards and own discarded blockers are unused. Always revealing the lower card is an **unverified information-hiding heuristic**. [Core:130](/Users/vedaant/pokerbot/tools/core_agent.py:130), [Core:140](/Users/vedaant/pokerbot/tools/core_agent.py:140), [Core:314](/Users/vedaant/pokerbot/tools/core_agent.py:314). |
| **omaha** | Exactly-two-hole/three-board enumeration is correct by inspection. **Preflop scoring has a confirmed major error:** `As Ah Ad Ac` gets **81.1% equity, percentile 0**; a local 4,000-deal sample gave **52.9% ±0.8 percentage points SE**. Double-suited `As Ah Ks Kh` gets only 69.4%, versus sampled 71.0%. [Core:157](/Users/vedaant/pokerbot/tools/core_agent.py:157). Postflop collapses nut and weak hands into category averages; detects flush draws but **no straight/wrap draws**. [Core:182](/Users/vedaant/pokerbot/tools/core_agent.py:182). |
| **auction** | Three-hole-card best-five evaluation is implemented. Bid gains **0.10/0.06/0.03 are explicitly estimates**, not generated measurements; stack caps are heuristic. Opponents winning extra cards do not alter equity estimates. [Core:267](/Users/vedaant/pokerbot/tools/core_agent.py:267), [Core:1339](/Users/vedaant/pokerbot/tools/core_agent.py:1339). Unknown-name three-card winners route to `discard_reveal`, potentially missing hands requiring all three private cards. Second-price/tie rules remain speculative. |
| **short_deck** | Own 81-class table, A6789 straight and flush-over-full-house rankings are implemented. Postflop corrections average across streets; betting charts and raiser-range discount remain shared with hold’em. [Generator:98](/Users/vedaant/pokerbot/tools/gen_variant_tables.py:98), [Core:630](/Users/vedaant/pokerbot/tools/core_agent.py:630). Recognition requires the expected config name. Trips-over-straight or different deck rules are unsupported. [Core:326](/Users/vedaant/pokerbot/tools/core_agent.py:326). |

Robustness findings:

- **“Automatic” does not guarantee legal.** It returns the first kind/minimum with no card payload; `legal()` never validates selection indices. Unknown selection contracts can fail every decision. Both fuzz and gate miss payload validation. [Core:941](/Users/vedaant/pokerbot/tools/core_agent.py:941), [fuzz.py:273](/Users/vedaant/pokerbot/tools/fuzz.py:273), [gate.py:130](/Users/vedaant/pokerbot/skills/sequoia-launch/scripts/gate.py:130).
- **Malformed inputs usually cause silent check/fold, not outward crashes.** Invalid card encodings trigger rank lookups; missing state fields trigger attribute errors. Empty legal actions ultimately return an illegal `check`. Confirmed locally. [Core:64](/Users/vedaant/pokerbot/tools/core_agent.py:64), [Core:1081](/Users/vedaant/pokerbot/tools/core_agent.py:1081).
- **Memory ignores the configured limit.** Confirmed 30-byte output with an 8-byte limit; normal eight-seat output is 96 bytes, comfortably within the documented default. [Core:858](/Users/vedaant/pokerbot/tools/core_agent.py:858).
- **Timing tails remain exposed.** In 3,000 focused calls each, Omaha maximum was **1.181 ms**; Irish **1.837 ms**, p99.9 **0.976 ms**. These are local measurements, not kit results or proof of bank exhaustion. The bot never adjusts work to remaining bank; gate checks per-call tails, not cumulative bank consumption. [Core:175](/Users/vedaant/pokerbot/tools/core_agent.py:175), [Core:207](/Users/vedaant/pokerbot/tools/core_agent.py:207), [gate.py:205](/Users/vedaant/pokerbot/skills/sequoia-launch/scripts/gate.py:205).

My **top five risks**, ranked:

1. **Wrong variant/action contract silently passes local gates.**  
   Evidence: routing at [core_agent.py:337](/Users/vedaant/pokerbot/tools/core_agent.py:337); empty selections are explicitly accepted by the mock, potentially differently from the kit: [discard_reveal.md:107](/Users/vedaant/pokerbot/zoo/variants/discard_reveal.md:107).  
   **Why:** systematic wrong scoring or failed special decisions.  
   **Check:** once available, replay every real-kit phase through its actual validator; test renamed variants, four-card preflop states, three-card auction winners and mandatory card payloads.

2. **Equity compression produces confidently wrong decisions.**  
   Evidence: Omaha averaging [core_agent.py:163](/Users/vedaant/pokerbot/tools/core_agent.py:163); board-play strength [core_agent.py:1130](/Users/vedaant/pokerbot/tools/core_agent.py:1130).  
   **Why:** errors directly drive all-ins, folds and discards.  
   **Check:** reproduce the `AAAA` versus double-suited `AAKK` experiment; enumerate river equity for royal-board splits, paired boards and nut versus non-nut Omaha flushes. The first two failures are already confirmed.

3. **Payout handling and stacked margins overprice survival.**  
   Evidence: [core_agent.py:631](/Users/vedaant/pokerbot/tools/core_agent.py:631), [core_agent.py:789](/Users/vedaant/pokerbot/tools/core_agent.py:789).  
   **Why:** default heads-up overfolding; incorrect decisions under variable payouts. A confirmed four-player `(25,25,25,25)` fixture returns a **0.30 ICM premium despite guaranteed equal prizes**.  
   **Check:** compare fold/win/lose utilities with full ICM for winner-take-all, 50/30/20, four-place and flat payouts; separately disable each margin in memory.

4. **Tuning field rewards behavior that stronger bots can exploit.**  
   Evidence: seven league entrants share the core, [eval-results/README.md:28](/Users/vedaant/pokerbot/eval-results/README.md:28); exploiter advantages of 5–6 points in strong lineups, [STATE.md:112](/Users/vedaant/pokerbot/skills/STATE.md:112).  
   **Why:** aggregate weak-field wins conceal narrow defense, absent river bluffs and weak range adaptation.  
   **Check:** run `gauntlet.py zoo/claude_exploiter_1 --vs bots/final --mini --tables 1000 --seed review1`, repeat on `review2`, and inspect strong lineups separately. Use `PYTHONDONTWRITEBYTECODE=1` for read-only runs.

5. **Variant timing tails exhaust the bank or fail bankless testing.**  
   Evidence: focused overruns above; ordinary fuzz generates only two/three hole cards and no discard phase, [fuzz.py:217](/Users/vedaant/pokerbot/tools/fuzz.py:217).  
   **Why:** a passing hold’em fuzz run cannot establish Omaha/Irish latency safety.  
   **Check:** real-platform replay of Omaha rivers, Irish discards and maximum event batches; measure both bankless failures and cumulative `sum(max(0, elapsed_ms−1))` over complete tables against 100 ms.