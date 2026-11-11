"""Run a bot through the upload check and a gauntlet of sparring line-ups.

    python practice.py starter                      # uses the kit's `poker-agent` (official rules)
    python practice.py my_bot --tables 500 --seed 7
    python practice.py my_bot --mini                # no kit installed: unofficial mini simulator

With the organizers' starter kit installed and its environment active, every table is
played by the kit's own runner, so limits and rules are exactly the kit's. `--mini` swaps
in devtest/mini_sim.py, which is a re-implementation for smoke tests only.
"""

import argparse
import json
import math
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPARRING = HERE / "sparring"


def lineups(bot: Path) -> dict[str, list[Path]]:
    s = {path.name: path for path in SPARRING.iterdir() if (path / "agent.py").is_file()}
    starter = HERE / "starter"
    return {
        "mixed field": [bot, s["check_or_fold"], s["min_raiser"], s["calling_station"],
                        s["shover"], s["nit"], s["nit"], starter],  # fmt: skip
        "passive field (many broken bots)": [bot] + [s["check_or_fold"]] * 4 + [s["nit"]] * 3,
        "aggressive field": [bot, s["shover"], s["shover"], s["shover"], s["min_raiser"],
                             s["min_raiser"], starter, starter],  # fmt: skip
        "seven starters": [bot] + [starter] * 7,
        "four of you, four starters": [bot] * 4 + [starter] * 4,
    }


def upload_test(runner: list[str], bot: Path) -> None:
    """Imitate the upload test match: heads-up against check-or-fold, up to 20 hands, 1 ms
    per decision and NO time bank. An upload is rejected if over 10% of decisions fail.
    The kit's `play` always gives the 100 ms bank, so only the mini simulator can do this."""
    result = run(runner, ["play", str(bot), str(SPARRING / "check_or_fold"), "--tables", "300",
                          "--hand-cap", "20", "--bank-ms", "0", "--payouts", "50", "--seed", "upload"])  # fmt: skip
    if result.returncode != 0:
        print(f"upload test: runner failed\n{result.stderr}")
        return
    entry = json.loads(result.stdout)["bots"][f"{bot.name}#0"]
    rate = entry["failed_decisions"] / max(1, entry["decisions"])
    verdict = "WOULD BE REJECTED (over 10%)" if rate > 0.10 else "passes" if rate == 0 else "passes, but not clean"
    print(f"upload test (no time bank, 300 short heads-up matches): {entry['failed_decisions']} of "
          f"{entry['decisions']} decisions failed ({rate:.1%}) -> {verdict}")
    print(f"  slowest decision {entry['latency_us']['max']:.0f} µs; with no bank, anything over 1000 µs fails\n")


def run(runner: list[str], arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(runner + arguments, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("bot", type=Path, help="Directory containing your agent.py.")
    parser.add_argument("--tables", type=int, default=200, help="Tables per line-up.")
    parser.add_argument("--seed", default="practice", help="Same seed = same deals, for A/B runs.")
    parser.add_argument("--mini", action="store_true", help="Use the unofficial mini simulator.")
    parser.add_argument("--runner", help="Override the runner command, e.g. 'poker-agent'.")
    options = parser.parse_args()
    bot = options.bot.resolve()
    if not (bot / "agent.py").is_file():
        sys.exit(f"{bot} has no agent.py")
    if options.runner:
        runner = shlex.split(options.runner)
    elif options.mini:
        runner = [sys.executable, str(HERE / "devtest" / "mini_sim.py")]
    else:
        runner = ["poker-agent"]
    print(f"runner: {' '.join(runner)}" + ("   (UNOFFICIAL rules)" if options.mini else ""))

    try:
        checked = run(runner, ["check", str(bot / "agent.py")])
    except FileNotFoundError:
        sys.exit("`poker-agent` not found. Activate the starter kit's environment, or pass --mini.")
    if checked.returncode != 0:
        sys.exit(f"upload check FAILED:\n{checked.stdout}{checked.stderr}")
    print("upload check: passed\n")

    if options.mini:
        upload_test(runner, bot)

    worst_failures = 0
    for name, bots in lineups(bot).items():
        result = run(runner, ["play", *map(str, bots), "--tables", str(options.tables),
                              "--seed", options.seed, "--no-history"])  # fmt: skip
        if result.returncode != 0:
            print(f"{name}: runner failed\n{result.stderr}")
            continue
        summary = json.loads(result.stdout)["bots"]
        # Entries are labelled "<folder>#<index>"; ours are the ones built from `bot`.
        mine = [summary[f"{path.name}#{index}"] for index, path in enumerate(bots) if path == bot]
        tables = sum(sum(entry["places"].values()) for entry in mine)
        average = sum(e["average_points"] * sum(e["places"].values()) for e in mine) / tables
        places = {}
        for entry in mine:
            for place, count in entry["places"].items():
                places[int(place)] = places.get(int(place), 0) + count
        failures = sum(entry["failed_decisions"] for entry in mine)
        worst_failures = max(worst_failures, failures)
        par = 100 / len(bots)
        # Points per table swing between 0 and 50, so the standard error is roughly 20/sqrt(tables).
        error = 20 / math.sqrt(tables)
        top = " ".join(f"{place}:{100 * places.get(place, 0) / tables:.0f}%" for place in (1, 2, 3))
        print(f"{name}\n  points/table {average:6.2f} ± {error:.1f}   (par {par:.1f})"
              f"   finishes {top}   failed decisions {failures}")  # fmt: skip
        slow = [entry["latency_us"] for entry in mine if "latency_us" in entry]
        if slow:
            print(f"  decision time p99.9 {max(s['p99.9'] for s in slow):.0f} µs,"
                  f" max {max(s['max'] for s in slow):.0f} µs (limit 1000 µs)")  # fmt: skip
    print()
    if worst_failures:
        print("FAILED DECISIONS > 0: each one was played as check/fold. Fix before uploading.")
    else:
        print("No failed decisions.")


if __name__ == "__main__":
    main()
