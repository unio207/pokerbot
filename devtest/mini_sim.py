"""A small, UNOFFICIAL sit-and-go simulator for smoke-testing bots without the organizers' kit.

    python devtest/mini_sim.py check starter/agent.py
    python devtest/mini_sim.py play starter sparring/nit sparring/shover --tables 200

It plays standard no-limit hold'em only (no variant phases) with the table defaults the
starter kit documents: 8 seats, 2,000 chips, 50/30/20 points, ICM split at the hand cap,
1 ms per decision with a 100 ms per-table time bank. `play` prints the same JSON summary
as the kit's `poker-agent play`, plus decision latency.

It runs bots in-process, so latency here is optimistic compared with the real platform,
and its rules are a re-implementation. The kit's `poker-agent play` is the authority.
"""

import argparse
import ast
import importlib.util
import json
import math
import random
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "shim"))

from poker_agent_sdk import (  # noqa: E402
    Action,
    BlindLevel,
    Event,
    GameState,
    LegalAction,
    Seat,
    TableConfig,
    icm,
)

sys.path.insert(0, str(HERE.parent / "starter"))
from agent import hand_rank  # noqa: E402  (the starter bot's evaluator, reused for showdowns)

BLINDS = ((10, 20), (20, 40), (30, 60), (50, 100), (80, 160), (125, 250), (200, 400),
          (300, 600), (500, 1000), (800, 1600), (1200, 2400), (2000, 4000))  # fmt: skip
DECK = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]
FORBIDDEN_IMPORTS = {"poker_engine", "pokerkit"}  # exist only in the local kit; uploads importing them are rejected
# Everything a bot can import on the competition machines besides the standard library.
ALLOWED_LIBRARIES = {"poker_agent_sdk", "poker_agent_protocol", "numpy", "scipy", "pandas", "sklearn",
                     "torch", "lightgbm", "xgboost", "onnxruntime", "numba", "eval7"}  # fmt: skip
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_CODE_BYTES = 1024 * 1024  # of code in agent.py


class CopyPool:
    """A team's bot as the platform runs it: agent.py is imported once, then several copies
    each construct `Agent()`, and any copy may answer any table's turn. A bot that keeps
    table state on `self` therefore breaks here the same way it would in the tournament."""

    def __init__(self, factory, copies=2):
        self.copies = [factory() for _ in range(copies)]
        self.pick = random.Random(0)  # its own generator, so it never disturbs the deals

    def act(self, state, memory):
        return self.pick.choice(self.copies).act(state, memory)


