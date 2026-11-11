"""The Shark: a patient tight-aggressive player that reads the table and exploits it.

Source:   Claude Code
Profile:  The Shark: wants to exploit weak bots by tracking and adapting
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    TAG baseline as percentile thresholds per variant; ranges follow the players left
          (heads-up opens wide), push/fold below 12 bb, all-in calls priced by real ICM against
          the shover's estimated range. Per-seat VPIP/PFR/fold-to-open/cbet/bet/3bet, aggression
          and showdown stats (prior-blended, capped at 15 pp) drive steals, bluffs, thin value,
          light 3-bets and call-downs. All five variants ran on the mini simulator; its
          discard_reveal and auction rules are guesses.

Layout as in zoo/_template: act() wrapper, VARIANTS table, decide() written once, helpers.
Memory is compact JSON: an event marker (idempotent), this hand's tracking, per-seat stats,
and variant-only stats under the variant's name. Nothing is kept on self or in globals.
"""

import json
import random
import zlib
from bisect import bisect_left
from itertools import combinations, combinations_with_replacement

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

# ----------------------------------------------------------------------------- tuning knobs
ADAPT = True            # False: the plain TAG baseline, no reads (to measure what adapting earns)
MIN_HANDS = 15          # hands seen of a seat before its stats move anything
MIN_SAMPLE = 5          # chances to show a habit (bets faced, showdowns...) before that rate counts
PRIOR_W = 10            # weight of the prior in (observed + w * prior) / (n + w)
CAP = 0.15              # largest adjustment any one read can make
NO_READ_TIGHT = 0.92    # open-frequency multiplier while the table is unread
OPEN_FREQ = {0: 0.32, 1: 0.32, 2: 0.32, 3: 0.21, 4: 0.16, 5: 0.13, 6: 0.11, 7: 0.10}  # by players behind
HU_OPEN = 0.80                  # heads-up the button opens most hands
THREEBET, CALL_OPEN, FOURBET = 0.25, 0.30, 0.015  # 3-bet and flat as shares of the opener's range
PUSH_BB, PUSH_K = 12, 6.0       # push/fold below this depth; push share ~ PUSH_K / (depth * behind^0.6)
CALL_EDGE = 0.32                # calling an all-in: share of the shover's range = 2^((CALL_EDGE - need) / 0.1)
ICM_MIN = 0.05                  # risks below this share of our stack are priced by chip odds
VALUE_T, RAISE_T = 0.62, 0.84   # postflop strength to bet for value / raise for value
CBET, STAB, SEMI_BLUFF, RIVER_BLUFF = 0.55, 0.10, 0.30, 0.12
MULTIWAY = 0.05                 # strength discount per extra opponent
MANIAC_CALL = 0.33              # lighter call-downs only for bets below this share of our stack
SIZE, SIZE_SHOWN, SIZE_STATION = 0.66, 0.5, 1.0  # bet share of pot: normal, table sees a strong card, station
NEAR = 0.03                     # discard_reveal: keeps this close in strength count as equal
COVER_BB, AUCTION_CAP = 1.0, 0.2  # auction: cheap cover bid; never bid more than this share of stack
PRIOR = {"fof": 0.75, "vpip": 0.25, "pfr": 0.15, "fcb": 0.45, "ftb": 0.40, "f3b": 0.55, "agg": 0.40,
         "weak": 0.35, "bluff": 0.15}
H, VP, PF, CBF, CBX, TBF, TBX, AG, CL, SD, SW, BL, FBF, FBX, OPF, OPX = range(16)  # per-seat stat slots
RATES = {"fof": (OPX, OPF), "vpip": (VP, H), "pfr": (PF, H), "fcb": (CBX, CBF), "ftb": (FBX, FBF),
         "f3b": (TBX, TBF), "agg": (AG, CL), "weak": (SW, SD), "bluff": (BL, SD)}  # (count, chances)

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}
PRIME = dict(zip(range(2, 15), (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)))
CARD = {r + s: (PRIME[RANK[r]], 1 << i) for r in RANK for i, s in enumerate("cdhs")}


# ----------------------------------------------------------------------------- 1. wrapper
class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        try:
            mem = load(memory)
            name = variant_of(state, mem)
            update(mem, state, name)
            mem["v"] = name if name != "holdem" else mem["v"]
        except Exception:
            mem, name = fresh(), "holdem"
        variant = VARIANTS[name]
        try:
            handler = variant["phases"].get(state.phase)
            if state.phase != "betting":  # a phase the variant adds; one we do not know: automatic
                action = handler(state, mem) if handler and len(state.cards) in variant["cards"] else automatic(state)
            elif len(state.cards) not in variant["cards"]:
                action = passive(state)  # a card count this ruleset never deals: fail safe
            else:
                action = decide(state, variant, mem)
            action = legal(action, state)
        except Exception:
            action = passive(state)
        try:
            return action, json.dumps(mem, separators=(",", ":")).encode()
        except Exception:
            return action, memory


