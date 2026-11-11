"""The Tourist: a friendly weekend player who loves seeing flops.

Source:   Claude Code (Claude Opus 5.5)
Profile:  no poker experience, 60 minutes ("The Tourist")
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction
Notes:    limps ~41-46% of hands, raises preflop ~2%, chases draws, calls down any pair on
          flop and turn but folds it to a pot-sized river bet, bets 1/3 pot only with two
          pair+, slow-plays monsters half the time, shoves pairs/aces under 8 bb. Never
          bluffs; uses no memory. All five variants ran in the mini simulator; it relies on
          no simulator guess (discard_reveal select: keep pair or two highest, show higher).
"""

from itertools import combinations, combinations_with_replacement

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}

# ----------------------------------------------------------------------------- knobs
LUCKY = 0.03            # "lucky" suited cards and pocket pairs play one notch looser
BIG_RAISE_X = 3         # a preflop bet of 3 big blinds or more is "big"
SHOVE_BB = 8            # below this many big blinds: shove any pair or ace
OPEN_RAISE_BB = 3       # the rare preflop raise
VALUE_BET = 1 / 3       # bets and raises are a third of the pot
CHASE_POT = 1.5         # calls a draw for up to 1.5x the pot (bad prices, on purpose)
WEAK_PAIR_MAX_POT = 2.0 # a weak pair still calls bets up to twice the pot
RIVER_SCARY = 0.9       # a river bet about pot-sized scares off any one-pair hand
CURIOUS_BB = 1          # checks/folds nothing, but calls a bet of one big blind "to see"
BID_BB = (1, 2)         # auction: bid 1 bb for "another card", 2 bb with a pair or an ace

# Postflop strength bands by made-hand category; the decide() thresholds read these.
NOTHING, ACE_HIGH, DRAW, WEAK_PAIR, TOP_PAIR, TWO_PAIR = 0.10, 0.15, 0.30, 0.45, 0.60, 0.75
BAND = {2: 0.75, 3: 0.82, 4: 0.88, 5: 0.90, 6: 0.94, 7: 0.98}   # two pair .. quads
SHORT_BAND = {**BAND, 5: 0.94, 6: 0.90}                          # flush beats full house


# ----------------------------------------------------------------------------- 1. wrapper
class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        try:
            variant = VARIANTS[variant_of(state)]
            if state.phase == "betting":
                action = decide(state, variant)
            else:
                # A decision phase the variant adds. No handler: the automatic choice.
                handler = variant["phases"].get(state.phase)
                action = handler(state) if handler else automatic(state)
            return legal(action, state), memory
        except Exception:
            return passive(state), memory


# ----------------------------------------------------------------------------- 2. variants
def start_score(first: str, second: str) -> float:
    """A beginner's points for two cards: high cards, pairs, an ace, suited, connected."""
    high, low = sorted((RANK[first[0]], RANK[second[0]]), reverse=True)
    if high == low:
        return 0.55 + 0.45 * (high - 2) / 12 + LUCKY  # 22 = 0.58, AA = 1.03
    score = 0.7 * (high + low) / 28 + (0.12 if high == 14 else 0.0)
    if first[1] == second[1]:
        score += 0.04 + LUCKY
    return score + (0.03 if high - low == 1 else 0.0)


CARDS = [rank + suit for rank in RANK for suit in "cdhs"]
START = {(a, b): start_score(a, b) for a in CARDS for b in CARDS if a != b}  # built at import


def pairs_of(cards):
    return [(cards[i], cards[j]) for i in range(len(cards)) for j in range(i + 1, len(cards))]


def best_start(cards) -> float:
    return max((START[pair] for pair in pairs_of(cards)), default=0.0)


def made(ranks, suits, low_ace):
    """Category of the best hand in these cards (0 high card .. 7 quads), counted the easy
    way: rank counts, five of a suit, five in a row. Straight flushes count as flushes."""
    counts = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1
    shape = sorted(counts.values(), reverse=True) + [0]
    row = set(ranks) | ({low_ace} if 14 in counts else set())
    if shape[0] >= 4:
        return 7
    if shape[0] == 3 and shape[1] >= 2:
        return 6
    if max(suits.count(suit) for suit in set(suits)) >= 5:
        return 5
    if any(all(r + i in row for i in range(5)) for r in row):
        return 4
    return 3 if shape[0] == 3 else 2 if shape[1] == 2 else 1 if shape[0] == 2 else 0


