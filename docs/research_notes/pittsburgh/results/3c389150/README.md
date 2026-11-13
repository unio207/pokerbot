# Tournament 3c389150 artifacts

See the [analysis](../../report-3c389150.md). The `tables=10000` endpoint returned
10,003 complete unique tables; all are included. This is a tournament prefix.

| File | Contents |
|---|---|
| `3c389150-audit.json` | Validation, results, block summaries, and five positive-hand examples |
| `3c389150-stats.txt` | Stage, position, preflop-action, and opponent statistics |
| `3c389150.pkl` | Trusted aggregate cache produced by `scripts/an.py` |
| `comparison.json` | Comparison with the previous `242e19e4` cache, including denominators |
| `source.json` | Download URL, requested table limit, raw byte size, and SHA-256 |

The raw download remains outside Git. From the repository root, with your
authorized API key in `POKER_API_KEY`:

```sh
mkdir -p hand-history
curl --fail-with-body -H "Authorization: Bearer $POKER_API_KEY" \
  -o hand-history/hands-3c389150-1178-4e95-bc03-7cc3b0b13282-first-10000.jsonl.gz \
  "https://pokerbot.sequoiacap.com/tournament/api/teams/0214624e-3ca6-43d9-9a33-ce3e71ab9727/tournaments/3c389150-1178-4e95-bc03-7cc3b0b13282/hands?tables=10000"

python3 docs/research_notes/pittsburgh/scripts/audit_history.py \
  hand-history/hands-3c389150-1178-4e95-bc03-7cc3b0b13282-first-10000.jsonl.gz \
  /tmp/3c389150-audit.json
```

The audit locates the organizers' starter-kit history reader inside/beside the
repository or under `~/starter-kit` / `~/work/starter-kit`. Use `--reader` to
specify a different `hand-history/read.py` location.

Render results and compare the committed caches without downloading any hands:

```sh
python3 docs/research_notes/pittsburgh/scripts/rep.py \
  docs/research_notes/pittsburgh/results/3c389150/3c389150.pkl
python3 docs/research_notes/pittsburgh/scripts/compare_runs.py \
  docs/research_notes/pittsburgh/results/242e19e4/242e19e4.pkl \
  docs/research_notes/pittsburgh/results/3c389150/3c389150.pkl \
  /tmp/3c389150-comparison.json
```

To regenerate the aggregate from the raw file:

```sh
python3 docs/research_notes/pittsburgh/scripts/an.py \
  hand-history/hands-3c389150-1178-4e95-bc03-7cc3b0b13282-first-10000.jsonl.gz \
  /tmp/3c389150.pkl
```