# ----------------------------------------------------------------------------- evaluator
def build_tables(wheel: int, flush_over_full: bool) -> tuple[dict, dict]:
    """Five-card values keyed by the product of rank primes: (unsuited, flush). A value is
    order<<24 | type<<20 | ranks, type 0..8 = high card..straight flush; order ranks types."""
    plain, flush, order_of = {}, {}, ({5: 6, 6: 5} if flush_over_full else {})
    for ranks in combinations_with_replacement(range(14, 1, -1), 5):
        groups = sorted(((ranks.count(r), r) for r in set(ranks)), reverse=True)
        if groups[0][0] == 5:
            continue
        key, distinct = 1, len(groups) == 5
        for r in ranks:
            key *= PRIME[r]
        straight = ranks[0] if distinct and ranks[0] - ranks[4] == 4 else 0
        if distinct and ranks[0] == 14 and ranks[1] == wheel and ranks[1] - ranks[4] == 3:
            straight = wheel
        shape = tuple(c for c, _ in groups)
        kind = {(4, 1): 7, (3, 2): 6, (3, 1, 1): 3, (2, 2, 1): 2, (2, 1, 1, 1): 1}.get(shape, 4 if straight else 0)
        code = sum(r << (16 - 4 * i) for i, r in enumerate([straight] if straight else [r for _, r in groups]))
        plain[key] = order_of.get(kind, kind) << 24 | kind << 20 | code
        if distinct:
            kind = 8 if straight else 5
            flush[key] = order_of.get(kind, kind) << 24 | kind << 20 | code
    return plain, flush

STD = {"tables": build_tables(5, False), "wheel": (14, 2, 3, 4, 5), "low": 2, "suit": 13}
SHORT = {"tables": build_tables(9, True), "wheel": (14, 6, 7, 8, 9), "low": 6, "suit": 9}

def best_value(hole, board, rules, exact2=False) -> int:
    """Best five-card value: any five of hole+board, or exactly two hole and three board."""
    plain, flush = rules["tables"]
    fives = ([a + b for a in combinations(hole, 2) for b in combinations(board, 3)] if exact2
             else combinations(tuple(hole) + tuple(board), 5))
    best = 0
    for five in fives:
        a, b, c, d, e = (CARD[x] for x in five)
        key = a[0] * b[0] * c[0] * d[0] * e[0]
        value = flush[key] if a[1] & b[1] & c[1] & d[1] & e[1] else plain[key]
        best = value if value > best else best
    return best


# ----------------------------------------------------------------------------- strength
def chen(a: str, b: str, short=False) -> float:
    """Chen-style score of two cards; in a short deck connectors gain and suits lose."""
    hi, lo = sorted((RANK[a[0]], RANK[b[0]]), reverse=True)
    score = {14: 10, 13: 8, 12: 7, 11: 6}.get(hi, hi / 2)
    if hi == lo:
        return max(5, 2 * score) - short
    gap = hi - lo - 1 - (short and hi == 14 and lo == 9)
    score += -(0, 1, 2, 4, 5)[min(gap, 4)] + ((1 if short else 2) if a[1] == b[1] else 0)
    return score + (1 + short if gap <= 1 and hi < 12 else 0)

def pre_score(cards, short=False) -> float:
    """One number per starting hand of 2, 3 or 4 private cards."""
    pairs = sorted((chen(a, b, short) for a, b in combinations(cards, 2)), reverse=True)
    if len(cards) <= 3:
        return pairs[0] + 0.15 * sum(pairs[1:])
    suits = sorted((sum(c[1] == s for c in cards) for s in "cdhs"), reverse=True)
    ranks = [c[0] for c in cards]
    return (pairs[0] + 0.5 * pairs[1] + 0.25 * pairs[2] + 1.5 * (suits[:2] == [2, 2])
            - 3 * any(ranks.count(r) >= 3 for r in ranks) - 2 * (suits[0] >= 3))

def preflop(holes: int, short=False, samples=4000):
    """Preflop strength = share of the variant's starting hands we beat, so thresholds on it
    are frequencies and one TAG rule gives TAG frequencies in every variant."""
    deck = [c for c in CARD if not short or RANK[c[0]] >= 6]
    draw = random.Random(holes * 7 + short)  # a private generator, used at import only
    table = sorted(pre_score(draw.sample(deck, holes), short) for _ in range(samples))
    return lambda cards: bisect_left(table, pre_score(cards, short) + 1e-9) / samples

