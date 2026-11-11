"""Small-bet steal and value zoo opponent (strategy C).

Source: Codex, independently delegated implementation in the same session.
Profile: Exploit overfolders cheaply; value bet calling stations.
Notes: 2-BB positional opens, bounded opponent memory, selective dry-board c-bets.
Ranges and hand-equity proxies are estimates, not Nash/solver outputs. Standard
hold'em only; other decision phases use their first legal action. No runtime
rollouts. Opponent response counts are observations, not certainty about code.
"""

import json
from collections import Counter

import poker_agent_sdk
from poker_agent_sdk import Action, GameState


def hand_score(high, low, suited):
    """Heuristic ranking for opening masks; not an equity calculation."""
    if high == low:
        return 35 + high * 4
    return (high * 2.2 + low * 1.1 + (4 if suited else 0)
            + max(0, 4 - (high - low)) * 1.5 + (3 if high == 14 else 0))


def opening_table():
    hands = []
    for high in range(2, 15):
        for low in range(2, high + 1):
            for suited in ((False,) if high == low else (False, True)):
                hands.append((hand_score(high, low, suited), high, low, suited,
                              6 if high == low else 4 if suited else 12))
    result = {}
    cumulative = 0
    for _, high, low, suited, combos in sorted(hands, reverse=True):
        result[high, low, suited] = (cumulative + combos / 2) / 1326
        cumulative += combos
    return result


# Initialized once, read-only during decisions. No table-specific global state.
OPEN_PERCENTILE = opening_table()


def fallback(state):
    if state.can("check"):
        return Action.check()
    if state.can("fold"):
        return Action.fold()
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def raise_to(state, amount):
    legal = state.can("raise")
    if legal:
        return Action.raise_to(max(legal.min_amount, min(legal.max_amount, int(amount))))
    if state.can("call"):
        return Action.call()
    return fallback(state)


def ranks(cards):
    return ["23456789TJQKA".index(card[0]) + 2 for card in cards]


def straight_high(values):
    values = set(values)
    if 14 in values:
        values.add(1)
    for high in range(14, 4, -1):
        if all(value in values for value in range(high - 4, high + 1)):
            return high
    return 0


def evaluate(cards):
    """Exact best-five tuple for ordinary hold'em, using rank/suit counts."""
    values = ranks(cards)
    counts = Counter(values)
    suits = {}
    for card, value in zip(cards, values):
        suits.setdefault(card[1], []).append(value)
    flush = next((sorted(v, reverse=True) for v in suits.values() if len(v) >= 5), None)
    if flush:
        high = straight_high(flush)
        if high:
            return 8, high
    quads = sorted((v for v, count in counts.items() if count == 4), reverse=True)
    if quads:
        return 7, quads[0], max(v for v in values if v != quads[0])
    trips = sorted((v for v, count in counts.items() if count >= 3), reverse=True)
    pairs = sorted((v for v, count in counts.items() if count >= 2), reverse=True)
    if trips:
        other_pairs = [v for v in pairs if v != trips[0]]
        if other_pairs:
            return 6, trips[0], other_pairs[0]
    if flush:
        return (5, *flush[:5])
    high = straight_high(values)
    if high:
        return 4, high
    if trips:
        return (3, trips[0], *sorted((v for v in values if v != trips[0]), reverse=True)[:2])
    if len(pairs) >= 2:
        return 2, pairs[0], pairs[1], max(v for v in values if v not in pairs[:2])
    if pairs:
        return (1, pairs[0], *sorted((v for v in values if v != pairs[0]), reverse=True)[:3])
    return (0, *sorted(values, reverse=True)[:5])


def load_memory(state, memory):
    try:
        data = json.loads(memory) if len(memory) < 4096 else {}
        if not isinstance(data, dict) or not isinstance(data.get("s"), dict):
            raise ValueError
        for row in data["s"].values():
            if len(row) != 4 or any(type(n) is not int or n < 0 for n in row):
                raise ValueError
        if len(data["s"]) > 16:
            raise ValueError
    except (ValueError, TypeError, UnicodeDecodeError, KeyError):
        data = {"s": {}, "p": True, "r": False, "h": -1}
    return data


