"""The Grinder: a tight, disciplined, chart-trained regular.

Source:   Claude Code
Profile:  The Grinder: strong, tight-aggressive. Plays about 20% of hands, mostly raising,
          position-aware opens, polarized 3-bets, board-sized c-bets, folds one pair to
          big river bets, never hero calls, push/fold at 12 BB, tightens on the bubble.
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    Preflop ranges are shares of the dealt-hand distribution (percentile tables built
          at import per variant), so the bot plays the same share of hands in every
          variant. Postflop: exact made-hand evaluation (lookup tables) plus draws.
          All five variants ran in the mini simulator. Simulator guesses are used only
          when present (revealed cards in seat.shown_cards, `auction` events).
"""

from bisect import bisect_right
from collections import Counter
from itertools import combinations, combinations_with_replacement
from random import Random
from zlib import crc32

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}

# ----------------------------------------------------------------------------- tuning knobs
OPEN_SHARE = (0.40, 0.26, 0.17, 0.13, 0.10)  # share of hands opened by seats from the button: BTN, CO, HJ, LJ, earlier
SB_OPEN_SHARE = 0.28        # small blind, folded to
BB_RAISE_LIMPS = 0.25       # big blind raises limpers with this share
SHORT_HANDED_WIDEN = 1.35   # multiply open shares with 3 or fewer players
OPEN_BB = 2.5               # open size in big blinds, +1 per limper
THREEBET_SHARE = 0.035      # value 3-bets: top 3.5% of hands
BLUFF3_FREQ = 0.45          # how often a suited small ace outside the calling range 3-bets in late position
FLAT_SHARE, BB_DEFEND_SHARE = 0.09, 0.15    # call a single raise; from the big blind
FOURBET_SHARE, CALL_3BET_SHARE = 0.015, 0.04  # facing a 3-bet: 4-bet (get it in); call
ALLIN_CALL_SHARE = 0.035    # call a preflop all-in (or a raise of 40%+ of our stack)
PUSH_BB = 12                # shove-or-fold at or below this many big blinds
PUSH_BASE, PUSH_SLOPE = 0.12, 0.025  # shove share at 12 BB, plus this per BB shorter
BUBBLE_TIGHTEN = 0.7        # every range share is multiplied by this on the bubble
CBET_DRY, CBET_WET = 0.55, 0.10   # flop c-bet frequency with air, on dry and wet boards
CBET_MADE = 0.56            # flop c-bet any hand at least this strong (top pair or better)
SIZE_DRY, SIZE_WET = 0.33, 0.66   # bet size as a share of the pot
VALUE_BET = {3: 0.60, 4: 0.68, 5: 0.74}  # strength to bet for value, by board size
CALL_BASE = {3: 0.42, 4: 0.52, 5: 0.58}  # strength to call a small bet
RIVER_BIG_BET, RIVER_BIG_CALL = 0.6, 0.80  # one pair folds to a river bet of 60% pot or more
RAISE_FOR_VALUE, COMMIT_CALL = 0.88, 0.80  # raise a bet; put half our stack or more in
ICM_EXTRA, THREAT_EXTRA = 0.08, 0.04  # more strength needed: those all-ins on the bubble;
                                     # per opponent whose public cards look strong
SEMI_BLUFF_TURN = 0.55      # how often a good draw keeps betting the turn as the aggressor


# ----------------------------------------------------------------------------- 1. wrapper
class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        saved = b""  # memory holds only the variant tag, so a replayed event changes nothing
        try:
            name = variant_of(state, memory)
            variant = VARIANTS[name]
            saved = b"" if name == "holdem" else b"GR1|" + name.encode()
            if state.phase == "betting":
                action = decide(state, variant)
            else:
                # A decision phase the variant adds. No handler: the automatic choice.
                handler = variant["phases"].get(state.phase)
                action = handler(state) if handler else automatic(state)
            return legal(action, state), saved
        except Exception:
            return passive(state), saved

