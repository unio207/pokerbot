"""Strategy bot for the pokerbot sit-and-go, in the zoo template's layout. One file.

Source:   strategies branch (VedaantK, commit fa9590f); moved into the zoo template layout
          and given its variant entries by Claude (Fable 5.2)
Profile:  chart_nash. A. Position charts when deep, Nash-style push/fold when short, pot odds postflop.
Variants: all, as of 2026-11-11: holdem, discard_reveal, short_deck, omaha, auction, irish
Notes:    Seven profiles share this source; `ACTIVE` below picks one and tools/build.py
          stamps a copy per profile into bots/<name>/agent.py. Hold'em play is the tuned
          original. The other variants' numbers are estimates measured on our own mini
          simulator (tools/gen_variant_tables.py), not on the organizers' kit.

How this file is organised (read zoo/_template/README.md before changing it):
  1. act()      crash-proof wrapper. Never changes between variants.
  2. VARIANTS   one entry per ruleset in zoo/variants/. Everything that depends on the
                variant lives in an entry: how to recognise it, how to answer its extra
                decision phases, and how to score our private cards.
  3. decide()   the betting strategy, written once. PROFILES holds every tuning knob, one
                dict per strategy; then preflop, postflop, ICM and the per-seat tracker.
  4. helpers    legal actions, table reading, hand evaluation and the embedded tables.

To change a strategy, edit a knob in PROFILES or switch ACTIVE, then run tools/build.py.

Rules every bot must follow (same as the competition):
- One file. `class Agent` with `act(state, memory) -> (Action, bytes)`.
- No state on `self` or in globals between calls: the platform runs several copies and
  any copy may answer any turn. Use the `memory` bytes (empty at the start of every
  table, cut at 64 KB, keep it small, parse it defensively).
- Return within 1 ms. An exception, timeout or illegal action is played as check/fold
  (in a variant's own phase: the platform's automatic choice).
- A raise outside [min_amount, max_amount] is illegal; it is NOT clamped for you, and a
  float amount is rounded down. Use whole numbers and clamp them yourself.
- Check and call are never both offered, and fold is not offered when checking is free.
- Imports: standard library, poker_agent_sdk, and only NumPy, SciPy, pandas,
  scikit-learn, PyTorch (CPU), LightGBM, XGBoost, ONNX Runtime, Numba, eval7.
  Never poker_engine or pokerkit. No network, files or subprocesses.
- Read table settings from `state.config` (blinds, payouts, players); payouts can differ
  per table, so do not assume 50/30/20.

Nothing here is random: the same state and memory always give the same action.
"""

import functools

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

ACTIVE = "chart_nash"
DEBUG_RAISE = False  # tools/fuzz.py sets this so internal errors surface instead of folding


# ----------------------------------------------------------------------------- 1. wrapper
class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if DEBUG_RAISE:
            tracker, memory = _track(state, memory)
            return legal(route(state, tracker), state), memory
        if type(memory) is not bytes:
            memory = b""
        tracker = None
        try:
            tracker, memory = _track(state, memory)
        except Exception:
            tracker, memory = None, b""  # lose the notes, keep playing
        try:
            return legal(route(state, tracker), state), memory
        except Exception:
            try:
                return passive(state), memory
            except Exception:
                return Action.check(), memory


def route(state: GameState, tracker) -> Action:
    """Find the variant, then the betting strategy or the variant's handler for this phase."""
    variant = VARIANTS[variant_of(state)]
    if state.phase == "betting":
        return decide(state, variant, tracker)
    # A decision phase the variant adds. No handler: the automatic choice.
    handler = variant["phases"].get(state.phase)
    return handler(state) if handler else automatic(state)


# ----------------------------------------------------------------------------- 2. variants
# Each ruleset in zoo/variants/<name>.md gets one entry in VARIANTS under the same name:
#   detect    state -> bool. True when this table plays the variant. Checked in order,
#             after an exact match on state.config.variant; "holdem" is the fallback.
#   phases    {phase name: handler(state) -> Action} for the variant's extra phases.
#   strength  state -> float in 0..1, how good our private cards are right now.
# and two extra fields the strategy reads, which `strength` is built from:
#   preflop   state -> (equity vs one random hand, percentile where 0.0 is the best hand)
#   postflop  (state, facing a bet?) -> (strength 0..1 as rough equity, has a strong draw)
# These functions are the only code that knows how many cards we hold, which ones play
# and how hands rank. To support a new variant: read its ruleset, write its functions, add
# its entry. Every function falls back to the hold'em one when the cards are not what its
# ruleset says, so a wrong guess about the kit costs accuracy, never an exception.


def holdem_preflop(state: GameState) -> tuple[float, float]:
    """Two private cards: the embedded 169-class table. Any other count takes the best
    two-card combination, which is only a first guess for a variant we have no entry for."""
    cards = state.cards
    if len(cards) < 2:
        return 0.0, 1.0  # nothing to score: the worst hand
    if len(cards) == 2:
        key = _class_key(cards[0], cards[1])
    else:
        key = max(
            (_class_key(a, b) for i, a in enumerate(cards) for b in cards[i + 1 :]),
            key=_EQUITY.__getitem__,
        )
    return _EQUITY[key], _PERCENTILE[key]


def holdem_postflop(state: GameState, facing: bool) -> tuple[float, bool]:
    """Best five of two private cards and the board (best two-card combination otherwise)."""
    cards = state.cards
    if len(cards) == 2:
        return _pair_strength(cards, state.board, facing)
    best, draw = 0.0, False
    for i, a in enumerate(cards):
        for b in cards[i + 1 :]:
            best = max(best, _made_strength((a, b), state.board))
            draw = draw or _has_draw((a, b), state.board)
    return best, draw


def _pair_strength(hole, board, facing: bool) -> tuple[float, bool]:
    """Two private cards on one board: the measured equity bucket, else the rough estimate."""
    if P["post"] == "bucket":
        key, draw = _bucket(hole, board)
        value = (_BUCKET_T if facing else _BUCKET_R).get(key)
        if value is not None:
            return value, draw
    return _made_strength(hole, board), _has_draw(hole, board)


def double_board_strength(hole, boards, facing: bool) -> tuple[float, bool]:
    """Two private cards scored on each board and averaged: each board pays half the pot,
    so the mean of the two equities is the share of the pot we expect."""
    scores = [_pair_strength(hole, board, facing) for board in boards]
    return sum(score for score, _ in scores) / len(scores), any(draw for _, draw in scores)


def double_board_keep(cards, boards, facing: bool = False) -> tuple[float, bool, tuple]:
    """(strength, draw, the two indices kept): the pair of our cards with the most equity
    summed over the boards. The same pair has to play on every board."""
    best = (-1.0, False, (0, 1))
    for i in range(len(cards) - 1):
        for j in range(i + 1, len(cards)):
            score, draw = double_board_strength((cards[i], cards[j]), boards, facing)
            if score > best[0]:
                best = (score, draw, (i, j))
    return best


def _boards(state: GameState) -> list:
    """Both boards of a double-board table (RULES.md: state.variant["boards"]), once dealt."""
    variant = getattr(state, "variant", None)
    boards = variant.get("boards") if isinstance(variant, dict) else None
    if not isinstance(boards, (list, tuple)) or len(boards) != 2:
        return []
    return [tuple(board) for board in boards if len(board) >= 3]


_ONE_BOARD = 0.0  # best single-board strength of the pair we keep; set by pittsburgh_postflop


def pittsburgh_postflop(state: GameState, facing: bool) -> tuple[float, bool]:
    """Kit RULES.md (double_board_turn_discard): three cards until the discard after the
    turn, two on the river, two boards. Before the discard we are worth the pair we would keep."""
    cards, boards = state.cards, _boards(state)
    global _ONE_BOARD
    if len(boards) != 2 or len(cards) not in (2, 3):
        return holdem_postflop(state, facing)
    if len(cards) == 2:
        strength, draw, keep = *double_board_strength(cards, boards, facing), (0, 1)
    else:
        strength, draw, keep = double_board_keep(cards, boards, facing)
    pair = (cards[keep[0]], cards[keep[1]])
    _ONE_BOARD = max(_pair_strength(pair, board, facing)[0] for board in boards)
    return strength, draw


def pittsburgh_discard(state: GameState) -> Action:
    """Throw away one of three cards: `cards=(index,)` of the card that is not kept."""
    cards, boards = state.cards, _boards(state)
    if len(cards) != 3 or not boards:
        return automatic(state)
    keep = double_board_keep(cards, boards)[2]
    return Action("discard", cards=(3 - keep[0] - keep[1],))


# Heads-up pot share of three cards on two boards, by class (Codex's fit over 300,000 kit deals,
# checked here on eight hands at 12,000 deals each: within 0.013). The best two cards alone
# overrate pairs by 8 to 12 points and weak aces by 10. Marks: that share at each twentieth of
# all 22,100 hands, best first.
_PITT_MARKS = (0.78, 0.6719, 0.5916, 0.568, 0.552, 0.5399, 0.5284, 0.5189, 0.5096, 0.5003, 0.4923, 0.4836, 0.4739, 0.4641, 0.4552, 0.4431, 0.4319, 0.4207, 0.4048, 0.3886, 0.3265)


def _three_card_equity(cards) -> float:
    pairs = [_EQUITY[_class_key(a, b)] for i, a in enumerate(cards) for b in cards[i + 1 :]]
    ranks = [card[0] for card in cards]
    distinct = len(set(ranks))
    if distinct == 3:
        equity = 0.05890 + 0.10728 * max(pairs) + 0.74613 * sum(pairs) / 3
    elif distinct == 2:
        i, j = [index for index, rank in enumerate(ranks) if ranks.count(rank) == 2]
        pocket = _EQUITY[_class_key(cards[i], cards[j])]
        other = max(_EQUITY[_class_key(cards[k], cards[3 - i - j])] for k in (i, j))
        equity = -0.15478 + 0.95933 * pocket + 0.17325 * other
    else:
        equity = -0.29592 + 1.23494 * pairs[0]
    return min(1.0, max(0.0, equity))


def pittsburgh_preflop(state: GameState) -> tuple[float, float]:
    cards = state.cards
    if len(cards) != 3:
        return holdem_preflop(state)
    equity = _three_card_equity(cards)
    return equity, _percentile_of(equity, _PITT_MARKS)


def discard_reveal_preflop(state: GameState) -> tuple[float, float]:
    """zoo/variants/discard_reveal.md: three cards, worth their best two-card combination.
    Everyone holds three, so the same two cards rank lower than in hold'em."""
    cards = state.cards
    if len(cards) != 3:
        return holdem_preflop(state)
    score = max(_EQUITY[_class_key(a, b)] for i, a in enumerate(cards) for b in cards[i + 1 :])
    return _DISCARD_FIT[0] + _DISCARD_FIT[1] * score, _percentile_of(score, _DISCARD_MARKS)


