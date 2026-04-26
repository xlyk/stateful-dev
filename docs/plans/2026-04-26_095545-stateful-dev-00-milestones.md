# Stateful Dev Implementation Plan Index

> **For Hermes:** Use the `stateful-cron-development` skill to execute these milestone plans task-by-task with strict RED/GREEN/REFACTOR.

**Goal:** Build a local-first Python CLI plus Hermes plugin wrapper that makes stateful cron development workers safer and less dependent on manual JSON/state protocol handling.

**Architecture:** Keep the implementation as a normal Python package first. Expose deterministic plan parsing, state validation, locking, transitions, and report rendering through a `stateful-dev` Typer CLI. Add the Hermes plugin wrapper only after the CLI/library is tested.

**Tech Stack:** Python 3.11+, uv, Typer, pytest, Ruff, JSON files, optional Hermes plugin packaging.

**Non-goals for v1:** autonomous code writing, GitHub PR automation, multi-writer SQLite coordination, Textual TUI, model-driven plan rewriting, Poseidon-to-Mac push wake-up signals, and unsupervised live side effects.

**Cron deployment profile:**

```json
{
  "job_name": "stateful-dev-worker",
  "project_root": "/Users/xlyk/Code/stateful-dev",
  "plan_paths": [
    "docs/plans/2026-04-26_095545-stateful-dev-01-foundation.md",
    "docs/plans/2026-04-26_095545-stateful-dev-02-plan-and-state.md",
    "docs/plans/2026-04-26_095545-stateful-dev-03-transitions-and-reports.md",
    "docs/plans/2026-04-26_095545-stateful-dev-04-plugin-and-readiness.md",
    "docs/plans/2026-04-26_121500-poseidon-hitl-05-contracts-and-storage.md",
    "docs/plans/2026-04-26_121500-poseidon-hitl-06-api-and-discord.md",
    "docs/plans/2026-04-26_121500-poseidon-hitl-07-client-and-resume.md",
    "docs/plans/2026-04-26_121500-poseidon-hitl-08-worker-integration-readiness.md"
  ],
  "state_path": "/Users/xlyk/Code/stateful-dev/.agent-state/stateful-dev-worker/state.json",
  "batch_size": 1,
  "max_attempts": 3,
  "lock_timeout_minutes": 60,
  "schedule": "every 5m",
  "allow_commits": true,
  "allow_push": false,
  "allow_cron_reschedule": false,
  "allow_subagents": false,
  "todoist": {
    "enabled": true,
    "project_name": "Stateful Dev",
    "project_id": "6gV7Qgm6PWwrHhM2",
    "sections": ["Immediate", "Readiness Proof", "Hardening", "Future Work"],
    "sync_policy": "create_missing_and_update_status"
  },
  "status_delivery_target": "discord:#notifications",
  "fallback_delivery_target": "origin",
  "notification_policy": "useful_only",
  "completion_behavior": "pause_or_remove",
  "continuation_policy": "operator_decides"
}
```

## Milestones

1. [Foundation](2026-04-26_095545-stateful-dev-01-foundation.md) — package, CLI shell, baseline tests, CI-free local gates.
2. [Plan and state](2026-04-26_095545-stateful-dev-02-plan-and-state.md) — parse milestone tasks and validate durable JSON state.
3. [Transitions and reports](2026-04-26_095545-stateful-dev-03-transitions-and-reports.md) — locking, legal transitions, evidence, compact status output.
4. [Plugin and readiness](2026-04-26_095545-stateful-dev-04-plugin-and-readiness.md) — local Hermes plugin wrapper, docs, smoke proof.
5. [Poseidon HITL contracts and storage](2026-04-26_121500-poseidon-hitl-05-contracts-and-storage.md) — request/event models, SQLite store, audit, one-time consumption.
6. [Poseidon API and Discord ingress](2026-04-26_121500-poseidon-hitl-06-api-and-discord.md) — API handlers, node auth, Discord card and interaction normalization.
7. [Mac mini client and worker resume](2026-04-26_121500-poseidon-hitl-07-client-and-resume.md) — polling client, config, validation-before-consumption, local state recording, bounded subagent context.
8. [Worker integration and readiness proof](2026-04-26_121500-poseidon-hitl-08-worker-integration-readiness.md) — CLI helpers, docs, fake-Poseidon dry run, Discord dogfood checklist.

## Gates

- Focused tests: task-specific `uv run pytest ... -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`
- CLI smoke: `uv run stateful-dev --help`

## Completion audit

After all tasks are mechanically complete, run a separate readiness audit before treating the tool as trusted worker infrastructure. Verify docs, CLI UX, state safety, failure semantics, plugin discovery, and at least one disposable sample state flow.
