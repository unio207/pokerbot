"""The Maniac: believes aggression wins sit-and-gos, and tilts into more of it.

Source:   Claude Code (claude-opus-5-5)
Profile:  The Maniac: loose-aggressive pressure player that bets because it can
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    Plays 52-57% and raises 35-38% of hands in every variant (percentile thresholds per
          variant), c-bets almost every flop, barrels scare cards, raises min-bets, sizes at random.
          A big lost pot tilts it more aggressive for several hands (memory "t"); it folds air to a
          big river raise. All five variants ran on the mini simulator; no simulator guess relied on.

Layout (see zoo/_template/README.md): 1. act() crash-proof wrapper; 2. VARIANTS, one entry per
ruleset (detect, phases, strength, plus the extra fields decide reads); 3. decide(), the
temperament, written once with no variant tests; 4. helpers. Standard library only, no state
between calls except the memory bytes, no Monte Carlo in act: tables are built at import.
"""

import gc
import json
import random
from bisect import bisect_left
from functools import reduce
from itertools import combinations, combinations_with_replacement
from operator import or_

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

# ----------------------------------------------------------------------------- tuning knobs
OPEN_SHARE, STEAL_SHARE = 0.39, 0.60  # top share opened with a raise; from the last two seats (steals)
LIMP_SHARE = 0.66         # top share that at least limps / completes when unopened
THREEBET_SHARE, CALL_SHARE = 0.13, 0.48  # facing a normal raise: top share that re-raises, that calls
LIGHT_3BET_SHARE, LIGHT_3BET_P = 0.40, 0.55  # re-raise a min-raise (senses weakness): top share, how often
SHOVE_CALL_SHARE = 0.22   # top share that calls an all-in or a raise of 40%+ of the stack
SHORT_BB, SHORT_SHOVE_SHARE = 12, 0.55  # at or under this many big blinds: shove this top share or fold
CBET_P, BARREL_P, BLUFF_RIVER_P, SCARE_RIVER_P = 0.90, 0.62, 0.22, 0.75
STAB_P, CHECKED_TO_BONUS = 0.40, 0.25  # bet when not the aggressor; more when checked to
RAISE_WEAK_P, SEMIBLUFF_RAISE_P = 0.45, 0.18  # raise a min/small bet with anything; a bet with a pair/draw
BET_SIZES = (0.5, 0.5, 0.75, 1.0, 1.0, 1.4)  # pot fractions, drawn at random: no tell
TILT_BIG_POT_BB, TILT_BIG_POT_FRAC = 15, 0.25  # a big lost pot: whichever is larger
TILT_STEP, TILT_DECAY, TILT_GAIN = 0.35, 0.78, 0.8  # +tilt per big loss, x per hand, aggression x
RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}

# ----------------------------------------------------------------------------- 1. wrapper
class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        try:
            memory, tilt = update_memory(state, memory)
            variant = VARIANTS[variant_of(state)]
            if state.phase == "betting":
                action = decide(state, variant, tilt)
            else:
                # A decision phase the variant adds. No handler: the automatic choice.
                handler = variant["phases"].get(state.phase)
                action = handler(state, tilt) if handler else automatic(state)
            return legal(action, state), memory
        except Exception:
            return passive(state), memory

def update_memory(state, memory):
    """Tilt from the chip swing between hands. Keyed by hand number: a re-delivery is a no-op."""
    try:
        m = json.loads(memory.decode()) if memory else {}
        hand, start, tilt = int(m["h"]), int(m["s"]), min(1.0, max(0.0, float(m["t"])))
    except Exception:
        hand, start, tilt = 0, 0, 0.0
    if state.hand_number == hand:
        return memory, tilt
    now = next((e.amount for e in reversed(state.events) if e.kind == "stack" and e.seat == state.seat), None)
    if now is None:  # no end-of-hand stack event yet: our stack plus what is already in front of us
        now = me(state).stack + (me(state).bet if state.phase == "betting" and not state.board else 0)
    if 0 < hand < state.hand_number and start > 0:
        tilt *= TILT_DECAY ** (state.hand_number - hand)
        if start - now >= max(TILT_BIG_POT_BB * state.blinds.big_blind, TILT_BIG_POT_FRAC * start):
            tilt = min(1.0, tilt + TILT_STEP + (start - now) / start)
    return json.dumps({"h": state.hand_number, "s": now, "t": round(tilt, 3)}).encode(), tilt

