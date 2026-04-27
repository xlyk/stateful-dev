# Stateful Dev Cron-Gate Backlog Implementation Plan

> For Hermes: use `stateful-dev-cron`, `stateful-dev-helper`, `test-driven-development`, `todoist`, and `writing-clearly-and-concisely` to execute this plan task-by-task.

**Goal:** Implement the script-backed Hermes cron wake-gate architecture for `stateful-dev`, then harden the lifecycle helper commands in ordered phases.

**Project root:** `/Users/xlyk/Code/stateful-dev`

**Todoist project:** `Stateful Dev` (`6gV7Qgm6PWwrHhM2`)

**Execution order:** Follow numeric task order. Treat `Immediate` tasks as current scope. Do not start `Hardening` or `Future Work` tasks until all prior numbered tasks are terminal unless a later task is strictly required to complete the current task.

**Non-goals:**
- Do not turn `stateful-dev` into a coding-agent runtime, Git pusher, cron scheduler, Todoist authority, or multi-repo orchestrator.
- Do not add live external side effects without explicit operator approval.
- Do not implement multiple wake-decision engines. `stateful-dev cron-gate` owns deterministic local wake/skip decisions; Hermes scripts are thin adapters.

**Global gates for code tasks:**
- Strict TDD: write/verify RED before production code.
- Focused GREEN test for the changed behavior.
- Full suite: `uv run pytest -q`.
- Lint: `uv run ruff check .`.
- Build/package gate when CLI packaging, plugin manifests, docs package data, or entrypoints change: `uv build`.
- Commit only after gates pass, using a conventional commit message.

---

## Task 1: Define cron-gate wake/skip JSON contract

**Todoist ID:** `6gVM6r23VPpmqwp2`
**Todoist URL:** https://app.todoist.com/app/task/01-define-cron-gate-wakeskip-json-contract-6gVM6r23VPpmqwp2
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Define the stable integration contract between Hermes cron scripts and stateful-dev: wakeAgent true/false, mode values, required context fields, stdout/stderr convention, last non-empty JSON line rule, nonzero exit semantics, and blocker vs script-bug behavior. This must land before claim/cron-gate implementation so migration does not invent the schema ad hoc.

**Acceptance criteria:**
- Contract is documented in `docs/` or a suitable project reference file.
- Contract defines `wakeAgent`, `mode`, required context fields, stdout/stderr rules, last-line JSON behavior, nonzero exit semantics, and blocker-vs-script-bug behavior.
- Contract includes examples for wake, skip, and blocker payloads.
- A focused test or docs validation check fails before the document/update and passes after it when practical.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 2: MVP: Add minimal claim/next command for one stateful-dev item

**Todoist ID:** `6gV9qj9Q668JxqJ2`
**Todoist URL:** https://app.todoist.com/app/task/02-mvp-add-minimal-claimnext-command-for-one-stateful-dev-item-6gV9qj9Q668JxqJ2
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Foundation primitive. Implement stateful-dev claim/next: validate state, respect fresh locks, return existing active item or atomically claim one pending/failed_retryable item, increment attempts, recompute counts, record run metadata, and emit compact JSON for cron-gate. Keep HITL-specific enforcement out except reserved output fields.

**Acceptance criteria:**
- `stateful-dev claim` or equivalent command exists with JSON output.
- It validates state, respects fresh locks, resumes active items, claims one eligible item atomically, increments attempts, and recomputes counts.
- Tests cover pending, failed_retryable, active item, fresh lock, invalid state, terminal states, attempts, and JSON shape.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 3: Add stateful-dev cron-gate command for Hermes wake decisions

**Todoist ID:** `6gVM2qjW863MPQR2`
**Todoist URL:** https://app.todoist.com/app/task/03-add-stateful-dev-cron-gate-command-for-hermes-wake-decisions-6gVM2qjW863MPQR2
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Depends on [01] and [02]. Implement `stateful-dev cron-gate --state --project-root --worker-id --run-id --json`. It owns generic local wake/skip decisions: doctor/status, lock state, git branch/status, active item, eligible item, complete/no-work, blockers, and claim when safe. It emits the contract-defined wakeAgent JSON.

