# STATE: hand-off from sequoia-launch to the iteration skill

Updated: <date, T+mm>   Event: <Pittsburgh regional | finals>   Machine: <Mac | build machine>

## Active bot

| Version | Folder | Uploaded at | Active | What it is |
| --- | --- | --- | --- | --- |
| v0 | `v0/` | T+ | yes/no | |

Upload to ready: <seconds, measured on the first upload>. Rollback target: <version>.

## Variant

One paragraph from the Rules Card (`rules_card.json`): hole cards, phases, showdown rule,
payouts, anything drawn per table. Open questions that are still open.

## Knobs in the active version

Copy `PROFILES["final"]` and the `SETTINGS` table from `tools/core_agent.py` as built into
the active version, and name the `VARIANTS` entry the conversion added or changed.

## Gate

Last `gate.py` output for the active version: runner, machine, the timing line, PASS/FAIL.

## Gauntlet baseline

Runner (kit or mini), machine, seed, n per line-up, each line-up's points ± error, the total,
tables per minute, and the three detectable-difference lines. Promotion rule in force.

## Practice runs and rounds

| When | Version | Avg points | 1st / 2nd / 3rd | Missed | Restarts | Note |
| --- | --- | --- | --- | --- | --- | --- |

## Known weaknesses

## First experiments to try

One line each: the knob or rule, the expected direction, the line-up that should show it.

## Log

T+mm: what happened, one line.
