"""Read hand histories and say what the field is: who is dead, who shoves, who never folds.

    python3.12 tools/field_report.py history.jsonl.gz --hero <our name>     # a kit or team-page file
    python3.12 tools/field_report.py --inspect history.jsonl.gz             # show the file's structure
    python3.12 tools/field_report.py --simulate bots/final starter sparring/shover ... --tables 40

Per opponent it prints how often it plays a hand (VPIP), raises before the flop (PFR),
goes all-in before the flop, limps, folds to a raise, bets after the flop and folds to a
bet; a one-word type; the hands it showed after shoving; then the mix of types in the
field and what to change in our bot (the knobs are in SETTINGS in tools/core_agent.py).
The types and the advice were set on hold'em. For the Pittsburgh histories use tools/history/.

Formats. `--simulate` plays tables on our mini simulator and reads its replay records;
that path is tested. A file is read as JSON lines (gzip or plain), and `kit_hands` below
turns its records into hands. It reads the organizers' download format, checked against
the kit's `hand-history/sample.jsonl.gz` (same table and hand counts as the kit's
`read.py`). If a real file differs, run `--inspect` on it and fix that one function.
Everything after it only needs hands in this shape:

    {"table": id, "hand": n, "big_blind": 20, "names": {seat: name}, "stacks": {seat: chips at start},
     "events": [(kind, seat, amount, cards), ...]}   kinds as in poker_agent_sdk.Event
"""

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RANKS = "23456789TJQKA"
MIN_HANDS = 20  # below this a bot is listed but not typed


# ------------------------------------------------------------------------------ reading
def read_json_lines(path: Path) -> list:
    opener = gzip.open if path.suffix == ".gz" else open
    records = []
    with opener(path, "rt", encoding="utf-8") as handle:
        text = handle.read()
    try:  # one JSON document
        loaded = json.loads(text)
        records = loaded if isinstance(loaded, list) else [loaded]
    except json.JSONDecodeError:  # JSON lines
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    return records


def first(record: dict, *keys, default=None):
    for key in keys:
        if isinstance(record, dict) and key in record and record[key] is not None:
            return record[key]
    return default


def as_event(raw):
    """One event as (kind, seat, amount, cards) from a list, or a dict with the usual names."""
    if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], str):
        padded = list(raw) + [None, 0, []]
        return padded[0], padded[1], padded[2] or 0, tuple(padded[3] or ())
    if isinstance(raw, dict):
        kind = first(raw, "kind", "type", "action", "event")
        if isinstance(kind, str):
            return (kind.lower(), first(raw, "seat", "player", "actor"), first(raw, "amount", "chips", "total", default=0) or 0,
                    tuple(first(raw, "cards", "hole", "board", default=()) or ()))  # fmt: skip
    return None


def kit_hands(records) -> list[dict]:
    """Hands from the organizers' download (the kit's hand-history/README.md has the format).

    Line 1 is a header whose `entries` give entry id -> team name. Then, per table, a public
    record (`iteration`, `table`, `seats` = entry id by seat, `hands`) and a private
    `{"you": ...}` record, which is not needed here. A hand has `blinds` [small, big, ante],
    `stacks_before` by seat (0 = busted) and `events`. Events pass through unchanged: a
    `board` event is the new cards of one board, with the board number (1 or 2) in amount;
    kinds the analysis does not use (`discard`, `prize_*`, anything new) are skipped there.
    """
    teams, hands = {}, []
    for record in records:
        if not isinstance(record, dict):
            continue
        if isinstance(record.get("entries"), list):  # the header
            teams = {entry["entry_id"]: str(entry["team_name"]) for entry in record["entries"]}
            twice = {name for name, count in Counter(teams.values()).items() if count > 1}
            teams = {entry: f"{name}#{entry[-4:]}" if name in twice else name for entry, name in teams.items()}
            continue
        if not isinstance(record.get("hands"), list):  # the private record
            continue
        table = (record.get("iteration", 0), record.get("table", 0))  # table numbers repeat in every iteration
        names = {seat: teams.get(entry, str(entry)) for seat, entry in enumerate(record.get("seats") or [])}
        for hand in record["hands"]:
            blinds = hand.get("blinds") or []
            hands.append({
                "table": table, "hand": hand.get("hand", 0), "big_blind": int(blinds[1]) if len(blinds) > 1 else 20,
                "names": names, "stacks": dict(enumerate(hand.get("stacks_before") or [])),
                "events": [event for event in map(as_event, hand.get("events") or []) if event],
            })  # fmt: skip
    return hands


