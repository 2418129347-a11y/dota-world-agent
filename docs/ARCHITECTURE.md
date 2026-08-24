# Architecture

## Pipeline

```text
collect → normalize → filter date → merge series → deduplicate → rank
        → verify bracket stage → enrich matches → summarize → add reminders
        → render → deliver → report
```

## Modules

| Module | Responsibility |
| --- | --- |
| `collectors.py` | Fetch bounded Steam, OpenDota, and RSS inputs |
| `models.py` | Serializable normalized news model |
| `pipeline.py` | Recency, deduplication, trust scoring, and selection |
| `editorial.py` | Series grouping, China relevance, circle-news policy, player roles, and match commentary |
| `schedule.py` | Tier 1 reminders and exact bracket-stage verification for advancement/elimination copy |
| `summarizers.py` | Optional OpenAI summary plus deterministic fallback |
| `render.py` | Email-safe HTML and plain-text rendering |
| `mailer.py` | QQ SMTP or Resend delivery |
| `cli.py` | Orchestration, target dates, state, reports, and command-line interface |

## Trust boundaries

External titles, summaries, RSS markup, API fields, and model inputs are untrusted. Collection limits response sizes and timeouts. Rendering escapes untrusted HTML. The optional model receives bounded data and structured output requirements.

Sensitive disciplinary or integrity claims require an official source or sufficient independent corroboration. Community signals do not become facts merely because they are popular.

Match-result data alone cannot establish tournament impact. Advancement and elimination language requires a verified calendar entry matching the tournament, both teams, date, and stage; general article prose is never used for this inference.

## State and idempotency

The daily workflow caches `state/seen.json` and records item identifiers plus canonical URLs. A dated backfill uses `--ignore-seen` and does not update daily state. Delivery uses a date-and-recipient-derived idempotency key that does not expose the recipient.

## Configuration

- Sources and basic ranking: `references/sources.json`
- Interests, China tracking, and editorial limits: `references/editorial-policy.json`
- Source verification policy: `references/source-policy.md`
- Output requirements: `references/output-contract.md`
- Tier 1 reminders and stage snapshots: `references/tier1-events.json`
