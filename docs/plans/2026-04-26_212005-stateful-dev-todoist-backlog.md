# Stateful Dev Todoist Backlog Implementation Plan

> **For Hermes:** Use `stateful-dev-cron` and `stateful-dev-helper` to execute this plan task-by-task.
> **For MiniMax workers:** Follow each task's MiniMax handoff exactly. Do not infer scope from Todoist text alone.

**Goal:** Implement the active Todoist backlog for `xlyk/stateful-dev` so cron development workers need fewer hand-written state edits and less bespoke run bookkeeping.

**Architecture:** Keep `stateful-dev` as a small tested Python CLI/library plus thin Hermes plugin wrappers. Add state/lifecycle primitives incrementally with strict RED/GREEN/full-suite/lint evidence for each item.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff, Hermes plugin files under `plugins/stateful-dev`.

**Todoist Project:** `Stateful Dev` (`6gV7Qgm6PWwrHhM2`).

**Current worker state:** `.agent-state/stateful-dev-todoist-backlog-worker/state.json` owns execution state. Tasks 1 and 2 are already succeeded; future cron workers should start from the next eligible pending item in state, not from the top of this file.

---

## MiniMax handoff contract for delegated cron-worker tasks

Every pending task below is written for a MiniMax implementation worker running inside a stateful cron worker. MiniMax is the implementer, not the planner or reviewer.

### Required repo discovery before editing

Before changing files for any task:
1. Read `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `README.md`, and nearby docs if present.
2. Inspect existing code in `src/stateful_dev/`, tests in `tests/`, and plugin files in `plugins/stateful-dev/` when relevant.
3. Run or inspect the current command surface with `uv run stateful-dev --help` and, when relevant, subcommand `--help`.
4. Identify the focused test command for the task.
5. Report discovered conventions in 3-6 bullets in the run summary.

### Implementation constraints

- Keep each change minimal and localized.
- Follow existing Typer command style, typed helper functions, JSON output conventions, and pytest patterns.
- Preserve backwards compatibility for existing commands: `version`, `init`, `doctor`, `status`, `transition`, and `report`.
- Do not change secrets, webhook URLs, credential paths, auth flows, deployment config, cron schedules, or unrelated state files.
- Do not push.
- Do not start, resume, pause, remove, or create cron jobs from an implementation run.
- If a task appears to require broad architecture changes, public API breakage, or durable state mutation outside the task's scope, stop and mark the item `needs_review` with a precise operator question.

### TDD and verification loop

For every code task:
1. Add or update a focused failing test that captures the requirement.
2. Run the focused test and verify RED for the intended missing behavior. Syntax errors, typo imports, and broken environments are not valid RED.
3. Implement the smallest change that makes the focused test pass.
4. Run the focused test and verify GREEN.
5. Run `uv run pytest -q`.
6. Run `uv run ruff check .`.
7. Run `uv build` when packaging, plugin, template, or manifest behavior changes.
8. Commit only after all required gates pass.

### Final report format

Return exactly this structure in the cron run summary:

```md
### Summary
- <2-5 bullets>

### Files changed
- `<path>`: <why>

### Tests run
- `<command>` — <pass/fail and key output>

### State/Todoist
- State item: `<item-id>` -> `<new-status>`
- Todoist task: `<id>` -> `<open|completed|unchanged>`

### Deviations from plan
- None, or <specific deviation and why>

### Remaining risks
- None, or <specific risk>
```

---

## Task 1: Replace stale legacy cron-skill references in docs and fixtures

**Status:** Already succeeded in state. Do not delegate again unless state explicitly marks this item retryable.

**Todoist:** `6gV9qj4MWgJgrMJR`

**Objective:** Update remaining project docs and fixtures to use `stateful-dev-cron` and mention `stateful-dev-helper` for state mutation/validation.

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/*.md`
- Modify: `tests/**/*.py` fixtures/assertions as needed

**Required cycle:**
1. Write or update a focused docs/fixture test that fails on stale legacy cron-skill references.
2. Run the focused test and verify the failure is specifically the stale reference.
3. Update docs/fixtures only.
4. Run the focused test, full suite, `uv run ruff check .`, and commit with `docs:` or `test:` conventional commit.

## Task 2: Add stateful-dev status command for worker lifecycle dashboard

**Status:** Already succeeded in state. Do not delegate again unless state explicitly marks this item retryable.

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

### MiniMax implementation handoff