def inspect(records, limit=3, depth=4) -> None:
    """Print the shape of the first records, so `kit_hands` can be matched to a real file."""

    def shape(value, level):
        pad = "  " * level
        if isinstance(value, dict):
            for key, item in list(value.items())[:25]:
                summary = type(item).__name__ + (f"[{len(item)}]" if isinstance(item, (list, dict, str)) else f" = {item!r}")
                print(f"{pad}{key}: {summary}")
                if level < depth and isinstance(item, (dict, list)):
                    shape(item, level + 1)
        elif isinstance(value, list) and value:
            print(f"{pad}[0] {type(value[0]).__name__}: {json.dumps(value[0])[:160]}")
            if level < depth and isinstance(value[0], (dict, list)):
                shape(value[0], level + 1)

    print(f"{len(records)} records")
    for number, record in enumerate(records[:limit]):
        print(f"--- record {number}: {type(record).__name__}")
        shape(record, 1)


def simulated_hands(bots, tables, seed, variant) -> list[dict]:
    """Play tables on the mini simulator and return every hand of every table."""
    sys.path.insert(0, str(ROOT / "devtest"))
    import mini_sim

    rules = dict(stack=2000, decision_ms=1, bank_ms=100, hand_cap=250, hands_per_level=20,
                 payouts=(50, 30, 20), variant=variant, random_payouts=False)  # fmt: skip
    paths = [str((ROOT / bot).resolve()) for bot in bots]
    spec = dict(bots=paths, seed=seed, rules=rules, replay_tables=tables, fresh=False, token="field", notes=0)
    labels = [f"{Path(path).name}#{index}" for index, path in enumerate(paths)]
    hands = []
    for number in range(tables):
        result = mini_sim.play_table(spec, number)
        names = {seat: labels[entry] for seat, entry in enumerate(result["order"])}
        for hand in result["hands"]:
            hands.append({
                "table": number, "hand": hand["hand"], "big_blind": hand["blinds"][1], "names": names,
                "stacks": dict(enumerate(hand["start"])),
                "events": [(e[0], e[1], e[2], tuple(e[3])) for e in hand["events"] if e],
            })  # fmt: skip
    return hands


# ----------------------------------------------------------------------------- analysis
def hand_class(cards) -> str:
    """'AKs', 'T9o', '77' from the two best-ranked of the shown cards."""
    cards = sorted((card for card in cards if len(card) == 2 and card[0] in RANKS), key=lambda c: -RANKS.index(c[0]))[:2]
    if len(cards) < 2:
        return "?"
    a, b = cards
    return a[0] + b[0] + ("" if a[0] == b[0] else "s" if a[1] == b[1] else "o")


def premium(name: str) -> bool:
    return name in ("AA", "KK", "QQ", "JJ", "TT", "AKs", "AKo", "AQs", "AQo")


