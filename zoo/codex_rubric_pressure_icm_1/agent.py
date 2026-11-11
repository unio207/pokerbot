"""Vedaant Seceret Strategies HeHeHe: RubricPressure ICM zoo opponent (strategy F).

Source:   Claude (Fable 5.2), implementing Vedaant's design in zoo/VEDAANT_SECERET_STRATEGIES.md
Profile:  F. Strong zoo opponent. Scheduled steals plus postflop pressure, tempered by ICM.
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    Rubric decisions (fixed prior + bounded points, clipped); per-seat fold counters
          used only after 10 samples; small c-bets, probes and semibluff raises; value and
          pressure lines combined cautiously near the bubble. Shove/fold under 13 BB.

All numbers are hand-set estimates, not solver output. No rollouts, no state outside
`memory`. Variants added 2026-11-11 (Claude Code): the section at the end hands this unchanged
hold'em strategy a hold'em-shaped hand; unknown phases still take the first legal choice.
"""

import json
import dataclasses
from bisect import bisect_left
from itertools import combinations

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANKS = "23456789TJQKA"
N_MIN, N_FULL = 10, 24  # samples before a read is used at all / at full weight
STEP = 0.04  # one rubric point
MEMORY_CAP = 4096
# Base rates. Open and shove fractions are indexed by players still to act behind us.
OPEN = (0.10, 0.45, 0.40, 0.28, 0.22, 0.17, 0.14, 0.12, 0.11, 0.10)
SHOVE = (0.10, 0.55, 0.40, 0.30, 0.24, 0.20, 0.17, 0.15, 0.14, 0.13)
PRIOR = {"cbet": 0.55, "barrel4": 0.30, "barrel5": 0.20, "stab": 0.12, "probe": 0.18, "raise": 0.03}
MADE = (0.12, 0.0, 0.80, 0.88, 0.90, 0.92, 0.96, 0.99, 0.995)  # strength by hand category


def clip(value, low, high):
    return low if value < low else high if value > high else value


def chen(high, low, suited):
    """Chen-formula score, used only to order the 169 starting hands."""
    top = {14: 10.0, 13: 8.0, 12: 7.0, 11: 6.0}.get(high, high / 2)
    if high == low:
        return max(5.0, top * 2)
    gap = high - low - 1
    score = top + (2 if suited else 0) - (0, 1, 2, 4, 5)[min(gap, 4)]
    return score + (1 if gap <= 1 and high < 12 else 0) + low / 100


def percentiles():
    hands = [(chen(high, low, suited), high, low, suited, 6 if high == low else 4 if suited else 12)
             for high in range(2, 15) for low in range(2, high + 1)
             for suited in ((False,) if high == low else (False, True))]
    table, seen = {}, 0
    for _, high, low, suited, combos in sorted(hands, reverse=True):
        table[high, low, suited] = (seen + combos / 2) / 1326
        seen += combos
    return table


PCT = percentiles()  # built once at import, read-only afterwards


# ------------------------------------------------------------------------ legal actions
def fallback(state):
    if state.can("check"):
        return Action.check()
    if state.can("fold"):
        return Action.fold()
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def call(state):
    return Action.call() if state.can("call") else fallback(state)


def raise_to(state, total):
    legal = state.can("raise")
    if legal:
        return Action.raise_to(max(legal.min_amount, min(legal.max_amount, int(total))))
    return call(state)


def shove(state):
    legal = state.can("raise")
    return Action.raise_to(legal.max_amount) if legal else call(state)


# ------------------------------------------------------------------------------- memory
def load_memory(memory):
    try:
        data = json.loads(memory) if 0 < len(memory) <= MEMORY_CAP else None
        if not isinstance(data, dict) or not isinstance(data.get("s"), dict) or len(data["s"]) > 16:
            raise ValueError
        for row in data["s"].values():
            if not isinstance(row, list) or len(row) != 6 or any(type(n) is not int or n < 0 for n in row):
                raise ValueError
        for key in ("p", "b", "r"):
            data[key] = bool(data.get(key))
        for key in ("h", "c"):
            data[key] = data.get(key) if type(data.get(key)) is int else 0
    except (ValueError, TypeError, UnicodeDecodeError):
        data = {"s": {}, "p": True, "b": False, "r": False, "h": -1, "c": 0}
    return data