**Acceptance criteria:**
- `stateful-dev cron-gate --state --project-root --worker-id --run-id --json` exists.
- It emits the contract-defined wake/skip/blocker JSON.
- It owns generic local state/git/lock/claim decisions and does not duplicate them in wrapper scripts.
- Tests cover no-work, blocker, active item, eligible item, dirty git handling, and invalid state.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 4: Add per-worker Hermes cron gate wrapper scripts

**Todoist ID:** `6gVM2qqCxqH6h5q2`
**Todoist URL:** https://app.todoist.com/app/task/04-add-per-worker-hermes-cron-gate-wrapper-scripts-6gVM2qqCxqH6h5q2
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Create thin ~/.hermes/scripts/stateful_dev_<worker>_gate.py adapters. Each hardcodes WORKER_ID, PROJECT_ROOT, and STATE_PATH, chdirs into the project, calls `stateful-dev cron-gate`, and preserves the last non-empty stdout line as wakeAgent JSON. Do not duplicate claim/status/lock logic in wrappers.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 5: Add Poseidon HITL polling to cron-gate preflight path

**Todoist ID:** `6gVJvfXWm2vW6RFR`
**Todoist URL:** https://app.todoist.com/app/task/05-add-poseidon-hitl-polling-to-cron-gate-preflight-path-6gVJvfXWm2vW6RFR
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Re-scoped from a standalone preflight script. Add Poseidon/HITL polling as an optional preflight capability in the cron-gate/wrapper path. Poll before claim/wake, validate worker/request/item/state hash, stage matching events locally, fail closed when policy requires it, and avoid becoming a second wake-decision engine.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 6: Dogfood one real worker item through script-backed wake gate

**Todoist ID:** `6gVJvgH29VRFQqxR`
**Todoist URL:** https://app.todoist.com/app/task/06-dogfood-one-real-worker-item-through-script-backed-wake-gate-6gVJvgH29VRFQqxR
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Run before broad migration. Prove the script runs before prompt construction, Poseidon poll/preflight happens before claim/wake when enabled, no-work emits {"wakeAgent": false}, work wakes Hermes with exactly one claimed/provided item, state remains valid, and notification is useful.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 7: Add smoke tests for Hermes cron script wake/skip behavior

**Todoist ID:** `6gVM2rj8Xv5Fp6FR`
**Todoist URL:** https://app.todoist.com/app/task/07-add-smoke-tests-for-hermes-cron-script-wakeskip-behavior-6gVM2rj8Xv5Fp6FR
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
Codify Hermes scheduler behavior before migration: a script outputting {"wakeAgent": false} skips the LLM and suppresses delivery; non-skip output is injected under Script Output; relative script paths resolve under ~/.hermes/scripts; workdir and timeout behavior are known.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 8: Migrate stateful-dev cron workers to script-backed wake gates

**Todoist ID:** `6gVM2r5WP7889932`
**Todoist URL:** https://app.todoist.com/app/task/08-migrate-stateful-dev-cron-workers-to-script-backed-wake-gates-6gVM2r5WP7889932
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
After [06] and [07], update each relevant Hermes cron job with script=stateful_dev_<worker>_gate.py, keep workdir and restricted toolsets, run one no-work skip test and one work wake test, verify state remains valid, and avoid recursive cron management toolsets.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 9: Replace stateful-dev worker prompts with thin executor prompts

**Todoist ID:** `6gVM2r7cjcpgrrF2`
**Todoist URL:** https://app.todoist.com/app/task/09-replace-stateful-dev-worker-prompts-with-thin-executor-prompts-6gVM2r7cjcpgrrF2
**Section:** Immediate
**Labels:** stateful-dev-cron-gate

**Requirement:**
After gate migration, reduce worker prompts to executor instructions: treat Script Output as authoritative, process exactly the claimed/provided item, do not select another item, use stateful-dev transitions, enforce RED/GREEN/full-suite/lint, commit only after gates, do not push, and do not manage cron jobs.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 10: Add lock status and stale-lock recovery commands

