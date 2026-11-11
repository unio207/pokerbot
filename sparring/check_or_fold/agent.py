"""Checks when free, otherwise folds. Also what the platform plays for a crashed bot."""

import poker_agent_sdk
from poker_agent_sdk import Action, GameState


class Agent(poker_agent_sdk.Agent):
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        if state.phase != "betting":
            first = state.legal_actions[0]
            return Action(first.kind, first.min_amount), memory
        return (Action.check() if state.can("check") else Action.fold()), memory
