# Agent Instructions

This repo contains `stateful-dev`, local-first safety tooling for stateful Hermes cron coding workers.

## Operating rules

- Use durable project state, not chat/session memory, as execution authority.
- Keep the mapping one coding project -> one repo/worktree -> one state file -> one worker unless the operator approves a different boundary.
- Treat `.agent-state/` as local worker execution state. Do not commit it.
- Todoist is a visibility layer only. State JSON controls execution, locking, attempts, and evidence.
- Do not push, publish, mutate live services, or perform broad external side effects without explicit approval.
- Use conventional commit messages.
- Do not mention AI tooling in commits, PRs, project docs, or operator-facing deliverables unless explicitly requested.

## Development workflow

- Follow RED/GREEN TDD for behavior changes.
- For docs/config-only items, prove the missing contract with a focused hygiene test before creating or editing the deliverable.
- Do not treat syntax errors, typo imports, unrelated environment failures, or already-passing tests as valid RED evidence.
- Stop on unrelated dirty files before editing.
- Prefer small, focused changes with explicit evidence.

## Verified local commands

```bash
uv run pytest -q
uv run ruff check .
uv run stateful-dev --help
```

## Project memory

Read `HERMES.md` before changing worker protocol, memory, cron-gate, HITL, claim, lock, or test behavior. It contains curated project facts and pitfalls.

## Maintaining these instructions

Agents may propose or make edits to `AGENTS.md` and `HERMES.md` only for durable, verified, future-relevant project knowledge.

Allowed additions:

- Stable architecture facts.
- Verified commands for test, lint, build, smoke, or deploy.
- Repeated pitfalls that caused real failures.
- User/project conventions that affect future work.
- Safety rules for state, secrets, live services, or external side effects.

Do not add:

- Task progress or run summaries.
- One-off debugging notes.
- Guesses or unverified assumptions.
- Raw logs.
- Secrets, tokens, private credential paths, or unredacted private URLs.
- Praise, attribution, or notes about which agent did the work.
- Instructions that belong in a specific plan file or issue.

Before editing:

1. Verify the fact from code, tests, docs, live command output, or explicit operator instruction.
2. Prefer updating an existing bullet over adding a near-duplicate.
3. Keep the file concise; remove stale or superseded guidance.
4. If the learning is uncertain, append it to `.hermes/learnings.jsonl` instead of editing curated memory.
5. Run the relevant project checks when the edit affects commands, config, or behavior.

Commit curated memory changes separately when practical, for example:

```bash
git commit -m "docs: update agent project memory"
```
