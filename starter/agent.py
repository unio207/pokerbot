"""Starter bot for No Limit (Sequoia pokerbot tournament). Single file, standard library only.

Layout, top to bottom:
  1. act()            crash-proof wrapper: any error or illegal action becomes check/fold
  2. variant_decision the ONE place to handle a variant's extra decision phases
  3. hole_strength    the ONE place that scores private cards (rewrite for the variant)
  4. preflop / postflop betting logic, which only consumes those scores
  5. hand evaluator and the embedded 169-class preflop equity table

Everything about the table (blinds, payouts, hand cap, players) is read from `state`,
never hard-coded. Nothing is kept on `self` or in globals between calls; per-table
memory goes through the `memory` bytes.
"""

import json
import random

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

# ----------------------------------------------------------------------------- tuning knobs
SHOVE_MODE_BB = 12  # at or below this many big blinds: shove or fold preflop, no small raises
# Unopened shove range (fraction of best hands) by stack in big blinds, before position scaling.
SHOVE_RANGE = ((3, 0.75), (5, 0.50), (7, 0.36), (9, 0.28), (12, 0.20))
# Unopened raise range by number of players still to act behind us.
OPEN_RANGE = {0: 0.08, 1: 0.45, 2: 0.36, 3: 0.25, 4: 0.19, 5: 0.15, 6: 0.12, 7: 0.10}
THREE_BET_RANGE = 0.035  # re-raise a raise with this fraction of best hands
CALL_RAISE_RANGE = 0.10  # call a raise with this fraction (when the price is small)
CALL_SHOVE_DISCOUNT = 0.10  # equity vs a random hand overstates equity vs a shoving range
BUBBLE_CALL_MARGIN = 0.08  # extra equity required to call all-in one place off the points
VALUE_BET = 0.80  # postflop strength to bet/raise for value
MEDIUM_BET = 0.60  # postflop strength to bet half pot when checked to
SEMI_BLUFF_FREQ = 0.4


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        try:
            notes = _load(memory)
            _observe(state, notes)
            memory = json.dumps(notes, separators=(",", ":")).encode()
            return _legal(decide(state, notes), state), memory
        except Exception:
            return _passive(state), memory


def decide(state: GameState, notes: dict) -> Action:
    if state.phase != "betting":
        return variant_decision(state)
    if not state.board:
        return preflop(state, notes)
    return postflop(state)


# ----------------------------------------------------------------------------- variant hooks
def variant_decision(state: GameState) -> Action:
    """A decision phase the variant adds. RULES.md in your kit says what each one means.

    Default: the first legal action at its minimum, which is the platform's own automatic
    choice. Add one `if state.phase == ...` branch per phase of your variant.
    """
    if state.phase == "select" and len(state.cards) == 3:
        # Example (Bay Area variant): discard one of three hole cards, expose one of the
        # two kept. Keep the pair of cards that scores best; expose the lower kept card.
        best, keep = -1.0, (0, 1)
        for pair in ((0, 1), (0, 2), (1, 2)):
            kept = (state.cards[pair[0]], state.cards[pair[1]])
            score = _made_strength(kept, state.board) if state.board else _preflop_equity(kept)
            if score > best:
                best, keep = score, pair
        discard = 3 - keep[0] - keep[1]
        reveal = min(keep, key=lambda index: _RANK[state.cards[index][0]])
        return Action("select", cards=(discard, reveal))
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def hole_strength(state: GameState) -> tuple[float, float]:
    """(equity vs one random hand, percentile where 0.0 is the best hand) for our hole cards.

    Standard hold'em uses the embedded two-card table. With any other number of private
    cards this takes the best two-card combination, which is only a first guess:
    rewrite it once you know how many hole cards play at showdown.
    """
    cards = state.cards
    if len(cards) == 2:
        key = _class_key(cards[0], cards[1])
    else:
        key = max(
            (_class_key(a, b) for i, a in enumerate(cards) for b in cards[i + 1 :]),
            key=_EQUITY.__getitem__,
        )
    return _EQUITY[key], _PERCENTILE[key]


