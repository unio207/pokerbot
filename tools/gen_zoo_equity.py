"""Offline heads-up equity grid for standalone zoo bots (no runtime dependency).

python3 tools/gen_zoo_equity.py --samples 5000 --output /private/tmp/pokerbot-zoo-equity.json
python3 tools/gen_zoo_equity.py --from-json /private/tmp/pokerbot-zoo-equity.json --embed-to-bots

Opponent ranges are whole hand classes ordered by starter's random-hand equity;
they are approximations, not solved Nash ranges. Include the cutoff class, then
sample uniformly among its concrete, unblocked combinations. Each cell has its
own deterministic seed. Ties count as half a win. By default only the requested
JSON output is written. --embed-to-bots also updates the two existing D/E inline
tables and zoo/strategy_equity_provenance.json. --from-json skips simulation.
This tool may import the local shim; zoo bots may not.
"""

import argparse
import ast
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parent.parent
WIDTHS = (0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.0)
DECK = tuple(rank + suit for rank in "AKQJT98765432" for suit in "cdhs")


def load_starter():
    sys.path.insert(0, str(ROOT / "devtest" / "shim"))
    spec = importlib.util.spec_from_file_location("zoo_equity_starter", ROOT / "starter" / "agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def embed_to_bots(payload):
    """Replace only the two AST-delimited assignments, preserving all strategy code."""
    if payload.get("schema") != "pokerbot-zoo-equity-v1" or payload.get("range_widths") != list(WIDTHS):
        raise ValueError("Unrecognized equity grid schema or range widths")
    equity, ties = payload["equities"], payload["tie_rates"]
    if len(equity) != 169 or set(equity) != set(ties):
        raise ValueError("Expected the same 169 hand classes in both tables")
    for key, row in equity.items():
        if len(row) != 7 or len(ties[key]) != 7:
            raise ValueError(f"Wrong column count for {key}")
        for q, t in zip(row, ties[key]):
            if not (0 <= q <= 1 and 0 <= t <= 1 and q-t/2 >= -1e-9 and 1-q-t/2 >= -1e-9):
                raise ValueError(f"Invalid win/tie/loss probabilities for {key}")
    assignments = {
        "_RANGE_EQUITY": {key: tuple(row) for key, row in equity.items()},
        "_TIE_RATE": {key: tuple(row) for key, row in ties.items()},
    }
    updates = []
    for name in ("codex_shove_aware_1", "codex_adaptive_icm_1"):
        path = ROOT / "zoo" / name / "agent.py"
        source = path.read_text()
        lines = source.splitlines(keepends=True)
        spans = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
                if target in assignments:
                    if target in spans:
                        raise ValueError(f"Duplicate assignment {target} in {path}")
                    spans[target] = (node.lineno - 1, node.end_lineno)
        if spans.keys() != assignments.keys():
            raise ValueError(f"Missing inline equity assignments in {path}")
        for target, (start, end) in sorted(spans.items(), key=lambda item: item[1][0], reverse=True):
            lines[start:end] = [f"{target} = {assignments[target]!r}\n"]
        updated = "".join(lines)
        ast.parse(updated)
        updates.append((path, updated))
    # Prepare and validate every replacement before changing any existing file.
    provenance = {key: payload[key] for key in ("schema", "provenance", "range_widths", "actual_range_fractions")}
    updates.append((ROOT / "zoo" / "strategy_equity_provenance.json", json.dumps(provenance, indent=2) + "\n"))
    for path, source in updates:
        path.write_text(source)
        print(f"Updated {path.relative_to(ROOT)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--seed", default="pokerbot-zoo-equity-v1")
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/pokerbot-zoo-equity.json"))
    parser.add_argument("--from-json", type=Path, help="Read a saved grid instead of running Monte Carlo")
    parser.add_argument("--embed-to-bots", action="store_true", help="Update existing D/E inline tables and provenance")
    args = parser.parse_args()
    if args.from_json:
        payload = json.loads(args.from_json.read_text())
        if args.embed_to_bots:
            embed_to_bots(payload)
        else:
            print(f"Loaded {len(payload['equities'])} classes; add --embed-to-bots to install the grid")
        return
    if args.samples < 1:
        parser.error("--samples must be positive")
    starter = load_starter()
    combinations = {}
    for a, b in itertools.combinations(DECK, 2):
        combinations.setdefault(starter._class_key(a, b), []).append((a, b))
    classes = sorted(starter._EQUITY, key=lambda key: (-starter._EQUITY[key], key))
    ranges, fractions = [], []
    for width in WIDTHS:
        selected = []
        for key in classes:
            selected.extend(combinations[key])
            if len(selected) >= math.ceil(1326 * width):
                break
        ranges.append(selected)
        fractions.append(len(selected) / 1326)

    equities, tie_rates, unblocked_counts = {}, {}, {}
    rank = starter.hand_rank
    for number, key in enumerate(classes, 1):
        hero = combinations[key][0]
        hero_set = set(hero)
        remaining = tuple(card for card in DECK if card not in hero_set)
        row, ties_row, counts = [], [], []
        for column, opponent_range in enumerate(ranges):
            eligible = [opponent for opponent in opponent_range if not hero_set.intersection(opponent)]
            boards = [tuple(card for card in remaining if card not in opponent) for opponent in eligible]
            digest = hashlib.sha256(f"{args.seed}:{key}:{column}".encode()).digest()
            rng = random.Random(int.from_bytes(digest, "big"))
            wins = 0.0
            ties = 0
            for _ in range(args.samples):
                index = rng.randrange(len(eligible))
                board = tuple(rng.sample(boards[index], 5))
                ours = rank(hero + board)
                theirs = rank(eligible[index] + board)
                wins += 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0
                ties += ours == theirs
            row.append(round(wins / args.samples, 6))
            ties_row.append(round(ties / args.samples, 6))
            counts.append(len(eligible))
        equities[key] = row
        tie_rates[key] = ties_row
        unblocked_counts[key] = counts
        print(f"{number}/169 {key}: {row}", flush=True)

    payload = {
        "schema": "pokerbot-zoo-equity-v1",
        "provenance": {
            "generator": "tools/gen_zoo_equity.py",
            "starter_sha256": hashlib.sha256((ROOT / "starter" / "agent.py").read_bytes()).hexdigest(),
            "samples_per_cell": args.samples,
            "total_trials": len(classes) * len(WIDTHS) * args.samples,
            "seed": args.seed,
            "evaluator": "starter.agent.hand_rank, pure Python, standard holdem",
            "ordering": "starter._EQUITY descending, class key ascending on ties",
            "sampling": "uniform unblocked opponent combinations; uniform five-card boards; ties half",
            "range_note": "whole boundary class included; approximate strength ordering, not Nash ranges",
            "max_standard_error": 0.5 / math.sqrt(args.samples),
            "runtime_margin_guidance": "Use >=0.02 heads-up equity margin and >=0.03 for model uncertainty; multiway requires extra caution.",
        },
        "range_widths": list(WIDTHS),
        "actual_range_fractions": fractions,
        "unblocked_combo_counts": unblocked_counts,
        "equities": equities,
        "tie_rates": tie_rates,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(classes)} x {len(WIDTHS)} cells to {args.output}", flush=True)
    if args.embed_to_bots:
        embed_to_bots(payload)


if __name__ == "__main__":
    main()
