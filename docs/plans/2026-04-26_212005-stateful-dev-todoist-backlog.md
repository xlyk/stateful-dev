# Stateful Dev Todoist Backlog Implementation Plan

> **For Hermes:** Use stateful-dev-cron and stateful-dev-helper to execute this plan task-by-task.

**Goal:** Implement the active Todoist backlog for `xlyk/stateful-dev` so cron development workers need fewer hand-written state edits and less bespoke run bookkeeping.

**Architecture:** Keep `stateful-dev` as a small tested Python CLI/library plus thin Hermes plugin wrappers. Add state/lifecycle primitives incrementally with strict RED/GREEN/full-suite/lint evidence for each code item.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff, Hermes plugin files under `plugins/stateful-dev`.

**Todoist Project:** `Stateful Dev` (`6gV7Qgm6PWwrHhM2`).

---

## Task 1: Replace stale stateful-cron-development references in docs and fixtures

**Todoist:** `6gV9qj4MWgJgrMJR`

**Objective:** Update remaining project docs and fixtures to use `stateful-dev-cron` and mention `stateful-dev-helper` for state mutation/validation.

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/*.md`
- Modify: `tests/**/*.py` fixtures/assertions as needed

**Required cycle:**
1. Write or update a focused docs/fixture test that fails on stale `stateful-cron-development` references.
2. Run the focused test and verify the failure is specifically the stale reference.
3. Update docs/fixtures only.
4. Run the focused test, full suite, `uv run ruff check .`, and commit with `docs:` or `test:` conventional commit.

## Task 2: Add stateful-dev status command for worker lifecycle dashboard

**Todoist:** `6gV9qj8XrjqQMrm2`

**Objective:** Implement `stateful-dev status --state STATE.json` with plain and JSON output for worker lifecycle decisions.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/status.py`
- Test: `tests/test_status.py`

**Acceptance:** Reports counts, active item, next eligible item, lock state, completion boolean, last run summary when available, and suggested next action.

**Required cycle:** RED focused CLI/library test, GREEN implementation, full suite, lint, commit.

## Task 3: Add backup command and doctor --fix-counts safeguard

**Todoist:** `6gV9qjh4r4RGcMWR`

**Objective:** Add safe mechanical state backups and count-drift repair without mutating item statuses.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/backups.py`
- Modify: `src/stateful_dev/state.py`
- Test: `tests/test_backups.py`
- Test: `tests/test_doctor_cli.py`

**Acceptance:** `backup --state STATE.json --label LABEL --json` writes a timestamped sibling backup. `doctor --fix-counts --backup` fixes only count drift, refuses status changes, writes backup first, and validates after writing.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 4: Add plan lint, plan parse, and state sync-plans commands

**Todoist:** `6gV9qjmqxFR3vmc2`

**Objective:** Expose plan parsing/linting and append-missing state synchronization through the CLI.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify: `src/stateful_dev/plan_parser.py`
- Modify/Create: `src/stateful_dev/plan_lint.py`
- Modify: `src/stateful_dev/state.py`
- Test: `tests/test_plan_parser.py`
- Test: `tests/test_plan_lint_cli.py`
- Test: `tests/test_state_sync_plans.py`

**Acceptance:** `plan parse`, `plan lint`, and `state sync-plans --append-missing` produce JSON output; detect missing task headings, duplicate generated item IDs, plan/state drift, and disappeared plan items.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 5: Add run lifecycle commands and durable run summary files

**Todoist:** `6gV9qjHqXrPMMQRR`

**Objective:** Standardize run start/finish/fail commands and `.agent-state/<job>/runs/<run-id>.json` shape.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/runs.py`
- Test: `tests/test_runs.py`

**Acceptance:** `run start`, `run finish`, and `run fail` own durable run summaries and optional events JSONL/log paths so agents do not invent summary schema.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 6: Add atomic claim command for next stateful-dev work item

**Todoist:** `6gV9qj9Q668JxqJ2`