def analyse(hands) -> dict:
    stats = defaultdict(Counter)
    shown = defaultdict(list)
    for hand in hands:
        names, big_blind, stacks = hand["names"], max(1, hand["big_blind"]), hand.get("stacks") or {}
        preflop, bet_out, raised = True, True, False  # the blinds are an outstanding bet
        acted, shoved, in_hand = set(), set(), set()
        live = {seat for seat, chips in stacks.items() if chips > 0} or set(names)
        for seat in live:
            stats[names.get(seat, f"seat {seat}")]["hands"] += 1
        for kind, seat, amount, cards in hand["events"]:
            if kind == "board":
                preflop, bet_out = False, False
                continue
            if kind == "show" and seat in names:
                if seat in shoved:
                    shown[names[seat]].append(hand_class(cards))
                stats[names[seat]]["showdowns"] += 1
                continue
            if kind == "stack" and seat in names and amount == 0 and seat in live:
                stats[names[seat]]["busts"] += 1
                stats[names[seat]]["busts_preflop_all_in"] += seat in shoved
                continue
            if kind not in ("fold", "check", "call", "raise") or seat not in names:
                continue
            row = stats[names[seat]]
            if preflop:
                if seat not in acted:  # first voluntary action of the hand
                    acted.add(seat)
                    row["first_actions"] += 1
                    if raised:
                        row["faced_raise"] += 1
                        row["folded_to_raise"] += kind == "fold"
                    if kind == "call":
                        row["limps"] += not raised
                if kind in ("call", "raise") and seat not in in_hand:
                    in_hand.add(seat)
                    row["vpip"] += 1
                if kind == "raise":
                    if seat not in shoved and row["_pfr_hand"] != (hand["table"], hand["hand"]):
                        row["pfr"] += 1
                        row["_pfr_hand"] = (hand["table"], hand["hand"])
                    start = stacks.get(seat)
                    if (start and amount >= 0.9 * start) or (not start and amount >= 25 * big_blind):
                        if seat not in shoved:
                            row["shoves"] += 1
                        shoved.add(seat)
                    elif not raised and amount <= 2.05 * big_blind:
                        row["min_raises"] += 1
                    raised = True
            else:
                if bet_out:
                    row["faced_bet"] += 1
                    row["folded_to_bet"] += kind == "fold"
                elif kind in ("check", "raise"):
                    row["could_bet"] += 1
                    row["bets"] += kind == "raise"
                if kind == "raise":
                    bet_out = True
    for row in stats.values():
        row.pop("_pfr_hand", None)
    return {"stats": stats, "shown": shown}


def share(part, whole) -> float | None:
    return part / whole if whole else None


def kind_of(row) -> str:
    hands = row["hands"]
    if hands < MIN_HANDS:
        return "too few hands"
    vpip, pfr, shove = row["vpip"] / hands, row["pfr"] / hands, row["shoves"] / hands
    if vpip <= 0.03:
        return "dead"
    if shove >= 0.10 and row["shoves"] >= 0.6 * row["pfr"]:
        return "shover"  # most of its raises are all-in
    if vpip >= 0.45 and pfr <= 0.08:
        return "station"
    if pfr >= 0.15 and row["min_raises"] >= 0.6 * row["pfr"]:
        return "min-raiser"
    if pfr >= 0.30 or (vpip >= 0.45 and pfr >= 0.25):
        return "maniac"
    if vpip <= 0.12:
        return "nit"
    return "regular"


ADVICE = {
    "dead": (0.20, "Dead seats never contest a pot: raise any two cards when only they are left to act "
                   "(`steal_any`, `steal_widen`; the `steal` read needs `track=True`)."),
    "nit": (0.30, "Tight seats fold too much: open wider in late position (`open`, `steal_widen`) and "
                  "fold to their raises without a premium hand (`call_raise`)."),
    "shover": (0.12, "Habitual shovers: call their all-ins by their observed rate, not as a tight range "
                     "(`vs_shover=\"math\"`, lower `call_margin`), and open less with them behind."),
    "station": (0.15, "Calling stations do not fold: no bluffs or air c-bets (`cbet_air=0`, `semi_bluff` "
                      "down), bet bigger for value (`value_size`), the `station` read on."),
    "maniac": (0.15, "Loose raisers: re-raise for value wider (`threebet`), call down lighter "
                     "(`call_edge` down), and let them bet into strong hands."),
    "min-raiser": (0.15, "Min-raisers: re-raise wider and bigger (the `minraise` read), defend the "
                         "big blind against the small price."),
}  # fmt: skip


