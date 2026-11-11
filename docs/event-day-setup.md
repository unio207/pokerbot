# Event-day setup

Based on the competition's setup skill
(`https://pokerbot.sequoiacap.com/tournament/no-limit-2026-setup/SKILL.md`, version
2026-11-05.2) and the Getting started page.

## What the setup skill does

It is an instruction file for an AI coding assistant running **on your own computer**
(Claude Code or Codex with a terminal, not a web chat). Given your API key it:

1. Checks the key against the site and finds your team and its build machine.
2. Asks whether to work on the remote build machine (recommended) or only locally.
3. Creates or finds an SSH key, registers it with the site, and writes an SSH alias
   `no-limit-2026-build` (user `ubuntu`, folder `~/work`).
4. Optionally connects the Codex app or the Claude desktop app to the build machine.
5. After the variant is announced, downloads the starter kit with your API key, copies
   it to `~/work/starter-kit` on the machine, builds `.venv` there and runs a smoke test.
6. Or, for local work, sets the kit up in `./starter-kit` on your computer.

Steps 1 to 4 work **before** the event. Step 5 or 6 needs the announcement; running the
skill again then only adds the kit.

## Do tonight

Install the skill and run it once, so that only the kit step is left for the day.

```bash
curl -fsSL --create-dirs -o ~/.claude/skills/no-limit-2026-setup/SKILL.md https://pokerbot.sequoiacap.com/tournament/no-limit-2026-setup/SKILL.md
```

Then in Claude Code on your computer run `/no-limit-2026-setup` and paste the API key
from **Settings → API keys** when asked. Each team member does this with their own key
(up to five SSH keys per account). The site's page suggests a smaller model for it.

Check afterwards:

```bash
ssh no-limit-2026-build
```

Before the box opens this prints its opening time and disconnects; that still proves the
key works.

Notes:

- **Windows:** the skill says the kit's simulator does not run on native Windows, only
  `poker-agent check`. Use WSL or the build machine.
- **Python:** the kit needs Python 3.12 exactly, not 3.13.
- **Secrets:** the skill's own rule is never to copy a private key or the API key to the
  build machine. That includes GitHub credentials, so this repository gets there by
  `scp`, not `git clone`.

## On the day

1. Run `/no-limit-2026-setup` again. It downloads the kit and installs it at
   `~/work/starter-kit` on the build machine (or `./starter-kit` locally).
2. Read the kit's `RULES.md` for the variant.
3. Copy this repository next to the kit:

   ```bash
   scp -r pokerbot no-limit-2026-build:work/
   ```

4. Log in with the two ports forwarded, so the practice page and the kit's hand viewer
   open in your own browser:

   ```bash
   ssh -L 8765:127.0.0.1:8765 -L 8766:127.0.0.1:8766 no-limit-2026-build
   ```

5. On the machine, start the practice page. It finds `~/work/starter-kit` by itself and
   uses the real engine:

   ```bash
   cd ~/work/pokerbot && ../starter-kit/.venv/bin/python ui/server.py
   ```

   Open http://127.0.0.1:8765/ on your computer. The banner should read
   "Organizers' kit". `practice.py` finds the kit the same way:

   ```bash
   ../starter-kit/.venv/bin/python practice.py starter
   ```

6. Upload a legal bot straight away so the team always has an active bot, then start on
   the variant.

Working locally instead: unpack the kit as `starter-kit` inside or beside this folder
and run the same two commands; no port forwarding is needed.

## How our tools find the kit

`ui/server.py` and `practice.py` look for the kit's `poker-agent` in this order: the
`--kit` option (server only), the `POKER_AGENT` environment variable (server only), the
PATH, then a `starter-kit/.venv` folder inside this project, beside it, or in `~/work`.

The kit's hand viewer is started on port 8766 (`--viewer-port` changes it), which is why
that port is forwarded above.

## What the skill confirms about the kit

- The smoke test is `poker-agent play . examples/check_or_fold examples/min_raiser
  --tables 2 --no-history`, so the `--tables` and `--no-history` options our tools pass
  exist in the current kit.
- The Claude desktop app and Codex are both supported on the build machine, so using
  Claude there is expected by the organizers.

## Converting to the announced variant

The steps to turn `bots/final` into a bot for a variant we have not seen. Rehearsed on
2026-11-11 with `irish` (four hole cards, discard two after the flop), a variant written
for the purpose: the converted bot scored 30.9 points per table against 17.3 for the
unconverted one at the same tables (300 tables, mini simulator), with no failed
decisions and the bot's error handler switched off. The same day, `discard_reveal` was
smoked with the current `bots/final` (already variant-aware): 30.4 points per table vs
starter 20.8 over 300 tables, seed `discard_rehearse`, zero failed decisions.

1. **Read the kit's `RULES.md`** and write the variant down as `zoo/variants/<name>.md`
   from [`TEMPLATE.md`](../zoo/variants/TEMPLATE.md). The "What a bot must implement"
   section is the checklist for step 3. Note the exact phase names, action forms and
   `state.config.variant`.
2. **Upload `bots/final/agent.py` unchanged first.** It answers an unknown phase with the
   automatic choice, so it is legal in any variant and the team has an active bot.
3. **Add one entry to `VARIANTS` in `tools/core_agent.py`**, using the `irish` entry as
   the pattern:
   - `detect`: the phase name or card count that marks the variant.
   - `phases`: one handler per extra phase, returning the kit's action form. Fall back to
     `automatic(state)` when the cards are not what the ruleset says.
   - `preflop`: a score of the private cards mapped to (equity, percentile). Try two or
     three scores and keep the one that predicts winning best.
   - `postflop`: which private cards play with the board. `holdem_postflop` already
     takes the best two-card combination of any number of cards.
4. **Measure its tables.** Add a job to `tools/gen_variant_tables.py` (the `irish` job is
   four lines) and run it. On the mini simulator this needs the variant as a class in
   `devtest/sim_variants.py`; with the kit, deal the hands with the kit's engine instead.

   ```bash
   python3.12 tools/gen_variant_tables.py tools/core_agent.py --samples 400000
   ```

   This remeasures every variant's tables; keep only the new variant's lines if the
   others should stay as they were.
5. **Rebuild and check.**

   ```bash
   python3.12 tools/build.py
   ```

   ```bash
   python3.12 tools/fuzz.py bots/final --states 20000
   ```

   ```bash
   python3.12 tools/check_zoo.py --variant <name> bots/final
   ```

6. **Compare with the unconverted bot on the kit**, same seed, before uploading. Keep the
   unconverted upload selectable on the team page as the rollback.

What the rehearsal did not cover: reading an unfamiliar `RULES.md`, the kit's real phase
names and action forms, a changed deck or hand ranking (see the `short_deck` entry for
that pattern), and timing on the build machine. The rehearsal took a few minutes because
the variant, the simulator class and the bot were all ours; budget most of the hour.

## Reading the field between rounds

```bash
python3.12 tools/field_report.py <downloaded history file> --hero <our team name>
```

prints each opponent's habits, the mix of types in the field and which `PROFILES` knobs
to change. The organizers' file format was not available beforehand, so the first run on
a real file may recognise no hands. Then:

```bash
python3.12 tools/field_report.py --inspect <downloaded history file>
```

shows the file's structure; match it in the one function `kit_hands` in
`tools/field_report.py`. To see the report on our own simulator:

```bash
python3.12 tools/field_report.py --simulate bots/final starter sparring/shover sparring/nit sparring/check_or_fold --tables 40 --hero final
```
