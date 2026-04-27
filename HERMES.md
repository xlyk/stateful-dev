# Hermes Project Memory

This file is curated project memory for Hermes/stateful-dev coding agents. It is authoritative only for durable project facts, recurring pitfalls, verified commands, and safety constraints. It is not a run log.

## Purpose

`stateful-dev` is local-first helper tooling for stateful Hermes cron development workers. It turns worker protocol into executable checks: plan parsing, durable JSON state, validation, legal transitions, TDD evidence, reports, locks, cron-gate preflight, HITL polling, and claim safety.

## Invariants

- Durable local state is the source of truth for worker execution.
- `.agent-state/` is local execution state and must stay untracked.
- A worker should process at most one eligible item per run by default.
- Production code changes require valid RED evidence before GREEN unless the item is explicitly non-code and has a focused hygiene test.
- Todoist is visibility only; it must not be used as execution authority.
- Remote services such as Poseidon must route by durable worker/request/state identifiers, not Hermes cron IDs.
- Cron worker prompts must be self-contained because each run starts fresh.

## Architecture

- Hermes cron is the scheduler.
- `stateful-dev` owns deterministic local lifecycle mechanics: state validation, locking, item selection, claim gating, evidence transitions, and compact reports.
- Cron scripts under `~/.hermes/scripts/` are thin wake/preflight adapters; they should not reimplement claim/status logic.
- Poseidon is the HITL mailbox. It stores operator requests/events and should not own local worker state transitions.
- HITL-enabled workers should poll for operator events before claim/resume. Prompt wording alone is not enough; the guarantee belongs in deterministic `stateful-dev` commands.

## Verified local commands

```bash
uv run pytest -q
uv run ruff check .
uv run stateful-dev --help
```

## State and worker model

- Preferred state path shape: `.agent-state/<worker>/state.json` plus sibling run, patch, lock, and HITL inbox directories as needed.
- Use `stateful-dev doctor --state <state> --json` before trusting a state file.
- Use `stateful-dev transition` rather than hand-editing state whenever possible.
- Manual state edits are recovery operations only: pause the worker, back up the state file, make the smallest change, recompute counts, and run doctor.
- When the prompt and state disagree about the next item, state wins unless doctor proves the state is invalid or the operator approves repair.

## Testing policy

- Default repository tests must be safe on a clean checkout.
- Tests that depend on Kyle's live Hermes install, `~/.hermes/scripts`, real worker state files, Poseidon, Todoist, Discord, or other live services are local integration tests and must be gated or isolated.
- Wrapper-script tests should assert intended stdout/stderr behavior separately. Do not combine streams when the production contract parses stdout JSON.
- Tests for generated Hermes wrapper scripts should use disposable temporary state and scripts, not mutate live worker state.
- A docs/config deliverable still needs a focused RED/GREEN hygiene test when it is part of an executable worker item.

## Operational pitfalls

- Current Hermes cron script wake behavior depends on the last non-empty stdout line being JSON with `wakeAgent`; `wakeAgent: false` skips silently.
- A blocker/error contract must wake a notify-only path or scheduler behavior must change; do not assume `wakeAgent: false` will notify.
- Do not migrate real workers to script-backed cron gates until wake, skip, blocker, nonzero exit, stdout, and stderr behavior has been smoke-tested against the live scheduler.
- Do not create duplicate workers to bypass stale locks. Recover the exact worker with evidence.
- Do not put broad skills into worker prompts by default. Prefer a thin executor prompt plus project memory, then load specialized skills only when the current item needs them.

## Open design constraints

- Project-level memory should be loaded into stateful-dev worker prompts without flooding the prompt.
- Raw candidate learnings should be captured separately from curated memory and reviewed before promotion.
- Worker skill loading should become item-scoped or capability-scoped so most runs are not dominated by unused skill text.

## Maintaining this file

Agents may update this file when they discover durable project knowledge.

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
4. If the learning is uncertain, append it to `.hermes/learnings.jsonl` instead of editing this file.
5. Run the relevant project checks when the edit affects commands, config, or behavior.

Commit curated memory changes separately when practical, for example:

```bash
git commit -m "docs: update agent project memory"
```
