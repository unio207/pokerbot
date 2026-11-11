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
   - `FLAKY` (some failed decisions): add it anyway and leave it as it is. Real fields
     contain these, and the platform plays check/fold for them.
   - `BROKEN` (will not import or fails the upload check): fix the import or delete it.

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
- Standard library only (eval7 allowed). No network, files or subprocesses.
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

`_template` is skipped by `check_zoo.py`. It still appears in the web page's bot list; it
is a valid, very tight bot.
