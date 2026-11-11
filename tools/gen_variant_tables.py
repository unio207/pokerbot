"""Measure the variant tables embedded in a bot's source file and rewrite them in place.

    python3 tools/gen_variant_tables.py tools/core_agent.py [--samples 400000] [--procs 8] [--seed 2026]

The bot (tools/core_agent.py layout) scores its private cards per variant from a few small
tables. This fills them by Monte Carlo against one random opponent hand, using the rules
the mini simulator plays (devtest/sim_variants.py):

  _SHORT_TABLE     short_deck: equity of each of the 81 starting classes of a 36-card deck
  _SHORT_SHIFT     short_deck: measured minus full-deck made-hand strength, per hand category
  _DISCARD_FIT     discard_reveal: equity as a line in the best two-card equity of three cards
  _DISCARD_MARKS   discard_reveal: that score at each 5% step of all hands, best first
  _OMAHA_FIT       omaha: equity as a line in the mean two-card equity of four cards
  _OMAHA_MARKS     omaha: that score at each 5% step of all hands, best first
  _OMAHA_MADE      omaha: equity of the best two-plus-three hand, by street and category

`--samples` is the number of deals per table. Then run tools/build.py to restamp the bots.
These are measurements of our own re-implementation of each ruleset, not of the kit.
"""

import argparse
import importlib.util
import multiprocessing
import random
import re
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "devtest" / "shim"))
sys.path.insert(0, str(ROOT / "devtest"))

DECK = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]
SHORT = [card for card in DECK if card[0] not in "2345"]
_BOT = None


def load(path: str):
    global _BOT
    if _BOT is None:
        spec = importlib.util.spec_from_file_location("variant_bot", path)
        _BOT = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_BOT)
        _BOT._SHORT_SHIFT = (0.0,) * 9  # measure the uncorrected strength
    return _BOT


def outcome(ours, theirs) -> float:
    return 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0


def omaha_rank(bot, hole, board) -> tuple:
    cards = [(bot._RANK[card[0]], card[1]) for card in hole]
    table = [(bot._RANK[card[0]], card[1]) for card in board]
    return max(bot._five(two + three) for two in combinations(cards, 2) for three in combinations(table, 3))


def keep_two(bot, cards, flop):
    """The discard a bot makes in discard_reveal: keep the pair that plays best with the flop."""
    return max(combinations(cards, 2), key=lambda pair: bot._made_strength(pair, flop))


def short_classes(bot):
    keys = {bot._class_key(a, b) for a, b in combinations(SHORT, 2)}
    return sorted(keys, key=lambda key: (-bot._RANK[key[0]], -bot._RANK[key[1]], key[2:]))


def example(key):
    """Two concrete cards of a starting class."""
    return (key[0] + "s", key[1] + ("s" if key.endswith("s") else "h"))


def work(job):
    kind, path, count, seed = job
    bot, rng = load(path), random.Random(seed)
    if kind == "short_table":
        import sim_variants

        totals = {}
        for key in short_classes(bot):
            hole, won = example(key), 0.0
            rest = [card for card in SHORT if card not in hole]
            for trial in range(count):
                drawn = rng.sample(rest, 7)
                ours, theirs = (bot.hand_rank(hole + tuple(drawn[2:]), True),
                                bot.hand_rank(tuple(drawn[:2]) + tuple(drawn[2:]), True))  # fmt: skip
                if trial < 20:  # the bot's evaluator must agree with the simulator's
                    rules = dict(low_straight=9, flush_beats_full_house=True)
                    truth = (sim_variants.best_five(hole + tuple(drawn[2:]), **rules),
                             sim_variants.best_five(tuple(drawn), **rules))  # fmt: skip
                    assert outcome(ours, theirs) == outcome(*truth), (hole, drawn)
                won += outcome(ours, theirs)
            totals[key] = (won, count)
        return kind, totals
    if kind == "short_shift":
        totals = {}
        for _ in range(count):
            size = rng.choice((3, 4, 5))
            drawn = rng.sample(SHORT, 9)
            hole, board, full = tuple(drawn[:2]), tuple(drawn[4 : 4 + size]), tuple(drawn[4:])
            category = bot._FULL_DECK_ORDER[bot.hand_rank(hole + board, True)[0]]
            result = outcome(bot.hand_rank(hole + full, True), bot.hand_rank(tuple(drawn[2:4]) + full, True))
            won, guessed, n = totals.get(category, (0.0, 0.0, 0))
            totals[category] = (won + result, guessed + bot._made_strength(hole, board, True), n + 1)
        return kind, totals
    if kind == "discard" or kind == "omaha":
        sums, scores = [0.0] * 5, []
        for _ in range(count):
            drawn = rng.sample(DECK, 13)
            if kind == "discard":
                mine, theirs, board = drawn[:3], drawn[3:6], tuple(drawn[6:11])
                score = max(bot._EQUITY[bot._class_key(a, b)] for a, b in combinations(mine, 2))
                result = outcome(bot.hand_rank(keep_two(bot, mine, board[:3]) + board),
                                 bot.hand_rank(keep_two(bot, theirs, board[:3]) + board))  # fmt: skip
            else:
                mine, theirs, board = drawn[:4], drawn[4:8], drawn[8:13]
                score = sum(bot._EQUITY[bot._class_key(a, b)] for a, b in combinations(mine, 2)) / 6
                result = outcome(omaha_rank(bot, mine, board), omaha_rank(bot, theirs, board))
            for index, value in enumerate((1.0, score, result, score * score, score * result)):
                sums[index] += value
            if len(scores) < 20000:
                scores.append(score)
        return kind, (sums, scores)
    if kind == "omaha_made":
        totals = {}
        for _ in range(count):
            size = rng.choice((3, 4, 5))
            drawn = rng.sample(DECK, 13)
            mine, theirs, full = drawn[:4], drawn[4:8], drawn[8:13]
            category = omaha_rank(bot, mine, full[:size])[0]
            result = outcome(omaha_rank(bot, mine, full), omaha_rank(bot, theirs, full))
            won, n = totals.get((size - 3, category), (0.0, 0))
            totals[size - 3, category] = (won + result, n + 1)
        return kind, totals
    raise ValueError(kind)