#### Objective
Implement safe state backup support and a guarded `doctor --fix-counts --backup` repair path.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/backups.py`
- `src/stateful_dev/state.py`
- `src/stateful_dev/locking.py` only if existing atomic write helpers are reused or lightly extended
- `tests/test_backups.py`
- `tests/test_doctor_cli.py`

Allowed changes:
- Add a `backup` CLI command.
- Extend `doctor` with `--fix-counts` and `--backup` options.
- Add small library helpers for backup path generation and count replacement.

Non-goals:
- Do not change item statuses automatically.
- Do not introduce a new state schema version.
- Do not alter transition evidence rules.
- Do not touch cron job configuration.

#### Required repo discovery before editing
- Inspect `write_json_atomic()` in `src/stateful_dev/locking.py`.
- Inspect `validate_state()` and count recomputation in `src/stateful_dev/state.py`.
- Inspect current Typer command tests in `tests/test_doctor_cli.py` and `tests/test_cli.py`.

#### TDD / verification loop
1. Write a failing backup CLI test that calls `uv run stateful-dev backup --state <state> --label <label> --json` and expects a sibling backup file with unchanged content.
2. Write a failing doctor test where only `counts` drift; `doctor --fix-counts --backup --json` must create a backup, repair counts, and exit 0.
3. Add a failing test proving `doctor --fix-counts` does not repair invalid item statuses or malformed item fields.
4. Implement the minimal helpers and CLI options.
5. Run the focused tests, then `uv run pytest -q`, then `uv run ruff check .`.

#### Acceptance criteria
- [ ] `backup --state STATE.json --label LABEL --json` returns JSON containing at least `backup_path` and `state_path`.
- [ ] Backup filenames are deterministic enough to audit and safe against path traversal in labels.
- [ ] `doctor --fix-counts --backup --json` repairs only mechanical count drift.
- [ ] Invalid statuses and malformed item fields remain errors and are not silently repaired.
- [ ] State writes use the existing atomic write pattern.
- [ ] Tests and lint pass.

## Task 4: Add plan lint, plan parse, and state sync-plans commands

**Todoist:** `6gV9qjmqxFR3vmc2`

### MiniMax implementation handoff

#### Objective
Expose plan parsing, plan linting, and append-only state synchronization for newly added plan tasks.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/plan_parser.py`
- `src/stateful_dev/plan_lint.py`
- `src/stateful_dev/state.py`
- `tests/test_plan_parser.py`
- `tests/test_plan_lint_cli.py`
- `tests/test_state_sync_plans.py`

Allowed changes:
- Add a Typer sub-app or grouped commands for `plan parse` and `plan lint`.
- Add a `state sync-plans --append-missing` command.
- Add library helpers for comparing parsed plan items with existing state item IDs.

Non-goals:
- Do not reorder existing state items.
- Do not delete state items for disappeared plan tasks.
- Do not mutate terminal item statuses.
- Do not complete Todoist tasks.

#### Required repo discovery before editing
- Inspect `parse_plan_tasks()` and item ID generation rules.
- Inspect `_build_initial_state()` for item shape.
- Inspect existing tests for JSON CLI output conventions.

#### TDD / verification loop
1. Add failing `plan parse --json` tests for a plan with two `## Task N:` headings.
2. Add failing `plan lint --json` tests for missing task headings and duplicate generated item IDs.
3. Add failing `state sync-plans --append-missing --json` tests proving new tasks append and existing item order/statuses remain unchanged.
4. Implement minimal parser/lint/sync helpers.
5. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] `plan parse --plan PLAN.md --json` emits parsed tasks with titles, numbers, plan paths, and item IDs.
- [ ] `plan lint --plan PLAN.md --json` reports missing task headings and duplicate generated item IDs.
- [ ] `state sync-plans --state STATE.json --plan PLAN.md --append-missing --json` appends missing items only.
- [ ] Disappeared plan items are reported as drift but not removed.
- [ ] Existing state order, statuses, attempts, evidence, and Todoist IDs are preserved.
- [ ] Tests and lint pass.

## Task 5: Add run lifecycle commands and durable run summary files

**Todoist:** `6gV9qjHqXrPMMQRR`

### MiniMax implementation handoff

