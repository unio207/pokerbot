# Rules digest for the day

Everything here was read from `docs/official-format.md` (the site's Format page),
`docs/official-getting-started.md` (its Getting started page) and the organizers' setup skill
(version 2026-11-05.2). **The kit's `RULES.md` and `state.config` override all of it.** Where
the public rules page (`pokerbot.sequoiacap.com/rules.html`, re-read 2026-11-12) still says
something older, the older value is in brackets.

## Format

| Thing | Value | Where the bot or scripts read it |
| --- | --- | --- |
| Table | 8 players, 2,000 chips, blinds 10/20 rising every 20 hands [25], cap 250 hands [200] | `state.config` |
| Points | 50/30/20 default; rounds may draw payouts per table; ICM split among survivors at the cap | `state.config.payouts` |
| Decision time | 1 ms plus a small delivery allowance; 100 ms bank per table, emptied by one timeout, refilled at the next table | `state.config.decision_ms`, `time_bank_ms` |
| Memory | 64 KB per table, cut beyond that, empty at every table; about 16 KB is effectively free | `state.config.memory_bytes` |
| Runtime | Python 3.12, standard library, `poker_agent_sdk`, `poker_agent_protocol`, the kit's `requirements.txt`. No network. Bot folder read-only; `/tmp` (64 MB) writable; no files kept between tables | kit `README.md` |
| Upload | `agent.py`, or a zip with `agent.py` at its root: 50 MB uploaded [100], 200 MB unpacked, 1,000 entries, 1 MB of code in `agent.py`; one upload per 30 s [5 min] | Rules Card `limits` |
| Upload test | heads-up, up to 20 hands, against check-or-fold, 1 ms and **no time bank**; rejected if the bot does not start, crashes, or fails more than 10% of decisions | `gate.py` imitates it on the mini simulator |
| Schedule | build 60 min; rounds 1 to 6 snapshot at T+60, 80, 100, 120, 140, 160; weights 1x to 6x; at least 5,000 tables per round [10,000] | Rules Card `schedule`, `clock.py` |
| Practice | about 1,000 tables every 10 min during the build; never scored | team page |
| Score | sum over rounds of weight x average points per table; ties by weighted share of firsts, then seconds | |
| Active bot | each upload becomes active once ready unless a newer one is already active; any earlier ready upload can be switched back to; no active bot at a snapshot scores 0; organizers can freeze uploads | team page |

## How a decision fails, and what happens then

- Timeout, exception, or illegal action. The platform checks if free, else folds, or takes the
  automatic choice in a variant phase.
- Illegal means a kind not in `state.legal_actions`, or a raise total outside
  `[min_amount, max_amount]`. **Raises are not clamped**; an undersized raise facing a bet folds.
- Float amounts are rounded down, so a computed size can land one chip under the minimum.
  Ints only, clamped last.
- Check and call are never offered together. Reference hold'em offers no fold when checking
  is free.
- After a timeout, exception or crash the previous memory is kept and that turn's events are
  delivered again (do not double-count them blindly). After an illegal action the returned
  memory **is** stored.
- Memory that makes `act` raise comes back unchanged on every later turn at that table: one
  bad blob loses the table. Parse defensively, rebuild on any doubt.
- The platform imports `agent.py` once and forks copies. Tables load at import. Threads started
  at import do not exist in the copies. Nothing on `self` or in globals survives reliably.
- A copy that crashes or stalls is restarted, a limited number of times per round.
- Carrying information between tables breaks the rules, and seats are anonymized anyway.

## What the team page shows

Per round and practice run: average points, finishes by place, decisions, **missed decisions**,
**restarts**, latest errors. Never what the bot prints. After each round: hand histories of
every table we played (opponents named, our cards, others' cards when shown, the action
played for each failed decision). What each number triggers: `measure-and-upload.md`.

## The kit (as reported; first use is the test)

`poker-agent check <agent.py>`, `poker-agent play <bot dirs...> --tables N --no-history`
(prints a JSON summary; `--seed` is assumed by our tools and not confirmed), `poker-agent pack`.
Kit folder: `agent.py` template, `examples/check_or_fold`, `examples/min_raiser`, `sdk/`,
`RULES.md`, `README.md`, `AGENTS.md`, hand-history samples. `poker-agent check` rejects imports
of `poker_engine` and `pokerkit`. The kit needs Python 3.12 exactly and does not run its
simulator on native Windows.

## Still assumed on the morning of the event

1. Pre-written code and skills are allowed: **confirmed by Henry on 2026-11-12** (the public
   rules are silent and the landing page says "from scratch", so re-confirm for the finals).
   If that ever changes: the kit's `agent.py` is the base, the
   ladder to rebuild is the strategy spec in `skills/competition-build/SKILL.md`, and this
   skill is used as knowledge only.
2. Uploads go through the team page in a browser. The setup skill shows the site has an API
   (`/api/auth/api-key`, `/api/teams/<team>/machine`), but no upload endpoint is documented
   anywhere we have read. Look in the kit's `README.md` and `AGENTS.md` for one; do not guess.
3. `poker-agent play` accepts `--seed` and prints `bots.<name>#<index>` with `average_points`,
   `places`, `failed_decisions`. If not, `gauntlet.py` and `gate.py` stop with the runner's
   output: fix the two parsing lines there.
4. The blind ladder after 10/20. The mini simulator's ladder is a guess; `probe.py` reads the
   real one from `state.config.blinds`.
5. The kit runs on macOS. The setup skill offers a local install and only excludes native
   Windows.