**Todoist ID:** `6gV9qjXphGrGmJV2`
**Todoist URL:** https://app.todoist.com/app/task/10-add-lock-status-and-stale-lock-recovery-commands-6gV9qjXphGrGmJV2
**Section:** Hardening
**Labels:** none

**Requirement:**
Early hardening after claim is live. Implement lock status and lock recover with stale-time checks, backup-before-write, before/after doctor validation, and optional failed_retryable recovery for stale in_progress items. Refuse fresh-lock recovery.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 11: Add backup command and doctor --fix-counts safeguard

**Todoist ID:** `6gV9qjh4r4RGcMWR`
**Todoist URL:** https://app.todoist.com/app/task/11-add-backup-command-and-doctor-fix-counts-safeguard-6gV9qjh4r4RGcMWR
**Section:** Hardening
**Labels:** none

**Requirement:**
Implement stateful-dev backup --state STATE.json --label LABEL --json and doctor --fix-counts --backup. Only fix mechanical count drift; never mutate item statuses automatically.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 12: Add run lifecycle commands and durable run summary files

**Todoist ID:** `6gV9qjHqXrPMMQRR`
**Todoist URL:** https://app.todoist.com/app/task/12-add-run-lifecycle-commands-and-durable-run-summary-files-6gV9qjHqXrPMMQRR
**Section:** Hardening
**Labels:** none

**Requirement:**
Implement run start/finish/fail commands that own .agent-state/<job>/runs/<run-id>.json and optional events JSONL/log paths. Stop requiring agents to invent run summary shape. Keep this below cron-gate MVP unless HITL poll markers require it earlier.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 13: Add evidence record commands for RED, GREEN, full-suite, and lint gates

**Todoist ID:** `6gV9qjQMH26P8JCR`
**Todoist URL:** https://app.todoist.com/app/task/13-add-evidence-record-commands-for-red-green-full-suite-and-lint-gates-6gV9qjQMH26P8JCR
**Section:** Hardening
**Labels:** none

**Requirement:**
Implement stateful-dev record red|green|full-suite|lint with command, exit code, output/output-file, and structured result fields. Use recorded evidence for legal transitions to reduce hand-written JSON quoting errors. Record evidence; do not turn this into a test runner.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 14: Patch stateful-dev skills for script-backed cron gates

**Todoist ID:** `6gVM2rM9g8cP26CR`
**Todoist URL:** https://app.todoist.com/app/task/14-patch-stateful-dev-skills-for-script-backed-cron-gates-6gVM2rM9g8cP26CR
**Section:** Hardening
**Labels:** stateful-dev-cron-gate

**Requirement:**
Patch stateful-dev-cron and stateful-dev-helper after first dogfood proves the real shape. Document script-backed wake gates, claim/cron-gate commands, wakeAgent semantics, ~/.hermes/scripts restrictions, per-worker wrappers, and the scheduler/adapter/stateful-dev/agent boundary.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 15: Document the script-backed cron gate runbook

**Todoist ID:** `6gVM2rVG2GcVC6V2`
**Todoist URL:** https://app.todoist.com/app/task/15-document-the-script-backed-cron-gate-runbook-6gVM2rVG2GcVC6V2
**Section:** Hardening
**Labels:** stateful-dev-cron-gate

**Requirement:**
Add docs/cron-gate.md and README/usage updates covering architecture, wrapper examples, cron job config, wake/skip JSON contract, failure modes, local smoke tests, and migration steps for existing workers. Base this on dogfood evidence, not only design intent.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 16: Add complete/audit command for safe worker shutdown decisions

**Todoist ID:** `6gV9qjwR7gfwv2X2`
**Todoist URL:** https://app.todoist.com/app/task/16-add-completeaudit-command-for-safe-worker-shutdown-decisions-6gV9qjwR7gfwv2X2
**Section:** Future Work
**Labels:** none

**Requirement:**
Implement complete or audit command that verifies no active/retryable work remains, doctor passes, lock is clear, latest gates exist, Todoist visibility is reconciled, and next action is pause/remove worker or create follow-up plan.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 17: Add operator handoff CLI command