def has_draw(mine, board, low_ace) -> bool:
    """Four of a suit, or four of five in a row, using at least one of my cards."""
    suits = [card[1] for card in mine + board]
    if any(suits.count(card[1]) == 4 for card in mine):
        return True
    row = {RANK[card[0]] for card in mine + board}
    row |= {low_ace} if 14 in row else set()
    mine_ranks = {RANK[card[0]] for card in mine} | ({low_ace} if any(c[0] == "A" for c in mine) else set())
    return any(sum(r in row for r in range(start, start + 5)) >= 4
               and any(start <= r < start + 5 for r in mine_ranks) for start in range(1, 11))


def hand_score(mine, board, exact, low, band, threes=()) -> float:
    """0..1 for these private cards with the board. `exact`: Omaha's 2-from-hand, 3-from-board."""
    if exact:  # look up every 2 + 3 combination in the five-card table
        ranks, suits, table = [RANK[c[0]] for c in mine], {c[1] for c in mine}, FIVE[low]
        cat = max(5 if len(suits | three_suits) == 1 else table[tuple(sorted(ranks + three_ranks))]
                  for three_ranks, three_suits in threes)
    else:
        cards = mine + board
        cat = made([RANK[c[0]] for c in cards], [c[1] for c in cards], low - 4)
    board_ranks = [RANK[c[0]] for c in board]
    paired = [RANK[c[0]] for c in mine if board_ranks.count(RANK[c[0]]) or
              [x[0] for x in mine].count(c[0]) > 1]
    if 1 <= cat <= 3 and not paired:
        cat = 0  # the pair is all on the board: not really mine
    if cat >= 2:
        return band[cat]
    if cat == 1:
        return TOP_PAIR if max(paired) >= max(board_ranks) else WEAK_PAIR
    if len(board) < 5 and has_draw(list(mine), list(board), low - 4):
        return DRAW
    return ACE_HIGH if any(c[0] == "A" for c in mine) else NOTHING


def triples(board):
    """Every three board cards, as (their ranks, their suits)."""
    return [([RANK[c[0]] for c in three], {c[1] for c in three}) for three in combinations(board, 3)]


# Category of every five-rank combination (no flush), built once at import; key: low straight.
FIVE = {low: {five: made(list(five), list("abcde"), low - 4)
              for five in combinations_with_replacement(range(2, 15), 5) if max(map(five.count, five)) < 5}
        for low in (5, 9)}


def strength_for(groups, exact=False, low=5, band=BAND):
    """Builds a variant's `strength`: best of all private cards together ("all") or of
    every two-card group ("two"); before the flop, the best two-card start score."""
    def strength(state):
        cards = tuple(state.cards)
        if not state.board:
            return best_start(cards)
        if len(state.board) < 3:
            return NOTHING
        board = tuple(state.board)
        hands = pairs_of(cards) if groups == "two" else [cards]
        threes = triples(board) if exact else ()
        return max(hand_score(hand, board, exact, low, band, threes) for hand in hands)
    return strength


def pair_or_ace(state) -> bool:
    ranks = [card[0] for card in state.cards]
    return "A" in ranks or len(set(ranks)) < len(ranks)


def discard_reveal_select(state: GameState) -> Action:
    """Keep a pair if there is one, else the two highest cards: the board and draws are
    ignored, because "high cards win". Then proudly show the higher kept card."""
    cards = list(state.cards)
    if len(cards) != 3 or not state.can("select"):
        return automatic(state)
    ranks = [RANK[card[0]] for card in cards]
    pair = [i for i in range(3) if ranks.count(ranks[i]) >= 2]
    keep = pair[:2] if pair else sorted(range(3), key=lambda i: -ranks[i])[:2]
    discard = next(i for i in range(3) if i not in keep)
    reveal = max(keep, key=lambda i: ranks[i])
    return Action("select", cards=(discard, reveal))


def auction_bid(state: GameState) -> Action:
    """Another card is another chance: a small bid, a bit more with a pair or an ace."""
    allowed = state.can("bid")
    if allowed is None:
        return automatic(state)
    wanted = BID_BB[1 if pair_or_ace(state) else 0] * state.blinds.big_blind
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, int(wanted))))


