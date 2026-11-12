"""Stage 6: fixed line-ups, fixed seeds, points per table with a standard error and n.

    python gauntlet.py v1                      # baseline of one bot
    python gauntlet.py v2 --vs v1              # A/B on the same deals: difference and verdict
    python gauntlet.py v2 --vs v1 --tables 400 --seed fresh1

Line-ups are practice.py's five plus a zoo field when zoo/ has bots. Each line-up is split
into --batches runs with seeds "<seed>-<i>"; the standard error comes from the spread of the
batch means, so it needs nothing from the runner beyond its summary. With --vs both bots play
the same seeds and the error is that of the per-batch difference, which is smaller than the
error of either score. Uses the kit when installed, else the mini simulator (labelled).
"""

import argparse
import math
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import common


def lineups(bot):
    result = common.practice.lineups(bot)
    zoo = sorted(p.parent for p in (common.ROOT / "zoo").glob("*/agent.py") if p.parent.name != "_template")
    for start in range(0, len(zoo), 7):  # every zoo bot sits in one line-up; the last one wraps around
        result[f"zoo field {start // 7 + 1}"] = [bot] + [zoo[(start + i) % len(zoo)] for i in range(7)]
    return result


def play(command, bots, bot, tables, seed, extra):
    """Our average points per table and failed decisions in one runner call."""
    result = common.practice.run(command, ["play", *map(str, bots), "--tables", str(tables), "--seed", seed, "--no-history", *extra])
    summary = common.summary(result)
    mine = [summary[f"{path.name}#{index}"] for index, path in enumerate(bots) if path == bot]
    return sum(e["average_points"] for e in mine) / len(mine), sum(e["failed_decisions"] for e in mine)


def measure(command, bot, options, extra):
    """{line-up: [batch means]}, failed decisions."""
    per_batch = max(1, options.tables // options.batches)
    jobs = [(name, bots, f"{options.seed}-{index}") for name, bots in lineups(bot).items() for index in range(options.batches)]
    with ThreadPoolExecutor(options.jobs) as pool:
        results = list(pool.map(lambda job: play(command, job[1], bot, per_batch, job[2], extra), jobs))
    scores: dict[str, list[float]] = {}
    for (name, _, _), (points, _) in zip(jobs, results):
        scores.setdefault(name, []).append(points)
    return scores, sum(failed for _, failed in results), per_batch


def mean_error(values):
    return statistics.mean(values), statistics.stdev(values) / math.sqrt(len(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("bot")
    parser.add_argument("--vs", help="Incumbent to compare against on the same seeds.")
    parser.add_argument("--tables", type=int, default=200, help="Tables per line-up per bot.")
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--seed", default="gauntlet", help="Promote only after a second run on a fresh seed.")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2), help="Runner calls in parallel.")
    parser.add_argument("--mini", action="store_true")
    options = parser.parse_args()
    command, engine = common.runner(options.mini)
    card = common.card()
    # The kit takes payouts from its own config; the mini simulator has to be told.
    # One worker per call: --jobs already runs the calls side by side.
    extra = (["--payouts", *map(str, card["config"]["payouts"]), "--workers", "1", *common.mini_args(card, engine)]
             if engine == "mini" else [])  # fmt: skip
    bots = [common.bot_dir(options.bot)] + ([common.bot_dir(options.vs)] if options.vs else [])
    print(f"runner: {engine}" + (f"   (UNOFFICIAL mini simulator: {card['variant'].get('mini_name') or 'holdem'})" if engine == "mini" else "")
          + f"   seed {options.seed}   payouts {card['config']['payouts']}   jobs {options.jobs}")  # fmt: skip

    began = time.time()
    measured = [measure(command, bot, options, extra) for bot in bots]
    minutes = (time.time() - began) / 60
    names = list(measured[0][0])
    per_batch = measured[0][2]
    n = per_batch * options.batches
    total = n * len(names) * len(bots)
    for bot, (scores, failed, _) in zip(bots, measured):
        print(f"\n{bot.name}: failed decisions {failed}" + ("   <-- FIX BEFORE ANYTHING ELSE" if failed else ""))
        for name in names:
            mean, error = mean_error(scores[name])
            print(f"  {name:34s} {mean:6.2f} ± {error:.2f}  (n={n} tables)")
        overall = [statistics.mean(scores[name][i] for name in names) for i in range(options.batches)]
        mean, error = mean_error(overall)
        print(f"  {'ALL LINE-UPS (equal weight)':34s} {mean:6.2f} ± {error:.2f}  (n={n * len(names)} tables, par {sum(card['config']['payouts']) / card['config']['players']:.1f})")

    rate = total / minutes
    print(f"\nspeed: {total} tables in {minutes:.2f} min = {rate:.0f} tables/min on this machine ({engine})")
    if not options.vs:
        return
    new, old = measured[0][0], measured[1][0]
    print(f"\n{bots[0].name} minus {bots[1].name}, same seeds:")
    for name in names:
        mean, error = mean_error([a - b for a, b in zip(new[name], old[name])])
        print(f"  {name:34s} {mean:+6.2f} ± {error:.2f}")
    overall = [statistics.mean(new[name][i] - old[name][i] for name in names) for i in range(options.batches)]
    mean, error = mean_error(overall)
    print(f"  {'ALL LINE-UPS':34s} {mean:+6.2f} ± {error:.2f}")
    # Spread of the difference per table played by each bot, for planning how long a test must run.
    sigma = error * math.sqrt(n * len(names))
    print(f"\nsmallest difference this A/B can detect (2.8 standard errors: 5% false alarm, 80% power), at {rate:.0f} tables/min:")
    for budget in (5, 10, 30):
        each = rate * budget / 2
        print(f"  {budget:2d} min: {2.8 * sigma / math.sqrt(each):.2f} points/table  ({each:.0f} tables per bot)")
    verdict = ("BETTER by more than 2 standard errors: rerun with a fresh --seed, promote if it holds" if mean > 2 * error
               else "WORSE by more than 2 standard errors: drop it" if mean < -2 * error
               else "NO DETECTABLE DIFFERENCE at this n: keep the incumbent")  # fmt: skip
    print(f"\nverdict: {verdict}")


if __name__ == "__main__":
    main()