def discard_reveal_select(state: GameState) -> Action:
    """Discard one of three cards and expose one of the two kept: keep the pair that
    plays best with the board (draws included), expose the lower kept card."""
    cards = state.cards
    if len(cards) != 3:
        return automatic(state)
    best, keep = -1.0, (0, 1)
    for pair in ((0, 1), (0, 2), (1, 2)):
        kept = (cards[pair[0]], cards[pair[1]])
        score = _made_strength(kept, state.board) if state.board else _preflop_equity(kept)
        if score > best:
            best, keep = score, pair
    discard = 3 - keep[0] - keep[1]
    reveal = min(keep, key=lambda index: _RANK[cards[index][0]])
    return Action("select", cards=(discard, reveal))


def omaha_preflop(state: GameState) -> tuple[float, float]:
    """zoo/variants/omaha.md: four cards scored together as the mean of their six
    two-card combinations, which rewards high cards, pairs and suits that work together."""
    cards = state.cards
    if len(cards) != 4:
        return holdem_preflop(state)
    score = sum(_EQUITY[_class_key(a, b)] for i, a in enumerate(cards) for b in cards[i + 1 :]) / 6
    return _OMAHA_FIT[0] + _OMAHA_FIT[1] * score, _percentile_of(score, _OMAHA_MARKS)


def omaha_postflop(state: GameState, facing: bool) -> tuple[float, bool]:
    """Best hand from exactly two private cards and exactly three board cards. Strength
    is the measured equity of that hand category on this street, far below hold'em's."""
    if len(state.cards) != 4 or not 3 <= len(state.board) <= 5:
        return holdem_postflop(state, facing)
    hole = [(_RANK[card[0]], card[1]) for card in state.cards]
    board = [(_RANK[card[0]], card[1]) for card in state.board]
    best = (-1,)
    for i in range(3):
        for j in range(i + 1, 4):
            for a, b, c in _TRIPLES[len(board)]:
                rank = _five((hole[i], hole[j], board[a], board[b], board[c]))
                if rank > best:
                    best = rank
    left = 5 - len(board)
    strength = _OMAHA_MADE[len(board) - 3][best[0]]
    flush_draw = left > 0 and best[0] < 5 and any(
        sum(card[1] == suit for card in hole) >= 2 and sum(card[1] == suit for card in board) == 2
        for suit in "cdhs"
    )
    return min(strength, 0.97), flush_draw


def irish_preflop(state: GameState) -> tuple[float, float]:
    """zoo/variants/irish.md: four cards, two of which we keep once the flop is known.
    Scored as the average of their best two-card combination and the mean of all six."""
    cards = state.cards
    if len(cards) != 4:
        return holdem_preflop(state)
    pairs = [_EQUITY[_class_key(a, b)] for i, a in enumerate(cards) for b in cards[i + 1 :]]
    score = (max(pairs) + sum(pairs) / 6) / 2
    return _IRISH_FIT[0] + _IRISH_FIT[1] * score, _percentile_of(score, _IRISH_MARKS)


def irish_discard(state: GameState) -> Action:
    """Throw away two of four cards: keep the pair that plays best with the board."""
    cards = state.cards
    if len(cards) != 4:
        return automatic(state)
    best, keep = -1.0, (0, 1)
    for i in range(3):
        for j in range(i + 1, 4):
            kept = (cards[i], cards[j])
            score = _made_strength(kept, state.board) if state.board else _preflop_equity(kept)
            if score > best:
                best, keep = score, (i, j)
    return Action("discard", cards=tuple(index for index in range(4) if index not in keep))


def _five(cards) -> tuple:
    """Exactly five (rank, suit) cards as a tuple that compares correctly. Full deck."""
    ranks = sorted((card[0] for card in cards), reverse=True)
    a, b, c, d, e = ranks
    if a != b and b != c and c != d and d != e:
        suit = cards[0][1]
        flush = cards[1][1] == suit and cards[2][1] == suit and cards[3][1] == suit and cards[4][1] == suit
        high = a if a - e == 4 else 5 if a == 14 and b == 5 else 0
        if high:
            return (8 if flush else 4, high)
        return (5 if flush else 0, a, b, c, d, e)
    counts: dict[int, int] = {}
    for rank in ranks:
        counts[rank] = counts.get(rank, 0) + 1
    groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    top = groups[0][1]
    category = 7 if top == 4 else (6 if len(groups) == 2 else 3) if top == 3 else 2 if len(groups) == 3 else 1
    return (category, *[rank for rank, _ in groups])


_TRIPLES = {n: tuple((a, b, c) for a in range(n) for b in range(a + 1, n) for c in range(b + 1, n))
            for n in (3, 4, 5)}  # fmt: skip


def short_deck_preflop(state: GameState) -> tuple[float, float]:
    """zoo/variants/short_deck.md: its own table for the 81 classes of a 36-card deck."""
    cards = state.cards
    key = _class_key(cards[0], cards[1]) if len(cards) == 2 else None
    if key not in _SHORT_EQUITY:
        return holdem_preflop(state)
    return _SHORT_EQUITY[key], _SHORT_PERCENTILE[key]


def short_deck_postflop(state: GameState, facing: bool) -> tuple[float, bool]:
    """Flush above full house, ace low only in A-6-7-8-9, and strengths corrected for a
    deck where hands run closer together. The full-deck equity buckets are not used."""
    cards = state.cards
    if len(cards) != 2 or any(_RANK[card[0]] < 6 for card in cards + state.board):
        return holdem_postflop(state, facing)
    return _made_strength(cards, state.board, True), _has_draw(cards, state.board, True)


def auction_postflop(state: GameState, facing: bool) -> tuple[float, bool]:
    """zoo/variants/auction.md: best five of all our private cards (three after winning
    the auction) and the board."""
    cards = state.cards
    if len(cards) != 3:
        return holdem_postflop(state, facing)
    return _made_strength(cards, state.board), _has_draw(cards, state.board)


def auction_bid(state: GameState) -> Action:
    """One sealed bid for an extra private card. It is a second-price auction, so bid what
    the card is worth: the equity it adds times the pot. A draw gains most, a made hand
    least. Never more than a tenth of the stack, half that near the bubble with ICM on,
    and nothing when short."""
    allowed = state.can("bid")
    if allowed is None or len(state.cards) < 2 or len(state.board) < 3:
        return automatic(state)
    me = _me(state)
    strength = _made_strength(state.cards, state.board)
    gain = _AUCTION_GAIN[0] if _has_draw(state.cards, state.board) else _AUCTION_GAIN[2 if strength >= 0.85 else 1]
    limit = me.stack // 10 if me.stack > 10 * max(1, state.blinds.big_blind) else 0
    paid = sum(1 for payout in state.config.payouts if payout > 0)
    if P["icm_scale"] and 2 < state.players_remaining <= paid + 1:
        limit //= 2
    bid = min(int(gain * state.pot), limit)
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, bid)))


def _percentile_of(score: float, marks) -> float:
    """Share of hands that score higher. `marks` holds the score at each equal step of
    all hands, best first (tools/gen_variant_tables.py)."""
    if not marks or score >= marks[0]:
        return 0.0
    steps = len(marks) - 1
    for index in range(1, len(marks)):
        if score >= marks[index]:
            span = marks[index - 1] - marks[index]
            return (index - ((score - marks[index]) / span if span > 0 else 0.0)) / steps
    return 1.0


def _entry(detect, phases: dict, preflop_score, postflop_score) -> dict:
    def strength(state: GameState) -> float:
        if state.board:
            return postflop_score(state, state.to_call > 0)[0]
        return preflop_score(state)[0]

    return {"detect": detect, "phases": phases, "strength": strength,
            "preflop": preflop_score, "postflop": postflop_score}  # fmt: skip


VARIANTS = {
    "double_board_turn_discard": _entry(  # the kit's name; the portal calls it "pittsburgh"
        lambda state: isinstance(getattr(state, "variant", None), dict) and "boards" in state.variant,
        {"discard": pittsburgh_discard}, pittsburgh_preflop, pittsburgh_postflop,
    ),  # fmt: skip
    "irish": _entry(  # four cards before the flop; the two kept afterwards play as hold'em
        lambda state: state.phase == "discard",
        {"discard": irish_discard}, irish_preflop, holdem_postflop,
    ),  # fmt: skip
    "discard_reveal": _entry(  # after the select phase the two kept cards play as hold'em
        lambda state: state.phase == "select" or len(state.cards) == 3,
        {"select": discard_reveal_select}, discard_reveal_preflop, holdem_postflop,
    ),  # fmt: skip
    "omaha": _entry(  # exactly two of the four private cards play
        lambda state: len(state.cards) == 4,
        {}, omaha_preflop, omaha_postflop,
    ),  # fmt: skip
    "auction": _entry(  # two cards, or three for the auction winner: all of them play
        lambda state: state.phase == "bid",
        {"bid": auction_bid}, holdem_preflop, auction_postflop,
    ),  # fmt: skip
    "short_deck": _entry(  # nothing in the state marks it: recognised by state.config.variant only
        lambda state: False,
        {}, short_deck_preflop, short_deck_postflop,
    ),  # fmt: skip
    "holdem": _entry(  # keep last: the fallback when nothing else is recognised
        lambda state: True,
        {}, holdem_preflop, holdem_postflop,
    ),  # fmt: skip
}


def variant_of(state: GameState) -> str:
    """Name of the ruleset this table plays: the kit's name if we know it, else by its signs.

    A known name is not trusted when the table asks for a phase that ruleset does not have.
    """
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS and (state.phase == "betting" or state.phase in VARIANTS[name]["phases"]):
        return name
    return next(key for key, variant in VARIANTS.items() if variant["detect"](state))


# ----------------------------------------------------------------------------- 3. strategy: profiles
# Ranges are fractions of the best starting hands (0.12 = top 12%).
_BASE = dict(
    pf_bb=15,  # effective stack (big blinds) at or below which preflop is shove-or-fold
    deep_bb=30,  # below this, opens are smaller and a re-raise is a shove
    # Unopened raise range by players still to act behind us (0 = big blind over limpers,
    # 1 = small blind, 2 = button, 3 = cutoff, ... 7 = under the gun at a full table).
    open={0: 0.08, 1: 0.45, 2: 0.40, 3: 0.28, 4: 0.22, 5: 0.16, 6: 0.13, 7: 0.12},
    open_size=2.5,  # open-raise size in big blinds
    hu_open=0.65,  # heads-up button range
    push_scale=1.0,  # multiplies the push/fold table below
    threebet=0.035,  # re-raise a raise with this range
    call_raise=0.10,  # call a raise with this range when the price is small
    call_margin=0.03,  # equity required beyond pot odds to call an all-in
    call_top=0.0,  # always call an all-in with this range (0 = pot odds only)
    call_min_equity=0.0,  # floor on adjusted equity to call an all-in
    bubble_margin=0.04,  # extra equity to call all-in one place off the points
    points_widen=1.15,  # push/open wider once in the points
    icm_scale=0.0,  # 0 = chip EV, 1 = full ICM risk premium on large calls
    cap_aware=False,  # tighten pushes in the last hands before the hand cap
    post="basic",  # postflop mode: basic, minimal or bucket
    value_bet=0.80,  # postflop strength to bet or raise for value
    value_size=0.66,  # value bet, fraction of pot
    medium_bet=0.60,  # postflop strength to bet when checked to
    cbet_size=0.55,  # bet with a medium-strength hand, fraction of pot
    cbet_air=0.0,  # how often the preflop raiser bets a dry flop with nothing
    semi_bluff=0.4,  # how often to bet a strong draw when checked to
    call_edge=0.12,  # strength required beyond pot odds to call a postflop bet
    points_tight=0.0,  # extra call_edge once in the points
    mc_iters=0,  # not read: runtime Monte Carlo cannot fit in 1 ms in pure Python
    track=False,  # keep per-seat counters in memory
    adapt=frozenset(),  # which reads to act on: steal, shover, station, minraise
    steal_widen=1.0,  # range multiplier when every seat behind is tight
    steal_any=0.0,  # range floor when the seats behind fold almost always
    vs_shover="math",  # "doc": never call a habitual shover wider than the top 13%; "math": by its rate
)

