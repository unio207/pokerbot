"""Vedaant Seceret Strategies HeHeHe: RubricPressure ICM zoo opponent (strategy F).

Source:  Claude (Fable 5.2), implementing Vedaant's design in zoo/VEDAANT_SECERET_STRATEGIES.md
Profile: Strong zoo opponent. Scheduled steals plus postflop pressure, tempered by ICM.
Notes:   Rubric decisions (fixed prior + bounded points, clipped); per-seat fold counters
         used only after 10 samples; small c-bets, probes and semibluff raises; value and
         pressure lines combined cautiously near the bubble. Shove/fold under 13 BB.

All numbers are hand-set estimates, not solver output. Standard hold'em only: any other
decision phase takes the first legal action. No rollouts, no state outside `memory`.
"""

import json

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
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory if len(memory) <= cap else b""
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
