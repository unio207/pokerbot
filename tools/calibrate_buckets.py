"""Fill the two postflop equity tables embedded in a bot's source file, in place.

    python3 tools/calibrate_buckets.py tools/core_agent.py [--samples 400000] [--procs 8] [--seed 2026]

For random deals (hero hole cards + a 3, 4 or 5 card board, equal thirds) the bot's own
`_bucket_key(hole, board)` names a bucket. Each deal is scored against one opponent hand
with one random runout (1 / 0.5 / 0 via the bot's `hand_rank`), twice:
  _BUCKET_TABLE  opponent is a random hand
  _BUCKET_TIGHT  opponent is a top-30% preflop hand (`_PERCENTILE[_class_key(a, b)] <= 0.30`)
Buckets with fewer than 30 samples are dropped (the bot falls back to a heuristic). The lines
`_BUCKET_TABLE = "..."` and `_BUCKET_TIGHT = "..."` are rewritten in place as `key:permille`
items, keys sorted. `--samples` is the total number of deals, split across worker chunks.
"""

import argparse
import importlib.util
import multiprocessing
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "devtest" / "shim"))

DECK = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]
MARKERS = ("_BUCKET_TABLE", "_BUCKET_TIGHT")
MIN_SAMPLES, TIGHT_CUTOFF = 30, 0.30
_BOT = None


def load_bot(path):
    spec = importlib.util.spec_from_file_location("calibrated_bot", path)
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def score(bot, hole, board, opp, deck):
    full = list(board) + [deck.pop() for _ in range(5 - len(board))]
    ours, theirs = bot.hand_rank(tuple(hole) + tuple(full)), bot.hand_rank(tuple(opp) + tuple(full))
    return 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0


def chunk(job):
    """Run `deals` deals; return {table: {key: [equity_sum, count]}}."""
    global _BOT
    path, deals, seed = job
    _BOT = _BOT or load_bot(path)
    bot, rng = _BOT, random.Random(seed)
    out = {name: {} for name in MARKERS}
    for i in range(deals):
        deck = DECK[:]
        rng.shuffle(deck)
        hole, board = deck[:2], deck[2:2 + (3, 4, 5)[i % 3]]
        rest = deck[2 + len(board):]
        key = bot._bucket_key(tuple(hole), tuple(board))
        for name, tight in zip(MARKERS, (False, True)):
            while True:
                opp = rng.sample(rest, 2)
                if not tight or bot._PERCENTILE[bot._class_key(*opp)] <= TIGHT_CUTOFF:
                    break
            left = [c for c in rest if c not in opp]
            rng.shuffle(left)
            cell = out[name].setdefault(key, [0.0, 0])
            cell[0] += score(bot, hole, board, opp, left)
            cell[1] += 1
    return out


def merge(parts):
    total = {name: {} for name in MARKERS}
    for part in parts:
        for name, table in part.items():
            for key, (value, count) in table.items():
                cell = total[name].setdefault(key, [0.0, 0])
                cell[0] += value
                cell[1] += count
    return total


def rewrite(source, name, items):
    """Replace the single `name = "..."` line; fail if it is not found exactly once."""
    lines = [line for line in source.splitlines() if line.startswith(f'{name} = "')]
    if len(lines) != 1:
        sys.exit(f"error: expected exactly one line starting '{name} = \"', found {len(lines)}")
    new = f'{name} = "{" ".join(items)}"'
    pattern = re.compile(rf'^{name} = ".*"[ \t]*$', re.MULTILINE)
    result, count = pattern.subn(lambda _: new, source)  # callable: no backslash processing
    if count != 1:
        sys.exit(f"error: {name} line is not a single-line string literal")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bot", type=Path)
    ap.add_argument("--samples", type=int, default=400000, help="Total deals.")
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    path = args.bot.resolve()
    source = path.read_text()
    for name in MARKERS:  # fail before the expensive part
        if sum(line.startswith(f'{name} = "') for line in source.splitlines()) != 1:
            sys.exit(f"error: expected exactly one line starting '{name} = \"' in {path}")
    parts = args.procs * 4
    sizes = [args.samples // parts + (i < args.samples % parts) for i in range(parts)]
    jobs = [(str(path), size, args.seed * 1000 + i) for i, size in enumerate(sizes) if size]
    with multiprocessing.Pool(args.procs) as pool:
        total = merge(pool.map(chunk, jobs, chunksize=1))
    for name in MARKERS:
        table = total[name]
        kept = {k: round(1000 * v / c) for k, (v, c) in table.items() if c >= MIN_SAMPLES}
        source = rewrite(source, name, [f"{k}:{kept[k]}" for k in sorted(kept)])
        ranked = sorted(kept.items(), key=lambda kv: (kv[1], kv[0]))
        samples = sum(c for _, c in table.values())
        print(f"{name}: kept {len(kept)} keys, dropped {len(table) - len(kept)}, {samples} samples")
        print("  highest:", " ".join(f"{k}:{v}" for k, v in ranked[::-1][:10]))
        print("  lowest: ", " ".join(f"{k}:{v}" for k, v in ranked[:10]))
    path.write_text(source)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