# One line per profile for the file header: tools/build.py writes it into `Profile:`.
ABOUT = {
    "chart_nash": "A. Position charts when deep, Nash-style push/fold when short, pot odds postflop.",
    "steal_heavy": "B. Wider opens and steals, tighter all-in calls, frequent continuation bets.",
    "icm_survival": "C. Chart-Nash with ICM-priced calls, tighter near the bubble and the hand cap.",
    "push_fold": "D. Shove-or-fold from 20 big blinds down, almost no postflop play.",
    "equity_bucket": "E. Chart-Nash preflop, precomputed equity buckets postflop.",
    "adaptive": "F. Chart-Nash plus per-seat tracking and the exploits it allows.",
    "final": "A + F + C, the version to lock in: tracking, exploits and full ICM pricing.",
}

PROFILES = {
    # A. Position charts when deep, Nash-style push/fold short, pot odds postflop.
    "chart_nash": {},
    # B. Wider opens and steals, tighter all-in calls, frequent continuation bets.
    "steal_heavy": dict(
        pf_bb=12, deep_bb=25, open_size=2.2, hu_open=0.70, push_scale=1.1,
        open={0: 0.10, 1: 0.55, 2: 0.50, 3: 0.35, 4: 0.28, 5: 0.22, 6: 0.17, 7: 0.15},
        threebet=0.05, call_raise=0.12, call_top=0.15, call_min_equity=0.55,
        cbet_size=0.70, cbet_air=0.7, semi_bluff=0.5,
        track=True, adapt=frozenset({"steal"}), steal_widen=1.5, steal_any=0.85,
    ),  # fmt: skip
    # C. Chart-Nash with ICM-priced calls and tighter play near the bubble and the cap.
    "icm_survival": dict(
        hu_open=0.60, push_scale=0.9, threebet=0.03, call_raise=0.08, call_margin=0.05,
        bubble_margin=0.08, icm_scale=1.0, cap_aware=True, cbet_size=0.50, semi_bluff=0.2,
        points_tight=0.08,
    ),  # fmt: skip
    # D. Shove-or-fold from 20 big blinds down, almost no postflop play.
    "push_fold": dict(
        pf_bb=20, threebet=0.03, call_raise=0.05, post="minimal", semi_bluff=0.0,
        open={0: 0.06, 1: 0.36, 2: 0.32, 3: 0.22, 4: 0.17, 5: 0.13, 6: 0.11, 7: 0.10},
        track=True, adapt=frozenset({"steal"}), steal_widen=1.12,
    ),  # fmt: skip
    # E. Chart-Nash preflop, precomputed equity buckets postflop.
    "equity_bucket": dict(post="bucket", value_size=0.70, call_edge=0.04),
    # F. Chart-Nash plus per-seat tracking and the exploits it allows.
    "adaptive": dict(
        track=True, adapt=frozenset({"steal", "shover", "station", "minraise"}),
        steal_widen=1.15, steal_any=0.85, cbet_air=0.3, vs_shover="doc",
    ),  # fmt: skip
    # A + F + C: the version to lock in for the later tournaments. Full ICM pricing and
    # C's tighter calls measured better than the lighter mix first tried (see README).
    "final": dict(
        track=True, adapt=frozenset({"steal", "shover", "station", "minraise"}),
        steal_widen=1.15, steal_any=0.85, cbet_air=0.3, vs_shover="doc",
        icm_scale=1.0, cap_aware=True, open_size=2.3, semi_bluff=0.3,
        call_margin=0.05, bubble_margin=0.08, push_scale=0.9, points_tight=0.08,
        threebet=0.03, call_raise=0.08,
        # Averaged two-board strength seldom reaches the hold'em thresholds: bet thinner.
        value_bet=0.70, medium_bet=0.52,
    ),  # fmt: skip
}

P = {**_BASE, **PROFILES[ACTIVE]}

# Day-of knobs for `tools/field_fit.py --sweep` (floats only, one pair per line).
# Applied only when ACTIVE is "final" so other stamped profiles keep their own ranges.
# Keep these in sync with PROFILES["final"] (and the _BASE values final still uses).
SETTINGS = {
    "open_size": 2.3,
    "steal_widen": 1.15,
    "steal_any": 0.85,
    "call_margin": 0.05,
    "bubble_margin": 0.0,
    "semi_bluff": 0.3,
    "cbet_air": 0.6,
    "hu_open": 0.65,
    "push_scale": 0.9,
    "threebet": 0.03,
    "call_raise": 0.08,
    "points_tight": 0.0,
    "icm_scale": 0.0,
}
if ACTIVE == "final":
    P.update(SETTINGS)

# Unopened shove range by effective stack (big blinds) and players behind. The 15/12/10/8/5
# rows for 7, 3, 2 and 1 behind are from published chip-EV push/fold charts; the middle
# position column and the 20, 3 and 1.5 rows are filled in by interpolation and judgement.
_PUSH_BB = (1.5, 3, 5, 8, 10, 12, 15, 20)
_PUSH_COLUMNS = {
    1: (1.00, 0.95, 0.75, 0.60, 0.61, 0.58, 0.54, 0.45),  # small blind
    2: (1.00, 0.60, 0.47, 0.41, 0.39, 0.36, 0.33, 0.27),  # button
    3: (0.85, 0.50, 0.39, 0.33, 0.31, 0.30, 0.27, 0.22),  # cutoff
    5: (0.70, 0.38, 0.30, 0.23, 0.19, 0.17, 0.13, 0.11),  # middle
    7: (0.60, 0.30, 0.25, 0.19, 0.15, 0.14, 0.12, 0.10),  # early
}


def _push_table() -> dict:
    table = dict(_PUSH_COLUMNS)
    table[4] = tuple((a + b) / 2 for a, b in zip(table[3], table[5]))
    table[6] = tuple((a + b) / 2 for a, b in zip(table[5], table[7]))
    table[8] = table[9] = tuple(0.9 * a for a in table[7])
    table[0] = table[1]
    return table


_PUSH = _push_table()


def _push_pct(stack_bb: float, behind: int) -> float:
    """Unopened shove range for this stack and position, interpolated between table rows."""
    column = _PUSH[min(9, max(0, behind))]
    if stack_bb <= _PUSH_BB[0]:
        return column[0]
    for index in range(1, len(_PUSH_BB)):
        if stack_bb <= _PUSH_BB[index]:
            low, high = _PUSH_BB[index - 1], _PUSH_BB[index]
            share = (stack_bb - low) / (high - low)
            return column[index - 1] + share * (column[index] - column[index - 1])
    return column[-1]


# ----------------------------------------------------------------------------- 3. strategy: decide
def decide(state: GameState, variant: dict, tracker=None) -> Action:
    """The betting strategy. Everything it knows about our cards comes from `variant`."""
    if not state.board:
        return preflop(state, variant, tracker)
    return postflop(state, variant, tracker)


# ----------------------------------------------------------------------------- 3. strategy: preflop
def preflop(state: GameState, variant: dict, tracker) -> Action:
    equity, pct = variant["preflop"](state)
    me = _me(state)
    big_blind = max(1, state.blinds.big_blind)
    total = me.stack + me.bet
    others = [s for s in state.seats if s.seat != state.seat and s.status in ("active", "all_in")]
    eff_bb = min(total, max((s.stack + s.bet for s in others), default=total)) / big_blind
    raises = [event for event in state.history if event.kind == "raise"]
    limpers = sum(1 for event in state.history if event.kind == "call")
    behind_seats = _seats_behind(state)
    behind = len(behind_seats)
    paid = sum(1 for payout in state.config.payouts if payout > 0)
    left = state.players_remaining
    on_bubble = left == paid + 1
    in_points = left <= paid
    can_raise = state.can("raise")
    to_call = state.to_call
    pot = max(0, state.pot - _unwinnable(state, me))
    need = to_call / max(1, pot + to_call) if to_call else 0.0
    short = eff_bb <= P["pf_bb"]

    action = _cloned(state, me, pct, eff_bb, raises, limpers, to_call, can_raise, big_blind, behind, left)
    if action is not None:
        return action

    if raises:
        last = raises[-1]
        villain = _seat(state, last.seat)
        committing = to_call >= 0.4 * me.stack
        width = _raiser_width(state, tracker, last, len(raises), villain, big_blind)
        if committing or not can_raise or (villain is not None and villain.stack == 0):
            # Opponents already in for the raise count fully; seats still to act a little.
            callers = sum(1 for s in others if s.seat != last.seat and s.bet >= last.amount)
            return _call_all_in(state, tracker, me, villain, last, equity, pct, need, width,
                                on_bubble, callers, behind)  # fmt: skip
        if short:
            # A small raise while we are short: shove over it, peel cheaply, or fold.
            reshove = min(0.35, max(0.04, 0.45 * width))
            if on_bubble:
                reshove *= 0.8
            if pct <= reshove:
                return Action.raise_to(can_raise.max_amount)
            if behind == 0 and need <= 0.30 and pct <= 0.45:
                return Action.call()
            return Action.fold()
        # Deep and facing a raise.
        three, size = P["threebet"], 3.0
        stats = _stats(tracker, last.seat)
        if stats:
            hands, raised, minraised = stats[0], stats[1], stats[5]
            if "minraise" in P["adapt"] and raised >= 5 and minraised >= 0.6 * raised:
                three, size = max(three, 0.07), 3.5
            elif "shover" in P["adapt"] and hands >= 8 and raised > 0.4 * hands:
                three = max(three, min(0.15, 0.3 * raised / hands))
        if pct <= three:
            if eff_bb <= P["deep_bb"]:
                return Action.raise_to(can_raise.max_amount)
            return raise_to(state, int(size * (me.bet + to_call)))
        cheap = to_call <= 0.12 * me.stack
        closing = behind == 0 and need < 0.3
        if cheap and (pct <= P["call_raise"] or (closing and pct <= 0.2)):
            return Action.call()
        return Action.fold()

    # Nobody has raised yet.
    if to_call and not any(s.status == "active" for s in others):
        # Everyone left is all-in (a short blind): no more betting, so it is pure pot odds.
        return Action.call() if equity >= need + 0.02 else Action.fold()
    widen = P["points_widen"] if in_points else 1.0
    ante = state.blinds.ante * left
    if ante > 0:
        widen *= 1 + 0.6 * ante / (1.5 * big_blind)
    if short:
        limit = _push_pct(eff_bb, behind) * P["push_scale"] * widen
        if P["icm_scale"] and 2 < left <= paid + 2:
            covered = any(s.stack + s.bet >= total for s in others)
            limit *= 1 - 0.25 * P["icm_scale"] if covered else 1 + 0.2 * P["icm_scale"]
        elif on_bubble:
            limit *= 1.15 if total >= _median_stack(state) else 0.9
        if P["cap_aware"] and state.config.hand_cap - state.hand_number <= 6 and eff_bb > 3:
            limit *= 0.85
        mult, floor = _steal(tracker, behind_seats, True)
        limit = limit * mult
        if limpers:
            limit *= 0.7
        else:
            limit = max(limit, floor)
        if not can_raise and to_call >= me.stack > 0:
            # Too short to raise: calling is the shove.
            return Action.call() if pct <= limit or equity - 0.05 >= need else Action.fold()
        if can_raise and behind > 0 and pct <= limit:
            return Action.raise_to(can_raise.max_amount)
        if can_raise and behind == 0 and pct <= 0.5 * _push_pct(eff_bb, 2):
            return Action.raise_to(can_raise.max_amount)  # big blind punishing limpers
        if to_call == 0:
            return Action.check()
        if need <= 0.2 and pct <= 0.6 and to_call <= 0.1 * me.stack:
            return Action.call()  # cheap completion from the small blind
        return Action.fold()

    limit = P["open"].get(behind, 0.10)
    if left == 2 and behind == 1:
        limit = P["hu_open"]
    elif left <= 3:
        limit *= 1.25
    elif left <= 4:
        limit *= 1.15
    size = P["open_size"]
    if eff_bb < P["deep_bb"]:
        limit, size = 0.9 * limit, min(size, 2.2)
    mult, floor = _steal(tracker, behind_seats, False)
    limit = limit * widen * mult
    if not limpers:
        limit = max(limit, floor)
    if can_raise and pct <= limit:
        return raise_to(state, int((size + limpers) * big_blind))
    if to_call == 0:
        return Action.check()
    if need <= 0.2 and pct <= 0.6:
        return Action.call()  # cheap completion, e.g. from the small blind
    return Action.fold()