def recalled(memory) -> str:
    """The variant tag an earlier decision at this table saved, or ""."""
    try:
        text = bytes(memory[:64]).decode("ascii")
    except Exception:
        return ""
    return text[4:] if text.startswith("GR1|") and text[4:] in VARIANTS else ""


# ----------------------------------------------------------------------------- evaluator
PRIME = dict(zip(range(2, 15), (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)))
CARD = {r + s: (PRIME[RANK[r]], s, RANK[r]) for r in RANK for s in "cdhs"}  # (prime, suit, rank)

def rank_value(ranks, flush, low, flush_over_full):
    """Five ranks as an int that compares correctly: category << 20, then the ranks."""
    ranks = sorted(ranks, reverse=True)
    groups = sorted(Counter(ranks).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape, order = tuple(c for _, c in groups), [r for r, _ in groups]
    top = 0
    if len(groups) == 5 and ranks[0] - ranks[4] == 4:
        top = ranks[0]
    elif len(groups) == 5 and ranks[0] == 14 and ranks[1] == low and ranks[1] - ranks[4] == 3:
        top = low  # the ace plays low: A-2-3-4-5, or A-6-7-8-9 in short deck
    cat = {(4, 1): 7, (3, 2): 5 if flush_over_full else 6, (3, 1, 1): 3, (2, 2, 1): 2, (2, 1, 1, 1): 1}.get(shape, 0)
    if top and flush:
        cat, order = 8, [top]
    elif flush:
        cat = 6 if flush_over_full else 5
    elif top and cat == 0:
        cat, order = 4, [top]
    return cat << 20 | sum(r << (16 - 4 * i) for i, r in enumerate(order))

def build_tables(low, flush_over_full):
    """({prime product: value} without a flush, the same with one) for all five-card hands."""
    plain, suited = {}, {}
    for ranks in combinations_with_replacement(range(2, 15), 5):
        if max(Counter(ranks).values()) <= 4:
            key = PRIME[ranks[0]] * PRIME[ranks[1]] * PRIME[ranks[2]] * PRIME[ranks[3]] * PRIME[ranks[4]]
            plain[key] = rank_value(ranks, False, low, flush_over_full)
            if len(set(ranks)) == 5:
                suited[key] = rank_value(ranks, True, low, flush_over_full)
    return plain, suited

STANDARD, SHORT = build_tables(5, False), build_tables(9, True)

def value5(five, tables):
    a, b, c, d, e = five
    flush = a[1] == b[1] == c[1] == d[1] == e[1]
    return tables[flush][a[0] * b[0] * c[0] * d[0] * e[0]]

def best_value(groups, board, exact, tables):
    """Best hand: exactly two private cards and three board cards (`exact`), or the best
    five of each group of private cards with the board."""
    if exact:
        return max(value5(group + three, tables) for group in groups for three in combinations(board, 3))
    return max(value5(five, tables) for group in groups for five in combinations(group + board, 5))


# ----------------------------------------------------------------------------- scoring
def parse(cards):
    return tuple(CARD[c] for c in cards)

def groups_of(cards, rules):
    """The sets of private cards that may play together."""
    return list(combinations(cards, 2)) if rules["exact"] or (rules["pick_two"] and len(cards) > 2) else [cards]

def pair_points(hi, lo, suited, rules):
    """Chen-style score of two cards; `rules` sets the suited and connected bonuses."""
    points = {14: 10, 13: 8, 12: 7, 11: 6}.get(hi, hi / 2)
    if hi == lo:
        return max(5, 2 * points)
    gap = hi - lo - 1
    if hi == 14 and lo <= rules["low"]:  # the ace also connects low
        gap = min(gap, rules["low"] - lo)
    points -= (0, 1, 2, 4, 5)[min(gap, 4)] - (rules["connect"] if gap <= 1 and hi < 12 else 0)
    return points + (rules["suited"] if suited else 0)

def raw_preflop(cards, rules):
    """Raw score of all private cards before the flop, for any number of cards."""
    scores = sorted((pair_points(max(a[2], b[2]), min(a[2], b[2]), a[1] == b[1], rules)
                     for a, b in combinations(cards, 2)), reverse=True)
    if len(cards) == 2:
        return scores[0]
    if rules["exact"]:  # four cards, two play: reward hands where several pairs work together
        suits, ranks = Counter(c[1] for c in cards).values(), Counter(c[2] for c in cards).values()
        return (scores[0] + 0.5 * scores[1] + 0.25 * scores[2] + 1.5 * (sorted(suits) == [2, 2])
                - 1.5 * (max(suits) >= 3) - 3 * (max(ranks) >= 3))
    return scores[0] + 0.1 * scores[1]

def percentile_table(rules):
    """Sorted raw scores of every dealt hand (a fixed sample of 12,000 for four cards)."""
    deck = [card for card in CARD.values() if card[2] >= rules["min_rank"]]
    if rules["cards"] <= 3:
        hands = combinations(deck, rules["cards"])
    else:
        draw = Random(20261111)
        hands = (tuple(draw.sample(deck, rules["cards"])) for _ in range(12000))
    return sorted(raw_preflop(hand, rules) for hand in hands)

def hand_strength(state, rules):
    """0..1. Before the flop: the share of dealt hands ours beats. After: made-hand score."""
    cards, board = parse(state.cards), parse(state.board)
    if not board:
        table = rules["pre"] if len(cards) == rules["cards"] else PRE_TWO
        return bisect_right(table, raw_preflop(cards, rules)) / len(table)
    return made_score(groups_of(cards, rules), board, rules)

def made_score(groups, board, rules):
    """Score of our best hand: the category's base from `rules["made"]`, then where a pair
    ranks against the board, and less when the board makes the hand or shows a flush."""
    if not groups or len(board) < 3:
        return 0.0
    value = best_value(groups, board, rules["exact"], rules["tables"])
    cat, made = value >> 20, rules["made"]
    board_ranks = sorted((c[2] for c in board), reverse=True)
    counts = Counter(board_ranks)
    board_cat = 3 if max(counts.values()) >= 3 else min(2, sum(v == 2 for v in counts.values()))
    hole = [c[2] for g in groups for c in g]
    if len(board) == 5 and not rules["exact"] and value == value5(board, rules["tables"]):
        return made[0]  # we play the board
    if cat <= board_cat:
        return made[0] + 0.01 * max(hole)  # the board's hand with our kicker
    score = made[cat]
    if cat == 1 or (cat == 2 and board_cat == 1):  # one pair made with a private card
        pocket = [a[2] for g in groups for a, b in combinations(g, 2) if a[2] == b[2]]
        rank = max([r for r in hole if counts[r] == 1] + pocket, default=0)
        top, second = board_ranks[0], sorted(set(board_ranks))[-2]
        score = made[1] + (0.25 if rank > top else 0.15 + 0.004 * max(hole) if rank == top
                           else 0.0 if rank >= second else -0.1)
    elif cat == 3 and board_cat == 1:
        score -= 0.06  # trips with a board pair: kicker trouble
    if Counter(c[1] for c in board).most_common(1)[0][1] >= 3 and cat not in rules["beats_flush"]:
        score -= 0.10  # a flush is possible and we have none
    return max(0.0, min(1.0, score))

def draw_equity(cards, board, rules):
    """Rough chance a flush or straight draw completes by the river (0 on the river)."""
    if len(board) not in (3, 4):
        return 0.0
    best, need_mine = 0, 2 if rules["exact"] else 1
    for group in groups_of(cards, rules):
        outs = 0
        for suit in "cdhs":
            mine, shown = sum(c[1] == suit for c in group), sum(c[1] == suit for c in board)
            if mine >= need_mine and mine + shown == 4 and (shown >= 2 or not rules["exact"]):
                outs += rules["suit_size"] - 4
        ranks = {c[2] for c in group + board}
        hole = {c[2] for c in group}
        ranks |= {1} & {r - 13 for r in ranks}  # an ace is also a 1
        hole |= {1} & {r - 13 for r in hole}
        completing = {[r for r in w if r not in ranks][0] % 13 for w in rules["windows"]
                      if sum(r not in ranks for r in w) == 1 and hole & set(w)}
        best = max(best, min(15, outs + 4 * len(completing)))
    return best * (0.04 if len(board) == 3 else 0.02)

def windows(low):
    """Five-rank straight windows; the ace is 1 in the lowest (A-2-3-4-5 or A-6-7-8-9)."""
    return [[1] + list(range(low - 3, low + 1))] + [list(range(t - 4, t + 1)) for t in range(max(6, low + 1), 15)]


# ----------------------------------------------------------------------------- 2. variants
def discard_reveal_select(state: GameState) -> Action:
    """Keep the two cards with the best made hand plus draw equity on this flop. Show the
    kept card that tells least: a card that pairs the board or carries a suit the board
    shows twice names our hand, and a high card narrows it more than a low one."""
    rules = VARIANTS["discard_reveal"]
    if len(state.cards) != 3:
        return automatic(state)
    cards, board = parse(state.cards), parse(state.board)

    def worth(keep):
        two = (cards[keep[0]], cards[keep[1]])
        if len(board) < 3:
            return raw_preflop(two, rules)
        return made_score([two], board, rules) + 0.8 * draw_equity(two, board, rules)

    def telling(i):
        return 3 * (cards[i][2] in {c[2] for c in board}) + 2 * (sum(c[1] == cards[i][1] for c in board) >= 2) \
            + cards[i][2] / 15

    keep = max(combinations(range(3), 2), key=worth)
    discard = next(i for i in range(3) if i not in keep)
    return Action("select", cards=(discard, min(keep, key=telling)))

def auction_bid(state: GameState) -> Action:
    """Second-price auction: bid about what the card adds. Draws gain most; a strong made
    hand bids a little to deny the card; nothing else bids. Never a big part of the stack."""
    allowed, rules = state.can("bid"), VARIANTS["auction"]
    if allowed is None:
        return automatic(state)
    draw, made = rules["draw"](state), rules["strength"](state)
    share = 0.35 * draw if draw >= 0.15 else 0.06 if made >= 0.6 else 0.0
    wanted = min(share * state.pot, 0.08 * me(state).stack * (0.5 if on_bubble(state) else 1))
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, int(wanted))))

