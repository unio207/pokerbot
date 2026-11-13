"""A finished run's result against the field, from the portal. Read-only, like portal.py.

    python3.12 skills/sequoia-launch/scripts/results.py            # every run so far, one line each
    python3.12 skills/sequoia-launch/scripts/results.py 268dab24   # one run, and its ten best teams' names

Per run: our points per table with the portal's margin (about two standard errors), our rank
among the teams that did not forfeit, the field median and our points minus it, the top-ten
mean and our share of firsts. Compare versions on "minus median": the field's level moves
between runs. The names are the arguments for tools/history/chipflow.py, opens.py, headsup.py
and freq2.py. Run it on the Mac: the key must not go to the build machine.
"""

import statistics
import sys

import portal


def main() -> None:
    team_entry = portal.get("auth/api-key")["teams"][0]
    team, competition = team_entry["team_id"], team_entry["competition_id"]
    runs = portal.get(f"competitions/{competition}/tournaments")["items"]
    wanted = sys.argv[1] if len(sys.argv) > 1 else ""
    print("run       kind      tables  points ± margin  rank      median  minus median  top ten  firsts")
    for run in sorted(runs, key=lambda run: run["created_at"]):
        if not run["id"].startswith(wanted) or not run.get("completed_at"):
            continue
        teams = portal.get(f"tournaments/{run['id']}/results").get("items") or []
        live = sorted((entry for entry in teams if not entry["forfeited"]), key=lambda entry: -entry["average_points"])
        me = next((entry for entry in live if entry["team_id"] == team), None)
        if me is None:
            print(f"{run['id'][:8]}  {run['kind']:8s}  we did not play it")
            continue
        median = statistics.median(entry["average_points"] for entry in live)
        top = sum(entry["average_points"] for entry in live[:10]) / 10
        print(f"{run['id'][:8]}  {run['kind']:8s} {me['tables']:6d}  {me['average_points']:6.2f} ± {me['margin_of_error']:.2f}"
              f"  {live.index(me) + 1:3d} of {len(live):3d}  {median:6.2f}  {me['average_points'] - median:+12.2f}"
              f"  {top:7.2f}  {me['places'][0] / me['tables']:6.1%}")  # fmt: skip
        if wanted:
            print("ten best:", " ".join(f'"{entry["team_name"]}"' for entry in live[:10] if entry["team_id"] != team))


if __name__ == "__main__":
    if not portal.KEY.is_file():
        sys.exit(f"no API key at {portal.KEY}: run /no-limit-2026-setup first")
    main()
