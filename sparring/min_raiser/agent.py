"""Raises the minimum whenever it can, otherwise calls or checks."""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory
        allowed = state.can("raise")
        if allowed:
            return Action.raise_to(allowed.min_amount), memory
        return (Action.call() if state.can("call") else Action.check()), memory