def shown_threats(state: GameState) -> int:
    """discard_reveal: live opponents whose face-up card pairs the board or tops it."""
    board = [RANK[c[0]] for c in state.board]
    return sum(any(c[:1] in RANK and board and (RANK[c[0]] in board or RANK[c[0]] > max(board))
                   for c in seat.shown_cards) for seat in live_opponents(state))

def auction_threats(state: GameState) -> int:
    """auction: live opponents who bought a third card this hand."""
    live = {seat.seat for seat in live_opponents(state)}
    return sum(1 for e in state.history if e.kind == "auction" and e.seat in live)

CHART = dict(suited=2, connect=1, low=5, min_rank=2, exact=False, pick_two=False, cards=2, tables=STANDARD,
             made=(0.10, 0.42, 0.72, 0.84, 0.88, 0.92, 0.96, 0.99, 1.0),  # by hand category code
             beats_flush=(5, 6, 7, 8), suit_size=13, windows=windows(5), open_scale=1.0, cbet_tax=0.0)

def entry(detect, phases, threats=lambda state: 0, **changes):
    """A VARIANTS entry: the hold'em chart with `changes`, plus its preflop table."""
    rules = dict(CHART, **changes)
    rules.update(detect=detect, phases=phases, threats=threats, pre=percentile_table(rules),
                 strength=lambda state: hand_strength(state, rules),
                 draw=lambda state: draw_equity(parse(state.cards), parse(state.board), rules))
    return rules

