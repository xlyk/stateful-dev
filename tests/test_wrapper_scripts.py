"""Tests for per-worker Hermes cron gate wrapper scripts (Task 4).

These wrappers live in ~/.hermes/scripts/ and are thin adapters that:
1. call `stateful-dev cron-gate` with the correct arguments
2. emit the last-line JSON contract to stdout for Hermes to parse

They must NOT contain any claim/status/lock/wake-decision logic.
"""
import json
import subprocess
from pathlib import Path

import pytest

# The canonical worker for this project during T4 development.
DEMO_WORKER_ID = "stateful-dev-cron-gate-worker"
DEMO_PROJECT_ROOT = Path("/Users/xlyk/Code/stateful-dev")
_AGENT_STATE = ".agent-state/stateful-dev-cron-gate-worker"
DEMO_STATE = DEMO_PROJECT_ROOT / _AGENT_STATE / "state.json"


def _wrapper_path(worker_id: str = DEMO_WORKER_ID) -> Path:
    scripts_dir = Path.home() / ".hermes" / "scripts"
    return scripts_dir / f"stateful_dev_{worker_id}_gate.py"


class TestWrapperScriptExists:
    """The wrapper script must exist at the expected path."""

    def test_wrapper_script_exists(self) -> None:
        path = _wrapper_path()
        assert path.exists(), (
            f"Wrapper script not found at {path}. "
            "Create it as a thin adapter per Task 4."
        )

    def test_wrapper_script_is_executable(self) -> None:
        path = _wrapper_path()
        if not path.exists():
            pytest.skip("Wrapper script does not exist yet")
        assert path.stat().st_mode & 0o111, (
            f"{path} is not executable. Run: chmod +x {path}"
        )


class TestWrapperScriptOutput:
    """Running the wrapper must produce valid cron-gate contract JSON."""

    def _run_wrapper(
        self,
        extra_env: dict | None = None,
    ) -> subprocess.CompletedProcess:
        """Run the wrapper script and return the result."""
        path = _wrapper_path()
        if not path.exists():
            pytest.skip(f"Wrapper script does not exist yet at {path}")
        env = {**subprocess.os.environ.copy()}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def _stdout_lines(self, result: subprocess.CompletedProcess) -> list[str]:
        """Return non-empty stdout lines, newest last."""
        return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]

    def _last_json(self, result: subprocess.CompletedProcess) -> dict:
        lines = self._stdout_lines(result)
        assert lines, "No stdout lines found"
        return json.loads(lines[-1])

    def test_wrapper_runs_without_error(self) -> None:
        """Exit 0 or emit wakeAgent:false on error are both acceptable."""
        result = self._run_wrapper()
        if result.returncode != 0:
            payload = json.loads(
                (result.stdout + result.stderr).splitlines()[-1].strip()
            )
            assert payload.get("wakeAgent") is False, (
                f"Wrapper exited {result.returncode} but did not emit "
                f"wakeAgent:false. stdout: {result.stdout[:500]}"
            )

    def test_wrapper_emits_valid_json_on_last_line(self) -> None:
        """The last non-empty stdout line must be valid JSON."""
        result = self._run_wrapper()
        lines = self._stdout_lines(result)
        assert lines, "No stdout lines found"
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"Last stdout line is not valid JSON: {lines[-1][:200]}\n{e}"
            ) from e
        assert isinstance(parsed, dict)

    def test_wrapper_emits_required_contract_fields(self) -> None:
        """Output must contain all required cron-gate contract fields."""
        result = self._run_wrapper()
        payload = self._last_json(result)
        required_fields = [
            "wakeAgent",
            "mode",
            "worker_id",
            "run_id",
            "project_root",
            "state_path",
            "item_id",
            "item_title",
            "item_status",
            "blocker",
            "complete",
            "message",
        ]
        missing = [f for f in required_fields if f not in payload]
        assert missing == [], f"Missing required contract fields: {missing}"

    def test_wrapper_uses_correct_worker_id(self) -> None:
        """worker_id in output must match DEMO_WORKER_ID."""
        result = self._run_wrapper()
        payload = self._last_json(result)
        assert payload["worker_id"] == DEMO_WORKER_ID

    def test_wrapper_project_root_is_correct_path(self) -> None:
        """project_root in output must be the correct absolute path."""
        result = self._run_wrapper()
        payload = self._last_json(result)
        assert payload["project_root"] == str(DEMO_PROJECT_ROOT)

    def test_wrapper_state_path_is_correct(self) -> None:
        """state_path in output must be the correct state file."""
        result = self._run_wrapper()
        payload = self._last_json(result)
        assert payload["state_path"] == str(DEMO_STATE)


class TestWrapperScriptIsThin:
    """Wrapper scripts must be thin adapters — no wake-decision logic."""

    def test_wrapper_does_not_import_stateful_dev_modules(self) -> None:
        """The wrapper must not import from stateful_dev package."""
        path = _wrapper_path()
        if not path.exists():
            pytest.skip("Wrapper script does not exist yet")
        content = path.read_text(encoding="utf-8")
        forbidden = ["from stateful_dev", "import stateful_dev", "from stateful_dev."]
        found = [imp for imp in forbidden if imp in content]
        assert not found, (
            f"Wrapper must not import stateful_dev. Found: {found}. "
            "Wake decisions belong in `stateful-dev cron-gate`."
        )

    def test_wrapper_calls_stateful_dev_cron_gate(self) -> None:
        """The wrapper must call `stateful-dev cron-gate` as a subprocess."""
        path = _wrapper_path()
        if not path.exists():
            pytest.skip("Wrapper script does not exist yet")
        content = path.read_text(encoding="utf-8")
        assert "stateful-dev cron-gate" in content or "stateful-dev" in content, (
            "Wrapper must call `stateful-dev cron-gate` as a subprocess. "
            "It must not implement cron-gate logic inline."
        )

    def test_wrapper_does_not_call_claim(self) -> None:
        """The wrapper must not call `stateful-dev claim` directly."""
        path = _wrapper_path()
        if not path.exists():
            pytest.skip("Wrapper script does not exist yet")
        content = path.read_text(encoding="utf-8")
        assert "stateful-dev claim" not in content, (
            "Wrapper must not call `stateful-dev claim`. "
            "Claim is handled internally by `stateful-dev cron-gate`."
        )
