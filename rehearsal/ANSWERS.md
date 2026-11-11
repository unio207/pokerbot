# Rehearsal answer sheet

**Spoilers.** Read this only after the timer has stopped. The unconverted baseline is at
the very bottom and gives nothing away.

&nbsp;

&nbsp;

&nbsp;

&nbsp;

&nbsp;

&nbsp;

&nbsp;

&nbsp;

&nbsp;

&nbsp;

## What a full conversion covers

Detection and the new phase:

- [ ] `detect` keys on `state.config.variant == "rehearsal"` or the `draw` phase. Card
      count does not help: it is two, as in hold'em.
- [ ] A `draw` handler returning `Action("draw", cards=(index,))` to exchange and
      `Action("draw")` to stand, with `amount` left at zero.
- [ ] The handler never sends two indexes. That is invalid and is played as a stand, and
      it counts as a failed decision.
- [ ] The handler falls back to standing when the state is not what the rules describe.

The exchange decision:

- [ ] Stand with a made hand that uses both cards, or when the exchange cannot improve it.
- [ ] Exchange the card that contributes nothing: for example keep the paired card or the
      card of the flush suit, and throw the other.
- [ ] The decision is made on four board cards with one card to come plus the
      replacement, so a four-flush is worth far more than in hold'em: two chances to hit.
- [ ] The thrown card becomes public. Throwing a card of the suit or rank that would
      complete an obvious hand tells the table what you are not holding.

The ranking change:

- [ ] Hand evaluation has no straights: a straight ranks as high card and a straight
      flush as an ordinary flush. `hand_rank`, `_made_strength` and anything using eval7
      need this.
- [ ] Straight draws are worth nothing. Any draw bonus or semi-bluff based on them is
      removed for this variant.
- [ ] Preflop values shift: connectedness loses its value, suitedness and high cards gain.
      The preflop table is remeasured with the variant's ranking and exchange, not copied
      from hold'em.
- [ ] Flushes are the third-best hand here (below full house, above three of a kind) and
      come up more often because of the exchange, so one-pair hands lose value on later
      streets.

Using what opponents reveal:

- [ ] `draw` events with amount 0 (stood) and 1 (exchanged) are read for every seat.
      Standing on a scary board means a made hand; exchanging means the hand was weak or
      drawing on the turn.
- [ ] `discard` events remove known cards from what opponents can hold, and from our own
      outs.

Things the rules file states that are easy to miss:

- [ ] The exchange happens after the **turn**, not the flop.
- [ ] All-in players also choose, so the handler can be called with no chips behind.
- [ ] `state.variant` is empty and `shown_cards` is not used: the information is only in
      the events.
- [ ] The replacement keeps the exchanged card's position in `state.cards`.

## Unconverted baseline

`bots/final` as it stood on `main` when this was written, command from the README,
seed `rehearsal`, 300 tables, mini simulator:

| Bot | Points per table |
| --- | --- |
| `bots/final` (unconverted) | 21.07 |
| `zoo/codex_adaptive_icm_1` | 21.10 |
| `zoo/claude_grinder_1` | 16.97 |
| `starter` | 15.37 |
| `sparring/shover` | 11.80 |
| `sparring/nit` | 11.03 |
| `sparring/min_raiser` | 1.90 |
| `sparring/calling_station` | 0.77 |

Zero failed decisions for every bot. Par is 12.5. One score at 300 tables is good to
about ±1.2, so the converted bot should clear roughly 23.5 to count as an improvement.
