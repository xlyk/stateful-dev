# Hermes Learning Capture

This directory stores raw candidate learnings for future distillation into `HERMES.md` or `AGENTS.md`.

`learnings.jsonl` is intentionally ignored by git. It is not authoritative memory.

## Entry schema

Each line in `.hermes/learnings.jsonl` should be one JSON object:

```json
{"ts":"2026-04-27T00:00:00Z","type":"pitfall","scope":"tests","claim":"Wrapper tests must parse stdout separately from stderr.","evidence":"A prior test combined streams and missed the production JSON contract.","confidence":"high","promotion_candidate":true}
```

Allowed `type` values:

- `pitfall`
- `command`
- `architecture`
- `convention`
- `safety`
- `unknown`

Allowed `confidence` values:

- `low`
- `medium`
- `high`

## Rules

- Candidate learnings are not authoritative. Verify before relying on them.
- Do not store task progress, run summaries, raw logs, secrets, tokens, or credential paths.
- Promote only durable, verified, future-relevant knowledge to curated memory.