# Preflop frequencies of the ten best teams, read from round 1's hand histories (2026-11-12):
# the share of hands they play in each spot. Our hands are ranked by percentile, so a share is
# a threshold. Rows: 2, 3, 4-5, 6+ players left. Columns: up to 6, 10, 15, 25 big blinds, deeper.
_CL_DEPTH = (6, 10, 15, 25)
# First in (nobody has raised or called), by seats still to act: 1, 2, 3, 4 or more.
_CL_PLAY = (
    ((0.89, 0.90, 0.80, 0.76, 0.79),),
    ((0.82, 0.82, 0.76, 0.76, 0.78), (0.61, 0.47, 0.42, 0.47, 0.48)),
    ((0.84, 0.77, 0.74, 0.80, 0.80), (0.55, 0.38, 0.43, 0.47, 0.51), (0.35, 0.25, 0.25, 0.28, 0.28),
     (0.34, 0.18, 0.17, 0.18, 0.18)),
    ((0.84, 0.77, 0.71, 0.77, 0.76), (0.70, 0.47, 0.43, 0.47, 0.51), (0.56, 0.32, 0.25, 0.30, 0.30),
     (0.39, 0.20, 0.15, 0.15, 0.14)),
)  # fmt: skip
# Of those, the share that goes all-in at 10 to 15 big blinds (the weaker part; the stronger
# part raises small, as the top teams do, and calls a re-raise).
_CL_SHOVE15 = ((0.34,), (0.42, 0.20), (0.42, 0.18, 0.11, 0.07), (0.37, 0.15, 0.08, 0.04))
_CL_EARLY = (1.35, 1.1, 0.85, 0.7)  # 6+ left: the last row pools 4 to 7 seats behind; spread it
# Calling a first raise that is all-in, by its size in big blinds (same columns): big blind, others.
_CL_CALL_SHOVE = (
    ((0.83, 0.49, 0.34, 0.28, 0.15), (0.83, 0.49, 0.34, 0.28, 0.15)),
    ((0.67, 0.32, 0.19, 0.11, 0.05), (0.45, 0.20, 0.12, 0.06, 0.03)),
    ((0.55, 0.21, 0.11, 0.05, 0.02), (0.30, 0.10, 0.06, 0.05, 0.02)),
    ((0.53, 0.23, 0.14, 0.07, 0.07), (0.28, 0.10, 0.07, 0.05, 0.06)),
)
# Facing one raise that is not all-in: (re-raise, call) shares for the big blind, the small
# blind and the other seats.
_CL_RERAISE = (
    ((0.64, 0.79, 0.80, 0.73, 0.52),) * 3,
    ((0.55, 0.67, 0.65, 0.57, 0.53), (0.58, 0.52, 0.47, 0.46, 0.41), (0.58, 0.52, 0.47, 0.46, 0.41)),
    ((0.42, 0.51, 0.48, 0.45, 0.50), (0.37, 0.37, 0.35, 0.33, 0.34), (0.29, 0.25, 0.20, 0.17, 0.17)),
    ((0.59, 0.55, 0.51, 0.46, 0.35), (0.48, 0.41, 0.39, 0.30, 0.23), (0.27, 0.23, 0.19, 0.14, 0.09)),
)
_CL_CALL = (
    ((0.14, 0.03, 0.03, 0.04, 0.16),) * 3,
    ((0.18, 0.10, 0.09, 0.08, 0.11), (0.02, 0.00, 0.00, 0.01, 0.03), (0.02, 0.00, 0.00, 0.01, 0.03)),
    ((0.18, 0.09, 0.07, 0.07, 0.07), (0.01, 0.00, 0.00, 0.01, 0.01), (0.00, 0.00, 0.01, 0.01, 0.02)),
    ((0.12, 0.09, 0.09, 0.07, 0.08), (0.01, 0.00, 0.00, 0.01, 0.01), (0.01, 0.00, 0.01, 0.01, 0.01)),
)


def _cloned(state, me, pct, eff_bb, raises, limpers, to_call, can_raise, big_blind, behind, left):
    """The first preflop decision in the three spots the tables cover, or None for the general
    code: limped pots, a second raise, and a re-raise after we raised."""
    table = 0 if left <= 2 else 1 if left == 3 else 2 if left <= 5 else 3
    depth = sum(eff_bb > mark for mark in _CL_DEPTH)
    if not raises:
        if limpers or behind < 1 or to_call < 0:
            return None
        rows = _CL_PLAY[table]
        play = rows[min(behind, len(rows)) - 1][depth]
        if table == 3 and behind >= 4:
            play *= _CL_EARLY[min(behind, 7) - 4]
        if pct > play:
            return None
        if not can_raise:
            return Action.call() if to_call > 0 else None
        if depth <= 1 or (depth == 2 and pct > play - _CL_SHOVE15[table][min(behind, len(rows)) - 1]):
            return Action.raise_to(can_raise.max_amount)  # short, or the weaker part at 10 to 15: all-in
        if depth == 2:
            return raise_to(state, int(2.2 * big_blind))
        return raise_to(state, int((2.2 if left <= 2 else 2.3) * big_blind))
    last = raises[0]
    if len(raises) == 2 and last.seat == state.seat and eff_bb <= 15 and to_call > 0:
        # We raised small at 10 to 15 big blinds, which we only do with the strong part: no folding now.
        return Action.raise_to(can_raise.max_amount) if can_raise else Action.call()
    if len(raises) != 1 or last.seat == state.seat or to_call <= 0:
        return None
    seat = 0 if me.bet >= big_blind else 1 if me.bet > 0 else 2
    villain = _seat(state, last.seat)
    if (villain is not None and villain.stack == 0) or to_call >= me.stack or not can_raise:
        size = sum(min(last.amount, me.stack + me.bet) / big_blind > mark for mark in _CL_DEPTH)
        return Action.call() if pct <= _CL_CALL_SHOVE[table][min(seat, 1)][size] else Action.fold()
    reraise = _CL_RERAISE[table][seat][depth]
    if pct <= reraise:
        if eff_bb <= 25:
            return Action.raise_to(can_raise.max_amount)
        return raise_to(state, int(3.0 * (me.bet + to_call)))
    if pct <= reraise + _CL_CALL[table][seat][depth]:
        return Action.call()
    return Action.fold()


def _call_all_in(state, tracker, me, villain, last, equity, pct, need, width, on_bubble,
                 callers, behind) -> Action:  # fmt: skip
    """Facing an all-in or a raise that commits us: call (or shove over it) or fold."""
    # Our table equity is against a random hand; a raising range is stronger than that.
    discount = 0.26 * (1 - width) ** 2.2
    margin = P["call_margin"] + 0.05 * callers + 0.01 * behind
    if on_bubble:
        margin += P["bubble_margin"]
    if P["icm_scale"]:
        margin += P["icm_scale"] * _icm_premium(state, me, villain)
    adjusted = equity - discount
    good = adjusted >= max(need + margin, P["call_min_equity"]) or pct <= P["call_top"]
    stats = _stats(tracker, last.seat)
    if (good and stats and P["vs_shover"] == "doc" and "shover" in P["adapt"]
            and stats[0] >= 6 and stats[4] > 0.3 * stats[0]):  # fmt: skip
        good = pct <= 0.13
    if not good:
        return Action.fold()
    can_raise = state.can("raise")
    if can_raise and villain is not None and villain.stack > 0:
        return Action.raise_to(can_raise.max_amount)  # committed anyway: take the fold equity
    return Action.call()


def _raiser_width(state, tracker, last, raise_count, villain, big_blind) -> float:
    """Estimated fraction of hands the last raiser does this with (1.0 = any two cards)."""
    if villain is None:
        return 0.15
    # What the raiser can actually win or lose: its stack, capped by the biggest one against it.
    cover = max((s.stack + s.bet for s in state.seats
                 if s.seat != villain.seat and s.status in ("active", "all_in")), default=0)  # fmt: skip
    stack_bb = min(villain.stack + villain.bet, cover) / big_blind
    position = _behind_of(state, last.seat)
    all_in = villain.stack == 0 or last.amount >= 0.9 * (villain.stack + villain.bet)
    if all_in:
        # Assume a sound push/fold player; an all-in for far more than 20 blinds is tighter.
        width = _push_pct(min(stack_bb, 20), max(1, position))
        if stack_bb > 20:
            width *= (20 / stack_bb) ** 0.7
    else:
        width = _BASE["open"].get(position, 0.12)
    if raise_count > 1:
        width *= 0.5
    stats = _stats(tracker, last.seat)
    if stats and stats[0] >= 6 and "shover" in P["adapt"]:
        hands = stats[0]
        seen = (stats[4] if all_in else stats[1]) / hands
        trust = hands / (hands + 6)
        blended = (1 - trust) * width + trust * seen
        # The shove rate mixes deep and short hands, so it may only widen an all-in range.
        width = max(width, blended) if all_in else blended
    return min(1.0, max(0.02, width))