# ----------------------------------------------------------------------------- 2. variants
def build_rules(ranks, low_straight, flush_over_full):
    """Five-card values (bigger wins) keyed by sorted ranks: one table plain, one for flushes."""
    flush_cat, full_cat = (6, 5) if flush_over_full else (5, 6)
    plain, flush = {}, {}
    for key in combinations_with_replacement(sorted(ranks, reverse=True), 5):
        counts = {r: key.count(r) for r in key}
        if max(counts.values()) > 4:
            continue
        wheel = key[:2] == (14, low_straight) and key[1] - key[4] == 3
        top = 0 if len(counts) < 5 else key[0] if key[0] - key[4] == 4 else low_straight if wheel else 0
        order = sorted(counts, key=lambda r: (counts[r], r), reverse=True)
        shape = tuple(sorted(counts.values(), reverse=True))
        cat = {(4, 1): 7, (3, 2): full_cat, (3, 1, 1): 3, (2, 2, 1): 2, (2, 1, 1, 1): 1}.get(shape, 4 if top else 0)
        plain[key] = encode(cat, (top,) if top else order)
        if len(counts) == 5:
            flush[key] = encode(8, (top,)) if top else encode(flush_cat, key)
    windows = [sum(1 << r for r in range(top - 4, top + 1)) for top in range(min(ranks) + 4, 15)]
    windows.append(2 | sum(1 << r for r in ranks if r <= low_straight))  # the ace plays low (bit 1)
    return {"plain": plain, "flush": flush, "windows": windows, "ranks": ranks,
            "made": {8: 1.0, 7: 0.97, 6: 0.93, 5: 0.9, 4: 0.85}}

def encode(cat, ranks):  # category then up to five ranks, four bits each
    return reduce(lambda value, r: value << 4 | r, tuple(ranks) + (0,) * (5 - len(ranks)), cat)

def rank5(cards, rules):
    key = tuple(sorted((c[0] for c in cards), reverse=True))
    flush = cards[0][1] == cards[1][1] == cards[2][1] == cards[3][1] == cards[4][1]
    return rules["flush" if flush else "plain"][key]

FULL = build_rules(range(2, 15), 5, False)
SHORT = build_rules(range(6, 15), 9, True)  # no 2-5, flush beats full house, A-6-7-8-9 wheel
DECK = [(r, s) for r in range(2, 15) for s in "cdhs"]
parse = lambda cards: [(RANK[c[0]], c[1]) for c in cards]  # noqa: E731
bit = lambda r: 1 << r | (2 if r == 14 else 0)  # noqa: E731

