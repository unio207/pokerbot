"""Vedaant Seceret Strategies HeHeHe — STUB (template only; finish on another device).

Source:  handoff stub from Cursor session; see zoo/VEDAANT_SECERET_STRATEGIES.md
Profile: Strong zoo opponent — RubricPressure ICM (strategy F), unfinished
Notes:   Placeholder copy of _template. Replace decide / rewrite before relying on it.

Rules every zoo bot must follow (same as the competition):
- One file. `class Agent` with `act(state, memory) -> (Action, bytes)`.
- No state on `self` or in globals between calls; use the `memory` bytes (empty at the
  start of every table, keep it small).
- Return within 1 ms. An exception, timeout or illegal action is played as check/fold.
- Standard library only (eval7 is allowed). No network, files or subprocesses.
- Read table settings from `state` (blinds, payouts, players); do not hard-code them.
"""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            # A variant's own decision phase: take the platform's automatic choice.
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory
        return decide(state), memory


def decide(state: GameState) -> Action:
    """REPLACE THIS. The placeholder raises big pairs and big aces, and otherwise checks or folds."""
    ranks = sorted((RANK[card[0]] for card in state.cards), reverse=True)
    strong = (ranks[0] == ranks[1] and ranks[0] >= 10) or (ranks[0] == 14 and ranks[1] >= 12)
    if strong:
        return raise_to(state, 3 * state.blinds.big_blind)
    return Action.check() if state.can("check") else Action.fold()


# ----------------------------------------------------------------------------- helpers
def raise_to(state: GameState, total: int) -> Action:
    """Raise to `total` chips for this betting round, clamped to what is legal."""
    allowed = state.can("raise")
    if allowed:
        return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, total)))
    return Action.call() if state.can("call") else Action.check()


def shove(state: GameState) -> Action:
    allowed = state.can("raise")
    if allowed:
        return Action.raise_to(allowed.max_amount)
    return Action.call() if state.can("call") else Action.check()


def my_stack(state: GameState) -> int:
    return next(seat.stack for seat in state.seats if seat.seat == state.seat)


def stack_in_big_blinds(state: GameState) -> float:
    return my_stack(state) / max(1, state.blinds.big_blind)


def pot_odds(state: GameState) -> float:
    """Share of the final pot we must put in to call: call when our win chance is higher."""
    return state.to_call / (state.pot + state.to_call) if state.to_call else 0.0