# Extra fields read by decide: open_scale (opening ranges) and cbet_tax (strength a flop
# c-bet needs), tuned so the bot opens ~20% and c-bets ~65% dry in every variant.
VARIANTS = {
    "discard_reveal": entry(lambda s: s.phase == "select" or (len(s.cards) == 3 and not s.board),
                            {"select": discard_reveal_select}, shown_threats, cards=3, pick_two=True,
                            open_scale=1.08, cbet_tax=0.12),
    "omaha": entry(lambda s: len(s.cards) == 4, {}, cards=4, exact=True, open_scale=1.0, cbet_tax=-0.11,
                   made=(0.05, 0.22, 0.45, 0.62, 0.76, 0.85, 0.93, 0.98, 1.0)),
    "auction": entry(lambda s: s.phase == "bid", {"bid": auction_bid}, auction_threats),
    "short_deck": entry(lambda s: False, {}, suited=1, connect=2, low=9, min_rank=6, tables=SHORT,
                        beats_flush=(6, 7, 8), suit_size=9, windows=windows(9),
                        made=(0.10, 0.40, 0.68, 0.80, 0.84, 0.92, 0.95, 0.99, 1.0)),
    "holdem": entry(lambda s: True, {}),  # keep last: the fallback
}
PRE_TWO = VARIANTS["holdem"]["pre"]