def postflop(hole, board, variant, dead=()) -> float:
    """0..1: the made hand through the variant's (low, high) table, minus board danger, plus draws."""
    rules = variant["rules"]
    if len(board) < 3 or len(hole) < 2:
        return 0.0
    value = best_value(hole, board, rules, variant["exact2"])
    kind, top = value >> 20 & 15, value >> 16 & 15
    b_ranks = sorted((RANK[c[0]] for c in board), reverse=True)
    h_high, on_board = max(RANK[c[0]] for c in hole), b_ranks.count(top)
    if kind == 1 and on_board >= 2 or kind == 3 and on_board == 3:
        kind = 0  # the board's own pair or trips
    if kind == 0:
        q = (h_high - 2) / 12
    elif kind == 1:  # overpair, top pair by kicker, middle, low
        q = 1.0 if top > b_ranks[0] else 0.75 + h_high / 100 if top == b_ranks[0] else 0.45 if top >= b_ranks[1] else 0.2
    elif kind == 2:
        q = 0.3 if len(set(b_ranks)) < len(b_ranks) else 0.7 + 0.3 * (top == b_ranks[0])
    elif kind == 3:
        q = 1.0 if on_board == 1 else 0.6  # a set beats trips
    elif kind == 4:
        q = (top - 5) / 9
    elif kind == 5:
        suit = max("cdhs", key=lambda s: sum(c[1] == s for c in board))
        q = (max((RANK[c[0]] for c in hole if c[1] == suit), default=2) - 2) / 12
    else:
        q = 1.0
    lo, hi = variant["made"][kind]
    flushy = max(sum(c[1] == s for c in board) for s in "cdhs")
    strength = lo + (hi - lo) * q - (0.06 * (flushy - 2) if kind < 5 and flushy >= 3 else 0)
    strength -= 0.04 if kind < 4 and straight_window(set(b_ranks), rules, set()) >= 3 else 0
    if len(board) < 5 and kind < 4:
        strength += draws(hole, board, variant, dead) * (1.0 if len(board) == 3 else 0.6)
    return max(0.0, min(1.0, strength))

def straight_window(ranks: set, rules, completing: set, hole=(), need=0) -> int:
    """Most ranks of one straight window present; adds to `completing` the ranks that fill a
    window holding four, at least `need` of them ours."""
    most = 0
    for low in range(rules["low"] - 1, 11):
        window = set(rules["wheel"]) if low < rules["low"] else set(range(low, low + 5))
        most = max(most, len(window & ranks))
        if len(window & ranks) == 4 and len(window & set(hole)) >= need > 0:
            completing |= window - ranks
    return most

def draws(hole, board, variant, dead) -> float:
    """Flush and straight draw bonus; outs the table has seen (or we discarded) are removed."""
    rules, exact2 = variant["rules"], variant["exact2"]
    seen, need, bonus = set(hole) | set(board) | set(dead), 2 if exact2 else 1, 0.0
    for s in "cdhs":
        mine, theirs = sum(c[1] == s for c in hole), sum(c[1] == s for c in board)
        if mine >= need and min(mine, 2 if exact2 else 5) + theirs == 4:
            bonus = max(bonus, variant["draw"][0] * (rules["suit"] - sum(c[1] == s for c in seen)) / 9)
    b_ranks, completing = {RANK[c[0]] for c in board}, set()
    for cards in (combinations(hole, 2) if exact2 else [hole]):
        h = {RANK[c[0]] for c in cards}
        straight_window(h | b_ranks, rules, completing, h, need)
    if completing:
        dead_outs = sum(1 for c in dead if RANK[c[0]] in completing)
        bonus += variant["draw"][1] * min(2, len(completing)) / 2 * max(0.3, 1 - dead_outs / (4 * len(completing)))
    return bonus

def strength_of(name: str):
    def strength(state: GameState, dead=()) -> float:
        variant = VARIANTS[name]
        if not state.board:
            return variant["pre"](state.cards)
        if variant["pick2"] and len(state.cards) == 3:  # discard_reveal before its select phase
            return max(postflop(two, state.board, variant, dead) for two in combinations(state.cards, 2))
        return postflop(state.cards, state.board, variant, dead)
    return strength


# ----------------------------------------------------------------------------- 2. variants
def reveal_info(card: str, board) -> float:
    """How much a face-up card tells the table: it pairs the board, it is big, it suits the board."""
    return (any(card[0] == b[0] for b in board) + 0.6 * (RANK[card[0]] >= 13)
            + 0.4 * (sum(b[1] == card[1] for b in board) >= 2) + RANK[card[0]] / 100)

def discard_reveal_select(state: GameState, mem: dict) -> Action:
    """Strength first: keep the two cards that play best with the flop, draws included (the
    discard and others' face-up cards are dead outs). Then mislead: among keeps within NEAR of
    the best, take the one whose least telling card tells least, and turn that card up."""
    cards, board, options = state.cards, state.board, []
    for discard in range(len(cards)):
        keep = [i for i in range(len(cards)) if i != discard]
        strength = postflop([cards[i] for i in keep], board, VARIANTS["discard_reveal"],
                            (cards[discard],) + seen_cards(state))
        reveal = min(keep, key=lambda i: reveal_info(cards[i], board))
        options.append((strength, -reveal_info(cards[reveal], board), discard, reveal))
    top = max(o[0] for o in options)
    _, _, discard, reveal = max((o for o in options if o[0] >= top - NEAR), key=lambda o: (o[1], o[0]))
    mem["h"]["dc"] = cards[discard]  # a dead card only we know about
    return Action("select", cards=(discard, reveal))