def postflop(hole, board, rules, exact):
    """(made, draw) scores of these private cards on this board. `exact`: all of them must
    play with exactly three board cards (Omaha's two). The board's own pairs are discounted."""
    fives = (hole + list(three) for three in combinations(board, 3)) if exact else combinations(hole + board, 5)
    best = max(rank5(five, rules) for five in fives)
    cat, hr, br = best >> 20, [c[0] for c in hole], sorted((c[0] for c in board), reverse=True)
    board_pairs = sum(br.count(r) >= 2 for r in set(br))
    air = 0.08 + (0.08 if 14 in hr else 0) + (0.04 if max(hr) > br[0] else 0)
    if cat >= 4:
        made = rules["made"][cat]
        if len(board) == 5 and not exact and rank5(board, rules) >= best:
            made = 0.3  # the board plays
    elif cat == 3:
        made = air + 0.1 if any(br.count(r) >= 3 for r in br) else 0.84 if hr[0] in hr[1:] else 0.76
    elif cat == 2:
        made = air + 0.08 if board_pairs >= 2 else 0.5 if board_pairs else 0.72
    elif cat == 1 and not board_pairs:
        p = best >> 16 & 15
        made = 0.66 if p > br[0] else 0.56 if p == br[0] else 0.44 if p >= br[1] else 0.36
    else:
        made = air
    draw = 0.0
    if len(board) < 5 and cat < 4:
        for suit in {c[1] for c in hole}:
            mine = sum(c[1] == suit for c in hole)
            if (mine >= 2 or not exact) and mine + sum(c[1] == suit for c in board) == 4:
                draw = 0.18
        windows, board_mask = rules["windows"], reduce(or_, map(bit, br), 0)
        mask = reduce(or_, map(bit, hr), board_mask)
        outs = set()  # ranks that would complete a straight our own cards are part of
        for w in windows:
            miss = w & ~mask
            if miss and not miss & (miss - 1) and w & ~board_mask != miss:
                outs.add(miss if miss != 2 else 1 << 14)  # the low ace is the ace
        draw += 0.14 if len(outs) >= 2 else 0.06 if outs else 0.0
    return made, min(draw, 0.24)

def chen(a, b, short=False):
    """Chen-style score of two cards; in a short deck A-6..A-9 connect and connectors gain."""
    (hi, s1), (lo, s2) = sorted((a, b), reverse=True)
    points = {14: 10, 13: 8, 12: 7, 11: 6}.get(hi, hi / 2)
    if hi == lo:
        return max(points * 2, 5)
    gap = hi - lo - 1 if not (short and hi == 14 and lo <= 9) else max(0, lo - 7)
    score = points + (2 if s1 == s2 else 0) - (0, 1, 2, 4, 5)[min(gap, 4)]
    return score + (1 if gap <= 1 and hi < 12 else 0) + (1 if short and gap <= 1 else 0)

def pair_scores(cards, short=False):
    return sorted((chen(a, b, short) for a, b in combinations(cards, 2)), reverse=True)

def pre_three(cards):  # the best two of three, plus a little for the spare's options
    scores = pair_scores(cards)
    return scores[0] + 0.15 * scores[1]

def pre_omaha(cards):  # four cards work together: the second and third pairs and double suits count
    scores = pair_scores(cards)
    suits = sorted((sum(c[1] == s for c in cards) for s in "cdhs"), reverse=True)
    return scores[0] + 0.4 * scores[1] + 0.2 * scores[2] + (1.5 if suits[:2] == [2, 2] else 0)

def distribution(score, deck, size, samples=20000):
    """Sorted scores of all (or a fixed-seed sample of) this variant's starting hands: percentiles."""
    rng = random.Random(size)
    hands = combinations(deck, 2) if size == 2 else (rng.sample(deck, size) for _ in range(samples))
    return sorted(score(list(hand)) for hand in hands)

def make_strength(pre, dist, rules, mode, shift=0.0):
    """strength(state) -> 0..1. Preflop: percentile among this variant's starting hands. After:
    made hand + draws. mode "all": best five of all private cards; "pairs": best two of them;
    "exact": best two that must both play (Omaha). `shift` lowers ordinary made hands."""
    def strength(state):
        cards, board = parse(state.cards), parse(state.board)
        if len(cards) < 2:
            return 0.0
        if not board:
            return bisect_left(dist, pre(cards)) / len(dist)
        if mode == "all" and len(cards) <= 3:
            return min(1.0, sum(postflop(cards, board, rules, False)))
        return max(min(1.0, m + d + (shift if m < 0.85 else 0)) for m, d in
                   (postflop(list(two), board, rules, mode == "exact") for two in combinations(cards, 2)))
    return strength

def scariness(card, board):
    """How much a face-up card frightens the table: aces, flush cards and straight cards."""
    rank, suit = card
    score = rank / 100 + (0.5 if rank == 14 else 0.2 if rank == 13 else 0)
    score += 0.4 if sum(c[1] == suit for c in board) >= 2 else 0
    return score + (0.3 if sum(1 for c in board if 0 < abs(c[0] - rank) <= 2) >= 2 else 0)

