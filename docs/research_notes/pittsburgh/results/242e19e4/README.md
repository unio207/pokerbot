# Tournament 242e19e4 artifacts

See the [analysis](../../report-242e19e4.md) for findings and limitations.

| File | Contents |
|---|---|
| `242e19e4-audit.json` | Full-file validation, hero metrics, block summaries, and five positive-hand examples |
| `242e19e4-baseline.json` | Previous cached run's summary; that run was a prefix, not a full download |
| `242e19e4-stats.txt` | Detailed stage, position, action, and opponent statistics |
| `242e19e4.pkl` | Aggregate cache produced by `scripts/an.py`, consumed by `scripts/rep.py` |
| `source.json` | Source URL, tournament/team IDs, byte size, and SHA-256 of the raw download |

The raw 155,904,803-byte gzip remains outside Git. Download it to the repository's
ignored `hand-history/` directory with your own authorized API key. From the repo root:

```sh
mkdir -p hand-history
curl --fail-with-body -H "Authorization: Bearer $POKER_API_KEY" \
  -o hand-history/hands-242e19e4-657a-4a4f-9819-85b9850570fa.jsonl.gz \
  "https://pokerbot.sequoiacap.com/tournament/api/teams/0214624e-3ca6-43d9-9a33-ce3e71ab9727/tournaments/242e19e4-657a-4a4f-9819-85b9850570fa/hands"
```

Compare the downloaded file's SHA-256 with `source.json`. The cached report can be
rendered immediately without downloading the raw history:

```sh
python3 docs/research_notes/pittsburgh/scripts/rep.py \
  docs/research_notes/pittsburgh/results/242e19e4/242e19e4.pkl
```

The pickle is a trusted aggregate generated for this report; do not substitute an
untrusted pickle, since Python pickle loading can execute code.

Run the independent audit against the full file:

```sh
python3 docs/research_notes/pittsburgh/scripts/audit_history.py \
  hand-history/hands-242e19e4-657a-4a4f-9819-85b9850570fa.jsonl.gz \
  /tmp/242e19e4-audit.json
```

The audit uses the organizers' `hand-history/read.py`. It locates `starter-kit/`
inside or beside the repository, at `~/starter-kit`, or at `~/work/starter-kit`.
For another location, append `--reader /path/to/starter-kit/hand-history/read.py`.
No API key is read by the analysis scripts.

To regenerate the detailed aggregate:

```sh
python3 docs/research_notes/pittsburgh/scripts/an.py \
  hand-history/hands-242e19e4-657a-4a4f-9819-85b9850570fa.jsonl.gz \
  /tmp/242e19e4.pkl
python3 docs/research_notes/pittsburgh/scripts/rep.py /tmp/242e19e4.pkl
```
