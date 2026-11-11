"""Plays only premium hands: raises three big blinds, keeps betting, folds everything else."""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState

RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory
        ranks = sorted((RANK[card[0]] for card in state.cards), reverse=True)
        premium = (ranks[0] == ranks[1] and ranks[0] >= 9) or (ranks[0] == 14 and ranks[1] >= 12)
        if premium:
            allowed = state.can("raise")
            if allowed:
                target = max(3 * state.blinds.big_blind, state.pot)
                return Action.raise_to(max(allowed.min_amount, min(allowed.max_amount, target))), memory
            if state.can("call"):
                return Action.call(), memory
        return (Action.check() if state.can("check") else Action.fold()), memory