def _steal(tracker, behind_seats, shove: bool) -> tuple[float, float]:
    """(range multiplier, range floor) from what the seats still to act have shown."""
    adapt = P["adapt"]
    if tracker is None or "steal" not in adapt or not behind_seats:
        return 1.0, 0.0
    fold_all, all_tight, mult = 1.0, True, 1.0
    for seat in behind_seats:
        stats = _stats(tracker, seat)
        if not stats or stats[0] < 8:
            return 1.0, 0.0  # an unknown seat behind: no adjustment
        hands, raised, called, folded, shoved = stats[0], stats[1], stats[2], stats[3], stats[4]
        fold_all *= folded / hands
        if raised >= 0.15 * hands or raised + called >= 0.25 * hands:
            all_tight = False
        if "station" in adapt and called >= 0.5 * hands and raised < 0.15 * hands:
            mult = min(mult, 0.85)  # it will not fold: steal less
        if "shover" in adapt and shoved > 0.3 * hands:
            mult = min(mult, 0.8)
    floor = P["steal_any"] if fold_all >= (0.9 if shove else 0.85) else 0.0
    if all_tight:
        mult *= P["steal_widen"]
    return mult, floor


# ----------------------------------------------------------------------------- 3. strategy: postflop
def postflop(state: GameState, variant: dict, tracker) -> Action:
    me = _me(state)
    pot, to_call = state.pot, state.to_call
    others = [s for s in state.seats if s.seat != state.seat and s.status in ("active", "all_in")]
    opponents = len(others)
    global _ONE_BOARD
    _ONE_BOARD = 0.0
    strength, draw = variant["postflop"](state, to_call > 0)
    one = _ONE_BOARD  # two boards: each pays half, so a hand that owns one board bets as a freeroll
    # A hand that beats one random hand 70% of the time beats three of them far less often.
    strength = strength ** (1 + 0.3 * max(0, opponents - 1))
    can_raise = state.can("raise")
    minimal = P["post"] == "minimal"
    station = "station" in P["adapt"] and any(_is_station(tracker, s.seat) for s in others)
    value = P["value_bet"] - (0.05 if station else 0.0)
    bigger = 1.25 if station else 1.0  # a station pays off: bet more, never bluff

    if to_call == 0:
        if not can_raise:
            return Action.check()
        if strength >= value or one >= 0.80:
            return raise_to(state, me.bet + int(P["value_size"] * bigger * pot))
        if minimal:
            return Action.check()
        if strength >= P["medium_bet"] or (one >= 0.64 and opponents <= 2):
            return raise_to(state, me.bet + int(P["cbet_size"] * bigger * pot))
        if station or opponents > 2:
            return Action.check()
        if draw and _coin(state, 1) < P["semi_bluff"]:
            return raise_to(state, me.bet + int(0.5 * pot))
        if (P["cbet_air"] and len(state.board) == 3 and _was_aggressor(state)
                and _dry(state.board) and _coin(state, 2) < P["cbet_air"]):  # fmt: skip
            return raise_to(state, me.bet + int(0.4 * pot))
        return Action.check()

    pot = max(0, pot - _unwinnable(state, me))
    need = to_call / max(1, pot + to_call)
    edge = P["call_edge"]
    early = len(state.board) < 5
    if early:
        edge += 0.10  # rounds 1 and 2: we fold flop and turn bets 25 and 22%, the top teams 51 and 43%
    if P["points_tight"] and state.players_remaining <= sum(1 for p in state.config.payouts if p > 0):
        edge += P["points_tight"]
    if P["icm_scale"] and to_call >= 0.4 * me.stack:
        bettor = next((e.seat for e in reversed(state.history) if e.kind == "raise"), None)
        edge += P["icm_scale"] * _icm_premium(state, me, _seat(state, bettor))
    if (strength >= (0.78 if early else 0.88) or (one >= (0.84 if early else 0.93) and strength >= 0.72)) and can_raise:
        return raise_to(state, me.bet + to_call + int(0.75 * (pot + to_call)))
    if one >= 0.84 and need <= 0.42:
        return Action.call()  # trips or better on one board: that half of the pot is nearly ours
    if to_call > 0.5 * me.stack and strength < 0.75:
        return Action.fold()  # do not call off a stack with a marginal hand
    if strength >= need + edge or (draw and need <= (0.2 if early else 0.25) and not minimal):
        return Action.call()
    return Action.fold()


def _was_aggressor(state: GameState) -> bool:
    """Did we make the last raise before the flop?"""
    last = None
    for event in state.history:
        if event.kind == "board":
            break
        if event.kind == "raise":
            last = event.seat
    return last == state.seat


def _dry(board) -> bool:
    """A flop that is not all one suit and has no three cards within a straight's span."""
    suits = [card[1] for card in board]
    if max(suits.count(suit) for suit in suits) >= 3:
        return False
    ranks = sorted({_RANK[card[0]] for card in board})
    return not (len(ranks) >= 3 and ranks[-1] - ranks[0] <= 4)


def _coin(state: GameState, salt: int) -> float:
    """A repeatable number in [0, 1) from the hand: mixes frequencies without `random`."""
    x = state.hand_number * 7919 + state.seat * 104729 + salt * 31337 + len(state.board) * 613
    for card in state.cards:
        x = x * 131 + ord(card[0]) * 7 + ord(card[1])
    return ((x * 2654435761) & 0xFFFFFFFF) / 4294967296.0


# ----------------------------------------------------------------------------- 3. strategy: ICM
def _icm_me(stacks, index: int, payouts) -> float:
    """Our Malmuth-Harville share of the payouts (first three places), others' ignored."""
    mine = stacks[index]
    total = sum(stacks)
    if mine <= 0 or total <= 0:
        return 0.0
    first = payouts[0] if payouts else 0
    second = payouts[1] if len(payouts) > 1 else 0
    third = payouts[2] if len(payouts) > 2 else 0
    value = first * mine / total
    if not (second or third):
        return value
    for j, a in enumerate(stacks):
        if j == index or a <= 0:
            continue
        after_a = total - a
        chance_a = a / total
        value += second * chance_a * mine / after_a
        if third:
            for k, b in enumerate(stacks):
                if k == index or k == j or b <= 0:
                    continue
                value += third * chance_a * (b / after_a) * mine / (after_a - b)
    return value


def _icm_premium(state: GameState, me, villain) -> float:
    """Extra equity a call needs because chips lost cost more points than chips won gain."""
    if villain is None or villain.seat == me.seat:
        return 0.0
    alive = [s for s in state.seats if s.status != "busted"]
    count = len(alive)
    if count <= 2:
        return 0.0  # heads-up, chips and points move together
    payouts = (tuple(state.config.payouts) + (0,) * count)[:count]
    pot, to_call = state.pot, min(state.to_call, me.stack)
    refund = _unwinnable(state, me)  # bets beyond what we can match go back to their owners
    chip_need = to_call / max(1, pot - refund + to_call)
    base = [s.stack for s in alive]
    mine = next((i for i, s in enumerate(alive) if s.seat == me.seat), None)
    theirs = next((i for i, s in enumerate(alive) if s.seat == villain.seat), None)
    if mine is None or theirs is None:
        return 0.0

    def points(my_stack: int, their_stack: int) -> float:
        if my_stack <= 0:
            return float(payouts[count - 1])
        stacks = base[:]
        stacks[mine], stacks[theirs] = my_stack, their_stack
        return _icm_me(stacks, mine, payouts)

    fold = points(me.stack, villain.stack + pot)
    win = points(me.stack + pot - refund, villain.stack + refund)
    lose = points(me.stack - to_call, villain.stack + pot + to_call)
    if win - lose <= 1e-9:
        return 0.3
    return min(0.3, max(0.0, (fold - lose) / (win - lose) - chip_need))


# ----------------------------------------------------------------------------- 3. strategy: table memory
# Fixed-length bytes: an 8-byte header, then 11 bytes per seat.
#   header: b"T2", hands (2 bytes), flags (1 = flop dealt, 2 = pot raised), seat count,
#           mask of seats that have acted preflop this hand (2 bytes)
#   seat:   stack at the end of the last hand (2 bytes), then one-byte counters:
#           hands acted in, raised, called, folded, shoved, min-raised (all first preflop
#           action only), then postflop bets/raises, calls, folds
# Anything of the wrong length or without the header is thrown away, so a cut or
# corrupted blob costs the notes and nothing else.
_HEADER, _PER_SEAT = 8, 11


def _track(state: GameState, memory: bytes):
    """Fold the events since our last decision into the counters. Returns (tracker, memory)."""
    if not P["track"]:
        return None, memory
    count = len(state.seats)
    size = _HEADER + _PER_SEAT * count
    if type(memory) is bytes and len(memory) == size and memory[:2] == b"T2" and memory[5] == count:
        t = bytearray(memory)
    else:
        t = bytearray(size)
        t[0:2] = b"T2"
        t[5] = count
        start = min(65535, max(0, int(state.config.starting_stack)))
        for index in range(count):
            t[_HEADER + _PER_SEAT * index] = start & 255
            t[_HEADER + _PER_SEAT * index + 1] = start >> 8
    big_blind = max(1, state.blinds.big_blind)
    me = state.seat
    hands, flags, mask = t[2] | t[3] << 8, t[4], t[6] | t[7] << 8
    for event in state.events:
        kind = event.kind
        if kind == "hand":
            hands, flags, mask = min(65535, hands + 1), 0, 0
            continue
        if kind == "board":
            flags |= 1
            continue
        seat = event.seat
        if type(seat) is not int or not 0 <= seat < count or seat > 15:
            continue
        base = _HEADER + _PER_SEAT * seat
        if kind == "stack":
            amount = min(65535, max(0, int(event.amount)))
            t[base], t[base + 1] = amount & 255, amount >> 8
        elif kind == "raise" or kind == "call" or kind == "fold":
            if flags & 1:
                if seat != me:
                    _bump(t, base, 8 if kind == "raise" else 9 if kind == "call" else 10)
                continue
            first = not mask & (1 << seat)
            mask |= 1 << seat
            if first and seat != me:
                _bump(t, base, 2)
                if kind == "raise":
                    _bump(t, base, 3)
                    if event.amount >= 0.9 * (t[base] | t[base + 1] << 8):
                        _bump(t, base, 6)
                    elif not flags & 2 and event.amount <= 2.05 * big_blind:
                        _bump(t, base, 7)
                else:
                    _bump(t, base, 4 if kind == "call" else 5)
            if kind == "raise":
                flags |= 2
    if not state.board:
        flags &= ~1  # we are preflop, whatever a lost event left behind
    t[2], t[3], t[4], t[6], t[7] = hands & 255, hands >> 8, flags, mask & 255, mask >> 8
    return t, bytes(t)


def _bump(t: bytearray, base: int, offset: int) -> None:
    if t[base + offset] >= 250:  # halve the seat's counters: no overflow, and old hands fade
        for index in range(base + 2, base + _PER_SEAT):
            t[index] >>= 1
    t[base + offset] += 1