#### Objective
Standardize run start/finish/fail commands and the durable run summary JSON shape.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/runs.py`
- `src/stateful_dev/locking.py` only if existing atomic write helpers are reused
- `tests/test_runs.py`

Allowed changes:
- Add `run start`, `run finish`, and `run fail` commands.
- Create `.agent-state/<job>/runs/<run-id>.json` summaries via explicit `--runs-dir` or state-derived default.
- Support optional events JSONL/log path fields.

Non-goals:
- Do not claim work items.
- Do not transition item statuses.
- Do not manage cron schedules.
- Do not invent a complex event store beyond optional paths and compact JSON metadata.

#### Required repo discovery before editing
- Inspect `status.py` to see how latest run summary is expected to be discovered or represented.
- Inspect `reports.py` for summary fields currently consumed by `stateful-dev report`.
- Inspect current tests for temporary path usage.

#### TDD / verification loop
1. Add failing tests for `run start --state STATE.json --run-id RUN --json` creating a run summary.
2. Add failing tests for `run finish` recording processed items, gates, and next action.
3. Add failing tests for `run fail` recording error context without marking the whole worker complete.
4. Implement minimal run summary helpers and CLI commands.
5. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] Run summaries are written atomically under a `runs/` directory.
- [ ] `run start` refuses to overwrite an existing run ID unless an explicit safe option exists.
- [ ] `run finish` records processed items, gates, Todoist visibility, state path, and next action.
- [ ] `run fail` records an error summary suitable for operator review.
- [ ] Existing `report` behavior remains compatible.
- [ ] Tests and lint pass.

## Task 6: Add atomic claim command for next stateful-dev work item

**Todoist:** `6gV9qj9Q668JxqJ2`

### MiniMax implementation handoff

#### Objective
Implement an atomic `claim` command that selects exactly one eligible work item for a cron run.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/claiming.py`
- `src/stateful_dev/locking.py`
- `src/stateful_dev/state.py`
- `tests/test_claiming.py`

Allowed changes:
- Add `claim --state STATE.json --run-id RUN --lock-timeout N --json`.
- Mark one pending or retryable item `in_progress`.
- Increment attempts and record run metadata on the item.
- Return exact claimed item context.

Non-goals:
- Do not implement task execution.
- Do not record RED/GREEN evidence.
- Do not bypass fresh locks.
- Do not claim more than one item.

#### Required repo discovery before editing
- Inspect legal status names in `state.py` and transition rules in `transitions.py`.
- Inspect lock acquisition behavior in `locking.py`.
- Inspect `status.py` for next eligible item ordering.

#### TDD / verification loop
1. Add failing tests proving the first pending item is claimed and attempts increment.
2. Add failing tests proving `failed_retryable` is eligible after pending items or according to the chosen documented ordering.
3. Add failing tests proving fresh locks prevent claims.
4. Add failing tests proving no eligible item returns a clean no-op JSON response.
5. Implement minimal claim logic.
6. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] Claim validates state before mutation.
- [ ] Claim respects fresh locks and reports the lock owner when available.
- [ ] Claim chooses one pending or retryable item deterministically.
- [ ] Claim updates counts and item metadata atomically.
- [ ] Claim returns item ID, title, plan path, Todoist ID/URL if present, and suggested next action.
- [ ] Tests and lint pass.

## Task 7: Add evidence record commands for RED, GREEN, full-suite, and lint gates

**Todoist:** `6gV9qjQMH26P8JCR`

### MiniMax implementation handoff

#### Objective
Add structured evidence recording commands so workers do not hand-write fragile `--evidence-json` strings.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/evidence.py`
- `src/stateful_dev/transitions.py`
- `tests/test_evidence_cli.py`
- `tests/test_transitions.py`

Allowed changes:
- Add `record red`, `record green`, `record full-suite`, and `record lint` commands.
- Store command, exit code, output or output-file reference, and normalized result fields.
- Reuse existing transition validation where possible.

Non-goals:
- Do not execute shell commands from `stateful-dev`; callers provide command/result evidence.
- Do not weaken RED/GREEN/full-suite validation.
- Do not change terminal state behavior to allow post-success evidence mutation.

#### Required repo discovery before editing
- Inspect `transition_item()` evidence requirements.
- Inspect existing transition tests for valid and invalid RED/GREEN examples.
- Inspect CLI JSON output conventions.

#### TDD / verification loop
1. Add failing tests for `record red` creating valid RED evidence from command, exit code, and output.
2. Add failing tests for `record green`, `record full-suite`, and `record lint` recording expected fields.
3. Add failing tests proving successful-looking RED and failure-looking GREEN/full-suite are rejected.
4. Implement minimal evidence normalization and command plumbing.
5. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] Record commands avoid nested JSON shell quoting for common evidence paths.
- [ ] RED evidence with exit code 0 is rejected unless an explicit allowed mode is added and tested.
- [ ] GREEN and full-suite evidence with nonzero exit codes are rejected.
- [ ] Lint evidence is stored separately from full-suite evidence.
- [ ] Existing `transition --evidence-json` remains compatible.
- [ ] Tests and lint pass.

## Task 8: Add lock status and stale-lock recovery commands

**Todoist:** `6gV9qjXphGrGmJV2`

### MiniMax implementation handoff

#### Objective
Expose safe lock inspection and stale-lock recovery commands.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/locking.py`
- `src/stateful_dev/lock_recovery.py`
- `tests/test_locking.py`
- `tests/test_lock_recovery_cli.py`