# Extra fields read by decide(): play_at (limp/call preflop at this start score) and
# monster_at (the "very best" starting hands), set so each variant plays ~43-47% of hands.
VARIANTS = {
    "discard_reveal": {  # best two of three cards; after the select phase, the two kept
        "detect": lambda state: state.phase == "select" or (len(state.cards) == 3 and not state.board),
        "phases": {"select": discard_reveal_select}, "strength": strength_for("two"),
        "play_at": 0.59, "monster_at": 0.92},
    "omaha": {  # exactly two of the four private cards play, with exactly three board cards
        "detect": lambda state: len(state.cards) == 4,
        "phases": {}, "strength": strength_for("two", exact=True),
        "play_at": 0.65, "monster_at": 0.99},
    "auction": {  # the winner's three cards all play
        "detect": lambda state: state.phase == "bid",
        "phases": {"bid": auction_bid}, "strength": strength_for("all"),
        "play_at": 0.475, "monster_at": 0.83},
    "short_deck": {  # recognised by state.config.variant only
        "detect": lambda state: False,
        "phases": {}, "strength": strength_for("all", low=9, band=SHORT_BAND),
        "play_at": 0.59, "monster_at": 0.90},
    "holdem": {  # keep last: the fallback when nothing else is recognised
        "detect": lambda state: True,
        "phases": {}, "strength": strength_for("all"),
        "play_at": 0.475, "monster_at": 0.83},
}


def variant_of(state: GameState) -> str:
    """Name of the ruleset this table plays: the kit's name if we know it, else by its signs."""
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS:
        return name
    return next(key for key, variant in VARIANTS.items() if variant["detect"](state))


# ----------------------------------------------------------------------------- 3. strategy
def decide(state: GameState, variant: dict) -> Action:
    """The Tourist. Preflop: limp a lot, fold to big raises without a pair or an ace.
    After the flop: bet small with two pair+, call down pairs, chase draws, never bluff."""
    score = variant["strength"](state)
    big_blind = max(1, state.blinds.big_blind)
    facing = my_bet(state) + state.to_call  # the bet we are looking at this round
    pot_before = max(1, state.pot - state.to_call)
    if not state.board:
        if score < variant["play_at"]:  # near misses still call a single big blind
            short_call = state.can("call") and state.to_call <= CURIOUS_BB * big_blind
            return Action.call() if short_call and score >= variant["play_at"] - 0.05 else passive(state)
        if stack_in_big_blinds(state) < SHOVE_BB and pair_or_ace(state):
            return shove(state)  # "time is running out"
        if score >= variant["monster_at"]:
            slow_play = (state.hand_number + sum(RANK[c[0]] for c in state.cards)) % 2 == 0
            if not slow_play:
                return raise_to(state, max(OPEN_RAISE_BB * big_blind, 3 * facing))
        if facing >= BIG_RAISE_X * big_blind and not pair_or_ace(state):
            return passive(state)
        return Action.call() if state.can("call") else passive(state)

    river = len(state.board) >= 5
    bet_size = state.to_call / pot_before
    if score >= TWO_PAIR and my_bet(state) == 0:  # one small bet or raise per street
        return raise_to(state, facing + max(big_blind, int(state.pot * VALUE_BET)))
    if not state.can("call"):
        return passive(state)  # nothing to call: check (never bluff)
    if score >= TWO_PAIR:
        call = True
    elif river and score >= WEAK_PAIR:
        call = bet_size < RIVER_SCARY  # "that's a big bet... they must have it"
    elif score >= TOP_PAIR:
        call = True  # "I've got top pair!" calls the flop and turn whatever the size
    elif score >= WEAK_PAIR:
        call = bet_size <= WEAK_PAIR_MAX_POT
    elif score >= DRAW:
        call = bet_size <= CHASE_POT
    else:
        call = state.to_call <= CURIOUS_BB * big_blind and not river
    return Action.call() if call else passive(state)


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
    """Last line of defence: an action kind that is not offered, or a raise out of range."""
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


def my_bet(state: GameState) -> int:
    return next((seat.bet for seat in state.seats if seat.seat == state.seat), 0)


def stack_in_big_blinds(state: GameState) -> float:
    return my_stack(state) / max(1, state.blinds.big_blind)


def pot_odds(state: GameState) -> float:
    """Share of the final pot we must put in to call: call when our win chance is higher."""
    return state.to_call / (state.pot + state.to_call) if state.to_call else 0.0
