# Bot zoo

Opponents to test against. Each folder here is one bot. The aim was variety that looks
like the field, not strength: weak, odd and even failing bots belong here. It did not look
like the field: at the Pittsburgh regional these bots went to showdown in 20 to 90% of hands
and real teams in 8 to 13%, and a bot that scored 28 points per table against them scored
12.4 on the platform (`skills/STATE.md`). Use the zoo to find crashes, not to judge strength.
Background and the reasoning are in [`docs/bot-zoo.md`](../docs/bot-zoo.md).

## Variants

The tournament's variant is secret until the build starts, so zoo bots are built to take
any variant we have written down:

- [`zoo/variants/`](variants/README.md) holds one ruleset per variant, in a fixed layout,
  and says how to add a new one.
- [`zoo/_template/`](_template/README.md) is the bot skeleton. Its strategy is written
  once; everything that depends on the variant sits in one `VARIANTS` table with an entry
  per ruleset.

To have an AI assistant write a bot, point it at the template folder and name a profile
and the variants, for example: "Read `zoo/_template/README.md` and make a tight zoo bot
for all variants." The template's README is the brief it follows.

The mini simulator plays every variant that has a class in
[`devtest/sim_variants.py`](../devtest/sim_variants.py). Pick one with `--variant <name>`
on `devtest/mini_sim.py play`, `tools/check_zoo.py` and `practice.py --mini`, or in the
Variant box on the practice web page. Its versions are our own, with guesses where a
ruleset says "unknown".

## Add a bot

1. **Copy the template** to a new folder. Name it `<source>_<profile>_<n>`, using
   letters, digits, `_` and `-` only, for example `gpt_aggro_1` or `henry_tight_2`. Add
   the variant when the bot supports only one: `gpt_aggro_discard_reveal_1`.

   ```bash
   cp -r zoo/_template zoo/gpt_aggro_1
   ```


2. **Write the bot** in `zoo/<name>/agent.py`. Either:
   - follow [`zoo/_template/README.md`](_template/README.md): write `decide` and one
     `VARIANTS` entry per ruleset the bot supports, or
   - paste a whole `agent.py` from a model. The generation prompt and the list of team
     profiles are in [`docs/bot-zoo.md`](../docs/bot-zoo.md). A pasted file replaces the
     template entirely; that is fine.

3. **Fill in the header** at the top of the file: source, profile, the variants it
   implements, and one line on what it does. This is how we later know what mix the zoo
   contains. A pasted bot written for standard hold'em gets `Variants: holdem`.

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

The plan before the event was to tune on about two thirds of the zoo and check the final bot
against the rest. Scores against the zoo did not carry over to the real field (see the top).

## Moving a zoo bot to the real kit

A zoo bot is an ordinary competition bot, so its folder works unchanged as an argument to
the kit's `poker-agent play` and in the web page's kit engine. What the mini simulator
does and does not share with the kit is listed in
[`devtest/README.md`](../devtest/README.md). The main gap is the variant: a bot plays only the
rulesets named on its `Variants:` header line, and under any other variant, including the
announced one, it takes the automatic choice in any extra phase until an entry is added.

`_template` is skipped by `check_zoo.py`. It still appears in the web page's bot list; it
is a valid, very tight bot.
