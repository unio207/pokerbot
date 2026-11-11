# Building the bot zoo

The field tomorrow is other teams' bots, mostly written in an hour with AI assistants. A
zoo is a folder of 15–30 bots written the same way, so we tune against something that
looks like the real field instead of five hand-written opponents.

## Steps

1. **Generate.** Give the prompt below to several different models (and the same model
   several times, in fresh chats). Vary only the last line, the "team profile". Each
   answer is one `agent.py`.
2. **Save.** Put each one in its own folder: `zoo/<model>_<profile>_<n>/agent.py`. The
   practice web page finds any folder with an `agent.py` up to two levels deep.
3. **Filter the way the platform does.** Every real upload first plays a test match
   (heads-up against check-or-fold, up to 20 hands, no time bank) and is refused if it
   does not start, crashes, or fails more than 10% of its decisions. So a bot that fails
   constantly cannot be in the field. `tools/check_zoo.py` imitates that test: discard
   `REJECTED` and `BROKEN` bots, keep `FLAKY` ones (they pass the test but fail some
   decisions at a full table, which real bots will too).

   ```bash
   python3.12 tools/check_zoo.py
   ```

4. **Measure the zoo.** Play 8 random zoo bots per run a few times and note the mix:
   how many never raise, how many shove constantly, how many fail decisions.
5. **Tune against it.** Run our bot against random 7-bot samples from the zoo with a
   fixed seed, change one thing, rerun. Trust a change only over about 1,600 tables.
6. **Hold some back.** Tune on two thirds of the zoo and check the final version on the
   remaining third, so we do not overfit to particular bots.

## Generation prompt

```text
Write a complete poker bot as a single Python 3.12 file, agent.py, for a bot tournament.
Reply with only the code.

Interface (do not invent other methods):

    import poker_agent_sdk
    from poker_agent_sdk import Action, GameState

    class Agent(poker_agent_sdk.Agent):
        def act(self, state: GameState, memory: bytes) -> tuple[Action, bytes]: ...

- Actions: Action.fold(), Action.check(), Action.call(), Action.raise_to(total), where
  total is the bot's total bet for the current betting round.
- state.can(kind) returns the legal action of that kind or None; for "raise" it has
  .min_amount and .max_amount (max is all-in). state.legal_actions lists them all.
- state fields: cards (e.g. ("As", "Td")), board, pot, to_call, seat, seats (each with
  .seat, .stack, .bet, .status in active/folded/all_in/busted), button, blinds
  (.small_blind, .big_blind), blind_level, hands_until_next_level, players_remaining,
  bust_order, history (this hand's events), events (events since this bot's last turn;
  each has .kind, .seat, .amount, .cards; kinds include hand, blind, fold, check, call,
  raise, board, show, win, stack), phase ("betting"), config (.payouts, .hand_cap,
  .hands_per_level, .starting_stack, .players).
- memory is bytes, empty at the start of each table, returned and handed back on the
  next turn at that table. Nothing else persists: no globals, nothing on self.

- Check and call are never both offered. Fold is not offered when checking is free.
- A raise total outside [min_amount, max_amount] is an illegal action; it is not clamped,
  and a float amount is rounded down. Use whole numbers.

Rules: no-limit hold'em, 8 players, 2,000 chips each, blinds 10/20 rising every 20
hands, table ends at one survivor or 250 hands. Points per table are in
state.config.payouts (50/30/20 for 1st/2nd/3rd by default, but they can differ per
table); bots still in at the hand cap split the remaining points by ICM on their stacks
(poker_agent_sdk.icm(stacks, payouts) is provided). Each decision must return within
1 ms, with a 100 ms time bank per table for overruns; an error, timeout or illegal action
is played as check-or-fold. Every upload first plays a short test match with no time bank
and is rejected if more than 10% of its decisions fail. Python 3.12; you may import the
standard library and NumPy, SciPy, pandas, scikit-learn, PyTorch (CPU), LightGBM,
XGBoost, ONNX Runtime, Numba and eval7, nothing else. No network, no files, no state
across tables.

Team profile: <ONE OF THE PROFILES BELOW>
```

## Team profiles

Rotate these in the last line so the zoo is not 20 copies of the same idea.

- You have 60 minutes and no poker experience. Write what you can get working.
- You are a strong poker player and want a tight, disciplined tournament bot.
- You believe aggression wins sit-and-gos: shove and steal as much as is defensible.
- You want to survive to the top three above all else.
- You are a quant: use pot odds, equity estimates and ICM wherever you can.
- You want to exploit weak bots: track opponents in memory and adapt.
- You have 15 minutes left and must submit something simple that cannot crash.
- (No profile line at all: the model's default.)

Weight the mix toward the first profile and the default; that is probably what most of
the field looks like.

## Caveats

- The real field has no always-failing bots: the upload test screens them out, and a
  team with no accepted upload scores zero without being seated. Expect weak and passive
  bots, not dead seats, apart from bots that break only at a full table or mid-round.
- These bots are written for standard hold'em. When the variant is announced, most of the
  real field will be converting in a hurry, so expect more broken bots than the zoo has.
- Zoo results come from the unofficial mini simulator unless run through the kit's
  `poker-agent play`.