class Table:
    def __init__(self, agents, rng, rules, table_id, record=False, on_failure=None):
        """`record=True` keeps a per-hand replay in `self.hands` (hole cards included).
        `on_failure(seat, hand, reason, detail)` is called for each failed decision.
        Both are optional hooks for tools such as ui/server.py; they do not change play."""
        self.agents, self.rng, self.rules = agents, rng, rules
        self.hands: list[dict] | None = [] if record else None
        self.on_failure = on_failure
        self.n = len(agents)
        self.stacks = [rules.stack] * self.n
        self.button = rng.randrange(self.n)
        self.bust_order: list[int] = []
        # Indexes in bust_order whose seat tied with the one before it (same hand, equal stacks).
        self.ties: set[int] = set()
        self.payouts = draw_payouts(rules, rng)
        self.memory = [b""] * self.n
        self.cursor = [0] * self.n
        self.bank = [float(rules.bank_ms)] * self.n
        self.failures = [0] * self.n
        self.decisions = [0] * self.n
        self.latency: list[list[int]] = [[] for _ in range(self.n)]
        self.log: list[Event] = []
        self.levels = tuple(BlindLevel(small, big) for small, big in BLINDS)
        self.configs = [
            TableConfig(table_id, seat, self.n, "holdem", rules.stack, self.levels,
                        rules.hands_per_level, rules.hand_cap, self.payouts, rules.decision_ms,
                        65536, rules.bank_ms)  # fmt: skip
            for seat in range(self.n)
        ]

    # ------------------------------------------------------------------ a whole table
    def play(self) -> list[float]:
        hand = 0
        while hand < self.rules.hand_cap and sum(stack > 0 for stack in self.stacks) > 1:
            hand += 1
            self.play_hand(hand)
        payouts = list(self.payouts) + [0] * self.n
        points = [0.0] * self.n
        for group in self.bust_groups():
            # Seats that tied share their places and split those places' points.
            share = sum(payouts[self.n - 1 - index] for index in group) / len(group)
            for index in group:
                points[self.bust_order[index]] = share
        survivors = [seat for seat in range(self.n) if self.stacks[seat] > 0]
        shares = icm([self.stacks[seat] for seat in survivors], payouts[: len(survivors)])
        for seat, share in zip(survivors, shares):
            points[seat] = share
        return points

    def bust_groups(self) -> list[list[int]]:
        groups: list[list[int]] = []
        for index in range(len(self.bust_order)):
            if index in self.ties and groups:
                groups[-1].append(index)
            else:
                groups.append([index])
        return groups

    def places(self) -> list[int]:
        """1 = best. Survivors at the hand cap rank by chips; seats that tied share the better place."""
        places = [0] * self.n
        for group in self.bust_groups():
            for index in group:
                places[self.bust_order[index]] = self.n - group[-1]
        for seat in range(self.n):
            if self.stacks[seat] > 0:
                places[seat] = 1 + sum(other > self.stacks[seat] for other in self.stacks)
        return places

    # ------------------------------------------------------------------ one hand
    def next_seat(self, seat, alive):
        for step in range(1, self.n + 1):
            candidate = (seat + step) % self.n
            if candidate in alive:
                return candidate
        return seat

    def play_hand(self, hand):
        n, stacks = self.n, self.stacks
        start = stacks[:]
        alive = {seat for seat in range(n) if stacks[seat] > 0}
        level = min((hand - 1) // self.rules.hands_per_level, len(self.levels) - 1)
        blinds = self.levels[level]
        self.hand_start = len(self.log)
        self.log.append(Event("hand", None, hand))
        deck = DECK[:]
        self.rng.shuffle(deck)
        hole = {seat: (deck.pop(), deck.pop()) for seat in sorted(alive)}
        bet, total, folded = [0] * n, [0] * n, set()
        board: list[str] = []
        if len(alive) == 2:
            small_seat = self.button
        else:
            small_seat = self.next_seat(self.button, alive)
        big_seat = self.next_seat(small_seat, alive)
        for seat, amount in ((small_seat, blinds.small_blind), (big_seat, blinds.big_blind)):
            paid = min(amount, stacks[seat])
            stacks[seat] -= paid
            bet[seat] += paid
            total[seat] += paid
            self.log.append(Event("blind", seat, paid))
        context = dict(hand=hand, level=level, blinds=blinds, alive=alive, hole=hole, bet=bet,
                       total=total, folded=folded, board=board)  # fmt: skip
        # Replay-only events (chips moved without a public event), keyed by log position.
        marks: list[tuple[int, list]] | None = [] if self.hands is not None else None

        first = self.next_seat(big_seat, alive)
        for street in range(4):
            if street:
                dealt = [deck.pop() for _ in range(3 if street == 1 else 1)]
                board.extend(dealt)
                self.log.append(Event("board", None, 0, tuple(dealt)))
                first = self.next_seat(self.button, alive)
            self.betting_round(first, context)
            # Return an uncalled bet, then close the round.
            ordered = sorted(bet, reverse=True)
            if ordered[0] > ordered[1]:
                seat = bet.index(ordered[0])
                refund = ordered[0] - ordered[1]
                stacks[seat] += refund
                total[seat] -= refund
                if marks is not None:
                    marks.append((len(self.log), ["return", seat, refund, []]))
            for seat in range(n):
                bet[seat] = 0
            if len(alive - folded) == 1:
                break

        contenders = alive - folded
        if len(contenders) == 1:
            winner = next(iter(contenders))
            stacks[winner] += sum(total)
            self.log.append(Event("win", winner, sum(total)))
        else:
            while len(board) < 5:
                board.append(deck.pop())
            ranks = {seat: hand_rank(hole[seat] + tuple(board)) for seat in contenders}
            for seat in sorted(contenders):
                self.log.append(Event("show", seat, 0, hole[seat]))
            previous = 0
            for level_amount in sorted({total[seat] for seat in contenders}):
                side = sum(min(c, level_amount) - min(c, previous) for c in total)
                eligible = [seat for seat in contenders if total[seat] >= level_amount]
                best = max(ranks[seat] for seat in eligible)
                winners = sorted(seat for seat in eligible if ranks[seat] == best)
                for index, seat in enumerate(winners):
                    share = side // len(winners) + (1 if index < side % len(winners) else 0)
                    stacks[seat] += share
                    self.log.append(Event("win", seat, share))
                previous = level_amount
            leftover = sum(max(0, c - previous) for c in total)  # folded chips above the top level
            if leftover:
                stacks[max(contenders, key=lambda seat: ranks[seat])] += leftover
                if marks is not None:
                    marks.append((len(self.log), ["leftover", max(contenders, key=lambda seat: ranks[seat]),
                                                  leftover, []]))  # fmt: skip
        for seat in sorted(alive):
            self.log.append(Event("stack", seat, stacks[seat]))
        if marks is not None:
            self.record_hand(hand, level, blinds, start, hole, board, marks)
        # Two bots busting on the same hand: the one that started it with more chips places
        # higher; equal stacks tie.
        busted = sorted((s for s in alive if stacks[s] == 0), key=lambda s: start[s])
        for position, seat in enumerate(busted):
            if position and start[seat] == start[busted[position - 1]]:
                self.ties.add(len(self.bust_order))
            self.bust_order.append(seat)
        self.button = self.next_seat(self.button, {s for s in range(n) if stacks[s] > 0})

    def record_hand(self, hand, level, blinds, start, hole, board, marks):
        events = []
        pending = iter(marks + [(len(self.log) + 1, None)])
        mark = next(pending)
        for index in range(self.hand_start, len(self.log) + 1):
            while mark[0] == index:
                events.append(mark[1])
                mark = next(pending)
            if index < len(self.log):
                event = self.log[index]
                events.append([event.kind, event.seat, event.amount, list(event.cards)])
        self.hands.append({
            "hand": hand, "level": level, "blinds": [blinds.small_blind, blinds.big_blind],
            "button": self.button, "start": start, "end": self.stacks[:],
            "hole": {str(seat): list(cards) for seat, cards in hole.items()},
            "board": list(board), "events": events,
        })  # fmt: skip

    def betting_round(self, first, context):
        stacks, bet, total, folded, alive = (self.stacks, context["bet"], context["total"],
                                             context["folded"], context["alive"])  # fmt: skip
        raise_step = context["blinds"].big_blind
        acted: set[int] = set()
        seat = first
        while True:
            contenders = alive - folded
            if len(contenders) <= 1:
                return
            high = max(bet)
            turn = None
            for step in range(self.n):
                candidate = (seat + step) % self.n
                if candidate in contenders and stacks[candidate] > 0 and (
                    candidate not in acted or bet[candidate] < high
                ):
                    turn = candidate
                    break
            if turn is None:
                return
            others_with_chips = [s for s in contenders if s != turn and stacks[s] > 0]
            owed = high - bet[turn]
            if owed == 0 and not others_with_chips:
                return  # everyone else is all-in and matched: nothing to decide
            legal = [LegalAction("fold"), LegalAction("call")] if owed else [LegalAction("check")]
            ceiling = bet[turn] + stacks[turn]
            if stacks[turn] > owed and others_with_chips:
                legal.append(LegalAction("raise", min(high + raise_step, ceiling), ceiling))
            action = self.ask(turn, min(owed, stacks[turn]), tuple(legal), context)
            acted.add(turn)
            if action.kind == "fold":
                folded.add(turn)
                self.log.append(Event("fold", turn))
            elif action.kind == "check":
                self.log.append(Event("check", turn))
            elif action.kind == "call":
                paid = min(owed, stacks[turn])
                stacks[turn] -= paid
                bet[turn] += paid
                total[turn] += paid
                self.log.append(Event("call", turn, paid))
            else:
                paid = action.amount - bet[turn]
                stacks[turn] -= paid
                bet[turn] += paid
                total[turn] += paid
                if action.amount - high >= raise_step:
                    raise_step = action.amount - high
                self.log.append(Event("raise", turn, action.amount))
            seat = (turn + 1) % self.n

    # ------------------------------------------------------------------ one decision
    def ask(self, seat, to_call, legal, context) -> Action:
        alive, folded = context["alive"], context["folded"]
        seats = tuple(
            Seat(s, self.stacks[s], context["bet"][s],
                 "busted" if s not in alive else "folded" if s in folded
                 else "all_in" if self.stacks[s] == 0 else "active")  # fmt: skip
            for s in range(self.n)
        )
        rules = self.rules
        state = GameState(
            events=tuple(self.log[self.cursor[seat] :]),
            hand_number=context["hand"],
            seat=seat,
            cards=context["hole"][seat],
            board=tuple(context["board"]),
            pot=sum(context["total"]),
            to_call=to_call,
            legal_actions=legal,
            history=tuple(self.log[self.hand_start :]),
            seats=seats,
            button=self.button,
            blind_level=context["level"],
            blinds=context["blinds"],
            hands_until_next_level=rules.hands_per_level - (context["hand"] - 1) % rules.hands_per_level,
            players_remaining=len(alive),
            bust_order=tuple(self.bust_order),
            config=self.configs[seat],
            time_bank_ms=self.bank[seat],
        )
        delivered = len(self.log)  # after a timeout or exception these events are delivered again
        fallback = Action.check() if state.can("check") else Action.fold()
        self.decisions[seat] += 1
        began = time.perf_counter_ns()
        try:
            action, memory = self.agents[seat].act(state, self.memory[seat])
        except Exception:
            self.failures[seat] += 1
            if self.on_failure:
                self.on_failure(seat, context["hand"], "exception", traceback.format_exc(limit=-6))
            return fallback
        elapsed = time.perf_counter_ns() - began
        self.latency[seat].append(elapsed)
        over = elapsed / 1e6 - rules.decision_ms
        if over > 0:
            if over > self.bank[seat]:
                self.bank[seat] = 0.0
                self.failures[seat] += 1
                if self.on_failure:
                    self.on_failure(seat, context["hand"], "timeout",
                                    f"took {elapsed / 1e6:.2f} ms with the time bank exhausted")  # fmt: skip
                return fallback  # a timeout keeps the previous memory
            self.bank[seat] -= over
        self.cursor[seat] = delivered
        if isinstance(memory, bytes):
            self.memory[seat] = memory[:65536]  # stored even when the action turns out illegal
        allowed = state.can(action.kind) if isinstance(action, Action) else None
        if allowed is not None and action.kind == "raise":
            try:  # whole numbers (NumPy's too) pass unchanged; floats are rounded DOWN, not clamped
                action = Action("raise", math.floor(action.amount))
            except (TypeError, ValueError, OverflowError):
                allowed = None
        if allowed is None or (
            action.kind == "raise" and not allowed.min_amount <= action.amount <= allowed.max_amount
        ):
            self.failures[seat] += 1
            if self.on_failure:
                self.on_failure(seat, context["hand"], "illegal action",
                                f"{action!r}; legal: {', '.join(repr(a) for a in legal)}")  # fmt: skip
            return fallback
        return action


# ---------------------------------------------------------------------- commands
def load_agent(directory: Path):
    spec = importlib.util.spec_from_file_location(f"bot_{abs(hash(str(directory)))}", directory / "agent.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(directory))  # a bot may read files shipped next to it
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(directory))
    return CopyPool(module.Agent)


def draw_payouts(rules, rng) -> tuple[int, ...]:
    """The table's points per place. Normally the fixed payouts; with `random_payouts` each
    table draws its own split of 100 over three places (rounds may do this), which shows up
    bots that hard-code 50/30/20 instead of reading `state.config.payouts`."""
    if not getattr(rules, "random_payouts", False):
        return tuple(rules.payouts)
    draw = random.Random(rng.random())
    first = draw.randint(40, 60)
    second = draw.randint(max(21, (100 - first) // 2 + 1), min(first - 1, 100 - first - 5))
    return (first, second, 100 - first - second)


def check(path: Path) -> list[str]:
    """Static upload checks: what the kit's `poker-agent check` rejects (imports of the local-only
    engine), the documented size limits, and imports of libraries the competition machines
    do not have, which would stop the bot from starting there."""
    problems = []
    source = path.read_bytes()
    if len(source) > MAX_CODE_BYTES:
        problems.append("agent.py holds more than 1 MB of code")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"syntax error: {error}"]
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            top = name.split(".")[0]
            if top in FORBIDDEN_IMPORTS:
                problems.append(f"imports {name}, which exists only in the local kit; the upload is rejected")
            elif top and top not in sys.stdlib_module_names and top not in ALLOWED_LIBRARIES \
                    and not (path.parent / f"{top}.py").is_file() and not (path.parent / top).is_dir() \
                    and not (isinstance(node, ast.ImportFrom) and node.level):
                problems.append(f"imports {name}, which is not installed on the competition machines")
    agents = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Agent"]
    if not agents or not any(isinstance(m, ast.FunctionDef) and m.name == "act" for m in agents[0].body):
        problems.append("no `class Agent` with an `act` method")
    return problems


def play(arguments) -> None:
    bots = [bot.resolve() for bot in arguments.bots]
    if not 2 <= len(bots) <= 10 or not all((bot / "agent.py").is_file() for bot in bots):
        sys.exit("Give 2 to 10 bot directories that each contain agent.py.")
    seed = arguments.seed or f"{random.randrange(16**8):08x}"
    labels = [f"{bot.name}#{index}" for index, bot in enumerate(bots)]
    loaded = {bot: load_agent(bot) for bot in set(bots)}
    points = {label: [] for label in labels}
    places = {label: Counter() for label in labels}
    failures: Counter = Counter()
    decisions: Counter = Counter()
    latency = {label: [] for label in labels}
    for number in range(arguments.tables):
        rng = random.Random(f"{seed}:{number}")
        order = list(range(len(bots)))
        rng.shuffle(order)  # seats are reshuffled every table
        table = Table([loaded[bots[index]] for index in order], rng, arguments, f"mini-{number}")
        result = table.play()
        finish = table.places()
        for seat, index in enumerate(order):
            label = labels[index]
            points[label].append(result[seat])
            places[label][finish[seat]] += 1
            failures[label] += table.failures[seat]
            decisions[label] += table.decisions[seat]
            latency[label].extend(table.latency[seat])
    summary = {"seed": seed, "tables": arguments.tables, "bots": {}}
    for label in labels:
        times = sorted(latency[label]) or [0]
        summary["bots"][label] = {
            "average_points": round(sum(points[label]) / len(points[label]), 3),
            "places": dict(sorted(places[label].items())),
            "failed_decisions": failures[label],
            "decisions": decisions[label],
            "latency_us": {
                "p50": round(times[len(times) // 2] / 1000, 1),
                "p99.9": round(times[min(len(times) - 1, int(len(times) * 0.999))] / 1000, 1),
                "max": round(times[-1] / 1000, 1),
            },
        }
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="mini_sim", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check_command = commands.add_parser("check")
    check_command.add_argument("submission", type=Path)
    play_command = commands.add_parser("play")
    play_command.add_argument("bots", type=Path, nargs="+")
    play_command.add_argument("--tables", type=int, default=20)
    play_command.add_argument("--seed", default=None)
    play_command.add_argument("--decision-ms", type=int, default=1)
    play_command.add_argument("--bank-ms", type=int, default=100)
    play_command.add_argument("--hand-cap", type=int, default=250)
    play_command.add_argument("--hands-per-level", type=int, default=20)
    play_command.add_argument("--stack", type=int, default=2000)
    play_command.add_argument("--payouts", type=int, nargs="+", default=[50, 30, 20])
    play_command.add_argument("--random-payouts", action="store_true",
                              help="Each table draws its own split of 100 points over three places.")  # fmt: skip
    play_command.add_argument("--no-history", action="store_true", help="Accepted for compatibility.")
    arguments = parser.parse_args()
    if arguments.command == "check":
        problems = check(arguments.submission)
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
        sys.exit(1 if problems else 0)
    arguments.payouts = tuple(arguments.payouts)
    play(arguments)


if __name__ == "__main__":
    main()
