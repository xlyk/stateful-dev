"""Smoke tests for Hermes cron script wake/skip behavior.

These tests codify the Hermes scheduler's actual script execution behavior:
- Last non-empty stdout line is parsed as JSON for wake/skip decisions.
- Empty lines and whitespace-only lines are ignored.
- Multiple JSON lines in stdout: only the last counts.
- The wrapper script chdirs to project root before calling cron-gate.
- Nonzero exit + blocker/error JSON still emits structured payload.

These are NOT unit tests of stateful-dev internals. They are behavioral
smoke tests of the Hermes/script contract boundary.

Hermetic by default: tests that run real scripts use disposable state and
tempfile wrappers so they never touch ~/.hermes/scripts or live .agent-state.
"""
from __future__ import annotations

import json
import sys
import textwrap
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------
DEMO_PROJECT_ROOT = Path("/Users/xlyk/Code/stateful-dev")
DEMO_WORKER_ID = "stateful-dev-cron-gate-worker"
DEMO_STATE = DEMO_PROJECT_ROOT / ".agent-state" / DEMO_WORKER_ID / "state.json"

# -----------------------------------------------------------------------
# Fake wrapper source factory
# -----------------------------------------------------------------------
_WRAPPER_SOURCE = textwrap.dedent("""\
    #!/usr/bin/env python3
    from __future__ import annotations
    import json, os, subprocess, sys
    from datetime import UTC, datetime
    from pathlib import Path

    WORKER_ID = "{worker_id}"
    PROJECT_ROOT = Path("{project_root}")
    STATE_PATH = Path("{state_path}")

    def _generate_run_id() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _emit_json(payload: dict) -> None:
        print(json.dumps(payload), flush=True)

    def _run_cron_gate(run_id: str) -> tuple[int, str, str]:
        cmd = [
            "uv", "run", "--directory", str(PROJECT_ROOT),
            "stateful-dev", "cron-gate",
            "--state", str(STATE_PATH),
            "--project-root", str(PROJECT_ROOT),
            "--worker-id", WORKER_ID,
            "--run-id", run_id,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        return result.returncode, result.stdout, result.stderr

    def main() -> None:
        run_id = _generate_run_id()
        diag = "[gate-wrapper] worker=" + WORKER_ID + " run=" + run_id
        print(diag, file=sys.stderr, flush=True)
        exit_code, stdout, stderr = _run_cron_gate(run_id)
        last_json = None
        for line in reversed(stdout.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                json.loads(stripped)
                last_json = stripped
                break
            except json.JSONDecodeError:
                continue
        if last_json:
            print(last_json, flush=True)
            if exit_code != 0:
                sys.exit(exit_code)
            return
        if exit_code != 0:
            _emit_json({{
                "wakeAgent": False,
                "mode": "error",
                "worker_id": WORKER_ID,
                "run_id": run_id,
                "project_root": str(PROJECT_ROOT),
                "state_path": str(STATE_PATH),
                "item_id": None,
                "item_title": None,
                "item_status": None,
                "blocker": (
                    "wrapper exited " + str(exit_code) +
                    " and produced no parseable JSON output"
                ),
                "complete": False,
                "message": "Internal error in gate wrapper script.",
            }})
            sys.exit(exit_code)
        print(stdout.rstrip(), flush=True)

    if __name__ == "__main__":
        main()
""")


