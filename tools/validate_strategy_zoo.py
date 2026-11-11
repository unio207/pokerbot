"""Focused standalone zoo validation with the unofficial SDK shim.

Run: python3 tools/validate_strategy_zoo.py [--decisions 20000]
Generates diverse decision states; reinstantiates Agent at every decision so bots
cannot rely on instance state. This is a legality/memory/regression test, not a
strength estimate or certification by the organizers' runtime. Exceptions surface.
"""

import argparse
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "devtest" / "shim"))
from poker_agent_sdk import (Action, BlindLevel, Event, GameState, LegalAction,
                             Seat, TableConfig, icm)

NAMES = ("survival_icm", "chip_ev", "steal_value", "shove_aware", "adaptive_icm")
DECK = tuple(rank + suit for rank in "23456789TJQKA" for suit in "cdhs")
BAD_MEMORY = (b"", b"\xff", b"[]", b"null", b"{}", b'{"s":[]}',
              b'{"hand":null,"seen":"bad"}', b"{" + b"x" * 17000)


def load(name):
    path = ROOT / "zoo" / f"codex_{name}_1" / "agent.py"
    spec = importlib.util.spec_from_file_location(f"validate_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scenario(rng, index):
    n = (2, 3, 4, 8)[index % 4]
    hero = rng.randrange(n)
    villain = (hero + 1) % n
    bb = rng.choice((2, 20, 100, 400, 1600))
    depth = rng.choice((1, 2, 3, 5, 8, 10, 12, 15, 20, 40, 100))
    stacks = [max(1, int(bb * depth * rng.choice((.25, .5, 1, 2)))) for _ in range(n)]
    if n == 4 and index % 3 == 0:
        stacks = [6 * bb, 6 * bb, 3 * bb, bb]
    facing = index % 3 != 0
    hero_bet = rng.choice((0, bb // 2, bb))
    call = min(stacks[hero], rng.choice((1, bb, 2 * bb, max(1, stacks[hero] // 2), stacks[hero]))) if facing else 0
    villain_bet = hero_bet + call + (rng.randrange(1, bb + 1) if call == stacks[hero] else 0)
    statuses = ["active"] * n
    bets = [0] * n
    bets[hero] = hero_bet
    bets[villain] = villain_bet if facing else hero_bet
    if facing and index % 2:
        statuses[villain], stacks[villain] = "all_in", 0
    for other in range(n):
        if other not in (hero, villain) and rng.random() < .3:
            statuses[other] = "folded"
    seats = tuple(Seat(i, stacks[i], bets[i], statuses[i]) for i in range(n))
    if n < 8 and index % 5 == 0:
        seats += tuple(Seat(i, 0, 0, "busted") for i in range(n, 8))
    legal = [LegalAction("fold"), LegalAction("call")] if call else [LegalAction("check")]
    ceiling = hero_bet + stacks[hero]
    minimum = min(ceiling, max(bets) + bb)
    if ceiling > max(bets) and any(s.stack > 0 and s.status == "active" and s.seat != hero for s in seats):
        legal.append(LegalAction("raise", minimum, ceiling))
    if index % 31 == 0:
        legal = [LegalAction("call")] if call else [LegalAction("check")]
    payout = ((50, 30, 20), (100,), (70, 30), (25, 25, 25, 25), (60, 25, 10, 5))[index % 5]
    cards = rng.sample(DECK, 7)
    board_len = (0, 3, 4, 5)[(index // 4) % 4]
    board = tuple(cards[2:2 + board_len])
    button = rng.randrange(n)
    blind = BlindLevel(max(1, bb // 2), bb)
    config = TableConfig(f"validation-{index // 100}", hero, len(seats), "holdem", 2000,
                         (blind,), 20, 250, payout, 1, 16384, 100)
    history = [Event("hand", None, index + 1), Event("blind", button, blind.small_blind),
               Event("blind", (button + 1) % n, bb)]
    if board:
        history.append(Event("board", None, 0, board))
    if facing:
        history.append(Event("raise", villain, villain_bet))
    pot = sum(bets) + rng.choice((0, bb, 3 * bb, 10 * bb))
    state = GameState(tuple(history), index + 1, hero, tuple(cards[:2]), board,
                      max(1, pot), call, tuple(legal), tuple(history), seats, button,
                      0, blind, rng.randrange(1, 21), n, tuple(range(n, len(seats))), config)
    if index % 37 == 0:
        state = replace(state, phase="unknown_variant", cards=tuple(cards[:3]),
                        legal_actions=(LegalAction("bid", 3, 17),))
    return state


def legal(action, state):
    assert isinstance(action, Action), ("wrong action type", action)
    permit = state.can(action.kind)
    assert permit is not None, ("illegal kind", action, state.legal_actions)
    if action.kind == "raise":
        assert type(action.amount) is int and permit.min_amount <= action.amount <= permit.max_amount, (
            "illegal raise", action, permit)
    if state.phase != "betting":
        assert action.kind == state.legal_actions[0].kind and action.amount == state.legal_actions[0].min_amount


def replay_checks(modules, decisions):
    report = {}
    for name, module in modules.items():
        rng = random.Random("strategy-zoo-decisions")
        memory = b""
        cpu, wall = [], []
        max_memory = 0
        for index in range(decisions):
            state = scenario(rng, index)
            if index % 100 == 0:
                memory = b""
            supplied = BAD_MEMORY[(index // 7) % len(BAD_MEMORY)] if index % 7 == 0 else memory
            started_cpu, started_wall = time.process_time_ns(), time.perf_counter_ns()
            # Construct anew every turn, exactly as the stateless contract allows.
            result = module.Agent().act(state, supplied)
            wall.append((time.perf_counter_ns() - started_wall) / 1000)
            cpu.append((time.process_time_ns() - started_cpu) / 1000)
            assert isinstance(result, tuple) and len(result) == 2, (name, index, result)
            action, memory = result
            legal(action, state)
            assert isinstance(memory, bytes), (name, index, "memory is not bytes")
            assert len(memory) <= min(16384, state.config.memory_bytes), (name, index, "memory exceeds limit")
            max_memory = max(max_memory, len(memory))
        ordered_cpu, ordered_wall = sorted(cpu), sorted(wall)
        report[name] = {"decisions": decisions, "failed": 0, "max_memory_bytes": max_memory,
                        "cpu_us": {"median": round(statistics.median(cpu), 2),
                                   "p99": round(ordered_cpu[int(.99 * (decisions - 1))], 2),
                                   "max": round(max(cpu), 2)},
                        "wall_us": {"median": round(statistics.median(wall), 2),
                                    "p99": round(ordered_wall[int(.99 * (decisions - 1))], 2),
                                    "max": round(max(wall), 2)}}
    return report


def utility_checks(modules):
    rng = random.Random("icm-differential")
    count = 0
    for name in ("survival_icm", "shove_aware", "adaptive_icm"):
        module = modules[name]
        helper = getattr(module, "utility", None) or getattr(module, "icm_hero", None)
        assert helper is not None, (name, "missing ICM utility")
        for _ in range(80):
            n = rng.choice((2, 3, 4, 8))
            stacks = [rng.choice((1, 10, 100, 1000, 6000)) for _ in range(n)]
            payouts = rng.choice(((50, 30, 20), (100,), (70, 30)))
            expected = icm(stacks, payouts)
            for hero in range(n):
                actual = helper(stacks, hero, payouts)
                assert math.isclose(actual, expected[hero], abs_tol=1e-8), (name, stacks, hero, payouts, actual, expected[hero])
                count += 1
            hero = rng.randrange(n)
            stacks[hero] = 0
            survivors = sum(stack > 0 for stack in stacks)
            # Unlike shim.icm's zero share for eliminated seats, action utility must
            # include the guaranteed finishing payout for our just-busted hero.
            expected_bust = payouts[survivors] if survivors < len(payouts) else 0.
            actual = helper(stacks, hero, payouts)
            assert math.isclose(actual, expected_bust, abs_tol=1e-8), (name, "bust", actual, expected_bust)
            count += 1
    return count


def closing_call_state(hero_stack, villain_bet, dead=0):
    blind = BlindLevel(5, 10)
    payouts = (50, 30, 20)
    seats = (Seat(0, hero_stack, 0, "active"), Seat(1, 0, villain_bet, "all_in"),
             Seat(2, 100, dead, "folded"), Seat(3, 100, 0, "folded"))
    config = TableConfig("outcome", 0, 4, "holdem", 100, (blind,), 20, 250,
                         payouts, 1, 16384, 100)
    history = (Event("hand", None, 1), Event("blind", 2, dead),
               Event("fold", 2), Event("raise", 1, villain_bet),)
    return GameState(history, 1, 0, ("As", "Kd"), (), villain_bet + dead,
                     min(hero_stack, villain_bet), (LegalAction("fold"), LegalAction("call")),
                     history, seats, 3, 0, blind, 20, 4, (), config)


def outcome_checks(modules):
    count = 0
    for hero_stack, villain_bet, dead in ((100, 100, 0), (100, 300, 40), (300, 100, 70), (100, 300, 250)):
        state = closing_call_state(hero_stack, villain_bet, dead)
        call = min(hero_stack, villain_bet)
        refund = max(0, villain_bet - call)
        # Independently construct terminal chip accounting, including dead money
        # from a folded seat and an uncallable overbet returned to the aggressor.
        fold = [hero_stack, villain_bet + dead, 100, 100]
        win = [hero_stack + call + min(dead, call), refund + max(0, dead - call), 100, 100]
        lose = [hero_stack - call, villain_bet + dead + call, 100, 100]
        total = hero_stack + villain_bet + dead + 200
        assert sum(fold) == sum(win) == sum(lose) == total
        def value(chips):
            if chips[0] == 0:
                remaining = sum(x > 0 for x in chips)
                return state.config.payouts[remaining] if remaining < len(state.config.payouts) else 0.
            return icm(chips, state.config.payouts)[0]
        threshold = (value(fold) - value(lose)) / (value(win) - value(lose))
        actual = modules["survival_icm"].required_equity(state, state.seats[0], True)
        assert math.isclose(actual, threshold, abs_tol=1e-8), ("survival outcome", hero_stack, villain_bet, dead, actual, threshold)
        count += 1
        for name in ("shove_aware", "adaptive_icm"):
            actual_outcomes = modules[name].outcomes(state, state.seats[1])
            assert actual_outcomes is not None, (name, "supported closing pot rejected")
            af, aw, al, at, eligible = actual_outcomes
            assert af == fold and aw == win and al == lose, (name, actual_outcomes, (fold, win, lose))
            assert sum(at) == total, (name, "tie chips not conserved", at, total)
            assert eligible == 2 * call + min(dead, call), (name, "incorrect eligible pot", eligible)
            count += 1
    for name in ("survival_icm", "chip_ev"):
        state = closing_call_state(100, 300)
        state = replace(state, seats=state.seats[:2], players_remaining=2,
                        config=replace(state.config, players=2))
        actual = modules[name].required_equity(state, state.seats[0], name == "survival_icm")
        assert math.isclose(actual, .5, abs_tol=1e-8), (name, "heads-up uncallable overbet", actual, .5)
        count += 1
    return count


def opponent_checks(modules):
    count = 0
    state = closing_call_state(2000, 2000)
    state = replace(state, config=replace(state.config, starting_stack=2000),
                    blinds=BlindLevel(10, 20))
    for name in ("shove_aware", "adaptive_icm"):
        module = modules[name]
        for opportunities, raises, expected in ((6, 6, 2), (10, 8, 5), (16, 15, 6), (20, 2, 0)):
            events = []
            for hand in range(opportunities):
                events.extend((Event("hand", None, hand + 1), Event("blind", 0, 20),
                               Event("raise", 1, 2000) if hand < raises else Event("fold", 1)))
            observed = replace(state, events=tuple(events))
            notes = module.observe(observed, b"")
            actual = module.range_bucket(observed, notes, 1)
            assert actual == expected, (name, "range bucket", opportunities, raises, actual, expected)
            memory = json.dumps(notes, separators=(",", ":")).encode()
            after_empty = module.observe(replace(observed, events=()), memory)
            assert after_empty == notes, (name, "evidence counted without new events")
            # Replaying the same input is deterministic even with a fresh instance.
            first = module.Agent().act(observed, b"")
            second = module.Agent().act(observed, b"")
            assert first == second, (name, "instance-dependent result")
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=int, default=20000, help="generated decisions per bot (default 20000)")
    args = parser.parse_args()
    assert args.decisions > 0
    modules = {name: load(name) for name in NAMES}
    result = {"icm_differential_cases": utility_checks(modules),
              "closing_call_outcomes": outcome_checks(modules),
              "opponent_classification_cases": opponent_checks(modules),
              "bots": replay_checks(modules, args.decisions)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