def _stats(tracker, seat):
    """(hands, raised, called, folded, shoved, min-raised, post bets, post calls, post folds)."""
    if tracker is None or type(seat) is not int or seat < 0:
        return None
    base = _HEADER + _PER_SEAT * seat
    if base + _PER_SEAT > len(tracker):
        return None
    return tuple(tracker[base + 2 : base + _PER_SEAT])


def _is_station(tracker, seat) -> bool:
    stats = _stats(tracker, seat)
    if not stats:
        return False
    hands, raised, called = stats[0], stats[1], stats[2]
    if hands >= 8 and called >= 0.5 * hands and raised < 0.15 * hands:
        return True
    return stats[7] + stats[8] >= 6 and stats[7] >= 0.7 * (stats[7] + stats[8])


# ----------------------------------------------------------------------------- 4. helpers: legal actions
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
    """Last line of defence: never hand the platform an illegal action. A raise or bid is
    clamped to its range; a raise that is not offered becomes a call; the rest go passive."""
    if action.kind == "raise" and not state.can("raise"):
        action = Action.call()
    if action.kind == "call" and not state.can("call"):
        action = Action.check()
    allowed = state.can(action.kind)
    if allowed is None:
        return passive(state)
    if action.kind == "raise" or action.kind == "bid":
        return Action(action.kind, max(allowed.min_amount, min(allowed.max_amount, int(action.amount))))
    return action


def raise_to(state: GameState, total: int) -> Action:
    """Raise to `total` for this betting round, clamped to what is legal; shove when that
    is most of our stack anyway."""
    allowed = state.can("raise")
    if not allowed:
        return Action.call() if state.can("call") else Action.check()
    total = max(allowed.min_amount, min(allowed.max_amount, total))
    if total >= 0.6 * allowed.max_amount:
        total = allowed.max_amount
    return Action.raise_to(total)


def shove(state: GameState) -> Action:
    allowed = state.can("raise")
    if allowed:
        return Action.raise_to(allowed.max_amount)
    return Action.call() if state.can("call") else passive(state)


# ----------------------------------------------------------------------------- 4. helpers: table reading
def _me(state: GameState):
    for seat in state.seats:
        if seat.seat == state.seat:
            return seat
    return state.seats[0]


def _seat(state: GameState, number):
    for seat in state.seats:
        if seat.seat == number:
            return seat
    return None


def _big_blind_seat(state: GameState):
    """Heads-up the kit posts the big blind first and the small blind last, so the last blind
    event is not the big blind: take the one that posted the full big blind."""
    blinds = [event for event in state.history if event.kind == "blind"]
    if not blinds:
        return None
    full = [event.seat for event in blinds if event.amount == state.blinds.big_blind]
    # shortcut: a big blind all-in for less than the small blind picks the wrong seat (rare)
    return full[-1] if full else max(blinds, key=lambda event: event.amount).seat


def _seats_behind(state: GameState) -> list:
    """Seats still to act after us preflop if nobody raises (empty = we are the big blind)."""
    big = _big_blind_seat(state)
    if big is None or big == state.seat:
        return []
    seats = state.seats
    index = next((i for i, seat in enumerate(seats) if seat.seat == state.seat), 0)
    behind = []
    for step in range(1, len(seats)):
        seat = seats[(index + step) % len(seats)]
        if seat.status == "active":
            behind.append(seat.seat)
        if seat.seat == big:
            break
    return behind


def _behind_of(state: GameState, number) -> int:
    """How many seats were due to act after `number` preflop, whatever they did since."""
    big = _big_blind_seat(state)
    if big is None:
        return 3
    if big == number:
        return 0
    seats = state.seats
    index = next((i for i, seat in enumerate(seats) if seat.seat == number), 0)
    count = 0
    for step in range(1, len(seats)):
        seat = seats[(index + step) % len(seats)]
        if seat.status != "busted":
            count += 1
        if seat.seat == big:
            break
    return count


def _unwinnable(state: GameState, me) -> int:
    """Chips in `state.pot` that we cannot win: the part of each bet beyond our all-in."""
    limit = me.bet + min(state.to_call, me.stack)
    return sum(max(0, s.bet - limit) for s in state.seats if s.seat != me.seat)


