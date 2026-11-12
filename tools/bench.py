"""Benchmark heroes against fixed line-ups with standard errors and paired comparisons.

    python3 tools/bench.py --hero bots/final --hero starter --lineup all --tables 1000 \
        --seed tune --rules both [--baseline starter] [--json out.json] [--latency]

A run is (rules, lineup, hero): an 8-seat table with the hero in slot 0 and 7 opponents,
`--tables` times. Seats and deals depend only on (seed, table number), so two heroes see
identical tables and their per-table points can be differenced (paired). Bots that use the
global `random` get a per-table seed, as in ui/server.py. `--latency` runs in one process
(parallel timing is distorted) and reports p50 / p99.9 / max decision time in microseconds.
Output: a GitHub-markdown table on stdout, progress on stderr.
"""

import argparse
import gc
import json
import math
import multiprocessing
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "devtest"))
import mini_sim  # noqa: E402

LINEUPS = {
    "mixed": ["starter", "starter", "sparring/nit", "sparring/shover", "sparring/calling_station",
              "sparring/min_raiser", "sparring/check_or_fold"],
    "passive": ["sparring/check_or_fold"] * 4 + ["sparring/nit"] * 3,
    "aggressive": ["sparring/shover"] * 3 + ["sparring/min_raiser"] * 2 + ["starter"] * 2,
    "starters": ["starter"] * 7,
    # Default-assistant-shaped field (overnight zoo fillers + a couple of Claude archetypes).
    "ai_field": [
        "zoo/gpt_default_1", "zoo/gpt_limp_station_1", "zoo/gpt_jamming_1", "zoo/gpt_any_ace_1",
        "zoo/gpt_draw_chaser_1", "zoo/claude_tourist_1", "zoo/codex_default_1",
    ],
}
ZOO = [f"bots/{name}" for name in ("chart_nash", "steal_heavy", "icm_survival", "push_fold",
                                   "equity_bucket", "adaptive", "final")] + ["starter"]
RULES = {"kit": (20, 250), "published": (25, 200)}  # name -> (hands_per_level, hand_cap)
_AGENTS: dict[str, object] = {}  # per-process cache


def make_rules(name):
    per_level, cap = RULES[name]
    return argparse.Namespace(stack=2000, payouts=(50, 30, 20), decision_ms=1, bank_ms=100,
                              hand_cap=cap, hands_per_level=per_level)


def norm(path):
    """Repo-relative folder string for a bot (stable label and cache key)."""
    full = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        return str(full.relative_to(ROOT))
    except ValueError:
        return str(full)


def agent(path):
    if path not in _AGENTS:
        _AGENTS[path] = mini_sim.load_agent(ROOT / path)
    return _AGENTS[path]


def opponents(lineup, hero):
    """Seven opponent folders for this line-up, or None if the line-up is unavailable."""
    if lineup != "zoo":
        return LINEUPS[lineup]
    if hero in ZOO:
        return [bot for bot in ZOO if bot != hero]
    return ZOO[:-1]


# ---------------------------------------------------------------------- worker
def run_chunk(job):
    """Play tables [start, end) for one run; return per-table hero results."""
    key, hero, opps, seed, start, end, keep_latency = job
    rules = make_rules(key[0])
    players = [agent(hero)] + [agent(path) for path in opps]
    out, latency, count, worst = [], [], 0, 0
    gc.collect()
    gc.disable()
    try:
        for number in range(start, end):
            rng = random.Random(f"{seed}:{number}")
            order = list(range(len(players)))
            rng.shuffle(order)
            random.seed(f"{seed}:{number}:bots")
            table = mini_sim.Table([players[i] for i in order], rng, rules, f"bench-{number}")
            points = table.play()
            seat = order.index(0)
            out.append((points[seat], table.places()[seat], table.failures[seat], table.bank[seat]))
            times = table.latency[seat]
            count += len(times)
            worst = max([worst] + times)
            if keep_latency:
                latency.extend(times)
            gc.collect(1)
    finally:
        gc.enable()
    return key, hero, start, out, count, worst, latency


# ---------------------------------------------------------------------- statistics
def mean_se(values):
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, float("nan")
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(var / n)


