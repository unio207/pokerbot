"""Zoo bot: seat-by-seat exploiter.

Source:   claude (Claude Code), written without reading any other zoo bot
Profile:  You want to exploit weak bots: track opponents in memory and adapt.
Variants: all (2026-11-11): holdem, discard_reveal, short_deck, omaha, auction; irish as a fail-safe
Notes:    Tags every seat in memory (loose/tight, sticky/folding, dead), opens and shoves by
          expected value against those tags, value-bets callers, calls wide shovers lighter,
          and plays for first once in the money. All five variants ran in the mini simulator.

How this file is organised (see zoo/_template/README.md):
  1. act()      crash-proof wrapper.
  2. tables     preflop equity tables built at import.
  3. scoring    hand strength after the flop, for any number of private cards.
  4. VARIANTS   one entry per ruleset: detect, phases, strength, spread, tight.
  5. memory     per-seat counters kept in the memory bytes.
  6. decide()   the betting strategy; it reads only the strength score and the counters.
  7. helpers    legal actions and clamped raises.
"""

import struct
from bisect import bisect_right

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}

# The settings fitted to a field. tools/field_fit.py measures a field from its hand
# histories and tries other values for these; keep one "name": value pair per line.
SETTINGS = {
    "open_width": 1.3,  # how wide to open before the flop; higher opens more hands
    "shove_depth": 12,  # at or under this many big blinds, shove or fold
    "bet_credit": 0.18,  # strength taken off our hand when an opponent bets
    "call_margin": 0.13,  # extra win chance wanted before calling a bet after the flop
    "cbet": 0.9,  # how often to bet the flop with nothing after raising before it
    "value_bet": 0.62,  # strength needed to bet for value
}
SUIT = {"c": 0, "d": 1, "h": 2, "s": 3}


# ----------------------------------------------------------------------------- 1. wrapper
class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        try:
            counters = load(memory, state)
            try:
                observe(counters, state)
                memory = struct.pack(FORMAT, *counters)
            except Exception:
                counters = fresh(state)
            variant = VARIANTS[variant_of(state)]
            if state.phase == "betting":
                action = decide(state, variant, counters)
            else:
                handler = variant["phases"].get(state.phase)
                action = handler(state) if handler else automatic(state)
            return legal(action, state), memory
        except Exception:
            try:
                return passive(state), memory
            except Exception:
                return Action.fold(), memory


# ----------------------------------------------------------------------------- 2. tables
# Chance (in thousandths) that a two-card hand beats one random hand, from our own
# simulation. Row and column are ranks, lowest first; row above column is suited, below is
# offsuit, the diagonal is pairs.
HOLD_Q = (501, 318, 335, 346, 334, 343, 357, 400, 416, 442, 466, 504, 552, 368, 536, 350, 365, 356, 368, 372, 392, 424, 465, 480, 513, 564, 376, 404, 569, 397, 374, 379, 402, 403, 438, 463, 492, 517, 576, 389, 386, 417, 591, 397, 398, 412, 429, 442, 474, 500, 530, 581, 374, 397, 418, 423, 633, 441, 438, 455, 454, 469, 505, 545, 567, 380, 408, 414, 438, 472, 656, 437, 454, 468, 502, 519, 553, 593, 397, 413, 428, 448, 464, 486, 687, 482, 499, 510, 535, 556, 606, 409, 427, 427, 463, 473, 481, 517, 716, 513, 534, 550, 576, 608, 455, 462, 471, 479, 488, 506, 533, 539, 755, 538, 572, 597, 626, 476, 481, 490, 496, 507, 535, 552, 547, 582, 775, 575, 614, 630, 498, 507, 518, 530, 531, 553, 559, 580, 575, 601, 792, 617, 646, 538, 545, 550, 554, 564, 577, 578, 602, 601, 626, 639, 823, 663, 578, 582, 589, 612, 596, 614, 612, 609, 645, 652, 664, 674, 864)
SHORT_Q = (403, 350, 381, 402, 394, 396, 432, 439, 472, 382, 437, 411, 443, 437, 436, 445, 461, 501, 404, 440, 514, 467, 472, 476, 471, 470, 526, 426, 456, 495, 563, 512, 503, 500, 515, 543, 426, 463, 485, 532, 608, 553, 554, 557, 558, 423, 445, 495, 528, 577, 643, 559, 564, 574, 450, 453, 496, 522, 568, 578, 669, 572, 578, 470, 476, 503, 529, 575, 582, 581, 690, 609, 497, 523, 554, 561, 584, 585, 600, 614, 729)
THREE_QUANT = (350, 397, 412, 429, 441, 454, 463, 472, 481, 492, 501, 505, 513, 518, 533, 535, 538, 545, 550, 556, 569, 572, 575, 577, 582, 593, 597, 606, 609, 614, 617, 626, 633, 645, 652, 663, 664, 716, 775, 823, 864)
OMAHA_QUANT = (364, 426, 446, 463, 474, 484, 493, 501, 507, 514, 521, 528, 534, 539, 544, 550, 555, 560, 565, 571, 576, 580, 585, 590, 594, 598, 602, 607, 611, 615, 619, 624, 629, 634, 642, 651, 664, 687, 711, 737, 864)


