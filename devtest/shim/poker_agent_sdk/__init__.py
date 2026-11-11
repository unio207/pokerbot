"""Stand-in for the organizers' `poker_agent_sdk`, used ONLY by devtest/mini_sim.py.

It mirrors the public dataclasses the real SDK documents (Action, GameState, ...), so a bot
written for the real kit imports and runs unchanged. It is not the organizers' code. When
the real kit is installed, use `poker-agent play` instead: that is the authority.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    amount: int = 0
    cards: tuple[int, ...] = ()

    @staticmethod
    def fold() -> "Action":
        return Action("fold")

    @staticmethod
    def check() -> "Action":
        return Action("check")

    @staticmethod
    def call() -> "Action":
        return Action("call")

    @staticmethod
    def raise_to(amount: int) -> "Action":
        return Action("raise", amount)


@dataclass(frozen=True, slots=True)
class LegalAction:
    kind: str
    min_amount: int = 0
    max_amount: int = 0


@dataclass(frozen=True, slots=True)
class BlindLevel:
    small_blind: int
    big_blind: int
    ante: int = 0


@dataclass(frozen=True, slots=True)
class TableConfig:
    table_id: str
    seat: int
    players: int
    variant: str
    starting_stack: int
    blinds: tuple[BlindLevel, ...]
    hands_per_level: int
    hand_cap: int
    payouts: tuple[int, ...]
    decision_ms: int
    memory_bytes: int
    time_bank_ms: int = 0


@dataclass(frozen=True, slots=True)
class Seat:
    seat: int
    stack: int
    bet: int
    status: str  # active, folded, all_in, or busted
    shown_cards: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Event:
    kind: str
    seat: int | None = None
    amount: int = 0
    cards: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GameState:
    events: tuple[Event, ...]
    hand_number: int
    seat: int
    cards: tuple[str, ...]
    board: tuple[str, ...]
    pot: int
    to_call: int
    legal_actions: tuple[LegalAction, ...]
    history: tuple[Event, ...]
    seats: tuple[Seat, ...]
    button: int
    blind_level: int
    blinds: BlindLevel
    hands_until_next_level: int
    players_remaining: int
    bust_order: tuple[int, ...]
    config: TableConfig
    variant: dict[str, Any] = field(default_factory=dict)
    phase: str = "betting"
    time_bank_ms: float = 0.0

    def can(self, kind: str) -> LegalAction | None:
        return next((legal for legal in self.legal_actions if legal.kind == kind), None)


class Agent:
    def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]:
        raise NotImplementedError


def icm(stacks, payouts) -> list[float]:
    """Expected payout per player (Malmuth-Harville): each place is won in proportion to chips."""
    players = [p for p in range(len(stacks)) if stacks[p] > 0]
    total = sum(stacks[p] for p in players)
    equity = [0.0] * len(stacks)
    chance = {0: 1.0}
    for place in range(min(len(payouts), len(players))):
        following: dict[int, float] = {}
        for mask, probability in chance.items():
            remaining = total - sum(stacks[p] for i, p in enumerate(players) if mask >> i & 1)
            for i, player in enumerate(players):
                if mask >> i & 1:
                    continue
                share = probability * stacks[player] / remaining
                equity[player] += share * payouts[place]
                following[mask | 1 << i] = following.get(mask | 1 << i, 0.0) + share
        chance = following
    return equity