def postflop_strength(state: GameState) -> tuple[float, bool]:
    """(strength 0..1 as rough equity vs one random hand, has a strong draw)."""
    cards = state.cards
    if len(cards) <= 2:
        return _made_strength(cards, state.board), _has_draw(cards, state.board)
    # More than two private cards: best two-card combination (see hole_strength).
    best, draw = 0.0, False
    for i, a in enumerate(cards):
        for b in cards[i + 1 :]:
            best = max(best, _made_strength((a, b), state.board))
            draw = draw or _has_draw((a, b), state.board)
    return best, draw


# ----------------------------------------------------------------------------- preflop
def preflop(state: GameState, notes: dict) -> Action:
    equity, pct = hole_strength(state)
    me = _me(state)
    big_blind = max(1, state.blinds.big_blind)
    stack_bb = (me.stack + me.bet) / big_blind
    raises = [event for event in state.history if event.kind == "raise"]
    limpers = sum(1 for event in state.history if event.kind == "call")
    behind = _players_behind(state)
    paid = sum(1 for payout in state.config.payouts if payout > 0)
    left = state.players_remaining
    on_bubble = left == paid + 1
    in_points = left <= paid
    can_raise = state.can("raise")
    need = state.to_call / (state.pot + state.to_call) if state.to_call else 0.0

    # Facing an all-in, a raise that commits us, or any raise while short: call off or fold.
    committing = state.to_call >= 0.4 * me.stack
    if raises and (committing or stack_bb <= SHOVE_MODE_BB or not can_raise):
        discount = CALL_SHOVE_DISCOUNT
        if _raise_rate(notes, raises[-1].seat) > 0.35:
            discount = 0.03  # this seat raises constantly: its range is close to random
        margin = 0.03 + (BUBBLE_CALL_MARGIN if on_bubble else 0.0)
        if equity - discount >= need + margin:
            if can_raise and pct <= 0.06 and not committing:
                return Action.raise_to(can_raise.max_amount)
            return Action.call()
        return Action.fold()

    if not raises:
        widen = 1.3 if in_points else 1.0
        if stack_bb <= SHOVE_MODE_BB:
            limit = next((r for bb, r in SHOVE_RANGE if stack_bb <= bb), SHOVE_RANGE[-1][1])
            limit *= min(2.5, (8 / (behind + 1)) ** 0.6) * widen
            if on_bubble:
                limit *= 1.15 if me.stack >= _median_stack(state) else 0.9
            if limpers:
                limit *= 0.7
            if can_raise and behind > 0 and pct <= min(limit, 0.95):
                return Action.raise_to(can_raise.max_amount)
            if can_raise and behind == 0 and pct <= 0.5 * limit:
                return Action.raise_to(can_raise.max_amount)  # big blind punishing limpers
            return Action.check() if state.to_call == 0 else Action.fold()
        limit = OPEN_RANGE.get(behind, 0.10) * widen
        if can_raise and pct <= limit:
            size = (2.2 if stack_bb < 25 else 2.5) + limpers
            return _raise(state, int(size * big_blind))
        if state.to_call == 0:
            return Action.check()
        if need <= 0.2 and pct <= 0.6:
            return Action.call()  # cheap completion, e.g. from the small blind
        return Action.fold()

    # Deep and facing a raise.
    if can_raise and pct <= THREE_BET_RANGE:
        return _raise(state, 3 * (me.bet + state.to_call))
    cheap = state.to_call <= 0.12 * me.stack
    closing = behind == 0 and need < 0.3
    if cheap and (pct <= CALL_RAISE_RANGE or (closing and pct <= 0.2)):
        return Action.call()
    return Action.fold()


# ----------------------------------------------------------------------------- postflop
def postflop(state: GameState) -> Action:
    strength, draw = postflop_strength(state)
    me = _me(state)
    opponents = sum(1 for s in state.seats if s.status in ("active", "all_in")) - 1
    # A hand that beats one random hand 70% of the time beats three of them far less often.
    strength = strength ** (1 + 0.3 * max(0, opponents - 1))
    pot, to_call = state.pot, state.to_call
    can_raise = state.can("raise")

    if to_call == 0:
        if not can_raise:
            return Action.check()
        if strength >= VALUE_BET:
            return _raise(state, me.bet + int(0.66 * pot))
        if strength >= MEDIUM_BET:
            return _raise(state, me.bet + int(0.5 * pot))
        if draw and opponents <= 2 and random.random() < SEMI_BLUFF_FREQ:
            return _raise(state, me.bet + int(0.5 * pot))
        return Action.check()

    need = to_call / (pot + to_call)
    if strength >= 0.88 and can_raise:
        return _raise(state, me.bet + to_call + int(0.75 * (pot + to_call)))
    if to_call > 0.5 * me.stack and strength < 0.75:
        return Action.fold()  # do not call off a stack with a marginal hand
    if strength >= need + 0.12 or (draw and need <= 0.25):
        return Action.call()
    return Action.fold()


