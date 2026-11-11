"""Game variants for the mini simulator: one class per ruleset in zoo/variants/, same name.

A variant changes the base hold'em hand through a few hooks that `mini_sim.Table` calls:

    hole_cards            private cards dealt to each player
    deck()                the cards in play, unshuffled
    after_board(...)      runs after each street's board cards are dealt and before its
                          betting; the place for an extra decision phase
    rank(hole, board, hand_rank)   showdown strength of a player's remaining cards

A hook works on the hand's `context`: `hole` (seat -> cards), `shown` (seat -> face-up
cards), `deck` (undealt cards), `dead` (chips paid into the pot outside the betting) and
`marks` (replay-only events). It asks a bot through `table.ask(..., phase=, fallback=,
validate=)` and tells the table what happened with `table.log.append(Event(...))`.

To add a variant: write its ruleset in zoo/variants/<name>.md, subclass `Holdem` here
with the same `name`, and add it to `VARIANTS`. `mini_sim.py play --variant <name>`, the
practice web page and `tools/check_zoo.py --variant <name>` then pick it up.

These are our re-implementations from the rulesets, not the organizers' engine. Where a
ruleset says "unknown", the choice made here is a guess and is marked GUESS.
"""

import math
from collections import Counter
from itertools import combinations

from poker_agent_sdk import Action, Event, LegalAction

DECK = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]
RANK = {rank: value for value, rank in enumerate("23456789TJQKA", 2)}


def rank_five(cards, low_straight=5, flush_beats_full_house=False) -> tuple:
    """Exactly five cards as a tuple that compares correctly (bigger wins). `low_straight`
    is the top card of the straight in which the ace plays low: 5 in a full deck (A-2-3-4-5),
    9 in a 36-card deck (A-6-7-8-9)."""
    ranks = sorted((RANK[card[0]] for card in cards), reverse=True)
    flush = len({card[1] for card in cards}) == 1
    straight = 0
    if len(set(ranks)) == 5:
        if ranks[0] - ranks[4] == 4:
            straight = ranks[0]
        elif ranks[0] == 14 and ranks[1] == low_straight and ranks[1] - ranks[4] == 3:
            straight = low_straight
    groups = sorted(Counter(ranks).items(), key=lambda item: (item[1], item[0]), reverse=True)
    shape = tuple(count for _, count in groups)
    order = tuple(rank for rank, _ in groups)
    flush_value, full_value = (6, 5) if flush_beats_full_house else (5, 6)
    if straight and flush:
        return (8, straight)
    if shape == (4, 1):
        return (7, *order)
    if shape == (3, 2):
        return (full_value, *order)
    if flush:
        return (flush_value, *ranks)
    if straight:
        return (4, straight)
    return ({(3, 1, 1): 3, (2, 2, 1): 2, (2, 1, 1, 1): 1}.get(shape, 0), *order)


def best_five(cards, **rules) -> tuple:
    """Best five-card hand from any of the given cards."""
    return max(rank_five(five, **rules) for five in combinations(cards, 5))


class Holdem:
    """Standard no-limit hold'em: the base every other variant changes."""

    name = "holdem"
    title = "Standard hold'em"
    hole_cards = 2

    def deck(self) -> list[str]:
        return DECK[:]

    def after_board(self, table, context, street: int) -> None:
        """`street` is 1 after the flop, 2 after the turn, 3 after the river."""

    def rank(self, hole, board, hand_rank) -> tuple:
        return hand_rank(tuple(hole) + tuple(board))


class DiscardReveal(Holdem):
    """zoo/variants/discard_reveal.md: three hole cards; after the flop every live player
    discards one face down and turns one kept card face up. All choices are collected
    before any is shown.

    GUESS: the select phase comes after the flop is dealt and before flop betting.
    GUESS: the reveal reaches other bots as a `reveal` event and in `seat.shown_cards`.
    GUESS: the automatic choice discards the first card and reveals the second.
    GUESS: a `select` action with no cards asks for the automatic choice and is legal.
    """

    name = "discard_reveal"
    title = "Discard and reveal (3 hole cards)"
    hole_cards = 3
    AUTOMATIC = Action("select", cards=(0, 1))

    def after_board(self, table, context, street):
        live = sorted(context["alive"] - context["folded"])
        if street != 1 or len(live) < 2:
            return
        choices = {
            seat: table.ask(seat, 0, (LegalAction("select"),), context, phase="select",
                            fallback=self.AUTOMATIC, validate=self.validate).cards  # fmt: skip
            for seat in live
        }
        for seat in live:
            discard, reveal = choices[seat]
            cards = context["hole"][seat]
            context["hole"][seat] = tuple(card for index, card in enumerate(cards) if index != discard)
            context["shown"][seat] = (cards[reveal],)
            if context["marks"] is not None:  # replay only: the discard is never public
                context["marks"].append((len(table.log), ["discard", seat, 0, [cards[discard]]]))
            table.log.append(Event("reveal", seat, 0, (cards[reveal],)))

    def validate(self, action, state):
        """The action to play, or None when it is illegal (a failed decision)."""
        if not action.cards:
            return self.AUTOMATIC
        try:
            discard, reveal = (int(index) for index in action.cards)
        except (TypeError, ValueError):
            return None
        if discard == reveal or not all(0 <= index < len(state.cards) for index in (discard, reveal)):
            return None
        return Action("select", cards=(discard, reveal))