def _build_tables():
    """Percentile tables for hold'em hands, weighted by how many card combinations each has."""
    classes = []
    for a in range(13):
        for b in range(13):
            weight = 6 if a == b else 4 if a > b else 12
            classes.append((HOLD_Q[a * 13 + b] / 1000.0, weight))
    classes.sort()
    total = float(sum(weight for _, weight in classes))
    values, below, running = [], [], 0.0
    for q, weight in classes:
        values.append(q)
        running += weight
        below.append(running / total)
    q_at = []  # q of the hand at each whole percentile
    for percent in range(101):
        at = min(len(values) - 1, bisect_right(below, percent / 100.0 - 1e-9))
        q_at.append(values[at])
    mean_top = [values[-1]]  # mean q of the best r% of hands
    for percent in range(1, 101):
        need, got, acc = percent / 100.0 * total, 0.0, 0.0
        for q, weight in reversed(classes):
            take = min(weight, need - got)
            if take <= 0:
                break
            acc += q * take
            got += take
        mean_top.append(acc / got)
    return values, below, q_at, mean_top


Q_SORTED, Q_BELOW, Q_AT, Q_MEAN_TOP = _build_tables()
SHORT_SORTED = sorted(SHORT_Q)


def _build_straights(low):
    """For every set of ranks (bit 0 = deuce): the top card of its best straight, the most
    ranks it has inside any five-rank run, and how many missing ranks would make a straight."""
    runs = [(high, sum(1 << (r - 2) for r in range(high - 4, high + 1))) for high in range(14, low, -1)]
    runs.append((low, (1 << 12) | sum(1 << (r - 2) for r in range(low - 3, low + 1)) if low > 5
                 else (1 << 12) | 0b1111))  # the ace-low straight
    best, inside = [0] * 8192, [0] * 8192
    for mask in range(8192):
        for high, run in runs:
            have = bin(mask & run).count("1")
            if have == 5 and not best[mask]:
                best[mask] = high
            if have > inside[mask]:
                inside[mask] = have
    return best, inside


STRAIGHT, INSIDE = {}, {}
STRAIGHT[False], INSIDE[False] = _build_straights(5)
STRAIGHT[True], INSIDE[True] = _build_straights(9)  # short deck: lowest straight is A-6-7-8-9


def percentile(q: float) -> float:
    """Share of hold'em hands that are no better than a hand with this score."""
    at = bisect_right(Q_SORTED, q + 1e-9)
    return Q_BELOW[at - 1] if at else 0.0


def equity(q: float, share: float, spread: float) -> float:
    """Rough chance of beating a hand drawn from the best `share` of hands."""
    share = 0.01 if share < 0.01 else 1.0 if share > 1.0 else share
    value = 0.5 + spread * (0.8 + 0.2 * share) * (q - Q_MEAN_TOP[int(share * 100)])
    return 0.06 if value < 0.06 else 0.94 if value > 0.94 else value


# ----------------------------------------------------------------------------- 3. scoring
def parse(cards):
    return [(RANK[card[0]], SUIT[card[1]]) for card in cards]


def two_card_q(first, second) -> float:
    a, b = first[0] - 2, second[0] - 2
    if a == b:
        return HOLD_Q[a * 14] / 1000.0
    high, low = (a, b) if a > b else (b, a)
    if first[1] == second[1]:
        return HOLD_Q[high * 13 + low] / 1000.0
    return HOLD_Q[low * 13 + high] / 1000.0