# ----------------------------------------------------------------------------- safety
def _legal(action: Action, state: GameState) -> Action:
    """Never hand the platform an illegal action: clamp raises, downgrade the rest."""
    if action.kind == "raise":
        allowed = state.can("raise")
        if allowed:
            return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, action.amount)))
        action = Action.call()
    if action.kind == "call" and not state.can("call"):
        action = Action.check()
    if state.phase != "betting" or state.can(action.kind):
        return action
    return _passive(state)


def _passive(state: GameState) -> Action:
    if state.can("check"):
        return Action.check()
    if state.can("fold"):
        return Action.fold()
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def _raise(state: GameState, total: int) -> Action:
    """Raise to `total` for this betting round; shove when that is most of our stack anyway."""
    allowed = state.can("raise")
    if not allowed:
        return Action.call() if state.can("call") else Action.check()
    total = max(allowed.min_amount, min(allowed.max_amount, total))
    if total >= 0.6 * allowed.max_amount:
        total = allowed.max_amount
    return Action.raise_to(total)


# ----------------------------------------------------------------------------- table reading
def _me(state: GameState):
    for seat in state.seats:
        if seat.seat == state.seat:
            return seat
    return state.seats[0]


def _players_behind(state: GameState) -> int:
    """Players still to act after us preflop if nobody raises (0 = we are the big blind)."""
    blinds = [event.seat for event in state.history if event.kind == "blind"]
    if not blinds or blinds[-1] == state.seat:
        return 0
    seats = state.seats
    index = next((i for i, seat in enumerate(seats) if seat.seat == state.seat), 0)
    count = 0
    for step in range(1, len(seats)):
        seat = seats[(index + step) % len(seats)]
        if seat.status == "active":
            count += 1
        if seat.seat == blinds[-1]:
            break
    return count