def auction_bid(state: GameState, mem: dict) -> Action:
    """Second price, so bid about what the card is worth: equity it adds times the pot we
    expect to play for; draws gain most. Weak hands bid a small cover so the bid says little
    (free when nobody else bids); a coarse ladder hides fine distinctions."""
    allowed, bb, variant = state.can("bid"), state.blinds.big_blind, VARIANTS["auction"]
    now = postflop(state.cards, state.board, variant, seen_cards(state))
    made = postflop(state.cards, state.board, dict(variant, draw=(0.0, 0.0)))
    gain = 0.05 + 0.6 * (now - made) + (0.08 if 0.3 < made < 0.7 else 0.02)
    live = sum(s.status in ("active", "all_in") for s in state.seats) - 1
    worth = gain * state.pot * (1.5 + 0.5 * live) * max(0.2, 1 - 4 * push_premium(state))
    worth = min(max(worth, COVER_BB * bb if state.pot >= 4 * bb else 0), AUCTION_CAP * my_stack(state))
    step = max(1, bb // 2)
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, int(worth / step) * step)))

def reveal_credit(state: GameState, seat: int, mem: dict) -> float:
    """A bettor whose face-up card pairs or suits the board holds more; so does one that
    usually shows its lower card and now shows a big one."""
    card = next((s.shown_cards for s in state.seats if s.seat == seat and s.shown_cards), ())
    card = card or next((e.cards for e in state.history if e.kind == "reveal" and e.seat == seat), ())
    if not card:
        return 0.0
    c, row = card[0], mem["x"].get("discard_reveal", {}).get(str(seat))
    credit = 0.06 * any(c[0] == b[0] for b in state.board) + 0.03 * (sum(b[1] == c[1] for b in state.board) >= 2)
    if ADAPT and row and row[0] >= 4 and RANK[c[0]] >= 11:
        credit += 0.04 * (row[1] + 1) / (row[0] + 2)  # its share of showdowns showing the lower card
    return credit

def auction_credit(state: GameState, seat: int, mem: dict) -> float:
    """An auction winner holds three cards; a seat that always bids high wins with less."""
    if not any(e.kind == "auction" and e.seat == seat for e in state.history):
        return 0.0
    row = mem["x"].get("auction", {}).get(str(seat))
    habit = row[1] / row[0] / 10 if ADAPT and row and row[0] >= 4 else 0.0  # its average bid in big blinds
    return 0.07 - min(0.04, 0.01 * habit)

HOLDEM_MADE = ((0.05, 0.30), (0.35, 0.72), (0.62, 0.82), (0.74, 0.88), (0.84, 0.92), (0.86, 0.96),
               (0.95, 0.98), (0.99, 1.0), (1.0, 1.0))  # (low, high) strength per hand type
# Extra fields: pre (preflop percentile), pick2 (best two of three before a select), cards (hole
# counts dealt), rules/exact2 (evaluator), draw (flush, straight bonus), vpip_scale (how much
# wider a TAG plays), weak_sd (hand type counted weak at showdown), made, credit (variant reads).
BASE = {"phases": {}, "pick2": False, "cards": (2,), "rules": STD, "exact2": False, "draw": (0.16, 0.13),
        "vpip_scale": 1.0, "weak_sd": 1, "made": HOLDEM_MADE, "credit": lambda state, seat, mem: 0.0}
VARIANTS = {
    "discard_reveal": dict(BASE, detect=lambda state: state.phase == "select" or (len(state.cards) == 3 and not state.board)
                           or any(e.kind == "reveal" for e in state.history),
                           phases={"select": discard_reveal_select}, pre=preflop(3), pick2=True, cards=(2, 3),
                           made=((0.05, 0.25), (0.30, 0.66), (0.58, 0.80)) + HOLDEM_MADE[3:], credit=reveal_credit),
    "omaha": dict(BASE, detect=lambda state: len(state.cards) == 4,  # exactly two of four play
                  pre=preflop(4), cards=(4,), exact2=True, draw=(0.14, 0.12), vpip_scale=1.15, weak_sd=2,
                  made=((0.02, 0.12), (0.12, 0.40), (0.35, 0.60), (0.55, 0.78), (0.66, 0.86), (0.72, 0.95),
                        (0.88, 0.98), (0.98, 1.0), (1.0, 1.0))),
    "auction": dict(BASE, detect=lambda state: state.phase == "bid" or any(e.kind in ("bid", "auction") for e in state.history),
                    phases={"bid": auction_bid}, pre=preflop(2), cards=(2, 3), vpip_scale=1.05, credit=auction_credit),
    "short_deck": dict(BASE, detect=lambda state: False,  # nothing in the state marks it: by name only
                       pre=preflop(2, True), rules=SHORT, draw=(0.11, 0.16), vpip_scale=1.3,
                       made=((0.05, 0.25), (0.30, 0.66), (0.55, 0.78), (0.68, 0.84), (0.76, 0.88), (0.93, 0.98),
                             (0.88, 0.95), (0.99, 1.0), (1.0, 1.0))),
    "holdem": dict(BASE, detect=lambda state: True, pre=preflop(2)),  # keep last: the fallback
}
for _name, _entry in VARIANTS.items():
    _entry["strength"] = strength_of(_name)

