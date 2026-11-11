# Sequoia "No Limit" Pokerbot Tournament: Rules and Technical Format

Research date: 2026-11-10. Reliability key used below:
- **[OFFICIAL]** = official rules page or official landing page (read through a fetch-and-summarize tool, so wording is close paraphrase unless in quotation marks; section numbers are from the rules page).
- **[PRESS]** = secondary news write-up of the official pages.
- **[PARTICIPANT]** = unofficial GitHub repos by entrants. These are the only source for the starter-kit internals and the revealed variant. Not confirmed by the organizer; one repo is explicitly a "local mock" with labelled guesses.

Status on 2026-11-10: Bay Area regional (Nov 6) and Boston regional (Nov 9) have already happened; Pittsburgh is Nov 12; Finals are Nov 15. The landing page says applications are now closed.

## 0. Which event is this, and where are the official sources?

### Takeaway
The event is **"No Limit: A Bot Building Tournament"**, organized by Sequoia Capital and hosted with OpenAI and Citadel Securities, announced on X on 2026-10-27. Official site: https://pokerbot.sequoiacap.com/ ; official rules: https://pokerbot.sequoiacap.com/rules.html. It is a live, in-person, 60-minute build sprint followed by six scored bot tournaments, not a multi-week course-style contest, and it does not use MIT Pokerbots' engine or format.

