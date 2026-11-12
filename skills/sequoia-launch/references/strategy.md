# Format corrections (stage 5)

The strategy is the locked `final` profile in `tools/core_agent.py` (`PROFILES["final"]`):
position charts, push/fold when short, ICM-priced calls, per-seat tracking and exploits. Its
ladder is in `docs/baseline-strategies.md` and `skills/competition-build/SKILL.md`. During
the build hour only one question is asked of it: **does the Rules Card contradict something
it assumes?** Field tuning waits for hand histories and `skills/mid-round-iterate`.

Every number is from a command run on 2026-11-12 on the mini simulator unless a file is
named. Mini-simulator numbers rank ideas; they are not kit numbers.

## What the payout structure does to all-in decisions

Win chance needed to call an all-in against one opponent, by ICM
(`devtest/shim/poker_agent_sdk.icm`). Chip-EV needs 0.500 everywhere.

| Situation | 50/30/20 | Winner take all (100) |
| --- | --- | --- |
| 8 left, equal stacks | 0.556 | 0.500 |
| 4 left, equal stacks (the bubble) | 0.652 | 0.500 |
| 4 left, we are the big stack, calling the second stack, one short stack exists | 0.612 | 0.500 |
| 4 left, we are second, calling the big stack, one short stack exists | 0.752 | 0.500 |
| 3 left, equal stacks | 0.571 | 0.500 |
| 3 left, we are second, calling the big stack, one short stack exists | 0.637 | 0.500 |
| Heads-up, equal stacks | 0.500 | 0.500 |

- **50/30/20 punishes calling, not shoving, and the bubble (four left) is the peak.** Once in
  the points the premium falls, and heads-up it is gone: play aggressively for first.
- **Winner take all is chip-EV.** No bubble, no survival premium.
- **Flatter payouts (four or more places)** move the bubble earlier and raise every premium.
- **Payouts drawn per table:** nothing payout-dependent may be computed at import.

## Card says, knob answers

Every knob named in this table is in the `SETTINGS` table of `tools/core_agent.py`, which
overrides `PROFILES["final"]`: change it there, or the change does nothing. Knobs not in
`SETTINGS` are keys of `PROFILES["final"]` (or `_BASE`). Change one, run `tools/build.py`,
then `gauntlet.py bots/final --vs vN`.

| The Rules Card says | Check first | Knob to test |
| --- | --- | --- |
| payouts are 50/30/20 | nothing: this is what `final` was tuned on | none |
| winner take all, or one place paid | `icm_scale=1.0` already prices calls from `state.config.payouts`, so it should adapt by itself | `bubble_margin` 0.08 to 0, `points_tight` 0.08 to 0 |
| four or more places paid | **the core's ICM prices only the first three places** (`_icm_me` in `tools/core_agent.py`), and `paid` moves the bubble by itself | extend `_icm_me` if time allows; otherwise `bubble_margin` up to 0.15 |
| payouts drawn per table | grep the core for a payout constant used outside `act` | none if clean |
| the cap binds (see below) | `cap_aware=True` is already on | none; watch the place histogram in practice runs |
| antes (`BlindLevel.ante` above 0) | more dead money per hand | `steal_widen` up from 1.15, `push_scale` up from 0.9 |
| a slower or faster blind ladder | how many hands are played above 20 big blinds | `open_size`; nothing if most play is still short-stacked |
| `decision_ms` lower than 1 | the gate's timing line | nothing strategic: remove work, never add |

On the starter bot (not `final`), winner take all with its bubble margin at 0 against 0.08
gave +0.30 ± 0.31 points per table (n = 5,000 each): not detectable. Expect small effects and
test, do not assume.

## The hand cap

At the cap survivors split the remaining points by ICM on their stacks. On the mini
simulator's guessed ladder (2000/4000 at hand 250 with 16,000 chips in play) 2 of 300
mixed-field tables reached the cap; median length 153 hands, 90th percentile 186 (starter
bot, old checkout). **Decide from the real ladder:** take the level at the cap from
`state.config.blinds`; if the chips in play are more than about 20 big blinds per expected
survivor there, tables will reach the cap and the last hands are pure ICM decisions.

## What not to do in the build hour

- No new strategy code. `skills/competition-build` says to stop chasing mini-simulator EV, and
  the measurements agree: `final` already scores 24.55 ± 0.19 over nine line-ups against
  18.99 ± 0.16 for the starter.
- No global widening of calls against shovers. On the starter, lowering its shove-call
  discount from 0.10 to 0.04 cost 0.73 ± 0.23 points per table (n = 5,000 each). `final` uses
  `vs_shover="doc"`, the conservative setting, for the same reason.
- No river-bluff or mixing systems, no live Monte Carlo, no search.

## Bugs that lose these events (each has a gate check)

| Bug | Gate check that catches it |
| --- | --- |
| Raise outside `[min, max]`, or a float amount | fuzz legality; `tools/fuzz.py` |
| Exception swallowed by the `try` in `act`, played as check/fold for a whole table | fuzz hidden exceptions; `tools/fuzz.py` pass A (`DEBUG_RAISE`) |
| `bots/final` edited by hand, or the core changed without a rebuild | build check |
| Slow path on some states only (many hole cards, long history) | timing p99 and p99.9 |
| Memory blob that grows, or that breaks `act` on the next turn | memory growth; fuzz with corrupted blobs |
| Slow or failing import | import time; runner `check` |
| Unknown phase or event kind | fuzz dirty states |
| Works on hold'em, fails on the variant's phases | fuzz clean states built from the card's `phase_shapes`; tables on the variant |