def variant_of(state: GameState, mem: dict) -> str:
    """The kit's name if we know it, else what this table showed earlier, else its signs."""
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS:
        return name
    return mem["v"] if mem.get("v") in VARIANTS else next(k for k, v in VARIANTS.items() if v["detect"](state))


# ----------------------------------------------------------------------------- opponent model
def fresh() -> dict:
    return {"k": [0, -1], "v": "", "h": new_hand(0), "s": {}, "x": {}}

def new_hand(number: int) -> dict:
    """This hand: street, preflop raises, opener, last preflop raiser, c-bet (0 none, 1 live,
    2 closed), bet live this street, seat bitmasks already counted, river bettor, board, reveals."""
    return {"n": number, "st": 0, "nr": 0, "op": -1, "pa": -1, "cb": 0, "bt": 0, "vp": 0, "pf": 0,
            "fc": 0, "f3": 0, "fb": 0, "fo": 0, "ra": -1, "bd": [], "rv": {}, "dc": ""}

def load(memory: bytes) -> dict:
    try:
        mem = json.loads(memory) if memory and len(memory) <= 32768 else None
        ok = isinstance(mem, dict) and isinstance(mem.get("k"), list) and len(mem["k"]) == 2 and all(
            isinstance(mem.get(key), dict) for key in ("h", "s", "x")) and isinstance(mem.get("v"), str)
        return mem if ok else fresh()
    except Exception:
        return fresh()

def update(mem: dict, state: GameState, name: str) -> None:
    """Fold new events into the stats. Each event has a position (hand, index in hand); one at
    or before the stored marker was counted already, so a re-delivery changes nothing."""
    hand, pos = mem["k"]
    for event in state.events:
        hand, pos = (int(event.amount or hand + 1), 0) if event.kind == "hand" else (hand, pos + 1)
        if [hand, pos] <= mem["k"]:
            continue
        mem["k"] = [hand, pos]
        if event.kind == "hand":
            mem["h"] = new_hand(hand)
        else:
            track(mem, event, state, name)

def track(mem: dict, event, state: GameState, name: str) -> None:
    h, kind, seat, variant = mem["h"], event.kind, event.seat, VARIANTS[name]
    if kind == "board":
        h["st"], h["bt"], h["fb"] = h["st"] + 1, 0, 0
        h["bd"] += list(event.cards)
        return
    if not isinstance(seat, int) or seat == state.seat or seat < 0:
        return
    row = mem["s"].setdefault(str(seat), [0] * 16)
    bit, street = 1 << seat, h["st"]
    if kind in ("raise", "call", "fold"):  # first answer to a 3-bet, an open, a c-bet, a bet
        for live, mask, faced, folded in ((street == 0 and seat == h["op"] and h["nr"] >= 2, "f3", TBF, TBX),
                                          (street == 0 and h["nr"] == 1 and seat != h["op"], "fo", OPF, OPX),
                                          (street == 1 and h["cb"] == 1 and seat != h["pa"], "fc", CBF, CBX),
                                          (street >= 1 and h["bt"], "fb", FBF, FBX)):
            if live and not h[mask] & bit:
                h[mask] |= bit
                row[faced] += 1
                row[folded] += kind == "fold"
    if kind in ("raise", "call") and street == 0 and not h["vp"] & bit:
        h["vp"] |= bit
        row[VP] += 1
    if kind == "raise" and street == 0:
        h["nr"] += 1
        h["op"], h["pa"] = seat if h["nr"] == 1 else h["op"], seat
        row[PF] += not h["pf"] & bit
        h["pf"] |= bit
    elif kind == "raise":
        row[AG] += 1
        h["cb"] = (1 if seat == h["pa"] else 2) if street == 1 and h["cb"] == 0 else 2 if street == 1 else h["cb"]
        h["bt"], h["ra"] = 1, seat if street == 3 else h["ra"]
    elif kind == "call" and street:
        row[CL] += 1
    elif kind == "stack":
        row[H] += 1
    elif kind == "show" and len(event.cards) >= 2 and len(h["bd"]) >= 3 and len(event.cards) + len(h["bd"]) >= 5:
        weak = (best_value(event.cards, h["bd"], variant["rules"], variant["exact2"]) >> 20 & 15) <= variant["weak_sd"]
        row[SD], row[SW], row[BL] = row[SD] + 1, row[SW] + weak, row[BL] + (weak and h["ra"] == seat)
        shown = h["rv"].get(str(seat))
        if shown in event.cards and len(event.cards) == 2:  # did it turn up the lower of its two?
            stats = mem["x"].setdefault(name, {}).setdefault(str(seat), [0, 0])
            stats[0] += 1
            stats[1] += RANK[shown[0]] < RANK[event.cards[1 - event.cards.index(shown)][0]]
    elif kind == "reveal" and event.cards:
        h["rv"][str(seat)] = event.cards[0]
    elif kind == "bid":
        stats = mem["x"].setdefault(name, {}).setdefault(str(seat), [0, 0])
        stats[0] += 1
        stats[1] += int(event.amount) * 10 // max(1, state.blinds.big_blind)