def discard_reveal_select(state, tilt):
    """Keep the two cards with the most ways to bet (draws and bluff potential outweigh a safe
    made hand), then show the scariest kept card (an ace, or a flush or straight card): the
    table sees the threat that backs up later barrels, while the hidden card carries the equity."""
    cards, board = parse(state.cards), parse(state.board)
    if len(cards) != 3 or len(board) < 3 or state.can("select") is None:
        return automatic(state)
    def keep_value(keep):
        made, draw = postflop([cards[i] for i in keep], board, FULL, False)
        return 0.6 * made + 2.0 * draw + 0.15 * max(scariness(cards[i], board) for i in keep)
    keep = max(combinations(range(3), 2), key=keep_value)
    reveal = max(keep, key=lambda i: scariness(cards[i], board))
    return Action("select", cards=(next(i for i in range(3) if i not in keep), reveal))

def auction_bid(state, tilt):
    """Bid most with draws and air: a third card adds most to them, and winning is public, so
    it backs up every later barrel. Strong made hands bid little; never over 20% of the stack."""
    allowed = state.can("bid")
    if allowed is None or len(state.cards) < 2 or len(state.board) < 3:
        return automatic(state)
    made, draw = postflop(parse(state.cards[:2]), parse(state.board), FULL, False)
    share = 0.10 if made >= 0.7 else 0.45 if draw else 0.30
    wanted = min(state.pot * share * (1 + TILT_GAIN * tilt) * seeded(state, 3).uniform(0.7, 1.3), 0.2 * me(state).stack)
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, int(wanted))))

def shown_weakness(state):
    """Extra aggression for each live opponent whose face-up cards are weak and miss the board."""
    board, bonus = parse(state.board), 0.0
    for seat in state.seats:
        if seat.seat != state.seat and seat.status in ("active", "all_in") and seat.shown_cards and all(
                c[0] < 11 and all(b[0] != c[0] for b in board) and scariness(c, board) < 0.35
                for c in parse(seat.shown_cards)):
            bonus += 0.12
    return min(bonus, 0.3)

def auction_pressure(state):
    """Everyone saw who won the auction: if it was us, they fear the third card."""
    won = any(e.kind == "auction" and e.seat == state.seat for e in state.history)
    return shown_weakness(state) + (0.15 if won else 0.0)

pre_holdem = lambda cards: pair_scores(cards)[0]  # noqa: E731
pre_short = lambda cards: pair_scores(cards, True)[0]  # noqa: E731
HOLDEM_DIST = distribution(pre_holdem, DECK, 2)
# Extra fields decide reads: "pressure" (state -> extra aggression from public information, default
# shown_weakness); "open_scale" (opening-range multiplier, default 1.0) evens out VPIP/PFR per variant.
VARIANTS = {
    "discard_reveal": {
        "detect": lambda state: state.phase == "select" or (len(state.cards) == 3 and not state.board),
        "phases": {"select": discard_reveal_select},
        "strength": make_strength(pre_three, distribution(pre_three, DECK, 3), FULL, "pairs"),
        "open_scale": 0.64,  # three cards: strong hands are common and tables bust faster
    },
    "omaha": {  # exactly two of the four private cards play; one pair is worth less
        "detect": lambda state: len(state.cards) == 4,
        "phases": {},
        "strength": make_strength(pre_omaha, distribution(pre_omaha, DECK, 4), FULL, "exact", -0.08),
        "open_scale": 0.6,
    },
    "auction": {  # the winner holds three cards, all of which play
        "detect": lambda state: state.phase == "bid",
        "phases": {"bid": auction_bid},
        "strength": make_strength(pre_holdem, HOLDEM_DIST, FULL, "all"),
        "pressure": auction_pressure,
    },
    "short_deck": {  # nothing in the state marks it: recognised by state.config.variant only
        "detect": lambda state: False,
        "phases": {},
        "strength": make_strength(pre_short, distribution(pre_short, [c for c in DECK if c[0] >= 6], 2),
                                  SHORT, "all"),
        "open_scale": 1.2,  # hands run closer together: open a little wider
    },
    "holdem": {  # keep last: the fallback when nothing else is recognised
        "detect": lambda state: True,
        "phases": {},
        "strength": make_strength(pre_holdem, HOLDEM_DIST, FULL, "all"),
    },
}

