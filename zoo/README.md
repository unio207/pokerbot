# Bot zoo

Opponents to tune against. Each folder here is one bot. The aim is variety that looks
like tomorrow's field, not strength: weak, odd and even failing bots belong here.
Background and the reasoning are in [`docs/bot-zoo.md`](../docs/bot-zoo.md).

## Add a bot

1. **Copy the template** to a new folder. Name it `<source>_<profile>_<n>`, using
   letters, digits, `_` and `-` only, for example `gpt_aggro_1` or `henry_tight_2`.

   ```bash
   cp -r zoo/_template zoo/gpt_aggro_1
   ```

   The Clone button on the practice web page does the same thing.

2. **Write the bot** in `zoo/<name>/agent.py`. Either:
   - replace `decide` in the template by hand, using its helpers, or
   - paste a whole `agent.py` from a model. The generation prompt and the list of team
     profiles are in [`docs/bot-zoo.md`](../docs/bot-zoo.md). A pasted file replaces the
     template entirely; that is fine.

3. **Fill in the header** at the top of the file: source, profile, and one line on what
   it does. This is how we later know what mix the zoo contains.

4. **Check it.**

   ```bash
   python3.12 tools/check_zoo.py zoo/gpt_aggro_1
   ```

   - `OK`: add it.
   - `FLAKY` (passes the upload test but fails some decisions at a full table): add it
     anyway and leave it as it is. Real fields contain these, and the platform plays
     check/fold for the failed decisions.
   - `REJECTED` (fails more than 10% of decisions in the upload test): the real platform
     would refuse this upload, so it cannot be in the field. Fix it or delete it.
   - `BROKEN` (fails the static check or will not import): fix it or delete it.

5. **Commit and push.**

   ```bash
   git add zoo/gpt_aggro_1
   ```

   ```bash
   git commit -m "Add zoo bot gpt_aggro_1"
   ```

   ```bash
   git push
   ```

## Rules for zoo bots

The same as the competition, so that a zoo bot behaves like a real opponent:

- One file, `agent.py`, with `class Agent` and `act(state, memory) -> (Action, bytes)`.
- Nothing kept on `self` or in globals between calls; only the `memory` bytes.
- 1 ms per decision. Errors, timeouts and illegal actions are played as check/fold.
- Raises are not clamped: a total outside `[min_amount, max_amount]` is a failed decision.
- Imports: standard library, `poker_agent_sdk`, and the competition's library list (NumPy,
  SciPy, pandas, scikit-learn, PyTorch CPU, LightGBM, XGBoost, ONNX Runtime, Numba,
  eval7). Never `poker_engine` or `pokerkit`. No network, files or subprocesses.
- Do not import from `starter/` or from another zoo bot. Each bot stands alone.
- Do not "fix" a model's bot to make it stronger. Record it as it came.

## Use the zoo

```bash
python3.12 tools/check_zoo.py
```

lists every zoo bot with its status, points per table against the sparring bots, share of
first places, failed decisions and decision time. Use it to see the mix: how many never
win, how many fail decisions, how many are slow.

To play against zoo bots, start the web page (`python3.12 ui/server.py`) and pick them in
the seat dropdowns, or name them on the command line:

```bash
python3.12 devtest/mini_sim.py play starter zoo/gpt_aggro_1 zoo/henry_tight_2 sparring/nit --tables 200
```

Tune on about two thirds of the zoo and check the final bot against the rest.

## Moving a zoo bot to the real kit

A zoo bot is an ordinary competition bot, so its folder works unchanged as an argument to
the kit's `poker-agent play` and in the web page's kit engine. What the mini simulator
does and does not share with the kit is listed in
[`devtest/README.md`](../devtest/README.md). The main gap is the variant: zoo bots are
written for standard hold'em, and under the announced variant they will take the
automatic choice in any extra phase unless they are rewritten.

`_template` is skipped by `check_zoo.py`. It still appears in the web page's bot list; it
is a valid, very tight bot.