def summarize(rows, latency):
    points = [r[0] for r in rows]
    mean, se = mean_se(points)
    n = len(rows)
    places = [sum(r[1] == p for r in rows) / n * 100 for p in (1, 2, 3)]
    info = dict(points=mean, se=se, first=places[0], second=places[1], third=places[2],
                fails=sum(r[2] for r in rows), min_bank=min(r[3] for r in rows), tables=n,
                table_points=points)
    if latency is not None:
        times = sorted(latency)
        if times:
            info["latency_us"] = {"p50": times[len(times) // 2] / 1000,
                                  "p99.9": times[min(len(times) - 1, int(len(times) * 0.999))] / 1000}
    return info


def combine(items):
    """Unweighted mean of (mean, se) pairs; SE = sqrt(sum se^2) / k."""
    k = len(items)
    return sum(m for m, _ in items) / k, math.sqrt(sum(s * s for _, s in items)) / k


# ---------------------------------------------------------------------- main
def parse():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hero", action="append", required=True, help="Bot folder; repeat for several.")
    ap.add_argument("--baseline", help="Hero to compare the others against (default: last --hero).")
    ap.add_argument("--lineup", nargs="+", default=["all"],
                    help="mixed passive aggressive starters ai_field zoo | all")
    ap.add_argument("--tables", type=int, default=200)
    ap.add_argument("--seed", default="bench")
    ap.add_argument("--rules", choices=["kit", "published", "both"], default="kit")
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--json", type=Path, help="Also write all results (with per-table points) here.")
    ap.add_argument("--latency", action="store_true", help="Single process; report p50/p99.9/max in us.")
    return ap.parse_args()


def main():
    args = parse()
    heroes = list(dict.fromkeys(norm(h) for h in args.hero))
    for hero in heroes:
        if not (ROOT / hero / "agent.py").is_file():
            sys.exit(f"{hero} has no agent.py")
    baseline = norm(args.baseline) if args.baseline else (heroes[-1] if len(heroes) > 1 else None)
    names = list(LINEUPS) + ["zoo"] if "all" in args.lineup else args.lineup
    if "zoo" in names and (missing := [b for b in ZOO if not (ROOT / b / "agent.py").is_file()]):
        print(f"warning: skipping zoo, missing {', '.join(missing)}", file=sys.stderr)
        names.remove("zoo")
    rules_names = list(RULES) if args.rules == "both" else [args.rules]
    procs = 1 if args.latency else args.procs

    jobs, step = [], max(1, min(25, args.tables // (procs * 4) or 1))
    for rname in rules_names:
        for lineup in names:
            for hero in heroes:
                for start in range(0, args.tables, step):
                    jobs.append(((rname, lineup, hero), hero, opponents(lineup, hero), args.seed,
                                 start, min(start + step, args.tables), args.latency))
    chunks: dict[tuple, list] = {}
    want = sum(job[5] - job[4] for job in jobs)
    began, done = time.time(), 0
    shown = began
    if procs == 1:
        results = map(run_chunk, jobs)
        pool = None
    else:
        pool = multiprocessing.Pool(procs)
        results = pool.imap_unordered(run_chunk, jobs)
    for key, hero, start, out, count, worst, latency in results:
        chunks.setdefault(key, []).append((start, out, count, worst, latency))
        done += len(out)
        if time.time() - shown > 2 or done == want:
            shown = time.time()
            print(f"[{done}/{want}] {done / (shown - began):.1f} tables/s", file=sys.stderr)
    if pool:
        pool.close()
        pool.join()
    elapsed = time.time() - began
    total = sum(len(c[1]) for v in chunks.values() for c in v)
    print(f"{total} tables in {elapsed:.1f}s = {total / elapsed:.1f} tables/s on {procs} process(es)",
          file=sys.stderr)

    stats = {}
    for key, parts in chunks.items():
        parts.sort(key=lambda p: p[0])
        rows = [r for p in parts for r in p[1]]
        lat = [t for p in parts for t in p[4]] if args.latency else None
        info = summarize(rows, lat)
        if args.latency:
            info.setdefault("latency_us", {})["max"] = max(p[3] for p in parts) / 1000
        stats[key] = info
    for (rname, lineup, hero), info in stats.items():
        base = stats.get((rname, lineup, baseline))
        if baseline and hero != baseline and base:
            diff = [a - b for a, b in zip(info["table_points"], base["table_points"])]
            m, s = mean_se(diff)
            info["delta"], info["delta_se"], info["sig"] = m, s, abs(m) > 3 * s
    report(args, stats, names, rules_names, heroes, baseline)
    if args.json:
        dump = [dict(rules=k[0], lineup=k[1], hero=k[2], **v) for k, v in stats.items()]
        args.json.write_text(json.dumps(dict(seed=args.seed, tables=args.tables, baseline=baseline,
                                             runs=dump), indent=1))


def fmt(x, digits=2):
    return "" if x is None else f"{x:.{digits}f}"


def report(args, stats, names, rules_names, heroes, baseline):
    head = ["rules", "lineup", "hero", "points", "±SE", "1st%", "2nd%", "3rd%", "fails",
            "min bank ms", "Δ vs baseline", "±SE", "sig"]
    if args.latency:
        head += ["p50 µs", "p99.9 µs", "max µs"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for rname in rules_names:
        overall = {h: [] for h in heroes}
        deltas = {h: [] for h in heroes}
        for lineup in names:
            for hero in heroes:
                info = stats.get((rname, lineup, hero))
                if not info:
                    continue
                overall[hero].append((info["points"], info["se"]))
                if "delta" in info:
                    deltas[hero].append((info["delta"], info["delta_se"]))
                row = [rname, lineup, hero, fmt(info["points"]), fmt(info["se"], 3),
                       fmt(info["first"], 1), fmt(info["second"], 1), fmt(info["third"], 1),
                       info["fails"], fmt(info["min_bank"], 1), fmt(info.get("delta"), 3),
                       fmt(info.get("delta_se"), 3), ("**YES**" if info["sig"] else "no") if "sig" in info else ""]
                if args.latency:
                    lat = info.get("latency_us", {})
                    row += [fmt(lat.get(k), 1) for k in ("p50", "p99.9", "max")]
                lines.append("| " + " | ".join(map(str, row)) + " |")
        for hero in heroes:
            if not overall[hero]:
                continue
            m, s = combine(overall[hero])
            dm, ds, sig = None, None, ""
            if deltas[hero] and len(deltas[hero]) == len(overall[hero]):
                dm, ds = combine(deltas[hero])
                sig = "**YES**" if abs(dm) > 3 * ds else "no"
            row = [rname, "**overall**", hero, fmt(m), fmt(s, 3), "", "", "", "", "", fmt(dm, 3), fmt(ds, 3), sig]
            lines.append("| " + " | ".join(row + [""] * (len(head) - len(row))) + " |")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