def variant_of(state: GameState, memory: bytes = b"") -> str:
    """The kit's name if we know it, else the signs in the state, else a sign seen earlier
    at this table (discard_reveal looks like hold'em after the select phase)."""
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS:
        return name
    seen = next(key for key, variant in VARIANTS.items() if variant["detect"](state))
    return (recalled(memory) or seen) if seen == "holdem" else seen


# ----------------------------------------------------------------------------- 3. strategy
def decide(state: GameState, variant: dict) -> Action:
    strength = variant["strength"](state)
    return postflop(state, variant, strength) if state.board else preflop(state, variant, strength)

def preflop(state, variant, share_beaten):
    bb, stack = state.blinds.big_blind, me(state).stack + me(state).bet
    raises = sum(1 for e in state.history if e.kind == "raise")
    limpers = sum(1 for e in state.history if e.kind == "call")
    tight = BUBBLE_TIGHTEN if on_bubble(state) else 1.0
    position, players = seats_from_button(state)
    need = lambda share: share_beaten >= 1 - share * tight  # noqa: E731
    if stack <= PUSH_BB * bb:  # shove or fold
        late = position <= 1 or position == players - 1
        share = PUSH_BASE + PUSH_SLOPE * (PUSH_BB - stack / bb) + 0.1 * late if not raises \
            else ALLIN_CALL_SHARE + 0.02 * (state.to_call < stack / 2)
        return sized(state, None) if need(share) else passive(state)
    if not raises:
        share = (SB_OPEN_SHARE if position == players - 1 else BB_RAISE_LIMPS * (limpers > 0)
                 if position == players - 2 else OPEN_SHARE[min(position, len(OPEN_SHARE) - 1)])
        share *= variant["open_scale"] * (SHORT_HANDED_WIDEN if players <= 3 else 1.0)
        return sized(state, (OPEN_BB + limpers) * bb) if need(share) else passive(state)
    high = max(seat.bet for seat in state.seats)
    if state.to_call >= 0.4 * stack:
        return sized(state, None) if need(ALLIN_CALL_SHARE) else passive(state)  # no crumbs left behind
    if raises == 1:
        bluff = (suited_small_ace(state.cards) and position <= 2 and tight == 1.0
                 and roll(state) < BLUFF3_FREQ and not need(FLAT_SHARE))
        if need(THREEBET_SHARE) or bluff:
            return sized(state, high * (3 if position <= 2 else 3.6))
        return Action.call() if need(BB_DEFEND_SHARE if position == players - 2 else FLAT_SHARE) else passive(state)
    if need(FOURBET_SHARE):
        return sized(state, high * 2.3)
    return Action.call() if need(CALL_3BET_SHARE) and state.to_call <= 0.25 * stack else passive(state)

