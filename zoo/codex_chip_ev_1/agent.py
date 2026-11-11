"""Chip-EV push/fold zoo opponent (strategy B).

Source:   Codex (this session; not an independently sampled model).
Profile:  B. Chip-EV push/fold
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    Position-based chip accumulation; short-stack shove/fold; no ICM premium.

All ranges/equities are estimates from the supplied strategy chat and repository.
Exact single-opponent ICM ignores ties/future skill; multiway uses a risk premium.
No runtime rollouts, persistent globals, cross-bot imports, or mutable instance state.
Variants added 2026-11-11 (Claude Code): the section at the end hands this unchanged
hold'em strategy a hold'em-shaped hand; unknown phases still take the first legal choice.
"""

SURVIVAL = False
SHOVE_BB = 15
CALL_MARGIN = 0.02

import dataclasses
from bisect import bisect_left
from itertools import combinations

import poker_agent_sdk
from poker_agent_sdk import Action, GameState


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        # No instance/global writes: there is no learned state in these two policies.
        if state.phase != "betting":
            return variant_phase(state), b""
        state = view(state)  # variants: a hold'em-shaped hand (section at the end)
        return normalize(decide(state), state), b""


def passive(state):
    if state.can("check"):
        return Action.check()
    if state.can("fold"):
        return Action.fold()
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)


def normalize(action, state):
    allowed = state.can(action.kind)
    if action.kind == "raise" and allowed:
        return Action.raise_to(int(max(allowed.min_amount, min(allowed.max_amount, action.amount))))
    return action if allowed else passive(state)


def raise_to(state, amount):
    legal = state.can("raise")
    if legal:
        return Action.raise_to(int(max(legal.min_amount, min(legal.max_amount, amount))))
    return Action.call() if state.can("call") else passive(state)


def behind(state):
    # Identify the closing BB from actual blind events; skip busted/folded seats.
    blind_seats = [event.seat for event in state.history if event.kind == "blind"]
    live = [s.seat for s in state.seats if s.status != "busted"]
    if blind_seats:
        closing = blind_seats[-1]
    elif state.players_remaining == 2:
        closing = next((seat for seat in live if seat != state.button), state.seat)
    else:
        ring = sorted(live)
        after_button = [seat for seat in ring if seat > state.button] + [seat for seat in ring if seat <= state.button]
        closing = after_button[min(1, len(after_button)-1)]
    if state.seat == closing:
        return 0
    ring = sorted(s.seat for s in state.seats)
    order = [seat for seat in ring if seat > state.seat] + [seat for seat in ring if seat < state.seat]
    active = {s.seat for s in state.seats if s.status == "active"}
    count = 0
    for seat in order:
        count += int(seat in active)
        if seat == closing:
            return count
    return count


# Rows and percentages are the user's heuristic proposal, not solver ranges.
SHOVES = (
    (2, (90, 75, 55, 45, 38, 30, 30)),
    (3, (78, 60, 45, 35, 29, 23, 23)),
    (4, (74, 52, 38, 30, 25, 20, 20)),
    (5, (72, 46, 33, 26, 21, 17, 17)),
    (6, (68, 42, 29, 23, 19, 15, 15)),
    (8, (62, 36, 25, 19, 15, 12, 12)),
    (10, (58, 32, 22, 16, 13, 10, 10)),
    (12, (53, 28, 19, 14, 11, 9, 9)),
    (15, (46, 23, 16, 11, 9, 7, 7)),
)


def shove_limit(bb, players_behind):
    column = min(6, max(0, players_behind - 1))
    previous_bb, previous = SHOVES[0]
    if bb <= previous_bb:
        return previous[column] / 100
    for upper, row in SHOVES[1:]:
        if bb <= upper:
            mix = (bb - previous_bb) / (upper - previous_bb)
            return (previous[column] + mix * (row[column] - previous[column])) / 100
        previous_bb, previous = upper, row
    return previous[column] / 100


def icm_hero(stacks, hero, payouts):
    """Exact hero-only Malmuth-Harville for up to three paid places."""
    live = [i for i, stack in enumerate(stacks) if stack > 0]
    if stacks[hero] <= 0:
        return payouts[len(live)] if len(live) < len(payouts) else 0.0
    total = sum(stacks)
    mine = stacks[hero]
    result = payouts[0] * mine / total
    if len(payouts) > 1:
        for first in live:
            if first == hero:
                continue
            one = stacks[first] / total
            remaining = total - stacks[first]
            result += payouts[1] * one * mine / remaining
            if len(payouts) > 2:
                for second in live:
                    if second not in (hero, first):
                        result += payouts[2] * one * stacks[second] / remaining * mine / (remaining - stacks[second])
    return result


def risk_premium(state, me):
    """Conservative fallback for unresolved multiway or >3-place payout cases."""
    if state.players_remaining <= 2:
        return 0.0
    payouts = tuple(p for p in state.config.payouts if p > 0)
    if not payouts or len(set(payouts)) == 1 and len(payouts) >= state.players_remaining:
        return 0.0
    paid = len(payouts)
    other = [s.stack + s.bet for s in state.seats if s.seat != me.seat and s.status != "busted"]
    short = min(other, default=me.stack) <= (me.stack + me.bet) * .25
    bubble = state.players_remaining == paid + 1
    return .22 if bubble and short else .15 if bubble else .07 if state.players_remaining <= paid else .06


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