Allowed changes:
- Add `lock status --state STATE.json --json`.
- Add `lock recover --state STATE.json --stale-after-minutes N --backup --json`.
- Optionally add a flag to move stale `in_progress` items to `failed_retryable`.

Non-goals:
- Do not kill processes.
- Do not pause/resume cron jobs.
- Do not recover fresh locks.
- Do not mark work succeeded during recovery.

#### Required repo discovery before editing
- Inspect lock metadata shape in `locking.py`.
- Inspect state item statuses and count validation.
- Inspect backup behavior if Task 3 has already landed; reuse it instead of duplicating backup code.

#### TDD / verification loop
1. Add failing tests for `lock status` with no lock, fresh lock, and malformed metadata.
2. Add failing tests proving `lock recover` refuses fresh locks.
3. Add failing tests proving stale recovery backs up state before mutation.
4. Add failing tests for optional stale `in_progress` to `failed_retryable` recovery and count recomputation.
5. Implement minimal lock status/recovery helpers.
6. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] Lock status reports `held`, `run_id`, `acquired_at`, and stale/fresh classification when enough data exists.
- [ ] Recovery refuses fresh locks.
- [ ] Recovery writes a backup before changing state or lock files.
- [ ] Recovery validates state before and after mutation.
- [ ] Stale `in_progress` recovery never marks success.
- [ ] Tests and lint pass.

## Task 9: Add operator handoff CLI command

**Todoist:** `6gV9qjvFx9P8HXqR`

### MiniMax implementation handoff

#### Objective
Create a CLI command that renders standardized operator questions and fresh-agent handoff blocks.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/handoff.py`
- `tests/test_handoff_cli.py`

Allowed changes:
- Add `handoff` command with plain text and JSON output.
- Accept question, why, recommended answer, allowed next action, state path, item ID, and optional evidence bullets.

Non-goals:
- Do not send notifications.
- Do not call Discord, Todoist, or cron APIs.
- Do not mutate state.

#### Required repo discovery before editing
- Inspect `stateful-dev-cron` handoff format if available in local skill docs.
- Inspect `output.py` and existing rendering style.
- Inspect `status.py` plain output conventions.

#### TDD / verification loop
1. Add failing plain-output test that includes a copy/paste-ready block with project root, plan path, state path, item ID/title, question, evidence, and allowed next action.
2. Add failing JSON-output test for the same payload.
3. Implement minimal rendering helpers and CLI command.
4. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] Plain output is concise and copy/paste-ready for a fresh agent.
- [ ] JSON output preserves all fields for notification tooling.
- [ ] The command can derive item title and plan path from state when given `--state` and `--item-id`.
- [ ] Missing item IDs fail clearly.
- [ ] Tests and lint pass.

## Task 10: Add complete/audit command for safe worker shutdown decisions

**Todoist:** `6gV9qjwR7gfwv2X2`

### MiniMax implementation handoff

#### Objective
Implement a shutdown readiness audit that tells operators whether a worker can be paused/removed or needs follow-up planning.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/audit.py`
- `src/stateful_dev/status.py`
- `tests/test_audit_cli.py`

Allowed changes:
- Add `audit` or `complete` command. Prefer one canonical command plus an alias only if Typer support stays simple.
- Reuse `validate_state()` and lock/status helpers.
- Check latest gates when run summaries exist.

Non-goals:
- Do not pause/remove cron jobs.
- Do not push commits.
- Do not complete Todoist tasks.
- Do not infer product readiness from state counts alone.

#### Required repo discovery before editing
- Inspect `status.py` completion logic.
- Inspect `reports.py` and run summary shape if Task 5 has landed.
- Inspect state files in tests for terminal and non-terminal examples.