**Objective:** Implement safe one-item claiming for cron workers.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/claiming.py`
- Modify: `src/stateful_dev/locking.py`
- Modify: `src/stateful_dev/state.py`
- Test: `tests/test_claiming.py`

**Acceptance:** `claim --state STATE.json --run-id RUN --lock-timeout N --json` validates state, respects fresh locks, selects one pending/retryable item, marks it `in_progress`, increments attempts, records run metadata, and returns exact item context.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 7: Add evidence record commands for RED, GREEN, full-suite, and lint gates

**Todoist:** `6gV9qjQMH26P8JCR`

**Objective:** Reduce hand-written JSON evidence errors through structured `record` commands.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/evidence.py`
- Modify: `src/stateful_dev/transitions.py`
- Test: `tests/test_evidence_cli.py`
- Test: `tests/test_transitions.py`

**Acceptance:** `record red|green|full-suite|lint` captures command, exit code, output/output-file, and structured result fields; legal transitions can consume recorded evidence.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 8: Add lock status and stale-lock recovery commands

**Todoist:** `6gV9qjXphGrGmJV2`

**Objective:** Make lock inspection and stale recovery backup-first, age-checked, and doctor-validated.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify: `src/stateful_dev/locking.py`
- Modify/Create: `src/stateful_dev/lock_recovery.py`
- Test: `tests/test_locking.py`
- Test: `tests/test_lock_recovery_cli.py`

**Acceptance:** `lock status` reports current lock metadata. `lock recover` refuses fresh locks, backs up before write, validates before/after, and can optionally move stale `in_progress` items to `failed_retryable`.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 9: Add operator handoff CLI command

**Todoist:** `6gV9qjvFx9P8HXqR`

**Objective:** Expose standardized operator questions and fresh-agent handoffs.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/handoff.py`
- Test: `tests/test_handoff_cli.py`

**Acceptance:** `handoff` accepts question, why, recommended answer, allowed next action, and item context; outputs plain text and JSON with a copy/paste-ready block.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 10: Add complete/audit command for safe worker shutdown decisions

**Todoist:** `6gV9qjwR7gfwv2X2`

**Objective:** Verify shutdown readiness and suggest pause/remove/follow-up actions.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/audit.py`
- Test: `tests/test_audit_cli.py`

**Acceptance:** `complete` or `audit` verifies no active/retryable work remains, doctor passes, lock is clear, latest gates exist, and next action is pause/remove worker or create follow-up plan.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 11: Add deployment profile validation and worker prompt rendering

**Todoist:** `6gV9qm3rcg26qp9R`

**Objective:** Validate deployment profiles and render worker prompts from templates.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/profiles.py`
- Modify/Create: `src/stateful_dev/prompt_rendering.py`
- Test: `tests/test_profiles.py`
- Test: `tests/test_prompt_rendering.py`

**Acceptance:** `profile validate` and `prompt render` handle `deployment_profile.json` and `worker_prompt.md`; validate project root, plan paths, state path, gates, Todoist mapping, notification policy, and cron permissions.

**Required cycle:** RED focused tests, GREEN implementation, full suite, lint, commit.

## Task 12: Add Hermes plugin parity for stateful-dev lifecycle commands

**Todoist:** `6gV9qm6C4F5pXG72`

**Objective:** Expose thin plugin tools backed by tested library code for the new lifecycle commands.

**Files:**
- Modify: `plugins/stateful-dev/tools.py`
- Modify: `plugins/stateful-dev/schemas.py`
- Modify: `plugins/stateful-dev/__init__.py`
- Test: `tests/test_plugin_tools.py`
- Test: `tests/test_plugin_layout.py`

**Acceptance:** Plugin tools cover status, plan parse/lint, claim, record, transition, lock status/recover, handoff, and complete/audit without duplicating core logic.

**Required cycle:** RED focused plugin tests, GREEN implementation, full suite, lint, `uv build`, commit.