def from_quantiles(value: float, quantiles) -> float:
    """Turn a raw score into the hold'em score of the hand at the same percentile."""
    at = bisect_right(quantiles, int(value * 1000))
    return Q_AT[min(100, at * 100 // len(quantiles))]


def preflop_q(hole, short=False) -> float:
    """Hold'em-equivalent score of our private cards before the flop."""
    count = len(hole)
    if count == 2:
        if short:
            a, b = hole[0][0] - 6, hole[1][0] - 6
            if a < 0 or b < 0:
                return two_card_q(hole[0], hole[1])
            high, low = (a, b) if a > b else (b, a)
            raw = SHORT_Q[high * 9 + low] if hole[0][1] == hole[1][1] or a == b else SHORT_Q[low * 9 + high]
            return Q_AT[min(100, bisect_right(SHORT_SORTED, raw) * 100 // 81)]
        return two_card_q(hole[0], hole[1])
    if count == 3:
        best = max(two_card_q(hole[0], hole[1]), two_card_q(hole[0], hole[2]), two_card_q(hole[1], hole[2]))
        return from_quantiles(best, THREE_QUANT)
    if count == 4:
        pairs = sorted((two_card_q(hole[i], hole[j]) for i in range(4) for j in range(i + 1, 4)), reverse=True)
        return from_quantiles(0.5 * pairs[0] + 0.3 * pairs[1] + 0.2 * pairs[2], OMAHA_QUANT)
    if count == 1:
        return 0.3 + 0.02 * hole[0][0]
    return 0.4


def made_strength(hole, board, short=False) -> float:
    """0..1 value of our hand after the flop when all private cards may play (hold'em rules).
    About the chance of beating one opponent who stayed in, with draws counted in."""
    cards_out = len(board)
    count, board_count = [0] * 15, [0] * 15
    suits, board_suits = [0, 0, 0, 0], [0, 0, 0, 0]
    board_mask = 0
    board_top = 0
    for rank, suit in board:
        count[rank] += 1
        board_count[rank] += 1
        suits[suit] += 1
        board_suits[suit] += 1
        board_mask |= 1 << (rank - 2)
        if rank > board_top:
            board_top = rank
    mask = board_mask
    hole_top = 0
    for rank, suit in hole:
        count[rank] += 1
        suits[suit] += 1
        mask |= 1 << (rank - 2)
        if rank > hole_top:
            hole_top = rank
    straight = STRAIGHT[short]
    board_flush = max(board_suits)
    quads = trips = 0
    pairs = []
    board_paired = False
    for rank in range(14, 1, -1):
        have = count[rank]
        if board_count[rank] >= 2:
            board_paired = True
        if have == 4:
            quads = quads or rank
        elif have == 3:
            if trips:
                pairs.append(rank)
            else:
                trips = rank
        elif have == 2:
            pairs.append(rank)

    value = -1.0
    flush_suit = -1
    for suit in range(4):
        if suits[suit] >= 5:
            flush_suit = suit
    if flush_suit >= 0:
        board_flush_mask, mine = 0, 0
        for rank, suit in board:
            if suit == flush_suit:
                board_flush_mask |= 1 << (rank - 2)
        flush_mask = board_flush_mask
        for rank, suit in hole:
            if suit == flush_suit:
                flush_mask |= 1 << (rank - 2)
                if rank > mine:
                    mine = rank
        if straight[flush_mask] and straight[flush_mask] != straight[board_flush_mask]:
            return 0.99
        if mine == 0:
            value = 0.45
        else:
            higher = 0
            for rank in range(mine + 1, 15):
                if not board_flush_mask >> (rank - 2) & 1:
                    higher += 1
            if board_suits[flush_suit] >= 4:
                value = max(0.5, 0.93 - 0.08 * higher)
            else:
                value = max(0.8, 0.96 - 0.035 * higher)
            if board_paired and not short:
                value *= 0.94
    if quads:
        if board_count[quads] == 4:
            return min(0.95, 0.4 + 0.04 * (hole_top - 2))
        return 0.99
    if trips and pairs:
        if board_count[trips] == 3:
            full = 0.5 if board_count[pairs[0]] >= 2 else 0.78 + 0.012 * (pairs[0] - 2)
        else:
            full = 0.96
        if short and board_flush >= 3:
            full *= 0.9
        return full if full > value else value
    if value >= 0:
        return value

    def texture(v):
        if board_flush == 3:
            v *= 0.93 if short else 0.9
        elif board_flush >= 4:
            v *= 0.65
        if INSIDE[short][board_mask] >= 4:
            v *= 0.82
        return v

    top_straight = straight[mask]
    if top_straight:
        if straight[board_mask] == top_straight:
            value = 0.45
        else:
            value = 0.9
            for rank, _ in hole:
                if straight[board_mask | 1 << (rank - 2)] == top_straight:
                    value = 0.8
            if board_flush == 3:
                value *= 0.93 if short else 0.87
            elif board_flush >= 4:
                value *= 0.55
            if board_paired:
                value *= 0.93
        return value

    def pair_value(pair):
        above = 0
        for rank in range(pair + 1, 15):
            if board_count[rank]:
                above += 1
        if board_count[pair] == 0:  # a pair in our hand
            if above == 0:
                v = 0.76 + 0.012 * (pair - 8)
                return 0.70 if v < 0.70 else 0.84 if v > 0.84 else v
            return 0.57 if above == 1 else 0.47 if above == 2 else 0.40
        kicker = max((rank for rank, _ in hole if rank != pair), default=2)
        if above == 0:
            v = 0.66 + 0.012 * (kicker - 9)
            return 0.60 if v < 0.60 else 0.73 if v > 0.73 else v
        return 0.53 if above == 1 else 0.44

    high_card = 0.16 + (0.08 if hole_top == 14 else 0.05 if hole_top == 13 else 0.0)
    for rank, _ in hole:
        if rank > board_top:
            high_card += 0.03
    soft = 0.92 if short else 1.0  # one and two pair are worth less in a short deck
    if trips:
        if board_count[trips] == 3:
            value = 0.3 + 0.025 * (hole_top - 2)
        elif board_count[trips] == 1:
            value = texture(0.93)
        else:
            kicker = max((rank for rank, _ in hole if rank != trips), default=2)
            value = texture(0.84 + 0.006 * (kicker - 2))
    elif len(pairs) >= 2:
        ours = [pair for pair in pairs[:2] if board_count[pair] < 2]
        if not ours:
            value = high_card + 0.08
        elif len(ours) == 2:
            value = texture(0.89 if pairs[0] >= board_top else 0.85) * soft
        else:
            value = texture(pair_value(ours[0]) * 0.95) * soft
    elif pairs:
        if board_count[pairs[0]] == 2:
            value = high_card
        else:
            value = texture(pair_value(pairs[0])) * soft
    else:
        value = high_card

    if cards_out < 5 and value < 0.8:  # draws
        flop = cards_out == 3
        chance = 0.0
        for suit in range(4):
            held = suits[suit] - board_suits[suit]
            if suits[suit] == 4 and held >= 1:
                chance = (0.30 if flop else 0.16) if short else (0.35 if flop else 0.19)
                if held == 1:
                    best = max(rank for rank, s in hole if s == suit)
                    chance *= 0.85 if best >= 12 else 0.55
        outs = 0
        for rank in range(6 if short else 2, 15):
            bit = 1 << (rank - 2)
            if not mask & bit and straight[mask | bit] and straight[mask | bit] != straight[board_mask | bit]:
                outs += 1
        if outs:
            if short:
                run = (0.45 if flop else 0.26) if outs >= 2 else (0.25 if flop else 0.13)
            else:
                run = (0.31 if flop else 0.17) if outs >= 2 else (0.16 if flop else 0.09)
            chance = 1.0 - (1.0 - chance) * (1.0 - run)
        value += (1.0 - value) * chance * 0.8
    return value


def five_card_class(cards) -> int:
    """Category of exactly five cards: 0 high card .. 8 straight flush (hold'em order)."""
    ranks = [card[0] for card in cards]
    suit = cards[0][1]
    flush = cards[1][1] == suit and cards[2][1] == suit and cards[3][1] == suit and cards[4][1] == suit
    distinct = len(set(ranks))
    if distinct == 5:
        top, bottom = max(ranks), min(ranks)
        run = top - bottom == 4 or (top == 14 and sorted(ranks)[3] == 5)
        return 8 if run and flush else 5 if flush else 4 if run else 0
    if distinct == 4:
        return 1
    most = max(ranks.count(rank) for rank in ranks)
    if distinct == 3:
        return 3 if most == 3 else 2
    return 7 if most == 4 else 6


OMAHA_VALUE = (0.08, 0.2, 0.42, 0.6, 0.75, 0.8, 0.92, 0.99, 0.99)


def omaha_strength(hole, board) -> float:
    """Exactly two private cards and exactly three board cards play."""
    size = len(board)
    if size == 3:
        triples = (tuple(board),)
    elif size == 4:
        triples = tuple(tuple(board[:i] + board[i + 1:]) for i in range(4))
    else:
        triples = tuple((board[i], board[j], board[k])
                        for i in range(3) for j in range(i + 1, 4) for k in range(j + 1, 5))
    best = 0
    for i in range(3):
        for j in range(i + 1, 4):
            pair = (hole[i], hole[j])
            for triple in triples:
                found = five_card_class(pair + triple)
                if found > best:
                    best = found
    value = OMAHA_VALUE[best]
    board_ranks = [card[0] for card in board]
    board_top = max(board_ranks)
    board_suits = [0, 0, 0, 0]
    for _, suit in board:
        board_suits[suit] += 1
    board_paired = len(set(board_ranks)) < size
    hole_ranks = [card[0] for card in hole]
    if best == 5:
        suit = board_suits.index(max(board_suits))
        mine = max((rank for rank, s in hole if s == suit), default=0)
        missing = [rank for rank in range(14, 1, -1) if not any(c == (rank, suit) for c in board)]
        value = 0.93 if missing and mine == missing[0] else 0.84 if len(missing) > 1 and mine == missing[1] else 0.72
        if board_paired:
            value *= 0.9
    elif best == 4:
        if max(board_suits) >= 3:
            value *= 0.75
        if board_paired:
            value *= 0.85
    elif best == 3:
        sets = [rank for rank in set(hole_ranks) if hole_ranks.count(rank) >= 2 and rank in board_ranks]
        if sets:
            value = 0.8 if max(sets) == board_top else 0.7
        if max(board_suits) >= 3:
            value *= 0.8
    elif best == 2:
        if board_top in hole_ranks and not board_paired:
            value = 0.5
    elif best == 1:
        if board_top in hole_ranks or max(hole_ranks.count(rank) * rank for rank in hole_ranks) > 2 * board_top:
            value = 0.28
    if size < 5 and value < 0.8:
        flop = size == 3
        chance = 0.0
        for suit in range(4):
            if board_suits[suit] == 2:
                held = sorted((rank for rank, s in hole if s == suit), reverse=True)
                if len(held) >= 2:
                    chance = (0.33 if flop else 0.18) * (1.0 if held[0] >= 13 else 0.7)
        near = sum(1 for rank in set(hole_ranks) if any(0 < abs(rank - other) <= 2 for other in board_ranks))
        if near >= 3:
            chance = 1.0 - (1.0 - chance) * (0.8 if flop else 0.9)
        value += (1.0 - value) * chance * 0.8
    return value


# ----------------------------------------------------------------------------- 4. variants
# Each ruleset in zoo/variants/<name>.md has one entry under the same name:
#   detect    state -> bool, tried in order after an exact match on state.config.variant.
#   phases    {phase name: handler(state) -> Action} for the variant's extra phases.
#   strength  state -> 0..1. Before the flop: the hold'em-equivalent chance of beating one
#             random hand. After it: about the chance of beating one opponent still in.
#   spread    how far apart hands are before the flop, relative to hold'em (decide uses it
#             to turn a score into a chance against a range).
#   tight     amount taken off every strength after the flop, where strong hands are common.


def holdem_strength(state: GameState) -> float:
    hole = parse(state.cards)
    if len(hole) < 2:
        return 0.0
    if not state.board:
        return preflop_q(hole)
    return made_strength(hole, parse(state.board))


def short_deck_strength(state: GameState) -> float:
    hole = parse(state.cards)
    if len(hole) < 2:
        return 0.0
    if not state.board:
        return preflop_q(hole, True)
    return made_strength(hole, parse(state.board), True)


def omaha_state_strength(state: GameState) -> float:
    hole = parse(state.cards)
    if len(hole) != 4:
        return holdem_strength(state)
    if not state.board:
        return preflop_q(hole)
    return omaha_strength(hole, parse(state.board))


def discard_reveal_select(state: GameState) -> Action:
    """Keep the two cards that play best with the flop; show the one that tells least."""
    hole, board = parse(state.cards), parse(state.board)
    options = [(0, 1), (0, 2), (1, 2)]
    if len(hole) != 3:
        return automatic(state)
    if len(board) >= 3:
        keep = max(options, key=lambda pair: made_strength([hole[pair[0]], hole[pair[1]]], board))
    else:
        keep = max(options, key=lambda pair: two_card_q(hole[pair[0]], hole[pair[1]]))
    discard = 3 - keep[0] - keep[1]
    board_ranks = {rank for rank, _ in board}
    first, second = keep
    hits = [hole[first][0] in board_ranks, hole[second][0] in board_ranks]
    if hits[0] != hits[1]:  # one card made our hand: show the other
        reveal = second if hits[0] else first
    else:
        reveal = first if hole[first][0] <= hole[second][0] else second
    return Action("select", cards=(discard, reveal))


def auction_bid(state: GameState) -> Action:
    """Bid about what a third card is worth. It is a second-price auction and the card is
    worth a large share of the pot, so the bids are big; most with a hand that can improve."""
    allowed = state.can("bid")
    hole, board = parse(state.cards), parse(state.board)
    value = made_strength(hole, board) if len(board) >= 3 and len(hole) >= 2 else 0.3
    if value >= 0.85:
        gain = 0.8  # mostly to keep the card from someone else
    elif value >= 0.36:
        gain = 1.2
    else:
        gain = 0.3
    stack = my_stack(state)
    wanted = min(int(state.pot * gain), int(stack * 0.3))
    if state.players_remaining <= paid_places(state) + 1:
        wanted //= 2
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, wanted)))


def irish_discard(state: GameState) -> Action:
    """Four cards before the flop, two thrown away once it is out: keep the best pair."""
    hole, board = parse(state.cards), parse(state.board)
    options = [(i, j) for i in range(len(hole)) for j in range(i + 1, len(hole))]
    if len(board) >= 3:
        keep = max(options, key=lambda pair: made_strength([hole[pair[0]], hole[pair[1]]], board))
    else:
        keep = max(options, key=lambda pair: two_card_q(hole[pair[0]], hole[pair[1]]))
    return Action("discard", cards=tuple(index for index in range(len(hole)) if index not in keep)[:2])


def irish_strength(state: GameState) -> float:
    hole = parse(state.cards)
    if len(hole) == 4 and not state.board:
        return preflop_q(hole)
    return holdem_strength(state)


def _boards(state: GameState) -> list:
    """Both boards of a double-board table (kit RULES.md: state.variant["boards"])."""
    extra = getattr(state, "variant", None)
    boards = extra.get("boards") if isinstance(extra, dict) else None
    if isinstance(boards, (list, tuple)) and len(boards) == 2 and all(len(board) >= 3 for board in boards):
        return [parse(board) for board in boards]
    return [parse(state.board)] if len(state.board) >= 3 else []


def _pittsburgh_best(hole, boards) -> tuple:
    """(strength averaged over the boards, the two indices kept): each board wins half the pot,
    and the same two cards play on both."""
    best = (-1.0, (0, 1))
    for i in range(len(hole) - 1):
        for j in range(i + 1, len(hole)):
            pair = [hole[i], hole[j]]
            score = sum(made_strength(pair, board) for board in boards) / len(boards)
            if score > best[0]:
                best = (score, (i, j))
    return best


def pittsburgh_strength(state: GameState) -> float:
    hole = parse(state.cards)
    if len(hole) < 2:
        return 0.0
    boards = _boards(state)
    if not boards:
        return preflop_q(hole)
    return _pittsburgh_best(hole, boards)[0]


def pittsburgh_discard(state: GameState) -> Action:
    """Throw away one of three cards after the turn: `cards=(index,)` of the card not kept."""
    hole, boards = parse(state.cards), _boards(state)
    if len(hole) != 3 or not boards:
        return automatic(state)
    keep = _pittsburgh_best(hole, boards)[1]
    return Action("discard", cards=(3 - keep[0] - keep[1],))


VARIANTS = {
    "double_board_turn_discard": {  # the kit's name; first, so its discard phase does not route to irish
        "detect": lambda state: isinstance(getattr(state, "variant", None), dict) and "boards" in state.variant,
        "phases": {"discard": pittsburgh_discard},
        "strength": pittsburgh_strength, "spread": 0.75, "tight": 0.04,
    },
    "irish": {
        "detect": lambda state: state.phase == "discard",
        "phases": {"discard": irish_discard},
        "strength": irish_strength, "spread": 0.6, "tight": 0.03,
    },
    "discard_reveal": {
        "detect": lambda state: state.phase == "select" or (len(state.cards) == 3 and not state.board),
        "phases": {"select": discard_reveal_select},
        "strength": holdem_strength, "spread": 0.75, "tight": 0.04,
    },
    "omaha": {
        "detect": lambda state: len(state.cards) == 4,
        "phases": {},
        "strength": omaha_state_strength, "spread": 0.45, "tight": 0.0,
    },
    "auction": {
        "detect": lambda state: state.phase == "bid" or (len(state.cards) == 3 and len(state.board) >= 3),
        "phases": {"bid": auction_bid},
        "strength": holdem_strength, "spread": 0.85, "tight": 0.02,
    },
    "short_deck": {  # nothing in the state marks it: recognised by state.config.variant only
        "detect": lambda state: False,
        "phases": {},
        "strength": short_deck_strength, "spread": 0.6, "tight": 0.0,
    },
    "holdem": {  # keep last: the fallback when nothing else is recognised
        "detect": lambda state: True,
        "phases": {},
        "strength": holdem_strength, "spread": 0.85, "tight": 0.0,
    },
}


def variant_of(state: GameState) -> str:
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS:
        return name
    return next(key for key, variant in VARIANTS.items() if variant["detect"](state))


# ----------------------------------------------------------------------------- 5. memory
# The memory bytes hold whole numbers only: a header for the hand in progress, then ten
# counters for each of up to ten seats (by position in state.seats, since seat numbers are
# anonymised).
SEATS, HEADER, PER = 10, 10, 10
FORMAT = "<%dH" % (HEADER + SEATS * PER)
SIZE = struct.calcsize(FORMAT)
H_VERSION, H_RAISES, H_STREET, H_BIG, H_RAISER, H_BET_OUT, H_BETTOR, H_STREET_RAISES, H_BLINDS = range(9)
C_HANDS, C_ENTERED, C_RAISED, C_SHOVED, C_BETS, C_CALLS, C_FOLDS, C_STACK, C_FLAGS = range(9)
NOBODY = 255


def fresh(state: GameState) -> list:
    counters = [0] * (HEADER + SEATS * PER)
    counters[H_VERSION] = 1
    counters[H_BIG] = counters[H_RAISER] = counters[H_BETTOR] = NOBODY
    start = min(65535, int(getattr(state.config, "starting_stack", 2000) or 2000))
    for index, seat in enumerate(state.seats[:SEATS]):
        counters[HEADER + index * PER + C_STACK] = 0 if seat.status == "busted" else start
    return counters


def load(memory: bytes, state: GameState) -> list:
    if memory and len(memory) == SIZE:
        counters = list(struct.unpack(FORMAT, memory))
        if counters[H_VERSION] == 1:
            return counters
    return fresh(state)


def observe(c: list, state: GameState) -> None:
    """Fold the events since our last turn into the counters."""
    index_of = {seat.seat: index for index, seat in enumerate(state.seats[:SEATS])}
    for event in state.events:
        kind = event.kind
        if kind == "hand":
            c[H_RAISES] = c[H_STREET] = c[H_BET_OUT] = c[H_STREET_RAISES] = c[H_BLINDS] = 0
            c[H_BIG] = c[H_RAISER] = c[H_BETTOR] = NOBODY
            for base in range(HEADER, HEADER + SEATS * PER, PER):
                c[base + C_FLAGS] = 0
                if c[base + C_STACK] > 0 and c[base + C_HANDS] < 60000:
                    c[base + C_HANDS] += 1
            continue
        if kind == "board":
            c[H_STREET] += 1
            c[H_BET_OUT] = c[H_STREET_RAISES] = 0
            c[H_BETTOR] = NOBODY
            continue
        index = index_of.get(event.seat)
        if index is None:
            continue
        base = HEADER + index * PER
        if kind == "blind":
            c[H_BLINDS] += 1
            # heads-up the kit posts the big blind first: take the blind that posted the full big blind
            if event.amount >= max(1, state.blinds.big_blind) or (c[H_BLINDS] == 2 and c[H_BIG] == NOBODY):
                c[H_BIG] = index
        elif kind == "stack":
            c[base + C_STACK] = max(0, min(65535, int(event.amount)))
        elif c[H_STREET] == 0:
            if kind == "call" or kind == "raise":
                flags = c[base + C_FLAGS]
                if not flags & 1:
                    c[base + C_ENTERED] += 1
                if kind == "raise":
                    if not flags & 2:
                        c[base + C_RAISED] += 1
                    if not flags & 4 and event.amount >= 0.85 * c[base + C_STACK] > 0:
                        c[base + C_SHOVED] += 1
                        flags |= 4
                    flags |= 2
                    c[H_RAISES] += 1
                    c[H_RAISER] = index
                c[base + C_FLAGS] = flags | 1
        elif kind == "raise":
            c[base + C_BETS] += 1
            c[H_BET_OUT] = 1
            c[H_BETTOR] = index
            c[H_STREET_RAISES] += 1
        elif kind == "call":
            c[base + C_CALLS] += 1
        elif kind == "fold" and c[H_BET_OUT]:
            c[base + C_FOLDS] += 1


class Read:
    """What the counters say about one seat. All values are 1.0 for an average player."""

    __slots__ = ("loose", "sticky", "dead", "station", "shove_rate", "fold_to_bet", "credit", "hands")

    def __init__(self, c: list, index: int):
        base = HEADER + index * PER
        hands, entered, raised = c[base + C_HANDS], c[base + C_ENTERED], c[base + C_RAISED]
        self.hands = hands
        self.dead = hands >= 10 and entered == 0
        enter_rate = (entered + 2.5) / (hands + 10.0)
        raise_rate = (raised + 1.8) / (hands + 10.0)
        self.loose = min(3.0, max(0.3, raise_rate / 0.18))  # how wide it raises
        self.sticky = 0.03 if self.dead else min(2.5, max(0.3, enter_rate / 0.25))  # how wide it continues
        self.station = hands >= 8 and enter_rate > 0.36 and raised < 0.35 * entered
        self.shove_rate = c[base + C_SHOVED] / hands if hands >= 6 else 0.0
        bets, calls, folds = c[base + C_BETS], c[base + C_CALLS], c[base + C_FOLDS]
        self.fold_to_bet = (folds + 1.0) / (folds + calls + 2.0)
        aggression = (bets + 1.0) / (bets + calls + folds + 3.0)
        self.credit = min(1.7, max(0.5, 0.33 / aggression))  # how much to believe its bets


# ----------------------------------------------------------------------------- 6. strategy
def paid_places(state: GameState) -> int:
    try:
        return sum(1 for points in state.config.payouts if points > 0) or 3
    except Exception:
        return 3


def pressure(state: GameState, mine: int, theirs: int) -> tuple[float, float]:
    """(extra win chance wanted before risking our stack, extra weight on chips lost).
    Small early and once in the points; large on the bubble when someone else is shorter."""
    left, paid = state.players_remaining, paid_places(state)
    if left <= 2:
        return 0.0, 0.0
    if left <= paid:
        return 0.015, 0.05
    if left == paid + 1:
        if theirs < mine:
            return 0.03, 0.1
        shorter = any(seat.seat != state.seat and seat.status != "busted" and
                      0 < seat.stack + seat.bet < 0.7 * mine for seat in state.seats)
        return (0.10, 0.4) if shorter else (0.05, 0.15)
    return 0.03, 0.1


def decide(state: GameState, variant: dict, c: list) -> Action:
    seats = state.seats
    index_of = {seat.seat: index for index, seat in enumerate(seats[:SEATS])}
    me = next(seat for seat in seats if seat.seat == state.seat)
    my_index = index_of.get(state.seat, NOBODY)
    others = [seat for seat in seats if seat.seat != state.seat and seat.status in ("active", "all_in")]
    if not others:
        return Action.check() if state.can("check") else Action.call() if state.can("call") else passive(state)
    reads = {seat.seat: Read(c, index_of[seat.seat]) for seat in others if seat.seat in index_of}
    for seat in others:
        if seat.seat not in reads:
            reads[seat.seat] = Read(fresh(state), 0)
    strength = variant["strength"](state)
    if state.board:
        return after_flop(state, variant, c, me, my_index, others, reads, strength)
    return before_flop(state, variant, c, me, my_index, others, reads, strength, seats)


def before_flop(state, variant, c, me, my_index, others, reads, q, seats) -> Action:
    big = max(1, state.blinds.big_blind)
    spread = variant["spread"]
    total = me.stack + me.bet
    depth = total / big
    pot, to_call = state.pot, min(state.to_call, me.stack)
    high_bet = max(seat.bet for seat in seats)
    left = state.players_remaining
    share = percentile(q)
    can_check = state.can("check") is not None
    raises = c[H_RAISES]
    if raises == 0 and high_bet > big:  # the counters missed something: trust the table
        raises = 1

    if raises == 0:
        big_seat = seats[c[H_BIG]].seat if c[H_BIG] < len(seats) else None
        behind = [seat for seat in others if seat.status == "active" and
                  (seat.bet < high_bet or seat.seat == big_seat)]
        limpers = [seat for seat in others if seat.status == "active" and seat not in behind]
        deepest = max((seat.stack + seat.bet for seat in behind + limpers), default=0)
        extra, weight = pressure(state, total, deepest)
        effective = min(total, deepest) / big if deepest else depth

        if behind or limpers:
            if depth <= SETTINGS["shove_depth"] or effective <= SETTINGS["shove_depth"] - 4:
                # Shove or fold: expected chips against each seat's likely calling range.
                base_call = min(0.85, max(0.05, 1.7 / max(1.0, effective)))
                value, nobody = 0.0, 1.0
                for seat in behind + limpers:
                    read = reads[seat.seat]
                    chance = base_call * read.sticky
                    if seat.seat == big_seat:
                        chance *= 1.3
                    if seat in limpers:
                        chance *= 1.2
                    chance = min(0.95, chance)
                    reach = min(total, seat.stack + seat.bet)
                    win = equity(q, chance, spread)
                    called = win * (pot + reach - seat.bet) - (1.0 - win) * (reach - me.bet) * (1.0 + weight)
                    value += nobody * chance * called
                    nobody *= 1.0 - chance
                value += nobody * pot
                if value > (0.4 * big if can_check else 0.15 * big) + extra * total * 0.5:
                    return shove(state)
                if can_check:
                    return Action.check()
                if to_call <= big // 2 and to_call * 12 <= me.stack and share > 0.45:
                    return Action.call()  # cheap completion from the small blind
                return passive(state)

            # Deeper: open by position, wider when the seats behind give up their blinds.
            callers = sum(min(1.6, reads[seat.seat].sticky) for seat in behind)
            callers += sum(1.2 * min(1.6, reads[seat.seat].sticky) for seat in limpers)
            width = min(1.0, SETTINGS["open_width"] / (callers + 0.1) ** 0.85)
            if left == 2:
                width = max(width, 0.8)
            elif left <= paid_places(state):
                width *= 1.2
            elif left == paid_places(state) + 1:
                width *= 1.3 if total > deepest else 0.85
            if limpers:
                width *= 0.7
            if share >= 1.0 - width:
                size = (2.1 if depth < 30 else 2.5) * big + len(limpers) * big
                if any(reads[seat.seat].station for seat in behind + limpers) and share >= 0.85:
                    size += big  # callers pay more for our good hands
                if size >= 0.4 * total:
                    return shove(state)
                return raise_to(state, int(size))
            if can_check:
                return Action.check()
            if to_call <= big // 2 and share > (0.3 if not limpers else 0.2) and to_call * 15 <= me.stack:
                return Action.call()
            return passive(state)
        return Action.check() if can_check else Action.call() if to_call == 0 else passive(state)

    # ---- someone has raised
    raiser_index = c[H_RAISER]
    raiser = seats[raiser_index] if raiser_index < len(seats) and raiser_index != my_index else None
    if raiser is None or raiser.status not in ("active", "all_in"):
        raiser = max(others, key=lambda seat: seat.bet)
    read = reads[raiser.seat]
    their_total = raiser.stack + raiser.bet
    their_depth = their_total / big
    all_in = raiser.status == "all_in" or raiser.bet >= 0.6 * their_total
    if all_in:
        width = min(0.8, max(0.05, 2.2 / max(1.0, their_depth)))
        if left == 2:
            width *= 2.0
        elif left == 3:
            width *= 1.5
        if raises >= 2:
            width *= 0.5
        width *= read.loose
        if read.shove_rate > 0:
            width = max(width, 0.8 * read.shove_rate * (8.0 / max(2, left)) ** 0.5)
    else:
        width = 0.18 * (8.0 / max(2, left)) ** 0.7 if raises == 1 else 0.05
        width *= read.loose
    width = min(1.0, max(0.02, width))
    win = equity(q, width, spread)
    in_already = sum(1 for seat in others if seat is not raiser and seat.bet >= raiser.bet and seat.bet > big)
    win *= 0.85 ** in_already
    extra, weight = pressure(state, total, their_total)
    need = to_call / max(1.0, pot + to_call)
    committing = all_in or to_call >= 0.35 * me.stack

    if committing:
        if win >= need + extra:
            if win >= 0.6 and state.can("raise") and any(s.status == "active" for s in others if s is not raiser):
                return shove(state)  # shut out the players behind
            return Action.call()
        return passive(state)

    effective = min(total, their_total)
    if win >= 0.6:
        if effective <= 25 * big:
            return shove(state)
        return raise_to(state, int(3 * high_bet + in_already * high_bet))
    if effective <= 22 * big and state.can("raise"):
        # Shove over a loose opener: it folds most of what it opened.
        keeps = 0.9 if raiser.bet * 3 >= effective else min(0.9, max(0.15, 0.35 * read.sticky))
        called_win = equity(q, width * keeps, spread)
        called = called_win * (pot + effective - raiser.bet) - (1.0 - called_win) * (effective - me.bet) * (1.0 + weight)
        value = (1.0 - keeps) * pot + keeps * called
        still = sum(1 for seat in others if seat is not raiser and seat.status == "active")
        if value > 1.0 * big + extra * total + still * 0.5 * big and win >= 0.42:
            return shove(state)
    closing = c[H_BIG] == my_index
    if win >= need + (0.10 if closing else 0.14) and to_call <= (0.2 if closing else 0.12) * me.stack:
        return Action.call()
    return passive(state)


def after_flop(state, variant, c, me, my_index, others, reads, strength) -> Action:
    pot, to_call = max(1, state.pot), min(state.to_call, me.stack)
    street = len(state.board)
    strength -= variant["tight"]
    live = len(others)
    if live > 1:
        strength = strength ** (1.0 + 0.45 * (live - 1))
    able = [seat for seat in others if seat.status == "active"]
    station = any(reads[seat.seat].station for seat in others)
    high_bet = max(seat.bet for seat in state.seats)
    deepest = max(seat.stack + seat.bet for seat in others)
    extra, _ = pressure(state, me.stack + me.bet, deepest)

    if to_call <= 0:
        if not able:
            return Action.check() if state.can("check") else passive(state)
        if strength >= SETTINGS["value_bet"] - (0.06 if station else 0.0):
            size = pot * (0.85 if station else 0.66)
            if strength >= 0.8 and street == 5:
                size = pot * (1.0 if station else 0.8)
            if size >= 0.55 * me.stack:
                return shove(state)
            return raise_to(state, int(me.bet + size))
        if station or street == 5 and strength < 0.3 and live > 1:
            return Action.check()
        folds = sum(reads[seat.seat].fold_to_bet for seat in others) / live
        dead = all(reads[seat.seat].dead for seat in others)
        if street == 3 and c[H_RAISER] == my_index and live <= 2:
            if dead or _coin(state, 1) < SETTINGS["cbet"] * (1.0 if live == 1 else 0.45) * min(1.3, folds / 0.5):
                return raise_to(state, int(me.bet + 0.4 * pot))
        if street < 5 and live == 1 and 0.4 <= strength and _coin(state, 2) < 0.45:
            return raise_to(state, int(me.bet + 0.5 * pot))  # thin value, protection and draws
        if street == 5 and live == 1 and strength < 0.25 and folds > 0.6 and _coin(state, 3) < 0.35:
            return raise_to(state, int(me.bet + 0.6 * pot))
        return Action.check()

    # ---- facing a bet
    bettor_index = c[H_BETTOR]
    bettor = state.seats[bettor_index] if bettor_index < len(state.seats) and bettor_index != my_index else None
    read = reads.get(bettor.seat) if bettor is not None else None
    credit = read.credit if read is not None else 1.0
    size = to_call / max(1.0, pot - to_call)
    doubt = SETTINGS["bet_credit"] * credit * min(1.5, 0.5 + size)
    if c[H_STREET_RAISES] >= 2:
        doubt *= 1.6
    if street == 5:
        doubt *= 1.2
    adjusted = strength - doubt
    need = to_call / (pot + to_call)
    big_call = to_call >= 0.4 * me.stack
    if adjusted >= 0.78 and state.can("raise"):
        target = 3 * high_bet
        if target >= 0.5 * (me.stack + me.bet):
            return shove(state)
        return raise_to(state, int(target))
    if adjusted >= need + SETTINGS["call_margin"] + (extra if big_call else 0.0):
        return Action.call()
    return passive(state)


# ----------------------------------------------------------------------------- 7. helpers
def _coin(state: GameState, salt: int) -> float:
    """A repeatable number in [0, 1) from the hand: mixes frequencies without `random`."""
    x = state.hand_number * 7919 + state.seat * 104729 + salt * 31337 + len(state.board) * 613
    for card in state.cards:
        x = x * 131 + ord(card[0]) * 7 + ord(card[1])
    return ((x * 2654435761) & 0xFFFFFFFF) / 4294967296.0


def automatic(state: GameState) -> Action:
    """The platform's own choice in any phase: the first legal action at its minimum."""
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def passive(state: GameState) -> Action:
    """Check, else fold; in a phase that offers neither, the automatic choice."""
    if state.can("check"):
        return Action.check()
    if state.can("fold"):
        return Action.fold()
    return automatic(state)


def legal(action: Action, state: GameState) -> Action:
    """Last line of defence: an action kind that is not offered, or an amount out of range."""
    allowed = state.can(action.kind)
    if allowed is None:
        return passive(state)
    if action.kind == "raise":
        return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, int(action.amount))))
    return action


def raise_to(state: GameState, total: int) -> Action:
    """Raise to `total` chips for this betting round, clamped to what is legal."""
    allowed = state.can("raise")
    if allowed:
        return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, int(total))))
    return Action.call() if state.can("call") else passive(state)


def shove(state: GameState) -> Action:
    allowed = state.can("raise")
    if allowed:
        return Action.raise_to(allowed.max_amount)
    return Action.call() if state.can("call") else passive(state)


def my_stack(state: GameState) -> int:
    return next(seat.stack for seat in state.seats if seat.seat == state.seat)