def postflop(state, variant, strength):
    street, pot = len(state.board), max(1, state.pot)
    draw = variant["draw"](state)
    opponents = len(live_opponents(state))
    kinds = [e.kind for e in state.history]
    before_flop = state.history[: kinds.index("board")] if "board" in kinds else ()
    aggressor = [e.seat for e in before_flop if e.kind == "raise"][-1:] == [state.seat]
    wet = is_wet(state.board)
    size = SIZE_WET if wet else SIZE_DRY
    if state.can("check"):
        if strength >= VALUE_BET[street] + 0.03 * (opponents - 1):
            return sized(state, pot * (size if street == 3 else max(size, 0.5)))
        if street == 3 and aggressor and opponents <= 2:
            if (draw >= 0.3 or strength >= CBET_MADE + 0.06 * wet + variant["cbet_tax"]
                    or roll(state) < (CBET_WET if wet else CBET_DRY)):
                return sized(state, pot * size)
        if street == 4 and aggressor and draw >= 0.16 and roll(state) < SEMI_BLUFF_TURN:
            return sized(state, pot * SIZE_WET)
        return passive(state)  # give up without a hand or a good draw
    bet = state.to_call / max(1, pot - state.to_call)
    odds = state.to_call / (pot + state.to_call)
    need = CALL_BASE[street] + 0.12 * min(bet, 1.5) + 0.04 * (opponents - 1)
    need += THREAT_EXTRA * variant["threats"](state)
    if street == 5 and bet >= RIVER_BIG_BET:
        need = max(need, RIVER_BIG_CALL)  # one pair folds to a big river bet: no hero calls
    committing = state.to_call >= 0.5 * me(state).stack
    if committing:
        need = max(need, COMMIT_CALL + (ICM_EXTRA if on_bubble(state) else 0.0))
    if strength >= max(RAISE_FOR_VALUE, need) and state.can("raise"):
        return sized(state, 3 * max(s.bet for s in state.seats))
    if strength >= need or (street < 5 and not committing and draw >= odds + 0.03):
        return Action.call()
    return passive(state)

def is_wet(board) -> bool:
    """A two-tone or connected flop (three ranks within a five-rank window)."""
    ranks = sorted({RANK[c[0]] for c in board[:3]})
    return max(Counter(c[1] for c in board[:3]).values()) >= 2 or (len(ranks) == 3 and ranks[2] - ranks[0] <= 4)

def live_opponents(state):
    return [s for s in state.seats if s.seat != state.seat and s.status in ("active", "all_in")]

def suited_small_ace(cards) -> bool:
    return any(a[0] == "A" and b[1] == a[1] and b[0] in "2345" for a in cards for b in cards if a != b)

def roll(state) -> float:
    """A repeatable 0..1 draw from the hand, so a replayed decision makes the same choice."""
    return crc32(f"{state.hand_number}|{state.seat}|{''.join(state.cards)}|{len(state.board)}".encode()) % 1000 / 1000

def seats_from_button(state) -> tuple[int, int]:
    """(0 = button, 1 = cutoff, ..., players - 2 = big blind, players - 1 = small blind; players)."""
    alive = [s.seat for s in sorted(state.seats, key=lambda s: s.seat) if s.status != "busted"]
    if state.button not in alive or state.seat not in alive:
        return 3, max(len(alive), 4)
    return (alive.index(state.button) - alive.index(state.seat)) % len(alive), len(alive)

def on_bubble(state) -> bool:
    return state.players_remaining == sum(1 for p in state.config.payouts if p > 0) + 1


# ----------------------------------------------------------------------------- 4. helpers
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
    if action.kind in ("raise", "bid"):
        return Action(action.kind, max(allowed.min_amount, min(allowed.max_amount, int(action.amount))))
    return action

def sized(state: GameState, total) -> Action:
    """Raise to `total` for this round, clamped; all in when `total` is None or 45%+ of our
    stack. With no raise offered, call (or check)."""
    allowed, seat = state.can("raise"), me(state)
    if allowed is None:
        return Action.call() if state.can("call") else passive(state)
    if total is None or total >= 0.45 * (seat.stack + seat.bet):
        return Action.raise_to(allowed.max_amount)
    return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, int(total))))

def me(state: GameState):
    return next(seat for seat in state.seats if seat.seat == state.seat)