def _median_stack(state: GameState) -> int:
    stacks = sorted(seat.stack + seat.bet for seat in state.seats if seat.status != "busted")
    return stacks[len(stacks) // 2] if stacks else 0


# ----------------------------------------------------------------------------- table memory
def _load(memory: bytes) -> dict:
    """Parse defensively: memory can arrive cut, and a bad parse must not crash the bot."""
    try:
        notes = json.loads(memory) if memory else {}
        if isinstance(notes.get("hands"), int) and isinstance(notes.get("raises"), dict):
            return notes
    except Exception:
        pass
    return {"hands": 0, "raises": {}}


def _observe(state: GameState, notes: dict) -> None:
    for event in state.events:
        if event.kind == "hand":
            notes["hands"] += 1
        elif event.kind == "raise" and event.seat != state.seat:
            key = str(event.seat)
            notes["raises"][key] = notes["raises"].get(key, 0) + 1


def _raise_rate(notes: dict, seat) -> float:
    """Raises per hand by this seat at this table; 0 until there is a sample."""
    if notes["hands"] < 10:
        return 0.0
    return notes["raises"].get(str(seat), 0) / notes["hands"]


# ----------------------------------------------------------------------------- hand evaluation
_RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


def _straight_high(ranks) -> int:
    mask = 0
    for rank in ranks:
        mask |= 1 << rank
    if mask & (1 << 14):
        mask |= 2  # the ace also plays low
    for high in range(14, 4, -1):
        if (mask >> (high - 4)) & 31 == 31:
            return high
    return 0


def hand_rank(cards) -> tuple:
    """Best five of the given cards as a tuple that compares correctly (bigger wins)."""
    ranks = sorted((_RANK[card[0]] for card in cards), reverse=True)
    by_suit: dict[str, list[int]] = {}
    for card in cards:
        by_suit.setdefault(card[1], []).append(_RANK[card[0]])
    flush = next((sorted(v, reverse=True) for v in by_suit.values() if len(v) >= 5), None)
    if flush:
        high = _straight_high(flush)
        if high:
            return (8, high)
    counts: dict[int, int] = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1
    groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    top, top_count = groups[0]
    second, second_count = groups[1] if len(groups) > 1 else (0, 0)
    if top_count == 4:
        return (7, top, max((rank for rank in ranks if rank != top), default=0))
    if top_count == 3 and second_count >= 2:
        return (6, top, second)
    if flush:
        return (5, *flush[:5])
    high = _straight_high(ranks)
    if high:
        return (4, high)
    if top_count == 3:
        return (3, top, *[rank for rank in ranks if rank != top][:2])
    if top_count == 2 and second_count == 2:
        kicker = max((rank for rank in ranks if rank != top and rank != second), default=0)
        return (2, top, second, kicker)
    if top_count == 2:
        return (1, top, *[rank for rank in ranks if rank != top][:3])
    return (0, *ranks[:5])


def _made_strength(hole, board) -> float:
    """Rough equity vs one random hand from hand category and how the hole cards contribute."""
    mine = hand_rank(tuple(hole) + tuple(board))
    table = hand_rank(board)
    hole_ranks = sorted((_RANK[card[0]] for card in hole), reverse=True)
    board_ranks = sorted((_RANK[card[0]] for card in board), reverse=True)
    top_board = board_ranks[0]
    overcards = sum(1 for rank in hole_ranks if rank > top_board)
    nothing = 0.22 + 0.05 * overcards
    category = mine[0]
    if mine == table:
        strength = 0.30  # playing the board: at best a split
    elif category >= 6:
        strength = 0.97 if table[0] < 6 else 0.85
    elif category == 5:
        suit = next(s for s in "cdhs" if sum(card[1] == s for card in tuple(hole) + tuple(board)) >= 5)
        ours = max((_RANK[card[0]] for card in hole if card[1] == suit), default=2)
        on_board = sum(card[1] == suit for card in board)
        strength = 0.93 if on_board <= 3 else 0.55 + 0.35 * (ours - 2) / 12
    elif category == 4:
        strength = 0.86
    elif category == 3:
        if table[0] == 3:
            strength = 0.45  # trips are on the board; only kickers differ
        else:
            strength = 0.90 if hole_ranks[0] == hole_ranks[-1] else 0.84
    elif category == 2:
        if table[0] == 2:
            strength = 0.40
        elif table[0] == 1:  # the board is paired and we hold one more pair
            ours = mine[1] if mine[1] != table[1] else mine[2]
            strength = 0.64 if ours >= top_board else 0.50
        else:
            strength = 0.80
    elif category == 1:
        if table[0] == 1:
            strength = nothing + 0.05  # the pair is on the board
        elif mine[1] > top_board:
            strength = 0.72 + 0.06 * (mine[1] - 2) / 12  # overpair
        elif mine[1] == top_board:
            kicker = max((rank for rank in hole_ranks if rank != top_board), default=top_board)
            strength = 0.64 + 0.08 * (kicker - 2) / 12  # top pair
        elif len(board_ranks) > 1 and mine[1] >= sorted(set(board_ranks), reverse=True)[1]:
            strength = 0.52
        else:
            strength = 0.42
    else:
        strength = nothing
    if len(board) < 5 and category < 4:
        left = 5 - len(board)
        flush_draw, straight_draw = _draws(hole, board)
        strength += (0.07 * left if flush_draw else 0.0) + 0.025 * left * straight_draw
    return min(strength, 0.97)


def _draws(hole, board) -> tuple[bool, int]:
    """(four to a flush using a hole card, straight draw: 2 open-ended, 1 gutshot, 0 none)."""
    cards = tuple(hole) + tuple(board)
    flush_draw = any(
        sum(card[1] == suit for card in cards) == 4 and any(card[1] == suit for card in hole)
        for suit in "cdhs"
    )
    mask = 0
    for card in cards:
        mask |= 1 << _RANK[card[0]]
    if mask & (1 << 14):
        mask |= 2
    completing = sum(1 for rank in range(2, 15) if _straight_high_mask(mask | 1 << rank))
    return flush_draw, 2 if completing >= 2 else completing


def _straight_high_mask(mask: int) -> bool:
    if mask & (1 << 14):
        mask |= 2
    return any((mask >> low) & 31 == 31 for low in range(1, 11))


def _has_draw(hole, board) -> bool:
    if len(board) >= 5:
        return False
    flush_draw, straight_draw = _draws(hole, board)
    return flush_draw or straight_draw == 2


# ----------------------------------------------------------------------------- preflop table
def _class_key(a: str, b: str) -> str:
    """'AKs', 'T9o', 'QQ': the 169 starting-hand classes."""
    if _RANK[a[0]] < _RANK[b[0]]:
        a, b = b, a
    if a[0] == b[0]:
        return a[0] + b[0]
    return a[0] + b[0] + ("s" if a[1] == b[1] else "o")


def _preflop_equity(cards) -> float:
    return _EQUITY[_class_key(cards[0], cards[1])]


# Equity of each class against one random hand (Monte Carlo, tools/gen_preflop.py).
_EQUITY_TABLE = "AA:846 AKs:662 AKo:649 AQs:650 AQo:649 AJs:646 AJo:641 ATs:654 ATo:630 A9s:629 A9o:614 A8s:624 A8o:593 A7s:606 A7o:590 A6s:607 A6o:578 A5s:596 A5o:579 A4s:584 A4o:564 A3s:590 A3o:546 A2s:571 A2o:540 KK:834 KQs:632 KQo:622 KJs:629 KJo:603 KTs:613 KTo:592 K9s:602 K9o:584 K8s:592 K8o:559 K7s:580 K7o:549 K6s:565 K6o:549 K5s:548 K5o:533 K4s:557 K4o:513 K3s:531 K3o:515 K2s:535 K2o:500 QQ:811 QJs:593 QJo:582 QTs:595 QTo:578 Q9s:581 Q9o:546 Q8s:557 Q8o:544 Q7s:549 Q7o:500 Q6s:540 Q6o:505 Q5s:539 Q5o:502 Q4s:526 Q4o:498 Q3s:524 Q3o:481 Q2s:504 Q2o:466 JJ:775 JTs:578 JTo:565 J9s:549 J9o:525 J8s:532 J8o:520 J7s:533 J7o:489 J6s:502 J6o:478 J5s:495 J5o:460 J4s:484 J4o:462 J3s:485 J3o:452 J2s:473 J2o:455 TT:747 T9s:551 T9o:519 T8s:519 T8o:492 T7s:507 T7o:488 T6s:491 T6o:465 T5s:472 T5o:431 T4s:457 T4o:438 T3s:457 T3o:428 T2s:456 T2o:415 99:725 98s:501 98o:486 97s:482 97o:469 96s:464 96o:442 95s:464 95o:424 94s:442 94o:402 93s:430 93o:399 92s:415 92o:399 88:684 87s:479 87o:447 86s:462 86o:441 85s:435 85o:413 84s:434 84o:389 83s:407 83o:387 82s:400 82o:374 77:669 76s:459 76o:414 75s:439 75o:406 74s:422 74o:383 73s:408 73o:367 72s:385 72o:355 66:639 65s:434 65o:396 64s:420 64o:392 63s:381 63o:349 62s:370 62o:334 55:601 54s:406 54o:381 53s:399 53o:362 52s:384 52o:343 44:561 43s:386 43o:358 42s:373 42o:324 33:545 32s:356 32o:327 22:504"

_EQUITY = {key: int(value) / 1000 for key, value in (item.split(":") for item in _EQUITY_TABLE.split())}


def _percentiles() -> dict[str, float]:
    """Fraction of all starting hands that are strictly better, weighted by combinations."""
    combos = {key: 6 if len(key) == 2 else 4 if key[2] == "s" else 12 for key in _EQUITY}
    result, better = {}, 0
    for key in sorted(_EQUITY, key=_EQUITY.__getitem__, reverse=True):
        result[key] = better / 1326
        better += combos[key]
    return result


_PERCENTILE = _percentiles()
