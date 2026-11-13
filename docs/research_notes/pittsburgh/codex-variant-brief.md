**1. Unconverted `bots/final`: legal fallback behavior, but strategically wrong.**

| Situation | Actual path |
|---|---|
| Preflop, three cards | Unknown `double_board_turn_discard` falls through to `discard_reveal`: best two-card combination, then an equity fit calibrated for another variant. [agent.py:130](/Users/vedaant/pokerbot/bots/final/agent.py:130), [variant detection:309](/Users/vedaant/pokerbot/bots/final/agent.py:309) |
| Flop/turn betting, three cards | `holdem_postflop` evaluates each retained pair and takes the strongest **on board 1 only**. Draw flags are ORed across pairs. [agent.py:112](/Users/vedaant/pokerbot/bots/final/agent.py:112) |
| `phase == "discard"` | Detects `irish`; `irish_discard` sees three rather than four cards and calls `automatic`. Returns **`Action("discard", amount=1, cards=())`**. [agent.py:201](/Users/vedaant/pokerbot/bots/final/agent.py:201), [automatic:941](/Users/vedaant/pokerbot/bots/final/agent.py:941) |
| River, two cards | Falls back to `holdem`, still evaluating board 1 only. [agent.py:337](/Users/vedaant/pokerbot/bots/final/agent.py:337) |

**The empty discard is accepted, not rejected:** the engine discards the lowest-ranked card, breaking rank ties by card string. It does **not** attempt to discard two cards. [_double_board.py:200](/Users/vedaant/starter-kit/sdk/engine/src/poker_engine/variants/_double_board.py:200)

I reproduced these routes and the returned discard in memory; protocol legality passed. Betting actions pass through the existing legality wrapper. This establishes structural compatibility, not freedom from timeouts. [agent.py:51](/Users/vedaant/pokerbot/bots/final/agent.py:51), [legal:956](/Users/vedaant/pokerbot/bots/final/agent.py:956)

**2. Strategy**

- **Three-card starts:** more selection opportunities for everyone; ordinary hold’em equities cannot be carried over unchanged. **Computed combinatorially:** 17.18% of three-card deals contain a pair or trips, versus 5.88% pocket pairs in hold’em. These are deal frequencies, **not equities**.
- **Two boards:** expected pot share is **computed identity** \(E=(e_1+e_2)/2\), where each board’s equity includes fractional ties; ignore odd chips here. Board correlation does not change this identity, but matters for scoops and tournament risk. Do not estimate scoop probability as \(e_1e_2\) without an independence assumption.
- **Half-pot trap:** guaranteed outright victory on one board plus certain loss on the other means 50% pot share, not a guaranteed profitable stack-off. Tying one board while losing the other yields 25% in a heads-up pot.
- **Eight-handed guidance — qualitative estimates:** favor high pairs with useful third cards, high connected ranks, and suited ace combinations: `AAK`, `AAQ`, `KKQ`, `AKQ`, especially with a suited pair. Medium pairs plus connected/high support and suited broadway combinations improve in position. Discount low disconnected cards, weak offsuit aces and three-of-a-kind starts: one trip card must go, and it blocks a set out. Three cards of one suit provide selection but also consume a flush out.
- **Discard:** keep the **same pair** maximizing combined expected equity over both four-card boards, including river draws, ties and all known dead cards. Do not independently choose a different pair for each board. Discard still happens after early all-ins.

`RULES.md` contains no numeric `state.config` table. SDK defaults are eight players, 2,000 chips, blinds every 20 hands:
`10/20 → 20/40 → 30/60 → 50/100 → 80/160 → 125/250 → 200/400 → 300/600 → 500/1000 → 800/1600 → 1200/2400 → 2000/4000`; 250-hand cap, 50/30/20 payouts, 1 ms decisions, 100 ms bank, 64 KiB memory. **Actual `state.config` overrides defaults**, including payouts. [table.py:30](/Users/vedaant/starter-kit/sdk/engine/src/poker_engine/table.py:30)

**3. Smallest safe conversion in `core_agent.py`**

