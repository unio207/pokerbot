"""Fuzz bots with far weirder GameStates than the simulator produces.

    python3 tools/fuzz.py bots/final [more bot dirs...] --states 200000 --seed 1
    options: --max-p999-us N   also fail a bot whose p99.9 decision time exceeds N microseconds

Per bot, over one seeded stream of random states, two passes:
  A  module.DEBUG_RAISE = True: any exception from act() is a failure ("exception").
  B  DEBUG_RAISE = False, each call timed: result must be (Action, bytes); a betting action
     must be legal by the rule in mini_sim.Table.ask ("illegal"); other phases only need an
     Action of a legal kind; memory must be bytes within config.memory_bytes ("memory");
     a repeat call with the same input must agree ("nondeterministic").
Exit code 1 if any bot has any failure. Latency is reported (p50/p99/p99.9/max, calls
over 1000 us). Failures print a compact state and the traceback (first 3 of each type).
"""

import argparse
import gc
import random
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "devtest"))
import mini_sim  # noqa: E402  (also puts the poker_agent_sdk shim on sys.path)
from mini_sim import BLINDS, DECK  # noqa: E402
from poker_agent_sdk import Action, BlindLevel, Event, GameState, LegalAction, Seat, TableConfig  # noqa: E402

PAYOUTS = ((50, 30, 20), (100,), (60, 40), (40, 30, 20, 10), (50, 30, 20, 0))
LEVELS = tuple(BlindLevel(a, b) for a, b in BLINDS)
FOLD, CALL, CHECK = LegalAction("fold"), LegalAction("call"), LegalAction("check")
CHUNK = 4000
SLOW_US = 1000


# ------------------------------------------------------------------ generator
class FastRandom(random.Random):
    """random.Random with cheaper (slightly biased, still seeded and deterministic) helpers, so
    generating a state costs far less than the stdlib's rejection-sampling randint/sample."""

    def randint(self, a, b):
        return a + int(self.random() * (b - a + 1))

    def randrange(self, n):
        return int(self.random() * n)

    def choice(self, seq):
        return seq[int(self.random() * len(seq))]

    def choices(self, population, weights):
        x = self.random() * sum(weights)
        for item, w in zip(population, weights):
            x -= w
            if x < 0:
                break
        return [item]

    def sample(self, population, k):
        out = []
        while len(out) < k:
            item = population[int(self.random() * len(population))]
            if item not in out:
                out.append(item)
        return out


_OLD_HANDS = {}  # n -> prebuilt event blocks of earlier hands (the hand event is rebuilt per use)


def pick_stack(rng, bb):
    r = rng.random()
    if r < 0.03:
        return 0
    if r < 0.06:
        return 1
    if r < 0.20:
        return rng.randint(2, 100)
    if r < 0.70:
        return min(20000, bb * rng.randint(1, 60))
    return rng.randint(0, 20000)


def odd_seat(rng, n):
    return rng.choice((None, -1, n, n + rng.randint(1, 20)))


_EVENTS = {}


def ev(kind, seat, amount=0):
    """Memoised Event: frozen-dataclass construction is the generator's main cost and events are immutable."""
    key = (kind, seat, amount)
    return _EVENTS.get(key) or _EVENTS.setdefault(key, Event(kind, seat, amount))


def action_events(rng, n, hero, bb, count):
    rnd, out = rng.random, []
    for _ in range(count):
        r, x = rnd(), rnd()
        seat = int(x * n) if r > 0.03 else odd_seat(rng, n)
        if r < 0.3:
            out.append(ev("fold", seat))
        elif r < 0.6:
            out.append(ev("call", seat, bb * int(x * 4)))
        elif r < 0.85:
            out.append(ev("raise", seat, bb * (2 + int(rnd() * 39))))
        else:
            out.append(ev("check", seat))
    return out


def board_events(rng, n, hero, bb, board):
    out, cuts = [], {3: (3,), 4: (3, 4), 5: (3, 4, 5)}.get(len(board), ())
    prev = 0
    for cut in cuts:
        out += action_events(rng, n, hero, bb, rng.randint(0, 3))
        out.append(Event("board", None, 0, tuple(board[prev:cut])))
        prev = cut
    return out