def line_fit(sums) -> tuple[float, float]:
    n, sx, sy, sxx, sxy = sums
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    return round((sy - slope * sx) / n, 3), round(slope, 3)


def marks(scores) -> tuple:
    ordered = sorted(scores, reverse=True)
    return tuple(round(ordered[min(len(ordered) - 1, step * len(ordered) // 20)], 4) for step in range(21))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("bot", type=Path)
    parser.add_argument("--samples", type=int, default=400000)
    parser.add_argument("--procs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    path = str(args.bot.resolve())
    bot = load(path)
    chunks = max(1, args.procs)
    per_class = max(50, args.samples // 81 // chunks)
    jobs = [("short_table", path, per_class, args.seed + chunk) for chunk in range(chunks)]
    for offset, kind in enumerate(("short_shift", "discard", "omaha", "omaha_made"), 1):
        jobs += [(kind, path, args.samples // chunks, args.seed + 1000 * offset + chunk) for chunk in range(chunks)]
    with multiprocessing.Pool(chunks) as pool:
        results = pool.map(work, jobs, chunksize=1)

    merged = {}
    for kind, part in results:
        if kind in ("discard", "omaha"):
            sums, scores = merged.setdefault(kind, ([0.0] * 5, []))
            for index, value in enumerate(part[0]):
                sums[index] += value
            scores.extend(part[1])
        else:
            total = merged.setdefault(kind, {})
            for key, values in part.items():
                total[key] = tuple(a + b for a, b in zip(total.get(key, (0,) * len(values)), values))

    table = " ".join(f"{key}:{round(1000 * won / n)}" for key, (won, n) in merged["short_table"].items())
    shift = tuple(
        round(won / n - guessed / n, 3) if (won := merged["short_shift"].get(c, (0, 0, 0))[0]) is not None
        and (n := merged["short_shift"].get(c, (0, 0, 0))[2]) >= 200
        and (guessed := merged["short_shift"][c][1]) is not None else 0.0
        for c in range(9)
    )  # fmt: skip
    made = []
    for street in range(3):
        row, previous = [], 0.0
        for category in range(9):
            won, n = merged["omaha_made"].get((street, category), (0.0, 0))
            previous = round(won / n, 3) if n >= 200 else max(previous, bot._OMAHA_MADE[street][category])
            row.append(previous)
        made.append(tuple(row))
    values = {
        "_SHORT_TABLE": f'"{table}"',
        "_SHORT_SHIFT": repr(shift),
        "_DISCARD_FIT": repr(line_fit(merged["discard"][0])),
        "_DISCARD_MARKS": repr(marks(merged["discard"][1])),
        "_OMAHA_FIT": repr(line_fit(merged["omaha"][0])),
        "_OMAHA_MARKS": repr(marks(merged["omaha"][1])),
    }
    source = args.bot.read_text()
    for name, value in values.items():
        pattern = re.compile(rf"^{name} = .*$", re.M)
        if len(pattern.findall(source)) != 1:
            sys.exit(f"gen_variant_tables: expected exactly one line `{name} = ...` in {args.bot}")
        source = pattern.sub(lambda _: f"{name} = {value}", source)
        print(f"{name} = {value[:150]}{'...' if len(value) > 150 else ''}")
    pattern = re.compile(r"^_OMAHA_MADE = \(\n(?:    \(.*\),\n){3}\)$", re.M)
    if len(pattern.findall(source)) != 1:
        sys.exit(f"gen_variant_tables: expected one three-row `_OMAHA_MADE = (...)` block in {args.bot}")
    block = "_OMAHA_MADE = (\n" + "".join(f"    {row!r},\n" for row in made) + ")"
    source = pattern.sub(lambda _: block, source)
    print(block)
    args.bot.write_text(source)
    print(f"wrote {args.bot}; now run tools/build.py")


if __name__ == "__main__":
    main()