### Cited Findings
- Name "No Limit: A Bot Building Tournament"; teams of 1 or 2 get 60 minutes to build a pokerbot from scratch; bots play 10,000 games against each other; top teams fly to SF Finals for a $100K grand prize [OFFICIAL] — [Landing page](https://pokerbot.sequoiacap.com/)
- Announcement post: "Announcing No Limit: a bot building tournament hosted by @Sequoia, @citsecurities and @OpenAI. Teams of 1 or 2 get 60 minutes to build a pokerbot from scratch. Agents play thousands of games across six scored rounds. Open to university students and recent grads ('25 or '26..." — [Sequoia on X](https://x.com/sequoia/status/2115111389501218868) (dated Oct 27, 2026 per [Digg](https://digg.com/ai/smdduv3c))
- Organizer is Sequoia Capital Operations, LLC; hosts are OpenAI and Citadel Securities [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Schedule: applications opened Tue Oct 27; regionals Fri Nov 6 (Bay Area / Menlo Park, CA), Mon Nov 9 (Boston / Cambridge, MA), Thu Nov 12 (Pittsburgh, PA); Finals Sun Nov 15 in San Francisco, by invitation (rules §2.4). Application deadlines were Nov 3 / Nov 6 / Nov 9, 11:59 pm local [OFFICIAL] — [Landing page](https://pokerbot.sequoiacap.com/); [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Regional events run 6–9 pm local with 5:30 pm check-in; SF final runs noon–8 pm [PRESS] — [Zeniteq](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef)
- Eligibility (rules §1): currently enrolled students at U.S. or Canadian universities, plus class of 2025 or 2026 graduates; 18+ (under-18 needs parental/guardian consent for a regional); teams of 1 or 2; one regional per participant; free entry; organizer/host employees and immediate family excluded [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html). Note: [Digg](https://digg.com/ai/smdduv3c) reports "U.S. universities" only, which is narrower than the official rules/FAQ (U.S. and Canada).
- Prizes: regionals pay $5,000 per team to the top five; Finals pay $100,000 / $50,000 / $25,000 for 1st/2nd/3rd; prizes split equally between teammates; paid within 30 days of verification (rules §5) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html). A Sequoia partner's post cites "over $250K in total prizes" — [Digg, citing Abhishek Malani on X](https://digg.com/ai/smdduv3c)
- Advancement: top five teams from each regional advance to the Finals, plus up to five wildcard teams selected on scores (rules §5.1) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Sequoia partner Shaun Maguire described it as "a poker bot tournament, with rules for the age of AI," with "an incredible guest list (ex @polynoamial), and some plot twists," and credits partner Abhishek Malani as originator — [Shaun Maguire on X](https://x.com/shaunmmaguire/status/2115131879452295182)
- Contact email is pokerbot@sequoiacap.com; the landing page carries no GitHub, Discord or docs links [OFFICIAL] — [Landing page](https://pokerbot.sequoiacap.com/)

### Inferences
- This is the first edition (branded "No Limit '26" in a participant repo); I found no evidence of an earlier Sequoia pokerbot event.
- "Plot twists" in the partner's post is consistent with the confirmed secret-variant mechanic.

### Gaps
- Whether a later/online edition is planned is unknown; nothing found.
- X posts could not be opened directly (HTTP 402); post text is from search-result titles and press quotes.

## 1. What poker variant is played?

### Takeaway
Officially the variant is **secret until each event's 60-minute build phase starts**, and participants are barred from sharing it before the event ends. The fixed frame is confirmed: **8-bot sit-and-go tables (not heads-up, not cash-game chip-EV), 2,000-chip stacks, blinds 10/20 rising every 25 hands, table ends at one survivor or 200 hands**. Marketing says "no-limit hold'em"; participant repos report the Bay Area regional used a 3-hole-card discard-and-reveal hold'em twist, and that the Finals will use a different variant.

### Cited Findings
- Variant is revealed at the start of each event's build phase and is confidential until then (rules §3.2); "Participants may not publicly share the poker variant or other unreleased event details before the event ends." (§6.4) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Each scored tournament is 10,000 simulated eight-bot sit-and-gos with random seating (§4.1, §4.3) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- "Each table plays until one bot holds all the chips or 200 hands have been played." Bots start with 2,000 chips; blinds start 10/20 and rise every 25 hands (§4.4) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Landing page demo exhibits are described as replays of "10,000 eight-bot no-limit hold'em games"; other exhibits show a heads-up duel between bots named "CFR-7" and "Monte," a bot/dealer message trace, and an "opening book" tree. These are simulated demos, not a format specification [OFFICIAL] — [Landing page](https://pokerbot.sequoiacap.com/)
- Press notes the tension: landing page promotes "10,000 simulated no-limit hold'em games" while rules say "the poker variant remains confidential until each event's build phase begins" [PRESS] — [Zeniteq](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef)
- Bay Area variant as recorded by an entrant team (repo titled for the 2026 Bay Area event): "Variant (announced 6 PM): hold'em with three hole cards"; after the flop each live player discards one card face down and exposes one retained card, the third stays hidden; showdown uses "the two retained cards + board." Side "mystery prizes": "Empty Bluffer, the Shover, Calling Station" [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- A second entrant's mock describes the same game second-hand: "Discard & Reveal (the SF regional game, as described by its winner)": "3 hole cards; each player still in the hand discards 1 face down, keeps 1 hidden and turns 1 face up for the table"; "All reveals are collected first and then shown together, so no one sees another reveal before choosing"; but "The exact timing wasn't confirmed, so there are four versions" [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Same repo states "The poker variant is revealed on the day, and the Finals use a different one," and its mock also supports a `bid` hook (an auction-style variant) as a guess [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Default blind ladder in the mock (author's assumption, not official): 10/20, 15/30, 25/50, 40/80, 60/120, 100/200, 150/300, 250/500 [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)

### Inferences
- With 8 players, 100bb starting stacks that shrink fast (blinds rise every 25 hands, 200-hand cap), and finishing-position payouts, the game is ICM/tournament-survival poker, not chip-EV heads-up. Push/fold and bubble play dominate late; heads-up CFR solutions do not transfer directly.
- Expect each regional and the Finals to carry a twist on hold'em (extra hole cards, discards, reveals, possibly bidding). A bot design should isolate variant-specific logic (hand evaluation with a hidden/revealed card, discard choice) from generic tournament logic.
- The two participant descriptions of the Bay Area game agree on the core (3 hole cards, 1 discarded, 1 revealed, 1 hidden) but differ on timing (post-flop vs unconfirmed). Treat post-flop timing as probable, not certain.

### Gaps
- No official confirmation of any revealed variant; the Boston (Nov 9) variant was not found anywhere. Pittsburgh and Finals variants are unreleased.
- Exact blind ladder, ante presence, bet-sizing rules (min-raise definition), and discard/reveal street timing are not officially published.
- One participant mock lists event tables as "blinds 10/20 rising every 20 hands" with a "250-hand cap with ICM for survivors," conflicting with the official 25 hands / 200-hand cap. Possibly an event-day or practice-sim configuration; unresolved — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots) vs [Rules](https://pokerbot.sequoiacap.com/rules.html)

## 2. Engine, starter kit, languages, and bot interface

### Takeaway
**Python only.** Teams implement a provided `Agent` interface and receive a starter kit (agent template, local simulator, ICM calculator, payout structure, blind schedule) at the event. **No official public GitHub repo or public technical documentation was found**; the kit appears to be distributed to accepted participants (a participant mentions a download button on a `/sim` page). Interface details below come from entrants' repos and are unofficial.

### Cited Findings
- "Teams have 60 minutes to build a Python bot that implements the provided Agent interface." Starter kit: agent template, local simulator, ICM calculator, payout structure, blind schedule (rules §3.3) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Sequoia: "You don't need to be a poker pro, or even have any poker experience, to win No Limit. The pokerbots that beat the pros never trained on human play. The starter kit handles the rules and the ICM math. You bring the creativity and strategy." — [Sequoia on X](https://x.com/sequoia/status/2117313159342268468)
- Python version, allowed libraries and memory limits are not specified in the rules document [OFFICIAL, absence] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Kit layout per an entrant: `kit/` is "the organizers' starter kit (SDK, engine, rules, examples, hand-history reader)"; installed with `pip install -r kit/requirements.txt` and `pip install -e kit/sdk/agent-protocol -e kit/sdk/agent-sdk -e kit/sdk/engine`; the team used a Python 3.12 virtualenv [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- CLI: `poker-agent check <agent.py>` (legality and size check, same as upload), `poker-agent play botA botB kit/examples/check_or_fold --tables 50` (organizers' runner, sandboxed subprocesses, hand histories), `poker-agent pack` [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- Kit contents per the second entrant: `agent.py` template with a memory example, `examples/` (`check_or_fold`, `min_raiser`), `sdk/`, `poker-agent` command (`play`, `check`, `pack`), `requirements.txt`, `RULES.md`, hand-history samples and docs; "The starter kit is a button on `/sim`" [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Event SDK signature as reported: `act(self, state, memory) -> (Action, bytes)`, with `state.events`, `state.legal_actions`, `state.can(kind)`, `state.config`, `state.cards`. Variant phases use actions such as `Action("discard", cards=[...])`, `Action("reveal", cards=[...])`; the Bay Area team used `Action("select", cards=(discard_index, reveal_index))` with indices into `state.cards` [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots); [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- State persistence: per-table `memory` blob (64 KB, starts empty) returned from and passed back into `act`; each team runs as "a pool of copies, so `self` can't be relied on between calls"; "Stateless: no globals that change between calls" [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots); [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- Import restriction: "Never import `poker_engine` or `pokerkit` in `agent.py`; `poker-agent check` rejects them" [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- Illegal raise handling: "A `raise_to` outside `[min_amount, max_amount]` is a failed decision" (platform then plays check/fold); "raise totals are not clamped" in the event SDK [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia); [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- The mock's own (non-official) simpler interface: `class Agent` with `act(obs)`, optional `new_table(info)`, `new_hand(obs)`, `hand_over(result)`, variant hooks `discard(obs)`, `reveal(obs)`, `bid(obs)`; obs fields `hole_cards`, `board`, `pot`, `to_call`, `legal_actions`, `min_raise_to`, `max_raise_to`, `players[seat]`, `history`; actions fold/check/call/all_in/raise-to [PARTICIPANT, mock design not official] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Not MIT Pokerbots: the only link is that the mock's author ported bots from github.com/mitpokerbots and uzlez/fullhouse-engine as sparring partners [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)

### Inferences
- The presence of a `pokerkit` import ban and an `engine` package suggests the organizers' engine is built on or alongside the open-source PokerKit library. Unverified.
- No C++/Rust/Java path exists per the rules ("Python bot"). Whether compiled extensions (e.g. `eval7`, `numpy`) are importable in the sandbox is unconfirmed; one team installed them locally but the repo does not say they were accepted on upload.
- Because of the stateless pool-of-copies model, opponent modelling within a table must be serialized into the 64 KB memory blob, and nothing carries across tables.

### Gaps
- No official public repo, SDK docs, or API reference found. Exact `Agent` signature, `state` schema, `Action` constructor, Python version and sandbox package list are unverified.
- Could not determine whether third-party packages are available in the scoring sandbox.

## 3. Compute, time, memory limits; GPUs, network, LLM calls

### Takeaway
Hard official limits: **1 ms per decision, 100 MB max file size, isolated sandbox with no network, no LLM/API calls at play time**. Bots are therefore classical precomputed/heuristic code written in Python, not LLM agents. A timeout or error yields an automatic check/fold.

### Cited Findings
- Each decision must be returned within one millisecond; maximum file size 100 MB; a bot that errors or times out automatically folds, or checks if checking is available (rules §3.7) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- "Submitted bots run in isolated sandboxes without network access." Bots may not call OpenAI tools, external APIs or outside services for gameplay decisions (§3.6); AI tools may not make live gameplay decisions (§7.1) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- "Bot state resets at the start of each table. Opponents are anonymized so bots cannot identify specific teams." (§3.8) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Press confirmation: "Each bot must return a move within 1 ms"; "a maximum file size of 100mb" — [Zeniteq](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef); [RuntimeWire](https://runtimewire.com/article/sequoia-offers-100-000-to-the-winning-student-pokerbot-team)
- Time bank per entrants: "1 ms per decision, 100 ms bank per table that never refills"; advice "Keep p99.9 well under 1 ms" [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia); mock also models "a 100 ms per-table bank" and notes "A 1 ms budget is tight in Python" — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Upload limits as modelled in the mock: `agent.py` or a zip, 50 MB uploaded, 200 MB unpacked, 1,000 entries, 1 MB of code; sockets disabled in worker processes [PARTICIPANT, mock; differs from the official 100 MB figure] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Memory limit is not specified in the rules [OFFICIAL, absence] — [Rules](https://pokerbot.sequoiacap.com/rules.html)

### Inferences
- 1 ms in Python rules out runtime Monte Carlo equity rollouts, search, or neural-net inference of any size. Practical designs are lookup tables (preflop 169-class equity, push/fold/ICM charts, bucketed postflop strength) loaded at import, with O(1) lookups. The 100 MB cap is the budget for precomputed tables.
- GPUs are irrelevant at play time. Offline precomputation (on any hardware) within the 60-minute build is not prohibited by the rules text found, but the hour is the real constraint.
- Import/initialization cost is presumably outside the per-decision budget, but that is not documented.

### Gaps
- RAM cap, CPU allocation, per-table startup time allowance, and whether the 100 ms bank is official are not confirmed.
- Whether the 1 ms limit also applies to non-`act` callbacks is unconfirmed (mock assumes yes).

## 4. Evaluation, ranking, and submissions

### Takeaway
Ranking is by **finishing-position points averaged over 10,000 eight-bot sit-and-gos per tournament, across six tournaments (T1–T6) weighted 1x through 6x**, so late rounds dominate (T6 alone is 6/21 of the total, T4–T6 are 15/21). Teams may resubmit every five minutes throughout; the active bot is frozen at each tournament's start. No Elo, bracket, or chip-EV scoring.

### Cited Findings
- Six scored tournaments T1–T6; the first starts when the 60-minute build ends and later ones start 20 minutes apart (§4.1–4.2) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html); [Zeniteq](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef)
- Teams may submit one bot every five minutes; most recently accepted submission is the active bot (§3.5). Teams can keep editing and submitting after the build phase; each scored tournament freezes the active bot at its start (§4.2) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Points depend on finishing position. "The point distribution may vary by poker variant and will be announced at the start of the build phase." If a table reaches the 200-hand limit, remaining points are split among survivors by ICM (§4.5). No points table is published [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- If the bot count is not divisible by eight, empty seats are filled by randomly selected copies of submitted bots, which earn no points (§4.6) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Tournament score = average points per table; final score weights T1×1 … T6×6 (§4.7). "Ties are resolved by a tie-breaker challenge to be determined by the Organizer." (§4.8). Rankings and prizes depend solely on bot performance (§4.9) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Disputes go to a Gamemaster before the next scored tournament starts; T6 disputes within 5 minutes of results; hand logs are retained (§6.3) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Payout as seen by entrants: "Points are the table payouts (50/30/20 by default); 100 points per table split over 8 seats, so 12.5 is par" [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia); the mock likewise uses "50/30/20 for 1st/2nd/3rd" as a default and flags it as an assumption — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Practice cadence per the mock, citing a "No Limit '26 Boston format page and participant docs": "a 60-minute build with ~1,000-iteration practice runs every 10 minutes (never scored)", then six scored rounds "at least 5,000 iterations each" [PARTICIPANT; the "at least 5,000" figure conflicts with the official 10,000] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Same-hand bust and odd-chip handling in the mock ("Equal stacks split the places"; "Odd chips go to the first winner left of the button") are the author's assumptions for things "the rules don't specify" [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)
- Castle Challenge: an optional pre-application game (split 100 soldiers across 5 castles worth 1–5 points; about 3 minutes) with a public leaderboard updated every 15 minutes; top scorers get priority registration — [Landing page via search summary](https://pokerbot.sequoiacap.com/); [Sequoia on X](https://x.com/sequoia/status/2115486256041963847). [Zeniteq](https://www.zeniteq.com/sequoia-and-openai-open-a-100k-pokerbot-tournament-6aycef) says castle points map to "9, 4, 2 or 0 scoring points"; that refers to the Castle Challenge itself, is not in the official rules, and does not feed the bot tournament score per an entrant write-up ([Mianmalol/No_Limit_Bot_Tournament](https://github.com/Mianmalol/No_Limit_Bot_Tournament)).

### Inferences
- With top-3-only payouts (if 50/30/20 holds) and 8 seats, expected par is 12.5 points per table; variance reduction comes only from the 10,000-table sample, not from duplicate deals or AIVAT-style methods (none mentioned).
- The 1–6 weighting plus resubmission every 5 minutes rewards adapting to the field between rounds: reading hand logs/practice results, then re-tuning. A team's T1 bot matters little (1/21).
- Field composition is the other entrants' bots, so exploitative tuning against the observed population (e.g. many shove-heavy or passive bots) probably beats equilibrium play; the "Empty Bluffer / Shover / Calling Station" side prizes hint at the archetypes organizers expect.
- At most roughly 12 + 20 submissions are possible across the build hour and the 100 minutes of scored rounds, given the five-minute rate limit.

### Gaps
- Official points-per-place table for each event is announced on the day and not published; 50/30/20 is participant-reported.
- Wildcard selection criteria, tie-breaker format, and whether hand histories from scored rounds are given to teams between rounds are not documented publicly.
- No regional results or winner lists were found as of Nov 10.

## 5. Rules on AI assistants, solvers, pre-trained models, collusion, code sharing

### Takeaway
AI coding assistants are explicitly allowed for building (the rules name OpenAI's Codex and "Astra"), and public documentation may be used; AI may not make live decisions. Disqualifying conduct is collusion, copying another team's code, platform interference, and misuse of the submission endpoint. The rules found say nothing explicit about open-source solvers, pre-written code, or pre-trained models.

### Cited Findings
- "Teams may use Astra and Codex to write, debug, and refine their bots during the build phase." Publicly available documentation is also permitted (§3.4) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- AI tools may help write/debug/refine but may not make live gameplay decisions (§7.1); use of OpenAI tools is optional at every stage (§7.3); teams must review and test AI-generated code and remain responsible (§7.4); OpenAI service use is governed by OpenAI's terms [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Organizer may use an AI model after hands are played to pick replays for spectator screens; no effect on scoring (§7.2) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Disqualification for collusion, copying another team's code, interfering with the platform, or misusing the submission endpoint; also cheating, fraud, harassment, malicious code, material misrepresentation, including when discovered after results (§6.1) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Submissions must not contain personal information, third-party confidential information, malware, or hardcoded credentials (§8.4); participants keep ownership of bot code and grant a nonexclusive royalty-free license to run/evaluate it and to use hand logs and anonymized results for replays/publicity (§8.1) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- No betting on outcomes; chips and points have no cash value (§3.9–3.10) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Framing is "build a pokerbot from scratch" in 60 minutes — [Landing page](https://pokerbot.sequoiacap.com/)
- In practice, entrants prepared before the event: one team's repo has a `prep/` strategy folder, a pre-built local arena and a 169-class preflop equity table generator, and lists "Claude" as a team member; another built a full mock simulator in advance [PARTICIPANT] — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia); [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots)

### Inferences
- "Astra" is not defined in the rules; given it is paired with Codex and governed by OpenAI terms, it is presumably an OpenAI tool/model made available at the event. Unverified.
- Naming Codex/Astra reads as a sponsored offer rather than an exclusive whitelist (§7.3 makes OpenAI tools optional, and at least one team openly used Claude), but the rules as summarized do not explicitly bless other assistants. Anyone relying on a non-OpenAI assistant or on pre-written code/tables should confirm with organizers (pokerbot@sequoiacap.com) or the on-site Gamemaster.
- "From scratch" plus the secret variant limits how much pre-built code helps; variant-agnostic tooling (ICM push/fold tables, fast hand evaluators, a test harness) is what entrants are evidently bringing. Whether bringing pre-written code is formally allowed is not stated in the sources I could read.
- Anonymized opponents and per-table state reset are technical anti-collusion measures (bots cannot recognise a partner team).

### Gaps
- No explicit rule text found on: open-source solvers or libraries, pre-trained models, pre-written code brought to the event, or sharing code publicly after the event.
- I could not obtain the rules verbatim in full (tool summarizes); a human read of https://pokerbot.sequoiacap.com/rules.html §3, §6, §7 is advisable before relying on edge cases.

## 6. Docs, example bots, community, lectures

### Takeaway
Public technical material is thin: the official rules page and landing page only. No official GitHub org, Discord, lecture series or office hours were found; support is on-site ("Gamemasters," a technical lead and an events lead). Example bots (`check_or_fold`, `min_raiser`) ship inside the participant-only starter kit. The best public technical references are entrants' repos.

### Cited Findings
- Landing page has no starter-kit download, docs, GitHub or Discord link; only the contact email [OFFICIAL] — [Landing page](https://pokerbot.sequoiacap.com/)
- On-site roles: Gamemasters handle disputes; a technical lead decides platform/timing matters and an events lead decides rules/conduct matters (§6.2–6.3) [OFFICIAL] — [Rules](https://pokerbot.sequoiacap.com/rules.html)
- Kit examples `check_or_fold` and `min_raiser`, a `RULES.md`, hand-history samples and a hand-history reader are reported inside the kit [PARTICIPANT] — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots); [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- Unofficial practice resources: a local mock of the tournament with configurable variants and a UI — [aniketxdey/pokerbots](https://github.com/aniketxdey/pokerbots); a Bay Area team's bots, arena and league runner — [nnicholas-c/poker_sequoia](https://github.com/nnicholas-c/poker_sequoia)
- Guest list reportedly includes Noam Brown ("ex @polynoamial") — [Shaun Maguire on X](https://x.com/shaunmmaguire/status/2115131879452295182)
- Castle Challenge leaderboard and entrant write-ups exist but concern the application mini-game, not the bot API — [Sequoia on X](https://x.com/sequoia/status/2115486256041963847); [Caden Li on X](https://x.com/cadenbuild/status/2116220038147661901)

### Inferences
- A "/sim" page with a starter-kit button and a "Boston format page and participant docs" are referenced by an entrant, implying gated participant documentation exists behind acceptance; it is not publicly indexed.

### Gaps
- No official Discord/Slack, lectures, or office hours found. No post-event recaps, winner write-ups, or results pages found for the Nov 6 or Nov 9 regionals at the time of research.
- Another repo surfaced in search (twinbrian/pokerbots) returned 404 and could not be checked.