**Todoist ID:** `6gV9qjvFx9P8HXqR`
**Todoist URL:** https://app.todoist.com/app/task/17-add-operator-handoff-cli-command-6gV9qjvFx9P8HXqR
**Section:** Future Work
**Labels:** none

**Requirement:**
Expose render_operator_handoff through stateful-dev handoff with question, why, recommended answer, allowed next action, and item context. Output plain text and JSON.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 18: Add plan lint, plan parse, and state sync-plans commands

**Todoist ID:** `6gV9qjmqxFR3vmc2`
**Todoist URL:** https://app.todoist.com/app/task/18-add-plan-lint-plan-parse-and-state-sync-plans-commands-6gV9qjmqxFR3vmc2
**Section:** Future Work
**Labels:** none

**Requirement:**
Expose plan lint/parse JSON output and state sync-plans --append-missing. Detect missing task headings, duplicate generated item IDs, plan/state drift, and disappeared plan items.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 19: Add deployment profile validation

**Todoist ID:** `6gV9qm3rcg26qp9R`
**Todoist URL:** https://app.todoist.com/app/task/19-add-deployment-profile-validation-6gV9qm3rcg26qp9R
**Section:** Future Work
**Labels:** stateful-dev-cron-gate

**Requirement:**
Re-scoped from profile validation plus prompt rendering. Implement profile validate for deployment_profile.json only: project root, plan paths, state path, gates, Todoist mapping, notification policy, script wrapper config, cron permissions, and secret-file references. Prompt rendering is tracked separately in [20].

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 20: Add worker prompt rendering only after profile validation

**Todoist ID:** `6gVM6rM5v3jJfwgR`
**Todoist URL:** https://app.todoist.com/app/task/20-add-worker-prompt-rendering-only-after-profile-validation-6gVM6rM5v3jJfwgR
**Section:** Future Work
**Labels:** stateful-dev-cron-gate

**Requirement:**
Split from deployment profile validation. Add minimal prompt rendering only after profile validation is stable and only if it avoids duplicated worker prompts. Keep rendering thin: executor prompt templates, no scheduling/orchestration logic, no agent invocation.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 21: Add Hermes plugin parity for stable stateful-dev lifecycle commands

**Todoist ID:** `6gV9qm6C4F5pXG72`
**Todoist URL:** https://app.todoist.com/app/task/21-add-hermes-plugin-parity-for-stable-stateful-dev-lifecycle-commands-6gV9qm6C4F5pXG72
**Section:** Future Work
**Labels:** stateful-dev-cron-gate

**Requirement:**
Do late, after CLI/library commands are stable. Expose thin plugin tools backed by tested library code for status, plan parse/lint, claim, record, transition, lock status/recover, handoff, and complete/audit.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.

## Task 22: Optional: pass Hermes cron job metadata to scripts

**Todoist ID:** `6gVM2rvXjXCrQGcR`
**Todoist URL:** https://app.todoist.com/app/task/22-optional-pass-hermes-cron-job-metadata-to-scripts-6gVM2rvXjXCrQGcR
**Section:** Future Work
**Labels:** stateful-dev-cron-gate

**Requirement:**
Optional Hermes scheduler improvement. Consider passing HERMES_CRON_JOB_ID, HERMES_CRON_JOB_NAME, HERMES_CRON_WORKDIR, HERMES_CRON_DELIVER, and HERMES_CRON_SCHEDULE to scripts so one generic stateful_dev_gate.py can replace per-worker wrappers. Defer until wrappers prove painful.

**Acceptance criteria:**
- Implementation satisfies the Todoist requirement above.
- New behavior is covered with focused tests where applicable.
- `uv run pytest -q` and `uv run ruff check .` pass before success.
- State is updated through `stateful-dev transition` with RED/GREEN/full-suite/lint evidence when this task is executed by a cron worker.

**Notes:**
- Keep implementation small and composable.
- Preserve the architecture boundary: Hermes cron schedules, `~/.hermes/scripts` adapts, `stateful-dev` manages lifecycle state, and the Hermes agent performs coding work.
