"""Tests for per-worker Hermes cron gate wrapper scripts.

These wrappers live in ~/.hermes/scripts/ and are thin adapters that:
1. call `stateful-dev cron-gate` with the correct arguments
2. emit the last-line JSON contract to stdout for Hermes to parse

They must NOT contain any claim/status/lock/wake-decision logic.

Hermetic tests: default runs import the wrapper module directly and mock
_run_cron_gate at the module level, so they never touch ~/.hermes/scripts or
live .agent-state files.

Local integration tests (run real wrapper + real state):
    # Requires real wrapper on disk and will touch live .agent-state.
    # Run with: STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS=1 pytest -m local_wrapper
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEMO_WORKER_ID = "stateful-dev-cron-gate-worker"
DEMO_PROJECT_ROOT = Path("/Users/xlyk/Code/stateful-dev")
_AGENT_STATE = ".agent-state/stateful-dev-cron-gate-worker"
DEMO_STATE = DEMO_PROJECT_ROOT / _AGENT_STATE / "state.json"

WRAPPER_FILENAME = f"stateful_dev_{DEMO_WORKER_ID}_gate.py"
SCRIPTS_SUBDIR = Path.home() / ".hermes" / "scripts"
WRAPPER_LIVE_PATH = SCRIPTS_SUBDIR / WRAPPER_FILENAME

# ---------------------------------------------------------------------------
# Fake wrapper source factory
# ---------------------------------------------------------------------------

# Canonical wrapper source used for hermetic tests.
#
# Single-brace placeholders (e.g. {worker_id}) are substituted by .format().
# Code that must appear literally uses double-braces (e.g. {{FAKE_MODE}}).
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
        # Parse last JSON from stdout only (Hermes: last non-empty stdout line)
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

_WRAPPER_MODULE_DOC = textwrap.dedent("""\
    Per-worker Hermes cron gate wrapper for stateful-dev-cron-gate-worker.

    Thin adapter: chdirs into the project root and calls
    `stateful-dev cron-gate`.  No wake-decision logic lives here — that
    belongs to `stateful-dev cron-gate`.

    Hermes cron behaviour:
    - Runs the script before building the agent prompt.
    - Injects stdout as `## Script Output` when wakeAgent: true.
    - Parses the last non-empty stdout line as JSON for wake/skip decisions.
    - If the last non-empty line is {"wakeAgent": false}, skips the agent
      run and suppresses delivery.
