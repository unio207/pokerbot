# STATE: hand-off from sequoia-launch to mid-round-iterate

Updated: 2026-11-12 19:03 (T+50), during the Pittsburgh regional. Clock: T+0 = 18:13 (portal
`variant_announced_at` 23:13:58Z). Round 1 snapshot at T+60 = 19:13. Machine: MacBook M5, kit
at `../starter-kit` (its `.venv`, Python 3.12); build machine synced by `rsync`, kit at
`~/work/starter-kit`.
Repo: `main`, **nothing committed since `2f9741d`**: the conversion is in the working tree
(`tools/core_agent.py`, `bots/`, `tools/field_report.py`, `skills/sequoia-launch/scripts/gate.py`,
`zoo/variants/double_board_turn_discard.md`). `v0/`, `v1/` and `rules_card.json` are ignored by git.
**Numbers below are from the organizers' kit unless a line says mini.**
Template: `sequoia-launch/templates/STATE.md`.

## Active bot

| Version | File | Uploaded at | Active | What it is |
| --- | --- | --- | --- | --- |
| v0 | `v0/agent.py`, 70,036 bytes | 18:20:31 (T+7:31), submission `7e4d8e8e` | no (rollback target) | the `final` profile, unconverted: scores board 1 only, lets the platform discard its lowest card |
| v1 | `v1/agent.py`, 73,246 bytes, sha256 `2df6cc1cf4e70d03...` | 18:30:54 (T+17:54), submission `920a2429` | no | `final` converted to Pittsburgh (this session's conversion) |
| v2 | `v2/agent.py`, 75,994 bytes | 18:43:35, submission `066139f9` | no | Vedaant's conversion (`db_*` functions, his v3a, branch `pittsburgh-v2`), uploaded by Henry; not built from this core |
| v3 | `v3/agent.py`, 73,364 bytes, sha256 `5f7235d541933e20...` | 18:52:04, submission `393c48a3` | no | v1 plus the looser preflop bundle; played practice 3 as a field test |
| v4 | `v4/agent.py`, 73,673 bytes, sha256 `11f2e107c0d62c6d...` | 18:58:00, submission `d55b4134` | **yes** | v1 plus the heads-up big-blind fix; identical to `bots/final/agent.py` (`cmp`) |

Upload to ready: under 60 s both times (v1 was ready and active at the first portal read, 56 s
after upload; not timed more finely). Rollback target: v1, on the team page (the active switch, not a re-upload).

## Variant

Pittsburgh, kit name `double_board_turn_discard`, portal name `pittsburgh`. Ruleset:
`zoo/variants/double_board_turn_discard.md`. Rules Card: `rules_card.json`, from `probe.py` on
the kit plus `RULES.md`, `README.md`, `AGENTS.md` and the engine source.

- Three hole cards through preflop, flop and turn betting. Two boards; `state.board` is board
  1, `state.variant["boards"]` holds both.
- `discard` phase after turn betting when two or more players remain:
  `Action("discard", cards=(i,))`, `i` the index of the card thrown away. A failure discards
  the lowest card.
- Showdown per board with the two kept cards; each board wins half of every pot.
- Table settings equal the template: 8 players, 2,000 chips, 10/20, 20 hands per level, cap
  250, payouts 50/30/20, 1 ms, 100 ms bank, 64 KB.
- Side prizes (raw counts over scored rounds, no points): scoops and rivers seen. Not chased.

What the conversion is (`tools/core_agent.py`, the `double_board_turn_discard` entry, first in
`VARIANTS`):

- `detect`: `"boards" in state.variant`, so it holds whichever name the platform sends.
- `double_board_strength(hole, boards, facing)`: two cards scored per board with the hold'em
  code (`_pair_strength`, split out of `holdem_postflop`), averaged.
- `double_board_keep(cards, boards)`: the pair with the most strength summed over both boards.
  The discard handler throws away the third card; flop and turn strength is that pair's.
- Preflop: `discard_reveal_preflop` (three cards, best two), unchanged.
- `hand_rank` and `_draws` are memoised (`lru_cache`, 64 entries): three pairs share each
  board's rank. 4,096 entries made the garbage collector pause for 1 to 2 ms; keep it small.
- No mini-simulator class for this game. `--mini` plays hold'em: every measurement is on the kit.

## Knobs in the active version (`PROFILES["final"]`, `tools/core_agent.py`)

```python
track=True, adapt=frozenset({"steal", "shover", "station", "minraise"}),
steal_widen=1.15, steal_any=0.85, cbet_air=0.3, vs_shover="doc",
icm_scale=1.0, cap_aware=True, open_size=2.3, semi_bluff=0.3,
call_margin=0.05, bubble_margin=0.08, push_scale=0.9, points_tight=0.08,
threebet=0.03, call_raise=0.08,
```

Unchanged from before the event. Everything else comes from `_BASE` (`value_bet=0.80`,
`medium_bet=0.60`, `call_edge=0.12`, `post="basic"`). The 13 float knobs are repeated in
`SETTINGS`, applied last: change a knob there.

## Gate

`gate.py bots/final --tables 30`, runner kit, SDK kit, card `rules_card.json`: **GATE: PASS** on
both machines, on the file that is v1 (table below) and again on v4 (build machine: p50 137 µs,
p99 191, p99.9 211, max 288, 90 kit tables with 0 failed decisions). `gate.py` now deals a second board into
`state.variant["boards"]` when the card shows a two-board game; before that its fuzz and timing
never reached the new code.

| Check | Mac | Build machine |
| --- | --- | --- |
| fuzz legality, 20,000 states | 0 bad | 0 bad |
| hidden exceptions, 10,000 clean states | 0 | 0 |
| timing, 20,000 decisions, µs | p50 64, p99 88, p99.9 99, max 117 | p50 137, p99 193 (allowed 250), p99.9 212 (allowed 500), max 249 |
| kit tables | 90 over 3 line-ups, 0 failed | 90 over 3 line-ups, 0 failed |

Memory: largest blob 96 bytes (allowed 16,384). `agent.py` 73,246 bytes, import 0.010 s. The
upload-test imitation is skipped on the kit (its `play` always gives the time bank).

Failed decisions under load: the gauntlet (5 kit jobs at once on the Mac) logged 3, 2 and 2
failed decisions in three runs, each time on one bot only and once on v1 while the candidate
had 0. The one that could be located replayed with 0 failures alone, twice. The platform
logged 0 missed of 416,771. Treat a handful in a gauntlet as load, and a failure in `gate.py`
(which plays its tables alone) as real.

## Gauntlet baseline

`gauntlet.py bots/final --vs v0 --tables 100`, runner kit, 5 jobs, payouts 50/30/20, nine
line-ups, n = 900 tables per bot per seed. Par is 12.5.

| Seed | v1 | v0 | v1 minus v0 |
| --- | --- | --- | --- |
| `convert` | 25.17 ± 0.27 | not recorded | +2.42 ± 0.69 |
| `convert2` | 26.89 ± 0.71 | 23.31 ± 0.46 | +3.58 ± 0.74 |

Seed `convert2` by line-up (n = 100 tables per bot per line-up):

| Line-up | v1 | v0 | Difference |
| --- | --- | --- | --- |
| mixed field | 33.30 ± 2.51 | 29.50 ± 2.39 | +3.80 ± 1.70 |
| passive field | 40.40 ± 1.36 | 35.80 ± 2.11 | +4.60 ± 2.22 |
| aggressive field | 30.20 ± 1.42 | 29.50 ± 1.34 | +0.70 ± 1.20 |
| seven starters | 26.80 ± 1.65 | 19.60 ± 0.86 | +7.20 ± 1.44 |
| four of you, four starters | 17.77 ± 0.49 | 16.60 ± 0.50 | +1.18 ± 0.65 |
| zoo field 1 | 16.30 ± 2.00 | 18.10 ± 1.99 | -1.80 ± 2.49 |
| zoo field 2 | 27.00 ± 1.73 | 18.90 ± 1.21 | +8.10 ± 1.48 |
| zoo field 3 | 31.70 ± 1.44 | 29.00 ± 1.65 | +2.70 ± 1.90 |
| zoo field 4 | 18.50 ± 1.84 | 12.80 ± 1.75 | +5.70 ± 2.16 |

**v4, the active version, against v1** (`gauntlet.py v4 --vs v1`): 28.08 ± 0.25 against 26.31 ± 0.33,
+1.77 ± 0.25, positive in all nine line-ups (seed `hu1`, n = 2,700 per bot); 27.79 ± 0.58 against
26.43 ± 0.68, +1.36 ± 0.28 (seed `hu2`, n = 900). The number a candidate has to beat is v4's.

v1 as the incumbent in two earlier runs, n = 2,700 tables: 26.83 ± 0.23 (seed `river1`) and
26.94 ± 0.27 (seed `bet1`).

Speed: 1,200 tables per minute on the Mac (kit, 5 jobs). `--tables 300` for both bots takes
3.7 minutes and gives a standard error of 0.20 to 0.23 on the difference. Detectable at 2.8
standard errors: 1.06 points in 5 minutes, 0.75 in 10, 0.43 in 30.

Promotion rule in force: difference over all line-ups above 2 standard errors on one seed and
still positive on a fresh seed; `gate.py` PASS.

Before the event, mini simulator, hold'em, for reference only: `final` 24.55 ± 0.19 against
`starter` 18.99 ± 0.16 (n = 9,000). Not comparable with the kit numbers above.

## Tried during the build and not shipped

| Change | Result against v1 (kit, n = 2,700 per bot) | Decision |
| --- | --- | --- |
| River strength refit to measured pot share (`-0.152 + 1.195 x strength`) | -0.14 ± 0.23, seed `river1` | reverted |
| `value_bet` 0.80 to 0.70 and `medium_bet` 0.60 to 0.52 | +0.31 ± 0.20, seed `bet1`; mixed field -1.93 ± 0.64, seven starters +1.50 ± 1.07 | reverted; candidate, needs more tables |
| Looser preflop bundle (v3): `threebet` 0.06, `call_raise` 0.14, `hu_open` 0.80, `points_tight` 0.03, `bubble_margin` 0.04, opens x 1.25 | -1.49 ± 0.40, seed `loose1`; negative in eight of nine line-ups. Measured with the big-blind bug still in | reverted; re-measure piece by piece on v4 |
| Vedaant's conversion (v2) in place of this one | +0.07 ± 0.35, seed `ved1`. Timing on the Mac p99 250 µs against 88 (no memo) | not adopted; ideas to port one at a time |
| Preflop refit from Monte Carlo | not run as an A/B: the borrowed fit is within 0.004 of the measured share in the top seven deciles and 0.016 to 0.022 low in the bottom two | not worth a window |

Monte Carlo behind those (heads-up, both hands keep the pair the bot keeps, scripts in the
session scratchpad, not in the repo): preflop n = 800,000; postflop n = 400,000 per street.
Flop and turn strength is within 0.04 of the real pot share in every decile. The river
overrates weak hands (predicted 0.30 is 0.18, 0.37 is 0.29) against a random hand, yet
correcting it did not score.

## Practice runs and rounds

| Run | Time | Bot | Decisions | Missed | Restarts | Errors | Points, place |
| --- | --- | --- | --- | --- | --- | --- | --- |
| practice 1 | 18:34:34 | v1 | 416,771 | 0 | 0 | none | 15.95 ± 0.68, 32nd of 82 that played; 1st 11.4%, 2nd 22.3%, 3rd 17.8% |
| practice 2 | 18:45:01 | v2 | 803,861 | 0 | 0 | none | 14.47 ± 0.45, 43rd of 100; 1st 7.5%, 2nd 23.3%, 3rd 18.6% |
| practice 3 | 18:54:04 | v3 | 1,551,886 | 0 | 0 | none | not read yet |

Health columns are from `portal.py`. Points and places are Vedaant's, from the hand histories
(relayed, not re-derived here). Practice 1 had 146 entries, 64 forfeits, 2,500 tables; the runs
grow (5,000, then 10,000 tables). Field read from practice 1 and 2: the top teams win about a
third of their tables, play 19 to 32% of hands and fold to raises 67 to 81%; we played 15 to
16% and folded 88 to 89%, all of it with the big-blind bug below.

## Known weaknesses

- Fixed in v4, present in v0 to v3: `_big_blind_seat` took the last `blind` event, but heads-up
  the kit posts the big blind first (small blind last in 13,786 of 13,967 heads-up hands in our
  kit histories). On the button heads-up the bot thought it was the big blind, so `hu_open`
  never applied. Every heads-up or tightness measurement before v4 is suspect.
- A big blind all-in for less than the small blind still picks the wrong seat (rare).
- Every strength number is hold'em's, averaged over two boards. Thresholds (`value_bet`,
  `medium_bet`, `call_edge`, the 0.88 raise) were tuned for one board; averaged strength
  reaches 0.80 rarely (top flop decile averages 0.74), so the bot value-bets less than in
  hold'em.
- The draw flag is true with a draw on either board, though that draw wins half a pot.
- Before the discard the hand is scored as the pair it would keep now; the option to choose
  after the turn is not priced.
- Opponents hold three cards and keep their best two: nothing models that their ranges are
  stronger than hold'em ranges.
- Timing headroom on the build machine: p99 193 of our 250 µs margin. Anything that adds work
  per pair or per board needs `gate.py` there first.
- `zoo field 1` (the strong `claude_*` bots) is the one line-up where v1 did not beat v0
  (-1.80 ± 2.49, n = 100).
- `tools/field_fit.py --sweep` and `tools/bench.py` play the mini simulator, which cannot
  deal this game: use `gauntlet.py bots/final --vs v1` on the kit for every decision.
- `tools/field_report.py` reads the download format now, but its hand types and advice were
  set on hold'em: "maniac" and "station" trigger easily with three-card ranges, shown hands are
  the kept pair, and filler seats count like scored seats.
- `probe.py` on the kit needs `TMPDIR=/tmp` (bots run with a clean environment, so the probe
  bot writes to `/tmp`). It rewrites `rules_card.json`: the hand-filled fields would be lost.
- `_icm_me` prices only the first three payout places.

## First experiments to try

Judge each on `gauntlet.py bots/final --vs v4` on the kit and on the share of 1st places in the
next practice run. Vedaant's ranked list (GitHub issues #12 and #13, branch `research/pittsburgh`):

0. Practice 3's and practice 4's results for v3 and v4: does the heads-up fix lift the 1st-place
   share (11.4% and 7.5% before)? Heads-up button fold rate was 75% against the field's 33%.
0. `hu_open` and `push_scale` again, now that the bug is fixed; then wider opens and `call_raise`
   one at a time; then `points_tight` and `bubble_margin` down.
0. His half-pot veto (`db_floor`: do not fold a hand that is near the nuts on one board to a big
   bet) and dropping the draw-only call. His v3a with both plus a calibration read +0.62 ± 0.27
   and +0.34 ± 0.31 against his own v1.
1. Henry, 18:25: port `zoo/claude_exploiter_1`'s postflop read into the core (PR #11's mock
   tournament on the mini simulator had it about 3 points per table ahead of `final` against
   the strong AI-written bots, hold'em). Judge it on the zoo line-ups' rows of
   `gauntlet.py bots/final --vs v1`, on the kit.
2. Hand histories: about 5,000 hands from the first practice run or round,
   `tools/field_report.py <file> --hero "Team Allow It"`. What the field is decides the rest.
3. The betting-threshold candidate (`value_bet` 0.70, `medium_bet` 0.52 in `SETTINGS`): rerun
   with `--tables 600` on a fresh seed. It lost in the mixed field and gained against starters,
   so check the field report first.
4. `call_edge` and `points_tight` if the field is strong; `steal_widen` if it is weak.

## Log

- 2026-11-12, session 1: launch skill written against a checkout 49 commits behind main;
  found when the zoo looked empty. Pulled to `8f76ac0`, re-based the skill on `bots/final`
  and the repo's tools, moved it to `skills/sequoia-launch/`, added the 12 weak zoo bots from
  the overnight branch. Nothing uploaded. Pre-written code is allowed (Henry, 2026-11-12).
  Still open: whether there is an upload command (assume the team page in a browser).
- 2026-11-12 16:20 to 16:40, readiness check: every command and identifier in the three
  skills cross-checked against the code. Two faults fixed. (1) `tools/core_agent.py` had no
  `SETTINGS` table, so `field_fit.py --sweep --bot bots/final` exited; ported from PR #10
  (same values as the profile: the `--seed parity` gauntlet was identical before and after,
  and `--seed baseline` reproduces 24.55 ± 0.19 against 18.99 ± 0.16). (2)
  `mid-round-iterate` promoted on `tools/bench.py`, which plays hold'em on the mini
  simulator only; it now promotes on `gauntlet.py --vs vN` and `gate.py`, with the launch
  skill's promotion rule and upload checklist. Gate re-run on the rebuilt bot: PASS. The
  mid-round commands were run once on the mini `irish` ruleset in a scratch copy; reading a
  real hand-history file is still untested. PR #10 stays open (shim path order, hiding
  `zoo/_template` in the practice page).
