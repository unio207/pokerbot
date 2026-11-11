"""Push-or-fold maniac: shoves all in preflop with any pair, ace, or two big cards."""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory
        ranks = sorted((RANK[card[0]] for card in state.cards), reverse=True)
        strong = ranks[0] == ranks[1] or ranks[0] == 14 or ranks[1] >= 10
        if strong:
            allowed = state.can("raise")
            if allowed:
                return Action.raise_to(allowed.max_amount), memory
            if state.can("call"):
                return Action.call(), memory
        return (Action.check() if state.can("check") else Action.fold()), memory
