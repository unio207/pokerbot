"""Check every bot in zoo/ and report what kind of opponent each one is.

    python3.12 tools/check_zoo.py            # all zoo bots
    python3.12 tools/check_zoo.py zoo/my_bot # just one

For each bot: the upload check, then a short match on the unofficial mini simulator
against the sparring bots. Reports points per table, failed decisions, decision time
and a status:

    OK       plays without failed decisions
    FLAKY    plays, but some decisions failed (kept: real fields contain these)
    BROKEN   will not import or pass the upload check (fix or remove)
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = [sys.executable, str(ROOT / "devtest" / "mini_sim.py")]
FIELD = [ROOT / "sparring" / name for name in
         ("nit", "shover", "calling_station", "min_raiser", "check_or_fold", "nit", "shover")]  # fmt: skip
TABLES = 60


def main() -> None:
    if len(sys.argv) > 1:
        bots = [Path(argument).resolve() for argument in sys.argv[1:]]
    else:
        bots = sorted(p.parent for p in (ROOT / "zoo").glob("*/agent.py") if p.parent.name != "_template")
    if not bots:
        sys.exit("No zoo bots yet. Copy zoo/_template to zoo/<name> and edit it.")
    print(f"{'bot':32s} {'status':7s} {'pts/table':>9s} {'1st':>5s} {'failed':>7s} {'p99.9 µs':>9s}")
    broken = 0
    for bot in bots:
        name = bot.name[:32]
        checked = subprocess.run(SIM + ["check", str(bot / "agent.py")], capture_output=True, text=True)
        if checked.returncode != 0:
            problems = "; ".join(json.loads(checked.stdout)["problems"]) if checked.stdout else checked.stderr
            print(f"{name:32s} BROKEN  {problems}")
            broken += 1
            continue
        played = subprocess.run(
            SIM + ["play", str(bot), *map(str, FIELD), "--tables", str(TABLES), "--seed", "zoo"],
            capture_output=True, text=True,
        )  # fmt: skip
        if played.returncode != 0:
            last = (played.stderr.strip().splitlines() or ["did not run"])[-1]
            print(f"{name:32s} BROKEN  {last}")
            broken += 1
            continue
        entry = json.loads(played.stdout)["bots"][f"{bot.name}#0"]
        failed = entry["failed_decisions"]
        firsts = entry["places"].get("1", 0) / TABLES
        status = "FLAKY" if failed else "OK"
        print(f"{name:32s} {status:7s} {entry['average_points']:9.1f} {firsts:5.0%} {failed:7d}"
              f" {entry['latency_us']['p99.9']:9.0f}")  # fmt: skip
    print(f"\n{len(bots)} bots, {broken} broken. Par is 12.5 points per table.")
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