def stat(mem: dict, seat, name: str) -> float:
    """Observed rate blended with the prior; the prior alone before MIN_HANDS and MIN_SAMPLE."""
    row, prior = mem["s"].get(str(seat)), PRIOR[name]
    if not ADAPT or not row or row[H] < MIN_HANDS:
        return prior
    num, den = RATES[name]
    chances = row[AG] + row[CL] if name == "agg" else row[den]
    return prior if chances < MIN_SAMPLE else (row[num] + PRIOR_W * prior) / (chances + PRIOR_W)

def shift(mem: dict, seat, name: str) -> float:
    return clamp(stat(mem, seat, name) - PRIOR[name])

def clamp(x: float) -> float:
    return max(-CAP, min(CAP, x))


# ----------------------------------------------------------------------------- 3. strategy
def decide(state: GameState, variant: dict, mem: dict) -> Action:
    info = hand_info(state)
    mine = (mem["h"]["dc"],) if mem["h"].get("dc") and mem["h"]["n"] == state.hand_number else ()
    s = variant["strength"](state, seen_cards(state) + mine)
    opps = [x.seat for x in state.seats if x.seat != state.seat and x.status in ("active", "all_in")]
    r = mix(state)
    if not state.board:
        return preflop_decide(state, variant, mem, info, s, r)
    pot, owed = state.pot, state.to_call
    s -= MULTIWAY * (len(opps) - 1)
    folds = min((shift(mem, o, "ftb") for o in opps), default=0.0)  # the stickiest opponent decides
    station = any(shift(mem, o, "ftb") <= -0.07 or shift(mem, o, "fcb") <= -0.07
                  or (shift(mem, o, "weak") >= 0.07 and shift(mem, o, "agg") < 0) for o in opps)
    shown = [c for c in my_shown(state) if c[0] in {b[0] for b in state.board} or RANK[c[0]] >= 13]
    size = SIZE_SHOWN if shown else SIZE  # the table already credits us: smaller value bets
    if not owed:
        if s >= VALUE_T - (CAP if station else max(0.0, -folds)):  # thinner value against callers
            return bet(state, SIZE_STATION if station else size)  # and bigger: a station pays any size
        if station:
            return passive(state)  # never bluff a calling station
        if len(state.board) == 3 and info["pa"] == state.seat and len(opps) <= 2:
            freq = CBET + shift(mem, min(opps, key=lambda o: shift(mem, o, "fcb")), "fcb")
        elif len(state.board) < 5 and 0.35 <= s < VALUE_T:
            freq = SEMI_BLUFF + folds
        elif len(opps) == 1:
            freq = (RIVER_BLUFF if len(state.board) == 5 else STAB) + 2 * folds + 0.05 * bool(shown)
        else:
            freq = 0.0
        return bet(state, size) if r < freq else passive(state)  # bluffs use the value size
    bettor, odds, ratio = info["bettor"], owed / (pot + owed), owed / max(1, pot - owed)
    loose = min(shift(mem, bettor, "agg"), shift(mem, bettor, "vpip"))  # a maniac is loose AND aggressive
    cheap = owed < MANIAC_CALL * my_stack(state)  # call a maniac lighter only where it cannot bust us
    read = max(0.0, shift(mem, bettor, "bluff")) + (max(0.0, loose) if cheap else 0.0)
    if ratio >= 0.7:
        read -= max(0.0, -shift(mem, bettor, "vpip"))  # a nit's big bet means it
    e = s + clamp(read) - variant["credit"](state, bettor, mem)
    if e >= RAISE_T:
        return raise_to(state, my_bet(state) + owed + max(pot, 2 * owed))
    return Action.call() if e >= icm_need(state, bettor, pot, min(owed, my_stack(state)), 0) else passive(state)

