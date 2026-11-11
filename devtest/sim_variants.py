"""Game variants for the mini simulator: one class per ruleset in zoo/variants/, same name.

A variant changes the base hold'em hand through a few hooks that `mini_sim.Table` calls:

    hole_cards            private cards dealt to each player
    deck()                the cards in play, unshuffled
    after_board(...)      runs after each street's board cards are dealt and before its
                          betting; the place for an extra decision phase
    rank(hole, board, hand_rank)   showdown strength of a player's remaining cards

To add a variant: write its ruleset in zoo/variants/<name>.md, subclass `Holdem` here
with the same `name`, and add it to `VARIANTS`. `mini_sim.py play --variant <name>`, the
practice web page and `tools/check_zoo.py --variant <name>` then pick it up.

These are our re-implementations from the rulesets, not the organizers' engine. Where a
ruleset says "unknown", the choice made here is a guess and is marked GUESS.
"""

from poker_agent_sdk import Action, Event, LegalAction

DECK = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]


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


VARIANTS = {variant.name: variant for variant in (Holdem(), DiscardReveal())}
