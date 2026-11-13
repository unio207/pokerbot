"""Fit a bot's settings to a real field, from that field's hand histories.

    python3.12 tools/field_fit.py history.jsonl.gz --hero <our name>          # measure the field
    python3.12 tools/field_fit.py history.jsonl.gz --hero <our name> --sweep  # ... and try other settings
    python3.12 tools/field_fit.py --simulate zoo/claude_exploiter_1 zoo/claude_grinder_1 ... --hero claude_exploiter_1

`tools/field_report.py` reads the file and names each opponent's type. This tool goes one
step further, in three parts:

1. Measure. The numbers a bot's settings depend on: how often an opening raise takes the
   blinds, how often it is re-raised, how often a shove is called, how often a bet after
   the flop wins the pot at once, and how often the bettor wins when called and shown.
   Each is printed beside the same number for our zoo, so a difference is visible.
2. Look-alike field. Every opponent in the file is matched to the zoo or sparring bot
   whose statistics are closest, and seven seats are filled in proportion.
3. Sweep (`--sweep`). The bot plays the look-alike field on the mini simulator with each
   setting in its `SETTINGS` table moved down and up, one at a time.

Reading the file is `field_report.kit_hands`, which reads the organizers' download format
(checked against the kit's sample). The sweep cannot play `double_board_turn_discard`: the
mini simulator has no class for it. The match in part 2
is on six statistics, so the look-alike field is an approximation of the real one, and
the mini simulator is not the organizers' engine.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_report  # noqa: E402

ROOT = field_report.ROOT
SIM = [sys.executable, str(ROOT / "devtest" / "mini_sim.py")]
ZOO_FIELD = ["zoo/claude_grinder_1", "zoo/claude_maniac_1", "zoo/claude_shark_1", "zoo/claude_tourist_1",
             "zoo/codex_adaptive_icm_1", "zoo/codex_rubric_pressure_icm_1", "zoo/codex_shove_aware_1"]  # fmt: skip
MIN_HANDS = 40  # an opponent with fewer hands is not matched

# (key, label, what it bears on). Shown in this order.
MEASURES = (
    ("steal", "an opening raise takes the blinds", "higher: raise `open_width`"),
    ("reraise", "an opening raise is re-raised", "higher: lower `open_width`"),
    ("shove_called", "a first-in shove is called", "higher: lower `shove_depth`, shove tighter"),
    ("bet_wins", "a bet after the flop wins at once", "higher: raise `cbet`"),
    ("bet_raised", "a bet after the flop is raised", "higher: lower `cbet`, raise `value_bet`"),
    ("bettor_wins", "the last bettor wins when called and shown", "higher: raise `bet_credit`, `call_margin`"),
)


# ------------------------------------------------------------------------------ measuring
def measure(hands, hero=None) -> dict:
    """Counts for MEASURES over all hands. With `hero`, only what happened to the hero's
    own raises and bets, which is how the field answers us in particular."""
    is_hero = (lambda name: name is not None and hero is not None and (name == hero or name.split("#")[0] == hero))
    count = Counter()
    for hand in hands:
        names, stacks = hand["names"], hand.get("stacks") or {}
        big_blind = max(1, hand["big_blind"])
        preflop = True
        opener, opener_shoved, answered = None, False, None  # answered: None, "call" or "raise"
        bettor, bet_answer = None, None
        shown, winners = set(), set()

        def close_bet():
            if bettor is not None and (hero is None or is_hero(names.get(bettor))):
                count["bets"] += 1
                count["bet_wins"] += bet_answer is None
                count["bet_raised"] += bet_answer == "raise"

        last_bettor = None
        for kind, seat, amount, _cards in hand["events"]:
            if kind == "board":
                preflop = False
                close_bet()
                bettor, bet_answer = None, None
            elif kind == "show":
                shown.add(seat)
            elif kind == "win":
                winners.add(seat)
            elif kind in ("call", "raise"):
                if preflop:
                    if opener is None:
                        if kind == "raise":
                            start = stacks.get(seat)
                            opener = seat
                            opener_shoved = bool((start and amount >= 0.9 * start) or
                                                 (not start and amount >= 25 * big_blind))
                    elif seat != opener and answered != "raise":
                        answered = kind
                elif kind == "raise":
                    if bettor is None:
                        bettor = seat
                    elif seat != bettor and bet_answer != "raise":
                        bet_answer = "raise"
                    last_bettor = seat
                elif bettor is not None and seat != bettor and bet_answer is None:
                    bet_answer = "call"
        close_bet()
        if opener is not None and (hero is None or is_hero(names.get(opener))):
            if opener_shoved:
                count["shoves"] += 1
                count["shove_called"] += answered is not None
            else:
                count["opens"] += 1
                count["steal"] += answered is None
                count["reraise"] += answered == "raise"
        if last_bettor is not None and last_bettor in shown and len(shown) >= 2:
            if hero is None or not is_hero(names.get(last_bettor)):  # how honest the field's bets are
                count["shown_bets"] += 1
                count["bettor_wins"] += last_bettor in winners
    base = {"steal": "opens", "reraise": "opens", "shove_called": "shoves", "bet_wins": "bets",
            "bet_raised": "bets", "bettor_wins": "shown_bets"}  # fmt: skip
    return {key: (count[key], count[base[key]]) for key in base}


def rate(pair) -> str:
    part, whole = pair
    return f"{100 * part / whole:4.0f}% of {whole:<6d}" if whole else "   -            "


def print_measures(field, reference, ours) -> None:
    print(f"{'how often...':46s} {'this field':17s} {'our zoo':17s} {'against us':17s} what it bears on")
    for key, label, bearing in MEASURES:
        against = ours[key] if ours and key != "bettor_wins" else (0, 0)
        print(f"{label:46s} {rate(field[key])} {rate(reference[key])} {rate(against)} {bearing}")
    print("\nRead a row only when both columns have a few hundred cases; a gap of under about "
          "5 points is noise.\n'against us' counts only our own raises and bets.")


# -------------------------------------------------------------------------- look-alike field
def features(row) -> list[float] | None:
    """Six statistics of one bot, each 0..1, from a field_report row."""
    hands = row["hands"]
    if hands < MIN_HANDS:
        return None

    def share(part, whole, default):
        return part / whole if whole >= 10 else default

    return [row["vpip"] / hands, row["pfr"] / hands, min(1.0, 3 * row["shoves"] / hands),
            share(row["folded_to_raise"], row["faced_raise"], 0.7), share(row["bets"], row["could_bet"], 0.3),
            share(row["folded_to_bet"], row["faced_bet"], 0.5)]  # fmt: skip


WEIGHTS = (2.0, 2.0, 1.5, 1.0, 1.0, 1.0)


def candidates() -> list[str]:
    """Every zoo and sparring bot that can sit in a look-alike field."""
    found = [f"zoo/{p.parent.name}" for p in sorted((ROOT / "zoo").glob("*/agent.py"))
             if p.parent.name not in ("_template", "claude_exploiter_1")]  # fmt: skip
    found += [f"sparring/{p.parent.name}" for p in sorted((ROOT / "sparring").glob("*/agent.py"))]
    return found


def library(tables: int, variant: str) -> dict:
    """Statistics of every candidate, measured by playing them against each other."""
    bots = candidates()
    stats = defaultdict(Counter)
    for offset in range(0, len(bots), 4):  # rotate so every bot meets a mix of the others
        seats = [bots[(offset + step) % len(bots)] for step in range(8)]
        seats = list(dict.fromkeys(seats))
        for name, row in field_report.analyse(field_report.simulated_hands(seats, tables, f"lib{offset}", variant))["stats"].items():
            stats[seats[int(name.rsplit("#", 1)[1])]].update(row)
    return {bot: vector for bot, row in stats.items() if (vector := features(row))}


def look_alike(stats, hero, known: dict, tables: dict, seats=7):
    """(field of `seats` bots, [(opponent, hands, closest bot, distance)]). Seats are shared
    out by how many tables each opponent sat at, so a bot that busts early still counts."""
    is_hero = (lambda name: hero is not None and (name == hero or name.split("#")[0] == hero))
    matches, weight = [], Counter()
    for name, row in stats.items():
        vector = features(row)
        if is_hero(name) or vector is None:
            continue
        best = min(known, key=lambda bot: sum(w * (a - b) ** 2 for w, a, b in zip(WEIGHTS, vector, known[bot])))
        distance = sum(w * (a - b) ** 2 for w, a, b in zip(WEIGHTS, vector, known[best])) ** 0.5
        matches.append((name, row["hands"], best, distance))
        weight[best] += tables.get(name, 1)
    total = sum(weight.values())
    if not total:
        return [], matches
    exact = {bot: seats * sat / total for bot, sat in weight.items()}
    field = Counter({bot: int(share) for bot, share in exact.items()})
    for bot, _ in sorted(exact.items(), key=lambda item: -(item[1] - int(item[1])))[: seats - sum(field.values())]:
        field[bot] += 1
    return sorted(field.elements()), sorted(matches, key=lambda match: -match[1])


# ---------------------------------------------------------------------------------- sweep
SETTING_LINE = re.compile(r'^(\s*"(\w+)":\s*)([-0-9.]+)(,.*)$', re.M)


def read_settings(source: str) -> dict:
    block = re.search(r"^SETTINGS = \{\n(.*?)^\}", source, re.S | re.M)
    if not block:
        return {}
    return {name: float(value) for _, name, value, _ in SETTING_LINE.findall(block.group(1))}


def with_settings(source: str, changed: dict) -> str:
    def swap(match):
        name = match.group(2)
        return f"{match.group(1)}{changed[name]:g}{match.group(4)}" if name in changed else match.group(0)

    block = re.search(r"^SETTINGS = \{\n(.*?)^\}", source, re.S | re.M)
    return source[: block.start(1)] + SETTING_LINE.sub(swap, block.group(1)) + source[block.end(1) :]


def play(agent_source: str, field, tables, seed, variant, folder: Path) -> tuple[float, float]:
    """(points per table, share of first places) for this source against the field."""
    (folder / "agent.py").write_text(agent_source, encoding="utf-8")
    command = SIM + ["play", str(folder)] + [str(ROOT / bot) for bot in field] + [
        "--tables", str(tables), "--seed", seed, "--variant", variant]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(f"The simulator failed:\n{done.stderr[-2000:]}")
    text = done.stdout
    ours = next(iter(json.loads(text[text.index("{") :])["bots"].values()))
    places = ours["places"]
    return ours["average_points"], places["1"] / max(1, sum(places.values()))


def sweep(bot: Path, field, tables, seed, variant, step) -> None:
    source = (bot / "agent.py").read_text(encoding="utf-8")
    settings = read_settings(source)
    if not settings:
        sys.exit(f"{bot}/agent.py has no SETTINGS table with one `\"name\": value,` pair per line.")
    error = 20 / tables**0.5
    print(f"\nSweep: {bot.name} against the look-alike field, {tables} tables per row, variant {variant}.")
    print(f"One row's points are good to about ±{error:.1f}; believe a change only when it is "
          f"more than {2.8 * error:.1f} from the first row, then confirm it with another --seed.\n")  # fmt: skip
    print(f"{'setting':14s} {'value':>7s} {'points':>7s} {'change':>7s} {'firsts':>7s}")
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch) / bot.name
        folder.mkdir()
        base, firsts = play(source, field, tables, seed, variant, folder)
        print(f"{'(as it is)':14s} {'':>7s} {base:7.2f} {'':>7s} {100 * firsts:6.0f}%")
        for name, value in settings.items():
            for factor in (1 - step, 1 + step):
                tried = round(value * factor, 3)
                points, firsts = play(with_settings(source, {name: tried}), field, tables, seed, variant, folder)
                print(f"{name:14s} {tried:7g} {points:7.2f} {points - base:+7.2f} {100 * firsts:6.0f}%", flush=True)


# ----------------------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("history", nargs="?", type=Path, help="a hand-history file: JSON or JSON lines, .gz or plain")
    parser.add_argument("--simulate", nargs="+", metavar="BOT", help="play these bot folders on the mini simulator instead of reading a file")
    parser.add_argument("--hero", help="our bot's name in the file")
    parser.add_argument("--bot", type=Path, default=ROOT / "zoo" / "claude_exploiter_1", help="the bot folder whose SETTINGS are swept")
    parser.add_argument("--sweep", action="store_true", help="try other settings against the look-alike field")
    parser.add_argument("--field", nargs="+", metavar="BOT", help="sweep against these bot folders instead of the look-alike field")
    parser.add_argument("--tables", type=int, default=1500, help="tables per sweep row (default 1500)")
    parser.add_argument("--step", type=float, default=0.3, help="how far to move each setting, as a share (default 0.3)")
    parser.add_argument("--seed", default="fit")
    parser.add_argument("--variant", default="holdem")
    parser.add_argument("--sim-tables", type=int, default=40, help="tables for --simulate, the zoo reference and the bot library")
    args = parser.parse_args()

    if args.simulate:
        hands = field_report.simulated_hands(args.simulate, args.sim_tables, args.seed, args.variant)
    elif args.history:
        hands = field_report.kit_hands(field_report.read_json_lines(args.history))
        if not hands:
            sys.exit("No hands recognised. Run tools/field_report.py --inspect on the file, then fix `kit_hands` there.")
    else:
        parser.error("give a history file or --simulate BOT ...")
    print(f"{len(hands)} hands from {len({hand['table'] for hand in hands})} tables\n")

    reference = field_report.simulated_hands([str(args.bot.resolve().relative_to(ROOT))] + ZOO_FIELD,
                                             args.sim_tables, "reference", args.variant)  # fmt: skip
    print_measures(measure(hands), measure(reference), measure(hands, args.hero) if args.hero else None)

    field = args.field
    if not field:
        stats = field_report.analyse(hands)["stats"]
        sat = Counter(name for table in {hand["table"]: hand for hand in hands}.values() for name in table["names"].values())
        field, matches = look_alike(stats, args.hero, library(max(10, args.sim_tables // 2), args.variant), sat)
        print("\nLook-alike field (each opponent matched to the closest zoo or sparring bot):")
        for name, count, best, distance in matches[:40]:
            print(f"  {name[:34]:34s} {count:6d} hands  ->  {best:34s} {'close' if distance < 0.25 else 'rough' if distance < 0.45 else 'POOR MATCH'}")
        if len(matches) > 40:
            print(f"  ... and {len(matches) - 40} more")
        poor = sum(count for _, count, _, distance in matches if distance >= 0.45)
        if matches and poor:
            print(f"  {100 * poor / sum(m[1] for m in matches):.0f}% of opponent hands have no close match: "
                  "add bots like them to the zoo before trusting a sweep.")  # fmt: skip
        if not field:
            sys.exit(f"\nNo opponent has {MIN_HANDS} hands yet: not enough to build a field.")
        print("\nSeven seats in proportion:\n  " + " ".join(field))
    if args.sweep:
        sweep(args.bot.resolve(), field, args.tables, args.seed, args.variant, args.step)
    else:
        print("\nAdd --sweep to try other settings against this field.")


if __name__ == "__main__":
    main()