def required_equity(state, me, survival):
    cost = min(state.to_call, me.stack)
    eligible = eligible_after_call(state, me)
    need = cost / max(1, eligible)
    if not survival or not cost or state.players_remaining <= 2:
        return need
    opponents = [s for s in state.seats if s.seat != me.seat and s.status in ("active", "all_in")]
    payouts = tuple(state.config.payouts)
    # Exact utility only when the call closes a heads-up all-in and no extra side pots.
    if len(opponents) == 1 and (opponents[0].stack == 0 or cost == me.stack) and 0 < len(payouts) <= 3:
        villain = opponents[0]
        positions = {seat.seat: i for i, seat in enumerate(state.seats)}
        hero, other = positions[me.seat], positions[villain.seat]
        chips = [s.stack for s in state.seats]
        refund = max(0, state.pot + cost - eligible)
        fold = chips[:]
        fold[other] += state.pot
        win = chips[:]
        win[hero] += eligible - cost
        win[other] += refund
        lose = chips[:]
        lose[hero] -= cost
        lose[other] += state.pot + cost
        vf = icm_hero(fold, hero, payouts)
        vw = icm_hero(win, hero, payouts)
        vl = icm_hero(lose, hero, payouts)
        if vw > vl:
            return max(0.0, min(1.0, (vf - vl) / (vw - vl)))
    return min(1., need + risk_premium(state, me))


def decide(state):
    me = next(seat for seat in state.seats if seat.seat == state.seat)
    if len(state.cards) != 2 and not (state.board and len(state.cards) == 3):  # auction: 3 play
        # Standard-Hold'em lookup is deliberately disabled for unknown hole-card rules.
        return passive(state)
    if state.board:
        return postflop(state, me)
    bb = max(1, state.blinds.big_blind)
    depth = (me.stack + me.bet) / bb
    key = _class_key(*state.cards)
    eq, percentile = _EQUITY[key], _PERCENTILE[key]
    later = behind(state)
    raised = any(event.kind == "raise" for event in state.history)
    limpers = sum(event.kind == "call" for event in state.history)
    if raised:
        if state.to_call >= .35 * me.stack or depth <= SHOVE_BB:
            # Equity-v-random minus an explicit estimate for unknown raiser selection.
            # This is NOT range-conditioned rollout equity or a Nash calling solution.
            adjusted = max(0., eq - .10)
            required = required_equity(state, me, SURVIVAL)
            return Action.call() if adjusted >= required + CALL_MARGIN and state.can("call") else passive(state)
        if percentile <= .025 and state.can("raise"):
            return raise_to(state, 3 * (me.bet + state.to_call))
        if percentile <= (.06 if SURVIVAL else .12) and state.to_call <= .1 * me.stack:
            return Action.call() if state.can("call") else passive(state)
        return passive(state)
    if depth <= SHOVE_BB and later > 0:
        limit = shove_limit(depth, later) * (.8 if SURVIVAL else 1.)
        if limpers:
            limit *= .7
        if SURVIVAL and state.players_remaining == sum(p > 0 for p in state.config.payouts) + 1:
            limit *= .75
        if percentile <= limit and state.can("raise"):
            return raise_to(state, state.can("raise").max_amount)
        return passive(state)
    if SURVIVAL:
        limit = (.05, .38, .30, .20, .13, .10, .10, .10)[min(7, later)]
        if state.players_remaining == 2:
            limit = .8
    else:
        limit = (.10, .50, .45, .30, .22, .18, .15, .13)[min(7, later)]
        if state.players_remaining == 2:
            limit = .8
    if later == 0 and not limpers:
        return passive(state)
    if percentile <= limit and state.can("raise"):
        size = (2. if depth <= 30 else 2.2 if depth <= 60 else 2.5) + limpers
        return raise_to(state, size * bb)
    return passive(state)


def postflop(state, me):
    equity = _made_strength(state.cards, state.board)
    opponents = sum(s.status in ("active", "all_in") for s in state.seats) - 1
    # Deliberately conservative heuristic; this is not squaring independent equities.
    equity -= .10 * max(0, opponents - 1)
    if state.to_call:
        required = required_equity(state, me, SURVIVAL)
        margin = .08 if SURVIVAL else .05
        if state.to_call >= .35 * me.stack:
            margin += .03
        return Action.call() if equity >= required + margin and state.can("call") else passive(state)
    value = .78 if SURVIVAL else .67
    if equity >= value and state.can("raise"):
        return raise_to(state, me.bet + int((.66 if equity >= .80 else .5) * state.pot))
    return passive(state)


# Evaluator and random-opponent Monte Carlo estimates copied in-file from this repo's
# starter/agent.py for standalone upload. They are heuristics, not range/ICM solutions.
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


def _own_percentile(a, b):
    """This bot's own preflop percentile of two cards (used by the variants section)."""
    return _PERCENTILE[_class_key(a, b)]


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
