"""Zoo bot template. Copy this folder, rename it, and fill in the parts marked REPLACE.

Source:   <model or person who wrote it>
Profile:  <the team profile used in the prompt, or "default">
Variants: <rulesets from zoo/variants/ this bot implements, e.g. "holdem, discard_reveal", or "all">
Notes:    <one line on what it does, e.g. "tight preflop, shoves under 10 big blinds">

How this file is organised (read zoo/_template/README.md before writing a bot):
  1. act()      crash-proof wrapper. Never changes between variants.
  2. VARIANTS   one entry per ruleset in zoo/variants/. Everything that depends on the
                variant lives in an entry: how to recognise it, how to answer its extra
                decision phases, and how to score our private cards.
  3. decide()   the betting strategy (the bot's temperament). It only consumes the 0..1
                strength score from the variant entry, so it is written once.
  4. helpers    legal-action and stack helpers shared by everything above.

Rules every zoo bot must follow (same as the competition):
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
"""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


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
# Each ruleset in zoo/variants/<name>.md gets one entry here under the same name:
#   detect    state -> bool. True when this table plays the variant. Checked in order,
#             after an exact match on state.config.variant; "holdem" is the fallback.
#   phases    {phase name: handler(state) -> Action} for the variant's extra phases.
#   strength  state -> float in 0..1, how good our private cards are right now. This is
#             the only place that knows how many cards we hold and which ones play.
# To support a new variant: read its ruleset, write its functions, add its entry.


def two_card_strength(first: str, second: str) -> float:
    """REPLACE with real scoring. Rough 0..1 score of two cards, ignoring the board."""
    high, low = sorted((RANK[first[0]], RANK[second[0]]), reverse=True)
    if high == low:
        return 0.6 + 0.4 * (high - 2) / 12  # 22 = 0.60, TT = 0.87, AA = 1.00
    return 0.92 * (high + low) / 28 + (0.02 if first[1] == second[1] else 0.0)  # AK = 0.89


def best_two(cards) -> tuple[int, int]:
    """Indices of the two private cards that score best together."""
    pairs = [(i, j) for i in range(len(cards)) for j in range(i + 1, len(cards))]
    return max(pairs, key=lambda pair: two_card_strength(cards[pair[0]], cards[pair[1]]))


def best_two_strength(state: GameState) -> float:
    """Strength when exactly two private cards play at showdown, however many we hold."""
    if len(state.cards) < 2:
        return 0.0
    first, second = best_two(state.cards)
    return two_card_strength(state.cards[first], state.cards[second])


def discard_reveal_select(state: GameState) -> Action:
    """zoo/variants/discard_reveal.md: discard one of three cards, expose one of the two kept."""
    keep = best_two(state.cards)
    discard = next(index for index in range(len(state.cards)) if index not in keep)
    reveal = min(keep, key=lambda index: RANK[state.cards[index][0]])  # show the lower card
    return Action("select", cards=(discard, reveal))


def auction_bid(state: GameState) -> Action:
    """zoo/variants/auction.md: one sealed bid for an extra hole card. REPLACE the sizing."""
    allowed = state.can("bid")
    wanted = state.blinds.big_blind if best_two_strength(state) >= 0.85 else 0
    return Action("bid", max(allowed.min_amount, min(allowed.max_amount, int(wanted))))


def irish_discard(state: GameState) -> Action:
    """zoo/variants/irish.md: throw away two of four cards once the flop is out."""
    keep = best_two(state.cards)
    return Action("discard", cards=tuple(index for index in range(len(state.cards)) if index not in keep)[:2])


VARIANTS = {
    "irish": {  # four cards before the flop, the two kept afterwards
        "detect": lambda state: state.phase == "discard",
        "phases": {"discard": irish_discard},
        "strength": best_two_strength,  # REPLACE: before the flop four cards are worth more than their best two
    },
    "discard_reveal": {
        "detect": lambda state: state.phase == "select" or (len(state.cards) == 3 and not state.board),
        "phases": {"select": discard_reveal_select},
        "strength": best_two_strength,
    },
    "omaha": {  # exactly two of the four private cards play
        "detect": lambda state: len(state.cards) == 4,
        "phases": {},
        "strength": best_two_strength,
    },
    "auction": {
        "detect": lambda state: state.phase == "bid",
        "phases": {"bid": auction_bid},
        "strength": best_two_strength,  # REPLACE: the auction winner holds three cards, all of which play
    },
    "short_deck": {  # nothing in the state marks it: recognised by state.config.variant only
        "detect": lambda state: False,
        "phases": {},
        "strength": best_two_strength,  # REPLACE: no cards below 6, and a flush beats a full house
    },
    "holdem": {  # keep last: the fallback when nothing else is recognised
        "detect": lambda state: True,
        "phases": {},
        "strength": best_two_strength,
    },
}


def variant_of(state: GameState) -> str:
    """Name of the ruleset this table plays: the kit's name if we know it, else by its signs."""
    name = str(getattr(state.config, "variant", "") or "").lower().replace("-", "_")
    if name in VARIANTS:
        return name
    return next(key for key, variant in VARIANTS.items() if variant["detect"](state))


# ----------------------------------------------------------------------------- 3. strategy
def decide(state: GameState, variant: dict) -> Action:
    """REPLACE THIS. The placeholder raises big pairs and big aces, and otherwise checks or folds."""
    if variant["strength"](state) >= 0.85:
        return raise_to(state, 3 * state.blinds.big_blind)
    return passive(state)


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


def stack_in_big_blinds(state: GameState) -> float:
    return my_stack(state) / max(1, state.blinds.big_blind)


def pot_odds(state: GameState) -> float:
    """Share of the final pot we must put in to call: call when our win chance is higher."""
    return state.to_call / (state.pot + state.to_call) if state.to_call else 0.0