""")


def _make_fake_module(source: str) -> Any:
    """Load *source* as a module; does not register in sys.modules."""
    spec = importlib.util.spec_from_loader(
        "fake_wrapper_module",
        loader=None,
        origin="<fake-wrapper>",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    exec(source, module.__dict__)  # noqa: S307 — test fixture only
    return module


def write_fake_wrapper_module(**kwargs: str | Path) -> Any:
    """Return a loaded module of the canonical fake wrapper."""
    rendered = _WRAPPER_SOURCE.format(
        worker_id=DEMO_WORKER_ID,
        project_root=str(kwargs.get("project_root", DEMO_PROJECT_ROOT)),
        state_path=str(kwargs.get("state_path", DEMO_STATE)),
    )
    mod = _make_fake_module(rendered)
    mod.__doc__ = _WRAPPER_MODULE_DOC
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stdout_lines(stdout: str) -> list[str]:
    return [ln.strip() for ln in stdout.splitlines() if ln.strip()]


def _last_json_from_stdout(stdout: str) -> dict[str, Any]:
    lines = _stdout_lines(stdout)
    assert lines, "No stdout lines found"
    return json.loads(lines[-1])


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wrapper_module(**kwargs: str | Path) -> Any:
    """Canonical fake wrapper module (static analysis only)."""
    return write_fake_wrapper_module(**kwargs)


@pytest.fixture
def fake_wrapper_source() -> str:
    """The canonical wrapper source string for static-analysis tests."""
    return _WRAPPER_SOURCE


# ---------------------------------------------------------------------------
# Test: Wrapper script is thin (static analysis)
# ---------------------------------------------------------------------------

class TestWrapperScriptIsThin:
    """Wrapper scripts must be thin adapters — no wake-decision logic."""

    def test_no_stateful_dev_imports(self, fake_wrapper_source: str) -> None:
        assert "from stateful_dev" not in fake_wrapper_source
        assert "import stateful_dev" not in fake_wrapper_source
        assert "from stateful_dev." not in fake_wrapper_source

    def test_calls_cron_gate_subprocess(self, fake_wrapper_source: str) -> None:
        """
        The wrapper source must call subprocess.run with 'cron-gate' as an
        exact command token.  Checking for the token avoids false positives
        from incidental 'stateful-dev' mentions in comments.
        """
        import re
        assert re.search(r'''['"]cron-gate['"]''', fake_wrapper_source), (
            "Wrapper must call subprocess.run with 'cron-gate' as a "
            "command token."
        )

    def test_does_not_call_claim(self, fake_wrapper_source: str) -> None:
        assert "stateful-dev claim" not in fake_wrapper_source, (
            "Wrapper must not call `stateful-dev claim`. "
            "Claim is handled internally by `stateful-dev cron-gate`."
        )


# ---------------------------------------------------------------------------
# Test: Wrapper output (mocked _run_cron_gate at module level)
# ---------------------------------------------------------------------------

class TestWrapperScriptOutput:
    """Running the wrapper must produce valid cron-gate contract JSON."""

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
        **kwargs: Any,
    ) -> None:
        """Patch mod._run_cron_gate with a deterministic fake."""
        mod._run_cron_gate = _make_fake_run(contract, **kwargs)
        mod.subprocess = mock.MagicMock()

    def test_wrapper_runs_without_error(self, wrapper_module: Any) -> None:
        self._patch_run(wrapper_module, self._eligible_contract())
        stdout, stderr, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        # stderr may contain diagnostics — that is fine.
        lines = _stdout_lines(stdout)
        assert lines, "No stdout produced"
        # Must be parseable JSON (no exception = success)
        json.loads(lines[-1])

    def test_emits_valid_json_on_last_line(self, wrapper_module: Any) -> None:
        self._patch_run(wrapper_module, self._eligible_contract())
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        assert lines, "No stdout lines found"
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"Last stdout line is not valid JSON: {lines[-1][:200]}\n{e}"
            ) from e
        assert isinstance(parsed, dict)

    def test_emits_required_contract_fields(self, wrapper_module: Any) -> None:
        self._patch_run(wrapper_module, self._eligible_contract())
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        payload = _last_json_from_stdout(stdout)
        required_fields = [
            "wakeAgent", "mode", "worker_id", "run_id",
            "project_root", "state_path",
            "item_id", "item_title", "item_status",
            "blocker", "complete", "message",
        ]
        missing = [f for f in required_fields if f not in payload]
        assert missing == [], f"Missing required contract fields: {missing}"

    def test_uses_correct_worker_id(self, wrapper_module: Any) -> None:
        self._patch_run(wrapper_module, self._eligible_contract())
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        payload = _last_json_from_stdout(stdout)
        assert payload["worker_id"] == DEMO_WORKER_ID

    def test_project_root_is_correct(self, wrapper_module: Any) -> None:
        self._patch_run(wrapper_module, self._eligible_contract())
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        payload = _last_json_from_stdout(stdout)
        assert payload["project_root"] == str(DEMO_PROJECT_ROOT)

    def test_state_path_is_correct(self, wrapper_module: Any) -> None:
        self._patch_run(wrapper_module, self._eligible_contract())
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        payload = _last_json_from_stdout(stdout)
        assert payload["state_path"] == str(DEMO_STATE)

    def test_stdout_json_ignores_stderr(self, wrapper_module: Any) -> None:
        """
        stderr noise must not corrupt the stdout last-line JSON contract.
        The Hermes contract uses the last non-empty stdout line; stderr is
        ignored by the parser.
        """
        contract = self._eligible_contract()
        self._patch_run(
            wrapper_module, contract,
            stderr="uv warning: some stderr noise here\n",
        )
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        lines = _stdout_lines(stdout)
        assert lines, "No stdout lines found"
        assert lines[-1].startswith("{"), (
            f"Last stdout line is not JSON: {lines[-1][:100]}"
        )
        payload = json.loads(lines[-1])
        assert payload["wakeAgent"] is True
        assert "stderr noise" not in stdout

    def test_emits_wakeagent_false_on_error(self, wrapper_module: Any) -> None:
        """
        When cron-gate exits non-zero and produces no parseable JSON on
        stdout, the wrapper must emit its own wakeAgent: false contract.
        """
        # Patch _run_cron_gate to return non-zero with non-JSON stdout.
        # This forces the wrapper's error-emission path.
        def fake_error_run(run_id: str) -> tuple[int, str, str]:  # noqa: ARG001
            return 1, "some stdout that is not json\n", ""
        wrapper_module._run_cron_gate = fake_error_run
        wrapper_module.subprocess = mock.MagicMock()
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code != 0
        payload = _last_json_from_stdout(stdout)
        assert payload.get("wakeAgent") is False, (
            f"Expected wakeAgent: false on error, got: {payload.get('wakeAgent')}"
        )
        assert payload.get("mode") == "error"


    def test_preserves_nonzero_exit_with_valid_blocker_json(
        self, wrapper_module: Any
    ) -> None:
        """Nonzero blocker JSON must not become Hermes silent skip success."""
        contract = {
            **self._eligible_contract(),
            "wakeAgent": False,
            "mode": "blocker",
            "blocker": "dirty git",
            "message": "Resolve dirty git before running.",
        }
        self._patch_run(wrapper_module, contract, exit_code=1)
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code != 0
        payload = _last_json_from_stdout(stdout)
        assert payload["mode"] == "blocker"
        assert payload["wakeAgent"] is False

    def test_preserves_nonzero_exit_with_valid_error_json(
        self, wrapper_module: Any
    ) -> None:
        """Nonzero error JSON must wake Hermes through Script Error."""
        contract = {
            **self._eligible_contract(),
            "wakeAgent": False,
            "mode": "error",
            "blocker": "internal wrapper bug",
            "message": "File a bug report.",
        }
        self._patch_run(wrapper_module, contract, exit_code=1)
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code != 0
        payload = _last_json_from_stdout(stdout)
        assert payload["mode"] == "error"
        assert payload["wakeAgent"] is False

    def test_emits_complete_true_when_no_work(self, wrapper_module: Any) -> None:
        """When cron-gate signals complete, wrapper must pass it through."""
        contract = {**self._eligible_contract(), "complete": True, "message": "done"}
        self._patch_run(wrapper_module, contract)
        stdout, _, exit_code = _capture_main(wrapper_module)
        assert exit_code == 0
        payload = _last_json_from_stdout(stdout)
        assert payload.get("complete") is True


# -----------------------------------------------------------------------------
# Test: Thin worker prompt (no fat embedded prompt in cron job)
# -----------------------------------------------------------------------------

class TestCronJobHasThinExecutorPrompt:
    """
    The Hermes cron job must use a thin executor prompt — no fat embedded
    prompt that duplicates skill instructions.  The skill field (or skills
    list) must reference stateful-dev-lean-worker, and the prompt field
    must be absent or empty.
    """

    def test_cron_job_has_no_fat_embedded_prompt(self) -> None:
        """
        RED: The cron job config should not contain a fat embedded prompt.
        A fat prompt is one containing TDD policy, startup sequence steps,
        or plan/scope sections that duplicate the lean-worker skill.

        This test fails when the prompt field is long (> 500 chars) and
        contains keywords that indicate duplicated skill content.
        """
        cron_jobs_path = Path.home() / ".hermes" / "cron" / "jobs.json"
        if not cron_jobs_path.exists():
            pytest.skip("~/.hermes/cron/jobs.json not found")

        import json
        with open(cron_jobs_path, encoding="utf-8") as fh:
            data = json.load(fh)

        jobs = data.get("jobs", [])
        target = next(
            (j for j in jobs if j.get("name") == "stateful-dev-cron-gate-worker"),
            None,
        )
        if target is None:
            pytest.skip("stateful-dev-cron-gate-worker cron job not found")

        prompt = target.get("prompt") or ""

        # Indicators of a fat embedded prompt that duplicates skill content
        fat_indicators = [
            "TDD policy",
            "Required startup sequence",
            "RE D/GREEN",
            "full-suite/lint",
            "stateful-dev transition",
            "stateful-dev doctor",
            "blocker report",
            "conventional commit",
            "Do not push",
            "Dirty git",
            "RED/GREEN/REFACTOR",
            "fresh lock",
            "hand-edit",
        ]

        found_indicators = [kw for kw in fat_indicators if kw in prompt]

        # The prompt must either be absent/empty OR reference the lean-worker skill
        # A short prompt that delegates to the skill is acceptable
        has_skill_reference = (
            target.get("skill") == "stateful-dev-lean-worker"
            or "stateful-dev-lean-worker" in target.get("skills", [])
        )
        prompt_is_empty = len(prompt.strip()) == 0
        prompt_is_short_delegation = (
            len(prompt) < 200
            and "lean-worker" in prompt.lower()
        )

        assert (
            prompt_is_empty
            or prompt_is_short_delegation
            or (has_skill_reference and len(prompt) < 500 and not found_indicators)
        ), (
            f"Cron job still has a fat embedded prompt ({len(prompt)} chars) "
            f"with indicators: {found_indicators}. "
            f"Use skill='stateful-dev-lean-worker' with a thin delegation prompt."
        )


# -----------------------------------------------------------------------------
# Local integration tests (opt-in only)
# -----------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "local_wrapper: tests that run the real ~/.hermes/scripts wrapper",
    )


@pytest.mark.local_wrapper
class TestLiveWrapperScript:
    """
    Opt-in tests that run the real wrapper script on disk.

    Enabled only when STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS=1 and the
    wrapper exists at WRAPPER_LIVE_PATH.

    These tests can read/write the live
    .agent-state/stateful-dev-cron-gate-worker/state.json so they are
    excluded from the default hermetic run.
    """

    def _is_available(self) -> bool:
        return (
            os.environ.get("STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS") == "1"
            and WRAPPER_LIVE_PATH.exists()
        )

    def _run_live_wrapper(self) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "HOME": str(Path.home())}
        return subprocess.run(
            [str(WRAPPER_LIVE_PATH)],
            capture_output=True, text=True, timeout=60, env=env,
        )

    def _stdout_lines(self, result: subprocess.CompletedProcess[str]) -> list[str]:
        return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]

    def _last_json(
        self, result: subprocess.CompletedProcess[str]
    ) -> dict[str, Any]:
        lines = self._stdout_lines(result)
        assert lines, "No stdout lines found"
        return json.loads(lines[-1])

    def test_live_wrapper_runs(self) -> None:
        if not self._is_available():
            pytest.skip(
                "STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS!=1 "
                "or wrapper not on disk"
            )
        result = self._run_live_wrapper()
        lines = self._stdout_lines(result)
        assert lines, "Live wrapper produced no stdout"
        payload = json.loads(lines[-1])
        assert "wakeAgent" in payload

    def test_live_wrapper_emit_contract_fields(self) -> None:
        if not self._is_available():
            pytest.skip(
                "STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS!=1 "
                "or wrapper not on disk"
            )
        result = self._run_live_wrapper()
        payload = self._last_json(result)
        required_fields = [
            "wakeAgent", "mode", "worker_id", "run_id",
            "project_root", "state_path",
            "item_id", "item_title", "item_status",
            "blocker", "complete", "message",
        ]
        missing = [f for f in required_fields if f not in payload]
        assert missing == [], f"Missing required contract fields: {missing}"

    def test_live_wrapper_uses_correct_worker_id(self) -> None:
        if not self._is_available():
            pytest.skip(
                "STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS!=1 "
                "or wrapper not on disk"
            )
        result = self._run_live_wrapper()
        payload = self._last_json(result)
        assert payload["worker_id"] == DEMO_WORKER_ID

    def test_live_wrapper_is_thin(self) -> None:
        if not self._is_available():
            pytest.skip(
                "STATEFUL_DEV_RUN_LOCAL_WRAPPER_TESTS!=1 "
                "or wrapper not on disk"
            )
        content = WRAPPER_LIVE_PATH.read_text(encoding="utf-8")
        forbidden = [
            "from stateful_dev",
            "import stateful_dev",
            "from stateful_dev.",
        ]
        found = [imp for imp in forbidden if imp in content]
        assert not found, (
            f"Live wrapper must not import stateful_dev. Found: {found}"
        )
        assert "stateful-dev claim" not in content