| Change | Location and recommendation |
|---|---|
| Dedicated variant entry | Add `double_board_turn_discard` **before** Irish detection in [VARIANTS:309](/Users/vedaant/pokerbot/tools/core_agent.py:309). Exact-name routing then works throughout; fallback detection can recognize two entries in `state.variant["boards"]`, including empty preflop boards. |
| Preflop scorer | Adapt [holdem_preflop:96](/Users/vedaant/pokerbot/tools/core_agent.py:96): score all three pairs; blend best and mean, e.g. `(max(scores)+mean(scores))/2`. **Estimate**, not calibrated equity. Rank these scores across three-card deals for percentile thresholds; do not reuse Irish/discard-reveal fitted equities as Pittsburgh results. |
| Two-board scorer | Adapt [holdem_postflop:112](/Users/vedaant/pokerbot/tools/core_agent.py:112) to evaluate both boards separately and average. Existing pair enumeration avoids treating a hand requiring all three hole cards as retainable. However, averaging each board’s independent best pair remains optimistic. **On the turn, prefer the maximum combined score of one common pair.** |
| Explicit one-card discard | Add a handler beside [irish_discard:201](/Users/vedaant/pokerbot/tools/core_agent.py:201): evaluate three kept pairs × two boards using [_made_strength:1115](/Users/vedaant/pokerbot/tools/core_agent.py:1115), retain the best combined pair, return `Action("discard", cards=(3-i-j,))`. Strengths remain estimates. |
| Betting safeguards | Review [postflop:705](/Users/vedaant/pokerbot/tools/core_agent.py:705): board-1-only dry-flop bluffing, the draw-only call override at line 749, and the `<0.75` large-call cutoff at line 747 all misprice split-pot situations. A one-board draw must not bypass combined pot odds. |

Keep [hand_rank:1075](/Users/vedaant/pokerbot/tools/core_agent.py:1075); no ranking-rule rewrite is needed. Do not average its ordinal rank tuples as equities.

[PROFILES:428](/Users/vedaant/pokerbot/tools/core_agent.py:428) is overridden by [SETTINGS:442](/Users/vedaant/pokerbot/tools/core_agent.py:442). Tune the effective settings. [_icm_me:783](/Users/vedaant/pokerbot/tools/core_agent.py:783) supports only three paid places; `_icm_premium` models win/lose outcomes, omitting split outcomes.

**1 ms risk:** six strength evaluations plus tracking/ICM need measurement; avoid runtime Monte Carlo. **Measured locally, unconverted bot, one turn fixture/2,000 calls:** median 80 µs, p99 88 µs, maximum 21.35 ms. This excludes process transport and does not benchmark the conversion.

**4. Top five build-clock risks and checks**

1. **Missing official test environment.** This virtualenv lacks `poker-agent` and installed `poker_agent_sdk`. Check before budgeting a tournament run:

   ```sh
   PYTHONDONTWRITEBYTECODE=1 ~/starter-kit/.venv/bin/poker-agent --help
   ```

2. **Wrong routing or silent lowest-card discard.** Audit the generated artifact for the dedicated entry, handler and one-index return; protocol legality alone accepts empty discards:

   ```sh
   rg -n 'double_board_turn_discard|def .*discard|cards=|len\(cards\)' ~/pokerbot/bots/final/agent.py
   ```

3. **Board-1 assumptions and split-pot mispricing survive conversion.** Audit these call sites, especially draw overrides and binary ICM:

   ```sh
   rg -n 'state\.board|variant\[|variant\.get|draw and|strength < 0.75|def _icm|win =|lose =' ~/pokerbot/tools/core_agent.py
   ```

4. **Timeouts or engine incompatibility.** Once the CLI is available, run actual eight-seat Pittsburgh tables; require zero failed decisions. This writes no histories:

   ```sh
   bot=~/pokerbot/bots/final
   PYTHONDONTWRITEBYTECODE=1 ~/starter-kit/.venv/bin/poker-agent play \
     "$bot" "$bot" "$bot" "$bot" "$bot" "$bot" "$bot" "$bot" \
     --variant double_board_turn_discard --tables 20 --seed pgh-smoke \
     --decision-ms 1 --no-history
   ```

5. **Stale generated artifact or rejected imports.**

   ```sh
   ~/starter-kit/.venv/bin/python -B ~/pokerbot/tools/build.py --check
   PYTHONDONTWRITEBYTECODE=1 ~/starter-kit/.venv/bin/poker-agent check \
     ~/pokerbot/bots/final/agent.py
   ```

Current results: **build freshness passed; SDK source-level submission check passed using local source imports.** Official CLI simulation was unavailable. No files were written, uploads performed, network APIs called, or keys inspected.