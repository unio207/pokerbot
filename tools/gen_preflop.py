"""Regenerate the 169-class preflop equity table embedded in a bot's agent.py.

    python tools/gen_preflop.py starter/agent.py [samples_per_class]

Equity is each starting-hand class against one random hand, by Monte Carlo, using the
bot's own `hand_rank`. Rewrites the `_EQUITY_TABLE = "..."` line in place.
"""

import importlib.util
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "devtest" / "shim"))

RANKS = "AKQJT98765432"
DECK = [rank + suit for rank in RANKS for suit in "cdhs"]


def main() -> None:
    path = Path(sys.argv[1])
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    source = path.read_text()
    # Load the bot with a placeholder table so its import-time parsing succeeds.
    stub = re.sub(r'_EQUITY_TABLE = ".*"', '_EQUITY_TABLE = "AA:500"', source)
    scratch = path.with_name("_gen_tmp.py")
    scratch.write_text(stub)
    try:
        spec = importlib.util.spec_from_file_location("gen_bot", scratch)
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
    finally:
        scratch.unlink()
    rank = bot.hand_rank
    rng = random.Random(2026)
    items = []
    for i, high in enumerate(RANKS):
        for j, low in enumerate(RANKS):
            if j < i:
                continue
            for suited in (True, False):
                if i == j and suited:
                    continue
                hole = (high + "s", low + ("s" if suited else "h"))
                rest = [card for card in DECK if card not in hole]
                score = 0.0
                for _ in range(samples):
                    draw = rng.sample(rest, 7)
                    board = tuple(draw[2:])
                    ours, theirs = rank(hole + board), rank(tuple(draw[:2]) + board)
                    score += 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0
                key = high + low + ("" if i == j else "s" if suited else "o")
                items.append(f"{key}:{round(1000 * score / samples)}")
    table = " ".join(items)
    path.write_text(re.sub(r'_EQUITY_TABLE = ".*"', f'_EQUITY_TABLE = "{table}"', source))
    print(f"wrote {len(items)} classes to {path}")


if __name__ == "__main__":
    main()