def blind_events(rng, n, hero, blinds):
    bb_seat = hero if rng.random() < 0.15 else rng.randrange(n)
    sb_seat = (bb_seat - 1) % n
    r = rng.random()
    out = []
    if r < 0.88 or r > 0.94:
        out.append(ev("blind", sb_seat, rng.choice((blinds.small_blind, blinds.small_blind, 1))))
    if r < 0.88 or r > 0.97:
        out.append(ev("blind", bb_seat, rng.choice((blinds.big_blind, blinds.big_blind, 1))))
    return out


def current_history(rng, n, hero, blinds, hand_number, board):
    out = [ev("hand", None, hand_number)] + blind_events(rng, n, hero, blinds)
    out += action_events(rng, n, hero, blinds.big_blind, rng.randint(0, 8))
    return out + board_events(rng, n, hero, blinds.big_blind, board)


def old_hand(rng, n, hero, blinds):
    cards = rng.sample(DECK, 7)
    board = cards[:rng.choice((0, 3, 5))]
    out = blind_events(rng, n, hero, blinds)
    out += action_events(rng, n, hero, blinds.big_blind, rng.randint(0, 6))
    out += board_events(rng, n, hero, blinds.big_blind, board)
    if rng.random() < 0.5:
        out += [Event("show", s, 0, tuple(rng.sample(DECK, 2))) for s in rng.sample(range(n), min(n, 2))]
    out.append(Event("win", rng.randrange(n), rng.randint(0, 20000)))
    return out + [Event("stack", s, rng.randint(0, 20000)) for s in range(n) if rng.random() < 0.8]


def make_events(rng, n, hero, blinds, hand_number, history):
    r = rng.random()
    if r < 0.40:
        return tuple(history)
    if r < 0.65:
        return tuple(history[rng.randint(0, len(history)):])
    out = []
    pool = _OLD_HANDS.get(n)
    if pool is None:
        pool = _OLD_HANDS[n] = [old_hand(rng, n, rng.randrange(n), BlindLevel(*rng.choice(BLINDS)))
                                for _ in range(48)]  # fmt: skip
    for k in range(rng.randint(1, 3), 0, -1):
        out += [ev("hand", None, max(1, hand_number - k))] + rng.choice(pool)
    return tuple(out + history)


def make_seats(rng, n, hero, bb):
    rnd, seats = rng.random, []
    level = 0 if rnd() < 0.5 else rng.choice((bb, bb * 3, 500, 2000))
    for s in range(n):
        r = rnd()
        status = "active" if s == hero else ("active", "folded", "all_in", "busted")[(r > 0.5) + (r > 0.75) + (r > 0.85)]
        stack = 0 if status in ("all_in", "busted") else pick_stack(rng, bb)
        r = rnd()
        bet = 0 if status == "busted" or r < 0.4 else level if r < 0.76 else int(r * 3000)
        shown = tuple(rng.sample(DECK, 2)) if status == "folded" and r > 0.995 else ()
        seats.append(Seat(s, stack, bet, status, shown))
    return tuple(seats)


def make_legal(rng, stack, bet, pot, bb, to_call_hint):
    to_call = 0
    if rng.random() < 0.8:
        k = rng.randrange(6)  # the price: one blind, many blinds, over the stack, over the pot, 1 chip, anything
        if to_call_hint > 0 and rng.random() < 0.6:
            to_call = to_call_hint
        else:
            to_call = (bb, bb * rng.randint(2, 30), stack + rng.randint(1, 500), pot + rng.randint(1, 500), 1, rng.randint(1, 5000))[k]
        to_call = max(1, to_call)
    legal = [FOLD, CALL] if to_call else [CHECK]
    if rng.random() < 0.7:
        k = rng.randrange(5)
        low = max(1, (bb, bb * 2, to_call * 2, to_call + bb, rng.randint(1, 3000))[k])
        high = max(low, stack + bet) if rng.random() < 0.8 else low + rng.randint(0, 500)
        if rng.random() < 0.15:
            high = low
        legal.append(LegalAction("raise", low, high))
    return to_call, tuple(legal)


