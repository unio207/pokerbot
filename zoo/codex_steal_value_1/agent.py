"""Small-bet steal and value zoo opponent (strategy C).

Source:   Codex, independently delegated implementation in the same session.
Profile:  C. Exploit overfolders cheaply; value bet calling stations.
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    2-BB positional opens, bounded opponent memory, selective dry-board c-bets.

Ranges and hand-equity proxies are estimates, not Nash/solver outputs. No runtime
rollouts. Opponent response counts are observations, not certainty about code.
Variants added 2026-11-11 (Claude Code): the section at the end hands this unchanged
hold'em strategy a hold'em-shaped hand; unknown phases still take the first legal choice.
"""

import json
from collections import Counter
import dataclasses
from bisect import bisect_left
from itertools import combinations

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
            kept = memory if len(memory) <= min(4096, state.config.memory_bytes) else b""
            return variant_phase(state), kept
        state = view(state)  # variants: a hold'em-shaped hand (section at the end)
        data = load_memory(state, memory)
        observe(state, data)
        action = decide(state, data)
        encoded = json.dumps(data, separators=(",", ":")).encode()
        if len(encoded) > min(4096, state.config.memory_bytes):
            encoded = b""
        return action, encoded


def _own_percentile(a, b):
    """This bot's own preflop percentile of two cards (used by the variants section)."""
    high, low = sorted(ranks((a, b)), reverse=True)
    return OPEN_PERCENTILE[high, low, high != low and a[1] == b[1]]


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