#### TDD / verification loop
1. Add failing tests for incomplete state with pending/retryable/active work.
2. Add failing tests for complete terminal state with clear lock and passing doctor.
3. Add failing tests for complete counts but missing/failed gate evidence where run summaries are available.
4. Implement minimal audit helper and CLI output.
5. Run focused tests, full suite, and lint.

#### Acceptance criteria
- [ ] Audit reports doctor result, lock state, non-terminal counts, latest gate summary, completion boolean, and suggested next action.
- [ ] Audit recommends pause/remove only when no active/retryable work remains and validation passes.
- [ ] Audit recommends follow-up plan when readiness gaps remain.
- [ ] Audit never mutates cron, Todoist, git, or state.
- [ ] Tests and lint pass.

## Task 11: Add deployment profile validation and worker prompt rendering

**Todoist:** `6gV9qm3rcg26qp9R`

### MiniMax implementation handoff

#### Objective
Validate deployment profiles and render self-contained worker prompts from profile/template inputs.

#### Scope
Likely files/modules:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/profiles.py`
- `src/stateful_dev/prompt_rendering.py`
- `tests/test_profiles.py`
- `tests/test_prompt_rendering.py`
- Existing templates/docs only if required for tests

Allowed changes:
- Add `profile validate` command.
- Add `prompt render` command.
- Validate fields for project root, plan paths, state path, gates, Todoist mapping, notification policy, cron permissions, commit policy, and push policy.

Non-goals:
- Do not create cron jobs.
- Do not write scheduler config.
- Do not read secrets or credentials.
- Do not add a template engine dependency unless unavoidable and justified.

#### Required repo discovery before editing
- Inspect skill template files if present under local skill directories or docs.
- Inspect existing JSON output helpers.
- Inspect current worker prompt requirements in `stateful-dev-cron` docs if available.

#### TDD / verification loop
1. Add failing profile validation tests for valid profile, missing required fields, nonexistent plan path, and unsafe cron permissions.
2. Add failing prompt render tests proving the output includes project root, plan paths, state path, gates, Todoist IDs, notification policy, and side-effect limits.
3. Implement minimal dataclass/dict validation and string rendering.
4. Run focused tests, full suite, lint, and `uv build` if packaging data changes.

#### Acceptance criteria
- [ ] Profile validation emits actionable JSON errors.
- [ ] Prompt rendering is deterministic for the same profile/template input.
- [ ] Rendered prompts include no secrets.
- [ ] Rendered prompts explicitly disable push and cron management unless the profile permits them.
- [ ] Tests, lint, and build when relevant pass.

## Task 12: Add Hermes plugin parity for stateful-dev lifecycle commands

**Todoist:** `6gV9qm6C4F5pXG72`

### MiniMax implementation handoff

#### Objective
Expose thin plugin tools for lifecycle commands already implemented in the CLI/library.

#### Scope
Likely files/modules:
- `plugins/stateful-dev/tools.py`
- `plugins/stateful-dev/schemas.py`
- `plugins/stateful-dev/__init__.py`
- `tests/test_plugin_tools.py`
- `tests/test_plugin_layout.py`
- Core `src/stateful_dev/*` files only when a missing library seam prevents a thin wrapper

Allowed changes:
- Add plugin tools for status, plan parse/lint, claim, record, transition, lock status/recover, handoff, and audit/complete as available.
- Reuse tested library functions; wrappers should validate inputs and return JSON-serializable payloads.

Non-goals:
- Do not duplicate CLI implementation logic in plugin files.
- Do not add plugin tools for unimplemented core commands.
- Do not change Hermes global config.
- Do not install or reload plugins as a side effect.

#### Required repo discovery before editing
- Inspect existing plugin tools and schemas.
- Inspect tests that verify plugin layout and tool return shapes.
- Inspect public library functions added by earlier tasks before writing wrappers.

#### TDD / verification loop
1. Add failing plugin tests for one representative lifecycle wrapper using existing library code.
2. Add schema/layout tests for the intended tool list.
3. Implement thin wrappers incrementally.
4. Run focused plugin tests, `uv run pytest -q`, `uv run ruff check .`, and `uv build`.

#### Acceptance criteria
- [ ] Plugin wrappers are thin and call core library functions.
- [ ] Plugin payloads are JSON-serializable and schema-validated where existing plugin conventions require it.
- [ ] Plugin tool names are stable and documented in tests.
- [ ] No global Hermes config or installed plugin state changes during tests.
- [ ] Tests, lint, and build pass.