def preflop_decide(state, variant, mem, info, p, r) -> Action:
    """`p` is the share of this variant's starting hands we beat, so thresholds are frequencies.
    Ranges follow the players left to act and the table size; calls of all-ins use ICM."""
    bb, stack, owed, scale = state.blinds.big_blind, my_stack(state), state.to_call, variant["vpip_scale"]
    depth, hu = (stack + my_bet(state)) / max(1, bb), info["alive"] == 2
    if info["nr"] == 0:
        behind = info["behind"]
        freq = open_width(len(behind), hu) * scale
        if ADAPT and max((row[H] for row in mem["s"].values()), default=0) < MIN_HANDS:
            freq *= NO_READ_TIGHT  # no read yet: fewer hands
        elif behind:  # steal wider when the players left to act fold to opens
            freq += clamp(sum(shift(mem, b, "fof") for b in behind) / len(behind))
        if depth <= PUSH_BB:  # push or fold, tighter when being called costs us in ICM
            width = push_width(depth, len(behind), hu) * max(0.4, 1 - 3 * push_premium(state, behind))
            return shove(state) if p >= 1 - min(1.0, max(freq, width)) else passive(state)
        return raise_to(state, int((2.5 + info["limpers"]) * bb)) if p >= 1 - min(1.0, freq) else passive(state)
    raiser = info["pa"]
    width = info["width"] * (min(1.8, max(0.6, stat(mem, raiser, "pfr") / PRIOR["pfr"])) if ADAPT else 1.0)
    need = icm_need(state, raiser, state.pot, min(owed, stack), 0)
    odds = owed / (state.pot + owed)
    if owed >= 0.35 * stack or info["shove"]:  # an all-in: call the share of its range we beat often enough
        return Action.call() if p >= 1 - min(1.0, width * 2 ** ((CALL_EDGE - need) / 0.1)) else passive(state)
    if info["nr"] >= 2:
        if p >= 1 - FOURBET * scale:
            return raise_to(state, int(2.3 * (my_bet(state) + owed)))
        return Action.call() if p >= 1 - 2.5 * FOURBET * scale and owed < 0.25 * stack else passive(state)
    value3 = max(0.03, THREEBET * width)
    callf = CALL_OPEN * width + (0.08 if odds < 0.3 else 0.0) - 2 * (need - odds)  # ICM premium tightens flats
    if depth <= 1.5 * PUSH_BB:  # too short to flat: re-shove or fold
        return shove(state) if p >= 1 - min(1.0, width * 2 ** ((CALL_EDGE - need) / 0.1) * 0.5) else passive(state)
    three = int(3 * (my_bet(state) + owed) + (bb if info["behind"] else 0))
    if p >= 1 - value3:
        return raise_to(state, three)
    folder = shift(mem, raiser, "f3b")
    if folder > 0 and shift(mem, raiser, "pfr") > 0 and p >= 1 - (callf + 0.12) and r < 3 * folder:  # light 3-bet
        return raise_to(state, three)
    return Action.call() if p >= 1 - callf else passive(state)

def open_width(behind: int, hu: bool) -> float:
    return HU_OPEN if hu else OPEN_FREQ.get(behind, 0.13)

def push_width(depth: float, behind: int, hu: bool) -> float:
    """Share of hands to move all in first in with `depth` big blinds (push/fold charts' shape)."""
    return min(1.0, PUSH_K / (max(1.0, depth) * max(1, 1 if hu else behind) ** 0.6))

def hand_info(state: GameState) -> dict:
    """From this hand's history: preflop raises, last preflop raiser and the width of its range
    (from its seat, depth and whether it shoved), limpers, the seat whose bet we face, and the
    active seats still to act after us this street."""
    info = {"nr": 0, "pa": -1, "limpers": 0, "bettor": -1, "width": 1.0, "shove": False}
    seats = {s.seat: s for s in state.seats}
    alive = [s.seat for s in state.seats if s.status != "busted"]
    n, bb = max(state.config.players, max(seats) + 1), max(1, state.blinds.big_blind)
    info["alive"], hu = len(alive), len(alive) == 2
    blinds, street, folded = [], 0, set()
    for event in state.history:
        if event.kind == "board":
            street, info["bettor"] = street + 1, -1
        elif event.kind == "blind":
            blinds.append(event.seat)
        elif event.kind == "fold" and not street:
            folded.add(event.seat)
        elif event.kind == "raise":
            info["bettor"] = event.seat
            if not street:
                info["nr"], info["pa"] = info["nr"] + 1, event.seat
                last = blinds[-1] if blinds else state.button
                after = lambda seat: (seat - last - 1) % n  # noqa: E731
                behind = sum(1 for x in alive if x not in folded and after(x) > after(event.seat))
                raiser = seats.get(event.seat)
                depth = (raiser.stack + raiser.bet) / bb if raiser else 50.0
                info["shove"] = bool(raiser and raiser.stack == 0)
                if info["shove"] and depth <= 2 * PUSH_BB:
                    info["width"] = max(push_width(depth, behind, hu), 0.3 * info["width"] if info["nr"] > 1 else 0)
                else:  # a deep shove is a narrow range; a raise the usual one for its seat
                    info["width"] = (0.2 if info["shove"] else 1.0) * (open_width(behind, hu) if info["nr"] == 1 else 0.3 * info["width"])
        elif event.kind == "call" and not street and not info["nr"]:
            info["limpers"] += 1
    if info["bettor"] == -1 and not street and blinds:
        info["bettor"] = blinds[-1]
    last = blinds[-1] if not street and blinds else state.button  # who acts last this street
    after = lambda seat: (seat - last - 1) % n  # noqa: E731
    info["behind"] = [s.seat for s in state.seats if s.status == "active" and after(s.seat) > after(state.seat)]
    return info


