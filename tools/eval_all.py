"""Rank every strategy in the repo on the mini simulator, in every variant it plays.

    python3.12 tools/eval_all.py run league 3000 --seed eval1 --out eval-results/league.json.gz
    python3.12 tools/eval_all.py run weak 600 --seed eval1 --out eval-results/weak.json.gz
    python3.12 tools/eval_all.py report eval-results/league.json.gz eval-results/weak.json.gz \
        --pair bots/final bots/adaptive

Candidates: bots/* (the core profiles), starter and every zoo/* bot except _template.

league  Each table seats 8 candidates drawn at random (without replacement), so every
        strategy meets every other. `tables` is per variant.
weak    Hero + 7 opponents drawn (with replacement) from the sparring bots and starter.
        The opponents, seats and deals depend only on (seed, variant, table number), so
        every hero sees the same tables and heroes can be compared pairwise
        (`report --pair A B`). `tables` is per hero per variant.

Rules: 2,000 chips, blinds up every 20 hands, 250-hand cap, 50/30/20 points (par 12.5),
1 ms per decision with a 100 ms bank. Results are raw per-table rows:
{variant: {bot: [[table, points, place, failures, decisions, dealt, vpip, pfr, max_ns], ...]}}.
The mini simulator is unofficial; the organizers' kit is the authority.
"""

import argparse
import gzip
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "devtest"))
import mini_sim  # noqa: E402

CANDS = ([f"bots/{p.parent.name}" for p in sorted(ROOT.glob("bots/*/agent.py"))] + ["starter"] +
         [f"zoo/{p.parent.name}" for p in sorted(ROOT.glob("zoo/*/agent.py")) if p.parent.name != "_template"])
WEAK = [f"sparring/{n}" for n in ("calling_station", "check_or_fold", "min_raiser", "nit", "shover")] + ["starter"]
RULES = dict(stack=2000, decision_ms=1, bank_ms=100, hand_cap=250, hands_per_level=20,
             payouts=[50, 30, 20], random_payouts=False)
VARS = ["holdem", "omaha", "short_deck", "irish", "auction", "discard_reveal"]


# ---------------------------------------------------------------------- run
def job(args):
    mode, variant, seed, number, hero = args
    draw = random.Random(f"{seed}:{mode}:{number}:lineup")
    bots = draw.sample(CANDS, 8) if mode == "league" else [hero] + [draw.choice(WEAK) for _ in range(7)]
    spec = {"bots": [str(ROOT / b) for b in bots], "seed": f"{seed}:{mode}:{variant}",
            "rules": RULES | {"variant": variant}, "token": "x"}
    r = mini_sim.play_table(spec, number)
    out = []
    for seat, idx in enumerate(r["order"]):
        if mode == "weak" and idx != 0:
            continue
        lat = r["latency"][seat]
        out.append((bots[idx], r["points"][seat], r["places"][seat], r["failures"][seat], r["decisions"][seat],
                    r["dealt"][seat], r["vpip"][seat], r["pfr"][seat], max(lat) if lat else 0))
    return variant, number, out


def run(a):
    variants = a.variants or sorted(mini_sim.VARIANTS)
    jobs = []
    for v in variants:
        for n in range(a.tables):
            jobs += [(a.mode, v, a.seed, n, None)] if a.mode == "league" else [(a.mode, v, a.seed, n, h) for h in CANDS]
    random.Random(0).shuffle(jobs)  # spread slow variants across workers
    res, t0 = {}, time.time()
    with ProcessPoolExecutor(a.workers) as pool:
        for i, (v, n, out) in enumerate(pool.map(job, jobs, chunksize=4)):
            for bot, *row in out:
                res.setdefault(v, {}).setdefault(bot, []).append([n] + row)
            if i % 500 == 0:
                print(f"{i}/{len(jobs)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    save(a.out, res)
    print(f"done {len(jobs)} tables in {time.time() - t0:.0f}s -> {a.out}", file=sys.stderr)


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, separators=(",", ":"))
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(text.encode(), mtime=0))
    else:
        path.write_text(text)


def load(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


# ---------------------------------------------------------------------- report
def ms(xs):
    n = len(xs)
    m = sum(xs) / n
    return m, (math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else float("nan"))


def table(res, title):
    bots = sorted({b for v in res.values() for b in v})
    rows = []
    for b in bots:
        cells, means, ses = [], [], []
        fails = dec = dealt = vpip = pfr = first = n = 0
        for v in VARS:
            r = res.get(v, {}).get(b)
            if not r:
                cells.append("-")
                continue
            m, s = ms([x[1] for x in r])
            means.append(m)
            ses.append(s)
            cells.append(f"{m:.1f}")
            fails += sum(x[3] for x in r)
            dec += sum(x[4] for x in r)
            dealt += sum(x[5] for x in r)
            vpip += sum(x[6] for x in r)
            pfr += sum(x[7] for x in r)
            first += sum(x[2] == 1 for x in r)
            n += len(r)
        avg = sum(means) / len(means)
        se = math.sqrt(sum(s * s for s in ses)) / len(ses)
        rows.append((avg, se, b, cells, min(means), 100 * first / n, 100 * vpip / max(1, dealt),
                     100 * pfr / max(1, dealt), 100 * fails / max(1, dec), n))
    rows.sort(reverse=True)
    head = ["bot", "avg", "±SE"] + VARS + ["worst", "1st%", "VPIP%", "PFR%", "fail%", "tables"]
    print(f"\n## {title}\n")
    print("| " + " | ".join(head) + " |")
    print("|---|" + "---:|" * (len(head) - 1))
    for avg, se, b, cells, worst, fi, vp, pf, fl, n in rows:
        print("| " + " | ".join([f"`{b}`", f"{avg:.1f}", f"{se:.2f}"] + cells +
                                [f"{worst:.1f}", f"{fi:.1f}", f"{vp:.1f}", f"{pf:.1f}", f"{fl:.2f}", str(n)]) + " |")


def paired(res, a, b):
    print(f"\nPaired `{a}` minus `{b}` (same tables):\n")
    print("| variant | Δ points | ±SE |\n|---|---:|---:|")
    for v in VARS:
        if a not in res.get(v, {}) or b not in res.get(v, {}):
            continue
        ra = {x[0]: x[1] for x in res[v][a]}
        rb = {x[0]: x[1] for x in res[v][b]}
        m, s = ms([ra[k] - rb[k] for k in ra if k in rb])
        print(f"| {v} | {m:+.2f} | {s:.2f} |")


def report(a):
    if a.league:
        table(load(a.league), "League (8 random candidates per table)")
    if a.weak:
        weak = load(a.weak)
        table(weak, "Weak field (hero + 7 sparring/starter bots)")
        for x, y in a.pair or []:
            paired(weak, x, y)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("mode", choices=["league", "weak"])
    r.add_argument("tables", type=int, help="league: per variant; weak: per hero per variant")
    r.add_argument("--seed", default="eval1")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    r.add_argument("--out", type=Path, required=True, help=".json or .json.gz")
    r.add_argument("--variants", nargs="*", help="default: every variant the simulator has")
    p = sub.add_parser("report")
    p.add_argument("league", nargs="?", help="league results ('' to skip)")
    p.add_argument("weak", nargs="?", help="weak-field results")
    p.add_argument("--pair", nargs=2, action="append", metavar=("A", "B"), help="paired weak-field difference")
    a = ap.parse_args()
    run(a) if a.cmd == "run" else report(a)


if __name__ == "__main__":
    main()