def _median_stack(state: GameState) -> int:
    stacks = sorted(seat.stack + seat.bet for seat in state.seats if seat.status != "busted")
    return stacks[len(stacks) // 2] if stacks else 0


# ----------------------------------------------------------------------------- 4. helpers: hand evaluation
_RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


def _straight_high(ranks, low: int = 5) -> int:
    """Top card of the best straight, or 0. `low` is the top of the straight the ace plays
    low in: 5 in a full deck (A-2-3-4-5), 9 in a 36-card deck (A-6-7-8-9)."""
    mask = 0
    for rank in ranks:
        mask |= 1 << rank
    if mask & (1 << 14):
        mask |= 1 << (low - 4)  # the ace also plays low
    for high in range(14, 4, -1):
        if (mask >> (high - 4)) & 31 == 31:
            return high
    return 0


def hand_rank(cards, short: bool = False) -> tuple:
    """Best five of the given cards as a tuple that compares correctly (bigger wins).

    `short` is the 36-card ranking: a flush (6) beats a full house (5), ace low in A-6-7-8-9.
    """
    return _hand_rank(tuple(cards), short)


@functools.lru_cache(maxsize=64)  # pure; three kept pairs share each board's rank. Small: a big cache slows the garbage collector
def _hand_rank(cards: tuple, short: bool) -> tuple:
    low = 9 if short else 5
    ranks = sorted((_RANK[card[0]] for card in cards), reverse=True)
    by_suit: dict[str, list[int]] = {}
    for card in cards:
        by_suit.setdefault(card[1], []).append(_RANK[card[0]])
    flush = next((sorted(v, reverse=True) for v in by_suit.values() if len(v) >= 5), None)
    if flush:
        high = _straight_high(flush, low)
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
        return (5 if short else 6, top, second)
    if flush:
        return (6 if short else 5, *flush[:5])
    high = _straight_high(ranks, low)
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


def _made_strength(hole, board, short: bool = False) -> float:
    """Rough equity vs one random hand from hand category and how the hole cards contribute.

    The numbers are for a full deck; `short` adds the measured correction per category.
    """
    mine = hand_rank(tuple(hole) + tuple(board), short)
    table = hand_rank(board, short)
    hole_ranks = sorted((_RANK[card[0]] for card in hole), reverse=True)
    board_ranks = sorted((_RANK[card[0]] for card in board), reverse=True)
    top_board = board_ranks[0]
    overcards = sum(1 for rank in hole_ranks if rank > top_board)
    nothing = 0.22 + 0.05 * overcards
    category, on_table = mine[0], table[0]
    if short:  # put flush and full house back in full-deck order for the branches below
        category, on_table = _FULL_DECK_ORDER[category], _FULL_DECK_ORDER[on_table]
    if mine == table:
        strength = 0.30  # playing the board: at best a split
    elif category >= 6:
        strength = 0.97 if on_table < 6 else 0.85
    elif category == 5:
        suit = next(s for s in "cdhs" if sum(card[1] == s for card in tuple(hole) + tuple(board)) >= 5)
        ours = max((_RANK[card[0]] for card in hole if card[1] == suit), default=2)
        on_board = sum(card[1] == suit for card in board)
        strength = 0.93 if on_board <= 3 else 0.55 + 0.35 * (ours - 2) / 12
    elif category == 4:
        strength = 0.86
    elif category == 3:
        if on_table == 3:
            strength = 0.45  # trips are on the board; only kickers differ
        else:
            strength = 0.90 if hole_ranks[0] == hole_ranks[-1] else 0.84
    elif category == 2:
        if on_table == 2:
            strength = 0.40
        elif on_table == 1:  # the board is paired and we hold one more pair
            ours = mine[1] if mine[1] != table[1] else mine[2]
            strength = 0.64 if ours >= top_board else 0.50
        else:
            strength = 0.80
    elif category == 1:
        if on_table == 1:
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
        flush_draw, straight_draw = _draws(hole, board, short)
        if short:  # 5 flush outs instead of 9; straights fill more often
            strength += (0.04 * left if flush_draw else 0.0) + 0.04 * left * straight_draw
        else:
            strength += (0.07 * left if flush_draw else 0.0) + 0.025 * left * straight_draw
    if short:
        strength = max(0.02, strength + _SHORT_SHIFT[category])
    return min(strength, 0.97)


def _draws(hole, board, short: bool = False) -> tuple[bool, int]:
    """(four to a flush using a hole card, straight draw: 2 open-ended, 1 gutshot, 0 none)."""
    return _draws_of(tuple(hole), tuple(board), short)


@functools.lru_cache(maxsize=64)  # pure; strength and the draw flag both ask for it
def _draws_of(hole: tuple, board: tuple, short: bool) -> tuple[bool, int]:
    cards = hole + board
    flush_draw = any(
        sum(card[1] == suit for card in cards) == 4 and any(card[1] == suit for card in hole)
        for suit in "cdhs"
    )
    mask = 0
    for card in cards:
        mask |= 1 << _RANK[card[0]]
    if mask & (1 << 14):
        mask |= 32 if short else 2
    completing = sum(1 for rank in range(6 if short else 2, 15) if _straight_high_mask(mask | 1 << rank, short))
    return flush_draw, 2 if completing >= 2 else completing


def _straight_high_mask(mask: int, short: bool = False) -> bool:
    if mask & (1 << 14):
        mask |= 32 if short else 2
    return any((mask >> low) & 31 == 31 for low in range(1, 11))


def _has_draw(hole, board, short: bool = False) -> bool:
    if len(board) >= 5:
        return False
    flush_draw, straight_draw = _draws(hole, board, short)
    return flush_draw or straight_draw == 2


# ----------------------------------------------------------------------------- 4. helpers: equity buckets
def _bucket(hole, board) -> tuple[str, bool]:
    """(bucket key, has a strong draw). The key names the street, the made hand, any draw
    and the board texture; tools/calibrate_buckets.py measures the true equity of each key."""
    cards = tuple(hole) + tuple(board)
    mine = hand_rank(cards)
    table = hand_rank(board)
    hole_ranks = sorted((_RANK[card[0]] for card in hole), reverse=True)
    board_ranks = sorted((_RANK[card[0]] for card in board), reverse=True)
    top_board = board_ranks[0]
    overcards = sum(1 for rank in hole_ranks if rank > top_board)
    category = mine[0]
    suited = max(sum(card[1] == suit for card in board) for suit in "cdhs")
    if mine == table:
        made = "B"  # playing the board
    elif category >= 6:
        made = "M" if table[0] < 6 else "m"
    elif category == 5:
        suit = next(s for s in "cdhs" if sum(card[1] == s for card in cards) >= 5)
        ours = max((_RANK[card[0]] for card in hole if card[1] == suit), default=2)
        made = "F" if suited <= 3 else "G" if ours >= 12 else "g"
    elif category == 4:
        made = "S"
    elif category == 3:
        made = "b" if table[0] == 3 else "T" if hole_ranks[0] == hole_ranks[-1] else "t"
    elif category == 2:
        if table[0] == 2:
            made = "x"
        elif table[0] == 1:
            ours = mine[1] if mine[1] != table[1] else mine[2]
            made = "w" if ours >= top_board else "v"
        else:
            made = "W"
    elif category == 1:
        if table[0] == 1:
            made = "y%d" % overcards  # the pair is on the board
        elif mine[1] > top_board:
            made = "O"  # overpair
        elif mine[1] == top_board:
            kicker = max((rank for rank in hole_ranks if rank != top_board), default=top_board)
            made = "P" if kicker >= 11 else "p"  # top pair, good or weak kicker
        elif len(board_ranks) > 1 and mine[1] >= sorted(set(board_ranks), reverse=True)[1]:
            made = "q"
        else:
            made = "r"
    else:
        made = "n%d" % overcards
    flush_draw, straight_draw = False, 0
    if len(board) < 5 and category < 4:
        flush_draw, straight_draw = _draws(hole, board)
    texture = "m" if suited >= 3 else "p" if table[0] >= 1 else "d"
    key = "%s%s%s%s%s" % ("FTR"[min(2, max(0, len(board) - 3))], made, "f" if flush_draw else "",
                          straight_draw or "", texture)  # fmt: skip
    return key, flush_draw or straight_draw == 2


def _bucket_key(hole, board) -> str:
    return _bucket(hole, board)[0]


def _parse(table: str) -> dict:
    return {key: int(value) / 1000 for key, value in (item.split(":") for item in table.split())}


# Mean equity of each bucket against one random hand, and against a top-30% hand
# (Monte Carlo, tools/calibrate_buckets.py). A missing key falls back to _made_strength.
_BUCKET_TABLE = "FFm:949 FMp:968 FO1d:762 FO2d:774 FOd:792 FOfm:845 FOm:645 FP1d:801 FP1m:676 FP2d:819 FPd:804 FPfd:884 FPfm:839 FPm:658 FSd:920 FSm:833 FTd:925 FTm:851 FWd:870 FWm:716 Fbp:440 Fn01d:388 Fn01m:304 Fn02d:465 Fn02m:382 Fn0d:297 Fn0f1d:580 Fn0f1m:512 Fn0f2d:621 Fn0f2m:568 Fn0fd:545 Fn0fm:464 Fn0m:238 Fn11d:455 Fn11m:391 Fn12d:498 Fn12m:405 Fn1d:406 Fn1f1d:665 Fn1f1m:578 Fn1f2d:649 Fn1f2m:620 Fn1fd:623 Fn1fm:559 Fn1m:331 Fn21d:478 Fn21m:353 Fn22d:516 Fn22m:381 Fn2d:437 Fn2f1d:698 Fn2f1m:654 Fn2f2d:703 Fn2f2m:557 Fn2fd:650 Fn2fm:609 Fn2m:363 Fp1d:745 Fp1m:612 Fp2d:714 Fp2m:554 Fpd:784 Fpf1d:787 Fpf1m:756 Fpfd:889 Fpfm:786 Fpm:639 Fq1d:704 Fq1m:569 Fq2d:703 Fq2m:512 Fqd:691 Fqf1d:800 Fqf1m:782 Fqfd:810 Fqfm:742 Fqm:565 Fr1d:622 Fr1m:586 Fr2d:658 Fr2m:646 Frd:569 Frf1d:706 Frf1m:625 Frf2m:667 Frfd:724 Frfm:643 Frm:460 Ftp:931 Fvp:649 Fwp:777 Fy01p:425 Fy02p:522 Fy0f1p:500 Fy0f2p:633 Fy0fp:555 Fy0p:332 Fy11p:487 Fy12p:488 Fy1f1p:509 Fy1fp:629 Fy1p:453 Fy21p:503 Fy22p:544 Fy2f1p:618 Fy2fp:687 Fy2p:475 RBd:45 RBm:150 RBp:175 RFm:964 RGm:958 RMm:944 RMp:930 ROd:797 ROm:741 RPd:822 RPm:755 RSd:930 RSm:863 RSp:912 RTd:918 RTm:862 RWd:886 RWm:807 Rbm:329 Rbp:361 Rgm:794 Rmp:761 Rn0d:155 Rn0m:142 Rn1d:247 Rn1m:223 Rn2d:242 Rn2m:226 Rpd:806 Rpm:742 Rqd:708 Rqm:648 Rrd:513 Rrm:463 Rtm:880 Rtp:943 Rvm:605 Rvp:657 Rwm:773 Rwp:830 Rxm:466 Rxp:489 Ry0m:200 Ry0p:217 Ry1m:311 Ry1p:348 Ry2m:323 Ry2p:351 TFm:955 TGm:945 TMm:989 TMp:940 TO1d:753 TO1m:621 TO2d:644 TO2m:500 TOd:819 TOf1m:652 TOf2m:683 TOfm:845 TOm:727 TP1d:777 TP1m:683 TP2d:727 TP2m:537 TPd:821 TPf1d:832 TPf1m:777 TPf2d:763 TPf2m:784 TPfd:880 TPfm:827 TPm:722 TSd:906 TSm:827 TSp:909 TT1d:833 TT1m:718 TT2d:710 TTd:935 TTfm:877 TTm:845 TW1d:749 TW1m:614 TW2d:594 TW2m:506 TWd:882 TWf1m:771 TWfd:905 TWfm:864 TWm:770 Tb1p:366 Tb2p:314 Tbfp:452 Tbp:394 Tgm:781 Tmp:512 Tn01d:273 Tn01m:238 Tn02d:316 Tn02m:250 Tn0d:222 Tn0f1d:410 Tn0f1m:360 Tn0f2d:457 Tn0f2m:413 Tn0fd:378 Tn0fm:331 Tn0m:190 Tn11d:376 Tn11m:328 Tn12d:385 Tn12m:335 Tn1d:342 Tn1f1d:527 Tn1f1m:461 Tn1f2d:525 Tn1f2m:463 Tn1fd:476 Tn1fm:448 Tn1m:294 Tn21d:382 Tn21m:312 Tn22d:362 Tn22m:309 Tn2d:363 Tn2f1d:520 Tn2f1m:466 Tn2f2d:434 Tn2f2m:356 Tn2fd:492 Tn2fm:471 Tn2m:311 Tp1d:760 Tp1m:692 Tp2d:731 Tp2m:672 Tpd:803 Tpf1d:857 Tpf1m:745 Tpf2d:766 Tpf2m:766 Tpfd:846 Tpfm:796 Tpm:708 Tq1d:681 Tq1m:589 Tq2d:666 Tq2m:539 Tqd:711 Tqf1d:746 Tqf1m:686 Tqf2d:761 Tqf2m:681 Tqfd:780 Tqfm:718 Tqm:619 Tr1d:560 Tr1m:475 Tr2d:566 Tr2m:499 Trd:556 Trf1d:644 Trf1m:599 Trf2d:693 Trf2m:606 Trfd:655 Trfm:594 Trm:474 Tt1m:880 Tt1p:918 Tt2p:918 Ttfm:913 Ttfp:943 Ttm:843 Ttp:937 Tv1m:567 Tv1p:669 Tv2m:548 Tv2p:665 Tvf1m:670 Tvf1p:682 Tvfm:673 Tvfp:737 Tvm:594 Tvp:654 Tw1m:663 Tw1p:760 Tw2p:754 Twf1m:816 Twf1p:900 Twfm:803 Twfp:846 Twm:724 Twp:811 Tx1p:463 Tx2p:390 Txf1p:450 Txfp:498 Txp:416 Ty01m:294 Ty01p:314 Ty02m:312 Ty02p:337 Ty0f1m:380 Ty0f1p:445 Ty0f2m:439 Ty0f2p:494 Ty0fm:369 Ty0fp:404 Ty0m:244 Ty0p:270 Ty11m:357 Ty11p:431 Ty12m:380 Ty12p:408 Ty1f1m:486 Ty1f1p:544 Ty1f2m:456 Ty1f2p:547 Ty1fm:501 Ty1fp:530 Ty1m:361 Ty1p:416 Ty21m:424 Ty21p:442 Ty22m:385 Ty22p:408 Ty2f1m:548 Ty2f1p:564 Ty2f2m:472 Ty2f2p:462 Ty2fm:533 Ty2fp:565 Ty2m:407 Ty2p:441"
_BUCKET_TIGHT = "FFm:907 FMp:949 FO1d:690 FO2d:754 FOd:787 FOfm:802 FOm:630 FP1d:744 FP1m:632 FP2d:712 FPd:754 FPfd:823 FPfm:798 FPm:604 FSd:900 FSm:767 FTd:920 FTm:826 FWd:830 FWm:728 Fbp:297 Fn01d:269 Fn01m:230 Fn02d:385 Fn02m:302 Fn0d:147 Fn0f1d:509 Fn0f1m:444 Fn0f2d:575 Fn0f2m:480 Fn0fd:433 Fn0fm:351 Fn0m:123 Fn11d:357 Fn11m:313 Fn12d:423 Fn12m:323 Fn1d:268 Fn1f1d:585 Fn1f1m:491 Fn1f2d:589 Fn1f2m:509 Fn1fd:534 Fn1fm:442 Fn1m:213 Fn21d:425 Fn21m:307 Fn22d:458 Fn22m:281 Fn2d:390 Fn2f1d:629 Fn2f1m:540 Fn2f2d:663 Fn2f2m:443 Fn2fd:620 Fn2fm:523 Fn2m:304 Fp1d:674 Fp1m:549 Fp2d:698 Fp2m:568 Fpd:686 Fpf1d:723 Fpf1m:707 Fpfd:788 Fpfm:663 Fpm:560 Fq1d:599 Fq1m:483 Fq2d:645 Fq2m:631 Fqd:556 Fqf1d:680 Fqf1m:746 Fqfd:728 Fqfm:659 Fqm:466 Fr1d:548 Fr1m:468 Fr2d:635 Fr2m:531 Frd:465 Frf1d:675 Frf1m:552 Frf2m:617 Frfd:669 Frfm:544 Frm:379 Ftp:910 Fvp:527 Fwp:722 Fy01p:295 Fy02p:438 Fy0f1p:518 Fy0f2p:633 Fy0fp:413 Fy0p:165 Fy11p:370 Fy12p:391 Fy1f1p:537 Fy1fp:519 Fy1p:282 Fy21p:389 Fy22p:433 Fy2f1p:500 Fy2fp:567 Fy2p:362 RBd:0 RBm:72 RBp:68 RFm:943 RGm:907 RMm:924 RMp:893 ROd:837 ROm:769 RPd:794 RPm:721 RSd:927 RSm:849 RSp:899 RTd:918 RTm:854 RWd:856 RWm:781 Rbm:122 Rbp:121 Rgm:703 Rmp:655 Rn0d:19 Rn0m:16 Rn1d:142 Rn1m:122 Rn2d:274 Rn2m:251 Rpd:697 Rpm:634 Rqd:528 Rqm:477 Rrd:366 Rrm:325 Rtm:851 Rtp:916 Rvm:471 Rvp:524 Rwm:718 Rwp:782 Rxm:282 Rxp:287 Ry0m:22 Ry0p:27 Ry1m:151 Ry1p:172 Ry2m:267 Ry2p:302 TFm:928 TGm:925 TMm:975 TMp:910 TO1d:740 TO1m:674 TO2d:637 TO2m:500 TOd:828 TOf1m:739 TOf2m:683 TOfm:837 TOm:692 TP1d:715 TP1m:602 TP2d:637 TP2m:533 TPd:795 TPf1d:776 TPf1m:738 TPf2d:658 TPf2m:662 TPfd:839 TPfm:779 TPm:669 TSd:899 TSm:805 TSp:881 TT1d:803 TT1m:700 TT2d:725 TTd:935 TTfm:877 TTm:812 TW1d:735 TW1m:657 TW2d:569 TW2m:494 TWd:845 TWf1m:812 TWfd:889 TWfm:812 TWm:733 Tb1p:282 Tb2p:263 Tbfp:296 Tbp:218 Tgm:696 Tmp:220 Tn01d:139 Tn01m:119 Tn02d:217 Tn02m:192 Tn0d:67 Tn0f1d:301 Tn0f1m:259 Tn0f2d:366 Tn0f2m:307 Tn0fd:246 Tn0fm:194 Tn0m:58 Tn11d:260 Tn11m:226 Tn12d:290 Tn12m:244 Tn1d:204 Tn1f1d:401 Tn1f1m:359 Tn1f2d:409 Tn1f2m:380 Tn1fd:368 Tn1fm:316 Tn1m:160 Tn21d:363 Tn21m:321 Tn22d:321 Tn22m:263 Tn2d:362 Tn2f1d:520 Tn2f1m:448 Tn2f2d:396 Tn2f2m:447 Tn2fd:485 Tn2fm:431 Tn2m:299 Tp1d:682 Tp1m:601 Tp2d:663 Tp2m:572 Tpd:693 Tpf1d:768 Tpf1m:693 Tpf2d:667 Tpf2m:655 Tpfd:768 Tpfm:689 Tpm:611 Tq1d:555 Tq1m:476 Tq2d:596 Tq2m:494 Tqd:550 Tqf1d:637 Tqf1m:578 Tqf2d:641 Tqf2m:615 Tqfd:650 Tqfm:594 Tqm:470 Tr1d:467 Tr1m:403 Tr2d:526 Tr2m:433 Trd:425 Trf1d:576 Trf1m:537 Trf2d:674 Trf2m:528 Trfd:548 Trfm:469 Trm:370 Tt1m:804 Tt1p:895 Tt2p:910 Ttfm:890 Ttfp:928 Ttm:827 Ttp:919 Tv1m:537 Tv1p:573 Tv2m:589 Tv2p:647 Tvf1m:636 Tvf1p:627 Tvfm:552 Tvfp:604 Tvm:464 Tvp:521 Tw1m:700 Tw1p:705 Tw2p:698 Twf1m:763 Twf1p:733 Twfm:716 Twfp:784 Twm:659 Twp:757 Tx1p:246 Tx2p:300 Txf1p:400 Txfp:350 Txp:239 Ty01m:145 Ty01p:161 Ty02m:197 Ty02p:225 Ty0f1m:272 Ty0f1p:333 Ty0f2m:283 Ty0f2p:366 Ty0fm:205 Ty0fp:251 Ty0m:77 Ty0p:90 Ty11m:233 Ty11p:275 Ty12m:240 Ty12p:301 Ty1f1m:393 Ty1f1p:425 Ty1f2m:320 Ty1f2p:408 Ty1fm:335 Ty1fp:381 Ty1m:196 Ty1p:235 Ty21m:306 Ty21p:337 Ty22m:264 Ty22p:306 Ty2f1m:397 Ty2f1p:505 Ty2f2m:417 Ty2f2p:529 Ty2fm:410 Ty2fp:474 Ty2m:302 Ty2p:347"

_BUCKET_R = _parse(_BUCKET_TABLE)
_BUCKET_T = _parse(_BUCKET_TIGHT)


# ----------------------------------------------------------------------------- 4. helpers: preflop table
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
_EQUITY_TABLE = "AA:853 AKs:672 AKo:651 AQs:660 AQo:645 AJs:653 AJo:635 ATs:644 ATo:628 A9s:626 A9o:608 A8s:620 A8o:597 A7s:607 A7o:588 A6s:600 A6o:578 A5s:599 A5o:577 A4s:591 A4o:568 A3s:582 A3o:557 A2s:573 A2o:548 KK:823 KQs:635 KQo:616 KJs:624 KJo:607 KTs:616 KTo:596 K9s:602 K9o:581 K8s:582 K8o:557 K7s:578 K7o:553 K6s:566 K6o:541 K5s:557 K5o:530 K4s:552 K4o:525 K3s:538 K3o:514 K2s:535 K2o:505 QQ:802 QJs:604 QJo:579 QTs:595 QTo:572 Q9s:579 Q9o:553 Q8s:561 Q8o:537 Q7s:542 Q7o:520 Q6s:536 Q6o:508 Q5s:528 Q5o:502 Q4s:520 Q4o:490 Q3s:511 Q3o:482 Q2s:502 Q2o:473 JJ:775 JTs:576 JTo:553 J9s:557 J9o:533 J8s:542 J8o:516 J7s:523 J7o:498 J6s:506 J6o:478 J5s:500 J5o:470 J4s:490 J4o:462 J3s:480 J3o:456 J2s:473 J2o:443 TT:749 T9s:540 T9o:516 T8s:524 T8o:496 T7s:505 T7o:480 T6s:491 T6o:464 T5s:471 T5o:446 T4s:466 T4o:434 T3s:460 T3o:426 T2s:449 T2o:415 99:721 98s:507 98o:480 97s:494 97o:465 96s:476 96o:446 95s:457 95o:429 94s:441 94o:408 93s:434 93o:400 92s:425 92o:392 88:692 87s:479 87o:449 86s:462 86o:430 85s:445 85o:414 84s:428 84o:395 83s:408 83o:375 82s:402 82o:368 77:664 76s:454 76o:424 75s:437 75o:406 74s:418 74o:384 73s:398 73o:367 72s:380 72o:346 66:632 65s:433 65o:400 64s:412 64o:381 63s:397 63o:361 62s:379 62o:342 55:604 54s:415 54o:380 53s:396 53o:361 52s:378 52o:341 44:570 43s:386 43o:349 42s:368 42o:335 33:538 32s:359 32o:322 22:504"

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


# ----------------------------------------------------------------------------- 4. helpers: variant tables
# Measured by tools/gen_variant_tables.py on the mini simulator's rules for each variant
# (Monte Carlo against one random hand). Rerun it to refresh them; it rewrites these lines.

# short_deck: equity of each of the 81 starting classes of a 36-card deck.
_SHORT_TABLE = "AA:728 AKo:595 AKs:618 AQo:588 AQs:600 AJo:584 AJs:596 ATo:564 ATs:580 A9o:546 A9s:562 A8o:532 A8s:544 A7o:501 A7s:531 A6o:481 A6s:503 KK:689 KQo:573 KQs:588 KJo:562 KJs:579 KTo:568 KTs:572 K9o:513 K9s:532 K8o:470 K8s:499 K7o:465 K7s:482 K6o:443 K6s:462 QQ:657 QJo:560 QJs:578 QTo:553 QTs:570 Q9o:511 Q9s:526 Q8o:474 Q8s:498 Q7o:434 Q7s:450 Q6o:420 Q6s:445 JJ:637 JTo:548 JTs:573 J9o:511 J9s:527 J8o:471 J8s:497 J7o:430 J7s:452 J6o:394 J6s:420 TT:610 T9o:513 T9s:523 T8o:475 T8s:494 T7o:436 T7s:463 T6o:399 T6s:418 99:563 98o:475 98s:490 97o:442 97s:461 96o:395 96s:425 88:503 87o:412 87s:439 86o:376 86s:399 77:442 76o:356 76s:385 66:393"
# short_deck: correction to the full-deck made-hand strength, by full-deck hand category.
_SHORT_SHIFT = (0.043, -0.051, -0.046, -0.052, -0.025, 0.064, -0.08, 0.008, 0.029)
# discard_reveal: equity = a + b * (best two-card equity of the three cards); and that
# score at each 5% step of all three-card hands, best first.
_DISCARD_FIT = (0.018, 0.85)
_DISCARD_MARKS = (0.853, 0.775, 0.672, 0.651, 0.635, 0.62, 0.607, 0.599, 0.588, 0.578, 0.568, 0.553, 0.54, 0.53, 0.516, 0.5, 0.48, 0.465, 0.445, 0.414, 0.349)
# omaha: the same for the mean two-card equity of the four cards.
_OMAHA_FIT = (0.06, 0.88)
_OMAHA_MARKS = (0.823, 0.6067, 0.5822, 0.5658, 0.5523, 0.542, 0.5318, 0.5228, 0.5142, 0.5058, 0.4977, 0.4897, 0.4813, 0.4732, 0.4645, 0.4552, 0.4448, 0.4332, 0.4188, 0.4003, 0.348)
# omaha: equity of the best exactly-two-plus-three hand, by street (flop, turn, river) and category.
_OMAHA_MADE = (
    (0.344, 0.469, 0.601, 0.811, 0.807, 0.883, 0.939, 0.996, 0.996),
    (0.226, 0.378, 0.544, 0.757, 0.807, 0.877, 0.931, 0.999, 0.999),
    (0.025, 0.198, 0.471, 0.675, 0.806, 0.87, 0.926, 0.999, 1.0),
)
# irish: the same for the average of the best and the mean two-card equity of the four cards.
_IRISH_FIT = (-0.061, 1.006)
_IRISH_MARKS = (0.853, 0.7039, 0.6609, 0.6269, 0.6111, 0.5993, 0.5896, 0.5801, 0.571, 0.5624, 0.5536, 0.5448, 0.5361, 0.527, 0.5166, 0.5051, 0.4926, 0.4784, 0.4606, 0.4375, 0.364)
# auction: equity an extra private card adds with a draw, an ordinary hand, a made hand (estimates).
_AUCTION_GAIN = (0.10, 0.06, 0.03)

_FULL_DECK_ORDER = (0, 1, 2, 3, 4, 6, 5, 7, 8)  # short-deck category -> full-deck category
_SHORT_EQUITY = {key: int(value) / 1000 for key, value in (item.split(":") for item in _SHORT_TABLE.split())}


def _short_percentiles() -> dict[str, float]:
    combos = {key: 6 if len(key) == 2 else 4 if key[2] == "s" else 12 for key in _SHORT_EQUITY}
    total = sum(combos.values()) or 1
    result, better = {}, 0
    for key in sorted(_SHORT_EQUITY, key=_SHORT_EQUITY.__getitem__, reverse=True):
        result[key] = better / total
        better += combos[key]
    return result


_SHORT_PERCENTILE = _short_percentiles()