# ----------------------------------------------------------------------------- 4. helpers
def seen_cards(state: GameState) -> tuple:
    """Other players' face-up cards: dead for our outs."""
    cards = {c for s in state.seats if s.seat != state.seat for c in s.shown_cards}
    return tuple(cards | {c for e in state.history if e.kind == "reveal" and e.seat != state.seat for c in e.cards})

def my_shown(state: GameState) -> tuple:
    """Our own cards the table can see."""
    mine = next((s.shown_cards for s in state.seats if s.seat == state.seat), ())
    return tuple(mine) or tuple(c for e in state.history if e.kind == "reveal" and e.seat == state.seat for c in e.cards)

def icm_equity(stacks: dict, me: int, payouts) -> float:
    """Our share of the prize points by ICM (Malmuth-Harville), first three places."""
    mine, pays = stacks.get(me, 0), [p for p in payouts if p > 0][:3] + [0, 0]
    others = [v for k, v in stacks.items() if v > 0 and k != me]
    if mine <= 0 or not pays[0]:
        return 0.0
    total = mine + sum(others)
    eq = pays[0] * mine / total
    for j, sj in enumerate(others):
        rest = total - sj
        third = sum(sk / (rest - sk) for k, sk in enumerate(others) if k != j) if pays[2] else 0.0
        eq += sj / total * mine / rest * (pays[1] + pays[2] * third)
    return eq

def icm_need(state: GameState, villain: int, pot: int, mine: int, theirs: int) -> float:
    """Equity we need to get all-in against `villain`: we risk `mine`, they add `theirs` to
    `pot`. Equals the chip odds when ICM is linear (heads-up); higher on the bubble."""
    stacks = {s.seat: s.stack for s in state.seats if s.status != "busted"}
    me = state.seat
    if villain not in stacks or villain == me or mine < ICM_MIN * stacks.get(me, 0):
        return mine / max(1, pot + mine + theirs)  # small risks: chip odds are close enough
    pays = state.config.payouts
    fold = dict(stacks)
    fold[villain] += pot
    win, lose = dict(stacks), dict(stacks)
    win[me], win[villain] = win[me] + pot + theirs, max(0, win[villain] - theirs)
    lose[me], lose[villain] = lose[me] - mine, lose[villain] + pot + mine
    ef, ew, el = icm_equity(fold, me, pays), icm_equity(win, me, pays), icm_equity(lose, me, pays)
    return (ef - el) / (ew - el) if ew > el else 1.0

def push_premium(state: GameState, behind=None) -> float:
    """How much more than chip odds we would need if the biggest stack behind called our shove."""
    others = [s for s in state.seats if s.seat != state.seat and s.status != "busted"
              and (behind is None or s.seat in behind)]
    if not others:
        return 0.0
    big = max(others, key=lambda s: s.stack + s.bet)
    risk, pot = min(my_stack(state), big.stack), state.pot
    if risk <= 0:
        return 0.0
    return max(0.0, icm_need(state, big.seat, pot, risk, risk) - risk / (pot + 2 * risk))

def mix(state: GameState) -> float:
    """A deterministic 0..1 draw per decision: mixed strategies without global state."""
    return zlib.crc32(f"{state.hand_number}|{state.seat}|{len(state.board)}|{''.join(state.cards)}".encode()) / 2**32

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
    """Raise to `total` for this round, clamped; committing 40% of our chips goes all in."""
    allowed = state.can("raise")
    if not allowed:
        return Action.call() if state.can("call") else passive(state)
    if total >= 0.4 * (my_stack(state) + my_bet(state)):
        return Action.raise_to(allowed.max_amount)
    return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, int(total))))

def bet(state: GameState, fraction: float) -> Action:
    return raise_to(state, my_bet(state) + state.to_call + int(fraction * (state.pot + state.to_call)))

def shove(state: GameState) -> Action:
    allowed = state.can("raise")
    return Action.raise_to(allowed.max_amount) if allowed else Action.call() if state.can("call") else passive(state)

def my_stack(state: GameState) -> int:
    return next(seat.stack for seat in state.seats if seat.seat == state.seat)

def my_bet(state: GameState) -> int:
    return next(seat.bet for seat in state.seats if seat.seat == state.seat)