class ShortDeck(Holdem):
    """zoo/variants/short_deck.md: 36 cards (no 2-5), a flush beats a full house, and the
    ace plays low only as A-6-7-8-9."""

    name = "short_deck"
    title = "Short deck (36 cards)"

    def deck(self):
        return [card for card in DECK if RANK[card[0]] >= 6]

    def rank(self, hole, board, hand_rank):
        return best_five(tuple(hole) + tuple(board), low_straight=9, flush_beats_full_house=True)


class Omaha(Holdem):
    """zoo/variants/omaha.md: four hole cards; a hand is exactly two of them with exactly
    three board cards. Betting stays no-limit."""

    name = "omaha"
    title = "Omaha (4 hole cards, use exactly 2)"
    hole_cards = 4

    def rank(self, hole, board, hand_rank):
        return max(rank_five(two + three) for two in combinations(hole, 2) for three in combinations(board, 3))


class Auction(Holdem):
    """zoo/variants/auction.md: after the flop every live player with chips makes one
    sealed bid for an extra hole card. The highest bidder pays the second-highest bid into
    the pot and gets the card; tied top bidders each pay their bid and each get a card; a
    bid of 0 never wins. All bids are then made public."""

    name = "auction"
    title = "Auction (bid for a third hole card)"

    def after_board(self, table, context, street):
        live = sorted(context["alive"] - context["folded"])
        bidders = [seat for seat in live if table.stacks[seat] > 0]
        if street != 1 or len(live) < 2 or not bidders:
            return
        bids = {
            seat: table.ask(seat, 0, (LegalAction("bid", 0, table.stacks[seat]),), context, phase="bid",
                            fallback=Action("bid", 0), validate=self.validate).amount  # fmt: skip
            for seat in bidders
        }
        for seat in bidders:
            table.log.append(Event("bid", seat, bids[seat]))
        top = max(bids.values())
        if top == 0:
            return
        winners = [seat for seat in bidders if bids[seat] == top]
        price = top if len(winners) > 1 else max((bids[seat] for seat in bidders if seat != winners[0]), default=0)
        for seat in winners:
            card = context["deck"].pop()
            table.stacks[seat] -= price
            context["dead"] += price
            context["hole"][seat] += (card,)
            table.log.append(Event("auction", seat, price))
            if context["marks"] is not None:  # replay only: the card is private
                context["marks"].append((len(table.log), ["extra", seat, 0, [card]]))

    def validate(self, action, state):
        allowed = state.can("bid")
        try:
            amount = math.floor(action.amount)
        except (TypeError, ValueError, OverflowError):
            return None
        return Action("bid", amount) if allowed.min_amount <= amount <= allowed.max_amount else None

    def rank(self, hole, board, hand_rank):
        return best_five(tuple(hole) + tuple(board))


class Irish(Holdem):
    """zoo/variants/irish.md: four hole cards; after the flop every live player discards
    two face down and plays on with the other two. Our own rehearsal variant.

    GUESS: the discard comes after the flop is dealt and before flop betting.
    GUESS: the automatic choice discards the last two cards.
    GUESS: a `discard` action with no cards asks for the automatic choice and is legal.
    """

    name = "irish"
    title = "Irish (4 hole cards, discard 2 after the flop)"
    hole_cards = 4
    AUTOMATIC = Action("discard", cards=(2, 3))

    def after_board(self, table, context, street):
        live = sorted(context["alive"] - context["folded"])
        if street != 1 or len(live) < 2:
            return
        for seat in live:
            thrown = table.ask(seat, 0, (LegalAction("discard"),), context, phase="discard",
                               fallback=self.AUTOMATIC, validate=self.validate).cards  # fmt: skip
            cards = context["hole"][seat]
            context["hole"][seat] = tuple(card for index, card in enumerate(cards) if index not in thrown)
            if context["marks"] is not None:  # replay only: discards are never public
                context["marks"].append((len(table.log), ["discard", seat, 0, [cards[index] for index in thrown]]))

    def validate(self, action, state):
        """The action to play, or None when it is illegal (a failed decision)."""
        if not action.cards:
            return self.AUTOMATIC
        try:
            first, second = (int(index) for index in action.cards)
        except (TypeError, ValueError):
            return None
        if first == second or not all(0 <= index < len(state.cards) for index in (first, second)):
            return None
        return Action("discard", cards=(first, second))


VARIANTS = {variant.name: variant
            for variant in (Holdem(), DiscardReveal(), ShortDeck(), Omaha(), Auction(), Irish())}  # fmt: skip
