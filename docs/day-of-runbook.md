# Day-of runbook (No Limit 2026)

One-page checklist. Upload bot is always [`bots/final/agent.py`](../bots/final/agent.py).
Edit knobs in [`tools/core_agent.py`](../tools/core_agent.py), then `python3.12 tools/build.py`.

## Before the hour (should already be done)

- [ ] `ssh no-limit-2026-build` works (setup skill steps 1–4).
- [ ] This repo ready to `scp -r` (no GitHub credentials on the box).
- [ ] Know who owns variant scoring vs uploads/field analysis.

## Minute 0–10: get a legal bot live

1. Re-run `/no-limit-2026-setup` so the kit lands in `~/work/starter-kit`.
2. `scp -r pokerbot no-limit-2026-build:work/`
3. `ssh -L 8765:127.0.0.1:8765 -L 8766:127.0.0.1:8766 no-limit-2026-build`
4. On the box:

   ```bash
   cd ~/work/pokerbot
   ../starter-kit/.venv/bin/python tools/build.py --check
   ../starter-kit/.venv/bin/python tools/fuzz.py bots/final --states 5000
   ```

5. **Upload `bots/final` immediately** so the team always has an active bot.
6. Read the kit `RULES.md`. Write `zoo/variants/<name>.md` from the template if new.

## Variant conversion (person A)

Follow [`docs/event-day-setup.md`](event-day-setup.md) “Converting to the announced variant”.
Irish was the rehearsal: converted bot beat the unconverted one by a large margin on mini.

```bash
../starter-kit/.venv/bin/python tools/gen_variant_tables.py   # if tables need regen
../starter-kit/.venv/bin/python tools/build.py
../starter-kit/.venv/bin/python tools/fuzz.py bots/final
../starter-kit/.venv/bin/python practice.py bots/final --tables 50
```

## Rounds 1–3: scout (do not overfit)

1. Download hand histories from the team page after each round.
2. Inspect and fix the parser once:

   ```bash
   ../starter-kit/.venv/bin/python tools/field_report.py --inspect history.jsonl.gz
   # edit field_report.kit_hands if fields do not match, then:
   ../starter-kit/.venv/bin/python tools/field_report.py history.jsonl.gz --hero <our name>
   ../starter-kit/.venv/bin/python tools/field_fit.py history.jsonl.gz --hero <our name> \
     --bot bots/final --sweep
   ```

   `bots/final` exposes a top-level `SETTINGS` table (from `tools/core_agent.py`) so
   `--sweep` can move day-of knobs without editing the whole profile by hand.

3. Apply only knob changes that the sweep / report suggest (edit `SETTINGS` or
   `PROFILES["final"]`, then rebuild).
4. Rebuild; promote only if same-seed bench clears ~1 pt over ~1,600 tables:

   ```bash
   ../starter-kit/.venv/bin/python tools/build.py
   ../starter-kit/.venv/bin/python tools/bench.py --hero bots/final --hero bots/final_prev \
     --lineup mixed aggressive ai_field --tables 1600 --seed promote --baseline bots/final_prev
   ```

5. Keep the previous upload ready to roll back.

## Rounds 4–6: ship the best version (71% of score)

Upload the promoted `bots/final`. Do not experiment live without a rollback file.

## Practice line-ups (mini, before kit)

```bash
python3 tools/bench.py --hero bots/final --hero starter --lineup mixed aggressive ai_field \
  --tables 400 --seed overnight --baseline starter
python3 tools/fuzz.py bots/final
```

`ai_field` is the default-assistant-shaped lineup added for overnight prep.