def observe(state, data):
    """Fold the events since our last turn into per-seat counters.

    Row: [preflop actions, folds, calls, raises, postflop turns facing a bet, folds to it].
    """
    for event in state.events[-96:]:
        kind = event.kind
        if kind == "hand":
            data["p"], data["b"], data["r"], data["c"] = True, False, False, 0
        elif kind == "board":
            data["p"], data["b"] = False, False
        elif kind in ("fold", "call", "raise") and event.seat is not None:
            if event.seat != state.seat:
                row = data["s"].get(str(event.seat))
                if row is None and len(data["s"]) < 16:
                    row = data["s"].setdefault(str(event.seat), [0, 0, 0, 0, 0, 0])
                if row is not None and data["p"]:
                    row[0] += 1
                    row[("fold", "call", "raise").index(kind) + 1] += 1
                    if kind == "raise":
                        data["r"] = False  # someone raised after us: not the aggressor
                elif row is not None and data["b"]:
                    row[4] += 1
                    row[5] += kind == "fold"
                if row is not None and (row[0] > 400 or row[4] > 400):
                    row[:] = [n // 2 for n in row]
            if kind == "raise":
                data["b"] = True
    if data["h"] != state.hand_number:
        data["h"] = state.hand_number
        if state.board or not data["p"]:
            data["r"], data["c"] = False, 0
    data["p"] = not state.board


def fit(hits, n, prior, low, high):
    """Fixed prior until N_MIN samples, then move toward the observed rate, clamped."""
    if n < N_MIN:
        return prior
    weight = min(1.0, (n - N_MIN + 1) / (N_FULL - N_MIN + 1))
    return clip(prior + weight * (hits / n - prior), low, high)


def row_of(data, seat):
    return data["s"].get(str(seat.seat), (0, 0, 0, 0, 0, 0))


def is_station(data, seat):
    row = row_of(data, seat)
    return (row[0] >= N_MIN and row[2] / row[0] >= 0.5) or (row[4] >= N_MIN and row[5] / row[4] <= 0.25)


# ---------------------------------------------------------------------------------- ICM
def icm_pressure(state, hero, bb):
    """0 (chips are points) to 0.8 (busting now is very costly). A rubric, not exact ICM."""
    paid = sum(1 for points in state.config.payouts if points > 0)
    left = state.players_remaining
    if left <= 2 or paid == 0:
        return 0.0, False
    stacks = [seat.stack + seat.bet for seat in state.seats if seat.status != "busted"]
    mine = hero.stack + hero.bet
    leader = mine >= max(stacks)
    gap = max(0, left - paid)  # places still to bust before everyone left is paid
    pressure = (0.30, 0.60, 0.40, 0.25)[gap] if gap <= 3 else 0.12
    if leader:
        pressure -= 0.15
    elif mine <= min(stacks):
        pressure -= 0.10  # shortest stack cannot wait for anyone
    elif any(stack <= 5 * bb for stack in stacks if stack < mine):
        pressure += 0.10  # someone else is about to bust
    if mine <= 6 * bb:
        pressure *= 0.5
    return clip(pressure, 0.0, 0.8), leader


# ------------------------------------------------------------------------------ preflop
def preflop(state, data, hero, opponents, bb, pressure, leader):
    values = sorted((RANKS.index(card[0]) + 2 for card in state.cards), reverse=True)
    if len(values) != 2:
        return fallback(state)
    high, low = values
    pct = PCT[high, low, high != low and state.cards[0][1] == state.cards[1][1]]
    equity = 0.50 + 0.029 * (high - 2) if high == low else 0.63 - 0.30 * pct
    cautious = pressure >= 0.5
    total = hero.stack + hero.bet
    depth = total / bb
    top_bet = max(seat.bet for seat in state.seats)

    if top_bet > bb:  # facing a raise
        raiser = max(opponents, key=lambda seat: seat.bet)
        row = row_of(data, raiser)
        jammed = raiser.status == "all_in"
        width = clip(0.9 - 0.055 * (raiser.stack + raiser.bet) / bb, 0.10, 0.70) if jammed else 0.18
        if row[0] >= N_MIN:
            width = clip(0.5 * width + 0.5 * min(0.9, 1.3 * row[3] / row[0]), 0.05, 0.90)
        if data["r"] and not jammed:
            width = min(width, 0.10)  # re-raised over our open
        callers = sum(1 for seat in opponents if seat.bet >= top_bet) - 1
        equity -= 0.20 * (1 - width) ** 2 + 0.03 * callers
        odds = state.to_call / max(1, state.pot + state.to_call)
        commit = min(1.0, state.to_call / max(1, hero.stack))
        margin = 0.03 + 0.20 * pressure * commit
        if pct <= (0.04 if width < 0.3 else 0.09) and state.can("raise"):
            data["r"] = True
            if depth <= 20 or commit >= 0.25:
                return shove(state)
            return raise_to(state, 3 * top_bet)
        if depth <= 15 and not jammed and width >= 0.3 and pct <= 0.15 and not cautious and state.can("raise"):
            return shove(state)  # resteal against a frequent raiser
        cheap = state.to_call <= 1.5 * bb and commit < 0.10
        if equity >= odds + margin and pct <= (0.55 if cheap else 1.0 if commit >= 0.5 else 0.22):
            return call(state)
        return fallback(state)

    # Unopened (or limped) pot. Who is still to act behind us?
    count = max(seat.seat for seat in state.seats) + 1
    ring = sorted((seat.seat for seat in state.seats if seat.status != "busted"),
                  key=lambda seat: (seat - state.button - 1) % count)
    heads_up = len(ring) == 2
    order = ring[1:] + ring[:1] if heads_up else ring[2:] + ring[:2]
    later = order[order.index(state.seat) + 1:] if state.seat in order else []
    behind = [seat for seat in opponents if seat.seat in later and seat.status == "active"]
    limpers = max(0, sum(1 for seat in opponents if seat.bet >= bb) - (1 if hero.bet < bb else 0))
    points = -min(3, limpers)
    rows = [row_of(data, seat) for seat in behind]
    if rows and all(row[0] >= N_MIN for row in rows):
        folds = sum(fit(row[1], row[0], 0.62, 0.30, 0.92) for row in rows) / len(rows)
        points += 3 if folds >= 0.80 else 1 if folds >= 0.70 else -2 if folds <= 0.50 else 0
    station = any(is_station(data, seat) for seat in behind)
    points -= 1 if station else 0
    if cautious:
        points += 2 if leader else -2
    nb = min(len(behind), 9)
    if depth <= 13:
        base = 0.65 if heads_up and nb else SHOVE[nb]
        points += 3 if depth <= 6 else 1 if depth <= 9 else 0
        return shove(state) if pct < clip(base + STEP * points, 0.05, 0.95) else fallback(state)
    if any(seat.stack <= 8 * bb for seat in behind):
        points -= 1
    base = (0.70 if nb else 0.30) if heads_up else OPEN[nb]
    if pct >= clip(base + STEP * points, 0.06, 0.95):
        return fallback(state)
    size = 3 * bb if station else int((2.5 if nb == 1 and not heads_up else 2.2) * bb)
    size += limpers * bb
    data["r"] = True
    return shove(state) if size >= 0.4 * total else raise_to(state, size)


# ----------------------------------------------------------------------------- postflop
def straight_top(values):
    if 14 in values:
        values = values | {1}
    return next((top for top in range(14, 4, -1) if all(v in values for v in range(top - 4, top + 1))), 0)


def made(cards):
    """(category 0-8, tie-breakers) for 3 to 7 cards."""
    values = sorted((RANKS.index(card[0]) + 2 for card in cards), reverse=True)
    suits = {}
    for card, value in zip(sorted(cards, key=lambda c: -RANKS.index(c[0])), values):
        suits.setdefault(card[1], []).append(value)
    flush = next((group for group in suits.values() if len(group) >= 5), None)
    if flush and straight_top(set(flush)):
        return 8, straight_top(set(flush))
    groups = sorted(((values.count(v), v) for v in set(values)), reverse=True)
    (first_n, first), (second_n, second) = groups[0], (groups[1] if len(groups) > 1 else (0, 0))
    if first_n == 4:
        return 7, first, max((v for v in values if v != first), default=0)
    if first_n == 3 and second_n >= 2:
        return 6, first, second
    if flush:
        return (5, *flush[:5])
    if straight_top(set(values)):
        return 4, straight_top(set(values))
    kickers = [v for v in values if v != first]
    if first_n == 3:
        return (3, first, *kickers[:2])
    if first_n == 2 and second_n == 2:
        return 2, first, second, max((v for v in values if v not in (first, second)), default=0)
    if first_n == 2:
        return (1, first, *kickers[:3])
    return (0, *values[:5])


def read_hand(state, extra_opponents):
    """Strength line (rough equity when called), draw outs, and board texture."""
    hole = [RANKS.index(card[0]) + 2 for card in state.cards]
    board = [RANKS.index(card[0]) + 2 for card in state.board]
    mine, table = made(tuple(state.cards) + tuple(state.board)), made(state.board)
    category, top, ordered = mine[0], max(board), sorted(set(board), reverse=True)
    if category == table[0]:  # the board already has this category: do we improve on it?
        if category == 1:
            strength = 0.28 if max(hole) >= 13 else 0.22
        elif category == 2:
            strength = 0.60 if mine[1:3] != table[1:3] else 0.25
        elif category == 0:
            strength = 0.20 if min(hole) > top and len(board) < 5 else 0.12
        else:
            strength = 0.15 if mine[:len(table)] == table else 0.70 if category >= 4 else 0.35
    elif category == 1:
        pair, pocket = mine[1], hole[0] == hole[1]
        if pocket and pair > top:
            strength = 0.72
        elif pair == top:
            strength = 0.66 if min(hole) >= 11 or max(hole) >= 13 and pair != max(hole) else 0.57
        else:
            strength = 0.44 if pocket or (len(ordered) > 1 and pair >= ordered[1]) else 0.34
    elif category == 2 and table[0] == 1:  # one pair of ours plus the board's pair
        ours = mine[1] if mine[1] != table[1] else mine[2]
        strength = 0.60 if ours >= max((v for v in board if v != table[1]), default=0) else 0.45
    else:
        strength = 0.82 if category == 3 and table[0] == 1 else MADE[category]

    board_suits = [card[1] for card in state.board]
    suited = max(board_suits.count(suit) for suit in set(board_suits))
    spread = set(board) | ({1} if 14 in board else set())
    run = max(sum(v in spread for v in range(low, low + 5)) for low in range(1, 11))
    if category < 5:
        strength -= 0.22 if suited >= 4 else 0.07 if suited == 3 else 0.0
    if category < 4 and run >= 4:
        strength -= 0.15
    strength -= min(0.18, 0.06 * extra_opponents)

    outs = 0
    if len(board) < 5:
        if category < 5:
            for suit in set(card[1] for card in state.cards):
                held = sum(card[1] == suit for card in state.cards)
                if held + board_suits.count(suit) == 4:
                    outs += 9 if held == 2 else 7
        if category < 4:
            have = set(hole) | set(board)
            fills = [v for v in range(2, 15) if v not in have and straight_top(have | {v})
                     and not straight_top(set(board) | {v})]
            outs += min(8, 4 * len(fills))
        if category == 0:
            outs += 2 * sum(v > top for v in hole)
    texture = {"dry": suited <= 2 and run <= 2, "wet": suited >= 3 or run >= 4 or (suited == 2 and run >= 3),
               "paired": len(set(board)) < len(board),
               "scare": len(board) >= 4 and board[-1] >= 13 and board[-1] > max(board[:-1])}
    return clip(strength, 0.02, 0.995), min(outs, 15), category, texture


def sample(state, salt):
    """Deterministic number in [0, 1) for mixed plays: the same state gives the same answer."""
    x = (state.hand_number * 2654435761 + state.seat * 40503 + salt * 9973
         + sum(ord(c) for card in state.cards for c in card) * 131) & 0xFFFFFFFF
    x = ((x ^ (x >> 15)) * 2246822519) & 0xFFFFFFFF
    return ((x ^ (x >> 13)) & 0xFFFF) / 65536


def postflop(state, data, hero, opponents, bb, pressure, leader):
    live = [seat for seat in opponents if seat.status == "active"]
    strength, outs, category, texture = read_hand(state, len(opponents) - 1)
    street, pot, cautious = len(state.board), state.pot, pressure >= 0.5
    station = any(is_station(data, seat) for seat in opponents)
    known = [row_of(data, seat) for seat in live if row_of(data, seat)[4] >= N_MIN]
    folds = sum(fit(row[5], row[4], 0.45, 0.15, 0.80) for row in known) / len(known) if known else 0.45
    # Pressure story: points shared by every bluffing spot.
    points = 2 if texture["dry"] else -2 if texture["wet"] else 0
    points += (1 if texture["paired"] else 0) + (1 if texture["scare"] else 0)
    points += 1 if len(opponents) == 1 else -2 * (len(opponents) - 1)
    points += 3 if folds >= 0.60 else 1 if folds >= 0.50 else -3 if folds <= 0.30 else 0
    points += (-5 if station else 0) + (3 if outs >= 8 else 1 if outs >= 4 else 0)
    points += (1 if leader and pressure > 0.2 else 0) - (2 if any(seat.stack <= pot / 2 for seat in live) else 0)

    def pressure_ok(spot, cost, salt):
        if not live or (cautious and outs < 8) or (cost > 0.35 * hero.stack and outs < 8):
            return False  # no fold equity, or strength and story disagree under ICM
        chance = clip(PRIOR[spot] + STEP * points, 0.0, 0.85) * (1 - 0.6 * pressure)
        return sample(state, street * 8 + salt) < chance

    if state.to_call:
        bet = max(seat.bet for seat in opponents)
        before = max(1, pot - state.to_call)
        big = state.to_call >= 0.6 * before
        facing = strength - (0.08 if big else 0.03) - (0.06 if big and street == 5 and category <= 1 else 0)
        all_in = state.to_call >= hero.stack
        draw = outs * 0.021 * ((5 - street) if all_in else min(1, 5 - street))
        if outs >= 8 and hero.stack > 3 * state.to_call and street < 5:
            draw += 0.05  # implied odds
        if strength >= 0.84 and state.can("raise"):
            data["c"] = street
            return raise_to(state, bet + (0.9 if station else 0.7) * (pot + state.to_call))
        if strength < 0.55 and state.can("raise") and state.to_call < 0.4 * before + bb:
            points += 1
        if strength < 0.55 and state.can("raise") and pressure_ok("raise", 2.5 * bet - hero.bet, 1):
            data["c"] = street
            return raise_to(state, 2.5 * bet)
        odds = state.to_call / max(1, pot + state.to_call)
        margin = 0.04 + 0.18 * pressure * min(1.0, state.to_call / max(1, hero.stack))
        return call(state) if max(facing, draw) >= odds + margin else fallback(state)

    if strength >= 0.62 and not (len(opponents) > 1 and strength < 0.70):
        data["c"] = street
        fraction = 0.8 if station else 0.45 if cautious and strength < 0.80 else 0.6
        return raise_to(state, max(bb, round(fraction * pot)))
    if strength >= 0.50:
        if station and len(opponents) == 1:
            data["c"] = street
            return raise_to(state, max(bb, pot // 3))  # thin value from a caller
        return fallback(state)
    last = all((hero.seat - state.button - 1) % 64 > (seat.seat - state.button - 1) % 64 for seat in live)
    points += 1 if last else 0
    if street == 3:
        spot, fraction = ("cbet" if data["r"] else "stab"), 1 / 3
    elif data["c"] == street - 1:
        spot, fraction = f"barrel{street}", (0.5 if street == 4 else 0.6)
    else:
        spot, fraction = "probe", 0.5
    size = max(bb, round(fraction * pot))
    if state.can("raise") and pressure_ok(spot, size, 0):
        data["c"] = street
        return raise_to(state, size)
    return fallback(state)


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        cap = min(MEMORY_CAP, state.config.memory_bytes)
        if state.phase != "betting":
            return variant_phase(state), memory if len(memory) <= cap else b""
        state = view(state)  # variants: a hold'em-shaped hand (section at the end)
        try:
            data = load_memory(memory)
            observe(state, data)
            bb = max(1, state.blinds.big_blind)
            hero = next(seat for seat in state.seats if seat.seat == state.seat)
            opponents = [seat for seat in state.seats
                         if seat.seat != state.seat and seat.status in ("active", "all_in")]
            if not opponents:
                action = fallback(state)
            else:
                pressure, leader = icm_pressure(state, hero, bb)
                play = postflop if state.board else preflop
                action = play(state, data, hero, opponents, bb, pressure, leader)
            encoded = json.dumps(data, separators=(",", ":")).encode()
            return action, encoded if len(encoded) <= cap else b""
        except Exception:  # any surprise: play safe and start the memory again
            return fallback(state), b""


def _own_percentile(a, b):
    """This bot's own preflop percentile of two cards (used by the variants section)."""
    high, low = sorted((RANKS.index(a[0]) + 2, RANKS.index(b[0]) + 2), reverse=True)
    return PCT[high, low, high != low and a[1] == b[1]]


# ============================================================================= variants
# Added 2026-11-11 so this bot plays every ruleset in zoo/variants/. The strategy above is
# unchanged and still reads hold'em-shaped hands; `view` gives it one:
#   preflop   the variant's hand percentile (share of hands better) becomes the hold'em
#             class this bot ranks at the same percentile, dealt as two stand-in cards, so
#             the bot keeps its own opening frequencies in every variant.
#   postflop  the cards that play: omaha's best exactly-two pair, the two kept after
#             discard_reveal's select, all two or three in auction, short deck as dealt.
# On a hold'em table the state passes through untouched. Tables measured by
# tools/gen_variant_tables.py on the mini simulator's rules (copied from tools/core_agent.py).
# Known simplification: short-deck made hands are read with the full-deck evaluator (it
# misses A-6-7-8-9 and scores a full house a little above a flush).
_V_RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}
_V_EQUITY_TABLE = "AA:853 AKs:672 AKo:651 AQs:660 AQo:645 AJs:653 AJo:635 ATs:644 ATo:628 A9s:626 A9o:608 A8s:620 A8o:597 A7s:607 A7o:588 A6s:600 A6o:578 A5s:599 A5o:577 A4s:591 A4o:568 A3s:582 A3o:557 A2s:573 A2o:548 KK:823 KQs:635 KQo:616 KJs:624 KJo:607 KTs:616 KTo:596 K9s:602 K9o:581 K8s:582 K8o:557 K7s:578 K7o:553 K6s:566 K6o:541 K5s:557 K5o:530 K4s:552 K4o:525 K3s:538 K3o:514 K2s:535 K2o:505 QQ:802 QJs:604 QJo:579 QTs:595 QTo:572 Q9s:579 Q9o:553 Q8s:561 Q8o:537 Q7s:542 Q7o:520 Q6s:536 Q6o:508 Q5s:528 Q5o:502 Q4s:520 Q4o:490 Q3s:511 Q3o:482 Q2s:502 Q2o:473 JJ:775 JTs:576 JTo:553 J9s:557 J9o:533 J8s:542 J8o:516 J7s:523 J7o:498 J6s:506 J6o:478 J5s:500 J5o:470 J4s:490 J4o:462 J3s:480 J3o:456 J2s:473 J2o:443 TT:749 T9s:540 T9o:516 T8s:524 T8o:496 T7s:505 T7o:480 T6s:491 T6o:464 T5s:471 T5o:446 T4s:466 T4o:434 T3s:460 T3o:426 T2s:449 T2o:415 99:721 98s:507 98o:480 97s:494 97o:465 96s:476 96o:446 95s:457 95o:429 94s:441 94o:408 93s:434 93o:400 92s:425 92o:392 88:692 87s:479 87o:449 86s:462 86o:430 85s:445 85o:414 84s:428 84o:395 83s:408 83o:375 82s:402 82o:368 77:664 76s:454 76o:424 75s:437 75o:406 74s:418 74o:384 73s:398 73o:367 72s:380 72o:346 66:632 65s:433 65o:400 64s:412 64o:381 63s:397 63o:361 62s:379 62o:342 55:604 54s:415 54o:380 53s:396 53o:361 52s:378 52o:341 44:570 43s:386 43o:349 42s:368 42o:335 33:538 32s:359 32o:322 22:504"
_V_SHORT_TABLE = "AA:728 AKo:595 AKs:618 AQo:588 AQs:600 AJo:584 AJs:596 ATo:564 ATs:580 A9o:546 A9s:562 A8o:532 A8s:544 A7o:501 A7s:531 A6o:481 A6s:503 KK:689 KQo:573 KQs:588 KJo:562 KJs:579 KTo:568 KTs:572 K9o:513 K9s:532 K8o:470 K8s:499 K7o:465 K7s:482 K6o:443 K6s:462 QQ:657 QJo:560 QJs:578 QTo:553 QTs:570 Q9o:511 Q9s:526 Q8o:474 Q8s:498 Q7o:434 Q7s:450 Q6o:420 Q6s:445 JJ:637 JTo:548 JTs:573 J9o:511 J9s:527 J8o:471 J8s:497 J7o:430 J7s:452 J6o:394 J6s:420 TT:610 T9o:513 T9s:523 T8o:475 T8s:494 T7o:436 T7s:463 T6o:399 T6s:418 99:563 98o:475 98s:490 97o:442 97s:461 96o:395 96s:425 88:503 87o:412 87s:439 86o:376 86s:399 77:442 76o:356 76s:385 66:393"
_V_DISCARD_MARKS = (0.853, 0.775, 0.672, 0.651, 0.635, 0.62, 0.607, 0.599, 0.588, 0.578, 0.568, 0.553, 0.54, 0.53, 0.516, 0.5, 0.48, 0.465, 0.445, 0.414, 0.349)
_V_OMAHA_MARKS = (0.823, 0.6067, 0.5822, 0.5658, 0.5523, 0.542, 0.5318, 0.5228, 0.5142, 0.5058, 0.4977, 0.4897, 0.4813, 0.4732, 0.4645, 0.4552, 0.4448, 0.4332, 0.4188, 0.4003, 0.348)


def _v_key(a, b):
    """'AKs', 'T9o', 'QQ': the 169 starting-hand classes."""
    if _V_RANK[a[0]] < _V_RANK[b[0]]:
        a, b = b, a
    if a[0] == b[0]:
        return a[0] + b[0]
    return a[0] + b[0] + ("s" if a[1] == b[1] else "o")


def _v_table(text):
    return {key: int(value) / 1000 for key, value in (item.split(":") for item in text.split())}


def _v_percentiles(table):
    """Share of hands strictly better than each class, weighted by combinations."""
    combos = {key: 6 if len(key) == 2 else 4 if key[2] == "s" else 12 for key in table}
    total, result, better = sum(combos.values()), {}, 0
    for key in sorted(table, key=table.__getitem__, reverse=True):
        result[key] = better / total
        better += combos[key]
    return result


_V_EQUITY = _v_table(_V_EQUITY_TABLE)
_V_SHORT = _v_table(_V_SHORT_TABLE)
_V_SHORT_PCT = _v_percentiles(_V_SHORT)


def _v_pct_of(score, marks):
    """Share of hands scoring higher; `marks` is the score at each equal step, best first."""
    if score >= marks[0]:
        return 0.0
    steps = len(marks) - 1
    for index in range(1, len(marks)):
        if score >= marks[index]:
            span = marks[index - 1] - marks[index]
            return (index - ((score - marks[index]) / span if span > 0 else 0.0)) / steps
    return 1.0


def _v_pairs(cards):
    return [(a, b) for i, a in enumerate(cards) for b in cards[i + 1:]]


def discard_reveal_pct(cards):
    if len(cards) != 3:
        return None
    return _v_pct_of(max(_V_EQUITY[_v_key(a, b)] for a, b in _v_pairs(cards)), _V_DISCARD_MARKS)


def omaha_pct(cards):
    if len(cards) != 4:
        return None
    return _v_pct_of(sum(_V_EQUITY[_v_key(a, b)] for a, b in _v_pairs(cards)) / 6, _V_OMAHA_MARKS)


def short_deck_pct(cards):
    key = _v_key(*cards) if len(cards) == 2 else None
    return _V_SHORT_PCT.get(key)


def _v_five(cards):
    """Exactly five cards as a tuple that compares correctly (bigger wins). Full deck."""
    ranks = sorted((_V_RANK[card[0]] for card in cards), reverse=True)
    flush = len({card[1] for card in cards}) == 1
    if len(set(ranks)) == 5:
        high = ranks[0] if ranks[0] - ranks[4] == 4 else 5 if ranks[:2] == [14, 5] else 0
        if high:
            return (8 if flush else 4, high)
        return (5 if flush else 0, *ranks)
    counts = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1
    groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    top = groups[0][1]
    category = 7 if top == 4 else (6 if len(groups) == 2 else 3) if top == 3 else 2 if len(groups) == 3 else 1
    return (category, *[rank for rank, _ in groups])


def _v_best(hole, board, exact=False):
    """Best five-card hand: any five of all cards, or exactly two private and three board."""
    if exact:
        return max(_v_five(pair + three) for pair in combinations(hole, 2) for three in combinations(board, 3))
    cards = tuple(hole) + tuple(board)
    if len(cards) < 5:
        return (-1,)
    return max(_v_five(five) for five in combinations(cards, 5))


def _v_best_two(cards, board, exact=False):
    """The two private cards that make the best hand with the board (preflop table on ties)."""
    return max(((a, b) for a, b in _v_pairs(tuple(cards))),
               key=lambda pair: (_v_best(pair, board, exact) if board else (), _V_EQUITY[_v_key(*pair)]))


def omaha_hole(state):
    if len(state.cards) != 4 or not 3 <= len(state.board) <= 5:
        return None
    return _v_best_two(state.cards, tuple(state.board), exact=True)


def discard_reveal_hole(state):
    """After the select phase we hold two; if the kit bets the flop first, the best two."""
    if len(state.cards) != 3:
        return None
    return _v_best_two(state.cards, tuple(state.board))


def _v_automatic(state):
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def discard_reveal_select(state):
    """Keep the two cards that play best with the board, show the lower of them."""
    cards = tuple(state.cards)
    if len(cards) != 3 or not state.can("select"):
        return _v_automatic(state)
    keep = _v_best_two(cards, tuple(state.board))
    indices = [cards.index(keep[0]), cards.index(keep[1])]
    discard = next(index for index in range(3) if index not in indices)
    reveal = min(indices, key=lambda index: _V_RANK[cards[index][0]])
    return Action("select", cards=(discard, reveal))


def auction_bid(state):
    """Second-price bid for an extra card: a share of the pot by what the card adds (most
    to a draw, least to a made hand), at most a tenth of the stack, nothing when short."""
    allowed = state.can("bid")
    if allowed is None or len(state.cards) < 2 or len(state.board) < 3:
        return _v_automatic(state)
    stack = next((seat.stack for seat in state.seats if seat.seat == state.seat), 0)
    if stack <= 10 * max(1, state.blinds.big_blind):
        return Action("bid", allowed.min_amount)
    cards = tuple(state.cards) + tuple(state.board)
    suits = [card[1] for card in cards]
    flush_draw = any(suits.count(card[1]) == 4 for card in state.cards)
    row = {_V_RANK[card[0]] for card in cards} | ({1} if any(card[0] == "A" for card in cards) else set())
    open_end = any(all(r + i in row for i in range(4)) for r in range(1, 12))
    made = _v_best(state.cards, state.board)[0] >= 2
    gain = 0.10 if (flush_draw or open_end) and not made else 0.03 if made else 0.06
    bid = min(int(gain * state.pot), stack // 10)
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, bid)))