def variant_of(state: GameState) -> str:
    """Name of the ruleset this table plays: the kit's name if we know it, else by its signs."""
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    return name if name in VARIANTS else next(key for key, variant in VARIANTS.items() if variant["detect"](state))

# ----------------------------------------------------------------------------- 3. strategy
def decide(state: GameState, variant: dict, tilt: float = 0.0) -> Action:
    """The Maniac. Tilt and weak exposed cards scale every aggressive frequency up."""
    s, rng, bb = variant["strength"](state), seeded(state, 1), state.blinds.big_blind
    agg = 1 + TILT_GAIN * tilt + variant.get("pressure", shown_weakness)(state)
    stack, bet = me(state).stack, me(state).bet
    if not state.board:
        return preflop(state, s, agg, rng, bb, stack, bet, variant.get("open_scale", 1.0))
    streets = [[]]
    for event in state.history:  # this hand's events, split at each new board card
        streets.append([]) if event.kind == "board" else streets[-1].append(event)
    street, previous = streets[-1], next((st for st in reversed(streets[:-1]) if st), [])
    pot, to_call, river, size = state.pot, state.to_call, len(state.board) >= 5, rng.choice(BET_SIZES)
    if not to_call:
        if [e.seat for e in previous if e.kind == "raise"][-1:] == [state.seat]:  # we were the aggressor: keep firing
            p = CBET_P if len(state.board) == 3 else BARREL_P if not river else \
                SCARE_RIVER_P if scare_card(state) else BLUFF_RIVER_P
        else:
            p = STAB_P + (CHECKED_TO_BONUS if any(e.kind == "check" for e in street) else 0)
        if s >= 0.55 or rng.random() < min(0.97, p * agg):
            return raise_to(state, bet + max(bb, int(size * pot)))
        return passive(state)
    i_raised = any(e.kind == "raise" and e.seat == state.seat for e in street)
    bet_frac = to_call / max(1, pot - to_call)
    weak = to_call <= bb or bet_frac <= 0.34  # a min-bet or a small stab
    big = bet_frac >= 0.75 or to_call >= 0.4 * stack
    if river and s < 0.5 and (i_raised or big):
        return passive(state)  # the off switch: nothing, facing a big river bet or a re-raise
    target = bet + to_call + int(size * (pot + to_call))
    if (s >= 0.8 or (s >= 0.6 and weak and rng.random() < 0.5 * agg)  # value, or raise the weak bet
            or (not i_raised and weak and rng.random() < RAISE_WEAK_P * agg)
            or (not i_raised and not river and 0.42 <= s < 0.7 and rng.random() < SEMIBLUFF_RAISE_P * agg)):
        return raise_to(state, target)
    if s >= 0.42 or (weak and s >= 0.2) or (not big and not river and s >= 0.3):
        return Action.call()
    return passive(state)