def observe(state, data):
    # Events are incremental since our previous act. A bounded tail deliberately
    # loses some evidence on overflow; it never turns missing events into folds.
    events = state.events
    if len(events) > 64:
        data["p"] = not bool(state.board)
        events = events[-64:]
    for event in events:
        if event.kind == "hand":
            data["p"], data["r"], data["h"] = True, False, event.amount
        elif event.kind == "board":
            data["p"] = False
        elif data.get("p", True) and event.seat is not None and event.seat != state.seat:
            # Relevant preflop responses to an outstanding bet; checks are not
            # counted as evidence of folding or calling against a raise.
            if event.kind in ("fold", "call", "raise"):
                key = str(event.seat)
                if key not in data["s"] and len(data["s"]) >= 16:
                    continue
                row = data["s"].setdefault(key, [0, 0, 0, 0])
                if row[0] >= 200:
                    row[:] = [n // 2 for n in row]
                row[0] += 1
                row[{"fold": 1, "call": 2, "raise": 3}[event.kind]] += 1
    if data.get("h") != state.hand_number:
        data["h"], data["r"] = state.hand_number, False
    data["p"] = not bool(state.board)


def fold_rate(data, seat):
    row = data["s"].get(str(seat), [0, 0, 0, 0])
    if row[0] < 6:
        return 0.45
    return (row[1] + 1) / (row[0] + 2)


def station(data, seat):
    n, folds, calls, raises = data["s"].get(str(seat), [0, 0, 0, 0])
    return n >= 10 and calls / n >= 0.8 and raises / n <= 0.1


def eligible_after_call(state, me):
    """Contestable pot INCLUDING our call; cap all contributions at our exposure.

    Full short-call accounting when the bounded public history balances with the
    pot; otherwise remove uncallable current-street excess conservatively.
    """
    cost = min(state.to_call, me.stack)
    if len(state.history) <= 128:
        contributions = {s.seat: 0 for s in state.seats}
        street = contributions.copy()
        valid = True
        for event in state.history:
            if event.kind == "board":
                ordered = sorted(street.values(), reverse=True)
                if len(ordered) > 1 and ordered[0] > ordered[1]:
                    highest = max(street, key=street.get)
                    contributions[highest] -= ordered[0] - ordered[1]
                street = dict.fromkeys(street, 0)
            elif event.kind in ("blind", "call", "raise") and event.seat in contributions:
                amount = event.amount - street[event.seat] if event.kind == "raise" else event.amount
                if amount < 0:
                    valid = False
                    break
                contributions[event.seat] += amount
                street[event.seat] += amount
        if valid and sum(contributions.values()) == state.pot:
            contributions[me.seat] += cost
            return sum(min(amount, contributions[me.seat]) for amount in contributions.values())
    excess = sum(max(0, seat.bet - me.bet - cost) for seat in state.seats if seat.seat != me.seat)
    return max(cost, state.pot + cost - excess)


def decide(state, data):
    bb = max(1, state.blinds.big_blind)
    hero = next(seat for seat in state.seats if seat.seat == state.seat)
    opponents = [seat for seat in state.seats
                 if seat.seat != state.seat and seat.status in ("active", "all_in")]
    active = [seat.seat for seat in state.seats if seat.status != "busted"]
    # Sort physical seats clockwise, with the button last. Heads-up has the
    # button/SB first preflop; other tables have SB, BB, then early positions.
    ordered = sorted(active)
    button_index = ordered.index(state.button) if state.button in ordered else len(ordered) - 1
    clockwise = ordered[button_index + 1:] + ordered[:button_index + 1]
    order = list(reversed(clockwise)) if len(active) == 2 else clockwise[2:] + clockwise[:2]
    hero_index = order.index(state.seat)
    behind = [s for s in opponents if s.seat in order[hero_index + 1:] and s.status == "active"]
    bb_depth = (hero.stack + hero.bet) / bb
    odds = state.to_call / max(1, eligible_after_call(state, hero))
    paid = sum(p > 0 for p in state.config.payouts)
    # C is primarily a chip-accumulation bot. A modest payout-dependent premium
    # prevents its weakest all-in calls while preserving its distinct profile.
    premium = 0.0
    if state.players_remaining > 2 and state.to_call >= hero.stack * 0.6:
        premium = 0.12 if state.players_remaining == paid + 1 else 0.05

    if not state.board:
        card_ranks = sorted(ranks(state.cards), reverse=True)
        if len(card_ranks) != 2:
            return fallback(state)
        high, low = card_ranks
        suited = high != low and state.cards[0][1] == state.cards[1][1]
        percentile = OPEN_PERCENTILE[high, low, suited]
        # Only this hand's bounded preflop history, not table-wide rescanning.
        raises = [e for e in state.history[-64:] if e.kind == "raise"]
        unopened = not raises
        sb = clockwise[0]
        button = state.button
        if len(active) == 2:
            fraction = 0.80
        elif state.seat == button:
            fraction = 0.50
        elif state.seat == sb:
            fraction = 0.55
        elif len(behind) <= 3:
            fraction = 0.30
        else:
            fraction = 0.15
        probability = 1.0
        for seat in behind:
            probability *= fold_rate(data, seat.seat)
        if unopened and behind and probability > 0.65 and len(behind) <= 3:
            fraction = 1.0 if probability > 0.82 else 0.85
        if any(station(data, seat.seat) for seat in opponents):
            fraction *= 0.8
        # Equity-vs-random proxy, deliberately conservative versus observed
        # raises. It is not a replacement for range-conditioned equity tables.
        equity = max(0.18, min(0.85, 0.66 - 0.39 * percentile))
        if high == low:
            equity = 0.48 + high * 0.027
        if raises:
            equity -= 0.14
            if state.to_call >= max(bb * 5, hero.stack * 0.6):
                equity -= 0.08
            if percentile <= 0.035 and state.can("raise") and bb_depth <= 20:
                return raise_to(state, hero.bet + hero.stack)
            if equity >= odds + premium + 0.08 and percentile <= 0.17:
                return Action.call() if state.can("call") else fallback(state)
            return fallback(state)
        if percentile < fraction:
            if bb_depth <= 8:
                short_fraction = min(fraction, 0.18 + 0.06 * max(0, 5 - len(behind)))
                if percentile > short_fraction:
                    return fallback(state)
                return raise_to(state, hero.bet + hero.stack)
            size = 3.5 if any(station(data, seat.seat) for seat in opponents) else 2
            action = raise_to(state, round(size * bb))
            if action.kind == "raise":
                data["r"] = True
            return action
        return fallback(state)

    cards = tuple(state.cards) + tuple(state.board)
    rank = evaluate(cards)
    board_rank = evaluate(state.board) if len(state.board) == 5 else None
    plays_board = board_rank == rank
    values = ranks(state.board)
    suit_counts = Counter(card[1] for card in state.board)
    four_flush = max(suit_counts.values()) >= 4
    connected = max((sum(v in set(values) for v in range(lo, lo + 5))
                     for lo in range(1, 11)), default=0) >= 4
    danger = four_flush or connected
    texture = max(suit_counts.values()) <= 2 and not connected
    category = rank[0]
    hole = ranks(state.cards)
    top_pair = category == 1 and rank[1] == max(values) and rank[1] in hole
    overpair = category == 1 and hole[0] == hole[1] and hole[0] > max(values)
    equity = (0.12, 0.40, 0.77, 0.87, 0.90, 0.92, 0.96, 0.99, 0.995)[category]
    if top_pair:
        equity = 0.64 if max(hole) >= 12 else 0.56
    if overpair:
        equity = 0.70
    if plays_board:
        equity = 0.15 if state.to_call else 0.5
    if danger and category < 6:
        equity -= 0.17
    multiway = len(opponents) > 1
    if multiway:
        equity -= 0.13
    # One-card draw pricing unless this call buys all remaining cards.
    combined_suits = Counter(card[1] for card in cards)
    flush_draw = max(combined_suits.values()) == 4 and len(state.board) < 5
    if flush_draw and category < 4:
        unseen = 52 - len(cards)
        draw = 9 / max(1, unseen)
        if state.to_call >= hero.stack and len(state.board) == 3:
            draw = 1 - (unseen - 9) * (unseen - 10) / (unseen * (unseen - 1))
        equity = max(equity, draw * 0.85)
    has_station = any(station(data, seat.seat) for seat in opponents)
    if state.to_call:
        # A large raise from a quiet opponent is respected by this simple bot.
        if state.to_call > 0.6 * max(1, state.pot - state.to_call) and category == 1:
            equity -= 0.08
        margin = 0.10 if multiway else 0.06
        return Action.call() if state.can("call") and equity >= odds + premium + margin else fallback(state)
    strong = category >= 2 and not plays_board and (not danger or category >= 6)
    strong_pair = (top_pair or overpair) and not danger and not multiway
    if strong or (strong_pair and has_station):
        return raise_to(state, hero.bet + max(bb, round(state.pot * (0.75 if has_station else 2 / 3))))
    dry_cbet = len(state.board) == 3 and texture and (max(values) >= 13 or len(set(values)) < 3)
    sample = (state.hand_number * 17 + state.seat * 7 + sum(hole)) % 2
    if data.get("r") and dry_cbet and not multiway and not has_station:
        if category >= 1 or flush_draw or sample == 0:
            return raise_to(state, hero.bet + max(bb, round(state.pot / 3)))
    return fallback(state)


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            first = state.legal_actions[0]
            kept = memory if len(memory) <= min(4096, state.config.memory_bytes) else b""
            return Action(first.kind, first.min_amount), kept
        data = load_memory(state, memory)
        observe(state, data)
        action = decide(state, data)
        encoded = json.dumps(data, separators=(",", ":")).encode()
        if len(encoded) > min(4096, state.config.memory_bytes):
            encoded = b""
        return action, encoded