VARIANTS = {
    "discard_reveal": {"detect": lambda state: state.phase == "select" or len(state.cards) == 3,
                       "phases": {"select": discard_reveal_select},
                       "preflop": discard_reveal_pct, "hole": discard_reveal_hole},
    "omaha": {"detect": lambda state: len(state.cards) == 4,
              "phases": {}, "preflop": omaha_pct, "hole": omaha_hole},
    "auction": {"detect": lambda state: state.phase == "bid",  # all two or three cards play
                "phases": {"bid": auction_bid}, "preflop": None, "hole": None},
    "short_deck": {"detect": lambda state: False,  # recognised by state.config.variant only
                   "phases": {}, "preflop": short_deck_pct, "hole": None},
    "holdem": {"detect": lambda state: True,  # keep last: the fallback
               "phases": {}, "preflop": None, "hole": None},
}


def variant_of(state):
    """The kit's variant name if we know it (and it has this phase), else by its signs."""
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS and (state.phase == "betting" or state.phase in VARIANTS[name]["phases"]):
        return name
    return next(key for key, variant in VARIANTS.items() if variant["detect"](state))


def _v_standins():
    """Every hold'em class as two stand-in cards, sorted by this bot's own percentile."""
    result = []
    for key in _V_EQUITY:
        first = key[0] + "h"
        second = key[1] + ("h" if key[2:] == "s" else "d")
        result.append((_own_percentile(first, second), (first, second)))
    return sorted(result)


_V_STANDINS = _v_standins()
_V_STANDIN_PCT = [pct for pct, _ in _V_STANDINS]


def view(state):
    """The state the hold'em strategy should see on this table (see the section comment)."""
    try:
        variant = VARIANTS[variant_of(state)]
        if not state.board:
            pct = variant["preflop"](tuple(state.cards)) if variant["preflop"] else None
            if pct is None:
                return state
            at = min(bisect_left(_V_STANDIN_PCT, pct), len(_V_STANDINS) - 1)
            cards = _V_STANDINS[at][1]
        else:
            cards = variant["hole"](state) if variant["hole"] else None
            if cards is None:
                return state
        return dataclasses.replace(state, cards=tuple(cards))
    except Exception:
        return state


def variant_phase(state):
    """A decision phase a variant adds: its handler, else the automatic choice."""
    try:
        handler = VARIANTS[variant_of(state)]["phases"].get(state.phase)
        return handler(state) if handler else _v_automatic(state)
    except Exception:
        return _v_automatic(state)