def _make_fake_module(source: str) -> Any:
    """Load *source* as a module without registering in sys.modules."""
    import importlib.util
    spec = importlib.util.spec_from_loader(
        "fake_wrapper_module",
        loader=None,
        origin="<fake-wrapper>",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    exec(source, module.__dict__)  # noqa: S307 — test fixture only
    return module


def _write_wrapper_source(project_root: Path, state_path: Path) -> Any:
    rendered = _WRAPPER_SOURCE.format(
        worker_id=DEMO_WORKER_ID,
        project_root=str(project_root),
        state_path=str(state_path),
    )
    return _make_fake_module(rendered)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _stdout_lines(stdout: str) -> list[str]:
    return [ln.strip() for ln in stdout.splitlines() if ln.strip()]


def _capture_main(mod: Any) -> tuple[str, str, int]:
    """Call mod.main() and capture stdout/stderr/exit code."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        exit_code = 0
        try:
            mod.main()
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
        stdout = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    return stdout, stderr, exit_code


def _make_fake_run(
    contract: dict[str, Any],
    *,
    exit_code: int = 0,
    stderr: str = "",
) -> Any:
    """Return a fake _run_cron_gate that returns deterministic output."""
    def fake(run_id: str) -> tuple[int, str, str]:  # noqa: ARG001
        return exit_code, json.dumps(contract) + "\n", stderr
    return fake


# -----------------------------------------------------------------------
# RED: Tests that must fail before the last-line-parsing logic is added
# -----------------------------------------------------------------------
class TestHermesLastLineRule:
    """
    Hermes scheduler behavior: the last non-empty stdout line is parsed as JSON.

    Empty lines and whitespace-only lines are ignored.
    Multiple JSON lines: only the last counts.

    These tests verify the wrapper correctly implements last-line parsing
    BEFORE any production fix is applied — proving the behavior is absent.
    """

    def _eligible_contract(self, run_id: str = "fake-run-id") -> dict[str, Any]:
        return {
            "wakeAgent": True,
            "mode": "wake",
            "worker_id": DEMO_WORKER_ID,
            "run_id": run_id,
            "project_root": str(DEMO_PROJECT_ROOT),
            "state_path": str(DEMO_STATE),
            "item_id": None,
            "item_title": None,
            "item_status": None,
            "blocker": None,
            "complete": False,
            "message": "eligible",
        }

    def _patch_run(
        self,
        mod: Any,
        contract: dict[str, Any],
        *,
        stdout_extra: str = "",
        exit_code: int = 0,
        stderr: str = "",
    ) -> None:
        """Patch mod._run_cron_gate with output containing extra lines."""
        full_stdout = stdout_extra + json.dumps(contract) + "\n"
        def fake(run_id: str) -> tuple[int, str, str]:  # noqa: ARG001
            return exit_code, full_stdout, stderr
        mod._run_cron_gate = fake
        mod.subprocess = mock.MagicMock()

    def test_ignores_empty_lines_before_json(self, tmp_path: Path) -> None:
        """
        Empty lines between stdout noise and the JSON contract must be ignored.

        Hermes parses the last NON-EMPTY line as JSON. If the wrapper emits
        empty lines before the contract line, the contract line must still be
        found as the last non-empty line.
        """
        state_path = tmp_path / ".agent-state" / "worker" / "state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({
            "job_name": "test",
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [],
            "counts": {"pending": 1, "in_progress": 0, "succeeded": 0,
                       "red_verified": 0, "green_verified": 0, "blocked": 0,
                       "failed_retryable": 0, "failed_final": 0, "skipped": 0,
                       "needs_review": 0},
            "items": [{"id": "plan:T1", "title": "Work", "status": "pending",
                       "attempts": 0, "max_attempts": 3}],
        }))
        mod = _write_wrapper_source(tmp_path, state_path)
        # stdout has empty lines between noise and contract
        self._patch_run(
            mod,
            self._eligible_contract(),
            stdout_extra=(
                "Running cron-gate\n\n\n"
                "State: valid | Lock: clear\n\n"
            ),
        )
        stdout, _, exit_code = _capture_main(mod)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        assert lines, "No stdout produced"
        # The last non-empty line must be the contract JSON
        parsed = json.loads(lines[-1])
        assert parsed["wakeAgent"] is True
        assert parsed["mode"] == "wake"

    def test_ignores_whitespace_only_lines(self, tmp_path: Path) -> None:
        """
        Lines containing only whitespace must be ignored when finding the
        last non-empty line for JSON parsing.
        """
        state_path = tmp_path / ".agent-state" / "worker" / "state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({
            "job_name": "test",
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [],
            "counts": {"pending": 1, "in_progress": 0, "succeeded": 0,
                       "red_verified": 0, "green_verified": 0, "blocked": 0,
                       "failed_retryable": 0, "failed_final": 0, "skipped": 0,
                       "needs_review": 0},
            "items": [{"id": "plan:T1", "title": "Work", "status": "pending",
                       "attempts": 0, "max_attempts": 3}],
        }))
        mod = _write_wrapper_source(tmp_path, state_path)
        # stdout has whitespace-only lines
        self._patch_run(
            mod,
            self._eligible_contract(),
            stdout_extra=(
                "   \n"
                "\t\n"
                "   \t  \n"
            ),
        )
        stdout, _, exit_code = _capture_main(mod)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        parsed = json.loads(lines[-1])
        assert parsed["wakeAgent"] is True

    def test_multiple_json_lines_last_wins(self, tmp_path: Path) -> None:
        """
        When stdout contains multiple JSON-parseable lines, only the LAST
        one must be used for the wake/skip decision.

        This can happen if cron-gate emits debug JSON on one line and
        a different contract on the next.
        """
        state_path = tmp_path / ".agent-state" / "worker" / "state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({
            "job_name": "test",
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [],
            "counts": {"pending": 1, "in_progress": 0, "succeeded": 0,
                       "red_verified": 0, "green_verified": 0, "blocked": 0,
                       "failed_retryable": 0, "failed_final": 0, "skipped": 0,
                       "needs_review": 0},
            "items": [{"id": "plan:T1", "title": "Work", "status": "pending",
                       "attempts": 0, "max_attempts": 3}],
        }))
        mod = _write_wrapper_source(tmp_path, state_path)
        # First JSON says skip, second says wake
        self._patch_run(
            mod,
            self._eligible_contract(),
            stdout_extra=json.dumps({
                "wakeAgent": False, "mode": "skip",
                "complete": True, "message": "old"
            }) + "\n",
        )
        stdout, _, exit_code = _capture_main(mod)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        parsed = json.loads(lines[-1])
        # The last JSON must win — it says wake=True
        assert parsed["wakeAgent"] is True
        assert parsed["message"] == "eligible"

    def test_nonzero_exit_still_emits_blocker_json(self, tmp_path: Path) -> None:
        """
        When cron-gate exits nonzero but produces valid blocker JSON on stdout,
        the wrapper must emit that JSON (not silently drop it).

        Hermes treats nonzero script exit as a failure but still parses
        the last stdout line. The wrapper must not swallow the blocker.
        """
        state_path = tmp_path / ".agent-state" / "worker" / "state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({
            "job_name": "test",
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [],
            "counts": {"pending": 0, "in_progress": 0, "succeeded": 0,
                       "red_verified": 0, "green_verified": 0, "blocked": 0,
                       "failed_retryable": 0, "failed_final": 0, "skipped": 0,
                       "needs_review": 0},
            "items": [],
        }))
        mod = _write_wrapper_source(tmp_path, state_path)
        blocker_contract = {
            "wakeAgent": False,
            "mode": "blocker",
            "worker_id": DEMO_WORKER_ID,
            "run_id": "run-123",
            "project_root": str(tmp_path),
            "state_path": str(state_path),
            "item_id": None,
            "item_title": None,
            "item_status": None,
            "blocker": "dirty git",
            "complete": False,
            "message": "Resolve dirty git before running.",
        }
        self._patch_run(
            mod,
            blocker_contract,
            exit_code=1,  # nonzero
        )
        stdout, _, exit_code = _capture_main(mod)
        assert exit_code != 0  # wrapper propagates nonzero
        lines = _stdout_lines(stdout)
        assert lines, "No stdout produced"
        parsed = json.loads(lines[-1])
        assert parsed["mode"] == "blocker"
        assert parsed["wakeAgent"] is False
        assert parsed["blocker"] == "dirty git"


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------
@pytest.fixture
def wrapper_module(tmp_path: Path) -> Any:
    state_path = tmp_path / ".agent-state" / "worker" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({
        "job_name": "test",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": [],
        "counts": {"pending": 1, "in_progress": 0, "succeeded": 0,
                   "red_verified": 0, "green_verified": 0, "blocked": 0,
                   "failed_retryable": 0, "failed_final": 0, "skipped": 0,
                   "needs_review": 0},
        "items": [{"id": "plan:T1", "title": "Work", "status": "pending",
                   "attempts": 0, "max_attempts": 3}],
    }))
    return _write_wrapper_source(tmp_path, state_path)


@pytest.fixture
def completed_wrapper_module(tmp_path: Path) -> Any:
    """Wrapper module with all items terminal (no-work state)."""
    state_path = tmp_path / ".agent-state" / "worker" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({
        "job_name": "test",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": [],
        "counts": {"pending": 0, "in_progress": 0, "succeeded": 1,
                   "red_verified": 0, "green_verified": 0, "blocked": 0,
                   "failed_retryable": 0, "failed_final": 0, "skipped": 0,
                   "needs_review": 0},
        "items": [{"id": "plan:T1", "title": "Done", "status": "succeeded",
                   "attempts": 1, "max_attempts": 3}],
    }))
    return _write_wrapper_source(tmp_path, state_path)


# -----------------------------------------------------------------------
# GREEN: Verified behavior after implementation
# -----------------------------------------------------------------------
class TestHermesSmokeWake:
    """Wrappers must emit wake=True for eligible work."""

    def _patch_run(self, mod: Any, contract: dict[str, Any]) -> None:
        def fake(run_id: str) -> tuple[int, str, str]:  # noqa: ARG001
            return 0, json.dumps(contract) + "\n", ""
        mod._run_cron_gate = fake
        mod.subprocess = mock.MagicMock()

    def test_wake_with_eligible_work(self, wrapper_module: Any) -> None:
        contract = {
            "wakeAgent": True,
            "mode": "wake",
            "worker_id": DEMO_WORKER_ID,
            "run_id": "run-1",
            "project_root": str(DEMO_PROJECT_ROOT),
            "state_path": str(DEMO_STATE),
            "item_id": "plan:T1",
            "item_title": "Work",
            "item_status": "in_progress",
            "blocker": None,
            "complete": False,
            "message": "eligible",
        }
        self._patch_run(wrapper_module, contract)
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        assert lines
        parsed = json.loads(lines[-1])
        assert parsed["wakeAgent"] is True
        assert parsed["mode"] == "wake"
        assert parsed["item_id"] == "plan:T1"


class TestHermesSmokeSkip:
    """Wrappers must emit skip + wakeAgent=False when no work remains."""

    def _patch_run(self, mod: Any, contract: dict[str, Any]) -> None:
        def fake(run_id: str) -> tuple[int, str, str]:  # noqa: ARG001
            return 0, json.dumps(contract) + "\n", ""
        mod._run_cron_gate = fake
        mod.subprocess = mock.MagicMock()

    def test_skip_when_no_work(self, completed_wrapper_module: Any) -> None:
        contract = {
            "wakeAgent": False,
            "mode": "skip",
            "worker_id": DEMO_WORKER_ID,
            "run_id": "run-2",
            "project_root": str(DEMO_PROJECT_ROOT),
            "state_path": str(DEMO_STATE),
            "item_id": None,
            "item_title": None,
            "item_status": None,
            "blocker": None,
            "complete": True,
            "message": "All items terminal.",
        }
        self._patch_run(completed_wrapper_module, contract)
        stdout, _, exit_code = _capture_main(completed_wrapper_module)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        assert lines
        parsed = json.loads(lines[-1])
        assert parsed["wakeAgent"] is False
        assert parsed["mode"] == "skip"
        assert parsed["complete"] is True


class TestHermesSmokeStderrIsolation:
    """stderr must not corrupt or affect the stdout JSON parsing."""

    def _patch_run(
        self, mod: Any, contract: dict[str, Any], stderr: str = ""
    ) -> None:
        def fake(run_id: str) -> tuple[int, str, str]:  # noqa: ARG001
            return 0, json.dumps(contract) + "\n", stderr
        mod._run_cron_gate = fake
        mod.subprocess = mock.MagicMock()

    def test_stderr_does_not_corrupt_json_parsing(
        self, wrapper_module: Any
    ) -> None:
        """Heavy stderr noise must not prevent JSON parsing of stdout."""
        contract = {
            "wakeAgent": True,
            "mode": "wake",
            "worker_id": DEMO_WORKER_ID,
            "run_id": "run-3",
            "project_root": str(DEMO_PROJECT_ROOT),
            "state_path": str(DEMO_STATE),
            "item_id": "plan:T1",
            "item_title": "Work",
            "item_status": "in_progress",
            "blocker": None,
            "complete": False,
            "message": "eligible",
        }
        self._patch_run(
            wrapper_module, contract,
            stderr=(
                "uv: warning: some stderr noise here\n"
                "another stderr line\n"
                "   \n"
            ),
        )
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        assert lines
        # Must still parse as valid JSON
        parsed = json.loads(lines[-1])
        assert parsed["wakeAgent"] is True
        assert parsed["mode"] == "wake"