def percent(value) -> str:
    return "   - " if value is None else f"{100 * value:4.0f}%"


def report(result, hero: str | None) -> None:
    stats, shown = result["stats"], result["shown"]
    is_hero = (lambda name: hero is not None and (name == hero or name.split("#")[0] == hero))
    rows = sorted(stats.items(), key=lambda item: (not is_hero(item[0]), -item[1]["hands"]))
    width = max(12, min(34, max(len(name) for name, _ in rows)))
    print(f"{'bot':{width}s} {'hands':>6s} {'VPIP':>5s} {'PFR':>5s} {'shove':>5s} {'limp':>5s} "
          f"{'f/raise':>7s} {'bets':>5s} {'f/bet':>5s}  type")  # fmt: skip
    mix = Counter()
    for name, row in rows:
        hands = row["hands"]
        kind = "us" if is_hero(name) else kind_of(row)
        if not is_hero(name) and hands >= MIN_HANDS:
            mix[kind] += hands
        print(f"{name[:width]:{width}s} {hands:6d} {percent(share(row['vpip'], hands))} {percent(share(row['pfr'], hands))} "
              f"{percent(share(row['shoves'], hands))} {percent(share(row['limps'], row['first_actions']))} "
              f"  {percent(share(row['folded_to_raise'], row['faced_raise']))} {percent(share(row['bets'], row['could_bet']))} "
              f"{percent(share(row['folded_to_bet'], row['faced_bet']))}  {kind}")  # fmt: skip
    shovers = [(name, hands) for name, hands in shown.items() if len(hands) >= 5 and not is_hero(name)]
    if shovers:
        print("\nHands shown after going all-in before the flop:")
        for name, hands in sorted(shovers, key=lambda item: -len(item[1])):
            common = ", ".join(f"{hand} x{count}" for hand, count in Counter(hands).most_common(8))
            strong = sum(map(premium, hands)) / len(hands)
            print(f"  {name[:width]:{width}s} {len(hands):4d} shown, {100 * strong:3.0f}% premium (TT+, AK, AQ): {common}")
    total = sum(mix.values())
    if not total:
        print("\nNot enough hands to describe the field.")
        return
    print("\nField mix (share of opponent hands):  " + ",  ".join(f"{kind} {100 * n / total:.0f}%" for kind, n in mix.most_common()))
    advice = [text for kind, (line, text) in ADVICE.items() if mix[kind] / total >= line]
    print("\nWhat to change:" if advice else "\nNo type is common enough to act on; keep the default profile.")
    for text in advice:
        print(f"  - {text}")
    for name, row in rows:
        if is_hero(name) and row["busts"]:
            print(f"\n{name}: busted {row['busts']} times, {row['busts_preflop_all_in']} of them after shoving before the flop.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("history", nargs="?", type=Path, help="a hand-history file: JSON or JSON lines, .gz or plain")
    parser.add_argument("--hero", help="our bot's name in the file, listed first and left out of the field mix")
    parser.add_argument("--inspect", action="store_true", help="print the file's structure instead of a report")
    parser.add_argument("--simulate", nargs="+", metavar="BOT", help="play these bot folders on the mini simulator instead")
    parser.add_argument("--tables", type=int, default=40)
    parser.add_argument("--seed", default="field")
    parser.add_argument("--variant", default="holdem")
    args = parser.parse_args()
    if args.simulate:
        hands = simulated_hands(args.simulate, args.tables, args.seed, args.variant)
    elif args.history:
        records = read_json_lines(args.history)
        if args.inspect:
            return inspect(records)
        hands = kit_hands(records)
        if not hands:
            sys.exit("No hands recognised in this file. Run with --inspect, then fix `kit_hands` in tools/field_report.py.")
    else:
        parser.error("give a history file or --simulate BOT ...")
    tables = len({hand["table"] for hand in hands})
    print(f"{len(hands)} hands from {tables} tables\n")
    report(analyse(hands), args.hero)


if __name__ == "__main__":
    main()