- 2026-11-12 16:38 to 17:06, dry run and build machine. A fresh agent followed
  `sequoia-launch` on the sealed `rehearsal` variant in a scratch copy (mini simulator as
  the kit). By its own clock: Rules Card at T+2:14, conversion at T+4:40, gate PASS at
  T+4:55, fresh-seed confirmation +2.82 ± 0.22 at T+5:36, `v1/` at T+5:55; then a network
  error cut it off before the hand-off stage. No command in the skill failed as written.
  Measured afterwards by the main session on what it left: build check ok; `GATE: PASS`, 0 failed
  decisions of 34,669, p99 42 µs; converted 26.13 ± 0.44 against unconverted `v0`
  23.29 ± 0.69, +2.84 ± 0.72 (n = 900 per bot, one seed). The build machine was synced to
  `96575d3` and passes the gate (numbers under "Gate"). The copy command in the skills is
  now `rsync` with excludes; `starter-kit/` is ignored by git; the skills' `PY=` line also
  finds a kit unpacked inside the repo.
- 2026-11-12 17:30 to 17:40, team portal read in Henry's Chrome (read-only). Team `Team Allow
  It`, 2 of 2 members, build box `pittsburgh-team-116` at the address in `~/.ssh/config`, 0
  submissions, no active bot, uploads closed until the announcement; 145 teams, 0 bots ready,
  0 rounds. The Format page matches the template Rules Card on every value. Getting started
  confirms `poker-agent play --seed`, and says the kit ships a hand-history sample and reader.
  The API key file exists locally. Not opened: Account settings, the portal's chat.
- 2026-11-12 17:55, portal API. The saved key can read the competition record, our uploads,
  health and the rounds list (`skills/sequoia-launch/scripts/portal.py`, read-only). The
  competition record for `Pittsburgh` says `round_weighting: "fibonacci"`, not the 1x to 6x of
  the Format page's default table: the late rounds weigh even more than planned for. Variant
  still null at 17:55. The organizers' setup skill is unchanged (version 2026-11-05.2). The
  public rules page still names Astra and Codex as the assistants teams may use; the portal's
  Getting started page names Claude Code as well.
- 2026-11-12 18:13 to 18:45, the launch (T+0 to T+32). Variant on the portal at 18:13:58.
  Kit installed on both machines; `v0` gated on the kit and uploaded at T+7:31. `probe.py`
  needed `TMPDIR=/tmp`. Conversion written at T+8: two helpers, a discard handler, a
  `VARIANTS` entry, no simulator class. Its first timing on the build machine was p99 250 µs
  for the scoring alone; a memo on `hand_rank` and `_draws` brought it to 165. Against `v0`:
  +2.42 ± 0.69 and +3.58 ± 0.74 on two seeds. `v1` uploaded at T+17:54, clean in practice 1
  (0 missed of 416,771). `gate.py` taught to deal two boards. `tools/field_report.py`'s reader
  fixed against the kit sample by a subagent (64 hands, 13 tables, equal to the kit's
  `read.py`). Two changes tried against `v1` and not shipped (table above). Someone else ran
  `gate.py bots/final` on the build machine at 18:23 while I was timing there.
- 2026-11-12 18:45 to 19:03 (T+32 to T+50). Henry uploaded Vedaant's bot as v2 (clean in practice
  2); it measured equal to v1 (+0.07 ± 0.35). The looser bundle went up as v3 for practice 3 as a
  field test while its A/B ran: -1.49 ± 0.40, reverted. Vedaant found the heads-up big-blind bug
  (issue #13); confirmed on our kit histories, fixed, v4 gated and uploaded at 18:58, +1.77 ± 0.25
  and +1.36 ± 0.28 against v1 on two seeds. `v0/` to `v4/` are ignored by git: `bots/final` in this
  commit is v4; v1 is v4 without the `_big_blind_seat` change; v3 is v1 with the bundle above.