def gen_state(rng):
    """One (GameState, memory spec). A memory spec is ('empty',), ('chain',), ('trunc', r) or ('rand', bytes)."""
    n = rng.randint(2, 10)
    hero = rng.randrange(n)
    level = rng.randrange(len(BLINDS))
    sb, bb = BLINDS[level]
    ante = rng.choice((bb // 10, bb // 5, bb // 2, 1)) if rng.random() < 0.25 else 0
    blinds = BlindLevel(sb, bb, ante)
    cap = rng.choice((200, 250))
    hand_number = rng.randint(1, cap) if rng.random() < 0.98 else rng.randint(cap + 1, cap + 20)
    hpl = rng.choice((20, 25))
    seats = make_seats(rng, n, hero, bb)
    me = seats[hero]
    nboard = rng.choice((0, 0, 3, 4, 5))
    phase = "betting" if (r := rng.random()) < 0.97 else "select" if r < 0.99 else "bid"
    nhole = 3 if phase == "select" or rng.random() < 0.03 else 2
    deck = rng.sample(DECK, nhole + nboard)
    hole, board = tuple(deck[:nhole]), tuple(deck[nhole:])
    bets = sum(s.bet for s in seats)
    pot = bets + rng.randint(0, 3000) if rng.random() < 0.7 else rng.choice((0, rng.randint(0, 60000)))
    hint = max(s.bet for s in seats) - me.bet
    to_call, legal = make_legal(rng, me.stack, me.bet, pot, bb, hint)
    if phase == "select":
        to_call, legal = 0, (LegalAction("select"),)
    elif phase == "bid":
        to_call, legal = 0, (LegalAction("bid", 0, 100),)
    history = current_history(rng, n, hero, blinds, hand_number, board)
    alive = sum(s.status != "busted" for s in seats)
    remaining = alive if rng.random() < 0.92 else rng.randint(0, 12)
    busted = [s.seat for s in seats if s.status == "busted"]
    rng.shuffle(busted)
    config = TableConfig(
        "fuzz", hero, n, "holdem", rng.choice((10000, rng.randint(500, 20000))),
        LEVELS, hpl, cap, rng.choice(PAYOUTS), 1000,
        rng.choice((16384, 65536)), rng.choice((0, 0, rng.randint(1, 5000))),
    )  # fmt: skip
    state = GameState(
        events=make_events(rng, n, hero, blinds, hand_number, history), hand_number=hand_number, seat=hero,
        cards=hole, board=board, pot=pot, to_call=to_call, legal_actions=legal, history=tuple(history),
        seats=seats, button=rng.randrange(n), blind_level=level, blinds=blinds,
        hands_until_next_level=hpl - (hand_number - 1) % hpl if rng.random() < 0.9 else rng.randint(0, 30),
        players_remaining=remaining, bust_order=tuple(busted), config=config, phase=phase,
        time_bank_ms=float(rng.randint(0, 5000)),
    )  # fmt: skip
    r = rng.random()
    if r < 0.1:
        spec = ("empty",)
    elif r < 0.8:
        spec = ("chain",)
    elif r < 0.9:
        spec = ("trunc", rng.random())
    else:
        spec = ("rand", rng.randbytes(rng.randint(0, 300)))
    return state, spec


def memory_for(spec, previous):
    return {"empty": lambda: b"", "chain": lambda: previous,
            "trunc": lambda: previous[: int(len(previous) * spec[-1])] if spec[0] == "trunc" else b"",
            "rand": lambda: spec[-1]}[spec[0]]()  # fmt: skip


# ------------------------------------------------------------------ checks
def verdict(state, memory, result):
    """Return (failure_type, detail) for a Pass-B result, or None if it is fine."""
    if not (isinstance(result, tuple) and len(result) == 2):
        return "bad_return", f"not a 2-tuple: {result!r}"[:200]
    action, out = result
    if not isinstance(action, Action):
        return "bad_return", f"not an Action: {action!r}"[:200]
    allowed = state.can(action.kind)
    if allowed is None:
        return "illegal", f"{action!r} not among {[a.kind for a in state.legal_actions]}"
    if state.phase == "betting" and action.kind == "raise" and not (
        type(action.amount) is int and allowed.min_amount <= action.amount <= allowed.max_amount
    ):
        return "illegal", f"{action!r} outside [{allowed.min_amount}, {allowed.max_amount}]"
    if type(out) is not bytes:
        return "memory", f"memory is {type(out).__name__}, not bytes"
    if len(out) > state.config.memory_bytes:
        return "memory", f"{len(out)} bytes > limit {state.config.memory_bytes}"
    return None


def brief(state, spec, memory):
    me = state.seats[state.seat]
    return (f"phase={state.phase} hand={state.hand_number}/{state.config.hand_cap} seat={state.seat}/{len(state.seats)} "
            f"cards={state.cards} board={state.board} pot={state.pot} to_call={state.to_call} "
            f"stack={me.stack} bet={me.bet} legal={[(a.kind, a.min_amount, a.max_amount) for a in state.legal_actions]} "
            f"blinds={state.blinds.small_blind}/{state.blinds.big_blind}+{state.blinds.ante} "
            f"left={state.players_remaining} status={''.join(s.status[0] for s in state.seats)} "
            f"hist={len(state.history)} events={len(state.events)} mem={spec[0]}:{len(memory)}B")


# ------------------------------------------------------------------ driver
def fuzz_bot(directory, states, seed, max_p999):
    agent = mini_sim.load_agent(Path(directory))
    flags = type(agent).act.__globals__  # the bot module's namespace (load_agent does not register it)
    rng = FastRandom(seed)
    counts, shown, lat = Counter(), Counter(), []
    mem_a = mem_b = b""
    gen_time = 0.0
    fails = []

    def fail(kind, state, spec, memory, detail):
        counts[kind] += 1
        if shown[kind] < 3:
            shown[kind] += 1
            fails.append(f"  [{kind}] {brief(state, spec, memory)}\n    {detail.rstrip().replace(chr(10), chr(10) + '    ')}")

    gc.collect()
    gc.disable()  # as in ui/server.py: a collection inside a timed call would be a false slow call
    done = 0
    while done < states:
        t0 = time.perf_counter()
        chunk = [gen_state(rng) for _ in range(min(CHUNK, states - done))]
        gen_time += time.perf_counter() - t0
        done += len(chunk)
        flags["DEBUG_RAISE"] = True
        for state, spec in chunk:
            memory = memory_for(spec, mem_a)
            try:
                result = agent.act(state, memory)
                if isinstance(result, tuple) and len(result) == 2 and type(result[1]) is bytes:
                    mem_a = result[1][: state.config.memory_bytes]
            except Exception:
                fail("exception", state, spec, memory, traceback.format_exc(limit=-6))
        flags["DEBUG_RAISE"] = False
        for state, spec in chunk:
            memory = memory_for(spec, mem_b)
            try:
                began = time.perf_counter_ns()
                result = agent.act(state, memory)
                lat.append(time.perf_counter_ns() - began)
                again = agent.act(state, memory)
            except Exception:
                fail("exception_B", state, spec, memory, traceback.format_exc(limit=-6))
                continue
            problem = verdict(state, memory, result)
            if problem:
                fail(problem[0], state, spec, memory, problem[1])
            elif again != result:
                fail("nondeterministic", state, spec, memory, f"{result!r}\n  vs {again!r}"[:300])
            if isinstance(result, tuple) and len(result) == 2 and type(result[1]) is bytes:
                mem_b = result[1][: state.config.memory_bytes]
        gc.collect(1)
    gc.enable()
    lat.sort()
    us = lambda q: lat[min(len(lat) - 1, int(len(lat) * q))] / 1000 if lat else 0.0  # noqa: E731
    slow = sum(x > SLOW_US * 1000 for x in lat)
    p999 = us(0.999)
    bad = sum(counts.values()) > 0 or (max_p999 is not None and p999 > max_p999)
    fails_text = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"
    print(f"{directory}: {states} states, failures: {fails_text} | latency us p50={us(0.5):.0f} p99={us(0.99):.0f} "
          f"p99.9={p999:.0f} max={(lat[-1] / 1000 if lat else 0):.0f}, >{SLOW_US}us: {slow} "
          f"| gen {states / max(gen_time, 1e-9):,.0f} states/s")  # fmt: skip
    if max_p999 is not None and p999 > max_p999:
        print(f"  p99.9 {p999:.0f} us exceeds --max-p999-us {max_p999}")
    print("\n".join(fails))
    return bad


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("bots", nargs="+", help="bot directories, each holding agent.py")
    parser.add_argument("--states", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-p999-us", type=float, default=None)
    args = parser.parse_args()
    results = [fuzz_bot(d, args.states, args.seed, args.max_p999_us) for d in args.bots]
    sys.exit(1 if any(results) else 0)


if __name__ == "__main__":
    main()
