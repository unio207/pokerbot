# Timed conversion rehearsal

> **Written before the Pittsburgh regional (2026-11-12) and left as it was.** The 13-point gain
> quoted below is a mini-simulator number. `bots/final` is now the Pittsburgh bot, so the
> unconverted baseline in `ANSWERS.md` (21.07) will not reproduce. What happened:
> [`pittsburgh-results.md`](../docs/pittsburgh-results.md).

A variant none of us has converted a bot to, written the way the organizers write theirs,
so the person who will do the conversion on the day can practise it against the clock.

**Do not open [`RULES.md`](RULES.md) until the timer starts.** Reading it is the first
step of the exercise. The same goes for the `Rehearsal` class in
`devtest/sim_variants.py`, which plays the role of the kit's engine.

## Why

Converting to the announced variant is the largest single gain we have measured (about 13
points per table in the `irish` rehearsal). That rehearsal took minutes because the
variant, the simulator class and the bot were all ours. It did not test reading an
unfamiliar rules file, unfamiliar phase names and action forms, or a rule that changes
which hands are strong. This one does.

## Rules of the exercise

- **Who:** the person who owns variant scoring on the day. The other person times, and
  does their own day-of job in parallel (uploads, field tools) if they want the practice.
- **Time limit:** 45 minutes. The build is 60, and the first ten go on setup and getting
  a legal bot active.
- **Allowed:** everything allowed on the day: AI assistants, every tool in this repo,
  the docs.
- **Not allowed:** asking anyone who has read the rules file what it says.

## Steps

Follow "Converting to the announced variant" in
[`docs/event-day-setup.md`](../docs/event-day-setup.md). The variant's name on the mini
simulator is `rehearsal`.

1. Start the timer. Read `RULES.md`.
2. Record the unconverted score first (this is the "upload unchanged" step):

   ```bash
   python3.12 devtest/mini_sim.py play bots/final starter sparring/nit sparring/shover sparring/calling_station sparring/min_raiser zoo/claude_grinder_1 zoo/codex_adaptive_icm_1 --variant rehearsal --tables 300 --seed rehearsal
   ```

3. Write the ruleset as `zoo/variants/<name>.md` from the template.
4. Add the `VARIANTS` entry in `tools/core_agent.py`, measure its tables, rebuild.
5. Check it:

   ```bash
   python3.12 tools/build.py
   ```

   ```bash
   python3.12 tools/fuzz.py bots/final --states 20000
   ```

   ```bash
   python3.12 tools/check_zoo.py --variant rehearsal bots/final
   ```

6. Rerun the command from step 2 with the same seed and stop the timer.

## Scoring the rehearsal

| Question | Pass |
| --- | --- |
| Was a legal bot "uploaded" (step 2 run clean) within 10 minutes? | Yes |
| Failed decisions in the final run | 0 |
| Converted bot against the unconverted score, same seed | Higher by more than 2 points per table (300 tables gives about ±1.2 on one score) |
| Every rule in `RULES.md` reflected in the bot | Check against the list in [`ANSWERS.md`](ANSWERS.md) afterwards |
| Finished inside 45 minutes | Yes |

The unconverted baseline, measured when this was written (same command, seed
`rehearsal`, 300 tables): see the bottom of `ANSWERS.md`, which is safe to scroll to
because the number says nothing about the rules.

## Afterwards

Write down what cost the most time and fix that in
[`docs/event-day-setup.md`](../docs/event-day-setup.md) or the tools. Do the work on a
branch: the conversion itself does not need to be merged, and leaving `main` unconverted
keeps the variant usable for the other team member.

## Limits

The engine here is our mini simulator, not the organizers' kit, and the rules file is our
imitation of their style. The real file may be longer, vaguer or organised differently.
The page's hand replay was not adapted to this variant and may show a replaced card
wrongly.
