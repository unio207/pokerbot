"""Never folds a hand with any promise and never raises: calls up to half its stack."""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory
        if state.can("check"):
            return Action.check(), memory
        stack = next(seat.stack for seat in state.seats if seat.seat == state.seat)
        ranks = [RANK[card[0]] for card in state.cards] + [RANK[card[0]] for card in state.board]
        connected = len(set(ranks)) < len(ranks) or max(RANK[c[0]] for c in state.cards) >= 11
        if state.can("call") and (state.to_call <= stack // 2 or connected):
            return Action.call(), memory
        return Action.fold(), memory
