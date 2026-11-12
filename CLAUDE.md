# Instructions for Claude sessions in this repo

Bot and tooling for NO LIMIT '26, Sequoia's poker bot tournament (Pittsburgh regional
2026-11-12, finals 2026-11-15). Remote: `unio207/pokerbot`. `README.md` has the detail.
Run `git pull` first: a session on 2026-11-12 worked from a checkout 49 commits behind.

## Stack

- Python 3.12, standard library only. No third-party packages, no torch, no build step.
- The bot to upload is `bots/final/agent.py`, one file, generated from `tools/core_agent.py`
  by `tools/build.py`. Edit the core, never `bots/*/agent.py`.
- The web page in `ui/` is plain HTML, CSS and JS served by `ui/server.py`. No npm.

## Environment

- No environment of our own and no dependency file: nothing to install.
- With the organizers' starter kit: the kit's venv, `../starter-kit/.venv/bin/python` (Python
  3.12 exactly). The kit unlocks only at the variant announcement.
- Without the kit: system `python3.12` and the mini simulator (`--mini`); `devtest/shim/`
  stands in for the SDK.
- Claude Code runs on the Mac with a local kit. The team build machine (Ubuntu,
  `ssh no-limit-2026-build`, repo by `scp` to `~/work/pokerbot`, kit at
  `~/work/starter-kit`, no git credentials) is for timing.

## Data paths

- No datasets. Equity and variant tables are embedded in `tools/core_agent.py`.
- Kit search order (`practice.find_kit`): PATH, `./starter-kit`, `../starter-kit`,
  `~/work/starter-kit`.
- Generated and ignored by git: `hand-history/`, `practice-runs/`, `.claude/`, and on event
  day `rules_card.json`, `rules_card.*.json`, `v0/`, `v1/`, ..., `skills/sequoia-launch/.t0`.

## Run commands

```bash
python3.12 tools/build.py --check                      # bots/ match the core
python3.12 practice.py bots/final --mini               # upload check + five line-ups, no kit
python3.12 tools/fuzz.py bots/final --states 20000     # random and malformed states
python3.12 ui/server.py                                # practice page at http://127.0.0.1:8765/

K=skills/sequoia-launch/scripts
python3.12 $K/gate.py bots/final                       # safety gate: PASS or FAIL
python3.12 $K/gauntlet.py bots/final --vs starter      # A/B on the same seeds, ± error
```

There is no test suite. The checks are `gate.py`, `tools/fuzz.py` and `tools/bot_tests.py`.

## Current state (2026-11-12)

- `bots/final` passes the gate on the mini simulator; 24.55 ± 0.19 points per table over
  nine line-ups (n = 9,000, par 12.5). Details: `skills/STATE.md`.
- Nothing has run against the real kit. The variant is not announced.
- Skills: `skills/sequoia-launch` (variant announced to active bot, on a clock),
  `skills/competition-build` (the short checklist), `skills/mid-round-iterate` (between
  rounds). Research index: `skills/RESEARCH_NOTES.md`.
- `/sequoia-launch`, `/competition-build` and `/mid-round-iterate` work only after the
  skills are linked, once per clone (`.claude/` is ignored by git):
  `mkdir -p .claude/skills && for s in sequoia-launch competition-build mid-round-iterate; do ln -sfn ../../skills/$s .claude/skills/$s; done`
- The 13 float knobs of `final` are in `SETTINGS` in `tools/core_agent.py`, which overrides
  `PROFILES["final"]`. Change them there; `tools/field_fit.py --sweep` reads the same table.

## Rules for this repo

- No upload and no active-bot switch without Henry's go in that session.
- Do not edit `starter/`, `sparring/` or `zoo/` bots during an event: they are the fixed
  opponents.
- Never print or copy the competition API key; never put it on the build machine.
- Mini-simulator numbers are always labelled as such. They are not kit numbers.

## Practice page version

The practice web page (`ui/`) shows its version at the top right, with a menu of every
version and when it was made. The list is `VERSIONS` at the top of `ui/app.js`, newest
first.

Whenever you change the page, add a new entry at the top of `VERSIONS` in the same commit:

- **What counts:** any change to `ui/index.html`, `ui/app.js` or `ui/style.css`, and any
  change to `ui/server.py` or the simulator that alters what the page shows or does.
- **The entry:** the next number (`v4` after `v3`), the exact time with its UTC offset from
  `date -Iminutes` (for example `2026-11-11T02:13-05:00`), and one plain line saying what
  changed.
- **One entry per merged change**, not per edit: several edits made together share one
  version. Never renumber or delete earlier entries.
- Tell the user the new version number when you report the change, so they can check that
  the page they have open is the current one.