def preflop(state, s, agg, rng, bb, stack, bet, scale):
    raises = [e for e in state.history if e.kind == "raise"]
    cards = parse(state.cards)
    a, b = max(combinations(cards, 2), key=lambda two: chen(*two)) if len(cards) >= 2 else ((0, "x"), (1, "y"))
    looks = a[0] == b[0] or a[1] == b[1] or abs(a[0] - b[0]) <= 1 or 14 in (a[0], b[0])  # pair/suited/connected/ace
    deepest = max((x.stack + x.bet for x in state.seats if x.seat != state.seat and x.status == "active"), default=0)
    effective = min(stack + bet, deepest) / max(1, bb)
    if not raises:
        share = (STEAL_SHARE if seats_to_act(state) <= 2 else OPEN_SHARE) * scale * agg + (0.08 if looks else -0.08)
        if effective <= SHORT_BB:
            return shove(state) if s >= 1 - SHORT_SHOVE_SHARE * agg else passive(state)
        if s >= 1 - share:
            limpers = sum(1 for e in state.history if e.kind == "call")  # + one big blind per limper
            return raise_to(state, int(bb * (rng.choice((2.5, 3, 3, 3.5, 4)) + limpers)))
        if s >= 1 - LIMP_SHARE * (0.5 + 0.5 * scale) * agg or state.can("check"):
            return Action.call() if state.can("call") else passive(state)
        return passive(state)
    if state.to_call >= 0.4 * stack or effective <= SHORT_BB:
        return shove(state) if s >= 1 - SHOVE_CALL_SHARE * agg else passive(state)
    min_raise = len(raises) == 1 and raises[0].amount <= 2 * bb
    if s >= 1 - THREEBET_SHARE * agg or (min_raise and s >= 1 - LIGHT_3BET_SHARE * agg
                                         and rng.random() < LIGHT_3BET_P):
        return shove(state) if effective <= 25 else raise_to(state, int(raises[-1].amount * rng.choice((2.8, 3, 3.5))))
    if s >= 1 - CALL_SHARE * min(agg, 1.3) and state.to_call <= 0.2 * stack:
        return Action.call()
    return passive(state)

def scare_card(state):
    """The newest board card is an ace, or completes a three-flush or a run of connected cards."""
    board = parse(state.board)
    new, old = board[-1], board[:-1]
    flush = sum(c[1] == new[1] for c in board) >= 3 and max(sum(c[1] == s for c in old) for s in "cdhs") < 3
    return new[0] == 14 or flush or sum(1 for c in old if 0 < abs(c[0] - new[0]) <= 2) >= 2

def seats_to_act(state):
    """Active players after us up to the big blind (the last blind posted) before the flop."""
    blinds = [e.seat for e in state.history if e.kind == "blind"]
    status, n = {x.seat: x.status for x in state.seats}, max(len(state.seats), 1)
    steps = (blinds[-1] - state.seat) % n if blinds else 0
    return sum(status.get((state.seat + k) % n) == "active" for k in range(1, steps + 1))

def seeded(state, salt):
    """A generator fixed by hand, seat and how far the hand has gone: a seed reproduces."""
    return random.Random(state.hand_number * 1000003 + state.seat * 7919 + len(state.history) * 31 + salt)

# ----------------------------------------------------------------------------- 4. helpers
def automatic(state: GameState) -> Action:
    """The platform's own choice in any phase: the first legal action at its minimum."""
    first = state.legal_actions[0]
    return Action(first.kind, first.min_amount)

def passive(state: GameState) -> Action:
    """Check, else fold; in a phase that offers neither, the automatic choice."""
    return Action.check() if state.can("check") else Action.fold() if state.can("fold") else automatic(state)

def legal(action: Action, state: GameState) -> Action:
    """Last line of defence: an action kind that is not offered, or a raise out of range."""
    allowed = state.can(action.kind)
    if allowed is None:
        return passive(state)
    if action.kind == "raise":
        return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, int(action.amount))))
    return action

def raise_to(state: GameState, total: int) -> Action:
    """Raise to `total` for this round, clamped; over 60% of our chips means all of them."""
    allowed = state.can("raise")
    if allowed:
        total = allowed.max_amount if total >= 0.6 * allowed.max_amount else int(total)
        return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, total)))
    return Action.call() if state.can("call") else passive(state)

def shove(state: GameState) -> Action:
    return raise_to(state, 1 << 40)

def me(state: GameState):
    return next(seat for seat in state.seats if seat.seat == state.seat)

gc.freeze()  # the import-time tables never change: keep the collector from re-scanning them
