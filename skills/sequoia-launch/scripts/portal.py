"""Read-only view of the team portal, with the API key the setup skill saved.

    python3.12 skills/sequoia-launch/scripts/portal.py          # competition, team, uploads, health, rounds
    python3.12 skills/sequoia-launch/scripts/portal.py --all    # the same, nothing cut

Only GET requests, only to the organizers' site. The key is read from the file and sent in the
header; it is never printed. Run this on the Mac: the key must not go to the build machine.
The endpoints are the ones the team page itself loads (seen 2026-11-12); they are not documented,
so an error on one is shown and the others still print.
"""

import json
import sys
import urllib.request
from pathlib import Path

SITE = "https://pokerbot.sequoiacap.com/tournament/api"
KEY = Path.home() / ".config" / "no-limit-2026" / "api-key"
CUT = 4000  # characters per section unless --all


def get(path: str):
    request = urllib.request.Request(
        f"{SITE}/{path}", headers={"Authorization": f"Bearer {KEY.read_text().strip()}", "User-Agent": "curl"})  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            return json.load(reply)
    except Exception as error:  # one failing endpoint must not hide the others
        return {"error": f"{type(error).__name__}: {error}"}


def show(title: str, value) -> None:
    text = json.dumps(value, indent=1, default=str)
    if "--all" not in sys.argv and len(text) > CUT:
        text = text[:CUT] + f"\n... cut at {CUT} of {len(text)} characters: --all shows everything"
    print(f"== {title}\n{text}\n")


def main() -> None:
    if not KEY.is_file():
        sys.exit(f"no API key at {KEY}: run /no-limit-2026-setup first")
    teams = get("auth/api-key").get("teams") or []
    if not teams:
        sys.exit("the key is not on a team (or it is wrong or expired)")
    team, competition = teams[0]["team_id"], teams[0]["competition_id"]
    about = get(f"competitions/{competition}")
    wanted = ("name", "status", "frozen", "variant", "variant_announced_at", "round_weighting", "submission_cooldown_seconds")  # fmt: skip
    show("competition", {key: about.get(key) for key in wanted} if "error" not in about else about)
    mine = get(f"teams/{team}")
    show("team", {key: mine.get(key) for key in ("name", "active_submission_id")} if "error" not in mine else mine)
    show("uploads (submissions)", get(f"teams/{team}/submissions"))
    show("health (decisions, missed decisions, restarts, errors)", get(f"teams/{team}/health"))
    show("rounds and practice runs (tournaments)", get(f"competitions/{competition}/tournaments"))


if __name__ == "__main__":
    main()
